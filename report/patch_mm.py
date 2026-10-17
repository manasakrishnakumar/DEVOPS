import io
p = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/inference-api/app.py'
a = io.open(p, encoding='utf-8').read()


def rep(o, n):
    global a
    assert o in a, o[:60]
    a = a.replace(o, n, 1)


rep("DISABLE_CLIM = os.environ.get('DISABLE_CLIMATOLOGY', '0') == '1'",
    "MM_ON = os.environ.get('METAMORPHIC', '0') == '1'                  # reference-free metamorphic readiness probe (LSTM)\nMM_EVERY = int(os.environ.get('METAMORPHIC_EVERY', '6'))            # run the probe every N canary rounds\nDISABLE_CLIM = os.environ.get('DISABLE_CLIMATOLOGY', '0') == '1'")
rep("_SUSPECT = {}     # last audit verdict per tier",
    """_SUSPECT = {}     # last audit verdict per tier
_MM = {'score': None, 'detail': {}, 'n': 0}


def mm_forecast(b, series, steps):
    fc = b.forecast(series, steps)
    if _STATE['corrupt']:
        fc = {v: np.full(steps, np.nan) for v in fc}
    return _apply_output_fault(fc)


def mm_probe():
    \"\"\"Metamorphic readiness probe on the LSTM; returns the worst normalised violation (<= 1 valid) or None if unavailable.\"\"\"
    b = BACKENDS.get('lstm')
    if not MM_ON or b is None or not b.ready or not MMP.ready:
        return None
    with _RUN_LOCK:
        s, d = MMP.score(lambda ser, k: mm_forecast(b, ser, k), SERIES, SD)
    _MM.update(score=s, detail=d)
    metrics.gauge('metamorphic_score', round(s, 3) if np.isfinite(s) else 1e9)
    if s > 1.0:
        metrics.inc('metamorphic_violation', backend='lstm')
    return s""")
rep("GOLDEN = {}\nSD = {v: float(np.std(SERIES[v])) for v in VARS}",
    "from metamorphic import MetamorphicProbe\nMMP = MetamorphicProbe()\nGOLDEN = {}\nSD = {v: float(np.std(SERIES[v])) for v in VARS}")
rep("    aligned['climatology'] = GUARD.climatology(steps, ref)\n    ok = {t:",
    """    _MM['n'] += 1
    if MM_ON and 'lstm' in scores and (_MM['n'] % MM_EVERY == 1 or (_MM['score'] or 0) > 1.0):
        s = mm_probe()
        if s is not None and s > 1.0:
            scores['lstm'] = max(scores['lstm'], 1.0 + 1e-6)
    aligned['climatology'] = GUARD.climatology(steps, ref)
    ok = {t:""")
rep("        res[n] = {'valid': bool(s <= 1.0 and not (GOLDEN_ON and gd > GOLDEN_TOL)),",
    "        mm_bad = bool(MM_ON and n == 'lstm' and _MM['score'] is not None and _MM['score'] > 1.0)\n        res[n] = {'valid': bool(s <= 1.0 and not (GOLDEN_ON and gd > GOLDEN_TOL) and not mm_bad), 'metamorphic': (None if n != 'lstm' or _MM['score'] is None else round(min(_MM['score'], 1e9), 3)),")
io.open(p, 'w', encoding='utf-8').write(a)
print('app patched')
