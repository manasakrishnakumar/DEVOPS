"""SilentBench-Fuzz: random bit flips in the real LSTM weights, in the real service code (no cluster needed).

The hand-picked eight-flip fault of SilentBench was chosen to stay inside the envelope. This study removes that choice:
for every combination of
    bit-position class  : sign | exponent MSB | other exponent bits | high mantissa | low mantissa | any bit
    number of flips     : 1, 2, 4, 8, 16, 32, 64
random bits are flipped in random weights (all layers, one randomly chosen variable model per trial) and four things are
recorded for the 6-step forecast the service would return:
    wrong            the client oracle of chaos/probe.py (absolute + relative tolerance per variable) calls the answer wrong
    envelope detect  conformal envelope + invariants (GUARD.score > 1) or a non-finite output
    golden detect    golden-output deviation above the tolerance (GOLDEN_TOL)
    control          the same checks on unmodified models (false-alarm control)

    python analysis/bitflip_fuzz.py [--trials 40] [--out results]
"""
import argparse
import json
import math
import os
import sys
import time
import warnings

warnings.filterwarnings('ignore')
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get('FUZZ_API_DIR') or os.path.join(os.path.dirname(HERE), 'inference-api')     # FUZZ_API_DIR=/app runs it inside the inference image
os.chdir(API)
sys.path.insert(0, API)
os.environ.update(SEMANTIC_GUARD='1', GUARD_MODE='envelope+inv', GOLDEN_CHECK='1', FAULT_INJECTION='1')
for k in ('SIGNED_GOLDEN_DIR', 'CORRUPT_AT_STARTUP'):
    os.environ.pop(k, None)
import app as A  # noqa: E402

VARS = ['Rainfall', 'Temp_mean', 'Humidity']
TOL = {'Rainfall': (25.0, 0.10), 'Temp_mean': (1.5, 0.05), 'Humidity': (6.0, 0.05)}     # client oracle of chaos/probe.py
CLASSES = {'sign': [31], 'exp_msb': [30], 'exp_other': list(range(23, 30)), 'mant_high': list(range(16, 23)),
           'mant_low': list(range(0, 16)), 'any': list(range(0, 32))}
FLIPS = [1, 2, 4, 8, 16, 32, 64]


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def is_wrong(fc, ref):
    for v in VARS:
        x = np.asarray(fc[v], dtype=float)
        if not np.all(np.isfinite(x)):
            return True
        for a, g in zip(x, ref[v]):
            if abs(a - g) > TOL[v][0] + TOL[v][1] * abs(g):
                return True
    return False


def flip_bits(weights, n, bits, rng):
    """Return a copy of the weight list with n random bit flips (random array, random element, random bit from `bits`)."""
    out = [np.array(w, dtype=np.float32, copy=True) for w in weights]
    sizes = np.array([w.size for w in out], dtype=float)
    for _ in range(n):
        i = rng.choice(len(out), p=sizes / sizes.sum())
        flat = out[i].reshape(-1)
        j = rng.integers(flat.size)
        ints = flat.view(np.uint32)
        ints[j] ^= np.uint32(1 << int(rng.choice(bits)))
    return out


def evaluate(b, ref):
    try:
        fc = b.forecast(A.SERIES, 6)
    except Exception:            # e.g. infinite weights: the service answers HTTP 500 (a LOUD failure, not a silent wrong answer)
        return {'error': True, 'wrong': False, 'env': False, 'golden': False, 'dev': None}
    finite = all(np.all(np.isfinite(np.asarray(fc[v], dtype=float))) for v in VARS)
    score = A.GUARD.score(fc, b.start_month)
    dev = A.golden_dev('lstm', fc)
    return {'error': False, 'wrong': bool(is_wrong(fc, ref)), 'env': bool((not finite) or (not np.isfinite(score)) or score > 1.0),
            'golden': bool((not np.isfinite(dev)) or dev > A.GOLDEN_TOL), 'dev': None if not np.isfinite(dev) else float(dev)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=40)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), 'results'))
    a = ap.parse_args()
    b = A.BACKENDS['lstm']
    ref = {v: np.asarray(x, dtype=float) for v, x in b.forecast(A.SERIES, 6).items()}
    orig = {v: m.get_weights() for v, (m, s) in b.models.items()}
    t0 = time.time()
    control = [evaluate(b, ref) for _ in range(a.trials)]                              # unmodified models
    cells = {}
    for ci, (cls, bits) in enumerate(CLASSES.items()):
        for n in FLIPS:
            rng = np.random.default_rng(10_000 * (ci + 1) + n)
            rows = []
            for _ in range(a.trials):
                v = VARS[int(rng.integers(3))]
                model = b.models[v][0]
                model.set_weights(flip_bits(orig[v], n, bits, rng))
                try:
                    rows.append(evaluate(b, ref))
                finally:
                    model.set_weights(orig[v])
            w = [r for r in rows if r['wrong']]
            k = len(rows)
            cells[f'{cls}|{n}'] = {
                'class': cls, 'flips': n, 'trials': k,
                'error_loud': sum(r['error'] for r in rows),
                'wrong': sum(r['wrong'] for r in rows), 'wrong_ci': wilson(sum(r['wrong'] for r in rows), k),
                'env_detect': sum(r['env'] for r in rows), 'golden_detect': sum(r['golden'] for r in rows),
                'env_detect_given_wrong': sum(r['env'] for r in w), 'golden_detect_given_wrong': sum(r['golden'] for r in w),
                'silent_wrong_env': sum(r['wrong'] and not r['env'] for r in rows),
                'silent_wrong_golden': sum(r['wrong'] and not r['golden'] for r in rows),
                'golden_alarm_harmless': sum(r['golden'] and not r['wrong'] for r in rows),
                # per-trial record (lets the golden tolerance be swept offline): deviation in history-std units (null = non-finite), wrong flag, loud-error flag
                'trial_dev': [None if r['dev'] is None else round(r['dev'], 6) for r in rows],
                'trial_wrong': [int(r['wrong']) for r in rows],
                'trial_error': [int(r['error']) for r in rows],
            }
        print(f'{cls:10s} done  ({time.time() - t0:.0f}s)', flush=True)
    meta = {'trials_per_cell': a.trials, 'classes': {k: [min(v), max(v)] for k, v in CLASSES.items()}, 'flips': FLIPS,
            'oracle_tolerance': TOL, 'golden_tol_history_std': A.GOLDEN_TOL, 'seconds': round(time.time() - t0, 1),
            'cells': len(cells), 'total_trials': a.trials * len(cells), 'control_trials': a.trials}
    ctl = {'trials': len(control), 'env_false_alarms': sum(r['env'] for r in control),
           'golden_false_alarms': sum(r['golden'] for r in control), 'wrong': sum(r['wrong'] for r in control), 'errors': sum(r['error'] for r in control),
           'max_dev': max(r['dev'] or 0.0 for r in control)}
    os.makedirs(a.out, exist_ok=True)
    json.dump({'meta': meta, 'control': ctl, 'cells': cells}, open(os.path.join(a.out, 'bitflip_fuzz.json'), 'w'), indent=1)
    print(json.dumps({'meta': meta, 'control': ctl}))


if __name__ == '__main__':
    main()
