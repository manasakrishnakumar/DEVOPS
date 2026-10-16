"""Novelty 4: response-surface model of MTTR from DoE runs + Bayesian optimisation of probe settings.

1. Quadratic RSM (Ridge) per response, leave-one-out R^2 as validation.
2. GP on RSM residuals (surrogate = RSM + GP) and expected-improvement search over the discrete grid.
Objective: minimise recovery_s + LAMBDA * failed_pct subject to period*threshold >= MIN_DETECT_S
(false-restart budget: a stall shorter than MIN_DETECT_S must not trigger a restart).
"""
import json
import math
import os

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA = 0.3
MIN_DETECT_S = 10.0


def load():
    X, y1, y2 = [], [], []
    for line in open(os.environ.get('DOE_FILE', os.path.join(ROOT, 'results', 'doe.jsonl'))):
        r = json.loads(line)
        if r.get('recovery_s') is None:
            continue
        X.append([r['period'], r['threshold'], r['replicas']])
        y1.append(r['recovery_s'])
        y2.append(r.get('failed_pct', 0.0))
    return np.array(X, float), np.array(y1), np.array(y2)


def rsm():
    return make_pipeline(StandardScaler(), PolynomialFeatures(2), Ridge(alpha=1.0))


def main():
    X, rec, fail = load()
    print('runs:', len(X))
    out = {}
    models = {}
    for name, y in (('recovery_s', rec), ('failed_pct', fail)):
        m = rsm()
        pred = cross_val_predict(m, X, y, cv=LeaveOneOut())
        ss = ((y - pred) ** 2).sum()
        st = ((y - y.mean()) ** 2).sum() or 1.0
        out[f'{name}_loo_r2'] = round(1 - ss / st, 3)
        m.fit(X, y)
        models[name] = (m, y)
    obj_y = rec + LAMBDA * fail
    base = rsm().fit(X, obj_y)
    gp = GaussianProcessRegressor(Matern(nu=2.5) + WhiteKernel(1.0), normalize_y=True, random_state=0)
    gp.fit(X, obj_y - base.predict(X))
    # search only inside the experimental region (no extrapolation): period 5-20 s, threshold 1-5, replicas 1-3
    grid = np.array([[p, t, r] for p in range(5, 21) for t in range(1, 6) for r in (1, 2, 3)
                     if p * t >= MIN_DETECT_S], float)
    mu = np.maximum(base.predict(grid) + gp.predict(grid), 0.0)   # objective (seconds + weighted %) cannot be negative
    sd = gp.predict(grid, return_std=True)[1]
    best = obj_y.min()
    z = (best - mu) / np.maximum(sd, 1e-9)
    from scipy.stats import norm
    ei = (best - mu) * norm.cdf(z) + sd * norm.pdf(z)
    k = int(np.argmin(mu))
    out['recommended'] = {'period': float(grid[k][0]), 'threshold': float(grid[k][1]), 'replicas': float(grid[k][2]),
                          'predicted_objective': round(float(mu[k]), 2)}
    out['most_informative_next_run'] = grid[int(np.argmax(ei))].tolist()
    out['observed_best'] = X[int(np.argmin(obj_y))].tolist()
    out['observed_best_objective'] = round(float(best), 2)
    json.dump(out, open(os.path.join(ROOT, 'analysis', 'bo_result.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

