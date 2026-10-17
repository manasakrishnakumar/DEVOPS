# Novelty, gaps and prior art (checked 2026-10-17)

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
