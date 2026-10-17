"""Explore which metamorphic statistic separates healthy from faulty LSTM (first-step shift error vs all steps, shift size)."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
os.environ.update({'SEMANTIC_GUARD': '0', 'FAULT_INJECTION': '1'})
import app as A  # noqa: E402

B = A.BACKENDS['lstm']
V = ['Rainfall', 'Temp_mean', 'Humidity']
SD = {v: float(np.std(A.SERIES[v])) for v in V}
years = A.monthly['Year'].values.astype(int)
N = len(years)
ends = [e for e in range(36, N - 6, 4)]


def fn(series, steps):
    fc = B.forecast(series, steps)
    return A._apply_output_fault(fc)


def stats(c_sd):
    out = {v: [] for v in V}
    for e in ends:
        cut = {v: np.asarray(A.SERIES[v][:e], float) for v in V}
        f = fn(cut, 6)
        fs = fn({v: cut[v] + c_sd * SD[v] for v in V}, 6)
        for v in V:
            d = (np.asarray(fs[v]) - np.asarray(f[v])) / SD[v]
            out[v].append((d[0] / c_sd, float(np.max(np.abs(d - c_sd))) / c_sd))   # first-step gain, max abs deviation (normalised by c)
    return {v: np.array(out[v]) for v in V}


def summarize(tag, st):
    print(tag, {v: (round(float(np.median(st[v][:, 0])), 2), round(float(np.percentile(st[v][:, 0], 1)), 2), round(float(np.percentile(st[v][:, 0], 99)), 2)) for v in V}, flush=True)


for c in (0.5, 1.0):
    print('shift', c, 'sd', flush=True)
    summarize('healthy gain(median,p1,p99)', stats(c))
    A._inject_weights('bitflip', 8)
    summarize('bitflip', stats(c))
    A._heal_all()
    A._inject_weights('scaler')
    summarize('scaler', stats(c))
    A._heal_all()
