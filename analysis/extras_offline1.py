"""Extras batch 1 (offline): X11/X32 accuracy vs energy, X20 Hedge tier ordering, X19 input guard, X21 conformal
intervals, X18 third diverse model (GBM) and its effect on the cross-model vote.  Writes results/extras_offline1.json.
  python -X utf8 analysis/extras_offline1.py
"""
import json
import os
import sys
import warnings

import joblib
import numpy as np

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, 'inference-api')
sys.path.insert(0, API)
os.chdir(API)
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest  # noqa: E402
from guard import SemanticGuard, VARS  # noqa: E402
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402
from utils.lstm_model import load_lstm_model, forecast_lstm  # noqa: E402

m = aggregate_monthly(preprocess(load_data('data.csv')))
S = {v: m[v].values.astype(float) for v in VARS}
yy, mm = m['Year'].values.astype(int), m['Month'].values.astype(int)
OUT = {}
lstm = {v: load_lstm_model(v) for v in VARS}
sar = {v: joblib.load(f'saved_models/sarima_{v.lower()}.pkl') for v in VARS}
n = len(m)                                   # data ends June 2024; SARIMA step 1 = Jan 2024
hist_end = n - 6                              # origin: end of Dec 2023
actual = {v: S[v][hist_end:] for v in VARS}   # Jan-Jun 2024

# ---------------- X11 / X32: accuracy of SARIMA vs LSTM (Jan-Jun 2024) + energy
RAIN_CAPS = {1: 5.0, 2: 8.0, 3: 9.0, 4: 43.0, 5: 162.0, 6: 140.9}
acc = {}
for v in VARS:
    f_s = np.maximum(np.asarray(sar[v].get_forecast(steps=6).predicted_mean, float), 0)
    if v == 'Rainfall':
        f_s = np.minimum(f_s, [RAIN_CAPS[k] for k in range(1, 7)])
    f_l = forecast_lstm(lstm[v][0], lstm[v][1], S[v][:hist_end], 6)
    acc[v] = {'sarima_rmse': round(float(np.sqrt(np.mean((f_s - actual[v]) ** 2))), 3),
              'lstm_rmse': round(float(np.sqrt(np.mean((f_l - actual[v]) ** 2))), 3),
              'climatology_rmse': round(float(np.sqrt(np.mean((np.array([S[v][(mm == k)][:-1].mean() for k in range(1, 7)]) - actual[v]) ** 2))), 3)}
p12 = os.path.join(ROOT, 'results', 'phase12.json')
if os.path.exists(p12):
    en = json.load(open(p12))['energy']
    acc['energy_J_per_request'] = {'lstm(energy_aware=0)': en[0]['joules_per_request'], 'sarima(energy_aware=1)': en[1]['joules_per_request']}
OUT['X11_X32_accuracy_vs_energy_Jan_Jun_2024'] = acc

# ---------------- X20 Hedge over experts on the one-step stream 2019-01..2024-06
sd = {v: S[v].std() for v in VARS}
exp_loss = {'lstm': [], 'climatology': [], 'persistence': []}
for v in VARS:
    mod, sc = lstm[v]
    z = sc.transform(S[v].reshape(-1, 1)).ravel()
    X = np.array([z[i - 12:i] for i in range(12, n)]).reshape(-1, 12, 1)
    pred = sc.inverse_transform(mod.predict(X, verbose=0)).ravel()
    idx = np.arange(12, n)
    sel = yy[idx] >= 2019
    clim = np.array([S[v][(mm == mm[i]) & (yy < 2019)].mean() for i in idx[sel]])
    y = S[v][idx][sel]
    for name, p in (('lstm', pred[sel]), ('climatology', clim), ('persistence', S[v][idx - 1][sel])):
        exp_loss[name].append(np.minimum(((p - y) / sd[v]) ** 2, 4.0))
L = {k: np.mean(np.vstack(v), axis=0) for k, v in exp_loss.items()}     # per-month loss averaged over variables
names, T = list(L), len(L['lstm'])
w, eta, hedge = np.ones(len(names)), 1.0, 0.0
for t in range(T):
    prob = w / w.sum()
    hedge += float(sum(prob[i] * L[nm][t] for i, nm in enumerate(names)))
    w *= np.exp(-eta * np.array([L[nm][t] for nm in names]))
tot = {nm: float(L[nm].sum()) for nm in names}
OUT['X20_hedge'] = {'months': T, 'cumulative_loss': {**{k: round(v, 3) for k, v in tot.items()}, 'hedge': round(hedge, 3),
                    'uniform': round(float(np.mean([tot[k] for k in names])), 3)},
                    'final_weights': {nm: round(float(w[i] / w.sum()), 3) for i, nm in enumerate(names)}}

# ---------------- X19 input-side guard: Isolation Forest + conformal threshold on (rain, temp, humidity) triples
X = np.column_stack([S[v] for v in VARS])
cal_mask, fit_mask, test_mask = (yy >= 2000) & (yy <= 2018), yy <= 1999, yy >= 2019
iso = IsolationForest(n_estimators=300, random_state=0).fit(X[fit_mask])
sc_ = lambda A: -iso.score_samples(A)
thr = float(np.quantile(sc_(X[cal_mask]), 0.99))
fa = float(np.mean(sc_(X[test_mask]) > thr))
bad = {'rain_x5': X[test_mask] * [5, 1, 1], 'temp_in_F': X[test_mask] * [1, 1.8, 1] + [0, 32, 0],
       'humidity_gt_100': X[test_mask] + [0, 0, 60], 'negative_rain': X[test_mask] * [-1, 1, 1] - [50, 0, 0], 'all_zero': np.zeros_like(X[test_mask])}
OUT['X19_input_guard'] = {'false_alarm_holdout': round(fa, 3), 'threshold': round(thr, 4),
                          'detection': {k: round(float(np.mean(sc_(v) > thr)), 3) for k, v in bad.items()}}
joblib.dump({'iso': iso, 'thr': thr}, os.path.join(ROOT, 'frontend', 'input_guard.pkl'))

# ---------------- X21 conformal intervals for LSTM multi-step forecasts (h = 1..6), 90 %
H, ALPHA = 6, 0.10
errs = {v: [[] for _ in range(H)] for v in VARS}
test_errs = {v: [[] for _ in range(H)] for v in VARS}
for o in range(n - 1 - 240, n - H):
    for v in VARS:
        f = forecast_lstm(lstm[v][0], lstm[v][1], S[v][:o], H)
        for h in range(H):
            e = abs(f[h] - S[v][o + h])
            (errs if yy[o] <= 2018 else test_errs)[v][h].append(e)
iv, cov = {}, {}
for v in VARS:
    iv[v] = [float(np.quantile(errs[v][h], 1 - ALPHA)) for h in range(H)]
    cov[v] = [round(float(np.mean(np.array(test_errs[v][h]) <= iv[v][h])), 3) for h in range(H)]
json.dump({'alpha': ALPHA, 'half_width': iv}, open(os.path.join(API, 'intervals.json'), 'w'))
OUT['X21_intervals'] = {'half_width_90': {v: [round(x, 2) for x in iv[v]] for v in VARS}, 'heldout_coverage_2019_2024': cov}

# ---------------- X18 third diverse model: gradient boosting on lags + month; effect on the cross-model vote
LAGS = 12
gbm = {}
for v in VARS:
    rows = [np.r_[S[v][i - LAGS:i], np.sin(2 * np.pi * mm[i] / 12), np.cos(2 * np.pi * mm[i] / 12)] for i in range(LAGS, hist_end)]
    gbm[v] = GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0).fit(np.array(rows), S[v][LAGS:hist_end])
    joblib.dump(gbm[v], os.path.join(API, 'saved_models', f'gbm_{v.lower()}.pkl'))


def gbm_forecast(v, hist, month0, steps):
    h, out = list(hist[-LAGS:]), []
    for k in range(steps):
        mo = (month0 + k - 1) % 12 + 1
        x = np.r_[h[-LAGS:], np.sin(2 * np.pi * mo / 12), np.cos(2 * np.pi * mo / 12)]
        out.append(float(gbm[v].predict([x])[0]))
        h.append(out[-1])
    return np.array(out)


g_acc = {v: round(float(np.sqrt(np.mean((gbm_forecast(v, S[v][:hist_end], 1, 6) - actual[v]) ** 2))), 3) for v in VARS}
OUT['X18_gbm_rmse_Jan_Jun_2024'] = g_acc
guard = SemanticGuard(m)
clim6 = guard.climatology(6, 1)
fc = {'sarima': {v: np.maximum(np.asarray(sar[v].get_forecast(steps=6).predicted_mean, float), 0) for v in VARS},
      'lstm': {v: forecast_lstm(lstm[v][0], lstm[v][1], S[v][:hist_end], 6) for v in VARS},
      'gbm': {v: gbm_forecast(v, S[v][:hist_end], 1, 6) for v in VARS}, 'climatology': clim6}
bad_l = {v: forecast_lstm(lstm[v][0], lstm[v][1], S[v][:hist_end], 6) for v in VARS}
bad_l['Temp_mean'] = bad_l['Temp_mean'] * 0.35                                    # scaler-type fault
sub = {v: bad_l[v].copy() for v in VARS}
sub['Temp_mean'] = fc['lstm']['Temp_mean'] + 1.2                                  # subtle +1.2 C bias (like 8-bit flips)
res = {}
for name, lst in (('3_members', ['sarima', 'lstm', 'climatology']), ('4_members', ['sarima', 'lstm', 'gbm', 'climatology'])):
    for label, faulty in (('healthy', fc['lstm']), ('scaler_x0.35', bad_l), ('subtle_bias_+1.2C', sub)):
        mem = {k: fc[k] for k in lst}
        mem['lstm'] = faulty
        res[f'{name}|{label}'] = round(guard.disagreement(mem)['lstm'], 3)
OUT['X18_vote_lstm_disagreement'] = {'threshold': 1.0, 'scores': res}
json.dump(OUT, open(os.path.join(ROOT, 'results', 'extras_offline1.json'), 'w'), indent=1)
print(json.dumps(OUT, indent=1)[:3500])
