"""Phase 5 (C2): mine soft cross-variable / temporal invariants for the forecasting service.

Three-way split by year: FIT (parameters), CAL (conformal quantile q at alpha) and TEST (honest hold-rate).
Relations (per calendar month where relevant):
  cross   : target ~ a + b*x1 + c*x2   for (Humidity|Temp,Rain), (Temp|Humidity,Rain), (Rain|Temp,Humidity)
  temporal: |Delta y_t - median| <= q    per variable and month transition
  flatline: rolling std over 6 months must exceed a lower bound (stuck-at output)
A relation is kept only if its TEST hold-rate >= MIN_HOLD. Output: inference-api/invariants.json
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402

ALPHA = 0.01
MIN_HOLD = float(os.environ.get('MIN_HOLD', '0.95'))
MAX_TIGHT = float(os.environ.get('MAX_TIGHT', '1.0'))   # keep only relations whose acceptance band is narrower than 1 std
V = ['Rainfall', 'Temp_mean', 'Humidity']
CROSS = [('Humidity', ['Temp_mean', 'Rainfall']), ('Temp_mean', ['Humidity', 'Rainfall']),
         ('Rainfall', ['Temp_mean', 'Humidity'])]


def conf_q(scores, alpha=ALPHA):
    s = np.sort(np.asarray(scores))
    n = len(s)
    k = int(np.ceil((n + 1) * (1 - alpha)))
    return float(s[min(k, n) - 1])


def robust_scale(r, floor):
    return float(max(np.median(np.abs(r - np.median(r))) * 1.4826, 0.5 * np.std(r), floor))


def main():
    m = aggregate_monthly(preprocess(load_data('data.csv')))
    years, months = m['Year'].values.astype(int), m['Month'].values.astype(int)
    y = {v: m[v].values.astype(float) for v in V}
    t1 = int(os.environ.get('FIT_END', '1985'))     # FIT   : <= t1
    t2 = int(os.environ.get('CAL_END', '2015'))     # CAL   : t1 < y <= t2 (recent, so q reflects current regime)
                                                   # TEST  : > t2 (honest, most recent years)
    t0 = int(os.environ.get('FIT_START', '1951'))   # recent-window mining: FIT = [t0, t1]
    fit, cal, test = (years >= t0) & (years <= t1), (years > t1) & (years <= t2), years > t2
    std = {v: float(np.std(y[v])) for v in V}
    out = {'alpha': ALPHA, 'min_hold': MIN_HOLD, 'split_years': [int(t1), int(t2)], 'cross': [], 'temporal': [],
           'flatline': {}, 'summary': {}}
    # --- cross-variable: per-month coefficients, POOLED residual scale and POOLED conformal quantile
    for tgt, xs in CROSS:
        coefs = {}
        for mo in range(1, 13):
            sel = (months == mo) & fit
            A = np.column_stack([np.ones(sel.sum())] + [y[x][sel] for x in xs])
            coefs[mo], *_ = np.linalg.lstsq(A, y[tgt][sel], rcond=None)

        def resid(mask):
            r = np.zeros(len(y[tgt]))
            for mo in range(1, 13):
                s_ = (months == mo)
                A = np.column_stack([np.ones(len(r))] + [y[x] for x in xs])
                r[s_] = y[tgt][s_] - A[s_] @ coefs[mo]
            return r[mask]
        sc = robust_scale(resid(fit), 0.05 * std[tgt])
        q = conf_q(np.abs(resid(cal)) / sc)
        hold = float(np.mean(np.abs(resid(test)) / sc <= q))
        tight = q * sc / std[tgt]
        out['cross'].append({'target': tgt, 'inputs': xs, 'coef': {str(k): v.tolist() for k, v in coefs.items()},
                             'scale': sc, 'q': q, 'hold_rate': round(hold, 4), 'tightness': round(float(tight), 3),
                             'keep': bool(hold >= MIN_HOLD and tight <= MAX_TIGHT)})
    # --- temporal smoothness: per-month centre, pooled scale and pooled quantile
    for v in V:
        d = np.diff(y[v])
        dm, dy = months[1:], years[1:]
        dfit, dcal, dtest = (dy >= t0) & (dy <= t1), (dy > t1) & (dy <= t2), dy > t2
        cen = {mo: float(np.median(d[(dm == mo) & dfit])) for mo in range(1, 13)}
        cvec = np.array([cen[int(mo)] for mo in dm])
        r = d - cvec
        sc = robust_scale(r[dfit], 0.05 * std[v])
        q = conf_q(np.abs(r[dcal]) / sc)
        hold = float(np.mean(np.abs(r[dtest]) / sc <= q))
        tight = q * sc / std[v]
        out['temporal'].append({'variable': v, 'center': {str(k): c for k, c in cen.items()}, 'scale': sc, 'q': q,
                                'hold_rate': round(hold, 4), 'tightness': round(float(tight), 3),
                                'keep': bool(hold >= MIN_HOLD and tight <= MAX_TIGHT)})
    # --- flatline: rolling std of 6 consecutive months
    for v in V:
        w = np.array([np.std(y[v][i:i + 6]) for i in range(len(y[v]) - 5)])
        thr = float(np.quantile(w, 0.005))
        out['flatline'][v] = {'min_std': thr, 'window': 6}
    out['summary'] = {r['target'] + '|' + ','.join(r['inputs']): [r['hold_rate'], r['tightness'], r['keep']]
                      for r in out['cross']}
    out['summary'].update({'dt_' + r['variable']: [r['hold_rate'], r['tightness'], r['keep']] for r in out['temporal']})
    json.dump(out, open(os.path.join(ROOT, 'inference-api', 'invariants.json'), 'w'))
    print(json.dumps(out['summary'], indent=1))
    print('flatline thresholds:', {k: round(v['min_std'], 3) for k, v in out['flatline'].items()})


if __name__ == '__main__':
    main()
