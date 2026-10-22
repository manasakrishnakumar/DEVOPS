# Live browser check of every page

Generated 2026-10-22 23:39:03  |  46/48 pages OK

| Page | HTTP | Result | Title | Console errors | Failed requests | Screenshot |
|---|---|---|---|---|---|---|
| A home | 200 | OK | Bangalore Climate Analytics System | 2 | 0 | A01_home.png |
| A register form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A02_register.png |
| A login form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A03_login.png |
| A dashboard | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A04_dashboard.png |
| A predict form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A05_predict_form.png |
| A result (extreme rain) | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A06_result_extreme.png |
| A result (drought) | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A07_result_drought.png |
| A analysis | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A08_analysis.png |
| A xai | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A09_xai.png |
| A history | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | A10_history.png |
| A /api/forecast | 200 | OK |  | 0 | 0 |  |
| A /api/baseline | 500 | **FAIL** | TypeError: Object of type DataFrame is not JSON serializable // Werkzeug Debugge | 1 | 0 |  |
| B home | 200 | OK | Bangalore Climate Analytics System | 2 | 0 | B01_home.png |
| B register form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B02_register.png |
| B login form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B03_login.png |
| B dashboard | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B04_dashboard.png |
| B predict form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B05_predict_form.png |
| B result (extreme rain) | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B06_result_extreme.png |
| B result (drought) | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B07_result_drought.png |
| B analysis | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B08_analysis.png |
| B xai | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B09_xai.png |
| B history | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B10_history.png |
| B /api/forecast | 200 | OK |  | 0 | 0 |  |
| B /api/baseline | 500 | **FAIL** | Bangalore Climate Analytics System | 2 | 0 |  |
| B healthz | 200 | OK |  | 0 | 0 |  |
| B metrics | 200 | OK |  | 0 | 0 |  |
| B lstm_predict form | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B11_lstm_predict_form.png |
| B lstm_result | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B12_lstm_result.png |
| API /health/live | 200 | OK |  | 1 | 0 |  |
| API /health/ready | 200 | OK |  | 0 | 0 | C01_ready.png |
| API /health/semantic | 200 | OK |  | 0 | 0 | C02_semantic.png |
| API /golden/info | 200 | OK |  | 0 | 0 | C03_golden_info.png |
| API /predict?model=auto&steps=6 | 200 | OK |  | 0 | 0 | C04_predict.png |
| API /slo | 200 | OK |  | 0 | 0 | C05_slo.png |
| API /drift | 200 | OK |  | 0 | 0 | C06_drift.png |
| API /aging | 200 | OK |  | 0 | 0 | C07_aging.png |
| API /energy | 200 | OK |  | 0 | 0 | C08_energy.png |
| API /baseline | 200 | OK |  | 0 | 0 |  |
| API /shadow/status | 200 | OK |  | 0 | 0 |  |
| API /metrics | 200 | OK |  | 0 | 0 |  |
| API semantic health while corrupted (503 = correct) | 503 | OK |  | 1 | 0 | C09_semantic_corrupted.png |
| B dashboard while degraded | 200 | OK | Bangalore Climate Analytics System | 1 | 0 | B14_dashboard_degraded.png |
| API semantic health after heal | 200 | OK |  | 0 | 0 | C10_semantic_healed.png |
| Grafana climate dashboard | 200 | OK | Climate ML Service - Live - Dashboards - Grafana | 1 | 0 | D01_grafana.png |
| Prometheus up | 200 | OK | Prometheus Time Series Collection and Processing Server | 0 | 0 | E01_prometheus.png |
| Prometheus golden_violation_total | 200 | OK | Prometheus Time Series Collection and Processing Server | 0 | 0 | E02_prometheus.png |
| Prometheus sum by (tier) (predict_tier_total) | 200 | OK | Prometheus Time Series Collection and Processing Server | 0 | 0 | E03_prometheus.png |
| Prometheus golden_signature_valid | 200 | OK | Prometheus Time Series Collection and Processing Server | 0 | 0 | E04_prometheus.png |