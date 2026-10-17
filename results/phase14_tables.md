## Silent benchmark: wrong-answer share (%), mean [95 % bootstrap CI], n trials

| fault | C4 | D4 | E4 | G4 | Fisher C4 vs G4 (p) |
|---|---|---|---|---|---|
| corrupt | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=5 | 0.00033 |
| unitchange | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=9 | 0.0 [0.0, 0.0] n=5 | 0.00033 |
| flatline | 100.0 [100.0, 100.0] n=10 | 99.93 [99.79, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=5 | 0.00033 |
| scaler | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=5 | 0.00033 |
| stale | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=5 | 0.00033 |
| bitflip | 100.0 [100.0, 100.0] n=10 | 100.0 [100.0, 100.0] n=10 | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 1.1e-05 |
| bitflip_severe | 100.0 [100.0, 100.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 1.1e-05 |
| delay | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 0.0 [0.0, 0.0] n=10 | 1 |

## Operator policies: time to full quality (s) and restore rate

| policy | restored | mean [95 % CI] s |
|---|---|---|
| none | 0/20 | never |
| rules | 20/20 | 23.59 [22.23, 24.92] |
| bandit | 20/20 | 21.56 [20.62, 22.54] |

Rules vs bandit restore time: Mann-Whitney p = 0.041 (bandit ~2 s faster, small; both use the same action so this is run-to-run drift, not a policy effect).
Rules vs none (restored 20/20 vs 0/20): Fisher exact p = 1.5e-11.

## New extras (summary)

- KEDA: peak replicas [2, 1, 3]; burst failed % [76.4, 64.5] (single CPU-bound node, no benefit; K37).
- Chaos Mesh: pod-kill ready after [16.1, 16.3, 16.2] s; 300 ms network delay raised p50 from 39 to 646 ms, no failures.
- Log anomaly: templates=0, detection {'unitchange': 0.0, 'bitflip': 0.0, 'flatline': 0.0, 'corrupt': 0.0, 'stale': 0.0, 'scaler': 0.0} (service emits no per-request logs; negative result).
- RL autoscaler (simulation): {"fixed1": {"mean_reward": -240.41, "mean_drop_pct": 17.03}, "fixed3": {"mean_reward": -170.31, "mean_drop_pct": 5.19}, "reactive": {"mean_reward": -110.34, "mean_drop_pct": 4.2}, "q": {"mean_reward": -121.04, "mean_drop_pct": 2.41}}
