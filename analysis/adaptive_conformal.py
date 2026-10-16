"""Phase 13a (offline): static vs rolling-recalibrated vs adaptive-conformal (ACI) guard on hold-out windows (starts >= 2019).
Metric: false-alarm rate on healthy windows and detection of synthetic faults (envelope score only).
Writes results/phase13_adaptive_conformal.json.    python analysis/adaptive_conformal.py
"""
import json
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
from guard import SemanticGuard, VARS  # noqa: E402
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402

ALPHA, L, GAMMA, TEST_FROM = 0.01, 6, 0.005, 2019
m = aggregate_monthly(preprocess(load_data('data.csv')))
S = {v: m[v].values.astype(float) for v in VARS}
mm, yy = m['Month'].values.astype(int), m['Year'].values.astype(int)
g = SemanticGuard(m, alpha=ALPHA)
idx = [i for i in range(len(yy) - L)]
raw = np.array([g._env_raw({v: S[v][i:i + L] for v in VARS}, int(mm[i])) for i in idx])
start_year = yy[idx]


def quant(arr, alpha):
    arr = np.sort(arr)
    k = int(np.ceil((len(arr) + 1) * (1 - alpha)))
    return float(arr[min(k, len(arr)) - 1])


def faults(w):
    return {'unit_change_F': {**w, 'Temp_mean': w['Temp_mean'] * 9 / 5 + 32},
            'scaler_x0.35_temp': {**w, 'Temp_mean': w['Temp_mean'] * 0.35},
            'rain_x3_plus30': {**w, 'Rainfall': w['Rainfall'] * 3 + 30},
            'shift_temp_+4C': {**w, 'Temp_mean': w['Temp_mean'] + 4},
            'shift_hum_-20': {**w, 'Humidity': w['Humidity'] - 20},
            'swap_temp_hum': {**w, 'Humidity': w['Temp_mean'], 'Temp_mean': w['Humidity']}}


test = [i for i in idx if start_year[i] >= TEST_FROM]
fraw = {k: [] for k in faults({v: S[v][:L] for v in VARS})}
for i in test:
    for k, fw in faults({v: S[v][i:i + L] for v in VARS}).items():
        fraw[k].append(g._env_raw(fw, int(mm[i])))
fraw = {k: np.array(v) for k, v in fraw.items()}
traw = raw[test]

res = {}
q_static = quant(raw[start_year <= 2018], ALPHA)
res['static'] = {'false_alarm': float(np.mean(traw > q_static)), 'detect': {k: float(np.mean(v > q_static)) for k, v in fraw.items()}}
qs = []
for j, i in enumerate(test):                                         # rolling: trailing 20 years before the window's year
    Y = start_year[i]
    cal = raw[(start_year >= Y - 20) & (start_year < Y)]
    qs.append(quant(cal, ALPHA))
qs = np.array(qs)
res['rolling_20y'] = {'false_alarm': float(np.mean(traw > qs)), 'detect': {k: float(np.mean(v > qs)) for k, v in fraw.items()}}
cal0 = raw[start_year <= 2018]
a_t, qa, errs = ALPHA, [], []
for t in range(len(test)):                                          # ACI: online alpha update on the healthy stream
    q = quant(cal0, min(max(a_t, 0.001), 0.5))
    qa.append(q)
    err = float(traw[t] > q)
    errs.append(err)
    a_t = a_t + GAMMA * (ALPHA - err)
qa = np.array(qa)
res['aci'] = {'false_alarm': float(np.mean(errs)), 'detect': {k: float(np.mean(v > qa)) for k, v in fraw.items()}, 'final_alpha_t': round(a_t, 4)}
res['meta'] = {'alpha_target': ALPHA, 'window_months': L, 'test_windows': len(test), 'test_from_year': TEST_FROM, 'aci_gamma': GAMMA}
json.dump(res, open(os.path.join(ROOT, 'results', 'phase13_adaptive_conformal.json'), 'w'), indent=1)
for k in ('static', 'rolling_20y', 'aci'):
    print(k, 'FA', round(res[k]['false_alarm'], 3), {a: round(b, 2) for a, b in res[k]['detect'].items()})
