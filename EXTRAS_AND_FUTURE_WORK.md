# EXTRAS AND FUTURE WORK (separate from the main phases)

Companions: [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) · [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) · [TESTING_AND_KNOWN_ISSUES.md](TESTING_AND_KNOWN_ISSUES.md) · [REFERENCES_AND_LITERATURE_REVIEW.md](REFERENCES_AND_LITERATURE_REVIEW.md)

**Purpose.** This document lists every *extra* idea proposed in the project conversation (13–16 Oct 2026) that is **not** one of the major contributions. The major contributions stay in the main phases: **C-core** (silent failures are invisible to default Kubernetes/Compose), **N1/N2** (conformal guard, invariants, cross-model canary, tiered degradation), **C2** (soft invariants), **C3** (silent-fault benchmark), **C1** (correctness SLO, Phase 7), **N4** (DoE/RSM + Bayesian-tuned probes), and the **operator** (Phase 8). Extras may be added after those phases are finished. Nothing here is being built now.

**Status labels:** *Implemented-local* (code exists, tested only on the laptop, not in the cluster) · *Manifest-only* (files exist, never applied/run) · *Partial* · *Not started*.
**Inclusion rule for the paper.** Extras go in a "Supporting / preliminary experiments" section or "Future work". Never claim novelty for them; cite the related work noted in each row. Every number must come from a file in `results/`.

## 1. Master list

| ID | Extra | Origin (when proposed) | Current status | What already exists | Effort to finish | Depends on |
|---|---|---|---|---|---|---|
| X01 | Model-aging forecast (Weibull survival on out-of-sample LSTM errors, `/aging`) | "AI additions" round | **Implemented-local** | `analysis/model_aging.py`, `inference-api/aging.json`, `/aging` endpoint; shapes 1.03–1.34, median 2.7–5.3 months | 0.5 day (cluster run + figure) | — | **[EXTRA STATUS: DONE (cluster: /aging, TESTING 3.13)]**
| X02 | Drift-triggered retraining loop (PSI + Page-Hinkley → retrain → shadow gate → promote/reject) | AI additions | **Implemented-local** | `inference-api/drift.py`, `retrain/loop.py`, `/drift`; tested with a 3-epoch candidate (rejected 18/18) | 1 day (real-epoch retrain, verify humidity PSI cause) | X05 | **[EXTRA STATUS: DONE (cluster; retrain not better, K34)]**
| X03 | Energy-aware tier selection (cheapest valid tier, estimated joules) | AI additions | **Implemented-local** | `ENERGY_AWARE=1`, `/energy`; about 73 % lower estimated energy | 0.5 day; real counters (Kepler/RAPL) need Linux host | — | **[EXTRA STATUS: DONE (cluster; accuracy compared in 3.16)]**
| X04 | Failure predictor, extended (LSTM autoencoder, SMOTE, real-fault traces beyond the synthetic leak/drift) | Original novelty list | **Partial** (Phase 10 done with Isolation Forest + Mahalanobis on synthetic precursors) | `analysis/failure_predictor.py`, `results/predictor_results.json` | 1 day for extensions | longer healthy data (K30) |
| X05 | Shadow-traffic model gate (mirrored requests, conformal + vote criteria, promote/reject) | N5 | **Implemented-local** | `SHADOW_LSTM_DIR` in `app.py`, `analysis/shadow_gate.py`; bad scaler rejected 3/3 | 0.5 day in cluster (good + several bad candidates, rollback by image tag) | — | **[EXTRA STATUS: DONE (cluster 24/24; final re-check 7/7)]**
| X06 | Argo Rollouts canary with a Prometheus AnalysisTemplate | Phase 5 plan | **Manifest-only** | `k8s/rollout/rollout.yaml` | 1 day (install, test) | X05 |
| X07 | Kyverno admission policy + cosign signing + Trivy scan (supply chain; tampered-model fault) | Extras 6/7 round | **Manifest-only** | `k8s/policy/kyverno-verify.yaml`, `.github/workflows/ci.yml` (never run) | 1–2 days; needs a GitHub repo with Actions | GitHub repo |
| X08 | GitHub Actions CI (tests, build, scan, sign, push) | Phase 5 plan | **Manifest-only** | `.github/workflows/ci.yml` | 0.5 day after repo exists | GitHub link |
| X09 | OpenTelemetry tracing across frontend / API / DB (recovery latency per hop) | Phase 2 plan | **Not started** | none | 1 day | — |
| X10 | Warm-up-aware predictive autoscaling (KEDA + SARIMA load forecast) vs HPA / tuned HPA | Early novelty list (secondary) | **Not started** | none; related work: PathFormer scaling paper, SARIMA PBA | 2 days | cluster |
| X11 | SARIMA vs LSTM under identical faults (load time, size, recovery) as a dedicated comparison | Early plan | **Partial** | data exists in both configs but no dedicated analysis | 0.5 day analysis | existing results | **[EXTRA STATUS: DONE (3.15 and 3.16)]**
| X12 | MTTR decomposition (detect, schedule, image pull, model load, warm-up) | Early N2 text | **Not started** | only total recovery is recorded; `model_load_seconds` gauges exist | 1 day (instrument phases) | — |
| X13 | Semantic probe wired into Kubernetes probes (D1 guard only vs D2 semantic readiness/liveness restart) | Phase 4/5 plan | **Partial** | `/health/semantic` exists but is not used by any Kubernetes probe | 0.5 day | — |
| X14 | Per-variable partial readiness (rainfall / temperature / humidity independently) | Novelty list | **Partial** | `partial_ready()` reported in `/health/ready`; never exercised | 0.5 day | — |
| X15 | Cache tier exercised and measured (last-good forecast during outage) | Tier design | **Partial** | `_CACHE` in `app.py`, never reached in experiments | 0.25 day | — |
| X16 | Adaptive / online conformal guard and exchangeability study (static vs adaptive false-alarm rates under seasonality/drift) | Web-research round | **Not started** | static window calibration + hold-out ablation | 1 day | — | **[EXTRA STATUS: DONE (3.14)]**
| X17 | Time-series foundation model (Chronos/TimesFM) as a third version | Web-research round (rank 5) | **Not started** | none; risky: correlated failure modes, heavy dependencies | 2–3 days | torch install |
| X18 | Third diverse model (XGBoost or Prophet) in the voting set | AI-additions list | **Not started** | none | 1 day | — | **[EXTRA STATUS: DONE offline (3.16)]**
| X19 | Input-side semantic guard (conformal / Isolation Forest on user inputs and uploads) | AI additions | **Not started** | none | 1 day | — | **[EXTRA STATUS: DONE (offline + UI warning; weak, K35)]**
| X20 | Adaptive tier ordering (Hedge / multiplicative weights on recent error) | AI additions | **Not started** | none | 1 day | — | **[EXTRA STATUS: DONE offline (3.16)]**
| X21 | Uncertainty bands on forecast plots (conformal intervals shown to users) | AI additions | **Not started** | none | 0.5 day | — | **[EXTRA STATUS: DONE (API field, coverage 3.16)]**
| X22 | Frontend "degraded" label and tier badge in the web UI | Tier design | **Not started** | API returns `tier`, `degraded`; UI ignores them | 0.5 day | — | **[EXTRA STATUS: DONE (verified in browser)]**
| X23 | SHAP explanations for predictor and tier decisions | AI additions | **Not started** | XAI page exists for the original models only | 1 day | X04 | **[EXTRA STATUS: DONE (permutation attribution)]**
| X24 | LLM incident summariser (operator history + metrics → plain-language report) | AI additions | **Not started** | operator keeps `status.history` | 1 day | operator |
| X25 | Granger-causality root cause across pod metrics and output quality | AI additions | **Not started** | none; overlaps SGCAD | 2 days | X04 data | **[EXTRA STATUS: DONE (screen)]**
| X26 | RL/DQN autoscaler with warm-up awareness | AI additions | **Not started** | none; crowded area | 3 days | X10 |
| X27 | Synthetic fault augmentation (SMOTE / generative) for rare failures | AI additions | **Not started** | none | 0.5 day | X04 | **[EXTRA STATUS: DONE (no SMOTE gain)]**
| X28 | Log-based anomaly detection (small transformer on service logs) | AI additions | **Not started** | none; overlaps LogBERT-lite | 2 days | — |
| X29 | Chaos Mesh / LitmusChaos re-run of the fault taxonomy (node failure, slow database, network faults) | Phase 3 plan | **Not started** | custom injector `/fault` only | 1–2 days | cluster |
| X30 | Extended failure taxonomy: node failure, slow PostgreSQL, bad rollout | Original taxonomy list | **Not started** | crash/hang/oom + 7 silent faults exist | 1 day | X29 optional |
| X31 | Model-loading strategies (lazy / eager / shared volume / warm standby) vs recovery | Early novelty list | **Not started** | per-model load times measured once | 1–2 days | X12 |
| X32 | Energy / carbon per recovery strategy | Extras list | **Partial** | estimated joules per tier only | 0.5 day | X03 | **[EXTRA STATUS: DONE (3.16)]**
| X33 | Learned recovery policy: digital twin + bandit (re-run with third action) | N3 | **Partial** (twin run; Phase 8 operator experiments in progress) | `analysis/twin_bandit.py`, `policy.json`, operator `bandit` policy | finishing with Phase 8 | Phase 8 | **[EXTRA STATUS: DONE (Phase 8)]**
| X34 | Open benchmark release package (taxonomy, scripts, traces, README, licence) | Benchmark plan | **Partial** | scripts and results exist, no packaging | 0.5 day | GitHub repo |
| X35 | Git/GitHub with Git LFS for 118 MB models + reproducibility check on a clean machine | Laptop-change discussion | **Not started** | `.gitignore`, `.gitattributes`, `RESTORE.md` | 0.5 day | GitHub link |

## 2. Suggested order after all main phases are done
1. **Cheap, high value:** X13, X15, X22, X21 (small changes, visible in the demo), X11 (analysis only).
2. **Supporting experiments for the paper:** X05 (with rollback) → X04 → X16 → X12.
3. **Packaging:** X35 → X34 → X08.
4. **Only if time remains:** X01–X03 in the cluster, X09, X10, X06/X07.
5. **Probably skip:** X17, X25, X26, X28 (high effort, crowded, or weak independence).

## 3. How to include extras in the paper
- Section "Supporting experiments (preliminary)": one paragraph and one table per extra actually run (X05, X04, X16 recommended).
- "Future work": list the remaining IDs in one paragraph.
- Do not put any extra in the contribution list. Cite: PathFormer scaling paper and SARIMA PBA (X10); TELKA, safe-remediation and ARBITER (X33); D3M and Machida N-version ML (X18, X20); LogBERT-lite (X28); SGCAD (X25); shadow-deployment practice (X05).

## 4. Caveats
- Several extras overlap published work (see REFERENCES §3); only combinations specific to ML forecasting services on Kubernetes are defensible.
- Energy figures are estimates (15 W per busy core) unless real counters are used.
- Items marked Implemented-local were exercised on the laptop only; rerun them in the cluster before reporting.
- X03 and X10 interact with the single-worker saturation issue (K25); use the threaded image (:6) or later.

## 5. Information needed
- GitHub repository link (X07, X08, X34, X35).
- Whether the paper should include a "Supporting experiments" section (target venue/page limit).
- Which 2–3 extras the user wants as the first additions after Phase 8.
