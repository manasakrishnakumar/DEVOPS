"""Phase 12 in the cluster: (a) /aging and /drift output, (b) energy-aware vs always-LSTM serving (estimated joules per
request, tier shares, latency), (c) retrain-vs-production hold-out comparison for the 40-epoch retrained candidate.
Writes results/phase12.json.   INFER_TAG=8 python analysis/phase12_cluster.py
"""
import json
import os
import re
import sys
import threading
import time
import warnings

import numpy as np

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run  # noqa: E402
import run_operator as ro  # noqa: E402

OUT = {}


def scrape():
    t = ro.pod_get('/metrics')
    def tot(name):
        return sum(float(m.group(1)) for m in re.finditer(rf'^{name}(?:{{[^}}]*}})? ([0-9.eE+-]+)$', t, re.M))
    tiers = {m.group(1): float(m.group(2)) for m in re.finditer(r'^predict_tier_total{tier="(\w+)"} ([0-9.eE+-]+)$', t, re.M)}
    return {'joules': tot('energy_joules_total'), 'cpu_s': tot('tier_cpu_seconds_total'), 'tiers': tiers}


def energy(mode):
    run.kube('-n', run.KNS, 'set', 'env', 'deploy/inference-api', f'ENERGY_AWARE={mode}')
    run.kube('-n', run.KNS, 'rollout', 'restart', 'deploy/inference-api')
    time.sleep(10)
    ro.wait_ready()
    time.sleep(20)
    s0, res = scrape(), {}
    th = threading.Thread(target=lambda: res.update(p=run.run_probe('E4', [
        '--mode', 'silent', '--base', 'http://inference-api:5001', '--probe-path', '/predict?model=auto&steps=6', '--fault',
        'none', '--rps', '5', '--warmup', '5', '--fault-window', '150', '--heal-window', '2'])))
    th.start()
    th.join(timeout=400)
    s1 = scrape()
    fw = (res.get('p') or [{}])[0].get('fault_window', {})
    n = sum(s1['tiers'].values()) - sum(s0['tiers'].values())
    return {'energy_aware': mode, 'requests': n, 'joules_per_request': round((s1['joules'] - s0['joules']) / max(n, 1), 3),
            'cpu_s_per_request': round((s1['cpu_s'] - s0['cpu_s']) / max(n, 1), 4),
            'tier_counts': {k: s1['tiers'].get(k, 0) - s0['tiers'].get(k, 0) for k in s1['tiers']},
            'p95_ms': fw.get('p95_ms'), 'correct_pct': fw.get('correct_pct')}


def holdout_rmse(d):
    sys.path.insert(0, os.path.join(ROOT, 'inference-api'))
    os.chdir(os.path.join(ROOT, 'inference-api'))
    import joblib
    from tensorflow.keras.models import load_model
    from utils.preprocessing import load_data, preprocess, aggregate_monthly
    m = aggregate_monthly(preprocess(load_data('data.csv')))
    yrs = m['Year'].values.astype(int)
    res = {}
    for var, col in (('rainfall', 'Rainfall'), ('temp_mean', 'Temp_mean'), ('humidity', 'Humidity')):
        mod = load_model(os.path.join(d, f'lstm_{var}.h5'), compile=False)
        sc = joblib.load(os.path.join(d, f'scaler_{var}.pkl'))
        y = m[col].values.astype(float)
        z = sc.transform(y.reshape(-1, 1)).ravel()
        X = np.array([z[i - 12:i] for i in range(12, len(z))]).reshape(-1, 12, 1)
        pred = sc.inverse_transform(mod.predict(X, verbose=0)).ravel()
        idx = np.arange(12, len(z))
        sel = yrs[idx] >= 2019
        res[col] = round(float(np.sqrt(np.mean((y[idx][sel] - pred[sel]) ** 2))), 3)
    return res


def main():
    run.switch_to('E4')
    ro.wait_ready()
    OUT['aging'] = json.loads(ro.pod_get('/aging'))
    OUT['drift'] = json.loads(ro.pod_get('/drift'))
    OUT['energy'] = [energy('0'), energy('1')]
    run.kube('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'ENERGY_AWARE=0')
    cand = os.path.join(ROOT, 'results', 'candidates')
    OUT['holdout_rmse_2019_2024'] = {'production_lstm': holdout_rmse(os.path.join(ROOT, 'inference-api', 'saved_models', 'lstm')),
                                     'retrain_40ep': holdout_rmse(os.path.join(cand, 'retrain_40ep')),
                                     'bad_undertrained_3ep': holdout_rmse(os.path.join(cand, 'bad_undertrained'))}
    json.dump(OUT, open(os.path.join(ROOT, 'results', 'phase12.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: OUT[k] for k in ('energy', 'holdout_rmse_2019_2024')}, indent=1, default=str))


if __name__ == '__main__':
    main()
