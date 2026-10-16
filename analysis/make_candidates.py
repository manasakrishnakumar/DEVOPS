"""Phase 11/12: build candidate LSTM sets (good and deliberately bad) into results/candidates/<name>/.
good_copy, good_noise, bad_scaler, bad_swap, bad_bitflip, bad_nan, bad_undertrained (3 epochs), retrain_40ep (all data).
  python analysis/make_candidates.py
"""
import os
import shutil
import sys
import warnings

import joblib
import numpy as np

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, 'inference-api')
sys.path.insert(0, API)
os.chdir(API)
from tensorflow.keras.models import load_model  # noqa: E402
import utils.lstm_model as lm  # noqa: E402
from utils.preprocessing import load_data, preprocess, aggregate_monthly  # noqa: E402

SRC = os.path.join(API, 'saved_models', 'lstm')
OUT = os.path.join(ROOT, 'results', 'candidates')
VARS = ['rainfall', 'temp_mean', 'humidity']
rng = np.random.default_rng(3)


def fresh(name):
    d = os.path.join(OUT, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(SRC, d)
    return d


def edit_models(d, fn):
    for v in VARS:
        p = os.path.join(d, f'lstm_{v}.h5')
        m = load_model(p, compile=False)
        w = m.get_weights()
        w = fn(w)
        m.set_weights(w)
        m.save(p)


def noise(w):
    return [x + rng.normal(0, 1e-3, x.shape).astype(x.dtype) for x in w]


def bitflip(w):
    arr = np.ascontiguousarray(w[0], dtype=np.float32)
    flat = arr.reshape(-1)
    idx = rng.choice(flat.size, 16, replace=False)
    flat.view(np.uint32)[idx] ^= np.uint32(1 << 30)
    w[0] = arr
    return w


def nan_weight(w):
    w[0] = w[0].copy()
    w[0].reshape(-1)[0] = np.nan
    return w


os.makedirs(OUT, exist_ok=True)
fresh('good_copy')
edit_models(fresh('good_noise'), noise)
d = fresh('bad_scaler')
s = joblib.load(os.path.join(d, 'scaler_temp_mean.pkl'))
s.scale_ = s.scale_ * 0.35
joblib.dump(s, os.path.join(d, 'scaler_temp_mean.pkl'))
d = fresh('bad_swap')                                   # humidity and temperature scalers swapped
a, b = os.path.join(d, 'scaler_humidity.pkl'), os.path.join(d, 'scaler_temp_mean.pkl')
sa, sb = joblib.load(a), joblib.load(b)
joblib.dump(sb, a)
joblib.dump(sa, b)
edit_models(fresh('bad_bitflip'), bitflip)
edit_models(fresh('bad_nan'), nan_weight)

monthly = aggregate_monthly(preprocess(load_data(os.path.join(API, 'data.csv'))))
for name, epochs in (('bad_undertrained', 3), ('retrain_40ep', 40)):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    lm.MODELS_DIR = d
    for var, col in (('Rainfall', 'Rainfall'), ('Temp_mean', 'Temp_mean'), ('Humidity', 'Humidity')):
        lm.train_lstm_model(monthly[col], var, epochs=epochs)
    print('trained', name, flush=True)
print('candidates:', sorted(os.listdir(OUT)))
