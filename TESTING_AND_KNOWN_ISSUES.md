# TESTING AND KNOWN ISSUES

Companions: [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) · [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md)
Only results actually observed are listed as Passed/Failed. "NOT RUN" means no execution happened.

## 1. Environment
Windows 11 Home (10.0.26300), 12 logical CPUs, ≈15.7 GB RAM; Docker Desktop 29.8.2 (≈7.6 GB to VM); Minikube driver docker, 4 CPU / 5500 MB; host Python 3.10.6; TF 2.15.1 (host and image). Host sklearn 1.7.2 vs image 1.3.0 (pickle `InconsistentVersionWarning` seen for scalers).

## 2. Functional / unit tests
| ID | Test | Command / method | Result |
|---|---|---|---|
| T1 | Monolith pages (home, login, predict, lstm_predict, result, lstm_result, dashboard, history, analysis, xai) | Flask test client, temp SQLite | **Passed** (all 200) |
| T2 | inference-api endpoints (`/health/*`, `/predict` sarima/lstm/auto/bogus, `/metrics`) | test client | **Passed** (bogus → 503) |
| T3 | Compose stack end to end | register/login/pages via HTTP | **Passed** (all 200; user + prediction row in Postgres) |
| T4 | K8s frontend pages (`/healthz`, dashboard, analysis, xai) via port-forward | HTTP | **Passed** |
| T5 | Guard unit tests | `python -m pytest -q inference-api/tests` | **Passed** (2 tests) |
| T6 | Guard behaviour: NaN, ×3 outliers invalid; healthy SARIMA/LSTM valid | local script | **Passed** |
| T7 | Fault injectors (local, test client): corrupt→climatology, scaler→sarima, unitchange/flatline→climatology, heal restores LSTM output | local script | **Passed** (after fixing `stale` no-op; `bitflip` retuned) |
| T8 | Shadow candidate gate: healthy candidate 0 rejects (score 0.76); broken scaler 3/3 rejected (score 28) | local script | **Passed** |
| T9 | Retrain loop (3 epochs, promotion disabled) | `retrain/loop.py --max-reject -1` | **Passed as pipeline** (trigger→train→shadow→reject 18/18); candidate quality poor by design |
| T10 | Operator | – | **NOT RUN** (never deployed) |
| T11 | `chaos/doe.py`, `analysis/bo_probe.py` on real data | – | **NOT RUN** (BO smoke test on synthetic data only; output removed) |
| T12 | Kyverno, Argo Rollouts, cosign, CI workflow | – | **NOT RUN** |
| T14 | Silent benchmark pilot (C4,E4 × 3 faults × 1 trial) | `chaos/run.py --silent` | **Passed as pipeline; revealed K18–K21** |
| T15 | **Full validation suite** `validation/validate_all.py` (15 executed checks) | `python validation/validate_all.py` | **Passed 15/15** (2026-10-16 04:55; `results/validation_report.md`) |
| T16 | Silent benchmark pass 1 | `chaos/auto_phase56.ps1` | **Passed (120 rows, healthy baseline in every trial)** |
| T17 | DoE run (30 rows) | `chaos/doe.py --config C4` | **Executed**; BO output flagged (K23) |
| T18 | SLO replay (corrected) | `analysis/slo_replay.py` | **Executed** (C4 3 trials/fault, E4 2 trials/fault) - see 3.7 |
| T19 | Operator experiments (none / rules / bandit) | `chaos/run_operator.py --trials 5` | **Executed** - see 3.8 |
| T13 | Security tests (auth bypass, input validation, CSRF) | – | **NOT RUN** |

### 3.0 FINAL VERIFICATION before publishing (2026-10-16 23:20-23:58; images inference :9, frontend :3)
- **Browser walk-through** (built-in browser against the Kubernetes deployment via port-forward): register, login, dashboard, history, analysis, XAI, predict -> result, LSTM predict -> LSTM result all returned 200 with rendered plots, no tracebacks, no broken images; Grafana dashboard "Climate ML Service - Live" (12 panels) loads and a live Prometheus query returns data.
- **Novelties exercised in the browser/API:** semantic check (`/health/semantic`), tiers (corrupt / unitchange / flatline / stale -> climatology, scaler / severe bit flip -> SARIMA, subtle bit flip undetected as documented), `/slo`, `/aging`, `/drift`, `/energy`, `/shadow/status`, conformal `interval=1`, partial readiness, and the **degraded badge in the web UI** ("Forecast served in degraded mode (tier: climatology)").
- **Automated suite** `validation/validate_all.py`: **16/16 PASS** (adds V16 for phases 7-13 result data).
- **Live re-checks on the final images:** shadow gate 5/5 bad candidates rejected, 2/2 good promoted (`results/shadow_gate_final_check.jsonl`); operator rules policy on corrupt restored in 36.4 s with 6.7 % failed (single trial, `results/operator_final_check.jsonl`; earlier 5-trial median 23.4 s, 0.9 % failed).
- **Issues found and fixed during verification:** (1) frontend input-guard pickle was built with a newer scikit-learn than the image; now trained at start-up; (2) one silent-benchmark trial (E4 unitchange #8) had a 24 % timeout baseline and is excluded (kept in `results/silentbench_excluded.jsonl`); (3) an apparent `corrupt` miss in a browser script was a test artefact (two page scripts overlapping), not a service bug.

## 3. Experiments (measured)
### 3.1 Fault trials, 5 trials/cell (`results/fault_trials.jsonl`)
| Config | Fault | Recovered | Median recovery (s) | Mean failed % |
|---|---|---|---|---|
| A monolith | crash | 5/5 | 2.4 | 54.1 |
| A | hang / oom | 0/5 each | no effect (2 gunicorn workers) | – |
| B Compose | crash | 5/5 | 52.2 | 97.7 |
| B | hang | 2/5 | 183.4 | 99.8 |
| B | oom | 5/5 | 32.7 | 96.9 |
| B | corrupt | 0/5 | never | 100 |
| C Kubernetes | crash | 5/5 | 12.1 | 88.9 |
| C | hang | 5/5 | 61.8 | 97.6 |
| C | oom | 5/5 | 12.5 | 87.1 |
| C | corrupt | 0/5 | never | 100 |
| D guard (img :3) | crash | 5/5 | 14.0 | 90.6 |
| D | hang | 5/5 | 73.3 | 98.1 |
| D | oom | 5/5 | 35.8 | 95.1 |
| D | corrupt | 4/5 recovered, 1 no failed requests | 3.5 | 19.7 |

Interpretation caveats: n = 5; crash/oom partly healed by gunicorn respawning its worker; D slower on crash/hang/oom (larger image, extra start-up work).

### 3.2 Load sweeps (`results/load.jsonl`; 20 s per level)
| Config | Flow | Conc. | req/s | p50 ms | p95 ms | Errors |
|---|---|---|---|---|---|---|
| A | app (`/dashboard`) | 1/2/4/8 | 0.20/0.51/0.47/0.46 | 5534/3809/8220/15737 | 6212/4780/8821/17188 | 0 |
| B | app | 1/2/4/8 | 0.49/0.88/0.76/0.82 | 2216/2301/4753/8610 | 2766/2620/5393/10242 | 0 |
| C | app | 1/2/4/8 | 0.40/0.43/0.23/0.32 | 2759/4786/10725/17166 | 3044/5635/12666/27421 | 0/0/**746**/21 |
| B api | `/predict` | 1/2/4/8 | ≈15–17 | 48→503 | 123→753 | 0 |
| C api | `/predict` | 1/2/4/8 | ≈15–17 | 57→502 | 122→756 | 0 |

### 3.3 Offline guard ablation (`results/phase5_guard_ablation.json`)
Hold-out windows after 2018, α = 0.01, L = 6: false alarm 0.0 % (envelope and +inv). Detection: unit change 100 %, scaler 100 %, swap 100 %, NaN 100 %, hum −20 80 %, rain ×3 73 %, temp +4 °C 32 %, flatline 37 % (envelope) → 100 % (+inv). α = 0.05: false alarm 20 % / 36.7 %.

### 3.4 Other measured items
- Aging (`analysis/aging.json`, warn = 50 % of q): Weibull shape 1.03/1.29/1.34, median 5.3/2.7/4.9 months (R/T/H); rainfall error–age rank corr 0.33.
- Drift (`/drift`, deseasonalised PSI): Humidity 3.07, Rainfall 0.61, Temp 0.35; Page-Hinkley alerts all variables. Cause unverified.
- Energy (est., 15 W/core): 30 requests ≈ 1360 J (always LSTM) vs ≈ 365 J (energy-aware).
- Twin + bandit (`analysis/bandit_eval.json`, preliminary): avg cost restart-only 113.4, tier-switch 72.3, bandit 62.4, oracle 58.2.
- LSTM inference after `tf.function`: ≈ 150 ms per 12-step forecast (was ≈ 4.2 s), identical values.
- Silent benchmark (C3) **pilot** (1 trial per cell, `results/silentbench_pilot_*.jsonl`, 5 rps, 15 s warm-up, 30 s fault, 10 s heal):
  | Config | Fault | correct % | wrong % | degraded % | failed % | Note |
  |---|---|---|---|---|---|---|
  | C4 (guard off) | corrupt / unitchange / bitflip | 0 / 0 / 0 | 100 / 100 / 100 | 0 | 0 | never detected; healthy baseline 100 % correct |
  | E4 (envelope+inv) | corrupt | 0 | 0 | 100 | 0 | detected immediately, valid labelled forecasts |
  | E4 | unitchange | 0 | 0 | 53.3 | **46.7** | timeouts (see K18) — fixed afterwards |
  | E4 | bitflip (8 exponent-MSB flips) | 0 | **100** | 0 | 0 | plausible-but-wrong, inside envelope: **not detected** (honest limitation) |
  Full run (10 trials/cell) is executing via `chaos/auto_phase56.ps1`; results will be in `results/silentbench.jsonl` and `results/silentbench_summary.md`.

### 3.5 Silent-fault benchmark, pass 1 (120 trials = 3 configs x 8 faults x 5; `results/silentbench.jsonl`; 5 rps, 30 s fault window)
Share of responses in the fault window (mean of 5 trials); healthy baseline was 100 % correct in every trial.
| Fault | C4 guard off | D4 envelope | E4 envelope+invariants |
|---|---|---|---|
| corrupt (NaN output) | 100 % wrong, 0/5 detected | 100 % degraded (valid, labelled) | 100 % degraded |
| bitflip (8 exponent-MSB flips) | 100 % wrong | 100 % wrong (undetected) | 100 % wrong (undetected) |
| bitflip_severe (16) | 100 % wrong | 100 % fallback (SARIMA) | 100 % fallback |
| stale (window misaligned) | 100 % wrong | 100 % degraded | 100 % degraded |
| scaler (x0.35) | 100 % wrong | 100 % fallback | 100 % fallback |
| unitchange (C to F) | 100 % wrong | 100 % degraded | 100 % degraded |
| flatline (stuck-at) | 100 % wrong | **100 % wrong (undetected)** | 100 % degraded (detected by invariants) |
| delay (30 % requests +1.5 s) | 96.7 % failed | 97.3 % failed | 97.0 % failed (no config helps) |
Reading: the envelope alone misses flatline; invariants close that gap. Subtle bit flips evade every check. `delay` is not a correctness fault but collapses a single-worker service in all configs. Detection time is about 0 s for guarded configs (per-request check). p95 latency about 10 ms on degraded tiers vs 520-730 ms on LSTM.
Pending: pass 2 (trials 6-10), healthy soak summary (soak finished 05:28; rows with fault `none`), correctness-SLO replay (Phase 7), operator experiments (Phase 8).

### 3.5b Silent-fault benchmark, FINAL (10 trials per cell; E4 unitchange n=9 after excluding one trial with an unhealthy pre-fault baseline: 24 % timeouts, kept in `results/silentbench_excluded.jsonl`)
Dominant outcome in the fault window (30 s, 5 rps).
| Fault | C4 guard off | D4 envelope | E4 envelope+invariants |
|---|---|---|---|
| corrupt | 100.0 % wrong (n=10, detected 0/10) | 100.0 % degraded (n=10, detected 10/10) | 100.0 % degraded (n=10, detected 10/10) |
| bitflip | 100.0 % wrong (n=10, detected 0/10) | 100.0 % wrong (n=10, detected 0/10) | 100.0 % wrong (n=10, detected 0/10) |
| bitflip_severe | 100.0 % wrong (n=10, detected 0/10) | 100.0 % fallback (n=10, detected 10/10) | 100.0 % fallback (n=10, detected 10/10) |
| stale | 100.0 % wrong (n=10, detected 0/10) | 100.0 % degraded (n=10, detected 10/10) | 100.0 % degraded (n=10, detected 10/10) |
| scaler | 100.0 % wrong (n=10, detected 0/10) | 100.0 % fallback (n=10, detected 10/10) | 100.0 % fallback (n=10, detected 10/10) |
| unitchange | 100.0 % wrong (n=10, detected 0/10) | 100.0 % degraded (n=10, detected 10/10) | 100.0 % degraded (n=9, detected 9/9) |
| flatline | 100.0 % wrong (n=10, detected 0/10) | 99.9 % wrong (n=10, detected 1/10) | 100.0 % degraded (n=10, detected 10/10) |
| delay | 96.7 % failed (n=10, detected 10/10) | 97.0 % failed (n=10, detected 10/10) | 97.0 % failed (n=10, detected 10/10) |
| none | 100.0 % correct (n=1, detected 0/1) | 100.0 % correct (n=1, detected 0/1) | 100.0 % correct (n=1, detected 0/1) |

Healthy 10-minute soak (false alarms = anything other than correct): C4: correct 100.0 %, degraded 0.0 %, fallback 0.0 %, wrong 0.0 %, failed 0.0 %; D4: correct 100.0 %, degraded 0.0 %, fallback 0.0 %, wrong 0.0 %, failed 0.0 %; E4: correct 100.0 %, degraded 0.0 %, fallback 0.0 %, wrong 0.0 %, failed 0.0 %

### 3.6 DoE / RSM (`results/doe.jsonl`, 30 runs, config C4, hang fault)
Quadratic RSM leave-one-out R2: recovery 0.895, failed % 0.892. Replicas dominate: 1 replica about 52 s recovery / 97 % failed; 3 replicas about 1.3-3.3 s / 23-52 % failed (service-level view, other replicas answer). `bo_probe.py` recommended period 30 s, threshold 1, replicas 3 with predicted objective -5.56: **an extrapolation to the grid edge with a negative (impossible) value; do not report**. Observed best: period 20, threshold 5, replicas 3, objective 5.92. Only 30 of the expected 36 design runs were recorded (cause not investigated).

### 3.7 Correctness-SLO replay (Phase 7; image :6; SLO 99 %, windows 30 s and 2 m; 5 rps; fault injected at t = 0)
| Config | Fault | trials | median s to correctness alert | alerts fired | median s to degraded alert | invalid answers in 75 s window (per trial) | pod restarts |
|---|---|---|---|---|---|---|---|
| C4 | bitflip | 3 | no alert | 0/3 | no alert | [0, 0, 0] | 0 |
| C4 | corrupt | 3 | 9.2 | 3/3 | no alert | [381, 379, 382] | 0 |
| C4 | flatline | 3 | no alert | 0/3 | no alert | [0, 0, 0] | 0 |
| C4 | unitchange | 3 | 15.5 | 3/3 | no alert | [381, 376, 377] | 0 |
| E4 | bitflip | 2 | no alert | 0/2 | no alert | [0, 0] | 0 |
| E4 | corrupt | 2 | no alert | 0/2 | 17.5 | [0, 0] | 0 |
| E4 | flatline | 2 | no alert | 0/2 | 16.0 | [0, 0] | 0 |
| E4 | unitchange | 2 | no alert | 0/2 | 19.2 | [0, 0] | 0 |

Reading: with the guard off (C4) the correctness SLO is breached and the burn-rate alert fires within about 5-20 s for corrupt and unitchange; flatline and bitflip are not flagged because the post-hoc checker in GUARD_MODE=envelope cannot see them (flatline is caught by invariants; subtle bit flips by nothing). With the guard on (E4) served answers stay valid (few or no invalid answers) and the degraded-serving alert is the signal instead. Sample is small (C4: 3 trials, E4: 2 trials) because the run was cut short at the user deadline.

### 3.8 Phase 8: operator experiments (config E4, image :6, no heal, 150 s window, 5 rps)
restored_s = seconds from fault injection until 5 consecutive correct full-quality (LSTM-tier) answers.
| Policy | Fault | trials | restored | median restored s | correct % | degraded % | wrong % | failed % |
|---|---|---|---|---|---|---|---|---|
| none | corrupt | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |
| none | flatline | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |
| none | scaler | 5 | 0/5 | never | 0.0 | 0.0 | 0.0 | 0.0 |
| none | unitchange | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |
| rules | corrupt | 5 | 5/5 | 23.4 | 84.1 | 15.0 | 0.0 | 0.9 |
| rules | flatline | 5 | 5/5 | 20.4 | 86.9 | 12.8 | 0.0 | 0.3 |
| rules | scaler | 5 | 5/5 | 24.2 | 85.4 | 0.0 | 0.0 | 0.3 |
| rules | unitchange | 5 | 5/5 | 25.6 | 83.5 | 16.2 | 0.0 | 0.4 |
| bandit | corrupt | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |
| bandit | flatline | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |
| bandit | scaler | 5 | 5/5 | 20.0 | 86.6 | 0.0 | 0.0 | 0.4 |
| bandit | unitchange | 5 | 0/5 | never | 0.0 | 100.0 | 0.0 | 0.0 |

### 3.9 Twin + bandit re-run with the third action `switch_then_restart` (`analysis/bandit_eval.json`, `analysis/policy.json`)
Average cost per episode: {'bandit': 37.69, 'oracle': 25.86, 'always_restart_only': 270.0, 'always_switch_then_restart': 25.85, 'always_tier_switch': 151.48}; best action per fault: {'corrupt': 'switch_then_restart'}.
Policy table (expected cost per action): {"unreachable": {"restart_only": 40.7, "tier_switch": 59.3}, "timeout": {"restart_only": 91.1, "tier_switch": 106.5}, "invalid:lstm,sarima": {"restart_only": 270.0, "tier_switch": 198.9, "switch_then_restart": 24.7}, "invalid:lstm": {"tier_switch": 240.0, "switch_then_restart": 23.2}}



### 3.10 Phase 9: validation of tuned probe settings (hang fault, config C4, held-out runs)
| Setting (period s / threshold / replicas) | trials | recovered | median recovery s | mean failed % | p vs default (Mann-Whitney, recovery) |
|---|---|---|---|---|---|
| default 10/3/1 | 5 | 5/5 | 66.3 | 97.5 |  |
| control_default_3rep 10/3/3 | 5 | 5/5 | 1.7 | 24.5 | 0.008 |
| recommended_1rep 7/5/1 | 5 | 5/5 | 73.0 | 98.0 | 0.012 |
| recommended 7/5/3 | 5 | 5/5 | 1.7 | 25.2 | 0.012 |
| observed_best 20/5/3 | 5 | 5/5 | 1.7 | 20.8 | 0.012 |

### 3.11 Phase 10: failure predictor (Isolation Forest on telemetry vs baselines)
Healthy false alarms: 1 in 4.1 min (2.45 per 10 min) for Isolation Forest; Mahalanobis: 1 alarms.
| Scenario | trials with failure | method | alarmed before failure | median lead s |
|---|---|---|---|---|
| leak | 6/6 | Isolation Forest | 6/6 | 69.6 |
| leak | 6/6 | Mahalanobis (healthy distribution) | 6/6 | 69.6 |
| leak | 6/6 | static memory threshold 80 % | 6/6 | 23.9 |
| leak | 6/6 | reactive guard (score > 1) | 0/6 | None |
| drift | 6/6 | Isolation Forest | 6/6 | 23.7 |
| drift | 6/6 | Mahalanobis (healthy distribution) | 6/6 | 23.7 |
| drift | 6/6 | static memory threshold 80 % | 0/6 | None |
| drift | 6/6 | reactive guard (score > 1) | 0/6 | None |

### 3.12 Phase 11: in-cluster shadow-gate (image :8, config E4, mirrored 5 rps, gate: reject ratio <= 5 %, >= 20 samples)
| Candidate | expected | trials | decisions | median reject ratio | median score | median s to decision |
|---|---|---|---|---|---|---|
| good_copy | promote | 3 | {'promote': 3} | 0.00 | 0.64 | 12.9 |
| good_noise | promote | 3 | {'promote': 3} | 0.00 | 0.62 | 12.6 |
| bad_scaler | reject | 3 | {'reject': 3} | 1.00 | 8.64 | 8.2 |
| bad_swap | reject | 3 | {'reject': 3} | 1.00 | 10.21 | 8.2 |
| bad_bitflip | reject | 3 | {'reject': 3} | 1.00 | 2.03 | 8.8 |
| bad_nan | reject | 3 | {'reject': 3} | 1.00 | 3015040392.87 | 9.1 |
| bad_undertrained | reject | 3 | {'reject': 3} | 1.00 | 7.23 | 9.0 |
| retrain_40ep | None | 3 | {'promote': 3} | 0.00 | 0.67 | 14.5 |

Bad candidates caught (rejected): 15/15; good candidates wrongly rejected: 0/6. Argo Rollouts, Kyverno, cosign and CI were NOT run (manifests only; see EXTRAS X06-X08).

### 3.13 Phase 12 in the cluster: aging, drift, energy-aware serving, retraining
/aging: model_age_months=78, retrain_after_months=2.7, retrain_recommended=True. /drift: PSI={'Humidity': 3.0651, 'Rainfall': 0.6111, 'Temp_mean': 0.3521}, psi_alert=True, ph_alert=True.
| ENERGY_AWARE | requests | est. J/request | CPU s/request | tier counts | p95 ms | correct % |
|---|---|---|---|---|---|---|
| 0 | 788.0 | 3.994 | 0.2663 | {'lstm': 788.0} | 214.0 | 100.0 |
| 1 | 788.0 | 0.93 | 0.062 | {'sarima': 788.0} | 101.0 | 100.0 |

Hold-out RMSE 2019-2024 (one-step ahead): {"production_lstm": {"Rainfall": 90.451, "Temp_mean": 1.141, "Humidity": 2.476}, "retrain_40ep": {"Rainfall": 90.301, "Temp_mean": 1.161, "Humidity": 2.857}, "bad_undertrained_3ep": {"Rainfall": 106.23, "Temp_mean": 2.12, "Humidity": 5.196}}
Joules are estimates (CPU-seconds x 15 W), not hardware counters.

### 3.14 Phase 13a: static vs rolling vs adaptive conformal guard (offline, hold-out windows from 2019, alpha 0.01, 6-month windows)
| Strategy | false-alarm rate | unit_change_F | scaler_x0.35_temp | rain_x3_plus30 | shift_temp_+4C | shift_hum_-20 | swap_temp_hum |
|---|---|---|---|---|---|---|---|
| static | 0.000 | 1.00 | 1.00 | 0.73 | 0.62 | 1.00 | 1.00 |
| rolling_20y | 0.000 | 1.00 | 1.00 | 0.73 | 0.50 | 0.93 | 1.00 |
| aci | 0.000 | 1.00 | 1.00 | 0.73 | 0.62 | 1.00 | 1.00 |

### 3.15 Phase 13b: model family under identical faults (guard off, image :8, 5 trials per cell)
| Family | start-up s | model load s (sum) | RSS MB | fault | recovered | median recovery s | mean failed % |
|---|---|---|---|---|---|---|---|
| sarima | 0.602 | 0.3493 | 537.0 | crash | 5/5 | 6.8 | 76.5 |
| sarima | 0.602 | 0.3493 | 537.0 | oom | 5/5 | 11.2 | 71.3 |
| sarima | 0.602 | 0.3493 | 537.0 | hang | 0/5 | never | - |
| lstm | 5.17 | 4.9153 | 540.0 | crash | 5/5 | 12.8 | 92.8 |
| lstm | 5.17 | 4.9153 | 540.0 | oom | 5/5 | 19.6 | 85.0 |
| lstm | 5.17 | 4.9153 | 540.0 | hang | 0/5 | never | - |
| both | 6.178 | 5.6482 | 905.3 | crash | 5/5 | 16.2 | 93.2 |
| both | 6.178 | 5.6482 | 905.3 | oom | 5/5 | 17.3 | 85.5 |
| both | 6.178 | 5.6482 | 905.3 | hang | 3/5 | 18.1 | 7.4 |

Not run in Phases 11-13 (moved to extras): Argo Rollouts, Kyverno, cosign, GitHub Actions CI (X06-X08); KEDA warm-up-aware scaling (X10).

### 3.16 Extras batch 1 (offline; `analysis/extras_offline1.py`, `analysis/predictor_extras.py`; `results/extras_offline1.json`, `results/predictor_extras.json`)
- **X11/X32 accuracy vs energy (Jan-Jun 2024 RMSE):** SARIMA rain 47.389 / temp 0.779 / hum 0.972; LSTM 71.316 / 1.22 / 1.774; climatology 64.993 / 1.258 / 2.033. SARIMA is both more accurate and about 4x cheaper (0.93 vs 3.994 J/request, estimated): no accuracy-energy trade-off on this window (resolves K33 for this window only; 6 test months).
- **X20 Hedge tier ordering (one-step stream 2019-2024, 66 months):** cumulative loss {'lstm': 33.538, 'climatology': 28.786, 'persistence': 48.265, 'hedge': 30.247, 'uniform': 36.863}; final weights {'lstm': 0.009, 'climatology': 0.991, 'persistence': 0.0}. Climatology beat the LSTM out of sample; Hedge tracked the best expert.
- **X19 input guard (Isolation Forest + conformal threshold):** hold-out false alarm 0.061 (target 0.01), detection {'rain_x5': 0.576, 'temp_in_F': 0.394, 'humidity_gt_100': 0.409, 'negative_rain': 0.0, 'all_zero': 1.0}. Weak: use hard range rules as well; it only warns in the UI.
- **X21 conformal 90 % intervals for the LSTM:** half-widths {'Rainfall': [92.31, 94.17, 93.72, 93.05, 94.05, 89.38], 'Temp_mean': [1.52, 1.53, 1.53, 1.52, 1.52, 1.51], 'Humidity': [3.1, 3.18, 3.17, 3.18, 3.21, 3.17]}; held-out coverage 2019-2024 {'Rainfall': [0.75, 0.75, 0.75, 0.75, 0.75, 0.717], 'Temp_mean': [0.85, 0.85, 0.833, 0.833, 0.833, 0.883], 'Humidity': [0.817, 0.8, 0.8, 0.783, 0.8, 0.833]} (under-covers because of drift).
- **X18 third model (gradient boosting):** RMSE {'Rainfall': 65.282, 'Temp_mean': 1.036, 'Humidity': 1.462}; vote disagreement of a faulty LSTM (threshold 1.0): {'3_members|healthy': 0.077, '3_members|scaler_x0.35': 2.589, '3_members|subtle_bias_+1.2C': 0.138, '4_members|healthy': 0.172, '4_members|scaler_x0.35': 2.702, '4_members|subtle_bias_+1.2C': 0.227}. The extra member flags the large scaler fault but not a subtle +1.2 C bias.
- **X04 LSTM autoencoder:** leak early 6/6 (median lead 69.6 s), drift early 6/6 (median lead 23.7 s) but 79 alarm samples on healthy data (unusable false alarms).
- **X27 supervised classifier (leave-one-run-out F1):** plain 0.972, class-weight 0.96, SMOTE 0.961: SMOTE gives no gain here.
- **X23 attribution:** latency and CPU-rate features contribute most to the anomaly score (permutation attribution; SHAP not used). **X25 Granger screen:** CPU rate Granger-causes latency in 3/6 runs for both scenarios, other features rarely.
- Not yet run: cluster extras (X09, X12-X15, X30, X31), X10 scaling, X06 Argo, X17 foundation model; blocked: X07, X08, X35 (registry / CI), skipped: X26, X28, X29. See EXTRAS_AND_FUTURE_WORK.md.

### 3.17 Extras in the cluster (image :9 / frontend :3; `results/extras_cluster.jsonl`)
**X13 semantic probes wired into Kubernetes (no heal, 140 s):**
| Probe variant | Fault | trials | restored | median restored s | correct % | degraded % | failed % |
|---|---|---|---|---|---|---|---|
| D1_default | corrupt | 3 | 0/3 | never | 0.0 | 100.0 | 0.0 |
| D1_default | unitchange | 3 | 0/3 | never | 0.0 | 100.0 | 0.0 |
| D3_semantic_readiness | corrupt | 3 | 0/3 | never | 0.0 | 8.1 | 91.9 |
| D3_semantic_readiness | unitchange | 3 | 0/3 | never | 0.0 | 8.5 | 91.5 |
| D2_semantic_readiness_and_liveness | corrupt | 3 | 3/3 | 36.2 | 73.9 | 7.6 | 18.5 |
| D2_semantic_readiness_and_liveness | unitchange | 3 | 3/3 | 36.6 | 74.8 | 7.8 | 17.4 |

**X14 partial readiness (LSTM model for one variable lost, 60 s):**
| Readiness | trials | correct % | fallback % | degraded % | failed % |
|---|---|---|---|---|---|
| strict | 3 | 0.0 | 19.3 | 0.0 | 80.7 |
| partial | 3 | 0.0 | 100.0 | 0.0 | 0.0 |

**X15 cache tier (climatology disabled, all models faulty), 3 trials:** degraded (cache) 100.0 %, wrong 0.0 %, failed 0.0 %, correct 0.0 %.

**X31 eager vs lazy LSTM loading (3 restarts each):**
| Mode | median time to ready s | median first LSTM request s | median second request s |
|---|---|---|---|
| eager | 11.2 | 2.6 | 0.5 |
| lazy | 7.0 | 10.0 | 0.4 |

**X12 MTTR decomposition (crash, 5 trials, medians):** client_detect_s=0.1, container_restart_delay_s=28.0, ready_delay_after_start_s=6.0, app_startup_s=4.6, client_recovery_s=34.6

**X30 database faults seen from the web app (/history polled every 0.5 s):**
| Fault | trials | median failed % | median outage s | median recovered s |
|---|---|---|---|---|
| db_lock_30s | 3 | 4.3 | 19.6 | 20.1 |
| db_restart | 3 | 0.8 | 0.0 | 0.6 |

**X09 per-hop latency attribution (hop timing via histograms, not OpenTelemetry):**
| Scenario | page requests | avg request s | avg inference call s | avg DB s | other (rendering) s |
|---|---|---|---|---|---|
| healthy | 35 | 1.151 | 0.085 | 0.012 | 1.053 |
| inference_delay | 19 | 2.131 | 1.145 | 0.012 | 0.974 |

**X22 / X19 web UI checks:** degraded_badge_visible=True; unusual_input_warning_visible=True; normal_input_no_warning=True

**X10 bursty load (4 rps -> 24 rps for 70 s -> 4 rps; SARIMA endpoint; guard off):**
| Mode | trials | burst p95 ms (median) | burst failed % (median) | tail p95 ms | ready replicas at end |
|---|---|---|---|---|---|
| fixed_1_replica | 3 | 6658 | 67.0 | 2349 | ['1', '1', ''] |
| reactive_hpa | 3 | 4028 | 93.4 | 4748 | ['3', '3', '3'] |
| proactive_prescale | 3 | 5827 | 91.8 | 4458 | ['3', '3', '2'] |
Proactive pre-scaling here uses a known schedule as the "forecast" (not a learned forecaster); KEDA was not used.

**X17 foundation model (Chronos-T5-tiny, zero-shot):** {"rmse_Jan_Jun_2024": {"chronos": {"Rainfall": 69.917, "Temp_mean": 1.203, "Humidity": 1.784}, "sarima": {"Rainfall": 60.774, "Temp_mean": 0.779, "Humidity": 0.972}, "lstm": {"Rainfall": 71.316, "Temp_mean": 1.22, "Humidity": 1.774}}, "error_correlation_per_variable": {"chronos~sarima": [1.0, 0.97, 0.48], "chronos~lstm": [0.98, 0.58, 0.89], "sarima~lstm": [0.99, 0.65, 0.67]}, "vote_lstm_disagreement": {"3_members|healthy": 0.077, "3_members|scaler_x0.35": 2.589, "3_members|subtle_+1.2C": 0.138, "4_members_with_chronos|healthy": 0.136, "4_members_with_chronos|scaler_x0.35": 2.643, "4_members_with_chronos|subtle_+1.2C": 0.208}}

Not attempted: X06 Argo Rollouts (needs controller install and a candidate-bearing image per revision), X07/X08 (registry, Actions), X26, X28, X29 (see EXTRAS_AND_FUTURE_WORK.md).

## 4. Known issues (reproducible where possible)
| # | Issue | Evidence / reproduce | Root cause (established?) | Status |
|---|---|---|---|---|
| K1 | Docker Desktop stops mid-batch | batch died twice; `docker info` fails | sleep / sign-out (suspected from timeline) | mitigated with keep-awake; recurring risk |
| K2 | Config D first run invalid | pods `ErrImageNeverPull` | image build failed silently; script ignored errors | **fixed** (checks + pod image verification) |
| K3 | Crash-loop with per-request vote | pod logs "Handling signal: term" after liveness timeouts | single worker saturated by LSTM+SARIMA per request | **fixed** (canary + envelope-only per request) |
| K4 | Config A hang/oom "no effect" | `fault_trials.jsonl` | 2 workers mask one blocked worker | open (rerun with 1 worker or state) |
| K5 | D slower than C for crash/hang/oom | table 3.1 | larger image / extra start-up (lazy drift already applied) | open, not analysed |
| K6 | Corrupt fault leaves service degraded | D tiers = climatology until heal | no automatic restore (operator not deployed) | open |
| K7 | C app flow errors at concurrency 4–8 (746 errors) | `load.jsonl` | dashboard page ≈ 3–10 s/request, frontend 2 workers saturated; not investigated | open |
| K8 | Cross-variable invariants uninformative | `analysis/mine_invariants.py` | bands > 1 std; recent-period hold-rates 0.82–0.96 | accepted; reported |
| K9 | Window-level FA at α = 0.05 too high | ablation | non-exchangeability/drift | α kept at 0.01 |
| K10 | Humidity PSI 3.07 unexplained | `/drift` | unverified (correlations stable) | open |
| K11 | SARIMA/LSTM start months differ (Jan vs Jul 2024) | `app.py` start_month | original app convention | handled by calendar alignment; keep in paper |
| K40 | Subtle bit flips evaded envelope, invariants and cross-model vote | silentbench C4/D4/E4 | corrupted output stays plausible | **fixed** by golden-output check (3.18), 20/20 caught |
| K41 | Bandit policy never restarted (5/20 restored) | operator_trials v1 | cost omitted time below full quality; policy table stale | **fixed** (3.18), 20/20 restored |
| K12 | bit flips mostly masked in LSTM | local sweep | network robustness | informative; benchmark uses exponent-MSB flips |
| K13 | Energy numbers are estimates | – | no RAPL/Kepler in containers | open |
| K14 | Probe tolerances arbitrary | `probe.py::TOL` | chosen heuristically | justify or calibrate before paper |
| K15 | Unit-test coverage minimal | only 2 tests | – | open |
| K16 | Windows tooling: heredoc/quoting failures, console cp1252 (emoji in `train_lstm_model` print) | seen repeatedly | shell/console encoding | workaround: write files with editor tool; `python -X utf8` |
| K18 | E4 unitchange: 46.7 % failed requests in pilot | `silentbench_pilot_*.jsonl` | guard re-ran both models and rejected both on every request (no memory), single worker could not sustain 5 rps (about 0.3 s per request); canary did not flag finite out-of-envelope tiers | fixed: per-request circuit breaker (`_SUSPECT[tier]=True`) + canary flags `score>1`; **re-measurement pending in full run** |
| K19 | Runner routed C4/D4/E4 probes through Docker Compose (wait on missing network, 10+ min stall) | stalled pilot | `run_probe` only recognised configs C and D | fixed (`K8S_CFGS`) |
| K20 | Negative `detect_s` in pilot | E4 rows (−0.15, −0.3) | fault timestamp taken after injection call | fixed (stamp before injection) |
| K21 | bit-flip (`bitflip`) is undetectable by envelope/vote at 8 flips | E4 pilot 100 % wrong | in-envelope plausible output | open: report as benchmark finding; consider output-vs-input checks |
| K22 | `delay` fault collapses all configs (about 97 % failed) | pass 1 table | lock / single worker serialises slow requests; no per-request timeout or hedging | open (add timeout + circuit breaker for latency) |
| K23 | (FIXED, validation pending) BO recommendation was an RSM extrapolation (negative objective) | `results/bo_probe.log` | quadratic surface unconstrained at grid edge | bounded to the experimental region and objective clipped at 0: new recommendation period 7 s, threshold 5, replicas 3 (predicted objective 3.24 vs observed best 5.92 at 20/5/3); NOT yet validated by a held-out run vs defaults 10/3/1 |
| K24 | Envelope-only guard (D4) does not detect flatline | pass 1 D4 flatline 100 % wrong | no variance / stuck-at statistic in the envelope | mitigated by invariants (E4) |
| K25 | Inference pods restarted repeatedly during the Phase 7 replay; counters reset (negative deltas) | `results/slo_replay_invalid_*.jsonl`; pod events "Liveness probe failed: context deadline exceeded" | single sync gunicorn worker saturated by load + health polling, so `/health/live` (1 s timeout) timed out and kubelet restarted the pod | fixed: gunicorn `--worker-class gthread --threads 4` (image :6); earlier benchmark rows (image :4, 1 sync worker) were not affected in outcome but keep this caveat |
| K26 | SLO replay alert times stale/None although 383/385 answers were invalid | same file | Prometheus `evaluation_interval` = 1 m, so recording rules (30 s windows) refresh only each minute | fixed: replay queries burn expressions directly; evaluation interval set to 5 s; rows kept as `*_invalid_*` |
| K27 | Operator logs "Not enough permissions to list/watch namespaces" (kopf falls back to namespace `climate`) | `kubectl -n climate logs deploy/forecast-operator` | Role is namespaced; kopf also tries cluster-scoped reads | open; **operator never exercised end to end** (Phase 8 experiments NOT RUN) |
| K28 | Tuned probe period/threshold do NOT help; replicas do | `results/probe_validation.jsonl`, TESTING 3.10 | recommended probes at 1 replica (7/5/1): 73.0 s vs default 66.3 s (p = 0.012, slower); default probes at 3 replicas: 1.7 s (p = 0.008). The DoE gain was the replica effect | **N4 (probe tuning) is not supported**; report replicas as the factor, probe settings as a negative/neutral result |
| K29 | Leak failure marker used failed scrapes; none occurred because the respawned worker answered within one scrape | `results/telemetry/leak_*.csv` (RSS 964 -> 2642 MB, then reset) | analysis definition error | fixed: failure = request-counter reset or RSS collapse; predictor re-run offline on the same recordings |
| K30 | Predictor healthy false alarms: 1 in 4.1 min (2.45 per 10 min) for both detectors | `results/predictor_results.json` | only two 8-minute healthy recordings (calibration half 4 min); thresholds at the 99.5th percentile | open: collect longer healthy data, raise threshold or require more consecutive scrapes |
| K31 | Phase 10 faults are synthetic precursors (injected leak, scripted linear drift); lead times are not field evidence | collector / app.py | by design | state in the paper |
| K32 | Phase 13b `hang` rows ("0/5 recovered", "never", mean failed "-") are NOT comparable with Phase 3 hang rows | `results/model_family.jsonl`, outcome `no_effect` | image :8 serves with `gthread` (4 threads): one hung request blocks a single thread, other threads keep answering, so no request fails; Phase 3 used one synchronous worker | caveat: compare crash/oom across families only; rerun hang with sync worker if needed |
| K33 | Energy-aware mode served only SARIMA (788/788); the accuracy cost of never using LSTM was not measured | `results/phase12.json` | cheapest-first ordering plus audit that also resolves to SARIMA | open: add accuracy/RMSE column before claiming an energy-accuracy trade-off |
| K34 | Retraining is recommended by `/aging` and `/drift`, but the 40-epoch retrain is not better on 2019-2024 (RMSE rain 90.3 vs 90.5, temp 1.16 vs 1.14, humidity 2.86 vs 2.48) although the shadow gate promotes it | `results/phase12.json`, TESTING 3.12/3.13 | gate checks validity/agreement, not accuracy improvement | open: add an accuracy criterion to the gate |
| K35 | Input guard flags ordinary conditions as unusual (default test input 100 mm / 26 C / 70 % was flagged); hold-out false alarm 6 % | browser check, `results/extras_offline1.json` | monthly-triple Isolation Forest ignores season and has a loose threshold | open: warning only; add hard range rules |
| K36 | LSTM autoencoder raises many alarms on healthy telemetry (79 samples) | `results/predictor_extras.json` | threshold calibrated on a 4-minute healthy half | open |
| K37 | **(withdrawn: root cause was 4 gunicorn threads, see 3.20; repeat on image :12)** Bursty-load scaling comparison is inconclusive/negative: with the LSTM endpoint (3 -> 20 rps) 1 replica failed 52-85 %, reactive HPA 93-94 %, proactive pre-scaling 89-94 % | `results/extras_scaling.jsonl` | single 4-CPU Minikube node: extra TensorFlow pods and the load generator compete for the same CPU, so scaling out cannot add capacity; an earlier lighter SARIMA burst showed no failures in any mode (`results/extras_scaling_light_burst_superseded.jsonl`) | open: needs a multi-node cluster or lower per-pod CPU use; do not claim an autoscaling benefit |
| K38 | Earlier UI check "degraded badge not visible" and "normal input not warned" were test artefacts: the MTTR experiment left the guard off; the check ran right after heal | `results/extras_cluster_superseded_e8.jsonl` | script ordering/timing | fixed (guard restored at end of e5; wait after heal); final UI checks all True |
| K39 | Crash recovery on Kubernetes is dominated by the container restart delay (28 s of 34.6 s total) | TESTING 3.17 (X12) | kubelet restart back-off, not application start-up (4.6 s) | informative; a finding for the paper |
| K17 | No git repo; models 118 MB × 6 copies | folder listing | – | LFS plan in `RESTORE.md`; GitHub link pending |

## 5. Regression risks
Changing `guard.py` thresholds invalidates `phase5_guard_ablation.json`; changing `probe.py` tolerances invalidates silent-bench comparisons; rebuilding images under an existing tag requires `rollout restart`; `inference-api/utils/lstm_model.py` differs from `monolith/utils/lstm_model.py` (tf.function change) — keep outputs identical; frontend `utils` copies are not auto-synced.

## 6. Final acceptance criteria (proposed)
1. ≥ 10 trials per cell for all benchmark faults × 3 configs with CIs.
2. Live healthy soak ≥ 10 min per config, false-alarm % reported.
3. Correctness SLO alert fires within bounded time for each fault; no false page in soak.
4. DoE (≥ 30 runs) with validated RSM; tuned probes beat defaults on held-out runs.
5. Operator restores full tier after corrupt (measured).
6. All claims in the paper map to rows in `results/`.

## 8. ADDENDUM (updated 2026-10-17)
- Test inventory: unit tests = 2 (`inference-api/tests/test_guard.py`, passed); validation suite = 17 executed checks (V01-V17; 16/16 PASS at 2026-10-16 23:38, 17/17 PASS at 2026-10-17 09:56 after the cluster extras, `results/validation_report.md`); browser verification (TESTING 3.0); live re-checks of operator and shadow gate on images :9/:3; no automated frontend, security or load-limit tests beyond the experiments.
- Known issues are K1-K39 in section 4; K25-K28 and K32-K34 changed conclusions (restarts from a saturated worker, stale rule timings, replicas vs probes, hang comparability, energy accuracy, retraining gate).
- Result files and where each table comes from: `results/fault_trials.jsonl` (3.1), `load.jsonl` (3.2), `phase5_guard_ablation.json` (3.3), `silentbench*.jsonl/csv` (3.5, 3.5b), `doe.jsonl` + `probe_validation.jsonl` (3.6, 3.10), `slo_replay.jsonl` (3.7), `operator_trials.jsonl` (3.8), `predictor_results.json` + `telemetry/` (3.11), `shadow_gate_cluster.jsonl` (3.12), `phase12.json` (3.13), `phase13_adaptive_conformal.json` (3.14), `model_family.jsonl` (3.15), `extras_offline1.json` + `predictor_extras.json` (3.16), `extras_cluster.jsonl`, `extras_scaling.jsonl`, `extras_chronos.json` (3.17).
- Invalid or superseded data kept for the record: `fault_trials_D_invalid_*.jsonl`, `slo_replay_invalid_*.jsonl`, `operator_trials_invalid_*.jsonl`, `invalid_*.json*`, `silentbench_pilot_*.jsonl`, `silentbench_excluded.jsonl`.

### 3.18 Fix round 2026-10-17 (image :10, config G4; `results/silentbench.jsonl`, `results/operator_trials*.jsonl`)
1. **Golden-output integrity check (fixes the subtle-bit-flip gap, K40).** At start-up each tier's 24-step forecast is stored while the model is known healthy. The canary and the per-request path reject a tier whose forecast deviates from it by more than 0.002 history-std (models are deterministic; healthy deviation is 0.0). `GOLDEN_CHECK=1`, endpoint `/golden/refresh` after a validated model promotion. Config **G4 = E4 + golden check**.
   - Subtle bit flip (8 flips): envelope score 0.605 (inside the envelope, old guard blind) but golden deviation 1.195 -> tier marked invalid, requests fall back to SARIMA.
   - Silent benchmark G4 (10 trials bitflip, 10 bitflip_severe, 5 each other): **wrong answers 0 % in all faults** (bitflip/bitflip_severe/scaler: 100 % valid fallback; corrupt/flatline/unitchange/stale: 100 % degraded-valid); healthy control 5/5 trials 100 % correct (no false alarm). Previously bitflip was 100 % wrong for C4/D4/E4.
   - Limit: the check detects *change* of a deterministic model, not a model that was already wrong at start-up; it needs a trusted start-up/promotion moment, and the stored reference makes legitimate retraining require `/golden/refresh` (after the shadow gate).
2. **Bandit fixed at the root (K41).** Two causes: (a) the cost ignored that `tier_switch` leaves the service on a fallback tier forever (so it looked cheapest, 60 vs 270); (b) the deployed policy table had been built before the operator rows existed (no `switch_then_restart` entry). Cost now adds `W_Q=0.5` per second below full quality (240 s horizon when never restored). New table: invalid signatures -> `switch_then_restart` (36.5 / 34.7) vs `tier_switch` (319 / 360). Re-run 20 trials (image :5, config E4): **bandit restored 20/20 in 18.8-26.4 s** (before: 5/20, only scaler). Old rows kept in `results/operator_trials_bandit_v1_superseded.jsonl`. Honest note: with only restart available in the action set the learned policy converges to the same action as the rules policy; its value is that it *learns* this from data and would choose differently where restart is costly (crash: restart_only 48 vs tier_switch 75).
3. **Argo Rollouts (X06) run.** Controller v1.7.2 installed; canary (50 % -> analysis gate -> 100 %) with Prometheus AnalysisTemplates: revision 2 with the real shadow-reject gate promoted (Healthy, AnalysisRun Successful); revision 3 with a deliberately failing gate aborted ("RolloutAborted", AnalysisRun Failed). This proves the mechanism; it does not itself prove detection of bad models (that is the shadow gate, 3.12). `k8s/rollout/rollout-test.yaml`, `results/argo_analysisruns.txt`.
4. **Reframed (not fixed):** probe tuning shows no benefit (replicas dominate recovery, 3 replicas ~1.7 s vs 66 s) - report as a negative result; scaling test inconclusive on a single CPU-bound node (K37) - report as a limitation, needs multi-node.
5. Security review written: `SECURITY_REVIEW.md` (10 findings). Kyverno/cosign/CI files exist but were never run (need GitHub/registry).
6. Dashboard: panels 13-14 (golden violations / rejects). Validation suite: **18/18 PASS** (V18 = this round).

### 3.19 Extras round 2 and Phase 14 (2026-10-17; `results/extras_keda.jsonl`, `extras_chaosmesh.jsonl`, `extras_log_anomaly.json`, `extras_rl_autoscaler.json`, `phase14_stats.json`, `phase14_tables.md`, `results/figures/`)
- **Kyverno + cosign (X07):** Kyverno 1.x admission controller; validate policy (`k8s/policy/kyverno-validate.yaml`) rejected `nginx:latest`, `nginx:1.25`, accepted `climate-inference:10`. Signature verification (`kyverno-verify-tested.yaml`, public key `cosign.pub`): image pushed to a local registry (:5050), signed with cosign (key pair, no transparency log): signed image admitted; same tag re-pushed with a different image -> cosign "no signatures found"; unsigned `:tampered` tag denied at admission. Not verified: keyless signing, Trivy and the GitHub Actions workflow (`ci.yml`) - they only run on GitHub; the repository is private/unreadable from here, so check the Actions tab yourself.
- **OpenTelemetry (X09):** optional tracing (env `OTEL_EXPORTER_OTLP_ENDPOINT`) in frontend (image :4) and inference (image :11) with Jaeger all-in-one (`k8s/jaeger.yaml`). Verified: trace "GET /dashboard" (frontend 1506 ms) contains child "GET /predict" (inference-api 30 ms); 3 of 8 traces span both services. Operational lesson: `kubectl set image '*=...'` also replaced the init-container image and stalled the rollout (fixed by naming containers).
- **KEDA (X10, reactive Prometheus trigger):** scaled to 2 / 1 / 3 replicas but burst failures stayed 76 % / n/a (burst pod failed) / 65 % - same CPU-bound limit as K37; no benefit claimed.
- **Chaos Mesh (X29):** PodChaos pod-kill: ready again after 16.1 / 16.3 / 16.2 s (the inference pod's own start-up; faster than the 34.6 s container-crash case because the pod is rescheduled and the image is cached); NetworkChaos 300 ms delay: p50 39 -> 646 ms, 0 failures, back to 42 ms after removal. Note: helm needs `MSYS_NO_PATHCONV=1` on Git-Bash and `runtime=containerd` on this Minikube.
- **Log anomaly (X28):** 0 log templates (service emits no per-request log lines), 0 % detection of all six silent faults, 0 % healthy false alarms: a negative result - logs carry no signal here, the semantic check does.
- **RL autoscaler (X26, simulation only):** tabular Q-learning vs fixed-1 / fixed-3 / reactive on 200 held-out bursty traces: drops 17.0 / 5.2 / 4.2 / **2.4 %** but mean reward -240 / -170 / **-110** / -121 (reactive best on reward; RL lowest drops, uses more replicas). Not validated on the cluster.
- **Phase 14 (statistics):** bootstrap 95 % CIs and exact tests in `results/phase14_tables.md`; silent benchmark C4 vs G4 Fisher p = 3.3e-4 (n=10 vs 5) and 1.1e-5 for bit flips (10 vs 10); operator: none 0/20, rules 20/20 (23.6 s [22.3, 24.9]), bandit 20/20 (21.6 s [20.6, 22.6]); rules vs none Fisher p = 1.5e-11; rules vs bandit Mann-Whitney p = 0.041 (a ~2 s drift, same action, not a policy effect). Figures: `fig_silent_wrong_pct.png`, `fig_operator_restore.png`.

### 3.20 Novelty 6: deadline- and load-aware degradation (image :12, config H4 = G4 + `DEADLINE_MS=800`, tier concurrency caps LSTM 2 / SARIMA 3; `results/silentbench.jsonl`, `results/extras_deadline.jsonl`)
Mechanism: each request has a time budget; a tier is run in a worker pool and abandoned (`shed_total{tier,reason=timeout|deadline|load}`) if it cannot answer in time or its queue is full, and the tier chain falls through to the next cheaper tier (graceful degradation for *slow* answers, not only wrong ones). Gunicorn threads raised 4 -> 16 so shed requests are served at once.
- **Delay fault** (30 % of calls sleep 1.5 s, 10 trials each): G4 failed **96.8 %** of requests (p95 2008 ms); H4 failed **0 %**, 94.0 % served as valid degraded answers (climatology), p95 762 ms. Wrong answers 0 in both. Honest note: most requests end on climatology because the backend lock is shared; per-tier locks could keep more requests on SARIMA (future work).
- **LSTM burst** (3 -> 20 -> 3 rps, 1 replica, 3 trials): no failures in either config on image :12, but burst p95 G4 504 / 1283 / 867 ms vs H4 185 / 282 / 207 ms (about 4x lower).
- **Regression** (5 trials each, H4): healthy 100 % correct; corrupt/flatline 100 % degraded-valid; bit flip 100 % valid fallback; 0 % wrong everywhere.
- **Root-cause correction of K37:** the earlier burst failures (52-94 %) were measured with 4 gunicorn threads. With 16 threads the same burst fails 0 %, so the failures were mostly thread-pool queueing, not a CPU limit. The scaling comparison (HPA / pre-scaling / KEDA) must be repeated on image :12 with a heavier burst before any conclusion; until then K37 is **withdrawn as evidence either way**.
- Operational: the cluster became overloaded by the extra stacks (Kyverno, KEDA, Chaos Mesh, Argo) plus the lab: startup probes timed out and pods restarted; they were uninstalled after their experiments (results kept; install commands in TESTING 3.17-3.19). Dashboard panel 15 shows shed requests. Validation V19 added (19 checks).
