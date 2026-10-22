## Table X.1  Bit-flip fuzzing of the real LSTM weights (12600 trials, 300 per cell)

| bit class | trials | wrong answer % [95 % CI] | loud failure (HTTP 500) % | wrong, missed by envelope % | wrong, missed by golden % | golden alarm on harmless change % |
|---|---|---|---|---|---|---|
| sign | 2100 | 0.5 [0.3, 0.9] | 0.0 | 0.3 | 0.0 | 75.2 |
| exp_msb | 2100 | 50.2 [48.1, 52.3] | 0.4 | 15.5 | 0.0 | 49.2 |
| exp_other | 2100 | 0.3 [0.1, 0.6] | 0.0 | 0.2 | 0.0 | 72.5 |
| mant_high | 2100 | 0.0 [0.0, 0.2] | 0.0 | 0.0 | 0.0 | 28.0 |
| mant_low | 2100 | 0.0 [0.0, 0.2] | 0.0 | 0.0 | 0.0 | 0.0 |
| any | 2100 | 4.9 [4.0, 5.9] | 0.0 | 3.0 | 0.0 | 50.5 |

## Table X.2  Same study by number of flipped bits (all bit classes)

| flips | trials | wrong answer % | wrong, missed by envelope % | detection of wrong answers: envelope % | detection of wrong answers: golden % |
|---|---|---|---|---|---|
| 1 | 1800 | 1.5 | 0.9 | 37.0 | 100.0 |
| 2 | 1800 | 3.1 | 2.5 | 19.6 | 100.0 |
| 4 | 1800 | 5.8 | 2.8 | 51.0 | 100.0 |
| 8 | 1800 | 8.7 | 3.9 | 54.8 | 100.0 |
| 16 | 1800 | 12.6 | 4.7 | 62.8 | 100.0 |
| 32 | 1800 | 15.2 | 3.9 | 74.4 | 100.0 |
| 64 | 1800 | 18.3 | 3.4 | 81.2 | 100.0 |

## Table X.5  Golden-output check: detection of wrong answers vs alarms on harmless changes, by tolerance (history-std units; default 0.002; largest deviation of the unmodified models 0.0000)

| tolerance | wrong answers detected % | alarms on harmless changes % |
|---|---|---|
| 0.002 | 100.0 (1172/1172) | 50.7 (5784/11419) |
| 0.005 | 100.0 (1172/1172) | 42.6 (4869/11419) |
| 0.01 | 100.0 (1172/1172) | 36.2 (4138/11419) |
| 0.02 | 100.0 (1172/1172) | 30.3 (3465/11419) |
| 0.05 | 100.0 (1172/1172) | 21.3 (2431/11419) |
| 0.1 | 100.0 (1172/1172) | 13.9 (1582/11419) |
| 0.2 | 100.0 (1172/1172) | 8.6 (979/11419) |
| 0.5 | 97.9 (1147/1172) | 3.3 (382/11419) |
| 1.0 | 84.3 (988/1172) | 1.0 (117/11419) |
| 2.0 | 58.4 (684/1172) | 0.1 (6/11419) |

## Table X.6  Bit-flip fuzzing: host process vs a pod of the production image (300 vs 100 trials per cell)

| bit class | host: trials | host: wrong % | pod: trials | pod: wrong % | pod: wrong, missed by envelope | pod: wrong, missed by golden |
|---|---|---|---|---|---|---|
| sign | 2100 | 0.5 | 700 | 0.4 | 3 | 0 |
| exp_msb | 2100 | 50.2 | 700 | 49.3 | 112 | 0 |
| exp_other | 2100 | 0.3 | 700 | 0.4 | 2 | 0 |
| mant_high | 2100 | 0.0 | 700 | 0.0 | 0 | 0 |
| mant_low | 2100 | 0.0 | 700 | 0.0 | 0 | 0 |
| any | 2100 | 4.9 | 700 | 4.3 | 20 | 0 |
| all | 12600 | 9.3 | 4200 | 9.1 | 137 | 0 |

## Table X.3  Signed golden outputs vs the start-up reference (30 s window, 5 requests per second)

| condition | trials | wrong % | fallback (valid) % | correct % | failed % (transport resets) | semantic health | reference source | new pod Ready |
|---|---|---|---|---|---|---|---|---|
| healthy, signed reference | 20 | 0.0 | 0.0 | 99.9 | 0.1 | OK 20, not OK 0, no reply 0 | signed | yes |
| corrupt at start-up, start-up reference | 20 | 99.9 | 0.0 | 0.0 | 0.1 | OK 20, not OK 0, no reply 0 | startup | yes |
| corrupt at start-up, signed reference | 20 | 0.0 | 99.9 | 0.0 | 0.1 | OK 0, not OK 20, no reply 0 | signed | yes |
| golden.json tampered after signing | 10 | 0.0 | 0.0 | 100.0 (served by the old pod) | 0.0 | n/a | n/a | never Ready in 10/10 |
| model file differs from signed hash | 10 | 0.0 | 0.0 | 100.0 (served by the old pod) | 0.0 | n/a | n/a | never Ready in 10/10 |

## Table X.4  Recovery of two fault classes under four operator policies

| fault | policy | trials | restored | median time to full quality (s) | mean failed % | actions taken (typical) |
|---|---|---|---|---|---|---|
| transient | rules | 5 | 5/5 | 31.2 | 0.6 | restart |
| transient | release_aware | 5 | 5/5 | 29.4 | 0.3 | restart |
| transient | escalate | 5 | 5/5 | 30.2 | 0.6 | restart |
| bad_release | none | 3 | 0/3 | never | 0.3 | none |
| bad_release | rules | 5 | 0/5 | never | 2.2 | restart -> restart -> restart -> restart -> restart -> restart |
| bad_release | release_aware | 5 | 5/5 | 45.8 | 0.4 | rollback |
| bad_release | escalate | 5 | 5/5 | 77.4 | 0.6 | restart -> rollback |
