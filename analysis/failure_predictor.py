"""Phase 10: failure predictor.  Isolation Forest trained on HEALTHY telemetry only (unsupervised) raises an early alarm for
(a) a memory leak that ends in an OOM kill and (b) gradual output drift that ends in a guard rejection.
Baselines: static memory threshold (80 % of the 2500 MiB limit) and the reactive guard (score > 1).
Failure time: leak = request-counter reset / RSS collapse (worker OOM-killed and respawned); drift = first time LSTM semantic score > 1.
Outputs results/predictor_results.json.     python analysis/failure_predictor.py
"""
import glob
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEL = os.path.join(ROOT, 'results', 'telemetry')
MEM_LIMIT_MB = 2500 * 1.048576
FEATS = ['rss_mb', 'rss_slope', 'score_lstm', 'score_slope', 'lat_ms', 'cpu_rate', 'shift_ks']
CONSEC = 3


def features(df):
    df = df.copy()
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df[df['ok'] == 1].reset_index(drop=True)
    t = df['t'].values
    w = 5                                                    # 5 scrapes = 10 s
    def slope(col):
        s = np.full(len(df), 0.0)
        for i in range(w, len(df)):
            s[i] = (df[col].iloc[i] - df[col].iloc[i - w]) / max(t[i] - t[i - w], 1e-6)
        return s
    df['rss_slope'], df['score_slope'] = slope('rss_mb'), slope('score_lstm')
    dl = df['lat_sum'].diff(w) / df['lat_cnt'].diff(w).replace(0, np.nan)
    df['lat_ms'] = (dl * 1000).fillna(0.0)
    df['cpu_rate'] = (df['cpu_s'].diff(w) / pd.Series(t).diff(w)).fillna(0.0)
    df['score_lstm'] = df['score_lstm'].fillna(0.0).clip(upper=50)
    df['shift_ks'] = df['shift_ks'].fillna(0.0)
    return df.iloc[w:].reset_index(drop=True)      # first window has no valid slopes


class Mahalanobis:
    """Distance from the healthy distribution on standardised features (grows without bound out of range)."""
    def fit(self, X):
        X = np.asarray(X, float)
        self.mu = X.mean(0)
        self.sd = X.std(0) + 1e-3 * np.maximum(np.abs(self.mu), 1.0)
        Z = (X - self.mu) / self.sd
        self.inv = np.linalg.inv(np.cov(Z.T) + 1e-3 * np.eye(Z.shape[1]))
        return self

    def score(self, X):
        Z = (np.asarray(X, float) - self.mu) / self.sd
        return np.sqrt(np.maximum(np.einsum('ij,jk,ik->i', Z, self.inv, Z), 0.0))


def first_alarm(flags, t, after):
    run = 0
    for f, ti in zip(flags, t):
        if ti < after:
            run = 0
            continue
        run = run + 1 if f else 0
        if run >= CONSEC:
            return float(ti)
    return None


def load(kind):
    out = []
    for p in sorted(glob.glob(os.path.join(TEL, f'{kind}_*.csv'))):
        meta = json.load(open(p.replace('.csv', '.meta.json')))
        out.append((os.path.basename(p), pd.read_csv(p), meta))
    return out


def main():
    healthy = load('healthy')
    assert len(healthy) >= 2, 'need two healthy recordings (train, calibration/test)'
    train = features(healthy[0][1])
    cal = features(healthy[1][1])
    half = len(cal) // 2
    cal_fit, cal_test = cal.iloc[:half], cal.iloc[half:]
    model = IsolationForest(n_estimators=200, random_state=0, contamination='auto').fit(train[FEATS])
    sc = lambda d: -model.score_samples(d[FEATS])
    maha = Mahalanobis().fit(train[FEATS])
    sm = lambda d: maha.score(d[FEATS])
    thr = float(np.quantile(sc(cal_fit), 0.995))
    thr_m = float(np.quantile(sm(cal_fit), 0.995))
    fa_flags = sc(cal_test) > thr
    fa_flags_m = sm(cal_test) > thr_m
    minutes = (cal_test['t'].iloc[-1] - cal_test['t'].iloc[0]) / 60.0
    fa = int(sum(1 for i in range(len(fa_flags) - CONSEC + 1) if fa_flags[i:i + CONSEC].all() and (i == 0 or not fa_flags[i - 1:i + CONSEC - 1].all())))
    fa_m = int(sum(1 for i in range(len(fa_flags_m) - CONSEC + 1) if fa_flags_m[i:i + CONSEC].all() and (i == 0 or not fa_flags_m[i - 1:i + CONSEC - 1].all())))
    res = {'threshold': thr, 'threshold_mahalanobis': thr_m, 'healthy_false_alarms_mahalanobis': fa_m,
           'healthy_false_alarms': fa, 'healthy_minutes': round(float(minutes), 1),
           'healthy_false_alarms_per_10min': round(fa / max(minutes, 1e-9) * 10, 2), 'scenarios': {}}
    for kind in ('leak', 'drift'):
        rows = []
        for name, raw, meta in load(kind):
            if meta.get('t_inj') is None:
                continue
            df = features(raw)
            t = df['t'].values
            tf = None
            if kind == 'leak':
                # worker killed by the cgroup and respawned: request counter resets or RSS collapses (a failed scrape is
                # not required - the respawn can be faster than the scrape interval)
                r2 = raw.copy()
                for c in ('t', 'lat_cnt', 'rss_mb'):
                    r2[c] = pd.to_numeric(r2[c], errors='coerce')
                r2 = r2[r2['t'] >= meta['t_inj']].reset_index(drop=True)
                reset = np.where((r2['lat_cnt'].diff() < 0) | (r2['rss_mb'] < 0.6 * r2['rss_mb'].shift(1)))[0]
                tf = float(r2['t'].iloc[reset[0]]) if len(reset) else meta.get('t_failure_scrape')
            else:
                idx = np.where((df['score_lstm'].values > 1.0) & (t >= meta['t_inj']))[0]
                tf = float(t[idx[0]]) if len(idx) else None
            if tf is None:
                rows.append({'trial': name, 'failure_time': None})
                continue
            ifa = first_alarm(sc(df) > thr, t, meta['t_inj'])
            mha = first_alarm(sm(df) > thr_m, t, meta['t_inj'])
            mem = first_alarm(df['rss_mb'].values > 0.8 * MEM_LIMIT_MB, t, meta['t_inj'])
            guard = first_alarm(df['score_lstm'].values > 1.0, t, meta['t_inj'])
            lead = lambda a_: None if a_ is None else round(tf - a_, 1)
            rows.append({'trial': name, 'failure_time': round(tf, 1), 'inject_t': meta['t_inj'],
                         'iforest_alarm': ifa, 'iforest_lead_s': lead(ifa), 'mahalanobis_lead_s': lead(mha), 'memory_threshold_lead_s': lead(mem),
                         'reactive_guard_lead_s': lead(guard)})
        ok = [r for r in rows if r.get('failure_time') is not None]
        summ = {'trials': len(rows), 'with_failure': len(ok)}
        for key in ('iforest_lead_s', 'mahalanobis_lead_s', 'memory_threshold_lead_s', 'reactive_guard_lead_s'):
            v = [r[key] for r in ok]
            early = [x for x in v if x is not None and x > 0]
            summ[key] = {'early_before_failure': f'{len(early)}/{len(ok)}',
                         'median_lead_s': round(float(np.median(early)), 1) if early else None}
        res['scenarios'][kind] = {'summary': summ, 'trials': rows}
    json.dump(res, open(os.path.join(ROOT, 'results', 'predictor_results.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'scenarios'}, indent=1))
    for k, v in res['scenarios'].items():
        print(k, json.dumps(v['summary']))


if __name__ == '__main__':
    main()
