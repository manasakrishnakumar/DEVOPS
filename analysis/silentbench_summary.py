"""Summarise results/silentbench.jsonl -> results/silentbench_summary.csv and a printed markdown table."""
import csv
import json
import os
import statistics
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'silentbench.jsonl')) if l.strip()]
g = defaultdict(list)
for r in rows:
    if r.get('fault_window'):
        g[(r['config'], r['fault'])].append(r)
FAULTS = ['corrupt', 'bitflip', 'bitflip_severe', 'stale', 'scaler', 'unitchange', 'flatline', 'delay', 'none']
CFGS = ['C4', 'D4', 'E4']
out = []
for c in CFGS:
    for f in FAULTS:
        k = g.get((c, f))
        if not k:
            continue
        fw = lambda key: statistics.mean(r['fault_window'][key] for r in k)
        det = [r['detect_s'] for r in k if r.get('detect_s') is not None]
        out.append({'config': c, 'fault': f, 'trials': len(k), 'wrong_pct': round(fw('wrong_pct'), 1),
                    'correct_pct': round(fw('correct_pct'), 1), 'fallback_pct': round(fw('fallback_pct'), 1),
                    'degraded_pct': round(fw('degraded_pct'), 1), 'failed_pct': round(fw('failed_pct'), 1),
                    'detected_trials': f'{len(det)}/{len(k)}',
                    'median_detect_s': round(statistics.median(det), 2) if det else '',
                    'p95_ms': round(statistics.mean(r['fault_window']['p95_ms'] for r in k)),
                    'baseline_nonbase_pct': round(statistics.mean(100 - r['baseline']['correct_pct'] for r in k), 1)})
with open(os.path.join(ROOT, 'results', 'silentbench_summary.csv'), 'w', newline='') as fh:
    if out:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
print('| config | fault | n | wrong% | correct% | fallback% | degraded% | failed% | detected | median detect s | p95 ms |')
print('|---|---|---|---|---|---|---|---|---|---|---|')
for r in out:
    print('| {config} | {fault} | {trials} | {wrong_pct} | {correct_pct} | {fallback_pct} | {degraded_pct} | {failed_pct} | {detected_trials} | {median_detect_s} | {p95_ms} |'.format(**r))
