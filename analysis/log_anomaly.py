"""X: log anomaly detection.  Collects inference-api pod logs for healthy windows and windows with injected faults (via the pod),
normalises lines to templates (digits/hex -> <N>), counts templates per 10 s window and scores windows with an Isolation Forest
trained on healthy windows only.  Writes results/extras_log_anomaly.json.   python analysis/log_anomaly.py
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

import numpy as np
from sklearn.ensemble import IsolationForest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run_operator as ro  # noqa: E402

W = 10


def template(line):
    line = re.sub(r'\d{4}-\d\d-\d\d[ T][\d:.,]+', '', line)
    line = re.sub(r'0x[0-9a-f]+|\b\d+(\.\d+)?\b', '<N>', line)
    return line.strip()[:80]


def window_counts(since_s, dur):
    r = subprocess.run(['kubectl', '-n', 'climate', 'logs', 'deploy/inference-api', f'--since={int(since_s)}s'], capture_output=True, text=True)
    return [template(l) for l in r.stdout.splitlines() if l.strip()]


def collect(label, fault, n):
    rows = []
    for _ in range(n):
        if fault:
            ro.pod_get(f'/fault?mode={fault}')
        for _ in range(W // 2):
            ro.pod_get('/predict?model=lstm&steps=3')
            time.sleep(2)
        rows.append((label, window_counts(W + 2, W)))
        if fault:
            ro.pod_get('/fault?mode=heal')
            time.sleep(3)
    return rows


def main():
    data = collect('healthy', None, 25)
    for f in ('corrupt', 'bitflip', 'flatline', 'scaler', 'unitchange', 'stale'):
        data += collect(f, f, 4)
    vocab = sorted({t for _, ts in data for t in ts})
    X = np.array([[Counter(ts).get(v, 0) for v in vocab] for _, ts in data], dtype=float)
    X = np.hstack([X, X.sum(1, keepdims=True)])
    healthy = [i for i, (l, _) in enumerate(data) if l == 'healthy']
    tr, te_h = healthy[:15], healthy[15:]
    m = IsolationForest(n_estimators=200, random_state=0).fit(X[tr])
    thr = np.percentile(-m.score_samples(X[tr]), 95)
    flag = lambda i: bool(-m.score_samples(X[[i]])[0] > thr)
    out = {'templates': len(vocab), 'healthy_holdout_false_alarm_pct': round(100 * np.mean([flag(i) for i in te_h]), 1), 'by_fault_detected_pct': {}}
    for f in {l for l, _ in data if l != 'healthy'}:
        idx = [i for i, (l, _) in enumerate(data) if l == f]
        out['by_fault_detected_pct'][f] = round(100 * np.mean([flag(i) for i in idx]), 1)
    out['note'] = 'logs carry little signal for silent faults when the service does not log them; compare with semantic check (100 %).'
    json.dump(out, open(os.path.join(ROOT, 'results', 'extras_log_anomaly.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
