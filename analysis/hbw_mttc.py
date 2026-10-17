"""Novelty study N2: healthy-but-wrong time (HBW) and mean time to correctness (MTTC) from the SilentBench data.
HBW   = seconds in the 30 s fault window during which the platform reports the pod Ready (always, in these runs) while wrong answers are served
MTTC  = seconds from injection until the first answer that is not wrong (censored at the 30 s window when never)
MTTQ  = seconds from injection until FULL quality returns (operator trials; censored at 150 s)
Writes results/hbw_mttc.json and results/hbw_mttc.md.   python -X utf8 analysis/hbw_mttc.py
"""
import json
import os
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'silentbench.jsonl')) if l.strip()]
g = defaultdict(list)
for r in rows:
    if r['fault'] in ('none', 'delay'):
        continue
    g[(r['config'], r['fault'])].append(r)
out, md = {}, ['| fault | config | trials | HBW (s) mean | MTTC (s) median | wrong (%) mean |', '|---|---|---|---|---|---|']
for (cfg, f), v in sorted(g.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    hbw = [x['fault_window']['wrong_pct'] / 100 * 30 for x in v]
    mttc = [(x['detect_s'] if (x.get('detect_s') is not None and x['fault_window']['wrong_pct'] < 100) else 30.0) for x in v]
    mttc = [min(m, 30.0) if m >= 0 else 0.0 for m in mttc]
    wr = [x['fault_window']['wrong_pct'] for x in v]
    out[f'{cfg}|{f}'] = {'trials': len(v), 'hbw_s_mean': round(float(np.mean(hbw)), 2), 'mttc_s_median': round(float(np.median(mttc)), 2), 'wrong_pct_mean': round(float(np.mean(wr)), 1)}
    md.append(f"| {f} | {cfg} | {len(v)} | {np.mean(hbw):.1f} | {np.median(mttc):.1f}{' (censored)' if np.median(mttc) >= 30 else ''} | {np.mean(wr):.1f} |")
op = [json.loads(l) for l in open(os.path.join(ROOT, 'results', 'operator_trials.jsonl')) if l.strip()]
md += ['', '| operator policy | trials | restored | MTTQ median (s) (censored at 150) |', '|---|---|---|---|']
for p in ('none', 'rules', 'bandit'):
    v = [r.get('restored_s') for r in op if r['policy'] == p]
    c = [150.0 if x is None else x for x in v]
    out[f'operator|{p}'] = {'trials': len(v), 'restored': sum(x is not None for x in v), 'mttq_median_s': round(float(np.median(c)), 1)}
    md.append(f"| {p} | {len(v)} | {sum(x is not None for x in v)} | {np.median(c):.1f} |")
json.dump(out, open(os.path.join(ROOT, 'results', 'hbw_mttc.json'), 'w'), indent=1)
open(os.path.join(ROOT, 'results', 'hbw_mttc.md'), 'w').write('\n'.join(md) + '\n')
print('\n'.join(md[:12]))
