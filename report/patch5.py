import io
import json
R = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/report/'
ev = json.load(open(R + '../results/metamorphic_eval.json'))
F = ev['faults']

# ---- chapter 2.3: gap-based positioning with real prior art
c2 = io.open(R + 'c2.py', encoding='utf-8').read()
i = c2.index("('p', \"A full-text keyword scan of the reading list gave")
j = c2.index("('h3', '2.4  Summary'),")
new = '''('p', "The positioning of this work is gap-based: for each point we state what the surveyed papers do not do and what this project did. A full-text keyword scan of the twenty-three papers, extended by web searches for recent preprints, gave the following picture. Resilience and chaos-engineering papers inject infrastructure faults only; anomaly detectors operate on metrics, logs and traces, which are normal during a silent failure; SLO practice concerns latency and availability; readiness-probe guides for model servers test whether the server can answer, not whether the answer is correct; recovery work optimises infrastructure recovery; and delivery pipelines evaluate models offline."),
('table', ['Gap in the existing work', 'What this project does', 'Evidence', 'Closest prior work'], [
 ['Chaos studies inject infrastructure faults only', 'SilentBench: eight faults that keep the service healthy but wrong, on monolith, Compose and Kubernetes', 'Default probes: 100 % wrong answers, 0 detections (10 trials per cell)', 'Chaos papers (Siwach and Haridas; Nigam and Patel; Zaccarini et al.)'],
 ['Detectors watch metrics, logs and traces, which are normal in a silent failure', 'Health defined on the model output; a log-based detector measured as blind', '0 log templates, 0 of 6 faults detected from logs', 'Trace/log/metric anomaly detectors (A7, A13-A15, A18, A20, A21, A23)'],
 ['SLOs cover latency and availability, not answer correctness', 'Correctness SLO with Wilson lower bound and burn rates', 'Alert 9-15 s after value corruption', 'Gummadi and Chilamkurti; a runtime SLO guard for ML serving (arXiv 2607.09992) is close prior work'],
 ['Probe guides test "can serve", not "serves correct answers"; the recovery trade-off is unmeasured', 'Semantic readiness, semantic liveness and partial readiness measured under silent faults', 'Readiness alone: 92 % failed, never restored; readiness + liveness: 36 s; partial readiness 0 % vs strict 81 % failed', 'llm-d readiness guide; vLLM health-check issue (qualitative only)'],
 ['Recovery work optimises infrastructure, not answer quality', 'Operator that restores full quality; cost model that charges time below full quality', '20 of 20 restored in about 22-24 s vs never; cost-blind bandit 5 of 20', 'Chaos + RL + digital-twin papers (Nigam and Patel; Zaccarini et al.)'],
 ['Delivery pipelines evaluate models offline', 'Shadow-traffic gate on output validity and an Argo canary driven by it', '15 of 15 bad candidates rejected, 6 of 6 good promoted', 'Standard canary practice'],
 ['Degradation and deadlines are described in practitioner write-ups, not measured on real faults', 'Deadline- and load-aware tier fall-through measured under a delay fault', 'Failed requests 96.8 % to 0 %', 'Edge failover study (2023) and fallback-cascade write-ups'],
]),
('cap', 'Table 2.2  Gaps in the literature, what this project does, and the closest prior work'),
('p', "Several ingredients are individually known and are cited as such: golden-output and bit-flip detection (LM-Fix, RADAR, TrustSeed), conformal runtime monitoring of AI services (WATCH; evaluation-as-a-service with conformal guarantees; online conformal prediction by Hajihashemi and Shen), self-healing machine-learning frameworks, and tiered fallback. The contribution claimed here is therefore empirical and systems-level: a measured study of silent ML failures across deployment styles and an integrated, Kubernetes-native defence with quantified recovery, not a new algorithm. Only the twenty-three papers and a limited web search were checked; a structured IEEE Xplore and Google Scholar search is required before the word first is used in a paper."),

'''
c2 = c2[:i] + new + c2[j:]
io.open(R + 'c2.py', 'w', encoding='utf-8').write(c2)

# ---- chapter 6: reframe 6.4 and add metamorphic section
c6 = io.open(R + 'c6.py', encoding='utf-8').read()
c6 = c6.replace("('h3', '6.4  Innovative Components'),", "('h3', '6.4  Contributions (gap-based)'),")
c6 = c6.replace("Six components are put forward as the innovative contributions. They are individually modest; their value lies in the integration and in the measurements that support them. Claims of priority are restricted to the reviewed literature and must be confirmed by a structured IEEE and Scholar search.",
                "Six contributions are put forward. Several of their ingredients are known in the literature (Section 2.3); the contribution is the measured, integrated study that fills the gaps listed there. Claims of priority are restricted to the reviewed literature and must be confirmed by a structured IEEE and Scholar search.")
k = c6.index("('h3', '6.6  Overall Analysis'),")
meta = f'''('h3', '6.6  Metamorphic Readiness Probe (experimental)'),
('p', "To obtain a correctness check that needs no stored reference output, a metamorphic probe was built. A metamorphic relation links the outputs of the model on two related inputs. Relation 1 (sensitivity profile) requires that the response of the six-step forecast to a one-standard-deviation shift of the input window stays inside a band learned offline on the healthy model; the first relation that was tried, equivariance under translation, was falsified by the data because the trained LSTM mean-reverts, and it was replaced by the learned band. Relation 2 (recursive self-consistency) requires that the forecast after the first step equals the forecast made from the window extended by the first forecast value. Tolerances are conformal quantiles (alpha = 0.01, family-wise over three probe windows) calibrated on {ev['windows']} historical windows, so a model that is already corrupt at start-up can be detected; the probe is read-only and disabled by default."),
('table', ['Fault', 'Detected (30 probes)', 'Median score (threshold = 1)'], [
 ['corrupt (NaN)', '{F['corrupt']['detected_pct']} %', 'very large'],
 ['unit change', '{F['unitchange']['detected_pct']} %', '{F['unitchange']['median_score']}'],
 ['flat-line', '{F['flatline']['detected_pct']} %', '{F['flatline']['median_score']}'],
 ['stale output', '{F['stale']['detected_pct']} %', '{F['stale']['median_score']}'],
 ['bit flip (8 flips)', '{F['bitflip']['detected_pct']} %', '{F['bitflip']['median_score']} (marginal)'],
 ['bit flip (16 flips)', '{F['bitflip_severe']['detected_pct']} %', '{F['bitflip_severe']['median_score']} (marginal)'],
 ['scaler', '{F['scaler']['detected_pct']} %', '{F['scaler']['median_score']} (missed)'],
]),
('cap', 'Table 6.9  Metamorphic probe: detection per fault (no golden output, no stored reference)'),
('p', "The false-alarm rate depends on how the probe is calibrated. With calibration on the even windows of all years and testing on the odd windows it was {ev['false_alarm_interleaved_triple_pct']} percent per probe; with calibration on the years up to 2018 and testing after 2018 it rose to {ev['false_alarm_timesplit_triple_pct']} percent, because the response band does not survive the post-2018 drift and would need periodic re-calibration. In a cluster test with the golden check switched off, the probe scored healthy windows at the threshold (0.996 to 1.0) and missed the injected eight-flip bit fault (0.996). The honest conclusion is that the probe reliably detects output-level and gross faults (which the envelope, invariants and canary already detect) but not subtle weight corruption, for which the golden-output check remains necessary. It is therefore reported as an experimental and partly negative result, not as a claimed novelty."),

'''
c6 = c6[:k] + meta + c6[k:].replace("('h3', '6.6  Overall Analysis'),", "('h3', '6.7  Overall Analysis'),").replace("('h3', '6.7  Summary'),", "('h3', '6.8  Summary'),")
io.open(R + 'c6.py', 'w', encoding='utf-8').write(c6)

# ---- chapter 7 + references
c7 = io.open(R + 'c7.py', encoding='utf-8').read()
c7 = c7.replace(' "Metamorphic readiness probes: transform the input (shift by twelve months, rescale units) and check that the output transforms accordingly, which would need no stored reference and could detect models that were corrupt from the beginning.",',
                ' "Improve the metamorphic readiness probe (Section 6.6): periodic re-calibration against drift, a larger and more diverse set of probe windows, and relations with more power against subtle weight corruption.",')
c7 = c7.replace(' "Novelty claims are limited to the 23 papers reviewed;', ' "The metamorphic probe is experimental: marginal against subtle bit flips and sensitive to drift when calibrated on earlier years.",\n "Novelty claims are limited to the 23 papers reviewed and a limited web search;')
c7 = c7.replace(' "S. Hochreiter and J. Schmidhuber,', ''' "LM-Fix: Lightweight bit-flip detection and rapid recovery framework for language models, arXiv:2511.02866.",
 "WATCH: Adaptive monitoring for AI deployments via weighted-conformal martingales, arXiv:2505.04608.",
 "Cloud-native evaluation-as-a-service: A microservices architecture for scalable AI monitoring with conformal guarantees, arXiv:2607.21623.",
 "Trusted floors under untrusted learners: A runtime assured-SLO guard for ML serving, arXiv:2607.09992.",
 "Self-healing machine learning: A framework for autonomous adaptation in real-world environments, arXiv:2411.00186.",
 "Enhancing reliability in AI inference services: An empirical study on real production incidents, arXiv:2511.07424.",
 "RADAR: Run-time adversarial weight attack detection and accuracy recovery, in Proc. DATE, 2021.",
 "S. Hochreiter and J. Schmidhuber,''', 1)
io.open(R + 'c7.py', 'w', encoding='utf-8').write(c7)
b = io.open(R + 'build_report.py', encoding='utf-8').read()
b = b.replace("OUT = os.path.join(HERE, 'Project_Report.docx')", "OUT = os.path.join(HERE, 'Project_Report_v2.docx')")
io.open(R + 'build_report.py', 'w', encoding='utf-8').write(b)
m = io.open(R + 'measure.py', encoding='utf-8').read()
m = m.replace("'Project_Report.docx'", "'Project_Report_v2.docx'").replace("'Project_Report.pdf'", "'Project_Report_v2.pdf'")
io.open(R + 'measure.py', 'w', encoding='utf-8').write(m)
print('report patched')
