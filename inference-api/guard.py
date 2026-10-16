"""Semantic correctness guard for ML forecasts.

Novelty 1 - split-conformal envelope: for every calendar month the centre/scale are estimated on the first half
of the history and the conformity scores |y - centre| / scale on the second half. The (1-alpha) empirical quantile
gives a distribution-free bound; a forecast value outside it is flagged invalid. A healthy history value passes
with probability >= 1-alpha (marginal coverage), so the false-alarm rate is controlled rather than hand-tuned.

Novelty 2 - heterogeneous disagreement: SARIMA, LSTM and climatology are independent 'versions'; a member that
deviates from the member median by more than a calibrated number of history standard deviations is suspect.
"""
import json
import os

import numpy as np

VARS = ['Rainfall', 'Temp_mean', 'Humidity']


class SemanticGuard:
    def __init__(self, monthly, alpha=0.01):
        years = monthly['Year'].values
        months = monthly['Month'].values
        split = np.median(years)
        self.alpha = alpha
        self._monthly = monthly
        self.center, self.scale, self.q, self.std, self.clim = {}, {}, {}, {}, {}
        for v in VARS:
            y = monthly[v].values.astype(float)
            c, s, mean = np.zeros(13), np.ones(13), np.zeros(13)
            for m in range(1, 13):
                a = y[(months == m) & (years <= split)]
                c[m] = np.median(a)
                # robust scale with floors so near-constant dry months do not give a degenerate scale
                s[m] = max(np.median(np.abs(a - c[m])) * 1.4826, 0.5 * np.std(a), 0.05 * np.std(y))
                mean[m] = np.mean(y[months == m])
            scores = []
            for m in range(1, 13):
                b = y[(months == m) & (years > split)]
                scores.extend(np.abs(b - c[m]) / s[m])
            scores = np.sort(np.asarray(scores))
            n = len(scores)
            k = int(np.ceil((n + 1) * (1 - alpha)))
            self.q[v] = float(scores[min(k, n) - 1])
            self.center[v], self.scale[v], self.clim[v] = c, s, mean
            self.std[v] = float(np.std(y))

    def load_invariants(self, path='invariants.json', mode=None):
        self.mode = mode or os.environ.get('GUARD_MODE', 'envelope+inv')
        self.inv = {'cross': [], 'temporal': [], 'flatline': {}}
        try:
            d = json.load(open(path))
            self.inv = {'cross': [r for r in d['cross'] if r['keep']], 'temporal': [r for r in d['temporal'] if r['keep']],
                        'flatline': d.get('flatline', {})}
        except Exception:
            pass
        return self.calibrate_windows(cal_end=int(os.environ.get('GUARD_CAL_END', '2018')))

    def invariant_score(self, fc, start_month=1):
        """Max normalised violation (<= 1 valid) over kept soft invariants; 0 if none."""
        inv = getattr(self, 'inv', None)
        if not inv:
            return 0.0
        n = len(fc[VARS[0]])
        months = [self.month_of(k, start_month) for k in range(1, n + 1)]
        worst = 0.0
        for r in inv['cross']:
            for k in range(n):
                x = np.array([1.0] + [float(fc[v][k]) for v in r['inputs']])
                pred = float(np.dot(r['coef'][str(months[k])], x))
                worst = max(worst, abs(float(fc[r['target']][k]) - pred) / r['scale'] / r['q'])
        for r in inv['temporal']:
            v = r['variable']
            for k in range(1, n):
                d = float(fc[v][k]) - float(fc[v][k - 1])
                worst = max(worst, abs(d - r['center'][str(months[k])]) / r['scale'] / r['q'])
        if n >= 4:    # stuck-at / flatline
            for v, f in inv['flatline'].items():
                sd = float(np.std(np.asarray(fc[v], dtype=float)))
                worst = max(worst, f['min_std'] / max(sd, 1e-9))
        return worst

    def score(self, fc, start_month=1):
        """Window-level normalised score: <= 1 valid. envelope (+ invariants if GUARD_MODE has 'inv')."""
        n = len(fc[VARS[0]])
        L = self._L(n)
        if not hasattr(self, 'qwin_env'):
            self.calibrate_windows()
        env = self._env_raw(fc, start_month) / self.qwin_env[L]
        if not np.isfinite(env) or 'inv' not in getattr(self, 'mode', 'envelope+inv'):
            return env
        return max(env, self.invariant_score(fc, start_month) / self.qwin_inv[L])

    @staticmethod
    def month_of(step, start_month=1):
        return ((start_month - 1 + step - 1) % 12) + 1

    def climatology(self, steps, start_month=1):
        return {v: np.array([self.clim[v][self.month_of(k, start_month)] for k in range(1, steps + 1)]) for v in VARS}

    def envelope_score(self, fc, start_month=1):
        """Max conformity score over all values (<= q means valid). NaN/inf -> inf."""
        worst = 0.0
        for v in VARS:
            vals = np.asarray(fc[v], dtype=float)
            if not np.all(np.isfinite(vals)):
                return float('inf')
            for k, x in enumerate(vals, 1):
                m = self.month_of(k, start_month)
                worst = max(worst, abs(x - self.center[v][m]) / self.scale[v][m] / self.q[v])
        return worst  # per-value normalised (<= 1 valid)

    WIN_LENGTHS = (3, 6, 12, 24)

    def calibrate_windows(self, cal_start=None, cal_end=None):
        """Family-wise (window-level) calibration: the quantile of the MAX score over sliding windows of length L.
        A value-level 1-alpha bound over n values would otherwise give a much larger window-level false-alarm rate."""
        m = self._monthly
        years = m['Year'].values.astype(int)
        months = m['Month'].values.astype(int)
        lo = cal_start if cal_start is not None else int(np.median(years))
        hi = cal_end if cal_end is not None else int(years.max())
        series = {v: m[v].values.astype(float) for v in VARS}
        env, inv = {L: [] for L in self.WIN_LENGTHS}, {L: [] for L in self.WIN_LENGTHS}
        n = len(years)
        for L in self.WIN_LENGTHS:
            for i in range(0, n - L):
                if not (lo <= years[i] <= hi):
                    continue
                w = {v: series[v][i:i + L] for v in VARS}
                env[L].append(self._env_raw(w, int(months[i])))
                if getattr(self, 'inv', None) and (self.inv['cross'] or self.inv['temporal']):
                    inv[L].append(self.invariant_score(w, int(months[i])))
        k = lambda arr: float(np.sort(arr)[min(len(arr) - 1, int(np.ceil((len(arr) + 1) * (1 - self.alpha))) - 1)]) if len(arr) else 1.0
        self.qwin_env = {L: max(k(env[L]), 1e-9) for L in self.WIN_LENGTHS}
        self.qwin_inv = {L: max(k(inv[L]), 1.0) for L in self.WIN_LENGTHS}
        return self

    def _env_raw(self, fc, start_month=1):
        """Max |y - centre| / scale over all values (not divided by a quantile)."""
        worst = 0.0
        for v in VARS:
            vals = np.asarray(fc[v], dtype=float)
            if not np.all(np.isfinite(vals)):
                return float('inf')
            for k, x in enumerate(vals, 1):
                mo = self.month_of(k, start_month)
                worst = max(worst, abs(x - self.center[v][mo]) / self.scale[v][mo])
        return worst

    def _L(self, n):
        for L in self.WIN_LENGTHS:
            if n <= L:
                return L
        return self.WIN_LENGTHS[-1]

    def valid(self, fc, start_month=1):
        return self.envelope_score(fc, start_month) <= 1.0

    def disagreement(self, members):
        """members: {name: fc}. Returns {name: mean normalised distance to member-median}."""
        names = list(members)
        if len(names) < 3:
            return {n: 0.0 for n in names}
        out = {}
        for n in names:
            d = []
            for v in VARS:
                stack = np.vstack([np.asarray(members[x][v], dtype=float) for x in names])
                med = np.nanmedian(stack, axis=0)
                d.append(np.nanmean(np.abs(np.asarray(members[n][v], dtype=float) - med)) / self.std[v])
            out[n] = float(np.nanmean(d))
        return out
