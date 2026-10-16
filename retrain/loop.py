"""Addition 2: drift-triggered retraining loop with shadow-gated promotion (local prototype).

  trigger  : /aging says retrain_recommended (model age > Weibull median, PSI alert, or Page-Hinkley alert)
  retrain  : train LSTM candidates on all available data into a candidate directory (never served)
  shadow   : start the service with SHADOW_LSTM_DIR=candidate, replay N requests, read shadow_total / shadow_reject
  decision : promote (copy candidate over production LSTM dir, keep a backup) only if reject ratio <= MAX_REJECT
Every decision is appended to results/retrain_log.jsonl.

  python retrain/loop.py --epochs 30 --requests 40
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time
import warnings

warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, 'inference-api')
sys.path.insert(0, API)
os.chdir(API)


def train_candidate(cand_dir, epochs):
    import utils.lstm_model as lm
    from utils.preprocessing import load_data, preprocess, aggregate_monthly
    monthly = aggregate_monthly(preprocess(load_data('data.csv')))
    os.makedirs(cand_dir, exist_ok=True)
    lm.MODELS_DIR = cand_dir
    res = {}
    for v in ['Rainfall', 'Temp_mean', 'Humidity']:
        t = time.time()
        _, _, _, metrics = lm.train_lstm_model(monthly[v], v, epochs=epochs)
        res[v] = {'train_seconds': round(time.time() - t, 1), 'metrics': {k: float(x) for k, x in metrics.items()
                  if isinstance(x, (int, float))}}
    return res


def shadow_eval(cand_dir, requests_n):
    os.environ['SEMANTIC_GUARD'] = '1'
    os.environ['SHADOW_LSTM_DIR'] = cand_dir
    import importlib
    import app as A
    importlib.reload(A)
    c = A.app.test_client()
    for _ in range(requests_n):
        c.get('/predict?model=auto&steps=12')
    time.sleep(3)
    tot = rej = 0.0
    for line in c.get('/metrics').data.decode().splitlines():
        if line.startswith('shadow_total_total'):
            tot = float(line.split()[-1])
        if line.startswith('shadow_reject_total'):
            rej = float(line.split()[-1])
    score = [l for l in c.get('/metrics').data.decode().splitlines() if l.startswith('shadow_score')]
    return tot, rej, score, c.get('/aging').get_json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=30)
    p.add_argument('--requests', type=int, default=40)
    p.add_argument('--max-reject', type=float, default=0.05)
    p.add_argument('--force', action='store_true', help='retrain even if no trigger fires')
    a = p.parse_args()
    prod = os.path.join(API, 'saved_models', 'lstm')
    cand = os.path.join(API, 'saved_models', 'lstm_candidate')
    log = os.path.join(ROOT, 'results', 'retrain_log.jsonl')
    # trigger
    os.environ['SEMANTIC_GUARD'] = '1'
    os.environ.pop('SHADOW_LSTM_DIR', None)
    import app as A
    ag = A.app.test_client().get('/aging').get_json()
    rec = {'t': datetime.datetime.utcnow().isoformat() + 'Z', 'trigger': {
        'model_age_months': ag['model_age_months'], 'retrain_after_months': ag['retrain_after_months'],
        'psi': ag['drift'].get('psi'), 'psi_alert': ag['drift'].get('psi_alert'),
        'ph_alert': ag['drift'].get('ph_alert'), 'retrain_recommended': ag['retrain_recommended']}}
    if not ag['retrain_recommended'] and not a.force:
        rec['decision'] = 'no_trigger'
    else:
        rec['train'] = train_candidate(cand, a.epochs)
        tot, rej, score, _ = shadow_eval(cand, a.requests)
        ratio = rej / max(tot, 1)
        rec['shadow'] = {'samples': tot, 'rejects': rej, 'ratio': round(ratio, 3), 'last_score': score}
        if tot >= 10 and ratio <= a.max_reject:
            bak = prod + '_backup_' + datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
            shutil.copytree(prod, bak)
            for f in os.listdir(cand):
                shutil.copy2(os.path.join(cand, f), os.path.join(prod, f))
            rec['decision'] = 'promoted'
            rec['backup'] = bak
        else:
            rec['decision'] = 'rejected'
    os.makedirs(os.path.dirname(log), exist_ok=True)
    open(log, 'a').write(json.dumps(rec) + '\n')
    print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
