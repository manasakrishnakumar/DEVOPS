"""Novelty study N1: compound faults (two faults at once) on the real service code (local test client).
Weights/scaler fault + output-level or delay fault; configs E4 (envelope+invariants), G4 (+golden), H4 (+golden +800 ms deadline).
Oracle: a served answer is WRONG if it deviates by more than 0.05 history-sd from the healthy forecast of the tier it names.
Writes results/compound_faults.json.   python -X utf8 analysis/compound_faults.py
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
os.chdir(os.path.join(ROOT, 'inference-api'))
os.environ.update({'SEMANTIC_GUARD': '1', 'GUARD_MODE': 'envelope+inv', 'FAULT_INJECTION': '1', 'CANARY_SECONDS': '1'})
import app as A  # noqa: E402

c = A.app.test_client()
V = A.VARS
time.sleep(4)
STEPS = 6
REF = {}
A._heal_all()
REF['lstm'] = A.BACKENDS['lstm'].forecast(A.SERIES, STEPS)
off = (A.BACKENDS['lstm'].start_month - A.BACKENDS['sarima'].start_month) % 12
full = A.BACKENDS['sarima'].forecast(A.SERIES, STEPS + off)
REF['sarima'] = {v: full[v][:STEPS] for v in V}      # service serves sarima step 1 = Jan (its own calendar)
REF['sarima'] = A.BACKENDS['sarima'].forecast(A.SERIES, STEPS)
REF['climatology'] = A.GUARD.climatology(STEPS, A.BACKENDS['sarima'].start_month if False else A.BACKENDS['lstm'].start_month)


def wrong(d):
    tier = d['tier']
    ref = REF.get(tier)
    if ref is None:
        return False
    for v in V:
        x = d[v]
        if any(t is None for t in x):
            return True
        if np.max(np.abs(np.asarray(x, float) - np.asarray(ref[v], float))) / A.SD[v] > 0.05:
            return True
    return False


def apply(w, o):
    A._heal_all()
    if w == 'bitflip':
        A._inject_weights('bitflip', 8)
    elif w == 'scaler':
        A._inject_weights('scaler')
    elif w == 'corrupt':
        A._STATE['corrupt'] = True
    if o:
        A._FAULT_MODE['mode'] = o


CONFIGS = {'E4': dict(golden=False, deadline=0.0), 'G4': dict(golden=True, deadline=0.0), 'H4': dict(golden=True, deadline=0.8)}
SCEN = [('bitflip', 'flatline'), ('bitflip', 'stale'), ('scaler', 'unitchange'), ('bitflip', 'delay'), ('corrupt', 'delay'), ('scaler', 'flatline')]
res = {}
for cname, cfg in CONFIGS.items():
    A.GOLDEN_ON = cfg['golden']
    A.DEADLINE_S = cfg['deadline']
    for w, o in SCEN:
        apply(w, o)
        time.sleep(3.5)                         # let the 1 s canary and the circuit breaker react
        tiers, lat, wr, fail = {}, [], 0, 0
        for _ in range(25):
            t = time.time()
            r = c.get('/predict?model=lstm&steps=6')
            lat.append((time.time() - t) * 1000)
            if r.status_code != 200:
                fail += 1
                continue
            d = r.get_json()
            tiers[d['tier']] = tiers.get(d['tier'], 0) + 1
            wr += wrong(d)
        A._heal_all()
        time.sleep(3.0)
        key = f'{cname}|{w}+{o}'
        res[key] = {'wrong_pct': round(100 * wr / 25, 1), 'failed_pct': round(100 * fail / 25, 1), 'tiers': tiers, 'p95_ms': round(float(np.percentile(lat, 95)))}
        print(key, res[key], flush=True)
json.dump(res, open(os.path.join(ROOT, 'results', 'compound_faults.json'), 'w'), indent=1)
