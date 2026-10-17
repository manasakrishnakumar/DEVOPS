# SilentBench: silent-fault benchmark for ML forecasting services

Faults that return HTTP 200 with wrong output, injected into a Flask forecasting service (SARIMA + LSTM, Bangalore climate 1951-2024)
running on Kubernetes (Minikube). Each trial: 15 s healthy baseline, 30 s fault, 10 s after healing, 5 requests/s.

## Fault taxonomy (`/fault?mode=...`, only when FAULT_INJECTION=1)
| mode | injection | notes |
|---|---|---|
| corrupt | NaN output | |
| bitflip / bitflip_severe | flip the exponent MSB in 8 / 16 LSTM kernel weights (real weights, in memory) | 8 flips give plausible but wrong output |
| scaler | LSTM temperature scaler x0.35 | |
| stale | forecast misaligned by half the horizon | |
| unitchange | temperature reported in Fahrenheit | |
| flatline | output stuck at its first value | |
| delay | 30 % of requests +1.5 s | latency fault, not correctness |
| leak / drift / dropvar | memory leak to OOM / gradual scaler decay / one variable's model missing | used for the predictor and readiness extras |

## Response classes (`code/probe.py`, `silent_trial`)
correct (within tolerance of the healthy golden forecast), wrong (200 OK but invalid or deviating, not labelled), fallback (valid answer from another model tier),
degraded (labelled degraded tier), failed (non-200 or timeout).

## Data
`data/silentbench.jsonl`: one JSON object per trial (config C4 = guard off, D4 = conformal envelope, E4 = envelope + invariants; 10 trials per cell).
`data/silentbench_summary.csv`: per cell means. `data/silentbench_excluded.jsonl`: one trial excluded for an unhealthy pre-fault baseline.

## Reproduce
See the repository `RESTORE.md`; then `python chaos/run.py --silent --configs C4 D4 E4 --trials 10`.

## Licence
To be chosen by the authors before public release (not set here).
