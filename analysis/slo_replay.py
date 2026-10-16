"""Phase 7 replay: inject a silent fault under steady load and measure how fast the correctness / degraded burn
rates (Prometheus, 30 s + 2 m windows) cross their thresholds.  Writes results/slo_replay.jsonl.
  INFER_TAG=5 python analysis/slo_replay.py --configs C4 E4 --faults corrupt unitchange flatline bitflip
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run  # noqa: E402

PROM = 'http://localhost:9091/api/v1/query'


def bad_ratio(w):
    return (f'sum(rate(served_invalid_total[{w}])) / clamp_min(sum(rate(served_valid_total[{w}])) '
            f'+ sum(rate(served_invalid_total[{w}])), 1e-9)')


DEG30 = ('sum(rate(predict_tier_total{tier=~"climatology|cache"}[30s])) / '
         'clamp_min(sum(rate(predict_tier_total[30s])), 1e-9)')


def q(expr):
    r = requests.get(PROM, params={'query': expr}, timeout=10).json()['data']['result']
    return float(r[0]['value'][1]) if r else 0.0


def pod_get(path):
    code = f"import urllib.request;print(urllib.request.urlopen('http://localhost:5001{path}',timeout=30).read().decode())"
    r = subprocess.run(['kubectl', '-n', run.KNS, 'exec', 'deploy/inference-api', '--', 'python', '-c', code],
                       capture_output=True, text=True, timeout=90)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--configs', nargs='+', default=['C4', 'E4'])
    ap.add_argument('--faults', nargs='+', default=['corrupt', 'unitchange', 'flatline', 'bitflip'])
    ap.add_argument('--trials', type=int, default=2)
    a = ap.parse_args()
    pf = subprocess.Popen(['kubectl', '-n', 'monitoring', 'port-forward', 'svc/prom-prometheus-server', '9091:80'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(6)
    out = os.path.join(ROOT, 'results', 'slo_replay.jsonl')
    try:
        for cfg in a.configs:
            run.switch_to(cfg)
            time.sleep(10)
            infer = 'http://inference-api:5001'
            for fault in a.faults:
                for trial in range(a.trials):
                    pod_get('/fault?mode=heal')
                    time.sleep(12)               # let rate windows settle on healthy traffic
                    res = {}
                    th = threading.Thread(target=lambda: res.update(
                        probe=run.run_probe(cfg, ['--mode', 'silent', '--base', infer, '--probe-path',
                                                  '/predict?model=auto&steps=6', '--fault', 'none', '--rps', '5',
                                                  '--warmup', '10', '--fault-window', '150', '--heal-window', '2'])))
                    th.start()
                    t0 = time.time()
                    while q('sum(rate(served_valid_total[30s]))') < 2.0 and time.time() - t0 < 240:
                        time.sleep(2)
                    time.sleep(20)               # steady healthy load
                    base_burn = q(bad_ratio('30s')) / 0.01
                    s0 = json.loads(pod_get('/slo'))
                    t_inj = time.time()
                    pod_get('/fault?mode=' + fault)
                    t_corr = t_deg = None
                    while time.time() - t_inj < 75:
                        b30, b2 = q(bad_ratio('30s')) / 0.01, q(bad_ratio('2m')) / 0.01
                        d30 = q(DEG30)
                        now = time.time() - t_inj
                        if t_corr is None and b30 > 14.4 and b2 > 14.4:
                            t_corr = round(now, 1)
                        if t_deg is None and d30 > 0.5:
                            t_deg = round(now, 1)
                        time.sleep(2)
                    s1 = json.loads(pod_get('/slo'))
                    pod_get('/fault?mode=heal')
                    th.join(timeout=300)
                    row = {'config': cfg, 'image_tag': os.environ.get('INFER_TAG', '4'), 'fault': fault,
                           'trial': trial + 1, 'baseline_burn_30s': round(base_burn, 3),
                           'time_to_correctness_alert_s': t_corr, 'time_to_degraded_alert_s': t_deg,
                           'restarted': s1['served'] < s0['served'],
                           'served_in_window': s1['served'] - s0['served'], 'invalid_in_window': s1['invalid'] - s0['invalid'],
                           'wilson_lower_95_after': s1['wilson_lower_95'], 'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}
                    open(out, 'a').write(json.dumps(row) + '\n')
                    print(row, flush=True)
    finally:
        pf.terminate()


if __name__ == '__main__':
    main()
