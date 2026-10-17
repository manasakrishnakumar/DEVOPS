# REFERENCES AND LITERATURE REVIEW

Companions: [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) · [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) · [TESTING_AND_KNOWN_ISSUES.md](TESTING_AND_KNOWN_ISSUES.md) · [Literature_Survey.pdf](Literature_Survey.pdf)

**Verification policy.** Group A papers were available as PDFs; title, authors (first page) and abstract were read by script (`pypdf`), and a full-text keyword scan was run (conformal, probe, bandit, Bayesian optimisation, shadow/canary, silent, MTTR, degradation, drift, energy). Findings beyond the abstract were **not** read in depth. Years marked `~` were inferred from PDF text and are **unverified**. Group B items were pasted into chat as abstracts only (no authors/year captured). Group C comes from web-search snippets. No DOI was verified for any entry. Nothing here has been checked against IEEE Xplore.

## 1. Group A — PDFs provided (zip `OneDrive_1_10-14-2026.zip`, `getpdf_jsp.zip`)

| # | Title | Authors (first page) | Year | Problem / method | Key result (abstract) | Limitation / gap | Relevance to this project |
|---|---|---|---|---|---|---|---|
| A1 | AI-Augmented Chaos Testing: Toward Intelligent Resilience Engineering in Cloud-Native Systems | S. Nigam, S. Patel | 2025 (title) | GNN criticality + transformer anomaly forecast + RL experiment orchestration + "Resilience Mirror" digital twin | up to 46 % fewer SLO violations, 38 % lower MTTR (Kubernetes, edge, GPU) | generic workloads; no ML-output correctness | closest chaos/RL work; cite for chaos + digital twin |
| A2 | A Comparative Study of Automatic Migration from Monolith App to Microservices | J. Zairi, A. Kenzi | ~2025 | review of 20 decomposition studies | framework + criteria | no runtime data | migration background |
| A3 | A Predictive Elastic Scaling Method for Kubernetes Based on Load Forecasting | L. Li | ~2025 | PathFormer CPU forecast → replicas via Prometheus/K8s API | beats HPA (ETTm2, Alibaba trace, cluster) | ignores model warm-up | autoscaling baseline |
| A4 | A Stacking Ensemble ML-Based Failure Prediction Model for Optical Networks with Imbalanced Data | Z. Sun et al. | ~2024 | stacking ensemble, 5.3 % failure ratio | F1 98.97 % | optical networks | imbalance handling idea |
| A5 | AdaptiPID: Model-Aware Adaptive Gain Tuning … Robotic Manipulator Control | Y. Zhou | ~2026 | adaptive PID | – | unrelated | excluded |
| A6 | Architecture-based Failure Prediction via LSTM and Bayesian Network in Service-oriented Systems | X. Wu et al. | ~2022 | LSTM reliability series + BN | +14 % accuracy | infra series only | failure-prediction related work |
| A7 | Autoencoder-based Anomaly Detection in Microservices using Distributed Tracing (AnoTraceAE) | not read from page 1 | 2024 (2024 AISP header) | conv. autoencoder on traces, TrainTicket | superior to baselines | detection only | detector related work |
| A8 | Chaos Engineering based Kubernetes Pod Rescheduling through Deep Sets and RL | M. Zaccarini, F. Poltronieri, D. Borsatti, W. Cerroni, L. Foschini, G. Grabarnik et al. | ~2025 | TELKA: chaos + RL + digital twin for pod rescheduling | scalable to varying node counts | scheduling only | related to N3 |
| A9 | Deployment of SARIMA Models for Network Reliability Prediction | D. Singh | 2024 | SARIMA deployment steps | short-term reliability prediction | no ops metrics | SARIMA context |
| A10 | Evaluating operational readiness using chaos engineering simulations on Kubernetes in Big Data | G. Siwach, A. Haridas | ~2022 | random pod kills, recovery time | recovery time inferred | no ML/silent faults | baseline chaos study |
| A11 | Is it Worth Migrating a Monolith to Microservices? Performance, Availability and Energy | V. Berry et al. | ~2024 | migration experience report | MSA better when nothing replicated; monolith better when entire app replicated | generic web app | closest migration study |
| A12 | Kube-CC: Experiment Education Platform for Big Data Courses on Kubernetes | F. Xue et al. | ~2023 | K8s teaching platform | – | no resilience data | background only |
| A13 | MicroMILTS: Fault Location for Microservices (Mutual Information + LSTM-AE) | L. Yang et al. | ~2022 | BIRCH + LSTM-AE + MI | locates faulty service | infra metrics | detector related work |
| A14 | Multi-Level Ensemble Anomaly Detection for Microservices (Statistics, Isolation Forest, Adaptive Thresholding) | not read | ~2025 | Prometheus metrics, layered detector | stable detection on ERP-like testbed | no recovery | Isolation-Forest-on-metrics precedent |
| A15 | Recall-Prioritized Anomaly Detection in Cloud Microservices using Unsupervised Transformer Autoencoders | A. C. et al. | ~2025 | LogBERT-Lite on OpenStack logs | 8/11 faults, precision 4.37 % | low precision | related work |
| A16 | Research on Constraint-Aware Fault Recovery Diagnosis Decision Method for Offline Edge Kubernetes | Z. Wei, K. Bai | ~2025 | Repair/Degrade/Rebuild decision tree | MTTR 127 → 34 min (case) | manual-style, edge | "Degrade" strategy precedent for tiers |
| A17 | Residual Artifact Governance With ML-Enabled GC Prediction in K8s 5G/6G SBA | L.-M. Tufeanu et al. | 2026 (IEEE TNSM vol. 23) | ML time-to-collapse + GC agents | bounded residual peaks | telecom | ML early-warning analogy |
| A18 | Robust Hybrid Autoencoder-LSTM Framework for Real-Time Anomaly Detection in Multi-Cloud | S. Oviya et al. | ~2025 | AE + LSTM score | 94.2 % acc, 5.6 % FP (CICIDS2017) | intrusion data | comparison detector |
| A19 | SLO Observability with Splunk and Dynatrace in Microservices | V. P. K. Gummadi, L. S. Chilamkurti | ~2025 | SLO/SLI/error budgets practice | alert-fatigue reduction | no experiments | SLO framing for C1 |
| A20 | Multi-Modal Anomaly Detection for Microservices Based on VGAE-Transformer (VTMAD) | C. Shao, X. Zhou et al. | ~2025 | VGAE + Transformer | outperforms baselines (2 datasets) | heavy, no healing | detector related work |
| A21 | TraceDAE: Trace-Based Anomaly Detection in Microservice Systems via Dual Autoencoder | J. Li, S. Ying, T. Li et al. | 2025 (IEEE TNSM vol. 22 no. 5) | STG + GAT/LSTM dual AE | efficient detection | trace anomalies only | detector related work |
| A22 | Enhanced Multi-model Online Conformal Prediction | E. Hajihashemi, Y. Shen | not read | online conformal, bipartite-graph model subset selection | smaller sets, lower cost | theory; no systems use | only paper with conformal in the zips; supports N1 technique, not novelty |
| A23 | SGCAD: Structure-aware Granger Causality-based Anomaly Detection for Microservice Systems | Z. Zhang, C. Wan et al. | not read | neural Granger causality + root-cause ranking | high recall, low FP (RS-Anomic) | metrics only | detector related work |

Full-text keyword scan result across A1–A23: "conformal" appears only in A22; "Bayesian optimization/surrogate/Gaussian process" in none; "shadow"/"canary" in a deployment sense in none (A1 uses "Resilience Mirror"); "liveness probe/readiness" only a one-line background mention in A8; "bandit" only in A1 (RL/Bandits propose adaptive fault scenarios) and A22 references.

## 2. Group B — abstracts pasted in chat (bibliographic data NOT captured; do not cite without lookup)
CanaryRisk (canary-stage release risk, gradient boosting + SHAP, AUC 0.946, Online Boutique) · SARIMA-based Prediction-Based Autoscaler vs HPA (serverless cold start) · Pick and Spin (Kubernetes multi-LLM orchestration, warm/cold states) · KServe model-delivery paths (OCI image volumes, 208× warm-start difference) · eProbe (eBPF container probing) · MAPPO multi-agent RL for Kubernetes reliability · DQN multi-dimensional autoscaler · Fast-response/Slow-shrinkage HPA · OpenShift vs Helm comparative study (Online Boutique, K6, kube-burner) · Saga/Outbox distributed-transaction framework · monolith→microservices equivalence (deadlock/extra behaviour) · migration-tool comparison framework · Sec-Llama (compact LLM IDS) · TADL (Transformer anomaly detector/locator, sock-shop) · Ceph DoE/RSM MTTR study · FTTH outage classification (SMOTE, RF F1 = 1.0) · SOAR book · cloud self-healing survey · Kubernetes self-healing conceptual analysis · Research_Gap_Analysis_Final.pdf (12 IEEE climate-anomaly papers; Group B-climate: CNN-LSTM Ethiopia, IF/OCSVM Bangladesh, SHAP dual-model, LSTM-VAE/Anomaly Transformer, Z-score trends, reservoir WST, Fuzzy-PINN, CFGCN — belongs to the *earlier climate-analysis paper*, not this DevOps paper).

## 3. Group C — web-search results (snippets only; fetch and read before citing)
- Lazy container image pulling for model serving on Kubernetes: "The Lazy Pod That Lies" — https://arxiv.org/pdf/2608.19412 (probes green while model broken; motivation).
- Label-free failure detection by disagreement (D3M): https://arxiv.org/abs/2506.05047v3
- N-version machine learning architecture (Machida, DSML 2019): https://www.sd.cs.tsukuba.ac.jp/papers/dsml2019-machida.pdf
- Safe remediation as risk-constrained intervention: https://arxiv.org/pdf/2607.20005 ; ARBITER: https://arxiv.org/pdf/2607.19182 ; TELKA (IBM/Unife): https://research.ibm.com/publications/telka-twin-enhanced-learning-for-kubernetes-applications
- Signalling Health for Improved Kubernetes Microservice Availability: https://arxiv.org/pdf/2507.02158 (probe interval vs detection time; closest to N4)
- Conformal anomaly detection library (nonconform): https://arxiv.org/pdf/2605.13642
- Conformal coverage/deferral operational characteristics: https://arxiv.org/pdf/2602.18045v2
- Adaptive conformal anomaly detection with time-series foundation models: https://arxiv.org/pdf/2604.20122 ; TSFM cost-aware industrial monitoring: https://arxiv.org/pdf/2608.22968
- Soft invariants with hold-rates (networked systems): https://arxiv.org/pdf/2607.22944
- ML serving chaos on GPU LLM workloads: https://arxiv.org/pdf/2603.02057
- Shadow deployment practice: https://atlan.com/know/shadow-deployment-for-ml-models/ ; Uber deployment safety: https://www.uber.com/en-HN/blog/raising-the-bar-on-ml-model-deployment-safety
Status: arXiv IDs in the 26xx range were returned by the search tool; their existence/dates must be confirmed.

## 4. Research gap and contribution (evidence-based)
| Claim | Supported by | Status |
|---|---|---|
| Default probes/restarts do not recover silent ML failures | our trials B/C corrupt: 0/5 recovered, 100 % failed | **Measured (n = 5)** |
| Conformal window-level envelope + invariants + cross-model canary detects them with 0 % hold-out false alarms | offline ablation; config D corrupt 3.5 s | **Measured offline + 5 live trials** |
| Novelty of conformal health check for Kubernetes ML services | no hit in A1–A23 or web snippets | **Not verified** — need IEEE/Scholar search |
| N-version disagreement for ML serving | Machida 2019, D3M exist | **Not novel**; novelty only in heterogeneous forecasters + calendar alignment + tier fall-through |
| Learned recovery action policy | TELKA, 2607.20005, ARBITER exist | **Not novel** (supporting only) |
| Bayesian-optimised probe parameters | none found; closest 2507.02158 | **Unverified; no data yet** |
| Shadow/canary model gate | standard MLOps practice | **Not novel**; criterion only |
| Correctness SLO from conformal coverage | none found | **Unverified; not implemented** |

## 5. Literature-to-implementation traceability
| Source finding | Requirement | Design decision | Phase / files | Validation |
|---|---|---|---|---|
| Probes insufficient (A8, 2608.19412) | detect silent faults | semantic guard | P4 `guard.py` | config C vs D corrupt |
| Conformal validity assumes exchangeability (A22, 2605.13642, 2602.18045) | honest false-alarm control | window-level calibration, hold-out test | P5 `calibrate_windows` | `phase5_guard_ablation.json` |
| N-version disagreement (Machida, D3M) | label-free detection | canary vote | P4 `canary_once` | local disturbance tests; live data pending |
| Degrade strategy (A16) | graceful degradation | tier chain | P4 `serve` | D corrupt tiers = climatology |
| SLO practice (A19) | correctness SLO | SLI/burn-rate | P7 (not started) | – |
| Ceph DoE/RSM (Group B) | MTTR model | CCD + RSM + BO | P9 `doe.py`, `bo_probe.py` | not run |
| Migration reports (A11) | A/B/C comparison | three configs | P3 | load + fault tables |

## 6. Bibliography (IEEE-style placeholders — verify before use)
[1] S. Nigam and S. Patel, "AI-Augmented Chaos Testing: Toward Intelligent Resilience Engineering in Cloud-Native Systems," 2025. [venue/DOI not captured]
[2] V. Berry et al., "Is it Worth Migrating a Monolith to Microservices? An Experience Report on Performance, Availability and Energy Usage," [year/venue unverified].
[3] M. Zaccarini, F. Poltronieri, D. Borsatti, W. Cerroni, L. Foschini, G. Ya. Grabarnik, et al., "Chaos Engineering based Kubernetes Pod Rescheduling through Deep Sets and Reinforcement Learning," [year/venue unverified].
[4] E. Hajihashemi and Y. Shen, "Enhanced Multi-model Online Conformal Prediction," [venue/year unverified].
[5] Z. Zhang, C. Wan, et al., "SGCAD: Structure-aware Granger Causality-based Anomaly Detection for Microservice Systems," [venue/year unverified].
[6] J. Li, S. Ying, T. Li, et al., "TraceDAE: Trace-Based Anomaly Detection in Microservice Systems via Dual Autoencoder," IEEE Trans. Netw. Service Manag., vol. 22, no. 5, Oct. 2025.
[7] L.-M. Tufeanu et al., "Residual Artifact Governance With ML-Enabled Garbage Collection Prediction in Kubernetes-Based 5G/6G Service-Based Architecture," IEEE Trans. Netw. Service Manag., vol. 23, 2026.
[8] F. Machida, "N-version machine learning architecture for safety-critical systems," DSML 2019. [exact title/pages unverified]
Other entries: use Group A table and Group C URLs; all DOIs **unverified**.

## Information Needed
IEEE/Scholar lookup for years, venues and DOIs of all `~` entries; read-in-full of A1, A8, A11, A16, A22, 2507.02158, 2608.19412, D3M before final related-work text; a systematic search for "conformal" + microservice/health check, "bandit" + AIOps remediation, "Bayesian optimization" + probe parameters.

## 7. ADDENDUM (updated 2026-10-17): sources behind the extras (bibliographic details NOT verified)
Standard methods used in code (cite the original papers before submission; details not checked here): Isolation Forest, Mahalanobis distance, SMOTE, Page-Hinkley test, population stability index, Weibull survival model, Hedge / multiplicative weights, adaptive conformal inference, split-conformal prediction, Granger causality, gradient boosting, LSTM autoencoder. Chronos (Amazon time-series foundation model, `amazon/chronos-t5-tiny`) was only attempted (TESTING 3.17); its paper and licence must be looked up before citing.
Traceability additions: silent faults vs probes -> Phase 3/6 (C4 vs D4/E4); conformal exchangeability caveat -> Phase 5 window calibration and Phase 13a; N-version / disagreement -> canary and the third-model vote (TESTING 3.16); remediation-action papers (TELKA, safe remediation, ARBITER) -> Phase 8 operator and twin (supporting only); shadow-deployment practice -> Phase 11; SLO practice paper -> Phase 7. No new papers were read in full since section 6; the survey table's years marked ~ and two author lists remain to be verified.

## 8. ADDENDUM (2026-10-17): prior art found by web search (authors not captured; verify before citing)
LM-Fix arXiv 2511.02866; WATCH arXiv 2505.04608; Cloud-Native Evaluation-as-a-Service arXiv 2607.21623; Trusted Floors Under Untrusted Learners arXiv 2607.09992; Self-Healing Machine Learning arXiv 2411.00186; Enhancing reliability in AI inference services (production incidents) arXiv 2511.07424; RADAR (DATE 2021); TrustSeed (DATE 2026). See NOVELTY_AND_PRIOR_ART.md.
