"""End-to-end validation of everything implemented up to Phase 6. Executes real code, real models, the real cluster.
Writes results/validation_report.md (PASS / FAIL / SKIP with evidence).  Usage: python validation/validate_all.py
Never reports PASS without executing the check.
"""
import json
import os
import re
import subprocess
import sys
import time
import traceback
import warnings
from collections import Counter, defaultdict

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['PATH'] += r';C:\Program Files\Docker\Docker\resources\bin;C:\Program Files\Kubernetes\Minikube'
NS = 'climate'
RES = []


def sh(cmd, timeout=180):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def check(name, fn, skip_if=None):
    t = time.time()
    if skip_if:
        RES.append((name, 'SKIP', skip_if, 0))
        return
    try:
        ev = fn()
        RES.append((name, 'PASS', str(ev)[:400], time.time() - t))
    except AssertionError as e:
        RES.append((name, 'FAIL', 'assertion: ' + str(e)[:400], time.time() - t))
    except Exception as e:  # noqa: BLE001
        RES.append((name, 'FAIL', f'{type(e).__name__}: {e}'[:400], time.time() - t))
    print(f'{RES[-1][1]:5s} {name}', flush=True)


def pod_get(path, dep='inference-api', port=5001, timeout=60):
    code = f"import urllib.request;print(urllib.request.urlopen('http://localhost:{port}{path}',timeout={timeout}).read().decode())"
    rc, out = sh(['kubectl', '-n', NS, 'exec', f'deploy/{dep}', '--', 'python', '-c', code], timeout=timeout + 30)
    assert rc == 0, out[-300:]
    return out.strip()


# ---------------------------------------------------------------- environment
def v_env():
    out = []
    for cmd in (['docker', 'version', '--format', '{{.Server.Version}}'], ['kubectl', 'version', '--client', '-o', 'json']):
        rc, o = sh(cmd)
        assert rc == 0, o[-200:]
        out.append(o.strip()[:60].replace('\n', ' '))
    return ' | '.join(out)


def v_pods():
    rc, o = sh(['kubectl', '-n', NS, 'get', 'pods', '--no-headers'])
    assert rc == 0, o
    run = [l for l in o.splitlines() if re.search(r'1/1\s+Running', l)]
    names = ' '.join(l.split()[0] for l in run)
    for need in ('frontend', 'inference-api', 'postgres'):
        assert need in names, f'{need} not Running: {o}'
    return f'{len(run)} pods Running'


def v_images():
    rc, o = sh(['minikube', 'image', 'ls'])
    assert 'climate-inference:4' in o and 'climate-frontend:2' in o, o[-300:]
    return 'climate-inference:4 and climate-frontend:2 present in minikube'


# ---------------------------------------------------------------- static
def v_compile():
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(ROOT) for f in fs if f.endswith('.py')
             and not any(x in dp for x in ('__pycache__', 'saved_models', '.pytest_cache', 'monolith' + os.sep + 'static'))]
    bad = []
    for f in files:
        rc, o = sh([sys.executable, '-m', 'py_compile', f])
        if rc:
            bad.append(os.path.relpath(f, ROOT))
    assert not bad, bad
    return f'{len(files)} python files compile'


def v_unit():
    rc, o = sh([sys.executable, '-m', 'pytest', '-q', 'inference-api/tests'], timeout=300)
    assert rc == 0, o[-300:]
    return o.strip().splitlines()[-1]


def v_data_models():
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, 'inference-api', 'data.csv'))
    assert len(df) > 26000, len(df)
    sizes = {}
    for f in ('sarima_rainfall.pkl', 'sarima_temp_mean.pkl', 'sarima_humidity.pkl'):
        p = os.path.join(ROOT, 'inference-api', 'saved_models', f)
        assert os.path.getsize(p) > 100e6, f
        sizes[f] = round(os.path.getsize(p) / 1e6)
    for v in ('rainfall', 'temp_mean', 'humidity'):
        assert os.path.getsize(os.path.join(ROOT, 'inference-api', 'saved_models', 'lstm', f'lstm_{v}.h5')) > 1e5
    return f'daily rows={len(df)}, sarima MB={sizes}, 3 lstm .h5 present'


# ---------------------------------------------------------------- in-process service tests (real models)
def _import_app(env):
    for k, v in env.items():
        os.environ[k] = v
    sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
    os.chdir(os.path.join(ROOT, 'inference-api'))
    for m in [m for m in sys.modules if m in ('app', 'guard', 'backends', 'metrics', 'drift') or m.startswith('utils')]:
        del sys.modules[m]
    import app as A  # noqa: E402
    return A


def v_service_baseline():
    A = _import_app({'SEMANTIC_GUARD': '0', 'FAULT_INJECTION': '1'})
    c = A.app.test_client()
    assert c.get('/health/live').status_code == 200
    assert c.get('/health/ready').status_code == 200
    out = {}
    for m in ('sarima', 'lstm', 'auto'):
        r = c.get(f'/predict?model={m}&steps=6')
        d = r.get_json()
        assert r.status_code == 200 and all(len(d[v]) == 6 for v in ('Rainfall', 'Temp_mean', 'Humidity')), m
        out[m] = d['Rainfall'][0]
    assert c.get('/predict?model=bogus').status_code == 503
    assert abs(out['lstm'] - 87.295) < 0.5, out           # known real-LSTM value
    assert out['sarima'] == 5.0                            # capped January rainfall
    mt = c.get('/metrics').data.decode()
    assert 'model_load_seconds' in mt and 'predict_requests_total' in mt
    return f'rain[0] sarima={out["sarima"]} lstm={out["lstm"]}; metrics exposed'


def v_service_guard_faults():
    A = _import_app({'SEMANTIC_GUARD': '1', 'GUARD_MODE': 'envelope+inv', 'FAULT_INJECTION': '1', 'CANARY_SECONDS': '1'})
    c = A.app.test_client()
    time.sleep(4)
    g = lambda: c.get('/predict?model=auto&steps=6').get_json()
    base = g()
    assert base['tier'] == 'lstm' and not base['degraded'], base['tier']
    res = {}
    for f in ('corrupt', 'unitchange', 'flatline', 'scaler'):
        c.get('/fault?mode=' + f)
        time.sleep(0.3)
        d = g()
        time.sleep(1.5)
        d = g()
        res[f] = d['tier']
        assert d['tier'] != 'lstm', f'{f} not detected ({d["tier"]})'
        c.get('/fault?mode=heal')
        time.sleep(2.5)
    d = g()
    assert d['tier'] == 'lstm' and d['Temp_mean'][:3] == base['Temp_mean'][:3], 'heal did not restore'
    return f'detected -> tiers {res}; heal restores lstm identical output'


def v_guard_reproducible():
    rc, o = sh([sys.executable, 'analysis/guard_ablation.py'], timeout=600)
    assert rc == 0, o[-300:]
    new = json.load(open(os.path.join(ROOT, 'results', 'phase5_guard_ablation.json')))
    k = 'alpha=0.01|envelope+inv|L=6'
    assert new[k]['false_alarm_holdout'] == 0.0, new[k]
    det = new[k]['detection']
    assert det['unit_change_F'] == 1.0 and det['nan_rainfall'] == 1.0 and det['flatline'] == 1.0, det
    return f'hold-out false alarm {new[k]["false_alarm_holdout"]}; detection unit={det["unit_change_F"]} flatline={det["flatline"]}'


# ---------------------------------------------------------------- cluster tests
def v_cluster_health():
    d = json.loads(pod_get('/health/ready'))
    assert d['ready'] is True, d
    s = json.loads(pod_get('/health/semantic'))
    return f'ready={d["ready"]}; semantic_ok={s.get("semantic_ok")}'


def v_cluster_fault_cycle():
    mode = pod_get('/fault?mode=status')
    st = json.loads(mode)
    pod_get('/fault?mode=corrupt')
    time.sleep(1)
    d = json.loads(pod_get('/predict?model=auto&steps=6'))
    guard = st.get('guard')
    pod_get('/fault?mode=heal')
    time.sleep(7)
    d2 = json.loads(pod_get('/predict?model=auto&steps=6'))
    if guard:
        assert d['degraded'] is True or d['tier'] != 'lstm', d['tier']
    else:
        assert any(x is None for x in d['Temp_mean']), 'baseline should serve nulls'
    assert d2['Temp_mean'][0] is not None
    return f'guard={guard}: corrupt -> tier={d["tier"]} degraded={d["degraded"]}; healed tier={d2["tier"]}'


def v_frontend_flows():
    import requests
    pf = subprocess.Popen(['kubectl', '-n', NS, 'port-forward', 'svc/frontend', '5055:5000'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(6)
        b = 'http://localhost:5055'
        s = requests.Session()
        u = f'val{int(time.time())}'
        s.post(b + '/register', data=dict(username=u, email=f'{u}@t.com', password='Test@1234', confirm_password='Test@1234'),
               allow_redirects=False, timeout=60)
        s.post(b + '/login', data=dict(username=u, password='Test@1234'), allow_redirects=False, timeout=60)
        codes = {}
        s.post(b + '/predict', data=dict(rainfall=100, temperature=26, humidity=70, forecast_months=12),
               allow_redirects=False, timeout=120)
        s.post(b + '/lstm_predict', data=dict(rainfall=100, temperature=26, humidity=70, forecast_months=12),
               allow_redirects=False, timeout=120)
        for p in ('healthz', 'dashboard', 'result', 'lstm_result', 'history', 'analysis'):
            r = s.get(f'{b}/{p}', timeout=180)
            codes[p] = r.status_code
            assert r.status_code == 200, (p, r.status_code)
        rc, o = sh(['kubectl', '-n', NS, 'exec', 'deploy/postgres', '--', 'psql', '-U', 'climate', '-d', 'climate', '-tc',
                    f"select count(*) from users where username='{u}'"])
        assert rc == 0 and o.strip().startswith('1'), o
        return f'pages {codes}; user persisted in PostgreSQL'
    finally:
        pf.terminate()


def v_prometheus_grafana():
    import requests
    out = []
    for svc, port, path in (('prom-prometheus-server', 9091, '/api/v1/query?query=model_load_seconds'),
                            ('grafana', 3055, '/api/health')):
        pf = subprocess.Popen(['kubectl', '-n', 'monitoring', 'port-forward', f'svc/{svc}', f'{port}:80'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(5)
            r = requests.get(f'http://localhost:{port}{path}', timeout=30)
            assert r.status_code == 200, (svc, r.status_code)
            if 'prom' in svc:
                n = len(r.json()['data']['result'])
                assert n > 0, 'no model_load_seconds series'
                out.append(f'prometheus series={n}')
            else:
                out.append('grafana ' + r.json().get('database', 'ok'))
        finally:
            pf.terminate()
    return ' ; '.join(out)


# ---------------------------------------------------------------- experiment-data integrity
def v_results_integrity():
    rows = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'fault_trials.jsonl')) if l.strip()]
    c = Counter((r['config'], r['fault']) for r in rows)
    assert len(c) >= 14, c
    assert all(v == 5 for v in c.values()), dict(c)
    for r in rows:
        assert r['outcome'] in ('recovered', 'no_recovery', 'no_effect'), r['outcome']
        if r['outcome'] == 'recovered':
            assert r['recovery_s'] is not None and r['recovery_s'] >= 0
    loads = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'load.jsonl')) if l.strip()]
    assert len(loads) >= 20
    return f'{len(rows)} fault rows in {len(c)} cells (5 each); {len(loads)} load rows'


def v_silentbench_integrity():
    p = os.path.join(ROOT, 'results', 'silentbench.jsonl')
    assert os.path.exists(p), 'no silentbench.jsonl'
    rows = [json.loads(l) for l in open(p) if l.strip()]
    assert rows, 'empty'
    g = defaultdict(list)
    for r in rows:
        assert r.get('outcome') != 'no_baseline', r
        b, f = r['baseline'], r['fault_window']
        assert b['correct_pct'] >= 90, f"unhealthy baseline {r['config']} {r['fault']} {b}"
        tot = sum(f[k] for k in ('correct_pct', 'wrong_pct', 'fallback_pct', 'degraded_pct', 'failed_pct'))
        assert abs(tot - 100) < 1.0, tot
        g[(r['config'], r['fault'])].append(r)
    c4 = [r for r in rows if r['config'] == 'C4' and r['fault'] == 'corrupt']
    e4 = [r for r in rows if r['config'] == 'E4' and r['fault'] == 'corrupt']
    if c4:
        assert sum(r['fault_window']['wrong_pct'] for r in c4) / len(c4) > 90, 'C4 should serve wrong answers'
    if e4:
        assert sum(r['fault_window']['wrong_pct'] for r in e4) / len(e4) < 10, 'E4 should not serve wrong answers'
    return f'{len(rows)} rows, {len(g)} cells; baseline healthy, class percentages sum to 100'


def v_later_phases_data():
    """Phases 7-13 result files exist, are non-empty and internally consistent."""
    def jl(fn):
        return [json.loads(l) for l in open(os.path.join(ROOT, 'results', fn)) if l.strip()]
    out = []
    op = jl('operator_trials.jsonl')
    assert len(op) == 60, len(op)
    rules = [r for r in op if r['policy'] == 'rules']
    assert all(r['restored_s'] is not None for r in rules), 'rules policy must restore every trial'
    none_ = [r for r in op if r['policy'] == 'none']
    assert all(r['restored_s'] is None for r in none_), 'policy none should never restore'
    out.append(f'operator rows={len(op)} (rules restored {sum(r["restored_s"] is not None for r in rules)}/{len(rules)})')
    pv = jl('probe_validation.jsonl')
    assert {r['setting'] for r in pv} >= {'default', 'recommended', 'control_default_3rep'}, 'probe validation settings missing'
    out.append(f'probe_validation rows={len(pv)}')
    pr = json.load(open(os.path.join(ROOT, 'results', 'predictor_results.json')))
    assert pr['scenarios']['leak']['summary']['with_failure'] == 6 and pr['scenarios']['drift']['summary']['with_failure'] == 6
    out.append('predictor: 6/6 leak and 6/6 drift failures analysed')
    sg = jl('shadow_gate_cluster.jsonl')
    bad = [r for r in sg if r['expected'] == 'reject']
    good = [r for r in sg if r['expected'] == 'promote']
    assert all(r['decision'] == 'reject' for r in bad), 'a bad candidate was promoted'
    assert all(r['decision'] == 'promote' for r in good), 'a good candidate was rejected'
    out.append(f'shadow gate: {len(bad)}/{len(bad)} bad rejected, {len(good)}/{len(good)} good promoted')
    json.load(open(os.path.join(ROOT, 'results', 'phase12.json')))
    json.load(open(os.path.join(ROOT, 'results', 'phase13_adaptive_conformal.json')))
    assert len(jl('model_family.jsonl')) >= 40
    out.append('phase12/13 result files present')
    return ' ; '.join(out)


def v_extras_data():
    """Cluster extras result files: rows exist and the headline behaviours hold."""
    rows = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'extras_cluster.jsonl')) if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r.get('exp'), []).append(r)
    assert len(by['e1_semantic_probes']) == 18 and len(by['e2_partial_readiness']) == 6 and len(by['e5_mttr_decomposition']) == 5
    ui = {r['check']: r['value'] for r in by['e8_ui']}
    assert ui == {'degraded_badge_visible': True, 'unusual_input_warning_visible': True, 'normal_input_no_warning': True}, ui
    d2 = [r for r in by['e1_semantic_probes'] if r['variant'].startswith('D2')]
    assert all(r['restored_s'] is not None for r in d2), 'semantic readiness+liveness must restore'
    d3 = [r for r in by['e1_semantic_probes'] if r['variant'].startswith('D3')]
    assert all(r['restored_s'] is None for r in d3), 'readiness-only should not restore'
    part = [r for r in by['e2_partial_readiness'] if r['variant'] == 'partial']
    assert all(r['fault_window']['failed_pct'] < 5 for r in part), 'partial readiness should keep serving'
    ch = json.load(open(os.path.join(ROOT, 'results', 'extras_chronos.json')))
    sc = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'extras_scaling.jsonl')) if l.strip()]
    assert len(sc) == 9
    return f'extras rows={len(rows)}; UI checks all True; chronos status={ch.get("status")}; scaling rows={len(sc)}'


def v_fixes_data():
    """Fix round 2026-10-17: golden-output check catches subtle bit flips; cost-aware bandit restores."""
    sb = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'silentbench.jsonl')) if l.strip()]
    g4 = [r for r in sb if r['config'] == 'G4' and r['fault'] in ('bitflip', 'bitflip_severe')]
    assert len(g4) == 20 and all(r['fault_window']['wrong_pct'] == 0 for r in g4), 'golden check must remove wrong answers'
    ok = [r for r in sb if r['config'] == 'G4' and r['fault'] == 'none']
    assert ok and all(r['fault_window']['correct_pct'] == 100 for r in ok), 'golden check false alarm'
    op = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'operator_trials.jsonl')) if l.strip()]
    bd = [r for r in op if r['policy'] == 'bandit']
    assert len(bd) == 20 and all(r.get('restored_s') is not None for r in bd), 'bandit v2 must restore 20/20'
    return f'G4 bitflip rows={len(g4)} (0 wrong), healthy rows={len(ok)} (100% correct); bandit v2 restored {len(bd)}/20'


def v_deadline_data():
    """Novelty 6: deadline- and load-aware degradation removes failures under the delay fault; no regression."""
    sb = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'silentbench.jsonl')) if l.strip()]
    g = [r['fault_window']['failed_pct'] for r in sb if r['config'] == 'G4' and r['fault'] == 'delay']
    h = [r['fault_window']['failed_pct'] for r in sb if r['config'] == 'H4' and r['fault'] == 'delay']
    assert len(g) == 10 and len(h) == 10 and min(g) > 90 and max(h) == 0, (g, h)
    ok = [r['fault_window'] for r in sb if r['config'] == 'H4' and r['fault'] == 'none']
    assert ok and all(w['correct_pct'] == 100 for w in ok), 'H4 healthy false alarm'
    bw = [r['fault_window']['wrong_pct'] for r in sb if r['config'] == 'H4' and r['fault'] in ('corrupt', 'bitflip', 'flatline')]
    assert bw and max(bw) == 0
    return f'delay fault failed %: G4 mean {sum(g)/len(g):.1f} -> H4 {sum(h)/len(h):.1f}; H4 healthy 100% correct, 0% wrong on corrupt/bitflip/flatline'


def v_metamorphic_data():
    """Metamorphic probe evaluation file exists; output-level faults detected, interleaved false alarms low; limits recorded."""
    d = json.load(open(os.path.join(ROOT, 'results', 'metamorphic_eval.json')))
    for f in ('corrupt', 'unitchange', 'flatline', 'stale'):
        assert d['faults'][f]['detected_pct'] == 100.0, f
    assert d['false_alarm_interleaved_triple_pct'] <= 5.0 and d['deployed_probe_windows_healthy_after_heal_false_alarm_pct'] == 0.0
    return f"interleaved FA {d['false_alarm_interleaved_triple_pct']} %, time-split FA {d['false_alarm_timesplit_triple_pct']} % (limit), bitflip {d['faults']['bitflip']['detected_pct']} % marginal, scaler {d['faults']['scaler']['detected_pct']} %"


def main():
    check('V01 docker + kubectl available', v_env)
    check('V02 cluster pods Running', v_pods)
    check('V03 images present in minikube', v_images)
    check('V04 all python files compile', v_compile)
    check('V05 unit tests (pytest)', v_unit)
    check('V06 data and model files', v_data_models)
    check('V07 service, baseline mode (real models)', v_service_baseline)
    check('V08 service, guard on: faults detected + heal (real models)', v_service_guard_faults)
    check('V09 guard ablation reproduces stored numbers', v_guard_reproducible)
    check('V10 cluster readiness + semantic health', v_cluster_health)
    check('V11 cluster fault cycle corrupt/heal (in pod)', v_cluster_fault_cycle)
    check('V12 frontend flows through Kubernetes + PostgreSQL', v_frontend_flows)
    check('V13 Prometheus metrics + Grafana health', v_prometheus_grafana)
    check('V14 baseline experiment data integrity', v_results_integrity)
    check('V15 silent-benchmark data integrity', v_silentbench_integrity)
    check('V17 cluster extras results (semantic probes, partial readiness, UI, scaling, Chronos)', v_extras_data)
    check('V18 fix round: golden check + cost-aware bandit', v_fixes_data)
    check('V19 deadline-aware degradation (delay fault)', v_deadline_data)
    check('V20 metamorphic probe evaluation (experimental)', v_metamorphic_data)
    check('V16 phases 7-13 result data (operator, probe validation, predictor, shadow gate, family)', v_later_phases_data)
    os.chdir(ROOT)
    npass = sum(1 for r in RES if r[1] == 'PASS')
    lines = ['# Validation report', '', f'Generated {time.strftime("%Y-%m-%d %H:%M:%S")}  |  {npass}/{len(RES)} checks PASS', '',
             '| Check | Result | Evidence | Seconds |', '|---|---|---|---|']
    for n, s, e, t in RES:
        lines.append(f'| {n} | **{s}** | {e.replace("|", "/")} | {t:.0f} |')
    out = os.path.join(ROOT, 'results', 'validation_report.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 0 if npass == len(RES) else 1


if __name__ == '__main__':
    sys.exit(main())
