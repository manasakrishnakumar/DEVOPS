"""Phase 5 ablation (offline): false-alarm rate on hold-out history windows and synthetic-fault detection.
Calibration years <= GUARD_CAL_END (2018); hold-out windows start after 2018.
  python analysis/guard_ablation.py   ->  results/phase5_guard_ablation.json
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
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402
from guard import SemanticGuard, VARS  # noqa: E402

m = aggregate_monthly(preprocess(load_data('data.csv')))
S = {v: m[v].values.astype(float) for v in VARS}
mm, yy = m.Month.values.astype(int), m.Year.values.astype(int)


def faults(w):
    L = len(w['Rainfall'])
    return {'unit_change_F': {**w, 'Temp_mean': w['Temp_mean'] * 9 / 5 + 32},
            'scaler_x0.35_temp': {**w, 'Temp_mean': w['Temp_mean'] * 0.35},
            'rain_x3_plus30': {**w, 'Rainfall': w['Rainfall'] * 3 + 30},
            'swap_temp_hum': {**w, 'Humidity': w['Temp_mean'], 'Temp_mean': w['Humidity']},
            'flatline': {v: np.full(L, w[v][0]) for v in VARS},
            'shift_temp_+4C': {**w, 'Temp_mean': w['Temp_mean'] + 4},
            'shift_hum_-20': {**w, 'Humidity': w['Humidity'] - 20},
            'nan_rainfall': {**w, 'Rainfall': np.full(L, np.nan)}}


res = {}
for alpha in (0.01, 0.05):
    g = SemanticGuard(m, alpha=alpha).load_invariants('invariants.json')
    for mode in ('envelope', 'envelope+inv'):
        g.mode = mode
        for L in (3, 6, 12):
            idx = [i for i in range(len(yy) - L) if yy[i] > 2018]
            fa = float(np.mean([g.score({v: S[v][i:i + L] for v in VARS}, int(mm[i])) > 1 for i in idx]))
            det = {}
            for i in idx:
                w = {v: S[v][i:i + L] for v in VARS}
                for k, fw in faults(w).items():
                    det.setdefault(k, []).append(bool(g.score(fw, int(mm[i])) > 1))
            res[f'alpha={alpha}|{mode}|L={L}'] = {'false_alarm_holdout': round(fa, 4), 'windows': len(idx),
                                                  'detection': {k: round(float(np.mean(v)), 3) for k, v in det.items()}}
out = os.path.join(ROOT, 'results', 'phase5_guard_ablation.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, 'w'), indent=1)
for k, v in res.items():
    if k.endswith('L=6'):
        print(k, 'FA', v['false_alarm_holdout'], v['detection'])
