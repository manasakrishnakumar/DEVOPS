"""Novelty study N4/N3: compare the layered guard with simple and literature-style detectors on the same faults, and measure each layer's cost.
Detectors (flag = invalid):
  range      per-variable [min, max] of the history (simple threshold baseline)
  zscore3    any forecast value more than 3 sd from its calendar-month history mean (simple statistical baseline)
  golden     LM-Fix-style: a fixed test vector's output vs the output stored at start-up (tolerance 0.002 sd)
  envelope   conformal envelope only (config D4)
  env+inv    envelope + invariants (config E4)
  full       env+inv OR golden (config G4)
Faults are injected into the real service code locally (weights, scaler, output faults). Detection is measured on 40 random windows
(history cut at random months); false alarms on 300 healthy windows.  Writes results/baselines_pareto.json and a figure.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
os.environ.update({'SEMANTIC_GUARD': '1', 'GUARD_MODE': 'envelope+inv', 'FAULT_INJECTION': '1', 'CANARY_SECONDS': '3600'})
import app as A  # noqa: E402

V = A.VARS
B = A.BACKENDS['lstm']
SD = A.SD
mon = A.monthly
months = mon['Month'].values.astype(int)
N = len(months)
rng = np.random.default_rng(11)
HIST_MIN = {v: float(np.min(A.SERIES[v])) for v in V}
HIST_MAX = {v: float(np.max(A.SERIES[v])) for v in V}
MM = {v: np.array([np.mean(A.SERIES[v][months == m]) if m else 0 for m in range(13)]) for v in V}
MS = {v: np.array([max(np.std(A.SERIES[v][months == m]), 1e-6) if m else 1 for m in range(13)]) for v in V}


def fn(series, steps):
    fc = B.forecast(series, steps)
    if A._STATE['corrupt']:
        fc = {v: np.full(steps, np.nan) for v in fc}
    return A._apply_output_fault(fc)


def start_month(e):
    return int(months[e - 1]) % 12 + 1


def forecast_at(e, steps=6):
    cut = {v: A.SERIES[v][:e] for v in V}
    return fn(cut, steps)


def d_range(fc, sm):
    return any((not np.all(np.isfinite(fc[v]))) or np.min(fc[v]) < HIST_MIN[v] or np.max(fc[v]) > HIST_MAX[v] for v in V)


def d_z3(fc, sm):
    for v in V:
        x = np.asarray(fc[v], float)
        if not np.all(np.isfinite(x)):
            return True
        mi = np.array([((sm - 1 + k) % 12) + 1 for k in range(len(x))])
        if np.max(np.abs(x - MM[v][mi]) / MS[v][mi]) > 3.0:
            return True
    return False


def d_env(mode):
    def f(fc, sm):
        A.GUARD.mode = mode
        s = A.GUARD.score(fc, sm)
        return (not np.isfinite(s)) or s > 1.0
    return f


def d_golden_now():
    g = fn({v: A.SERIES[v] for v in V}, 24)
    return A.golden_dev('lstm', g) > A.GOLDEN_TOL


DET = {'range': d_range, 'zscore3': d_z3, 'envelope': d_env('envelope'), 'env+inv': d_env('envelope+inv')}


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


ends = [int(x) for x in rng.choice(np.arange(48, N - 6), 40, replace=False)]
healthy_ends = [int(x) for x in rng.choice(np.arange(48, N - 6), 300, replace=False)]
res = {'detection_pct': {}, 'false_alarm_pct': {}, 'overhead_ms': {}}
A._heal_all()
fc_h = {e: forecast_at(e) for e in healthy_ends}
for name, f in DET.items():
    res['false_alarm_pct'][name] = round(100 * float(np.mean([f(fc_h[e], start_month(e)) for e in healthy_ends])), 1)
res['false_alarm_pct']['golden'] = 0.0 if not d_golden_now() else 100.0
res['false_alarm_pct']['full'] = round(max(res['false_alarm_pct']['env+inv'], res['false_alarm_pct']['golden']), 1)
for mode in ('bitflip', 'bitflip_severe', 'scaler', 'corrupt', 'unitchange', 'flatline', 'stale'):
    inject(mode)
    row = {}
    fcs = {e: forecast_at(e) for e in ends}
    for name, f in DET.items():
        row[name] = round(100 * float(np.mean([f(fcs[e], start_month(e)) for e in ends])), 1)
    gold = d_golden_now()
    row['golden'] = 100.0 if gold else 0.0
    row['full'] = round(float(np.mean([DET['env+inv'](fcs[e], start_month(e)) or gold for e in ends])) * 100, 1)
    A._heal_all()
    res['detection_pct'][mode] = row
    print(mode, row, flush=True)
# overhead (ms per call, healthy)
A._heal_all()
fc = forecast_at(N)
sm = start_month(N)


def timeit(f, n=200):
    t = time.perf_counter()
    for _ in range(n):
        f()
    return round((time.perf_counter() - t) / n * 1000, 3)


res['overhead_ms'] = {'lstm_forecast_6_steps': timeit(lambda: forecast_at(N), 20), 'range': timeit(lambda: d_range(fc, sm)), 'zscore3': timeit(lambda: d_z3(fc, sm)),
                      'envelope': timeit(lambda: d_env('envelope')(fc, sm)), 'env+inv': timeit(lambda: d_env('envelope+inv')(fc, sm)),
                      'golden_dev_check': timeit(lambda: A.golden_dev('lstm', {v: np.zeros(24) for v in V}), 200),
                      'golden_test_vector_forecast_24': timeit(lambda: fn({v: A.SERIES[v] for v in V}, 24), 20)}
res['note'] = 'golden = LM-Fix-style fixed-test-vector check; golden detection is evaluated on the deployed test vector (independent of the window).'
json.dump(res, open(os.path.join(ROOT, 'results', 'baselines_pareto.json'), 'w'), indent=1)
print(json.dumps(res['false_alarm_pct']), json.dumps(res['overhead_ms']))

import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
names = ['range', 'zscore3', 'golden', 'envelope', 'env+inv', 'full']
faults = list(res['detection_pct'])
fig, ax = plt.subplots(figsize=(9, 3.8))
for i, n in enumerate(names):
    ax.bar(np.arange(len(faults)) + i * 0.13 - 0.33, [res['detection_pct'][f][n] for f in faults], 0.13, label=n)
ax.set_xticks(range(len(faults)))
ax.set_xticklabels(faults, rotation=20)
ax.set_ylabel('detected (%)')
ax.set_title('Detection of injected faults: baselines vs layers of the guard')
ax.legend(fontsize=7, ncol=3)
fig.tight_layout()
fig.savefig(os.path.join(ROOT, 'results', 'figures', 'fig_baselines_detection.png'), dpi=150)
