"""Phase 10 data collection: scrape the service /metrics every 2 s while a scenario runs under 5 rps load.
Scenarios: healthy (no fault), leak (memory leak -> OOM kill), drift (gradual scaler decay).
Writes results/telemetry/<scenario>_<n>.csv and a .meta.json with the injection time.
  INFER_TAG=7 python analysis/collect_telemetry.py --plan healthy:2:480 leak:6:200 drift:6:170
  python analysis/collect_telemetry.py --smoke
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run  # noqa: E402
import run_operator as ro  # noqa: E402

TEL = os.path.join(ROOT, 'results', 'telemetry')
os.makedirs(TEL, exist_ok=True)
COLS = ['t', 'ok', 'rss_mb', 'cpu_s', 'lat_sum', 'lat_cnt', 'score_lstm', 'score_sarima', 'shift_ks', 'invalid', 'valid']


def parse(text):
    def total(name):
        return sum(float(m.group(1)) for m in re.finditer(rf'^{name}(?:{{[^}}]*}})? ([0-9.eE+-]+)$', text, re.M))

    def one(name, label):
        m = re.search(rf'^{name}{{[^}}]*{label}[^}}]*}} ([0-9.eE+-]+)$', text, re.M)
        return float(m.group(1)) if m else float('nan')
    return {'rss_mb': total('process_rss_bytes') / 1e6, 'cpu_s': total('tier_cpu_seconds_total'),
            'lat_sum': total('predict_seconds_sum'), 'lat_cnt': total('predict_seconds_count'),
            'score_lstm': one('semantic_score', 'backend="lstm"'), 'score_sarima': one('semantic_score', 'backend="sarima"'),
            'shift_ks': total('output_score_shift_ks'), 'invalid': total('served_invalid_total'),
            'valid': total('served_valid_total')}


def scrape():
    try:
        return parse(ro.pod_get('/metrics')) | {'ok': 1}
    except Exception:
        return {'ok': 0}


def scenario(kind, n, duration, inject_at=60):
    ro.wait_ready()
    try:
        ro.pod_get('/fault?mode=heal')
    except Exception:
        pass
    time.sleep(8)
    th = threading.Thread(target=lambda: run.run_probe('E4', [
        '--mode', 'silent', '--base', 'http://inference-api:5001', '--probe-path', '/predict?model=auto&steps=6',
        '--fault', 'none', '--rps', '5', '--warmup', '5', '--fault-window', str(duration + 30), '--heal-window', '2']))
    th.start()
    t0 = None
    while t0 is None:                                  # wait until load is flowing
        s = scrape()
        if s.get('ok') and s.get('lat_cnt', 0) > 20:
            t0 = time.time()
        time.sleep(2)
    path = os.path.join(TEL, f'{kind}_{n}.csv')
    rows, t_inj, fail_seen, calls = [], None, None, 0
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        while time.time() - t0 < duration:
            t = time.time() - t0
            if kind != 'healthy' and t_inj is None and t >= inject_at:
                ro.pod_get('/fault?mode=' + kind)
                t_inj = t
            s = scrape()
            s['t'] = round(t, 1)
            w.writerow({c: s.get(c, '') for c in COLS})
            f.flush()
            if t_inj is not None and not s.get('ok') and fail_seen is None:
                fail_seen = t
            if kind == 'leak' and fail_seen is not None and t - fail_seen > 25:
                break
            time.sleep(2)
    json.dump({'kind': kind, 'n': n, 't_inj': t_inj, 't_failure_scrape': fail_seen, 'duration': duration,
               'image_tag': os.environ.get('INFER_TAG')}, open(path.replace('.csv', '.meta.json'), 'w'))
    try:
        ro.pod_get('/fault?mode=heal')
    except Exception:
        pass
    th.join(timeout=400)
    print('collected', path, 't_inj', t_inj, 'fail', fail_seen, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', nargs='+', default=['healthy:2:480', 'leak:6:200', 'drift:6:170'])
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()
    run.switch_to('E4')
    if a.smoke:
        s = scrape()
        print('smoke scrape:', s)
        assert s.get('ok') and s.get('rss_mb', 0) > 100, 'metrics scrape / rss gauge missing'
        return
    for item in a.plan:
        kind, cnt, dur = item.split(':')
        for n in range(1, int(cnt) + 1):
            scenario(kind, n, float(dur))


if __name__ == '__main__':
    main()
