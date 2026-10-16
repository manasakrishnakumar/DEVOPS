"""Addition 2 (detector half): input drift (PSI) and residual drift (Page-Hinkley) for the retraining trigger."""
import numpy as np


def psi(ref, cur, bins=10):
    ref, cur = np.asarray(ref, float), np.asarray(cur, float)
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(ref, edges)[0] / len(ref)
    q = np.histogram(cur, edges)[0] / len(cur)
    p, q = np.clip(p, 1e-4, None), np.clip(q, 1e-4, None)
    return float(np.sum((q - p) * np.log(q / p)))


def page_hinkley(x, delta=0.05, lam=8.0):
    """Upward mean-shift detector on a stream. Returns (alarm_index or None, final statistic)."""
    mean, s, m, alarm = 0.0, 0.0, 0.0, None
    for i, v in enumerate(x, 1):
        mean += (v - mean) / i
        s += v - mean - delta
        m = min(m, s)
        if s - m > lam and alarm is None:
            alarm = i - 1
    return alarm, float(s - m)
