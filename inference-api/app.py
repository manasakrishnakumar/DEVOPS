"""Inference API: SARIMA + LSTM forecasting with semantic guard, tiered degradation, health and metrics.

SEMANTIC_GUARD=0 (default) reproduces the baseline behaviour: first requested model is returned as-is.
SEMANTIC_GUARD=1 enables: conformal envelope check -> tier fall-through
  requested model -> lstm -> sarima -> climatology -> last-good cache.
"""
import os
import signal
import time
import warnings

warnings.filterwarnings('ignore')

import numpy as np
from flask import Flask, jsonify, request, Response

import metrics
from backends import SarimaBackend, LstmBackend, VARS
from guard import SemanticGuard
from drift import psi, page_hinkley
import json
from utils.preprocessing import load_data, preprocess, aggregate_monthly
from utils.anomaly_detection import get_baseline_for_flask, compute_ces_single

app = Flask(__name__)

if os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'):       # optional distributed tracing (X: OpenTelemetry); off unless the env var is set
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    _tp = TracerProvider(resource=Resource.create({'service.name': os.environ.get('OTEL_SERVICE_NAME', 'climate-service')}))
    _tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_tp)
    FlaskInstrumentor().instrument_app(app, excluded_urls='metrics,health,healthz')
    RequestsInstrumentor().instrument()
DATA_PATH = os.environ.get('DATA_PATH', 'data.csv')
ENABLED = os.environ.get('MODELS', 'sarima,lstm').split(',')
LAZY_LSTM = os.environ.get('LOAD_MODE', 'eager') == 'lazy'          # X31: load the LSTM on first use
GOLDEN_ON = os.environ.get('GOLDEN_CHECK', '0') == '1'            # integrity canary: output must equal the healthy start-up output
GOLDEN_TOL = float(os.environ.get('GOLDEN_TOL', '0.002'))          # in history-std units (deterministic models: noise is ~1e-7)
DEADLINE_S = float(os.environ.get('DEADLINE_MS', '0')) / 1000.0     # per-request time budget; 0 = off (deadline- and load-aware degradation)
TIER_CONC = {'lstm': int(os.environ.get('LSTM_CONC', '2')), 'sarima': int(os.environ.get('SARIMA_CONC', '3'))}   # max queued/running calls per tier
MM_ON = os.environ.get('METAMORPHIC', '0') == '1'                  # reference-free metamorphic readiness probe (LSTM)
MM_EVERY = int(os.environ.get('METAMORPHIC_EVERY', '6'))            # run the probe every N canary rounds
DISABLE_CLIM = os.environ.get('DISABLE_CLIMATOLOGY', '0') == '1'   # X15: force the cache tier
try:
    INTERVALS = json.load(open('intervals.json'))['half_width']      # X21: conformal half-widths (90 %)
except Exception:
    INTERVALS = None
GUARD_ON = os.environ.get('SEMANTIC_GUARD', '0') == '1'
DISAGREE_THR = float(os.environ.get('DISAGREE_THR', '1.0'))   # in history std units
TIERS = ['lstm', 'sarima', 'climatology', 'cache']
ENERGY_AWARE = os.environ.get('ENERGY_AWARE', '0') == '1'
AUDIT_EVERY = int(os.environ.get('AUDIT_EVERY', '10'))     # full cross-model vote every N requests when energy-aware
CPU_WATTS = float(os.environ.get('CPU_WATTS', '15'))       # assumed power per busy core (no RAPL in containers)
AGING_FILE = os.environ.get('AGING_FILE', 'aging.json')

_t = time.time()
monthly = aggregate_monthly(preprocess(load_data(DATA_PATH)))
SERIES = {v: monthly[v].values for v in VARS}
BASELINE = get_baseline_for_flask()
GUARD = SemanticGuard(monthly, alpha=float(os.environ.get('GUARD_ALPHA', '0.01'))).load_invariants(
    os.environ.get('INVARIANTS_FILE', 'invariants.json'))
BACKENDS = {}
for _n in ENABLED:  # models are loaded once at startup, never per request
    _b = {'sarima': SarimaBackend, 'lstm': LstmBackend}[_n.strip()]()
    if LAZY_LSTM and _b.name == 'lstm':
        _b.ready, _b.lazy = True, True
    else:
        _b.load()
    BACKENDS[_b.name] = _b
if 'lstm' in BACKENDS:   # LSTM forecasts continue from the end of the data
    BACKENDS['lstm'].start_month = int(monthly['Month'].iloc[-1]) % 12 + 1
# --- Novelty 5: shadow candidate model (mirrored traffic, never served) ---
CAND = None
_SHADOW_DIR = os.environ.get('SHADOW_LSTM_DIR')
if _SHADOW_DIR and 'lstm' in BACKENDS:
    import utils.lstm_model as _lm
    _orig_dir = _lm.MODELS_DIR
    _lm.MODELS_DIR = _SHADOW_DIR
    CAND = LstmBackend()
    CAND.load()
    _lm.MODELS_DIR = _orig_dir
    CAND.start_month = BACKENDS['lstm'].start_month
from metamorphic import MetamorphicProbe
MMP = MetamorphicProbe()
GOLDEN = {}
SD = {v: float(np.std(SERIES[v])) for v in VARS}
for _n2, _b2 in BACKENDS.items():
    if _b2.ready and not getattr(_b2, 'lazy', False):
        GOLDEN[_n2] = _b2.forecast(SERIES, 24)
metrics.gauge('startup_seconds', round(time.time() - _t, 3))
_STATE = {'corrupt': False, 'n': 0}
_CACHE = {}
_COST = {}        # EWMA CPU-seconds per request per tier (energy proxy)
_SUSPECT = {}     # last audit verdict per tier
_MM = {'score': None, 'detail': {}, 'n': 0}


def mm_forecast(b, series, steps):
    fc = b.forecast(series, steps)
    if _STATE['corrupt']:
        fc = {v: np.full(steps, np.nan) for v in fc}
    return _apply_output_fault(fc)


def mm_probe():
    """Metamorphic readiness probe on the LSTM; returns the worst normalised violation (<= 1 valid) or None if unavailable."""
    b = BACKENDS.get('lstm')
    if not MM_ON or b is None or not b.ready or not MMP.ready:
        return None
    with _RUN_LOCK:
        s, d = MMP.score(lambda ser, k: mm_forecast(b, ser, k), SERIES, SD)
    _MM.update(score=s, detail=d)
    metrics.gauge('metamorphic_score', round(s, 3) if np.isfinite(s) else 1e9)
    if s > 1.0:
        metrics.inc('metamorphic_violation', backend='lstm')
    return s


def golden_dev(tier, fc):
    """Largest deviation from the healthy start-up forecast, in history-std units (inf if non-finite). 0 if no golden output."""
    g = GOLDEN.get(tier)
    if not g:
        return 0.0
    k = min(len(fc[VARS[0]]), 24)
    dev = 0.0
    for v in VARS:
        x = np.asarray(fc[v][:k], dtype=float)
        if not np.all(np.isfinite(x)):
            return float('inf')
        dev = max(dev, float(np.max(np.abs(x - np.asarray(g[v][:k], dtype=float)))) / SD[v])
    return dev
FAULTS = os.environ.get('FAULT_INJECTION') == '1'


from concurrent.futures import ThreadPoolExecutor
import threading
from collections import deque
_RUN_LOCK = threading.RLock()
_SLO = {'total': 0, 'invalid': 0, 'degraded': 0, 'ref': [], 'live': deque(maxlen=100)}
_POOL = ThreadPoolExecutor(max_workers=1)


_SHADOW = {'total': 0, 'reject': 0, 'scores': [], 't0': None, 't_decision': None, 'decision': None, 'name': None}
GATE_MIN_SAMPLES, GATE_MAX_REJECT = 20, 0.05


def _shadow_update(bad, score, dis):
    s = _SHADOW
    s['total'] += 1
    s['reject'] += 1 if bad else 0
    if len(s['scores']) < 500:
        s['scores'].append(round(float(score), 3) if np.isfinite(score) else 1e9)
    ratio = s['reject'] / s['total']
    if s['decision'] is None and s['t0'] is not None:
        if s['total'] >= 10 and ratio > GATE_MAX_REJECT:                 # early reject
            s['decision'], s['t_decision'] = 'reject', round(time.time() - s['t0'], 2)
        elif s['total'] >= GATE_MIN_SAMPLES and ratio <= GATE_MAX_REJECT:
            s['decision'], s['t_decision'] = 'promote', round(time.time() - s['t0'], 2)


def shadow_check(steps):
    """Evaluate the candidate on the same request: conformal envelope + vote against production versions."""
    try:
        fc = CAND.forecast(SERIES, steps)
        score = GUARD.score(fc, CAND.start_month)
        mem = {'candidate': fc, 'climatology': GUARD.climatology(steps, CAND.start_month)}
        if 'sarima' in BACKENDS and 'lstm' in BACKENDS:   # align SARIMA to the LSTM calendar
            off = (CAND.start_month - BACKENDS['sarima'].start_month) % 12
            full = BACKENDS['sarima'].forecast(SERIES, steps + off)
            mem['sarima'] = {v: full[v][off:off + steps] for v in VARS}
        dis = GUARD.disagreement(mem).get('candidate', 0.0) if len(mem) >= 3 else 0.0
        bad = (not np.isfinite(score)) or score > 1.0 or dis > DISAGREE_THR
        metrics.inc('shadow_total')
        _shadow_update(bad, score, dis)
        if bad:
            metrics.inc('shadow_reject')
        metrics.gauge('shadow_score', round(score, 3) if np.isfinite(score) else 1e9)
        metrics.gauge('shadow_disagreement', round(dis, 3))
    except Exception:
        metrics.inc('shadow_error')


def run_backend(b, steps):
    with _RUN_LOCK:
        return _run_backend(b, steps)


_SEM = {t: threading.BoundedSemaphore(n) for t, n in TIER_CONC.items()}
_EXEC = ThreadPoolExecutor(max_workers=16)
_RESERVE_S = 0.05      # kept free for the cheap fallback tier


def _guarded(b, steps, sem):
    try:
        return run_backend(b, steps)
    finally:
        if sem:
            sem.release()


def timed_run(b, steps, t_end):
    """Deadline- and load-aware call: None means 'shed this tier' (queue full or budget exhausted) so the caller falls to a cheaper tier."""
    if DEADLINE_S <= 0:
        return run_backend(b, steps)
    sem = _SEM.get(b.name)
    if sem and not sem.acquire(blocking=False):
        metrics.inc('shed', tier=b.name, reason='load')
        return None
    remaining = t_end - time.time() - _RESERVE_S
    if remaining <= 0:
        if sem:
            sem.release()
        metrics.inc('shed', tier=b.name, reason='deadline')
        return None
    fut = _EXEC.submit(_guarded, b, steps, sem)
    try:
        return fut.result(timeout=remaining)
    except Exception as e:
        if isinstance(e, TimeoutError) or type(e).__name__ == 'TimeoutError':
            metrics.inc('shed', tier=b.name, reason='timeout')
            return None
        raise


_FAULT_MODE = {'mode': None}
_SAVED = {}
FAULT_MODES = ('corrupt', 'bitflip', 'bitflip_severe', 'stale', 'scaler', 'unitchange', 'flatline', 'delay')


_LEAK = []
_LEAK_STATE = {'run': False}
_DRIFT_T0 = {'t': None}


def _leak_worker():
    while _LEAK_STATE['run'] and len(_LEAK) < 120:      # about 25 MB per second until the cgroup limit kills the worker
        _LEAK.append(bytes([1]) * (25 * 1024 * 1024))
        time.sleep(1.0)


def _rss_bytes():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 0


def _apply_output_fault(fc):
    m = _FAULT_MODE['mode']
    if m == 'drift' and _DRIFT_T0['t'] is not None:      # gradual scaler decay: temperature x (1 -> 0.35) over 90 s
        frac = min(1.0, (time.time() - _DRIFT_T0['t']) / 90.0)
        fc = {**fc, 'Temp_mean': np.asarray(fc['Temp_mean'], float) * (1.0 - 0.65 * frac)}
    if m == 'unitchange':      # Celsius reported as Fahrenheit
        fc = {**fc, 'Temp_mean': np.asarray(fc['Temp_mean'], float) * 9 / 5 + 32}
    elif m == 'flatline':      # output stuck at its first value
        fc = {v: np.full(len(fc[v]), float(fc[v][0])) for v in fc}
    elif m == 'stale':         # stale input window -> calendar-misaligned forecast
        fc = {v: np.roll(np.asarray(fc[v], float), max(1, len(fc[v]) // 2)) for v in fc}
    return fc


def _inject_weights(kind, n_flips=8):
    """bitflip: flip an exponent bit in a few LSTM kernel weights (in memory).  scaler: corrupt the scaler."""
    b = BACKENDS.get('lstm')
    if b is None:
        return
    rng = np.random.default_rng(7)
    for v, pair in b.models.items():
        model, scaler = pair
        if kind == 'bitflip':
            w = model.get_weights()
            _SAVED.setdefault(('w', v), [x.copy() for x in w])
            arr = np.ascontiguousarray(w[0], dtype=np.float32)
            flat = arr.reshape(-1)
            idx = rng.choice(flat.size, n_flips, replace=False)
            ints = flat.view(np.uint32)
            ints[idx] ^= np.uint32(1 << 30)   # exponent MSB: large but usually finite, plausible-but-wrong output
            w[0] = arr
            model.set_weights(w)
        else:
            _SAVED.setdefault(('s', v), (scaler.scale_.copy(), scaler.min_.copy()))
            scaler.scale_ = scaler.scale_ * 0.35


def _restore_dropvar():
    b = BACKENDS.get('lstm')
    if b is not None and ('d', 'Humidity') in _SAVED:
        b.models['Humidity'] = _SAVED.pop(('d', 'Humidity'))
        b.ready = all(x is not None for x in b.models.values())


def _heal_all():
    _restore_dropvar()
    _LEAK_STATE['run'] = False
    _LEAK.clear()
    _DRIFT_T0['t'] = None
    _FAULT_MODE['mode'] = None
    _STATE['corrupt'] = False
    b = BACKENDS.get('lstm')
    if b is not None:
        for v, (model, scaler) in b.models.items():
            if ('w', v) in _SAVED:
                model.set_weights(_SAVED.pop(('w', v)))
            if ('s', v) in _SAVED:
                scaler.scale_, scaler.min_ = _SAVED.pop(('s', v))


def _run_backend(b, steps):
    if getattr(b, 'lazy', False) and not b.models:
        b.load()
        b.lazy = False
    if _FAULT_MODE['mode'] == 'delay' and np.random.random() < 0.3:
        time.sleep(1.5)
    c0 = time.process_time()
    fc = b.forecast(SERIES, steps)
    cpu = time.process_time() - c0
    _COST[b.name] = cpu if b.name not in _COST else 0.8 * _COST[b.name] + 0.2 * cpu
    metrics.add('tier_cpu_seconds', cpu, tier=b.name)
    metrics.add('energy_joules', cpu * CPU_WATTS, tier=b.name)
    if _STATE['corrupt']:  # injected silent fault: HTTP 200 with garbage values
        fc = {v: np.full(steps, np.nan) for v in VARS}
    return _apply_output_fault(fc)


def tier_chain(model):
    if ENERGY_AWARE and model == 'auto':      # cheapest measured tier first
        order = sorted((t for t in BACKENDS), key=lambda t: _COST.get(t, 0.0))
        return order + ['climatology', 'cache']
    chain = []
    if model in BACKENDS:
        chain.append(model)
    for t in TIERS:
        if t not in chain:
            chain.append(t)
    return chain


def serve(model, steps):
    """Return (forecast dict, tier name, info dict) or (None, None, info)."""
    info = {}
    if not GUARD_ON:   # baseline: no semantic checks, first usable backend only
        if model == 'auto':
            for n in ('lstm', 'sarima'):
                if n in BACKENDS and BACKENDS[n].ready:
                    return run_backend(BACKENDS[n], steps), n, info
            return None, None, info
        b = BACKENDS.get(model)
        return (run_backend(b, steps), b.name, info) if b and b.ready else (None, None, info)

    _STATE['n'] += 1
    t_end = time.time() + DEADLINE_S
    for tier in tier_chain(model):
        if tier in BACKENDS:
            b = BACKENDS[tier]
            if not b.ready or _SUSPECT.get(tier):      # canary marked this version suspect (cross-model vote)
                continue
            fc = timed_run(b, steps, t_end)
            if fc is None:
                continue
            score = GUARD.score(fc, b.start_month)   # cheap conformal envelope check on the output itself
            metrics.gauge('semantic_score', round(score, 3) if np.isfinite(score) else 1e9, backend=tier)
            if score <= 1.0 and GOLDEN_ON and golden_dev(tier, fc) > GOLDEN_TOL:
                _SUSPECT[tier] = True
                metrics.inc('golden_reject', backend=tier)
                continue
            if score <= 1.0:
                _CACHE[steps] = fc
                return fc, tier, info
            _SUSPECT[tier] = True          # circuit breaker: skip this tier until the next canary re-validates it
            metrics.inc('semantic_reject', backend=tier)
        elif tier == 'climatology' and not DISABLE_CLIM:
            ref = BACKENDS['lstm'].start_month if 'lstm' in BACKENDS else 1
            sm = BACKENDS[model].start_month if model in BACKENDS else ref
            return GUARD.climatology(steps, sm), 'climatology', info
        elif tier == 'cache' and steps in _CACHE:
            return _CACHE[steps], 'cache', info
    return None, None, info


def canary_once(steps=6):
    """Novelty 2 as a periodic canary: run every version, align calendar months, vote, update suspect flags."""
    ref = BACKENDS['lstm'].start_month if 'lstm' in BACKENDS else 1
    aligned, scores = {}, {}
    for tier, b in BACKENDS.items():
        if not b.ready:
            continue
        off = (ref - b.start_month) % 12
        full = run_backend(b, steps + off)
        fc = {v: full[v][:steps] for v in VARS}
        scores[tier] = GUARD.score(fc, b.start_month)
        if GOLDEN_ON and golden_dev(tier, fc) > GOLDEN_TOL:
            scores[tier] = max(scores[tier], 1.0 + 1e-6)          # integrity violation counts as invalid
            metrics.inc('golden_violation', backend=tier)
        aligned[tier] = {v: full[v][off:off + steps] for v in VARS}
        metrics.gauge('semantic_score', round(scores[tier], 3) if np.isfinite(scores[tier]) else 1e9, backend=tier)
    _MM['n'] += 1
    if MM_ON and 'lstm' in scores and (_MM['n'] % MM_EVERY == 1 or (_MM['score'] or 0) > 1.0):
        s = mm_probe()
        if s is not None and s > 1.0:
            scores['lstm'] = max(scores['lstm'], 1.0 + 1e-6)
    aligned['climatology'] = GUARD.climatology(steps, ref)
    ok = {t: aligned[t] for t in aligned if t == 'climatology' or np.isfinite(scores.get(t, np.inf))}
    dis = GUARD.disagreement(ok)
    for t in BACKENDS:
        bad = (t in scores and (not np.isfinite(scores[t]) or scores[t] > 1.0)) or dis.get(t, 0.0) > DISAGREE_THR
        _SUSPECT[t] = bool(bad)
        if bad:
            metrics.inc('semantic_suspect', backend=t)
        metrics.gauge('semantic_disagreement', round(dis.get(t, 0.0), 3), backend=t)
    return dis


def canary_loop():
    period = float(os.environ.get('CANARY_SECONDS', '5'))
    time.sleep(2)
    while True:
        try:
            canary_once()
        except Exception:
            metrics.inc('canary_error')
        time.sleep(period)


# --- Addition 1/2: aging + drift (computed once at start-up from the LSTM's out-of-sample one-step errors) ---
def _drift_state():
    out = {'psi': {}, 'ph_alarm_index': {}, 'psi_alert': False, 'ph_alert': False}
    try:
        y_years = monthly['Year'].values
        mm = monthly['Month'].values.astype(int)
        for v in VARS:   # deseasonalise with the reference-period month mean/std, then compare distributions
            ref_mask = y_years <= 2018
            mu = np.array([np.mean(SERIES[v][ref_mask & (mm == m)]) if m else 0 for m in range(13)])
            sd = np.array([max(np.std(SERIES[v][ref_mask & (mm == m)]), 1e-6) if m else 1 for m in range(13)])
            z = (SERIES[v] - mu[mm]) / sd[mm]
            out['psi'][v] = round(psi(z[ref_mask], z[-36:]), 4)
        out['psi_alert'] = bool(max(out['psi'].values()) > 0.25)     # PSI > 0.25 = major shift
        if 'lstm' in BACKENDS and BACKENDS['lstm'].ready:
            for v in VARS:
                m, s = BACKENDS['lstm'].models[v]
                sc = s.transform(SERIES[v].reshape(-1, 1)).ravel()
                X = np.array([sc[i - 12:i] for i in range(12, len(sc))]).reshape(-1, 12, 1)
                pred = s.inverse_transform(m.predict(X, verbose=0)).ravel()
                idx = np.arange(12, len(sc))
                e = np.abs(SERIES[v][idx] - pred) / GUARD.scale[v][monthly['Month'].values[idx].astype(int)]
                e = e[monthly['Year'].values[idx] > 2018]
                al, stat = page_hinkley(e - np.median(e), delta=0.1, lam=8.0)
                out['ph_alarm_index'][v] = al
                out['ph_alert'] = out['ph_alert'] or al is not None
    except Exception as ex:                      # drift is advisory; never break serving
        out['error'] = str(ex)
    return out


_DRIFT = {}


def get_drift():
    """Computed lazily on first use so it never delays readiness / recovery."""
    if not _DRIFT:
        _DRIFT.update(_drift_state())
        for _v, _p in _DRIFT.get('psi', {}).items():
            metrics.gauge('drift_psi', _p, variable=_v)
    return _DRIFT


try:
    AGING = json.load(open(AGING_FILE))
except Exception:
    AGING = None


@app.route('/drift')
def drift():
    return jsonify(get_drift())


@app.route('/aging')
def aging():
    if not AGING:
        return jsonify(error='no aging.json'), 404
    DRIFT = get_drift()
    age = int((monthly['Year'].iloc[-1] - AGING['train_end_year']) * 12 + monthly['Month'].iloc[-1])
    ra = AGING.get('retrain_after_months')
    return jsonify(model_age_months=age, retrain_after_months=ra,
                   retrain_recommended=bool(ra is not None and age > ra) or DRIFT.get('psi_alert', False)
                   or DRIFT.get('ph_alert', False), variables=AGING['variables'], drift=DRIFT)


@app.route('/slo')
def slo():
    """Correctness SLI since start with a 95 % Wilson lower bound (z = 1.645, one-sided)."""
    n, bad = _SLO['total'], _SLO['invalid']
    p = 1 - bad / n if n else 1.0
    z = 1.645
    lower = ((p + z * z / (2 * n) - z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n)) if n else None
    return jsonify(served=n, invalid=bad, degraded=_SLO['degraded'], correctness_sli=round(p, 5),
                   wilson_lower_95=None if lower is None else round(lower, 5),
                   quality_sli=round(1 - (bad + _SLO['degraded']) / n, 5) if n else None)


@app.route('/energy')
def energy():
    return jsonify(cpu_seconds_ewma=_COST, cpu_watts=CPU_WATTS,
                   est_joules_per_request={k: round(v * CPU_WATTS, 3) for k, v in _COST.items()},
                   energy_aware=ENERGY_AWARE)


@app.route('/health/live')
def live():
    return jsonify(status='alive')


@app.route('/health/ready')
def ready():
    st = {n: b.partial_ready() for n, b in BACKENDS.items()}
    ok = all(b.ready for b in BACKENDS.values())
    if request.args.get('partial'):      # X14: ready if every variable has at least one usable tier
        per = {v: [n for n, b in BACKENDS.items() if b.ready and (b.models.get(v) is not None or getattr(b, 'lazy', False))] for v in VARS}
        ok = all(per[v] for v in VARS)
        return jsonify(ready=ok, per_variable=per), (200 if ok else 503)
    return jsonify(ready=ok, models=st), (200 if ok else 503)


@app.route('/health/semantic')
def semantic():
    """Novelty 1: canary inference validated by the conformal envelope (use as readiness/liveness probe)."""
    res, ok = {}, True
    for n, b in BACKENDS.items():
        if not b.ready:
            res[n] = {'valid': False, 'reason': 'not loaded'}
            ok = False
            continue
        fc = run_backend(b, 6)
        s = GUARD.score(fc, b.start_month)
        gd = golden_dev(n, fc)
        mm_bad = bool(MM_ON and n == 'lstm' and _MM['score'] is not None and _MM['score'] > 1.0)
        res[n] = {'valid': bool(s <= 1.0 and not (GOLDEN_ON and gd > GOLDEN_TOL) and not mm_bad), 'metamorphic': (None if n != 'lstm' or _MM['score'] is None else round(min(_MM['score'], 1e9), 3)), 'score': None if not np.isfinite(s) else round(s, 3),
                  'golden_dev': None if not np.isfinite(gd) else round(gd, 5)}
        ok = ok and res[n]['valid']
        metrics.gauge('semantic_valid', int(s <= 1.0), backend=n)
    return jsonify(semantic_ok=ok, backends=res), (200 if ok else 503)


@app.route('/predict')
def predict():
    t0 = time.time()
    model = request.args.get('model', 'auto')
    steps = max(1, min(int(request.args.get('steps', 12)), 60))
    fc, tier, info = serve(model, steps)
    if fc is None:
        metrics.inc('predict_requests', model=model, status='503')
        return jsonify(error=f'model "{model}" unavailable'), 503
    # --- Phase 7: correctness SLI (independent post-hoc check of what was actually served) ---
    try:
        _ref_sm = BACKENDS['lstm'].start_month if 'lstm' in BACKENDS else 1
        _sm = BACKENDS[tier].start_month if tier in BACKENDS else _ref_sm
        _sc = float(GUARD.score(fc, _sm))
        _ok = bool(np.isfinite(_sc) and _sc <= 1.0)
        _SLO['total'] += 1
        _SLO['invalid'] += 0 if _ok else 1
        _SLO['degraded'] += 1 if tier in ('climatology', 'cache') else 0
        metrics.inc('served_valid' if _ok else 'served_invalid', tier=tier)
        if np.isfinite(_sc):
            if len(_SLO['ref']) < 100:
                _SLO['ref'].append(_sc)
            else:
                _SLO['live'].append(_sc)
            if len(_SLO['live']) == 100 and _SLO['total'] % 20 == 0:
                from scipy.stats import ks_2samp
                metrics.gauge('output_score_shift_ks', round(float(ks_2samp(_SLO['ref'], list(_SLO['live'])).statistic), 3))
    except Exception:
        metrics.inc('slo_error')
    _want_iv = bool(request.args.get('interval'))
    out = {'model_used': tier, 'tier': tier, 'degraded': tier in ('climatology', 'cache'), 'steps': steps,
           **{v: [round(float(x), 3) if np.isfinite(x) else None for x in fc[v]] for v in VARS}, **info}
    if all(request.args.get(k) for k in ('rainfall', 'temperature', 'humidity')):
        out['ces'] = compute_ces_single(float(request.args['rainfall']), float(request.args['temperature']),
                                        float(request.args['humidity']), BASELINE)
    if CAND is not None:
        _POOL.submit(shadow_check, steps)
    if _want_iv and INTERVALS:
        out['interval'] = {v: {'lo': [round(float(x) - INTERVALS[v][min(k, len(INTERVALS[v]) - 1)], 3) for k, x in enumerate(out[v]) if x is not None],
                               'hi': [round(float(x) + INTERVALS[v][min(k, len(INTERVALS[v]) - 1)], 3) for k, x in enumerate(out[v]) if x is not None]} for v in VARS}
        out['interval_note'] = '90 % conformal half-width calibrated on LSTM errors 2012-2018; held-out coverage 72-88 %'
    dt = time.time() - t0
    out['latency_ms'] = round(dt * 1000, 2)
    metrics.inc('predict_requests', model=tier, status='200')
    metrics.inc('predict_tier', tier=tier)
    metrics.observe('predict_seconds', dt, model=tier)
    return jsonify(out)


@app.route('/fault')
def fault():
    """Fault injection for chaos experiments (only when FAULT_INJECTION=1)."""
    if not FAULTS:
        return 'disabled', 404
    mode = request.args.get('mode', '')
    if mode == 'crash':        # kill the gunicorn master -> container exits
        os.kill(os.getppid(), signal.SIGQUIT)
        os._exit(1)
    if mode == 'hang':         # block the only worker
        time.sleep(10 ** 6)
    if mode == 'oom':          # allocate until the cgroup limit kills the worker
        junk = []
        while True:
            junk.append(bytes([1]) * (50 * 1024 * 1024))
            time.sleep(0.02)
    if mode == 'corrupt':      # model outputs become NaN while status stays 200
        _STATE['corrupt'] = True
        return jsonify(fault='corrupt')
    if mode == 'dropvar':      # X14: the LSTM model for one variable disappears (corrupt/missing file)
        _heal_all()
        b = BACKENDS['lstm']
        _SAVED[('d', 'Humidity')] = b.models['Humidity']
        b.models['Humidity'] = None
        b.ready = False
        return jsonify(fault='dropvar')
    if mode == 'leak':
        _heal_all()
        _FAULT_MODE['mode'] = 'leak'
        _LEAK_STATE['run'] = True
        threading.Thread(target=_leak_worker, daemon=True).start()
        return jsonify(fault='leak')
    if mode == 'drift':
        _heal_all()
        _FAULT_MODE['mode'] = 'drift'
        _DRIFT_T0['t'] = time.time()
        return jsonify(fault='drift')
    if mode in ('bitflip', 'bitflip_severe', 'scaler', 'stale', 'unitchange', 'flatline', 'delay'):
        _heal_all()
        _FAULT_MODE['mode'] = mode
        if mode == 'bitflip':
            _inject_weights('bitflip', 8)
        elif mode == 'bitflip_severe':
            _inject_weights('bitflip', 16)
        elif mode == 'scaler':
            _inject_weights('scaler')
        return jsonify(fault=mode)
    if mode == 'heal':
        _heal_all()
        return jsonify(fault='healed')
    if mode == 'status':
        return jsonify(mode=_FAULT_MODE['mode'], corrupt=_STATE['corrupt'], guard=GUARD_ON, guard_mode=GUARD.mode,
                       tiers_suspect=_SUSPECT)
    return jsonify(error='unknown mode'), 400


@app.route('/golden/refresh')
def golden_refresh():
    with _RUN_LOCK:
        for n, b in BACKENDS.items():
            if b.ready:
                GOLDEN[n] = b.forecast(SERIES, 24)
    return jsonify(refreshed=list(GOLDEN))


@app.route('/shadow/load')
def shadow_load():
    """Load a candidate LSTM set from a directory inside the pod (runtime, never served) and reset the gate."""
    global CAND
    d = request.args.get('dir', '')
    import utils.lstm_model as _lm
    with _RUN_LOCK:
        orig = _lm.MODELS_DIR
        _lm.MODELS_DIR = d
        try:
            c = LstmBackend()
            c.load()
        finally:
            _lm.MODELS_DIR = orig
        c.start_month = BACKENDS['lstm'].start_month
        CAND = c
    _SHADOW.update(total=0, reject=0, scores=[], t0=time.time(), t_decision=None, decision=None, name=os.path.basename(d))
    return jsonify(ready=c.ready, name=_SHADOW['name'])


@app.route('/shadow/status')
def shadow_status():
    s = _SHADOW
    n = max(s['total'], 1)
    return jsonify(name=s['name'], total=s['total'], rejects=s['reject'], reject_ratio=round(s['reject'] / n, 4),
                   decision=s['decision'], time_to_decision_s=s['t_decision'],
                   median_score=float(np.median(s['scores'])) if s['scores'] else None,
                   elapsed_s=None if s['t0'] is None else round(time.time() - s['t0'], 1))


@app.route('/shadow/clear')
def shadow_clear():
    global CAND
    CAND = None
    _SHADOW.update(total=0, reject=0, scores=[], t0=None, t_decision=None, decision=None, name=None)
    return jsonify(cleared=True)


@app.route('/baseline')
def baseline():
    return jsonify({k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                    for k, v in BASELINE.items()})


@app.route('/metrics')
def prom():
    metrics.gauge('process_rss_bytes', _rss_bytes())
    return Response(metrics.render(), mimetype='text/plain')


if GUARD_ON:
    threading.Thread(target=canary_loop, daemon=True).start()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5001')))
