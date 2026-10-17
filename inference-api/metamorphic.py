"""Metamorphic readiness probe (reference-free correctness check for input-dependent forecasters).

A metamorphic relation links the outputs of a model on two related inputs, so no stored reference output and no ground truth are needed:
  MR1  sensitivity profile: the response of the 6-step forecast to a +1 sd shift of the input window,
       g_k = (f(x + c)_k - f(x)_k) / c, must stay inside the band observed for the healthy trained model over historical windows
       (the LSTM mean-reverts, so g is NOT 1; the band is learned, not assumed). Weight, scaler and NaN faults change the profile.
  MR2  recursive self-consistency: f(x, k)[1:] == f(x + f(x,k)[0], k-1) up to float noise; output-level faults
       (flat-line, stale, unit change) break it.
Bands and tolerances are calibrated OFFLINE on the healthy model (distribution-free conformal quantile of the window-level maximum,
analysis/calibrate_metamorphic.py -> metamorphic.json), so a model that is already corrupt at start-up is still detected.
"""
import json
import os

import numpy as np

VARS = ['Rainfall', 'Temp_mean', 'Humidity']
STEPS = 6
SHIFT_SD = 1.0          # shift c = 1 history standard deviation
E2_FLOOR = 1e-3         # float32 noise floor of the recursive relation (in sd units)


def window_stats(fn, series, end, sd):
    """Return {var: (profile (STEPS,), e2)} for series cut at index `end` (exclusive); sd = history std per variable."""
    cut = {v: np.asarray(series[v][:end], float) for v in VARS}
    f = fn(cut, STEPS)
    fs = fn({v: cut[v] + SHIFT_SD * sd[v] for v in VARS}, STEPS)
    f2 = fn({v: np.append(cut[v], float(f[v][0])) for v in VARS}, STEPS - 1)
    out = {}
    for v in VARS:
        a, b, c = (np.asarray(x[v], float) for x in (f, fs, f2))
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(np.isfinite(c))):
            out[v] = (np.full(STEPS, np.inf), float('inf'))
            continue
        out[v] = ((b - a) / sd[v] / SHIFT_SD, float(np.max(np.abs(a[1:] - c))) / sd[v])
    return out


def profile_distance(cfg_v, prof):
    c = np.asarray(cfg_v['center'])
    s = np.asarray(cfg_v['scale'])
    return float(np.max(np.abs(prof - c) / s)) if np.all(np.isfinite(prof)) else float('inf')


class MetamorphicProbe:
    def __init__(self, path=None):
        path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metamorphic.json')
        self.cfg = json.load(open(path)) if os.path.exists(path) else None

    @property
    def ready(self):
        return self.cfg is not None

    def score_stats(self, sts, cfg=None):
        """Same score from precomputed window_stats of the probe windows (used by the offline evaluation)."""
        cfg = cfg or self.cfg
        worst = 0.0
        for st in sts:
            for v in VARS:
                prof, e2 = st[v]
                r1 = profile_distance(cfg['band'][v], prof) / cfg['band'][v]['q']
                r2 = (e2 / max(cfg['q2'], E2_FLOOR)) if np.isfinite(e2) else float('inf')
                worst = max(worst, r1, r2)
        return worst

    def score(self, fn, series, sd, ends=None):
        """Largest normalised violation over variables, relations and probe windows (<= 1 valid)."""
        n = len(series[VARS[0]])
        ends = ends or [n, n - 6, n - 12]
        worst, detail = 0.0, {}
        for e in ends:
            st = window_stats(fn, series, e, sd)
            for v in VARS:
                prof, e2 = st[v]
                r1 = profile_distance(self.cfg['band'][v], prof) / self.cfg['band'][v]['q']
                r2 = (e2 / max(self.cfg['q2'], E2_FLOOR)) if np.isfinite(e2) else float('inf')
                detail[f'{v}.profile'] = max(detail.get(f'{v}.profile', 0.0), r1)
                detail[f'{v}.recursive'] = max(detail.get(f'{v}.recursive', 0.0), r2)
                worst = max(worst, r1, r2)
        return worst, detail
