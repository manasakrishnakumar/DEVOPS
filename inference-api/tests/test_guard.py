import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guard import SemanticGuard, VARS  # noqa: E402


def synth():
    rng = np.random.default_rng(0)
    rows = []
    for y in range(1951, 2024):
        for m in range(1, 13):
            rows.append({'Year': y, 'Month': m,
                         'Rainfall': max(0.0, 60 * (1 + np.sin(m)) + rng.normal(0, 10)),
                         'Temp_mean': 24 + 3 * np.sin(m / 2) + rng.normal(0, 0.5),
                         'Humidity': 65 + 10 * np.sin(m) + rng.normal(0, 3)})
    return pd.DataFrame(rows)


def test_nan_and_outlier_rejected_clean_passes():
    g = SemanticGuard(synth())
    clean = g.climatology(6, 1)
    assert g.valid(clean, 1)
    assert not g.valid({v: np.full(6, np.nan) for v in VARS}, 1)
    assert not g.valid({v: clean[v] * 4 + 50 for v in VARS}, 1)


def test_disagreement_flags_outlier_member():
    g = SemanticGuard(synth())
    c = g.climatology(6, 1)
    d = g.disagreement({'a': c, 'b': c, 'bad': {v: c[v] * 3 + 30 for v in VARS}})
    assert d['bad'] > d['a']
