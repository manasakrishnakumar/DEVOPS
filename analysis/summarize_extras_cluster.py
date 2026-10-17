"""Write the cluster extras (e1-e8, scaling, Chronos) into the handoff documents."""
import collections
import io
import json
import os
import statistics

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep


def rows(fn):
    p = R + fn
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def mean(v):
    v = [x for x in v if x is not None]
    return round(statistics.mean(v), 1) if v else '-'


def med(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 1) if v else 'never'


ex = rows('results/extras_cluster.jsonl')
by = collections.defaultdict(list)
for r in ex:
    by[r.get('exp')].append(r)
L = ['### 3.17 Extras in the cluster (image :9 / frontend :3; `results/extras_cluster.jsonl`)']
errs = [r for r in ex if 'error' in r]
if errs:
    L.append('Errors: ' + '; '.join(f"{r['exp']}: {r['error'][:120]}" for r in errs))
v = by.get('e1_semantic_probes', [])
if v:
    L += ['**X13 semantic probes wired into Kubernetes (no heal, 140 s):**', '| Probe variant | Fault | trials | restored | median restored s | correct % | degraded % | failed % |', '|---|---|---|---|---|---|---|---|']
    g = collections.defaultdict(list)
    for r in v:
        g[(r['variant'], r['fault'])].append(r)
    for (var, f), x in g.items():
        rs = [r['restored_s'] for r in x]
        fw = lambda k: mean([r['fault_window'][k] for r in x if r.get('fault_window')])
        L.append(f"| {var} | {f} | {len(x)} | {sum(r is not None for r in rs)}/{len(x)} | {med(rs)} | {fw('correct_pct')} | {fw('degraded_pct')} | {fw('failed_pct')} |")
    L.append('')
v = by.get('e2_partial_readiness', [])
if v:
    L += ['**X14 partial readiness (LSTM model for one variable lost, 60 s):**', '| Readiness | trials | correct % | fallback % | degraded % | failed % |', '|---|---|---|---|---|---|']
    g = collections.defaultdict(list)
    for r in v:
        g[r['variant']].append(r)
    for k, x in g.items():
        fw = lambda key: mean([r['fault_window'][key] for r in x if r.get('fault_window')])
        L.append(f"| {k} | {len(x)} | {fw('correct_pct')} | {fw('fallback_pct')} | {fw('degraded_pct')} | {fw('failed_pct')} |")
    L.append('')
v = by.get('e3_cache_tier', [])
if v:
    fw = lambda key: mean([r['fault_window'][key] for r in v if r.get('fault_window')])
    L += [f"**X15 cache tier (climatology disabled, all models faulty), {len(v)} trials:** degraded (cache) {fw('degraded_pct')} %, wrong {fw('wrong_pct')} %, failed {fw('failed_pct')} %, correct {fw('correct_pct')} %.", '']
v = by.get('e4_load_mode', [])
if v:
    L += ['**X31 eager vs lazy LSTM loading (3 restarts each):**', '| Mode | median time to ready s | median first LSTM request s | median second request s |', '|---|---|---|---|']
    for m in ('eager', 'lazy'):
        x = [r for r in v if r['mode'] == m]
        L.append(f"| {m} | {med([r['time_to_ready_s'] for r in x])} | {med([r['first_lstm_request_s'] for r in x])} | {med([r['second_lstm_request_s'] for r in x])} |")
    L.append('')
v = by.get('e5_mttr_decomposition', [])
if v:
    L += ['**X12 MTTR decomposition (crash, 5 trials, medians):** ' + ', '.join(
        f'{k}={med([r.get(k) for r in v])}' for k in ('client_detect_s', 'container_restart_delay_s', 'ready_delay_after_start_s', 'app_startup_s', 'client_recovery_s')), '']
v = by.get('e6_db_faults', [])
if v:
    L += ['**X30 database faults seen from the web app (/history polled every 0.5 s):**', '| Fault | trials | median failed % | median outage s | median recovered s |', '|---|---|---|---|---|']
    g = collections.defaultdict(list)
    for r in v:
        g[r['fault']].append(r)
    for k, x in g.items():
        L.append(f"| {k} | {len(x)} | {med([r['failed_pct'] for r in x])} | {med([r['outage_s'] for r in x])} | {med([r['recovered_s'] for r in x])} |")
    L.append('')
v = by.get('e7_hop_timing', [])
if v:
    L += ['**X09 per-hop latency attribution (hop timing via histograms, not OpenTelemetry):**', '| Scenario | page requests | avg request s | avg inference call s | avg DB s | other (rendering) s |', '|---|---|---|---|---|---|']
    for r in v:
        L.append(f"| {r['scenario']} | {r['page_requests']} | {r['avg_request_s']} | {r['avg_inference_call_s_per_request']} | {r['avg_db_s_per_request']} | {r['other_rendering_s']} |")
    L.append('')
v = by.get('e8_ui', [])
if v:
    L += ['**X22 / X19 web UI checks:** ' + '; '.join(f"{r['check']}={r['value']}" for r in v), '']
sc = rows('results/extras_scaling.jsonl')
if sc:
    L += ['**X10 bursty load (4 rps -> 24 rps for 70 s -> 4 rps; SARIMA endpoint; guard off):**', '| Mode | trials | burst p95 ms (median) | burst failed % (median) | tail p95 ms | ready replicas at end |', '|---|---|---|---|---|---|']
    g = collections.defaultdict(list)
    for r in sc:
        g[r['mode']].append(r)
    for k, x in g.items():
        L.append(f"| {k} | {len(x)} | {med([r['burst']['p95_ms'] for r in x if 'burst' in r])} | {med([r['burst']['failed_pct'] for r in x if 'burst' in r])} | {med([r['tail']['p95_ms'] for r in x if 'tail' in r])} | {[r.get('ready_replicas_at_end') for r in x]} |")
    L += ['Proactive pre-scaling here uses a known schedule as the "forecast" (not a learned forecaster); KEDA was not used.', '']
ch = os.path.join(R, 'results', 'extras_chronos.json')
if os.path.exists(ch):
    c = json.load(open(ch))
    L += ['**X17 foundation model (Chronos-T5-tiny, zero-shot):** ' + (json.dumps({k: c[k] for k in ('rmse_Jan_Jun_2024', 'error_correlation_per_variable', 'vote_lstm_disagreement') if k in c}) if c.get('status') == 'ok' else c.get('status', '')), '']
L += ['Not attempted: X06 Argo Rollouts (needs controller install and a candidate-bearing image per revision), X07/X08 (registry, Actions), X26, X28, X29 (see EXTRAS_AND_FUTURE_WORK.md).', '']
block = '\n'.join(L) + '\n'
p = R + 'TESTING_AND_KNOWN_ISSUES.md'
a = io.open(p, encoding='utf-8').read()
i = a.find('### 3.17 Extras in the cluster')
if i >= 0:
    j = a.find('## 4. Known issues')
    a = a[:i] + a[j:]
a = a.replace('## 4. Known issues', block + '## 4. Known issues', 1)
io.open(p, 'w', encoding='utf-8').write(a)
p = R + 'EXTRAS_AND_FUTURE_WORK.md'
a = io.open(p, encoding='utf-8').read()
st = {'| X09 ': 'DONE as hop timing (not OpenTelemetry), TESTING 3.17', '| X10 ': 'DONE light (schedule-based pre-scaling vs HPA), 3.17', '| X12 ': 'DONE (3.17)',
      '| X13 ': 'DONE (3.17)', '| X14 ': 'DONE (3.17)', '| X15 ': 'DONE (3.17)', '| X17 ': 'ATTEMPTED (3.17)', '| X24 ': 'DONE as template summariser, results/incident_reports.md',
      '| X30 ': 'DONE (database lock and restart; node failure not possible on single node)', '| X31 ': 'DONE (eager vs lazy; other strategies not run)', '| X34 ': 'DONE (release/silentbench_release.zip)',
      '| X06 ': 'NOT RUN', '| X07 ': 'BLOCKED', '| X08 ': 'BLOCKED', '| X26 ': 'SKIPPED', '| X28 ': 'SKIPPED', '| X29 ': 'SKIPPED', '| X35 ': 'DONE (repository pushed with Git LFS)'}
lines = a.splitlines()
for k, line in enumerate(lines):
    for key, val in st.items():
        if line.startswith(key) and 'EXTRA STATUS' not in line:
            lines[k] = line + ' **[EXTRA STATUS: ' + val + ']**'
io.open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('cluster extras documented;', len(ex), 'rows')
