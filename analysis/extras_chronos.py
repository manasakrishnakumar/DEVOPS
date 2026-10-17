"""X17: time-series foundation model (Chronos-T5-tiny, zero-shot) as an extra version. Attempt only: records the reason if the
install or model download fails.  Writes results/extras_chronos.json.   python -X utf8 analysis/extras_chronos.py
"""
import json
import os
import subprocess
import sys
import warnings

import numpy as np

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = {}
try:
    try:
        import torch  # noqa: F401
        from chronos import ChronosPipeline
    except Exception:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'chronos-forecasting'], capture_output=True, text=True, timeout=1500)
        if r.returncode:
            raise RuntimeError('pip install failed: ' + r.stderr[-300:])
        import torch  # noqa: F401
        from chronos import ChronosPipeline
    API = os.path.join(ROOT, 'inference-api')
    sys.path.insert(0, API)
    os.chdir(API)
    import joblib
    from guard import SemanticGuard, VARS
    from utils.preprocessing import load_data, preprocess, aggregate_monthly
    from utils.lstm_model import load_lstm_model, forecast_lstm
    m = aggregate_monthly(preprocess(load_data('data.csv')))
    S = {v: m[v].values.astype(float) for v in VARS}
    n = len(m)
    he = n - 6
    pipe = ChronosPipeline.from_pretrained('amazon/chronos-t5-tiny', device_map='cpu', torch_dtype=torch.float32)
    fc = {'chronos': {}, 'sarima': {}, 'lstm': {}}
    err = {'chronos': {}, 'sarima': {}, 'lstm': {}}
    for v in VARS:
        ctx = torch.tensor(S[v][:he], dtype=torch.float32)
        smp = pipe.predict(ctx, 6, num_samples=20)
        fc['chronos'][v] = np.median(smp[0].numpy(), axis=0)
        sar = joblib.load(f'saved_models/sarima_{v.lower()}.pkl')
        fc['sarima'][v] = np.maximum(np.asarray(sar.get_forecast(steps=6).predicted_mean, float), 0)
        mod, sc = load_lstm_model(v)
        fc['lstm'][v] = forecast_lstm(mod, sc, S[v][:he], 6)
        for k in fc:
            err[k][v] = fc[k][v] - S[v][he:]
    OUT['rmse_Jan_Jun_2024'] = {k: {v: round(float(np.sqrt(np.mean(err[k][v] ** 2))), 3) for v in VARS} for k in fc}
    corr = {}
    for a, b in (('chronos', 'sarima'), ('chronos', 'lstm'), ('sarima', 'lstm')):
        cs = [np.corrcoef(err[a][v], err[b][v])[0, 1] for v in VARS]
        corr[f'{a}~{b}'] = [round(float(c), 2) for c in cs]
    OUT['error_correlation_per_variable'] = corr
    g = SemanticGuard(m)
    mem = {'sarima': fc['sarima'], 'lstm': fc['lstm'], 'climatology': g.climatology(6, 1), 'chronos': fc['chronos']}
    bad = {v: fc['lstm'][v].copy() for v in VARS}
    bad['Temp_mean'] = bad['Temp_mean'] * 0.35
    sub = {v: fc['lstm'][v].copy() for v in VARS}
    sub['Temp_mean'] = sub['Temp_mean'] + 1.2
    res = {}
    for name, keys in (('3_members', ['sarima', 'lstm', 'climatology']), ('4_members_with_chronos', ['sarima', 'lstm', 'climatology', 'chronos'])):
        for label, f in (('healthy', fc['lstm']), ('scaler_x0.35', bad), ('subtle_+1.2C', sub)):
            mm = {k: mem[k] for k in keys}
            mm['lstm'] = f
            res[f'{name}|{label}'] = round(g.disagreement(mm)['lstm'], 3)
    OUT['vote_lstm_disagreement'] = res
    OUT['status'] = 'ok'
except Exception as e:  # noqa: BLE001
    OUT['status'] = f'not completed: {type(e).__name__}: {str(e)[:300]}'
json.dump(OUT, open(os.path.join(ROOT, 'results', 'extras_chronos.json'), 'w'), indent=1)
print(json.dumps(OUT, indent=1))
