import io
import json
R = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/'


def ed(fn, f):
    a = io.open(R + fn, encoding='utf-8').read()
    a = f(a)
    io.open(R + fn, 'w', encoding='utf-8').write(a)


ev = json.load(open(R + 'results/metamorphic_eval.json'))
F = ev['faults']
T = f'''
### 3.21 Metamorphic readiness probe (experimental, opt-in; image :13; `inference-api/metamorphic.py`, `analysis/calibrate_metamorphic.py`, `results/metamorphic_eval.json`)
Idea: check the LSTM with *related inputs* instead of a stored reference output. MR1 (sensitivity profile): the 6-step response of the forecast to a +1 sd shift of the input window must stay inside a band learned offline on the healthy model (the LSTM mean-reverts, so the response is not 1 - the first assumed relation f(x+c)~f(x)+c was falsified by the data and replaced). MR2 (recursive self-consistency): f(x,k)[1:] = f(x+f(x,k)[0],k-1). Tolerances are conformal quantiles (alpha 0.01, family-wise over 3 probe windows) calibrated on {ev['windows']} historical windows; no golden output or start-up reference is used. Off by default (`METAMORPHIC=1` to enable; read-only; runs every `METAMORPHIC_EVERY` canary rounds under the run lock).
- False alarms: interleaved split (calibrate on even windows of all years, test odd) {ev['false_alarm_interleaved_triple_pct']} % per probe (triple of windows), {ev['false_alarm_interleaved_single_pct']} % per window; **time split (calibrate <= 2018, test > 2018) {ev['false_alarm_timesplit_triple_pct']} % per probe** - the band does not survive the post-2018 drift, so it needs periodic re-calibration.
- Detection over 30 random probe-window triples: corrupt {F['corrupt']['detected_pct']} %, unit change {F['unitchange']['detected_pct']} %, flat-line {F['flatline']['detected_pct']} %, stale {F['stale']['detected_pct']} % (scores 100-1e9 x threshold, via MR2/MR1); subtle bit flip (8 flips) {F['bitflip']['detected_pct']} % and 16 flips {F['bitflip_severe']['detected_pct']} % but with scores only about 1.1 x threshold (marginal); scaler fault {F['scaler']['detected_pct']} %.
- Cluster test (image :13, golden off, probe on): healthy probe score already 0.996-1.0 (at the threshold because the deployed probe windows are the latest, most drifted ones) and the injected bit flip scored 0.996 (missed); one violation counter increment occurred on healthy data. **Conclusion: the probe is reliable for output-level and gross faults (which the envelope, invariants and canary already catch) but NOT for subtle weight corruption; the golden-output check remains necessary. Not recommended to enable without re-calibration; reported as an experimental, partly negative result (K42).** Final cluster state: probe off, golden check on, deadline 800 ms.
'''
ed('TESTING_AND_KNOWN_ISSUES.md', lambda a: a + T)
ed('TESTING_AND_KNOWN_ISSUES.md', lambda a: a.replace('| K12 |', '| K42 | Metamorphic probe marginal for subtle weight faults and brittle under drift (time-split false alarms 66 %, deployed healthy score ~1.0) | results/metamorphic_eval.json, 3.21 | LSTM mean-reverts so no clean equivariance; band calibrated before the 2018 humidity/temperature drift | open: re-calibration schedule or a larger probe set; do not claim bit-flip detection from it |\n| K12 |', 1))

PRIOR = '''# Novelty, gaps and prior art (checked 2026-10-17)

Method: full-text keyword scan of the 23 reading-list papers plus web searches (standard mode). Only these sources were checked; a structured IEEE Xplore / Google Scholar search is still required before the word "first" is used in a paper.

## Not novel as techniques (cite)
| Technique | Existing work found |
|---|---|
| Golden-output / bit-flip detection | LM-Fix (arXiv 2511.02866), RADAR (DATE 2021), TrustSeed (DATE 2026) |
| Conformal runtime monitoring of AI services | WATCH (arXiv 2505.04608), Cloud-native Evaluation-as-a-Service with conformal guarantees (arXiv 2607.21623), predictive monitoring with conformal guarantees (arXiv 2312.01959), A22 (online conformal) |
| Runtime SLO guard for ML serving | Trusted Floors Under Untrusted Learners (arXiv 2607.09992) |
| Self-healing ML framework; production inference incident study | arXiv 2411.00186; arXiv 2511.07424 |
| Tiered fallback / deadline budgets | edge failover paper (Illinois experts 2023) and practitioner write-ups |
| Learned recovery policy / digital twin | A1, A8 |

## Gaps in the other papers that this project fills (gap-based novelty)
| # | Gap in the literature | What this project did | Evidence |
|---|---|---|---|
| 1 | Resilience/chaos studies inject infrastructure faults only | SilentBench: 8 silent faults across monolith, Compose, Kubernetes | default probes 100 % wrong, 0 detections (10 trials per cell) |
| 2 | Anomaly detectors watch metrics/logs/traces, which are normal in silent failures | health defined on the model output; log detector measured as blind | 0 templates, 0/6 faults from logs |
| 3 | SLOs cover latency/availability, not answer correctness | correctness SLO (Wilson bound, burn rates) | alert 9-15 s after value corruption |
| 4 | Probe guides test "can serve", not "serves correct answers"; trade-off unmeasured | semantic readiness / liveness / partial readiness measured | readiness alone 92 % failed never restored; +liveness 36 s; partial 0 % vs strict 81 % failed |
| 5 | Recovery work optimises infrastructure, not answer quality | operator + quality-aware cost model | 20/20 restored in ~22-24 s vs never; cost-blind bandit 5/20 |
| 6 | Delivery pipelines evaluate models offline | shadow gate on output validity + Argo canary | 15/15 bad rejected, 6/6 good promoted |
| 7 | Degradation/deadlines described in blogs, not measured on real faults | deadline- and load-aware tiers | delay fault 96.8 % -> 0 % failed |

## Honest verdict
The contribution is empirical and systems-level (measured study + integrated Kubernetes-native defence), not a new algorithm. Strongest gaps: 1, 2, 4. Weaker (close prior work): 3, 6, 7. The metamorphic probe (TESTING 3.21) is an experimental, partly negative result.
'''
io.open(R + 'NOVELTY_AND_PRIOR_ART.md', 'w', encoding='utf-8').write(PRIOR)
ed('README.md', lambda a: a.replace('| `SECURITY_REVIEW.md` |', '| `NOVELTY_AND_PRIOR_ART.md` | gap-based novelty, prior art found, honest verdict |\n| `SECURITY_REVIEW.md` |', 1))
ed('EXTRAS_AND_FUTURE_WORK.md', lambda a: a + '\n- Metamorphic readiness probe (X36): DONE as experimental, partly negative result - reliable for output-level faults, marginal for subtle bit flips, brittle under drift (TESTING 3.21, K42).\n')
ed('IMPLEMENTATION_PHASES.md', lambda a: a + '\n## 14. Metamorphic probe and prior-art check (2026-10-17)\nMetamorphic readiness probe built, calibrated and tested (TESTING 3.21; experimental, partly negative). Prior-art search done; novelty reframed as gap-based and empirical (NOVELTY_AND_PRIOR_ART.md).\n')
ed('PROJECT_HANDOFF.md', lambda a: a + '\n## 12. Addendum 2026-10-17 (metamorphic probe, prior art)\nImage :13 adds the opt-in metamorphic probe (METAMORPHIC=1, off by default); final cluster state: probe off, golden on, deadline 800 ms. Prior-art search shows golden-output, conformal monitoring, runtime SLO guards and tiered fallback exist in the literature; novelty is empirical/systems-level (see NOVELTY_AND_PRIOR_ART.md). Read arXiv 2607.09992 (Trusted Floors) before writing.\n')
ed('REFERENCES_AND_LITERATURE_REVIEW.md', lambda a: a + '\n## 8. ADDENDUM (2026-10-17): prior art found by web search (authors not captured; verify before citing)\nLM-Fix arXiv 2511.02866; WATCH arXiv 2505.04608; Cloud-Native Evaluation-as-a-Service arXiv 2607.21623; Trusted Floors Under Untrusted Learners arXiv 2607.09992; Self-Healing Machine Learning arXiv 2411.00186; Enhancing reliability in AI inference services (production incidents) arXiv 2511.07424; RADAR (DATE 2021); TrustSeed (DATE 2026). See NOVELTY_AND_PRIOR_ART.md.\n')


def val(a):
    fn = '''
def v_metamorphic_data():
    """Metamorphic probe evaluation file exists; output-level faults detected, interleaved false alarms low; limits recorded."""
    d = json.load(open(os.path.join(ROOT, 'results', 'metamorphic_eval.json')))
    for f in ('corrupt', 'unitchange', 'flatline', 'stale'):
        assert d['faults'][f]['detected_pct'] == 100.0, f
    assert d['false_alarm_interleaved_triple_pct'] <= 5.0 and d['deployed_probe_windows_healthy_after_heal_false_alarm_pct'] == 0.0
    return f"interleaved FA {d['false_alarm_interleaved_triple_pct']} %, time-split FA {d['false_alarm_timesplit_triple_pct']} % (limit), bitflip {d['faults']['bitflip']['detected_pct']} % marginal, scaler {d['faults']['scaler']['detected_pct']} %"

'''
    if 'v_metamorphic_data' not in a:
        a = a.replace('\ndef main():', fn + '\ndef main():', 1)
        a = a.replace("    check('V16 phases 7-13", "    check('V20 metamorphic probe evaluation (experimental)', v_metamorphic_data)\n    check('V16 phases 7-13", 1)
    return a


ed('validation/validate_all.py', val)
print('docs patched')
