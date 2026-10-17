"""Calibrate and evaluate the metamorphic probe on the trained LSTM (no golden output, no stored reference).
 - false alarms: (a) interleaved split (calibrate on even windows of all years, test odd windows), (b) time split (calibrate <= 2018, test > 2018)
 - detection per injected fault on random probe-window triples
Writes inference-api/metamorphic.json (calibrated on all windows) and results/metamorphic_eval.json.   python -X utf8 analysis/calibrate_metamorphic.py
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
os.environ.update({'SEMANTIC_GUARD': '0', 'FAULT_INJECTION': '1'})
import app as A  # noqa: E402
import metamorphic as M  # noqa: E402

ALPHA = 0.01
B = A.BACKENDS['lstm']
SD = {v: float(np.std(A.SERIES[v])) for v in M.VARS}
years = A.monthly['Year'].values.astype(int)
N = len(years)
rng = np.random.default_rng(3)


def fn(series, steps):
    fc = B.forecast(series, steps)
    if A._STATE['corrupt']:
        fc = {v: np.full(steps, np.nan) for v in fc}
    return A._apply_output_fault(fc)


def build(sts):
    k = max(1, int(np.ceil((len(sts) + 1) * (1 - ALPHA / 3))))
    band = {}
    for v in M.VARS:
        G = np.array([s[v][0] for s in sts])
        c = np.median(G, axis=0)
        sc = np.maximum(1.4826 * np.median(np.abs(G - c), axis=0), 0.02)
        d = np.sort(np.max(np.abs(G - c) / sc, axis=1))
        band[v] = {'center': c.tolist(), 'scale': sc.tolist(), 'q': float(max(d[min(k, len(d)) - 1], 1e-6))}
    e2 = np.sort([max(s[v][1] for v in M.VARS) for s in sts])
    return {'alpha': ALPHA, 'shift_sd': M.SHIFT_SD, 'band': band, 'q2': float(max(e2[min(k, len(e2)) - 1], M.E2_FLOOR)), 'n_calibration_windows': len(sts)}


def fa(P, cfg, ST, test_ends, n=300):
    flags = []
    for _ in range(n):
        tri = rng.choice(test_ends, 3, replace=False)
        flags.append(P.score_stats([ST[int(e)] for e in tri], cfg) > 1.0)
    single = [P.score_stats([ST[int(e)]], cfg) > 1.0 for e in test_ends]
    return round(100 * float(np.mean(flags)), 1), round(100 * float(np.mean(single)), 1)


t0 = time.time()
ends = list(range(36, N - 6))
ST = {e: M.window_stats(fn, A.SERIES, e, SD) for e in ends}
print('windows', len(ends), 'time', round(time.time() - t0), 's', flush=True)
P = M.MetamorphicProbe()
res = {'alpha': ALPHA, 'windows': len(ends)}
cfg_a = build([ST[e] for e in ends if e % 2 == 0])
res['false_alarm_interleaved_triple_pct'], res['false_alarm_interleaved_single_pct'] = fa(P, cfg_a, ST, [e for e in ends if e % 2 == 1])
cfg_b = build([ST[e] for e in ends if years[e - 1] <= 2018])
res['false_alarm_timesplit_triple_pct'], res['false_alarm_timesplit_single_pct'] = fa(P, cfg_b, ST, [e for e in ends if years[e - 1] > 2018])
cfg = build([ST[e] for e in ends])
json.dump(cfg, open(os.path.join(ROOT, 'inference-api', 'metamorphic.json'), 'w'), indent=1)
P = M.MetamorphicProbe()
print('false alarms', {k: v for k, v in res.items() if k.startswith('false')}, flush=True)
triples = [tuple(int(x) for x in rng.choice(ends, 3, replace=False)) for _ in range(30)]


def inject(mode):
    A._heal_all()
    if mode == 'bitflip':
        A._inject_weights('bitflip', 8)
    elif mode == 'bitflip_severe':
        A._inject_weights('bitflip', 16)
    elif mode == 'scaler':
        A._inject_weights('scaler')
    elif mode == 'corrupt':
        A._STATE['corrupt'] = True
    else:
        A._FAULT_MODE['mode'] = mode


res['faults'] = {}
for mode in ('bitflip', 'bitflip_severe', 'scaler', 'corrupt', 'unitchange', 'flatline', 'stale'):
    inject(mode)
    sc = [P.score(fn, A.SERIES, SD, ends=list(t))[0] for t in triples]
    A._heal_all()
    res['faults'][mode] = {'detected_pct': round(100 * float(np.mean([s > 1.0 for s in sc])), 1), 'median_score': round(float(np.median([min(s, 1e9) for s in sc])), 2)}
    print(mode, res['faults'][mode], flush=True)
sc = [P.score(fn, A.SERIES, SD, ends=list(t))[0] for t in triples]
res['deployed_probe_windows_healthy_after_heal_false_alarm_pct'] = round(100 * float(np.mean([s > 1.0 for s in sc])), 1)
json.dump(res, open(os.path.join(ROOT, 'results', 'metamorphic_eval.json'), 'w'), indent=1)
print('after heal healthy FA', res['deployed_probe_windows_healthy_after_heal_false_alarm_pct'], 'elapsed', round(time.time() - t0), 's')
