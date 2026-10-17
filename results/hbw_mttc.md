| fault | config | trials | HBW (s) mean | MTTC (s) median | wrong (%) mean |
|---|---|---|---|---|---|
| bitflip | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| bitflip | D4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| bitflip | E4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| bitflip | G4 | 10 | 0.0 | 0.0 | 0.0 |
| bitflip | H4 | 5 | 0.0 | 0.0 | 0.0 |
| bitflip_severe | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| bitflip_severe | D4 | 10 | 0.0 | 0.0 | 0.0 |
| bitflip_severe | E4 | 10 | 0.0 | 0.0 | 0.0 |
| bitflip_severe | G4 | 10 | 0.0 | 0.0 | 0.0 |
| corrupt | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| corrupt | D4 | 10 | 0.0 | 0.0 | 0.0 |
| corrupt | E4 | 10 | 0.0 | 0.0 | 0.0 |
| corrupt | G4 | 5 | 0.0 | 0.0 | 0.0 |
| corrupt | H4 | 5 | 0.0 | 0.0 | 0.0 |
| flatline | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| flatline | D4 | 10 | 30.0 | 30.0 (censored) | 99.9 |
| flatline | E4 | 10 | 0.0 | 0.0 | 0.0 |
| flatline | G4 | 5 | 0.0 | 0.0 | 0.0 |
| flatline | H4 | 5 | 0.0 | 0.0 | 0.0 |
| scaler | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| scaler | D4 | 10 | 0.0 | 0.0 | 0.0 |
| scaler | E4 | 10 | 0.0 | 0.0 | 0.0 |
| scaler | G4 | 5 | 0.0 | 0.0 | 0.0 |
| stale | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| stale | D4 | 10 | 0.0 | 0.0 | 0.0 |
| stale | E4 | 10 | 0.0 | 0.0 | 0.0 |
| stale | G4 | 5 | 0.0 | 0.0 | 0.0 |
| unitchange | C4 | 10 | 30.0 | 30.0 (censored) | 100.0 |
| unitchange | D4 | 10 | 0.0 | 0.0 | 0.0 |
| unitchange | E4 | 9 | 0.0 | 0.0 | 0.0 |
| unitchange | G4 | 5 | 0.0 | 0.0 | 0.0 |

| operator policy | trials | restored | MTTQ median (s) (censored at 150) |
|---|---|---|---|
| none | 20 | 0 | 150.0 |
| rules | 20 | 20 | 23.8 |
| bandit | 20 | 20 | 21.5 |
