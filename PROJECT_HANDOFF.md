# PROJECT HANDOFF

Project root: `C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project`
Original application (untouched, archive): `...\bangalore_climate_app_final\bangalore_climate_app`
Companion documents: [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) · [REFERENCES_AND_LITERATURE_REVIEW.md](REFERENCES_AND_LITERATURE_REVIEW.md) · [TESTING_AND_KNOWN_ISSUES.md](TESTING_AND_KNOWN_ISSUES.md) · [EXTRAS_AND_FUTURE_WORK.md](EXTRAS_AND_FUTURE_WORK.md) (all non-major ideas, to include after the main phases) · [RESTORE.md](RESTORE.md) · [Literature_Survey.pdf](Literature_Survey.pdf)

> Evidence policy: everything below was observed on disk or in tool output during the working sessions (13–16 Oct 2026). Items not run are labelled "NOT RUN". Where a number comes from a small sample (5 trials per cell) it is labelled preliminary.

---
## 1. Project overview

**Owner / context.** Manasa Krishnakumar, RV College of Engineering, ISE, USN 1RV23IS067 (from `DevOps_Project_Proposal.docx`). Course: Development and Operations (DevOps), Professional Core Elective-IV. Goal: a measurable, paper-worthy DevOps study.

**Working title.** "Self-Healing Beyond Liveness: Model-Aware Recovery, Delivery and Failure Prediction for ML Forecasting Services on Kubernetes" (alternative short form: "Model-Aware Self-Healing for ML Forecasting Services on Kubernetes: A Fault-Injection Study"). *Title is not yet frozen; the contribution list changed twice (see §6).*

**Original proposal (two candidates in the proposal docx).**
1. Migrate the existing monolithic Bangalore Climate Analytics app to Kubernetes microservices and measure performance/scalability.
2. Build a small app and measure Kubernetes self-healing vs plain Docker.
The user's decision (conversation): do a combined project on the *real* climate app, adding ML-specific novelty so the paper is publishable.

**Actual implemented system.** The existing Flask app (SARIMA + real trained LSTM forecasts, Climate Extreme Score, Isolation-Forest anomalies, XAI pages, user login/history) was cleaned, split into `frontend` + `inference-api` + PostgreSQL, containerised, deployed on Minikube with Prometheus/Grafana, and instrumented with a fault-injection and load harness. On top, a *semantic correctness guard* (conformal envelope + soft invariants + cross-model canary + tiered degradation) was built and measured.

**Problem statement.** Kubernetes/Compose health checks only observe liveness. An ML forecasting service can fail silently (HTTP 200 with wrong/NaN forecasts). Measured here: default Kubernetes and Compose **never recover** from such a fault.

**Objectives.** (O1) quantify recovery behaviour of monolith vs Compose vs Kubernetes under faults; (O2) design and evaluate a correctness-aware guard with graceful degradation; (O3) a silent-fault benchmark; (O4) a correctness SLO; (O5) DoE/RSM + Bayesian optimisation of probe parameters.

**Scope / limits.** Single laptop (12 logical CPUs, ~7.6 GB to Docker, Minikube 4 CPU/5.5 GB); one dataset (Bangalore monthly 1951–Jun 2024, 882 rows); 5 trials per cell so far.

**Contributions (current list, see §6 for history).**
| ID | Contribution | Status |
|---|---|---|
| C-core | Silent-failure evidence: corrupt fault never recovers on B/C | **Verified (5 trials/cell)** |
| N1 | Conformal semantic probe/guard (window-level calibration) | Implemented, offline ablation + config D measured |
| N2 | Cross-model canary (SARIMA, LSTM, climatology) + tiered degradation | Implemented, locally tested, config D measured |
| C2 | Soft invariants (kept: temporal Temp_mean + flatline) | Implemented; weak (see issues) |
| C3 | Silent-fault benchmark (8 fault modes incl. severe bit flip) | **Pass 1 complete (120 trials)**; pass 2 running |
| C1 | Correctness SLO (SLI, burn-rate) | Implemented (metrics, `/slo`, rules, replay); **not yet measured** |
| N3 | Learned recovery policy (twin + bandit + operator) | Twin/bandit run (preliminary); operator experiments written, **queued** |
| N4 | DoE/RSM + Bayesian-optimised probes | DoE (30 runs, RSM R2 about 0.89) + held-out validation: **tuned probe period/threshold gave no benefit; replicas dominate (K28)** - report as a negative/neutral result |
| N5 | Shadow-traffic model gate | Implemented, tested locally only |
| A1–A3 | Aging, drift-retrain, energy-aware tiers | Implemented, tested locally only |

**Verified novelty.** *Not verified.* Only keyword/abstract checks against the 23 provided PDFs and a web search (snippets). See [REFERENCES_AND_LITERATURE_REVIEW.md](REFERENCES_AND_LITERATURE_REVIEW.md) §4. Do not claim novelty beyond "to the best of our knowledge".

---
## 2. Technology stack (actual)

| Technology | Version (evidence) | Role | Status |
|---|---|---|---|
| Python | 3.10.6 host; `python:3.10-slim` in images | all services/scripts | used |
| Flask / Werkzeug | 2.3.3 / 2.3.7 (`*/requirements.txt`) | web + API | used |
| Flask-Login, Flask-WTF, WTForms | 0.6.2 / 1.1.1 / 3.0.1 | frontend auth/forms | used |
| gunicorn | unpinned in `inference-api`, 21.2.0 frontend | WSGI server (1 worker in inference-api, 2 in frontend/monolith) | used |
| pandas / numpy / scipy / scikit-learn | 2.0.3 / 1.24.3 / 1.11.1 / 1.3.0 | data + stats (host has newer: pandas 2.3.3, sklearn 1.7.2) | used |
| statsmodels | 0.14.0 (image) / 0.14.5 host | SARIMA models (`.pkl`, ~118 MB each) | used |
| tensorflow-cpu / keras | 2.15.1 | LSTM `.h5` models (~0.4 MB each) | used |
| matplotlib / seaborn / plotly | 3.7.2 / 0.12.2 / 5.15.0 | plots (frontend/utils) | used |
| SQLite → PostgreSQL | postgres:15-alpine, psycopg2-binary 2.9.9 | users/predictions (DATABASE_URL switches backend) | used |
| Docker Desktop | 29.8.2 (WSL2 backend) | build/run | used |
| Docker Compose | bundled | config B | used |
| Minikube / kubectl | cluster reported v1.37.0 | config C/D/E | used |
| Helm | installed via winget | Prometheus + Grafana charts | used |
| Prometheus (chart `prometheus`), kube-state-metrics, Grafana | via Helm | observability, 5 s scrape | used |
| kopf 1.37.2 / kubernetes 29.0.0 | operator image | `ForecastService` operator | built, **not deployed** |
| pyDOE2, imbalanced-learn, locust | installed on host | DoE design / SMOTE / (locust not used; own probe used) | pyDOE2 used in `chaos/doe.py`; others unused |
| Argo Rollouts, Kyverno, cosign, Trivy | manifests/CI only | delivery/supply chain | **not installed/run** |
| GitHub Actions | `.github/workflows/ci.yml` | CI | **never run (no repo)** |
| KEDA, OpenTelemetry | – | scaling / tracing | **not implemented** |

No credentials are stored in this document. Defaults in manifests (`SECRET_KEY`, DB password) are lab placeholders in `k8s/00-base.yaml` and `docker-compose.yml`; change before any real deployment.

---
## 3. Architecture (as implemented)

```mermaid
flowchart LR
  U[Browser] --> F[frontend Flask :5000]
  F -- REST /predict?model=sarima|lstm --> I[inference-api :5001]
  F --> P[(PostgreSQL)]
  I --> S[SARIMA backend .pkl]
  I --> L[LSTM backend .h5 + scaler]
  I --> G[SemanticGuard: envelope + invariants]
  I --> C[climatology / cache tiers]
  I -- /metrics --> PR[Prometheus] --> GR[Grafana]
  OP[operator (not deployed)] -. /health/semantic .-> I
```

**Request flow (`inference-api/app.py::serve`).** For `model=auto|lstm|sarima`: walk `tier_chain` (requested → lstm → sarima → climatology → cache). Per tier: skip if canary marked it suspect; run backend; compute `GUARD.score` (window-level envelope + invariants); accept if ≤ 1, else next tier. With `SEMANTIC_GUARD=0` the first ready backend is returned unchecked (baseline).
**Canary (`canary_once`, every `CANARY_SECONDS`=5 s, background thread).** Runs all backends, aligns calendar months (SARIMA step 1 = Jan 2024, LSTM step 1 = Jul 2024), computes disagreement vs member median (SARIMA/LSTM/climatology), sets `_SUSPECT`.
**Frontend.** If `INFERENCE_URL` is set, SARIMA is accessed via `_RemoteSarimaVar` (looks like statsmodels result) so the original post-processing (monthly rainfall caps, CES blending, plots) is unchanged; LSTM page calls `/predict?model=lstm`. `SAVE_PLOT_FILES=0` disables pod-local file writes.
**Auth.** Flask-Login sessions, password hashing via werkzeug; shared `SECRET_KEY` from Secret in K8s. No CSRF protection beyond Flask-WTF forms on some pages (not audited).
**Deployment.** Config A = `monolith/` image; B = `docker-compose.yml`; C/D/E = Minikube namespace `climate` (`k8s/*.yaml`), monitoring in namespace `monitoring`.
**Error handling.** `/predict` returns 503 when no tier is available; backends fail soft to next tier; drift/aging are advisory (never block serving).

---
## 4. Folder and file map (actual)

| Path | Purpose | Main contents | Status | Safe to modify? |
|---|---|---|---|---|
| `monolith/` | Config A: merged SARIMA+LSTM Flask app | `app.py` (≈1.9k lines), `utils/*`, `templates/`, `static/`, `saved_models/` | tested via Flask test client + load/fault runs | yes (copy of orig + env config) |
| `frontend/` | Config B/C UI service | `app.py` (remote inference), `metrics.py`, `utils/*` | tested (compose + K8s pages 200) | yes |
| `inference-api/app.py` | API, tiers, canary, faults, /aging /drift /energy | see §3 | tested (local + cluster) | yes, carefully |
| `inference-api/guard.py` | `SemanticGuard`: envelope, window calibration, invariants, vote | `score`, `calibrate_windows`, `invariant_score`, `disagreement` | ablation run; 2 unit tests | yes |
| `inference-api/backends.py` | `SarimaBackend` (with rainfall caps), `LstmBackend` | – | tested | yes |
| `inference-api/drift.py`, `metrics.py` | PSI/Page-Hinkley; Prometheus text exporter | – | tested locally | yes |
| `inference-api/invariants.json`, `aging.json` | mined invariants; Weibull aging | generated | regenerate via `analysis/*` | regenerate, don't hand-edit |
| `inference-api/saved_models/` | `sarima_*.pkl` (3×118 MB), `lstm/*.h5` + scalers | binary | do not modify | no |
| `inference-api/tests/test_guard.py` | 2 unit tests | – | passes | yes |
| `chaos/probe.py` | in-network probe: `fault`, `load`, `silent` modes | – | fault/load used; `silent` pilot running | yes |
| `chaos/run.py` | experiment runner; configs A,B,C,D,C4,D4,E4 | – | A–D used | yes |
| `chaos/doe.py` | DoE runner (hang fault, CCD) | – | **never run** | yes |
| `chaos/*.ps1` | detached automation scripts | batch, auto_phase4, pilot_silent | used | yes |
| `analysis/` | `mine_invariants.py`, `guard_ablation.py`, `model_aging.py`, `twin_bandit.py`, `bo_probe.py`, `shadow_gate.py`, `silentbench_summary.py` | – | see status in §5 | yes |
| `retrain/loop.py` | drift→retrain→shadow→promote | – | tested locally (3 epochs, rejected) | yes |
| `operator/` | kopf operator, CRD/RBAC, Dockerfile | – | image built; **never deployed** | yes |
| `k8s/` | base manifests; `policy/kyverno-verify.yaml`, `rollout/rollout.yaml` | – | base applied; policy/rollout **not applied** | yes |
| `monitoring/` | Grafana dashboard, helm values, SLO rules | – | dashboard applied; `slo-values.yaml` **not applied** | yes |
| `results/` | all measured data (`fault_trials.jsonl`, `load.jsonl`, `phase5_guard_ablation.json`, `twin_bandit.log`, …) | JSONL | evidence; do not delete | no |
| `.github/workflows/ci.yml` | CI definition | – | never executed | yes |
| `Literature_Survey.docx/.pdf` | 21+2 paper survey | – | years marked `~` unverified | yes |

Generated/backup files in `results/`: `fault_trials_D_invalid_*.jsonl` (invalid D runs, kept as record), `fault_trials_pilot_C_only.jsonl`, `silentbench_old.jsonl`.

---
## 5. Feature status table

| Feature | Planned behavior | Actual implementation | Files | Test status | Remaining |
|---|---|---|---|---|---|
| Merge SARIMA+LSTM | single clean app | done from newer SARIMA code + LSTM routes; real `.h5` LSTM | `monolith/` | Completed and tested (Flask client, 200s) | LSTM page numbers differ from original stand-in |
| Service split | frontend/API/DB | done | `frontend/`, `inference-api/` | Completed and tested (compose + K8s) | – |
| Kubernetes baseline + Grafana | config C | done | `k8s/`, `monitoring/` | Completed and tested | OTel tracing not done |
| Fault/load harness | repeatable trials | done | `chaos/` | Completed and tested | equal worker counts for A |
| Baseline data A/B/C | 5 trials/cell | complete | `results/fault_trials.jsonl`, `load.jsonl` | Completed | more trials (10) desirable |
| Semantic guard (N1) | reject invalid output | envelope + window calibration | `guard.py` | Implemented; offline ablation; config D measured | live false-alarm soak NOT RUN |
| Cross-model canary (N2) | vote + suspect flags | done | `app.py` | Implemented, locally tested; D measured | per-fault live evidence pending |
| Tiered degradation | LSTM→SARIMA→climatology→cache | done | `app.py` | Completed and tested (D: corrupt 3.5 s) | stays degraded until restart |
| Soft invariants (C2) | cross-variable + temporal | miner + scoring; only `dt_Temp_mean` + flatline kept | `analysis/mine_invariants.py`, `guard.py` | Partially implemented; ablation shows flatline 37→100 % | little value from cross relations |
| Silent-fault benchmark (C3) | 7 faults, correctness metric | injectors + probe `silent` mode + runner | `app.py`, `probe.py`, `run.py` | Implemented, **pilot running** | full run (C4/D4/E4 × 8 faults × 10) NOT RUN |
| Correctness SLO (C1) | SLI + burn rate + alerts | only availability SLO rules written | `monitoring/slo-values.yaml` | Planned but not started | all of C1 |
| Operator (N3) | restore full tier, bandit policy | code + image | `operator/` | Implemented but not tested | deploy + experiments |
| Twin + bandit | action costs | run on 5 trials/cell | `analysis/twin_bandit.py` | Implemented (preliminary) | more data |
| DoE/RSM + BO (N4) | tuned probes | code only | `chaos/doe.py`, `analysis/bo_probe.py` | Implemented but not run on real data | run DoE |
| Shadow gate (N5) | reject bad candidate | in-process shadow | `app.py`, `analysis/shadow_gate.py` | tested locally (3/3 rejects) | cluster + Argo |
| Aging / drift / retrain (A1,A2) | Weibull, PSI/PH, loop | done | `analysis/model_aging.py`, `drift.py`, `retrain/loop.py` | tested locally | in-cluster run |
| Energy-aware tiers (A3) | cheapest valid tier | done (estimates) | `app.py` | tested locally (−73 % est.) | real counters unavailable |
| Failure predictor | IF / LSTM-AE | – | – | Planned but not started | all |
| Supply chain (Kyverno/cosign) | admission policy | manifests only | `k8s/policy/`, `ci.yml` | Planned, not installed | install + test |

---
## 6. Decisions and conversation history (recoverable)

1. **Combined project chosen** over the two proposal options (user wanted uniqueness/novelty, AI/ML, graphs, real-time graphs).
2. **LSTM added** by user (zip `bangalore_climate_app_LSTM.zip`); found it was *older* than the SARIMA folder, so the SARIMA project was kept as base and LSTM files merged. User allowed changes to the LSTM project.
3. **Real `.h5` LSTM** replaces the seasonal-repeat stand-in (numbers on LSTM page changed). Standing user instruction: do not change the meaning/outcome of original SARIMA/LSTM results — SARIMA path unchanged (rainfall caps preserved).
4. **Novelty set evolved:** (a) generic migration+recovery → (b) model-aware readiness, MTTR decomposition, failure predictor, rollout gate, operator → (c) N1–N5 (conformal probe, cross-model canary, learned recovery, Bayesian probes, shadow gate) → (d) after web check: headline N1+N2(+N4), N3/N5 demoted → (e) user approved C1 (correctness SLO), C2 (invariants), C3 (silent benchmark).
5. **User preferences:** very low token use; wants detailed phases with statuses; wants real-time graphs (Grafana live, static figures later); time-consuming work acceptable; asked to fix problems from the root cause; wants automatic continuation while asleep.
6. **Rejected/changed:** per-request cross-model voting (saturated single worker → crash loop); trend term in invariants (made hold-rate worse); α=0.05 guard (20–37 % hold-out false alarms).
7. **Pending user input:** GitHub repo link (to push; LFS needed for 118 MB models); final title; whether to drop N3/N5 from the headline; confirm bibliographic details of survey papers.

---
## 7. Continuation instructions

**Last verified working state.** Minikube cluster + Compose stack working; baseline A/B/C and config D data complete; guard ablation done; image `climate-inference:4` built (2.8 GB) and loaded to Minikube (confirmed by `minikube image ls`).
**Last completed task.** Phase 6 code: fault injectors (`bitflip`, `bitflip_severe`, `scaler`, `stale`, `unitchange`, `flatline`, `delay`) in `inference-api/app.py` verified locally via Flask test client (see TESTING doc), `probe.py --mode silent`, `run.py --silent` with configs `C4/D4/E4`, `analysis/silentbench_summary.py`.
**In progress.** Automated pipeline `chaos/auto_phase56.ps1` started 2026-10-16 02:41 (see `results/phase56_auto.log`; done flag `results/phase56_done.flag`): benchmark pass 1, healthy soak, DoE, pass 2, summary + PDF. Pilot already done (see TESTING §3.4); three defects (K18–K20) were fixed before the full run.
**Automation chain currently queued (all detached PowerShell, logs in `results/phase56_auto.log`):**
`auto_phase56.ps1` (pass 1, finished 04:52, 120 rows) → `after_pass1.ps1` ran `validation/validate_all.py` (**15/15 PASS**, `results/validation_report.md`) → `auto_phase56b.ps1` (soak done 05:28, DoE done 06:15 with 30 rows, `bo_probe.py` done, **pass 2 running since 06:15**, then summary + PDF; done flag `results/phase56_done.flag`) → `after_partB.ps1` → `phase78.ps1` (Phase 7 SLO replay + Phase 8 operator experiments + twin re-run; flag `results/phase78_done.flag`, log `results/phase78.log`).
**UPDATE (2026-10-16 22:00): Phases 11, 12 and 13 are also complete (TESTING 3.12-3.15; Argo/Kyverno/CI/KEDA remain extras). Earlier update: Phases 8, 9 and 10 are complete and documented (TESTING 3.8-3.11). Remaining main work: final results/figures/paper (extras are in EXTRAS_AND_FUTURE_WORK.md). Phase 8 operator experiments were run afterwards (see TESTING 3.8/3.9). Earlier note (superseded): STOPPED AT USER DEADLINE (2026-10-16 ~10:15).** Phase 6 complete (10 trials/cell + soak). Phase 7 measured (small sample). Phase 8: operator deployed (`climate-operator:2`), experiments NOT RUN. Image `climate-inference:6` (gthread 4 threads) is the latest.
**Next exact task (new machine).** Restore per RESTORE.md; verify images :6 and operator:2 (rebuild if missing); then run `chaos/run_operator.py`, re-run `analysis/twin_bandit.py`, re-do BO with constraints (K23); then Phases 11-14.
**Older next-task notes (superseded):**
1. Check `results/phase56_done.flag` and `results/phase56_auto.log`; if "failed", read the named log in `results/` and fix from the root cause.
2. Inspect `results/silentbench_summary.md` (D4/E4 vs C4), healthy-soak rows (`fault: none`), `results/doe.jsonl`, `analysis/bo_result.json`.
3. Analyse K21 (undetected bitflip) and K5 (D slower recovery).
4. Implement Phase 7 (correctness SLO).
**Before editing, inspect:** `inference-api/app.py` (serve, canary_once, fault), `inference-api/guard.py`, `chaos/probe.py::silent_trial`, `chaos/run.py::switch_cfg4`.
**Setup:** Docker Desktop running; `minikube start --driver=docker --cpus=4 --memory=5500`; laptop plugged in/awake; PATH needs Docker `resources\bin` and Minikube dirs; see `RESTORE.md`.
**Always verify** after an image build: `docker image inspect`, `minikube image ls`, pod image and env (done automatically by `switch_cfg4`).
**Risks.** Docker Desktop stops on sleep/sign-out; image tag reuse needs `rollout restart`; PowerShell/Git-Bash quoting issues with long heredocs (use Write tool for files); kubelet/Docker memory pressure (584 MB free RAM observed).

**Prompt for a new chat:** see the end of the final report in the originating session; also stored at the bottom of [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md).

## Information Needed
- GitHub repository URL and permission to push (models need Git LFS or external hosting).
- Final paper title and target venue/deadline.
- Confirmation of years/authors for papers marked `~` in the survey.
- Whether config A should be rerun with 1 worker for a like-for-like comparison.

## 8. ADDENDUM (updated 2026-10-17): everything since the first handoff

### 8.1 Where the documents and code are stored
| What | Location |
|---|---|
| Project root (local) | `C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project\` (synced by OneDrive if enabled) |
| GitHub repository | https://github.com/manasakrishnakumar/DEVOPS, branch `main`; first push = commit `0e305ce` (2026-10-16 night; models via Git LFS, about 381 MB); the second push (cluster extras, final documents) was made on 2026-10-17 after the suite passed 17/17 |
| Handoff documents | `PROJECT_HANDOFF.md`, `IMPLEMENTATION_PHASES.md`, `REFERENCES_AND_LITERATURE_REVIEW.md`, `TESTING_AND_KNOWN_ISSUES.md`, `EXTRAS_AND_FUTURE_WORK.md`, `README.md`, `RESTORE.md` (all in the project root) |
| PDFs | `PROJECT_HANDOFF_COMPLETE.pdf` (the four handoff documents), `EXTRAS_AND_FUTURE_WORK.pdf`, `Literature_Survey.pdf` / `.docx` (21+2 paper survey; years marked ~ unverified) |
| Raw data and evidence | `results/` (JSONL per experiment, `validation_report.md`, `silentbench_summary.csv`, `incident_reports.md`, `candidates/`, `telemetry/`) |
| Benchmark release package | `release/silentbench/` and `release/silentbench_release.zip` |
| Original, untouched application (archive) | `C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\bangalore_climate_app` (not in the repository) |

### 8.2 Status (all main implementation phases 0-13 are complete and measured; final results/paper phase remains)
Phase 0 baseline | 1 service split | 2 Kubernetes + Prometheus/Grafana (OpenTelemetry not done) | 3 fault/load harness + baselines | 4 guard, canary, tiers | 5 invariants + window calibration | 6 silent-fault benchmark (10 trials per cell + 10-minute soak) | 7 correctness SLO (small sample) | 8 operator experiments (60 trials) | 9 probe validation (replicas dominate, tuned probe settings not helpful) | 10 failure predictor (synthetic leak/drift) | 11 shadow gate in cluster (24/24, re-check 7/7) | 12 aging/drift/energy/retrain in cluster | 13 adaptive conformal + model family. Argo Rollouts, Kyverno, cosign, CI and KEDA were not run (extras).
Final verification before the first push (2026-10-16 23:20-23:58): browser walk-through of every page, API/novelty checks, Grafana, validation suite 16/16 PASS (details TESTING 3.0). After the cluster extras (2026-10-17 09:56) the suite has 17 checks (V17 = extras) and **17/17 PASS**; all extras were run or explicitly marked blocked/skipped (EXTRAS_AND_FUTURE_WORK.md).

### 8.3 Container images in Minikube / Docker (tag -> purpose)
`climate-monolith:1` (config A) | `climate-frontend:2` (config B/C frontend), `:3` (adds degraded badge, input guard, hop timing, DB timers) | `climate-inference:2` (baseline, sync worker) | `:3` (guard v1, invalid for config D, replaced) | `:4` (guard v2, benchmark pass 1/2, DoE) | `:5` (SLO/shadow, sync) | `:6` (gthread, 4 threads) | `:7` (leak/drift faults, RSS metric) | `:8` (runtime shadow endpoints; phases 11-13) | `:9` (lazy load, cache tier, intervals, partial readiness, dropvar; final) | `climate-operator:1`, `:2` (action mapping, policy volume). Rebuilding under an existing tag needs `kubectl rollout restart`; always verify the pod's image (`switch_cfg4` does this).

### 8.4 Service endpoints (inference-api) and switches
Endpoints: `/predict?model=auto|sarima|lstm&steps=N[&interval=1]`, `/health/live`, `/health/ready[?partial=1]`, `/health/semantic`, `/metrics`, `/slo`, `/aging`, `/drift`, `/energy`, `/baseline`, `/shadow/load?dir=`, `/shadow/status`, `/shadow/clear`, `/fault?mode=` (crash, hang, oom, corrupt, bitflip, bitflip_severe, scaler, stale, unitchange, flatline, delay, leak, drift, dropvar, heal, status; only when FAULT_INJECTION=1).
Environment: SEMANTIC_GUARD, GUARD_MODE (envelope | envelope+inv), GUARD_ALPHA (0.01), GUARD_CAL_END (2018), CANARY_SECONDS (5), DISAGREE_THR (1.0), ENERGY_AWARE, AUDIT_EVERY, CPU_WATTS (15), SHADOW_LSTM_DIR, MODELS, LOAD_MODE (eager | lazy), DISABLE_CLIMATOLOGY, FAULT_INJECTION, BITFLIP settings fixed in code. Frontend: INFERENCE_URL, SAVE_PLOT_FILES, DATABASE_URL, SECRET_KEY.

### 8.5 Files added since section 4 (not listed there)
`analysis/`: mine_invariants, guard_ablation, model_aging, twin_bandit, bo_probe, shadow_gate (+_cluster), failure_predictor, predictor_extras, collect_telemetry, adaptive_conformal, make_candidates, phase12_cluster, extras_offline1, extras_cluster, extras_scaling, extras_chronos, incident_summary, make_release, silentbench_summary, summarize_phase8/9_10/11_13/extras_cluster, build_handoff_pdf, slo_replay, shadow_gate.
`chaos/`: probe.py (fault, load, silent modes), run.py, doe.py, run_operator.py, validate_probe(.py/_control.py), run_family.py, burst_load.py and the detached `.ps1` pipelines (phase78b, phase910, phase1113b, extras_batch/2, final_check, after_* waiters).
`validation/validate_all.py` (16 checks). `retrain/loop.py`. `operator/` (kopf operator, CRD, RBAC). `release/silentbench/`. `results/candidates/` (8 candidate LSTM sets). Frontend: `frontend/app.py` (remote inference, metrics, degraded badge, input guard trained at start-up), `frontend/utils/database.py` (PostgreSQL/SQLite, advisory lock, DB timers).

### 8.6 Decisions and status changes since section 6
- **N4 (probe tuning) is not supported**: replicas drive recovery; recommended probe settings at one replica were slower than defaults (TESTING K28). Report as neutral/negative.
- **N3 (bandit policy)**: the cost model preferred tier-switch-only and never restarted; the rules policy is the working operator policy (TESTING 3.8).
- **Predictor**: Isolation Forest cannot extrapolate beyond its training range; a Mahalanobis detector was added; both give the same lead times; healthy false alarms 2.45 per 10 min on a small sample.
- **Image :8/:9 uses gthread**, so Phase 3 hang results (sync worker) are not comparable with Phase 13b hang results (K32).
- **Title**: unchanged (see section 1). The user was offered three options (keep and finish predictor/delivery, rename to the silent-failure framing, or hybrid); no choice recorded yet. Delivery (shadow gate) and failure prediction now exist as supporting experiments; Argo/Kyverno/CI do not.
- **User instructions to respect**: low token use; detailed phased documentation; do not claim novelty beyond the evidence; fix problems from the root cause; push to GitHub only after full verification (done once).

### 8.7 Next steps
1. Done on 2026-10-17: extras batches and fix-run finished, suite 17/17, documents and PDFs refreshed, second commit pushed. Findings to carry into the paper: semantic readiness alone leaves the service failed (92 %), semantic readiness + liveness restores in 36 s, partial readiness keeps serving (0 % failed vs 81 % strict), crash recovery is dominated by the 28 s container restart delay, scaling out on a single CPU-bound node did not help (K37).
2. Final results phase: figures from `results/*.jsonl`, confidence intervals and significance tests (n = 5-10 per cell is small), paper draft with "to the best of our knowledge" wording; IEEE/Scholar search for conformal + health checks, bandit + AIOps remediation.
3. Optional: run X06 (Argo), X07/X08 once a registry/Actions setup exists; confirm bibliographic details of the survey papers.

## Information Needed (updated)
Final title choice; target venue and page limit; confirmation of paper years/authors/DOIs; whether to publish the benchmark release (licence choice); registry/CI access for X07/X08.
