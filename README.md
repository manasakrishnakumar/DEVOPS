# Correctness-Aware Self-Healing for ML Forecasting Services on Kubernetes: Detecting and Recovering from Silent Failures

A DevOps research project (R V College of Engineering, ISE). The workload is the Bangalore Climate Analytics app
(SARIMA + LSTM forecasts of rainfall, temperature and humidity, 1951-2024). The study shows that **silent model failures
(HTTP 200 with wrong forecasts) are invisible to default Kubernetes and Docker Compose health checks**, and builds and measures a
correctness guard, graceful degradation, a silent-fault benchmark, a correctness SLO and an operator that restores full quality.

## Key findings (all measured, small samples; see the documents)
- Default Kubernetes / Compose never recover from silent faults (100 % wrong answers, 0 of 10 detected).
- A conformal-envelope guard with soft invariants and a cross-model canary turns detectable silent faults into valid, labelled degraded answers; 0 false alarms on hold-out windows and in a 10-minute healthy soak.
- The operator restores full quality in about 19-26 s with the rules policy (20/20) and, after a cost-model fix, with the learned bandit policy (20/20; it first failed 15/20).
- Tuned probe period/threshold gave no benefit; replicas dominate recovery time.
- A golden-output integrity check (config G4) catches the subtle bit flips that evaded every other check (20/20 caught, 0 false alarms in healthy control).
- Deadline- and load-aware degradation (config H4) turns the delay fault from 96.8 % failed requests into 0 % failed (94 % valid degraded answers) and cuts burst p95 about 4x.
- Bit-flip fuzzing (12,600 trials): exponent-MSB flips give 50 % wrong answers and the envelope misses 34 % of all wrong answers; the golden check misses none. Signed (cosign) golden outputs close the corrupted-at-start-up blind spot (99.9 % wrong with health OK before, 0 % wrong after) and a tampered reference or model file never becomes Ready (10/10 each). Operator rollback restores a bad release in 46 s (release-aware) / 77 s (escalate) where restart-only never recovers (0/5).
- Honest limits: the golden check only detects change from a trusted start-up state; the guard does not help crash/hang/OOM; 5-10 trials per cell on one laptop.

## Where to start
| File | Content |
|---|---|
| `PROJECT_HANDOFF.md` | overview, architecture, file map, status table, decisions, how to continue |
| `IMPLEMENTATION_PHASES.md` | phases 0-15 with evidence and what was changed |
| `TESTING_AND_KNOWN_ISSUES.md` | every measured result, tests, known issues (K1-K42) |
| `REFERENCES_AND_LITERATURE_REVIEW.md` | 23 provided papers + web sources, gaps, traceability |
| `EXTRAS_AND_FUTURE_WORK.md` | all additional ideas with status |
| `NOVELTY_AND_PRIOR_ART.md` | gap-based novelty, prior art found, honest verdict |
| `SECURITY_REVIEW.md` | manual security review, 10 findings |
| `RESTORE.md` | set up a new machine (Docker Desktop, Minikube, images, experiments) |
| `PROJECT_HANDOFF_COMPLETE.pdf`, `Literature_Survey.pdf` | PDF versions |

## Layout
`monolith/` (config A) · `frontend/` + `inference-api/` + PostgreSQL (configs B/C) · `k8s/`, `monitoring/` (Minikube, Prometheus, Grafana) ·
`chaos/` (probes, fault/load runner, DoE, operator experiments) · `analysis/` (guard ablation, invariants, predictor, twin/bandit, extras) ·
`operator/` (kopf operator) · `retrain/` · `validation/validate_all.py` (25 executed checks) · `results/` (all raw data).

## Quick check
```bash
python validation/validate_all.py      # needs Docker Desktop + Minikube with the images loaded (see RESTORE.md)
```
Models (`*.pkl`, `*.h5`) are stored with Git LFS. Default secrets in manifests are lab placeholders; change them before any real deployment.
