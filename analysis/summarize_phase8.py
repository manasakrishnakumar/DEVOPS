"""Summarise Phase 8 (operator experiments + re-run twin) into the handoff documents."""
import collections
import io
import json
import os
import statistics

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
rows = [json.loads(l) for l in open(R + 'results/operator_trials.jsonl') if l.strip()]
g = collections.defaultdict(list)
for r in rows:
    g[(r['policy'], r['fault'])].append(r)
order = {'none': 0, 'rules': 1, 'bandit': 2}
L = ['### 3.8 Phase 8: operator experiments (config E4, image :6, no heal, 150 s window, 5 rps)',
     'restored_s = seconds from fault injection until 5 consecutive correct full-quality (LSTM-tier) answers.',
     '| Policy | Fault | trials | restored | median restored s | correct % | degraded % | wrong % | failed % |', '|---|---|---|---|---|---|---|---|---|']
for (pol, f), v in sorted(g.items(), key=lambda kv: (order.get(kv[0][0], 9), kv[0][1])):
    rs = [r['restored_s'] for r in v if r.get('restored_s') is not None]
    mean = lambda k: statistics.mean(r['fault_window'][k + '_pct'] for r in v)
    L.append(f"| {pol} | {f} | {len(v)} | {len(rs)}/{len(v)} | {statistics.median(rs):.1f} | {mean('correct'):.1f} | "
             f"{mean('degraded'):.1f} | {mean('wrong'):.1f} | {mean('failed'):.1f} |" if rs else
             f"| {pol} | {f} | {len(v)} | 0/{len(v)} | never | {mean('correct'):.1f} | {mean('degraded'):.1f} | {mean('wrong'):.1f} | {mean('failed'):.1f} |")
L.append('')
try:
    ev = json.load(open(R + 'analysis/bandit_eval.json'))
    pol = json.load(open(R + 'analysis/policy.json'))
    L += ['### 3.9 Twin + bandit re-run with the third action `switch_then_restart` (`analysis/bandit_eval.json`, `analysis/policy.json`)',
          f"Average cost per episode: {ev.get('avg_cost_per_episode')}; best action per fault: {ev.get('best_action_per_fault')}.",
          'Policy table (expected cost per action): ' + json.dumps({k: {a: round(c, 1) for a, c in v.items()} for k, v in pol.items()}), '']
except Exception as e:  # noqa: BLE001
    L += [f'(twin re-run output unavailable: {e})', '']
block = '\n'.join(L) + '\n'

p = R + 'TESTING_AND_KNOWN_ISSUES.md'
a = io.open(p, encoding='utf-8').read()
i = a.find('### 3.8 Phase 8')
if i >= 0:
    j = a.find('## 4. Known issues')
    a = a[:i] + a[j:]
a = a.replace('## 4. Known issues', block + '## 4. Known issues', 1)
a = a.replace('| T19 | Operator experiments (none / rules / bandit) | `chaos/run_operator.py` | **NOT RUN** (stopped at user deadline 2026-10-16) |',
              '| T19 | Operator experiments (none / rules / bandit) | `chaos/run_operator.py --trials 5` | **Executed** - see 3.8 |')
io.open(p, 'w', encoding='utf-8').write(a)

p = R + 'IMPLEMENTATION_PHASES.md'
a = io.open(p, encoding='utf-8').read()
a = a.replace('**Implemented and deployed; experiments NOT RUN (stopped at user deadline)**', '**Measured (see TESTING 3.8, 3.9)**')
io.open(p, 'w', encoding='utf-8').write(a)
p = R + 'PROJECT_HANDOFF.md'
a = io.open(p, encoding='utf-8').read()
a = a.replace('**STOPPED AT USER DEADLINE (2026-10-16 ~10:15).**', '**UPDATE: Phase 8 operator experiments were run afterwards (see TESTING 3.8/3.9). Earlier note (superseded): STOPPED AT USER DEADLINE (2026-10-16 ~10:15).**')
io.open(p, 'w', encoding='utf-8').write(a)
print('phase 8 documents updated;', len(rows), 'operator rows')
