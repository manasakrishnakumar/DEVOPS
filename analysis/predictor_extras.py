"""Extras (offline, on results/telemetry): X04 LSTM autoencoder detector, X27 supervised classifier with/without SMOTE,
X23 feature attribution (permutation-based; SHAP not used), X25 Granger-causality screen.
Writes results/predictor_extras.json.   python -X utf8 analysis/predictor_extras.py
"""
import importlib.util
import json
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('fp', os.path.join(ROOT, 'analysis', 'failure_predictor.py'))
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)
from sklearn.ensemble import IsolationForest, RandomForestClassifier  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from imblearn.over_sampling import SMOTE  # noqa: E402

F = fp.FEATS
OUT = {}
healthy = fp.load('healthy')
train, cal = fp.features(healthy[0][1]), fp.features(healthy[1][1])
runs = []                                                    # (kind, name, features df, t_inj, t_fail)
for kind in ('leak', 'drift'):
    for name, raw, meta in fp.load(kind):
        if meta.get('t_inj') is None:
            continue
        df = fp.features(raw)
        t = df['t'].values
        if kind == 'leak':
            r2 = raw.copy()
            for c in ('t', 'lat_cnt', 'rss_mb'):
                r2[c] = pd.to_numeric(r2[c], errors='coerce')
            r2 = r2[r2['t'] >= meta['t_inj']].reset_index(drop=True)
            k = np.where((r2['lat_cnt'].diff() < 0) | (r2['rss_mb'] < 0.6 * r2['rss_mb'].shift(1)))[0]
            tf = float(r2['t'].iloc[k[0]]) if len(k) else None
        else:
            k = np.where((df['score_lstm'].values > 1.0) & (t >= meta['t_inj']))[0]
            tf = float(t[k[0]]) if len(k) else None
        if tf is not None:
            runs.append((kind, name, df, meta['t_inj'], tf))

# ---------------- X04: LSTM autoencoder on sliding windows of healthy features
try:
    from tensorflow import keras
    W = 8
    mu, sd = train[F].mean().values, train[F].std().values + 1e-6
    seq = lambda d: np.array([((d[F].values[i - W:i] - mu) / sd) for i in range(W, len(d))], dtype='float32')
    Xtr = seq(train)
    inp = keras.Input((W, len(F)))
    z = keras.layers.LSTM(16)(inp)
    out = keras.layers.LSTM(len(F), return_sequences=True)(keras.layers.RepeatVector(W)(z))
    ae = keras.Model(inp, out)
    ae.compile('adam', 'mse')
    ae.fit(Xtr, Xtr, epochs=30, batch_size=32, verbose=0)
    err = lambda X: np.mean((ae.predict(X, verbose=0) - X) ** 2, axis=(1, 2))
    thr = float(np.quantile(err(seq(cal.iloc[:len(cal) // 2])), 0.995))
    fa_flags = err(seq(cal.iloc[len(cal) // 2:])) > thr
    res = {'healthy_alarms_in_test_half': int(fa_flags.sum()), 'scenarios': {}}
    for kind in ('leak', 'drift'):
        leads = []
        for k_, name, df, ti, tf in [r for r in runs if r[0] == kind]:
            X = seq(df)
            e = err(X)
            tt = df['t'].values[W:]
            a = fp.first_alarm(e > thr, tt, ti)
            leads.append(None if a is None else round(tf - a, 1))
        early = [x for x in leads if x is not None and x > 0]
        res['scenarios'][kind] = {'early': f'{len(early)}/{len(leads)}', 'median_lead_s': float(np.median(early)) if early else None}
    OUT['X04_lstm_autoencoder'] = res
except Exception as e:  # noqa: BLE001
    OUT['X04_lstm_autoencoder'] = f'unavailable: {e}'

# ---------------- X27: supervised "failure imminent" classifier, leave-one-run-out, with and without SMOTE
def labelled(r):
    kind, name, df, ti, tf = r
    y = ((df['t'] >= ti) & (df['t'] < tf)).astype(int).values
    return np.nan_to_num(df[F].values.astype(float), nan=0.0, posinf=0.0, neginf=0.0), y


data = [labelled(r) for r in runs]
Xh = np.nan_to_num(train[F].values.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
res = {}
for mode in ('plain', 'class_weight', 'smote'):
    f1s = []
    for i in range(len(data)):
        Xtr = np.vstack([Xh] + [d[0] for j, d in enumerate(data) if j != i])
        ytr = np.concatenate([np.zeros(len(Xh), int)] + [d[1] for j, d in enumerate(data) if j != i])
        if mode == 'smote' and ytr.sum() > 5:
            Xtr, ytr = SMOTE(random_state=0, k_neighbors=min(5, int(ytr.sum()) - 1)).fit_resample(Xtr, ytr)
        clf = RandomForestClassifier(n_estimators=200, random_state=0, class_weight='balanced' if mode == 'class_weight' else None).fit(Xtr, ytr)
        f1s.append(f1_score(data[i][1], clf.predict(data[i][0]), zero_division=0))
    res[mode] = {'mean_f1': round(float(np.mean(f1s)), 3), 'runs': len(f1s)}
OUT['X27_supervised_f1_leave_one_run_out'] = res

# ---------------- X23: permutation attribution of the Isolation Forest score (replace a feature by its healthy median)
iso = IsolationForest(n_estimators=200, random_state=0).fit(train[F])
med = train[F].median()
attr = {}
for kind in ('leak', 'drift'):
    contrib = np.zeros(len(F))
    n = 0
    for k_, name, df, ti, tf in [r for r in runs if r[0] == kind]:
        seg = df[(df['t'] >= ti) & (df['t'] < tf)][F]
        if seg.empty:
            continue
        base = -iso.score_samples(seg)
        for j, f in enumerate(F):
            alt = seg.copy()
            alt[f] = med[f]
            contrib[j] += float(np.mean(base - (-iso.score_samples(alt))))
        n += 1
    attr[kind] = {f: round(float(c / max(n, 1)), 4) for f, c in sorted(zip(F, contrib), key=lambda x: -x[1])}
OUT['X23_attribution_score_drop_when_feature_neutralised'] = attr

# ---------------- X25: Granger-causality screen (does feature X help predict latency, p < 0.05, maxlag 3)
from statsmodels.tsa.stattools import grangercausalitytests  # noqa: E402
g = {}
for kind in ('leak', 'drift'):
    pv = {f: [] for f in F if f != 'lat_ms'}
    for k_, name, df, ti, tf in [r for r in runs if r[0] == kind]:
        seg = df[(df['t'] >= ti - 20) & (df['t'] <= tf)]
        for f in pv:
            try:
                a = seg[['lat_ms', f]].diff().dropna()
                if a[f].std() < 1e-9 or len(a) < 15:
                    continue
                r = grangercausalitytests(a, maxlag=3, verbose=False)
                pv[f].append(min(r[l][0]['ssr_ftest'][1] for l in r))
            except Exception:
                pass
    g[kind] = {f: {'runs_tested': len(v), 'significant_runs': int(sum(p < 0.05 for p in v))} for f, v in pv.items() if v}
OUT['X25_granger_to_latency'] = g
json.dump(OUT, open(os.path.join(ROOT, 'results', 'predictor_extras.json'), 'w'), indent=1)
print(json.dumps(OUT, indent=1)[:3000])
