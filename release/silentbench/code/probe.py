"""In-network load / fault probe. Runs inside the cluster or compose network so one clock is used.

fault mode : steady load -> inject fault -> measure detection, recovery, failed requests (JSON line)
load  mode : concurrency sweep, latency percentiles + throughput (JSON lines)
"""
import argparse
import json
import math
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests


def good(resp, strict):
    if resp.status_code != 200:
        return False
    if not strict:
        return True
    try:
        d = resp.json()
        vals = d['Rainfall'] + d['Temp_mean'] + d['Humidity']
        return all(v is not None and math.isfinite(v) for v in vals)
    except Exception:
        return False


def wait_ready(url, strict, limit=900):
    t0 = time.time()
    ok = 0
    while time.time() - t0 < limit:
        try:
            ok = ok + 1 if good(requests.get(url, timeout=3), strict) else 0
        except Exception:
            ok = 0
        if ok >= 3:
            return time.time() - t0
        time.sleep(1)
    raise SystemExit('target never became ready')


def fault_trial(a):
    probe = a.base + a.probe_path
    strict = 'predict' in a.probe_path
    waited = wait_ready(probe, strict)
    recs, lock, stop = [], threading.Lock(), threading.Event()

    def one(ts):
        t = time.time()
        tier = None
        try:
            r = requests.get(probe, timeout=a.req_timeout)
            ok, code = good(r, strict), r.status_code
            if strict and code == 200:
                try:
                    tier = r.json().get('tier')
                except Exception:
                    pass
        except Exception:
            ok, code = False, 0
        with lock:
            recs.append((ts, ok, time.time() - t, code, tier))

    pool = ThreadPoolExecutor(max_workers=96)
    period = 1.0 / a.rps
    t_start = time.time()
    t_fault = None
    nxt = t_start

    def inject():
        try:
            requests.get(a.base + f'/fault?mode={a.fault}', timeout=3)
        except Exception:
            pass

    while True:
        now = time.time()
        if now >= nxt:
            pool.submit(one, now)
            nxt += period
        if t_fault is None and now - t_start >= a.warmup:
            t_fault = time.time()
            threading.Thread(target=inject, daemon=True).start()
        if t_fault is not None:
            with lock:
                after = sorted(r for r in recs if r[0] >= t_fault)
            fails = [r for r in after if not r[1]]
            if fails:
                first_fail = fails[0][0]
                tail = [r for r in after if r[0] > first_fail]
                run = 0
                rec_t = None
                for r in tail:
                    run = run + 1 if r[1] else 0
                    if run >= 10:
                        rec_t = r[0]
                        break
                if rec_t is not None:
                    break
            if now - t_fault > a.timeout:
                break
        time.sleep(0.005)
    time.sleep(1)
    pool.shutdown(wait=False, cancel_futures=True)
    with lock:
        allr = sorted(recs)
    after = [r for r in allr if t_fault <= r[0]]
    fails = [r for r in after if not r[1]]
    tiers = {}
    for r in after:
        if r[4]:
            tiers[r[4]] = tiers.get(r[4], 0) + 1
    out = {'fault': a.fault, 'target': a.base, 'rps': a.rps, 'ready_wait_s': round(waited, 2), 'tiers_after_fault': tiers,
           'pre_fault_requests': len(allr) - len(after)}
    if not fails:
        out.update(outcome='no_effect', detection_s=None, recovery_s=None, failed=0, total=len(after))
    else:
        first_fail = fails[0][0]
        if rec_t is None:
            end = after[-1][0]
            out.update(outcome='no_recovery', recovery_s=None)
        else:
            end = rec_t
            out.update(outcome='recovered', recovery_s=round(rec_t - t_fault, 2))
        win = [r for r in after if r[0] <= end]
        wf = [r for r in win if not r[1]]
        out.update(detection_s=round(first_fail - t_fault, 2), failed=len(wf), total=len(win),
                   failed_pct=round(100 * len(wf) / max(1, len(win)), 1),
                   downtime_s=round(max(r[0] for r in wf) - first_fail, 2))
    print(json.dumps(out), flush=True)


TOL = {'Rainfall': (25.0, 0.10), 'Temp_mean': (1.5, 0.05), 'Humidity': (6.0, 0.05)}   # absolute, relative
VARS3 = ['Rainfall', 'Temp_mean', 'Humidity']


def _within(vals, gold):
    for v in VARS3:
        for x, g in zip(vals[v], gold[v]):
            if x is None or not math.isfinite(x):
                return False
            if abs(x - g) > TOL[v][0] + TOL[v][1] * abs(g):
                return False
    return True


def silent_trial(a):
    """Healthy baseline -> inject silent fault -> observe -> heal. Counts wrong answers, fallbacks, degraded, failed."""
    probe = a.base + a.probe_path
    wait_ready(probe, True)
    try:
        requests.get(a.base + '/fault?mode=heal', timeout=5)
    except Exception:
        pass
    time.sleep(1.5)
    recs, lock = [], threading.Lock()

    def one(ts, phase):
        rec = {'ts': ts, 'phase': phase, 'status': 0, 'tier': None, 'degraded': False, 'vals': None}
        t = time.time()
        try:
            r = requests.get(probe, timeout=a.req_timeout)
            rec['status'] = r.status_code
            if r.status_code == 200:
                d = r.json()
                rec['tier'] = d.get('tier')
                rec['degraded'] = bool(d.get('degraded'))
                rec['vals'] = {v: d[v] for v in VARS3}
        except Exception:
            pass
        rec['lat'] = time.time() - t
        with lock:
            recs.append(rec)

    pool = ThreadPoolExecutor(max_workers=32)
    period = 1.0 / a.rps
    t0 = time.time()
    t_fault = t0 + a.warmup
    t_heal = t_fault + a.fault_window
    t_end = t_heal + a.heal_window
    injected = healed = False
    nxt = t0
    while True:
        now = time.time()
        if now >= t_end:
            break
        if not injected and now >= t_fault:
            injected = True
            t_fault = time.time()          # stamp BEFORE injecting so detect_s is never negative
            try:
                requests.get(a.base + f'/fault?mode={a.fault}', timeout=5)
            except Exception:
                pass
        if injected and not healed and now >= t_heal:
            healed = True
            if not a.no_heal:
                try:
                    requests.get(a.base + '/fault?mode=heal', timeout=5)
                except Exception:
                    pass
            t_heal = time.time()
        if now >= nxt:
            phase = 'base' if not injected else ('fault' if not healed else 'heal')
            pool.submit(one, now, phase)
            nxt += period
        time.sleep(0.005)
    time.sleep(a.req_timeout + 0.5)
    pool.shutdown(wait=False, cancel_futures=True)
    with lock:
        R = sorted(recs, key=lambda r: r['ts'])
    base = [r for r in R if r['phase'] == 'base' and r['status'] == 200 and r['vals']]
    if not base:
        print(json.dumps({'fault': a.fault, 'outcome': 'no_baseline'}), flush=True)
        return
    tiers = [r['tier'] for r in base]
    gtier = max(set(tiers), key=tiers.count)
    gold = {v: [statistics.median(r['vals'][v][k] for r in base if r['tier'] == gtier and r['vals'][v][k] is not None)
                for k in range(len(base[0]['vals'][v]))] for v in VARS3}

    def cls(r):
        if r['status'] != 200:
            return 'failed'
        if r['degraded']:
            return 'degraded'
        finite = r['vals'] and all(x is not None and math.isfinite(x) for v in VARS3 for x in r['vals'][v])
        if r['tier'] == gtier:
            return 'correct' if finite and _within(r['vals'], gold) else 'wrong'
        return 'fallback' if finite else 'wrong'

    def summarize(rows):
        n = max(1, len(rows))
        c = {k: 0 for k in ('correct', 'wrong', 'fallback', 'degraded', 'failed')}
        for r in rows:
            c[cls(r)] += 1
        lat = sorted(r['lat'] for r in rows) or [0.0]
        return {**{k + '_pct': round(100 * v / n, 1) for k, v in c.items()}, 'n': len(rows),
                'p95_ms': round(1000 * lat[min(len(lat) - 1, int(0.95 * len(lat)))], 0)}

    fault_rows = [r for r in R if r['phase'] == 'fault']
    react = [r for r in fault_rows if cls(r) in ('failed', 'degraded', 'fallback')]
    detect = round(react[0]['ts'] - t_fault, 2) if react else None
    heal_rows = [r for r in R if r['phase'] == 'heal']
    run, rec_t = 0, None
    for r in heal_rows:
        run = run + 1 if cls(r) == 'correct' else 0
        if run >= 5:
            rec_t = round(r['ts'] - t_heal, 2)
            break
    # time until the full-quality tier is back (5 consecutive correct primary-tier answers) -- works without heal
    run_, restored = 0, None
    for r in [r for r in R if r['ts'] >= t_fault]:
        run_ = run_ + 1 if cls(r) == 'correct' else 0
        if run_ >= 5 and any(cls(x) != 'correct' for x in R if t_fault <= x['ts'] <= r['ts']):
            restored = round(r['ts'] - t_fault, 2)
            break
    out = {'fault': a.fault, 'target': a.base, 'golden_tier': gtier, 'rps': a.rps, 'restored_s': restored,
           'baseline': summarize([r for r in R if r['phase'] == 'base']), 'fault_window': summarize(fault_rows),
           'detect_s': detect, 'recovered_after_heal_s': rec_t}
    print(json.dumps(out), flush=True)


def app_session(base, name):
    s = requests.Session()
    s.post(base + '/register', data=dict(username=name, email=f'{name}@t.com', password='Test@1234',
                                         confirm_password='Test@1234'), allow_redirects=False, timeout=30)
    s.post(base + '/login', data=dict(username=name, password='Test@1234'), allow_redirects=False, timeout=30)
    return s


def load_sweep(a):
    strict = a.flow == 'api'
    url = a.base + a.probe_path
    wait_ready(a.base + ('/healthz' if a.flow == 'app' else a.probe_path), strict)
    for conc in [int(x) for x in a.levels.split(',')]:
        lat, errs, lock = [], [0], threading.Lock()
        end = time.time() + a.duration

        def worker(i):
            s = app_session(a.base, f'ld{uuid.uuid4().hex[:8]}') if a.flow == 'app' else requests.Session()
            while time.time() < end:
                t = time.time()
                try:
                    r = s.get(url, timeout=60)
                    ok = good(r, strict) if a.flow == 'api' else r.status_code == 200
                except Exception:
                    ok = False
                dt = time.time() - t
                with lock:
                    (lat.append(dt) if ok else errs.__setitem__(0, errs[0] + 1))

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(conc)]
        t0 = time.time()
        [t.start() for t in ts]
        [t.join() for t in ts]
        el = time.time() - t0
        lat.sort()
        pct = lambda p: round(lat[min(len(lat) - 1, int(p * len(lat)))] * 1000, 1) if lat else None
        print(json.dumps({'flow': a.flow, 'target': a.base, 'concurrency': conc, 'ok': len(lat), 'errors': errs[0],
                          'rps': round(len(lat) / el, 2), 'mean_ms': round(statistics.mean(lat) * 1000, 1) if lat else None,
                          'p50_ms': pct(.5), 'p95_ms': pct(.95), 'p99_ms': pct(.99)}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['fault', 'load', 'silent'], required=True)
    p.add_argument('--fault-window', type=float, default=45)
    p.add_argument('--no-heal', action='store_true')
    p.add_argument('--heal-window', type=float, default=15)
    p.add_argument('--base', required=True)
    p.add_argument('--probe-path', default='/predict?model=sarima&steps=3')
    p.add_argument('--fault', default='crash')
    p.add_argument('--rps', type=float, default=10)
    p.add_argument('--warmup', type=float, default=15)
    p.add_argument('--timeout', type=float, default=240)
    p.add_argument('--req-timeout', type=float, default=2)
    p.add_argument('--flow', default='api', choices=['api', 'app'])
    p.add_argument('--levels', default='1,2,4,8')
    p.add_argument('--duration', type=float, default=20)
    a = p.parse_args()
    {'fault': fault_trial, 'load': load_sweep, 'silent': silent_trial}[a.mode](a)
