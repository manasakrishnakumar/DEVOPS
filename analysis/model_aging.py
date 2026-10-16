"""Addition 1: model-aging forecast with survival analysis.

The LSTM was trained on data up to 2018, so 2019-2024 is genuinely out-of-sample. For every variable we compute the
one-step-ahead normalised error  e_t = |y_t - yhat_t| / scale_month  and call it a degradation event when it exceeds
the conformal threshold q (the same envelope the semantic guard uses).  Gaps between events (right-censored at the end)
are fitted with a Weibull model:  shape k > 1 means the hazard grows with age (wear-out), k ~ 1 memoryless.
The fitted parameters give a median time-to-next-degradation that the service exposes at /aging and uses to
recommend retraining.  Output: analysis/aging.json
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

from scipy.optimize import minimize  # noqa: E402
from guard import SemanticGuard, VARS  # noqa: E402
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402
from utils.lstm_model import load_lstm_model  # noqa: E402

TRAIN_END_YEAR = 2018
SEQ = 12
WARN_FRAC = float(os.environ.get('WARN_FRAC', '0.5'))   # degradation 'warning' = WARN_FRAC * conformal threshold


def weibull_fit(durations, observed):
    """MLE with right censoring. Returns (shape k, scale lambda)."""
    d = np.maximum(np.asarray(durations, float), 0.5)
    o = np.asarray(observed, bool)

    def nll(p):
        k, lam = np.exp(p)
        z = (d / lam) ** k
        ll = np.where(o, np.log(k / lam) + (k - 1) * np.log(d / lam) - z, -z)
        return -ll.sum()

    r = minimize(nll, [0.0, np.log(d.mean() + 1)], method='Nelder-Mead')
    return tuple(float(x) for x in np.exp(r.x))


def main():
    monthly = aggregate_monthly(preprocess(load_data('data.csv')))
    g = SemanticGuard(monthly)
    out = {'train_end_year': TRAIN_END_YEAR, 'warn_fraction': WARN_FRAC, 'variables': {}}
    months = monthly['Month'].values.astype(int)
    years = monthly['Year'].values.astype(int)
    for v in VARS:
        model, scaler = load_lstm_model(v)
        y = monthly[v].values.astype(float)
        sc = scaler.transform(y.reshape(-1, 1)).ravel()
        X = np.array([sc[i - SEQ:i] for i in range(SEQ, len(sc))]).reshape(-1, SEQ, 1)
        pred = scaler.inverse_transform(model.predict(X, verbose=0)).ravel()
        idx = np.arange(SEQ, len(sc))
        oos = years[idx] > TRAIN_END_YEAR
        e = np.abs(y[idx] - pred) / g.scale[v][months[idx]]
        e_oos = e[oos]
        events = np.where(e_oos > WARN_FRAC * g.q[v])[0]
        n = len(e_oos)
        # inter-event gaps; last gap is right-censored
        pts = np.concatenate([[0], events + 1])
        gaps = np.diff(pts).tolist()
        obs = [True] * len(gaps)
        gaps.append(n - pts[-1] + 1)
        obs.append(False)
        gaps_arr = [g_ for g_ in gaps if g_ > 0]
        obs_arr = obs[-len(gaps_arr):]
        k, lam = weibull_fit(gaps_arr, obs_arr) if len(events) >= 2 else (float('nan'), float('nan'))
        half = lam * np.log(2) ** (1 / k) if np.isfinite(k) else None
        # trend of normalised error with age (Spearman-like via rank correlation)
        age = np.arange(n)
        rho = float(np.corrcoef(np.argsort(np.argsort(age)), np.argsort(np.argsort(e_oos)))[0, 1]) if n > 3 else None
        out['variables'][v] = {'months_out_of_sample': int(n), 'events': int(len(events)),
                               'event_rate_per_month': round(len(events) / max(n, 1), 4),
                               'q_threshold': round(g.q[v], 3), 'warn_threshold': round(WARN_FRAC * g.q[v], 3), 'mean_norm_error': round(float(e_oos.mean()), 3),
                               'weibull_shape': None if not np.isfinite(k) else round(k, 3),
                               'weibull_scale_months': None if not np.isfinite(lam) else round(lam, 2),
                               'median_months_to_next_degradation': None if half is None else round(float(half), 2),
                               'age_error_rank_corr': None if rho is None else round(rho, 3)}
        print(v, out['variables'][v])
    med = [d['median_months_to_next_degradation'] for d in out['variables'].values()
           if d['median_months_to_next_degradation']]
    out['retrain_after_months'] = round(float(min(med)), 1) if med else None
    json.dump(out, open(os.path.join(ROOT, 'analysis', 'aging.json'), 'w'), indent=1)
    print('retrain_after_months =', out['retrain_after_months'])


if __name__ == '__main__':
    main()
