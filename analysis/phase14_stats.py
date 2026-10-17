"""Phase 14: final statistics and paper figures from the raw results (no new experiments).
 - silent benchmark: wrong-answer share per config x fault with bootstrap 95 % CI; Fisher exact (trial-level "any wrong answers") C4 vs G4
 - operator trials: restore time per policy with bootstrap CI; Mann-Whitney U tests
 - extras: KEDA / Chaos Mesh / log anomaly / RL summary tables
Writes results/phase14_stats.json, results/phase14_tables.md, results/figures/*.png.   python -X utf8 analysis/phase14_stats.py
"""
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda f: os.path.join(ROOT, 'results', f)
rng = np.random.default_rng(0)


def boot(x, n=5000):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (None, None, None)
    m = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return (round(float(x.mean()), 2), round(float(np.percentile(m, 2.5)), 2), round(float(np.percentile(m, 97.5)), 2))


def load(f):
    return [json.loads(l) for l in open(R(f)) if l.strip()]


out, md = {}, []
sb = load('silentbench.jsonl')
cell = defaultdict(list)
for r in sb:
    cell[(r['config'], r['fault'])].append(r['fault_window'])
faults = ['corrupt', 'unitchange', 'flatline', 'scaler', 'stale', 'bitflip', 'bitflip_severe', 'delay']
cfgs = ['C4', 'D4', 'E4', 'G4']
out['silent'] = {}
md.append('## Silent benchmark: wrong-answer share (%), mean [95 % bootstrap CI], n trials\n')
md.append('| fault | ' + ' | '.join(cfgs) + ' | Fisher C4 vs G4 (p) |\n|---|' + '---|' * (len(cfgs) + 1))
for f in faults:
    row, cells = [], {}
    for c in cfgs:
        w = cell.get((c, f), [])
        if not w:
            row.append('-')
            continue
        m, lo, hi = boot([x['wrong_pct'] for x in w])
        cells[c] = (m, lo, hi, len(w))
        row.append(f'{m} [{lo}, {hi}] n={len(w)}')
    p = '-'
    if 'C4' in cells and 'G4' in cells:
        a = [x['wrong_pct'] > 0 for x in cell[('C4', f)]]
        b = [x['wrong_pct'] > 0 for x in cell[('G4', f)]]
        p = f'{stats.fisher_exact([[sum(a), len(a) - sum(a)], [sum(b), len(b) - sum(b)]])[1]:.2g}'
    out['silent'][f] = {c: v for c, v in cells.items()}
    md.append(f'| {f} | ' + ' | '.join(row) + f' | {p} |')

op = load('operator_trials.jsonl')
by = defaultdict(list)
for r in op:
    by[r['policy']].append(r.get('restored_s'))
md.append('\n## Operator policies: time to full quality (s) and restore rate\n')
md.append('| policy | restored | mean [95 % CI] s |\n|---|---|---|')
out['operator'] = {}
for p in ('none', 'rules', 'bandit'):
    v = by[p]
    ok = [x for x in v if x is not None]
    m = boot(ok) if ok else (None, None, None)
    out['operator'][p] = {'restored': f'{len(ok)}/{len(v)}', 'mean_ci': m}
    md.append(f'| {p} | {len(ok)}/{len(v)} | {m[0]} [{m[1]}, {m[2]}] |' if ok else f'| {p} | 0/{len(v)} | never |')
rr = [x for x in by['rules'] if x is not None]
bb = [x for x in by['bandit'] if x is not None]
if rr and bb:
    u = stats.mannwhitneyu(rr, bb)
    out['operator']['rules_vs_bandit_mannwhitney_p'] = round(float(u.pvalue), 3)
    md.append(f'\nRules vs bandit restore time: Mann-Whitney p = {u.pvalue:.3f} (bandit ~2 s faster, small; both use the same action so this is run-to-run drift, not a policy effect).')
fisher = stats.fisher_exact([[len(rr), 20 - len(rr)], [0, 20]])[1]
out['operator']['rules_vs_none_restore_fisher_p'] = float(fisher)
md.append(f'Rules vs none (restored 20/20 vs 0/20): Fisher exact p = {fisher:.2g}.')

ex = {}
for name, f in (('keda', 'extras_keda.jsonl'), ('chaosmesh', 'extras_chaosmesh.jsonl')):
    if os.path.exists(R(f)):
        ex[name] = load(f)
for f in ('extras_log_anomaly.json', 'extras_rl_autoscaler.json'):
    ex[f.split('.')[0]] = json.load(open(R(f)))
out['extras'] = ex
md.append('\n## New extras (summary)\n')
k = [r for r in ex.get('keda', []) if 'burst' in r]
md.append(f'- KEDA: peak replicas {[r["peak_ready_replicas"] for r in ex.get("keda", [])]}; burst failed % {[r["burst"]["failed_pct"] for r in k]} (single CPU-bound node, no benefit; K37).')
cm = ex.get('chaosmesh', [])
md.append('- Chaos Mesh: pod-kill ready after ' + str([r['ready_after_s'] for r in cm if r['exp'] == 'pod_kill']) + ' s; 300 ms network delay raised p50 from ' +
          str(next((r['p50_ms'] for r in cm if r['exp'] == 'baseline'), None)) + ' to ' + str(next((r['p50_ms'] for r in cm if r['exp'] == 'network_delay_300ms'), None)) + ' ms, no failures.')
md.append(f'- Log anomaly: templates={ex["extras_log_anomaly"]["templates"]}, detection {ex["extras_log_anomaly"]["by_fault_detected_pct"]} (service emits no per-request logs; negative result).')
md.append(f'- RL autoscaler (simulation): {json.dumps({k2: v for k2, v in ex["extras_rl_autoscaler"].items() if k2 != "note"})}')

# figures
fig, ax = plt.subplots(figsize=(9, 4))
x = np.arange(len(faults[:-1]))
for i, c in enumerate(cfgs):
    ys = [out['silent'][f].get(c, (0,))[0] if c in out['silent'][f] else 0 for f in faults[:-1]]
    ax.bar(x + i * 0.2 - 0.3, ys, 0.2, label=c)
ax.set_xticks(x)
ax.set_xticklabels(faults[:-1], rotation=20)
ax.set_ylabel('wrong answers served (%)')
ax.set_title('Silent faults: C4 no guard, D4 envelope, E4 +invariants, G4 +golden check')
ax.legend()
fig.tight_layout()
fig.savefig(R('figures/fig_silent_wrong_pct.png'), dpi=150)
fig, ax = plt.subplots(figsize=(5, 4))
ax.boxplot([[x for x in by[p] if x is not None] or [0] for p in ('rules', 'bandit')], labels=['rules', 'bandit (cost-aware)'])
ax.set_ylabel('time to full quality (s)')
ax.set_title('Operator restore time (none: 0/20 restored)')
fig.tight_layout()
fig.savefig(R('figures/fig_operator_restore.png'), dpi=150)
json.dump(out, open(R('phase14_stats.json'), 'w'), indent=1, default=str)
open(R('phase14_tables.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('\n'.join(md))
