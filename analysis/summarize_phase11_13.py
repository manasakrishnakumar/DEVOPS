"""Write Phase 11-13 results into the handoff documents."""
import collections
import io
import json
import os
import statistics

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
L = []


def rows(fn):
    p = R + fn
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


# ---- Phase 11
sg = rows('results/shadow_gate_cluster.jsonl')
if sg:
    g = collections.defaultdict(list)
    for r in sg:
        g[r['candidate']].append(r)
    L += ['### 3.12 Phase 11: in-cluster shadow-gate (image :8, config E4, mirrored 5 rps, gate: reject ratio <= 5 %, >= 20 samples)',
          '| Candidate | expected | trials | decisions | median reject ratio | median score | median s to decision |', '|---|---|---|---|---|---|---|']
    for name, v in g.items():
        dec = collections.Counter(r.get('decision') for r in v)
        tt = [r['time_to_decision_s'] for r in v if r.get('time_to_decision_s') is not None]
        L.append(f"| {name} | {v[0].get('expected')} | {len(v)} | {dict(dec)} | {statistics.median(r['reject_ratio'] for r in v):.2f} | "
                 f"{statistics.median(r['median_score'] for r in v if r.get('median_score') is not None):.2f} | "
                 f"{statistics.median(tt):.1f} |" if tt else f"| {name} | {v[0].get('expected')} | {len(v)} | {dict(dec)} | - | - | no decision |")
    bad = [r for r in sg if r.get('expected') == 'reject']
    good = [r for r in sg if r.get('expected') == 'promote']
    L += ['', f"Bad candidates caught (rejected): {sum(r.get('decision') == 'reject' for r in bad)}/{len(bad)}; "
              f"good candidates wrongly rejected: {sum(r.get('decision') == 'reject' for r in good)}/{len(good)}. "
              'Argo Rollouts, Kyverno, cosign and CI were NOT run (manifests only; see EXTRAS X06-X08).', '']
# ---- Phase 12
try:
    p12 = json.load(open(R + 'results/phase12.json'))
    ag, dr = p12.get('aging', {}), p12.get('drift', {})
    L += ['### 3.13 Phase 12 in the cluster: aging, drift, energy-aware serving, retraining',
          f"/aging: model_age_months={ag.get('model_age_months')}, retrain_after_months={ag.get('retrain_after_months')}, retrain_recommended={ag.get('retrain_recommended')}. "
          f"/drift: PSI={dr.get('psi')}, psi_alert={dr.get('psi_alert')}, ph_alert={dr.get('ph_alert')}.",
          '| ENERGY_AWARE | requests | est. J/request | CPU s/request | tier counts | p95 ms | correct % |', '|---|---|---|---|---|---|---|']
    for e in p12.get('energy', []):
        L.append(f"| {e['energy_aware']} | {e['requests']} | {e['joules_per_request']} | {e['cpu_s_per_request']} | {e['tier_counts']} | {e['p95_ms']} | {e['correct_pct']} |")
    L += ['', 'Hold-out RMSE 2019-2024 (one-step ahead): ' + json.dumps(p12.get('holdout_rmse_2019_2024')),
          'Joules are estimates (CPU-seconds x 15 W), not hardware counters.', '']
except Exception as e:  # noqa: BLE001
    L += [f'(Phase 12 results unavailable: {e})', '']
# ---- Phase 13
try:
    ac = json.load(open(R + 'results/phase13_adaptive_conformal.json'))
    L += ['### 3.14 Phase 13a: static vs rolling vs adaptive conformal guard (offline, hold-out windows from 2019, alpha 0.01, 6-month windows)',
          '| Strategy | false-alarm rate | ' + ' | '.join(ac['static']['detect']) + ' |', '|---|---|' + '---|' * len(ac['static']['detect'])]
    for k in ('static', 'rolling_20y', 'aci'):
        L.append(f"| {k} | {ac[k]['false_alarm']:.3f} | " + ' | '.join(f'{v:.2f}' for v in ac[k]['detect'].values()) + ' |')
    L.append('')
except Exception as e:  # noqa: BLE001
    L += [f'(Phase 13a results unavailable: {e})', '']
fam = rows('results/model_family.jsonl')
if fam:
    L += ['### 3.15 Phase 13b: model family under identical faults (guard off, image :8, 5 trials per cell)',
          '| Family | start-up s | model load s (sum) | RSS MB | fault | recovered | median recovery s | mean failed % |', '|---|---|---|---|---|---|---|---|']
    meta = {r['family']: r for r in fam if r.get('kind') == 'startup'}
    g = collections.defaultdict(list)
    for r in fam:
        if r.get('kind') == 'fault':
            g[(r['family'], r['fault'])].append(r)
    for (f, fault), v in g.items():
        rec = [r['recovery_s'] for r in v if r.get('recovery_s') is not None]
        m = meta.get(f, {})
        L.append(f"| {f} | {m.get('startup_s')} | {m.get('model_load_s_sum')} | {m.get('rss_mb')} | {fault} | {len(rec)}/{len(v)} | "
                 f"{statistics.median(rec):.1f} | " if rec else f"| {f} | {m.get('startup_s')} | {m.get('model_load_s_sum')} | {m.get('rss_mb')} | {fault} | 0/{len(v)} | never | ")
        L[-1] += f"{statistics.mean(r['failed_pct'] for r in v if r.get('failed_pct') is not None):.1f} |" if any(r.get('failed_pct') is not None for r in v) else '- |'
    L.append('')
L += ['Not run in Phases 11-13 (moved to extras): Argo Rollouts, Kyverno, cosign, GitHub Actions CI (X06-X08); KEDA warm-up-aware scaling (X10).', '']
block = '\n'.join(L) + '\n'

p = R + 'TESTING_AND_KNOWN_ISSUES.md'
a = io.open(p, encoding='utf-8').read()
i = a.find('### 3.12 Phase 11')
if i < 0:
    i = a.find('### 3.13 Phase 12')
if i >= 0:
    j = a.find('## 4. Known issues')
    a = a[:i] + a[j:]
a = a.replace('## 4. Known issues', block + '## 4. Known issues', 1)
io.open(p, 'w', encoding='utf-8').write(a)
p = R + 'IMPLEMENTATION_PHASES.md'
a = io.open(p, encoding='utf-8').read()
a = a.replace('| 11 | Delivery/security (N5) | shadow gate, Argo, Kyverno, CI | Partially implemented | shadow gate tested locally only |',
              '| 11 | Delivery/security (N5) | shadow gate, Argo, Kyverno, CI | **Shadow gate measured in cluster (TESTING 3.12); Argo/Kyverno/CI not run (extras)** | `analysis/shadow_gate_cluster.py` |')
a = a.replace('| 12 | Additions A1–A3 | aging, drift-retrain, energy | Implemented but not fully tested | local runs only |',
              '| 12 | Additions A1–A3 | aging, drift-retrain, energy | **Measured in cluster (TESTING 3.13)** | `analysis/phase12_cluster.py`, `results/phase12.json` |')
a = a.replace('| 13 | Secondary experiments | adaptive conformal, KEDA, SARIMA vs LSTM | Planned but not started | – |',
              '| 13 | Secondary experiments | adaptive conformal, KEDA, SARIMA vs LSTM | **Adaptive conformal + model family measured (TESTING 3.14, 3.15); KEDA not run (extras)** | `analysis/adaptive_conformal.py`, `chaos/run_family.py` |')
io.open(p, 'w', encoding='utf-8').write(a)
print('phase 11-13 documents updated')
