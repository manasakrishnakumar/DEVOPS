# Validation report

Generated 2026-10-17 12:30:14  |  18/18 checks PASS

| Check | Result | Evidence | Seconds |
|---|---|---|---|
| V01 docker + kubectl available | **PASS** | 29.8.2 / {   "clientVersion": {     "major": "1",     "minor": "36",  | 0 |
| V02 cluster pods Running | **PASS** | 3 pods Running | 0 |
| V03 images present in minikube | **PASS** | climate-inference:4 and climate-frontend:2 present in minikube | 1 |
| V04 all python files compile | **PASS** | 81 python files compile | 10 |
| V05 unit tests (pytest) | **PASS** | 2 passed in 0.66s | 2 |
| V06 data and model files | **PASS** | daily rows=26835, sarima MB={'sarima_rainfall.pkl': 124, 'sarima_temp_mean.pkl': 124, 'sarima_humidity.pkl': 124}, 3 lstm .h5 present | 1 |
| V07 service, baseline mode (real models) | **PASS** | rain[0] sarima=5.0 lstm=87.295; metrics exposed | 16 |
| V08 service, guard on: faults detected + heal (real models) | **PASS** | detected -> tiers {'corrupt': 'climatology', 'unitchange': 'climatology', 'flatline': 'climatology', 'scaler': 'sarima'}; heal restores lstm identical output | 26 |
| V09 guard ablation reproduces stored numbers | **PASS** | hold-out false alarm 0.0; detection unit=1.0 flatline=1.0 | 3 |
| V10 cluster readiness + semantic health | **PASS** | ready=True; semantic_ok=True | 1 |
| V11 cluster fault cycle corrupt/heal (in pod) | **PASS** | guard=True: corrupt -> tier=climatology degraded=True; healed tier=lstm | 9 |
| V12 frontend flows through Kubernetes + PostgreSQL | **PASS** | pages {'healthz': 200, 'dashboard': 200, 'result': 200, 'lstm_result': 200, 'history': 200, 'analysis': 200}; user persisted in PostgreSQL | 14 |
| V13 Prometheus metrics + Grafana health | **PASS** | prometheus series=6 ; grafana ok | 10 |
| V14 baseline experiment data integrity | **PASS** | 75 fault rows in 15 cells (5 each); 20 load rows | 0 |
| V15 silent-benchmark data integrity | **PASS** | 292 rows, 35 cells; baseline healthy, class percentages sum to 100 | 0 |
| V17 cluster extras results (semantic probes, partial readiness, UI, scaling, Chronos) | **PASS** | extras rows=49; UI checks all True; chronos status=ok; scaling rows=9 | 0 |
| V18 fix round: golden check + cost-aware bandit | **PASS** | G4 bitflip rows=20 (0 wrong), healthy rows=5 (100% correct); bandit v2 restored 20/20 | 0 |
| V16 phases 7-13 result data (operator, probe validation, predictor, shadow gate, family) | **PASS** | operator rows=60 (rules restored 20/20) ; probe_validation rows=25 ; predictor: 6/6 leak and 6/6 drift failures analysed ; shadow gate: 15/15 bad rejected, 6/6 good promoted ; phase12/13 result files present | 0 |
