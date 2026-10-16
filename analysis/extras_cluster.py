"""Extras (cluster): e1 X13 semantic probes in Kubernetes, e2 X14 partial readiness, e3 X15 cache tier, e4 X31 lazy vs eager,
e5 X12 MTTR decomposition, e6 X30 database faults, e7 X09 hop timing, e8 X22/X19 frontend badge + input guard.
Appends to results/extras_cluster.jsonl.   INFER_TAG=9 FRONT_TAG=3 python analysis/extras_cluster.py --only e1 e2 ...
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run  # noqa: E402
import run_operator as ro  # noqa: E402

OUT = os.path.join(ROOT, 'results', 'extras_cluster.jsonl')
K = run.kube


def save(row):
    row['ts'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    open(OUT, 'a').write(json.dumps(row, default=str) + '\n')
    print(json.dumps(row, default=str)[:300], flush=True)


def set_probes(readiness, liveness):
    ops = []
    for kind, path in (('readinessProbe', readiness), ('livenessProbe', liveness)):
        ops.append({'op': 'replace', 'path': f'/spec/template/spec/containers/0/{kind}/httpGet/path', 'value': path})
    K('-n', run.KNS, 'patch', 'deploy/inference-api', '--type=json', '-p', json.dumps(ops))
    time.sleep(8)
    ro.wait_ready()


def probe(fault, window, rps='5', path='/predict?model=auto&steps=6', no_heal=True):
    args = ['--mode', 'silent', '--base', 'http://inference-api:5001', '--probe-path', path, '--fault', fault, '--rps', rps,
            '--warmup', '10', '--fault-window', str(window), '--heal-window', '2']
    if no_heal:
        args.append('--no-heal')
    res = run.run_probe('E4', args)
    return res[0] if res else {}


def heal():
    try:
        ro.pod_get('/fault?mode=heal')
    except Exception:
        pass


def e1():
    """X13: semantic probes wired into Kubernetes. D1 default probes | D3 readiness=semantic | D2 readiness+liveness=semantic."""
    variants = {'D1_default': ('/health/ready', '/health/live'), 'D3_semantic_readiness': ('/health/semantic', '/health/live'),
                'D2_semantic_readiness_and_liveness': ('/health/semantic', '/health/semantic')}
    for name, (rd, lv) in variants.items():
        set_probes(rd, lv)
        for fault in ('corrupt', 'unitchange'):
            for t in range(3):
                ro.wait_ready()
                heal()
                time.sleep(8)
                r = probe(fault, 140)
                save({'exp': 'e1_semantic_probes', 'variant': name, 'fault': fault, 'trial': t + 1, 'restored_s': r.get('restored_s'),
                      'fault_window': r.get('fault_window')})
                heal()
    set_probes('/health/ready', '/health/live')


def e2():
    """X14: partial readiness. Strict readiness vs ?partial=1 when one variable's LSTM model disappears."""
    for name, rd in (('strict', '/health/ready'), ('partial', '/health/ready?partial=1')):
        set_probes(rd, '/health/live')
        for t in range(3):
            ro.wait_ready()
            heal()
            time.sleep(8)
            r = probe('dropvar', 60)
            save({'exp': 'e2_partial_readiness', 'variant': name, 'trial': t + 1, 'fault_window': r.get('fault_window')})
            heal()
    set_probes('/health/ready', '/health/live')


def e3():
    """X15: cache tier exercised (climatology disabled, every model faulty)."""
    K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'DISABLE_CLIMATOLOGY=1')
    time.sleep(8)
    ro.wait_ready()
    time.sleep(10)
    for t in range(3):
        heal()
        pod_ok = ro.pod_get('/predict?model=auto&steps=6')          # populate the last-good cache
        r = probe('unitchange', 60)
        save({'exp': 'e3_cache_tier', 'trial': t + 1, 'fault_window': r.get('fault_window'), 'note': 'degraded % = cache answers'})
        heal()
    K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'DISABLE_CLIMATOLOGY-')
    ro.wait_ready()


def e4():
    """X31: lazy vs eager LSTM loading: time to ready and first-request latency."""
    for mode in ('eager', 'lazy'):
        for t in range(3):
            K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', f'LOAD_MODE={mode}')
            t0 = time.time()
            K('-n', run.KNS, 'rollout', 'restart', 'deploy/inference-api')
            time.sleep(5)
            ro.wait_ready()
            ready_s = time.time() - t0
            t1 = time.time()
            ro.pod_get('/predict?model=lstm&steps=6')
            first = time.time() - t1
            t2 = time.time()
            ro.pod_get('/predict?model=lstm&steps=6')
            second = time.time() - t2
            save({'exp': 'e4_load_mode', 'mode': mode, 'trial': t + 1, 'time_to_ready_s': round(ready_s, 1),
                  'first_lstm_request_s': round(first, 2), 'second_lstm_request_s': round(second, 2)})
    K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'LOAD_MODE=eager')
    ro.wait_ready()


def _pod_json():
    r = K('-n', run.KNS, 'get', 'pods', '-l', 'app=inference-api', '-o', 'json')
    return json.loads(r.stdout)['items'][0]


def _ts(s):
    import datetime
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def e5():
    """X12: MTTR decomposition for crash: container restart delay, ready delay, app start-up, client-observed recovery."""
    K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'SEMANTIC_GUARD=0')
    ro.wait_ready()
    for t in range(5):
        ro.wait_ready()
        time.sleep(10)
        res = run.run_probe('E4', ['--mode', 'fault', '--base', 'http://inference-api:5001', '--probe-path',
                                   '/predict?model=lstm&steps=3', '--fault', 'crash', '--timeout', '200'])
        r = res[0] if res else {}
        time.sleep(5)
        pod = _pod_json()
        cs = pod['status']['containerStatuses'][0]
        fin = _ts(cs['lastState']['terminated']['finishedAt']) if cs.get('lastState', {}).get('terminated') else None
        started = _ts(cs['state']['running']['startedAt'])
        ready = next((_ts(c['lastTransitionTime']) for c in pod['status']['conditions'] if c['type'] == 'Ready'), None)
        m = ro.pod_get('/metrics')
        st = sum(float(x) for x in re.findall(r'^startup_seconds ([0-9.eE+-]+)$', m, re.M))
        save({'exp': 'e5_mttr_decomposition', 'trial': t + 1, 'client_recovery_s': r.get('recovery_s'), 'client_detect_s': r.get('detection_s'),
              'container_restart_delay_s': None if fin is None else round(started - fin, 1),
              'ready_delay_after_start_s': None if ready is None else round(ready - started, 1), 'app_startup_s': round(st, 2),
              'restart_count': cs.get('restartCount')})
        ro.wait_ready()


def _frontend_session():
    pf = subprocess.Popen(['kubectl', '-n', run.KNS, 'port-forward', 'svc/frontend', '5056:5000'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    time.sleep(6)
    b = 'http://localhost:5056'
    s = requests.Session()
    u = f'ex{int(time.time())}'
    s.post(b + '/register', data=dict(username=u, email=f'{u}@t.com', password='Test@1234', confirm_password='Test@1234'),
           allow_redirects=False, timeout=60)
    s.post(b + '/login', data=dict(username=u, password='Test@1234'), allow_redirects=False, timeout=60)
    return pf, s, b


def e6():
    """X30: database faults seen from the frontend: table lock (slow DB, 30 s) and database restart."""
    pf, s, b = _frontend_session()
    try:
        for kind in ('db_lock_30s', 'db_restart'):
            for t in range(3):
                rows, stop = [], threading.Event()

                def client():
                    while not stop.is_set():
                        t0 = time.time()
                        try:
                            ok = s.get(b + '/history', timeout=6).status_code == 200
                        except Exception:
                            ok = False
                        rows.append((t0, ok, time.time() - t0))
                        time.sleep(0.5)
                th = threading.Thread(target=client)
                th.start()
                time.sleep(20)
                t_inj = time.time()
                if kind == 'db_lock_30s':
                    subprocess.Popen(['kubectl', '-n', run.KNS, 'exec', 'deploy/postgres', '--', 'psql', '-U', 'climate', '-d', 'climate', '-c',
                                      'BEGIN; LOCK TABLE predictions IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(30); COMMIT;'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    K('-n', run.KNS, 'delete', 'pod', '-l', 'app=postgres', '--wait=false')
                time.sleep(80)
                stop.set()
                th.join()
                after = [r for r in rows if r[0] >= t_inj]
                bad = [r for r in after if not r[1]]
                last_bad = max((r[0] for r in bad), default=None)
                save({'exp': 'e6_db_faults', 'fault': kind, 'trial': t + 1, 'requests_after': len(after), 'failed_after': len(bad),
                      'failed_pct': round(100 * len(bad) / max(len(after), 1), 1),
                      'outage_s': None if not bad else round(last_bad - bad[0][0], 1),
                      'recovered_s': None if last_bad is None else round(last_bad - t_inj, 1)})
                time.sleep(20)
    finally:
        pf.terminate()


def _fm(b):
    t = requests.get(b + '/metrics', timeout=15).text
    def sc(n):
        return sum(float(m.group(1)) for m in re.finditer(rf'^{n}_(?:sum|count)?(?:{{[^}}]*}})? ([0-9.eE+-]+)$', t, re.M))
    def pair(n):
        s = sum(float(m.group(1)) for m in re.finditer(rf'^{n}_sum(?:{{[^}}]*}})? ([0-9.eE+-]+)$', t, re.M))
        c = sum(float(m.group(1)) for m in re.finditer(rf'^{n}_count(?:{{[^}}]*}})? ([0-9.eE+-]+)$', t, re.M))
        return s, c
    return {k: pair(k) for k in ('frontend_request_seconds', 'frontend_inference_seconds', 'db_seconds')}


def e7():
    """X09: per-hop latency attribution (frontend request vs inference call vs database) under healthy and slow-inference load."""
    pf, s, b = _frontend_session()
    try:
        for scenario in ('healthy', 'inference_delay'):
            heal()
            if scenario == 'inference_delay':
                ro.pod_get('/fault?mode=delay')
            m0 = _fm(b)
            t0 = time.time()
            n = 0
            while time.time() - t0 < 60:
                try:
                    s.get(b + '/dashboard', timeout=60)
                    n += 1
                except Exception:
                    pass
            m1 = _fm(b)
            heal()
            d = {k: ((m1[k][0] - m0[k][0]), (m1[k][1] - m0[k][1])) for k in m0}
            req = d['frontend_request_seconds'][0] / max(d['frontend_request_seconds'][1], 1)
            inf = d['frontend_inference_seconds'][0] / max(d['frontend_request_seconds'][1], 1)
            db = d['db_seconds'][0] / max(d['frontend_request_seconds'][1], 1)
            save({'exp': 'e7_hop_timing', 'scenario': scenario, 'page_requests': n, 'avg_request_s': round(req, 3),
                  'avg_inference_call_s_per_request': round(inf, 3), 'avg_db_s_per_request': round(db, 3),
                  'other_rendering_s': round(req - inf - db, 3)})
    finally:
        pf.terminate()


def e8():
    """X22 + X19: degraded badge and input guard visible in the web UI (flash messages)."""
    pf, s, b = _frontend_session()
    try:
        ro.pod_get('/fault?mode=unitchange')
        time.sleep(7)
        s.post(b + '/predict', data=dict(rainfall=100, temperature=26, humidity=70, forecast_months=6), allow_redirects=False, timeout=60)
        page = s.get(b + '/result', timeout=180).text
        save({'exp': 'e8_ui', 'check': 'degraded_badge_visible', 'value': 'degraded mode' in page})
        heal()
        s.post(b + '/predict', data=dict(rainfall=480, temperature=44, humidity=5, forecast_months=6), allow_redirects=False, timeout=60)
        page = s.get(b + '/result', timeout=180).text
        save({'exp': 'e8_ui', 'check': 'unusual_input_warning_visible', 'value': 'unusual compared with Bangalore' in page})
        s.post(b + '/predict', data=dict(rainfall=100, temperature=26, humidity=70, forecast_months=6), allow_redirects=False, timeout=60)
        page = s.get(b + '/result', timeout=180).text
        save({'exp': 'e8_ui', 'check': 'normal_input_no_warning', 'value': 'unusual compared with Bangalore' not in page and 'degraded mode' not in page})
    finally:
        heal()
        pf.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='+', default=['e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8'])
    a = ap.parse_args()
    run.switch_to('E4')
    ro.wait_ready()
    for name in a.only:
        try:
            print('==', name, flush=True)
            globals()[name]()
        except Exception as e:  # noqa: BLE001
            save({'exp': name, 'error': f'{type(e).__name__}: {e}'})
            heal()


if __name__ == '__main__':
    main()
