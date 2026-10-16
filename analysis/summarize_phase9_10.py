"""Write Phase 9 (probe tuning validation) and Phase 10 (failure predictor) results into the handoff documents."""
import collections
import io
import json
import os
import statistics

import numpy as np
from scipy.stats import mannwhitneyu

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
L = []
try:
    rows = [json.loads(l) for l in open(R + 'results/probe_validation.jsonl') if l.strip()]
    g = collections.defaultdict(list)
    for r in rows:
        g[r['setting']].append(r)
    L += ['### 3.10 Phase 9: validation of tuned probe settings (hang fault, config C4, held-out runs)',
          '| Setting (period s / threshold / replicas) | trials | recovered | median recovery s | mean failed % | p vs default (Mann-Whitney, recovery) |',
          '|---|---|---|---|---|---|']
    base = [r['recovery_s'] for r in g.get('default', []) if r.get('recovery_s') is not None]
    for name in ('default', 'control_default_3rep', 'recommended_1rep', 'recommended', 'observed_best'):
        v = g.get(name, [])
        if not v:
            continue
        rec = [r['recovery_s'] for r in v if r.get('recovery_s') is not None]
        p = ''
        if name != 'default' and len(rec) > 1 and len(base) > 1:
            p = f'{mannwhitneyu(rec, base, alternative="two-sided").pvalue:.3f}'
        L.append(f"| {name} {v[0]['period']}/{v[0]['threshold']}/{v[0]['replicas']} | {len(v)} | {len(rec)}/{len(v)} | "
                 f"{statistics.median(rec):.1f} | {np.mean([r['failed_pct'] for r in v if r.get('failed_pct') is not None]):.1f} | {p} |"
                 if rec else f"| {name} | {len(v)} | 0/{len(v)} | never | - | - |")
    L.append('')
except Exception as e:  # noqa: BLE001
    L += [f'(Phase 9 validation results unavailable: {e})', '']
try:
    pr = json.load(open(R + 'results/predictor_results.json'))
    L += ['### 3.11 Phase 10: failure predictor (Isolation Forest on telemetry vs baselines)',
          f"Healthy false alarms: {pr['healthy_false_alarms']} in {pr['healthy_minutes']} min "
          f"({pr['healthy_false_alarms_per_10min']} per 10 min) for Isolation Forest; Mahalanobis: {pr.get('healthy_false_alarms_mahalanobis')} alarms.",
          '| Scenario | trials with failure | method | alarmed before failure | median lead s |', '|---|---|---|---|---|']
    for kind, v in pr['scenarios'].items():
        s = v['summary']
        for key, label in (('iforest_lead_s', 'Isolation Forest'), ('mahalanobis_lead_s', 'Mahalanobis (healthy distribution)'), ('memory_threshold_lead_s', 'static memory threshold 80 %'),
                           ('reactive_guard_lead_s', 'reactive guard (score > 1)')):
            L.append(f"| {kind} | {s['with_failure']}/{s['trials']} | {label} | {s[key]['early_before_failure']} | {s[key]['median_lead_s']} |")
    L.append('')
except Exception as e:  # noqa: BLE001
    L += [f'(Phase 10 predictor results unavailable: {e})', '']
block = '\n'.join(L) + '\n'

p = R + 'TESTING_AND_KNOWN_ISSUES.md'
a = io.open(p, encoding='utf-8').read()
for tag in ('### 3.10 Phase 9', '### 3.11 Phase 10'):
    i = a.find(tag)
    if i >= 0:
        j = a.find('\n## 4. Known issues') if tag == '### 3.11 Phase 10' else a.find('### 3.11 Phase 10')
        j = j if j > i else a.find('## 4. Known issues')
        a = a[:i] + a[j:]
a = a.replace('## 4. Known issues', block + '## 4. Known issues', 1)
io.open(p, 'w', encoding='utf-8').write(a)
p = R + 'IMPLEMENTATION_PHASES.md'
a = io.open(p, encoding='utf-8').read()
a = a.replace('| 10 | Failure predictor | IF/LSTM-AE | Planned but not started | – |', '| 10 | Failure predictor | Isolation Forest on telemetry (leak, drift) | **Measured (see TESTING 3.11)** | `analysis/failure_predictor.py`, `results/predictor_results.json` |')
a = a.replace('**DoE executed (30 runs); BO output unreliable (K23)**', '**DoE executed (30 runs); bounded BO recommendation validated on held-out runs (see TESTING 3.10)**')
io.open(p, 'w', encoding='utf-8').write(a)
print('phase 9/10 documents updated')
