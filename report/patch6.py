import io
import json
R = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/'
bp = json.load(open(R + 'results/baselines_pareto.json'))
cf = json.load(open(R + 'results/compound_faults.json'))
hb = json.load(open(R + 'results/hbw_mttc.json'))
D, FA, OH = bp['detection_pct'], bp['false_alarm_pct'], bp['overhead_ms']
faults = list(D)
names = ['range', 'zscore3', 'golden', 'envelope', 'env+inv', 'full']


def ed(fn, f):
    a = io.open(R + fn, encoding='utf-8').read()
    a = f(a)
    io.open(R + fn, 'w', encoding='utf-8').write(a)


rows = ''.join(f"| {f} | " + ' | '.join(f"{D[f][n]}" for n in names) + ' |\n' for f in faults)
T = f'''
### 3.22 Baselines and cost-coverage (local, real service code; `analysis/baselines_pareto.py`, `results/baselines_pareto.json`, `results/figures/fig_baselines_detection.png`)
Detection (% of 40 random windows; golden is evaluated on its fixed test vector) of injected LSTM faults; false alarms on 300 healthy windows.
| fault | range | zscore3 | golden (LM-Fix-style) | envelope | env+inv | full |
|---|---|---|---|---|---|---|
{rows}| false alarms on healthy | {FA['range']} % | {FA['zscore3']} % | {FA['golden']} % | {FA['envelope']} % | {FA['env+inv']} % | {FA['full']} % |
Cost per call (ms): LSTM 6-step forecast {OH['lstm_forecast_6_steps']}; range {OH['range']}; zscore3 {OH['zscore3']}; envelope {OH['envelope']}; env+inv {OH['env+inv']}; golden test-vector forecast (24 steps) {OH['golden_test_vector_forecast_24']}; golden comparison {OH['golden_dev_check']}.
Findings (honest): (1) simple baselines are inadequate - the range check misses subtle bit flip, flat-line and stale output (0 %) and the 3-sd z-score flags {FA['zscore3']} % of healthy windows; (2) the golden/test-vector check alone detects every injected fault here with no false alarm, so on deterministic models it **subsumes** the other layers for detection - the earlier statement that layers are strictly complementary must be read as "for per-request checking"; (3) its cost is {OH['golden_test_vector_forecast_24']} ms per check versus {OH['env+inv']} ms for envelope+invariants, so it cannot be run per request, only periodically (every 5 s = about {round(OH['golden_test_vector_forecast_24'] / 5000 * 100, 1)} % of one core), whereas the cheap checks validate every served answer. The recommended design is therefore cheap per-request checks (bounding exposure between checks) plus a periodic golden check (bounding detection latency); this cost-coverage trade-off is the contribution, not the golden check itself.

### 3.23 Healthy-but-wrong time and mean time to correctness (`analysis/hbw_mttc.py`, `results/hbw_mttc.md`, `results/hbw_mttc.json`)
Definitions: HBW = seconds in the 30 s fault window during which the platform reports the pod Ready while wrong answers are served; MTTC = seconds from injection to the first non-wrong answer (censored at 30 s); MTTQ = seconds to full quality (operator trials, censored at 150 s). Results: guard off (C4): HBW 30 s and MTTC censored for every silent fault (the platform never leaves the healthy-but-wrong state); E4: HBW 0 s except subtle bit flip (30 s); G4/H4: HBW 0 s for all faults; operator MTTQ median: none never (0/20), rules {hb['operator|rules']['mttq_median_s']} s, bandit {hb['operator|bandit']['mttq_median_s']} s.

### 3.24 Compound faults (weights/scaler fault + output or delay fault; local, real service code; `analysis/compound_faults.py`, `results/compound_faults.json`)
25 requests per scenario after 3.5 s; oracle = deviation from the healthy forecast of the tier named in the response. Wrong answers: 0 % in all scenarios for E4, G4 and H4 except **bit flip + delay**: E4 serves 100 % wrong answers from the LSTM with p95 {cf['E4|bitflip+delay']['p95_ms']} ms; G4 serves 0 % wrong (SARIMA) but p95 {cf['G4|bitflip+delay']['p95_ms']} ms; H4 serves 0 % wrong with p95 {cf['H4|bitflip+delay']['p95_ms']} ms (climatology). Output-level compound faults (flat-line, stale, unit change with bit flip or scaler) and corrupt + delay were handled by all three configs (served from climatology). The interaction of a subtle silent fault with a slow-model fault is where all three mechanisms (golden check, tiers, deadline) are needed together.
'''
ed('TESTING_AND_KNOWN_ISSUES.md', lambda a: a + T)

V21 = '''
def v_novelty_studies():
    """Baselines, healthy-but-wrong metrics and compound-fault results (Phase 14b studies)."""
    b = json.load(open(os.path.join(ROOT, 'results', 'baselines_pareto.json')))
    assert b['detection_pct']['bitflip']['env+inv'] <= 10 and b['detection_pct']['bitflip']['golden'] == 100.0
    assert b['false_alarm_pct']['zscore3'] > 5 and b['false_alarm_pct']['env+inv'] <= 2
    c = json.load(open(os.path.join(ROOT, 'results', 'compound_faults.json')))
    assert c['E4|bitflip+delay']['wrong_pct'] == 100.0 and c['H4|bitflip+delay']['wrong_pct'] == 0.0
    h = json.load(open(os.path.join(ROOT, 'results', 'hbw_mttc.json')))
    assert h['C4|bitflip']['hbw_s_mean'] == 30.0 and h['G4|bitflip']['hbw_s_mean'] == 0.0
    return 'baselines: simple detectors weak or noisy, golden strong but costly; compound bitflip+delay: E4 100 % wrong, H4 0 %; HBW C4 30 s vs G4 0 s'

'''


def val(a):
    if 'v_novelty_studies' not in a:
        a = a.replace('\ndef main():', V21 + '\ndef main():', 1)
        a = a.replace("    check('V16 phases 7-13", "    check('V21 baselines, HBW/MTTC and compound faults', v_novelty_studies)\n    check('V16 phases 7-13", 1)
    return a


ed('validation/validate_all.py', val)

NOTE = f'''

## Five strongest contributions (final framing, 2026-10-17; each backed by measurements, none claimed as a new algorithm)
1. **SilentBench + healthy-but-wrong time / MTTC metrics** - measured silent-failure study across monolith, Compose and Kubernetes (TESTING 3.5b, 3.23). Default probes: HBW 30 s, 0 detections; guard: HBW 0 s.
2. **Compound silent + slow faults** - a subtle bit flip combined with a slow-model fault: E4 100 % wrong, G4 0 % wrong but slow (p95 {cf['G4|bitflip+delay']['p95_ms']} ms), H4 0 % wrong and bounded (p95 {cf['H4|bitflip+delay']['p95_ms']} ms) (TESTING 3.24). No compound-fault evaluation of ML-service health found in the reviewed papers.
3. **Cost-coverage evidence against baselines** - simple detectors (range, 3-sd z-score) miss or false-alarm; a golden/test-vector check detects everything but costs {OH['golden_test_vector_forecast_24']} ms per check vs {OH['env+inv']} ms for envelope+invariants, motivating cheap per-request checks plus a periodic golden check (TESTING 3.22).
4. **Correctness-aware probe design** - semantic readiness alone never restores; readiness + liveness restores in 36 s; partial vs strict readiness 0 % vs 81 % failed (TESTING 3.17).
5. **Quality-aware recovery and deadline-aware degradation** - cost-blind bandit 5/20 vs quality-aware 20/20 restored; delay fault 96.8 % to 0 % failed (TESTING 3.8, 3.20).
Not claimed as novel: golden-output check (LM-Fix, RADAR), conformal monitoring (WATCH and others), runtime SLO guard (arXiv 2607.09992), tiered fallback. The metamorphic probe is an experimental, partly negative result (TESTING 3.21).
'''
ed('NOVELTY_AND_PRIOR_ART.md', lambda a: a + NOTE)
ed('IMPLEMENTATION_PHASES.md', lambda a: a + '\n## 15. Five strongest contributions (2026-10-17)\nBaseline/cost-coverage study, healthy-but-wrong and MTTC metrics, compound-fault study done (TESTING 3.22-3.24); novelty reframed as five measured contributions (NOVELTY_AND_PRIOR_ART.md). Validation 21 checks.\n')
ed('PROJECT_HANDOFF.md', lambda a: a + '\n## 13. Addendum 2026-10-17 (five contributions)\nNew studies: TESTING 3.22 (baselines, cost-coverage), 3.23 (HBW/MTTC), 3.24 (compound faults). Note: golden/test-vector check alone detects all injected faults on a deterministic model (subsumes other layers for detection) but costs about 182 ms per check; the recommended design is cheap per-request checks plus periodic golden.\n')
ed('EXTRAS_AND_FUTURE_WORK.md', lambda a: a + '\n- X37 baselines and cost-coverage, X38 HBW/MTTC metrics, X39 compound faults: DONE (TESTING 3.22-3.24).\n')
print('docs patched')

# ---- report chapter 6
c6 = io.open(R + 'report/c6.py', encoding='utf-8').read()
tbl_rows = ',\n'.join(f" ['{f}', " + ', '.join(f"'{D[f][n]} %'" for n in names) + ']' for f in faults)
sec = f'''('h3', '6.7  Baselines and Cost-Coverage of the Guard Layers'),
('p', "To check that the guard is better than simple alternatives and to quantify what each layer costs, six detectors were compared on the same injected faults using the real service code: a range check (history minimum and maximum), a 3-sigma z-score against the calendar-month mean, a golden test-vector check in the style of LM-Fix, the conformal envelope alone, envelope with invariants, and the full guard (envelope, invariants and golden). Detection was measured on 40 random history windows and false alarms on 300 healthy windows."),
('table', ['Fault', 'range', 'z-score 3 sd', 'golden', 'envelope', 'env + inv', 'full'], [
{tbl_rows},
 ['false alarms (healthy)', '{FA['range']} %', '{FA['zscore3']} %', '{FA['golden']} %', '{FA['envelope']} %', '{FA['env+inv']} %', '{FA['full']} %'],
]),
('cap', 'Table 6.10  Detection of injected faults by simple baselines and by the layers of the guard (percent of windows)'),
('fig', 'fig_baselines_detection.png', 'Figure 6.17  Detection of injected faults: baselines versus guard layers', 6.0),
('p', "Three honest conclusions follow. First, simple detectors are inadequate: the range check never sees the subtle bit flip, the flat-line or the stale output, and the z-score check raises false alarms on {FA['zscore3']} percent of healthy windows. Second, the golden test-vector check on its own detected every injected fault with no false alarm, so on a deterministic model it subsumes the other layers for detection; the statement that the layers are complementary therefore holds for per-request checking only. Third, the cost differs by orders of magnitude: a golden check needs a 24-step forecast ({OH['golden_test_vector_forecast_24']} ms) whereas the envelope with invariants needs {OH['env+inv']} ms. The golden check can therefore be run only periodically (every five seconds it uses about {round(OH['golden_test_vector_forecast_24'] / 5000 * 100, 1)} percent of one core), while the cheap checks validate every served answer. The resulting design - cheap per-request checks that bound the exposure between golden checks, plus a periodic golden check that bounds the detection latency - is the cost-coverage contribution of the study."),

('h3', '6.8  Healthy-but-Wrong Time and Mean Time to Correctness'),
('p', "Two metrics are defined to describe what availability and restart-time metrics hide. Healthy-but-wrong (HBW) time is the number of seconds during a fault window in which the platform reports the pod Ready while wrong answers are served. Mean time to correctness (MTTC) is the time from injection to the first answer that is not wrong. In the SilentBench data the guard-off configuration (C4) has an HBW time of 30 s (the whole fault window) and an undefined MTTC for every silent fault, which means that the platform never leaves the healthy-but-wrong state; the full guard (G4, H4) has an HBW time of 0 s for every fault; the envelope and invariants (E4) have 0 s except for the subtle bit flip (30 s). Full quality (MTTQ) returns with the operator in {hb['operator|rules']['mttq_median_s']} s (rules) and {hb['operator|bandit']['mttq_median_s']} s (bandit) and never without it. The numbers are in results/hbw_mttc.md."),

('h3', '6.9  Compound Faults'),
('p', "Real incidents rarely come alone, so six combinations of a weight or scaler fault with an output-level or delay fault were injected into the real service code (25 requests per scenario; a response is wrong if it deviates from the healthy forecast of the tier it names). Output-level compound faults (flat-line, stale, unit change combined with a bit flip or scaler fault) and corrupt plus delay were handled by all three configurations by serving climatology. The interesting case is a subtle bit flip combined with a slow-model fault: E4 served 100 percent wrong answers from the LSTM with a p95 latency of {cf['E4|bitflip+delay']['p95_ms']} ms; G4 served no wrong answer (it fell back to SARIMA) but with a p95 latency of {cf['G4|bitflip+delay']['p95_ms']} ms; H4 served no wrong answer with a p95 latency of {cf['H4|bitflip+delay']['p95_ms']} ms. A subtle silent fault and a slow fault together need all three mechanisms - the golden check, the tier chain and the deadline - and neither of the two faults alone shows this interaction."),
('table', ['Scenario', 'E4 wrong %', 'G4 wrong %', 'H4 wrong %', 'E4 p95 (ms)', 'G4 p95 (ms)', 'H4 p95 (ms)'], [
 ''' + ',\n '.join(f"['{s}', '{cf['E4|' + s]['wrong_pct']}', '{cf['G4|' + s]['wrong_pct']}', '{cf['H4|' + s]['wrong_pct']}', '{cf['E4|' + s]['p95_ms']}', '{cf['G4|' + s]['p95_ms']}', '{cf['H4|' + s]['p95_ms']}']" for s in ['bitflip+flatline', 'bitflip+stale', 'scaler+unitchange', 'bitflip+delay', 'corrupt+delay', 'scaler+flatline']) + '''
]),
('cap', 'Table 6.11  Compound faults: wrong answers and p95 latency per configuration'),

'''
k = c6.index("('h3', '6.7  Overall Analysis'),")
c6 = c6[:k] + sec + c6[k:].replace("('h3', '6.7  Overall Analysis'),", "('h3', '6.10  Overall Analysis'),").replace("('h3', '6.8  Summary'),", "('h3', '6.11  Summary'),")
# layer-complementarity wording
c6 = c6.replace("The table shows that the layers are complementary rather than redundant: each added layer closes a class of faults that the previous layers cannot see.",
                "The table shows that, among the per-request checks, each added layer closes a class of faults that the previous layers cannot see. Section 6.7 qualifies this: the golden check alone detects every fault but is too expensive to run per request.")
io.open(R + 'report/c6.py', 'w', encoding='utf-8').write(c6)
b = io.open(R + 'report/build_report.py', encoding='utf-8').read()
b = b.replace("Project_Report_v2.docx", "Project_Report_v3.docx")
io.open(R + 'report/build_report.py', 'w', encoding='utf-8').write(b)
m = io.open(R + 'report/measure.py', encoding='utf-8').read()
m = m.replace("Project_Report_v2", "Project_Report_v3")
io.open(R + 'report/measure.py', 'w', encoding='utf-8').write(m)
print('report patched')
