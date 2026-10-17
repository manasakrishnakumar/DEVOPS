import io
R = r'C:/Users/manas/OneDrive/Desktop/bangalore_climate_app_final/devops_project/report/'

# ---- chapter 4: data plots
c4 = io.open(R + 'c4.py', encoding='utf-8').read()
anchor = "('p', \"Calibration and evaluation of the guard respect time order"
add = '''('p', "Figure 4.1 shows the monthly series that the models are trained on, computed from the daily file: monthly rainfall total, mean temperature and mean humidity from 1951 to 2024, together with a ten-year moving mean. The strong seasonality (monsoon rainfall peak, a warm pre-monsoon period and a humid monsoon season) is what makes SARIMA with a period of twelve months appropriate, and the slow upward drift of humidity in the later decades is the cause of the drift alarms reported in Chapter 6."),
('fig', 'fig_data_series.png', 'Figure 4.1  Monthly rainfall, temperature and humidity (1951-2024) from data.csv', 6.2),
('p', "The monthly climatology in Figure 4.2 (the average of each calendar month over all years) is the third tier of the degradation chain: it is always valid by construction, it needs no model, and it is used when both models are rejected or too slow."),
('fig', 'fig_climatology.png', 'Figure 4.2  Monthly climatology used by the climatology tier', 6.2),
'''
assert anchor in c4
c4 = c4.replace(anchor, add + anchor, 1)
# renumber later figures of chapter 4 (4.1 methodology -> 4.3, 4.2 architecture -> 4.4, 4.3 tiers -> 4.5)
c4 = c4.replace("Figure 4.3  Tiered degradation", "Figure 4.5  Tiered degradation").replace("Figure 4.2  System architecture", "Figure 4.4  System architecture").replace("'Figure 4.1  Methodology of the study'", "'Figure 4.3  Methodology of the study'")
c4 = c4.replace("Figure 4.1 gives the overall flow.", "Figure 4.3 gives the overall flow.").replace("Figure 4.2 shows the deployed system", "Figure 4.4 shows the deployed system").replace("Figure 4.3 shows the request path", "Figure 4.5 shows the request path")
io.open(R + 'c4.py', 'w', encoding='utf-8').write(c4)

# ---- chapter 6: real screenshots
c6 = io.open(R + 'c6.py', encoding='utf-8').read()
i = c6.index("('h3', '6.3  Screenshots'),")
j = c6.index("('h3', '6.4  Innovative Components'),")
new = '''('h3', '6.3  Screenshots and Live Plots'),
('p', "All screenshots in this section were taken from the running system in the built-in browser on 17 October 2026, after generating real traffic against the deployed service (more than 5,700 predictions served, including an injected bit-flip fault followed by healing). They show the application pages that were served by Kubernetes from PostgreSQL-backed sessions, the live Grafana dashboard with its 5-second refresh, the Prometheus expression browser and the Jaeger trace viewer. No image in this report is a mock-up."),
('h5', '6.3.1  Application pages'),
('fig', 'shot_app_home.jpg', 'Figure 6.3  Home page of the Bangalore Climate Analytics System (browser, localhost:5000)', 5.4),
('fig', 'shot_app_dashboard.jpg', 'Figure 6.4  Climate dashboard: current values, 6-month forecast table and recent predictions', 5.4),
('fig', 'shot_app_dashboard_plots.jpg', 'Figure 6.5  Dashboard forecast plots (rainfall and temperature)', 5.4),
('fig', 'shot_app_result_plots.jpg', 'Figure 6.6  Twelve-month SARIMA forecast plots served by the inference tier', 5.4),
('fig', 'shot_app_analysis_gallery.jpg', 'Figure 6.7  Analysis gallery: distributions, anomaly z-scores, anomaly evolution and decade-wise anomalies', 5.4),
('fig', 'fig_live_forecasts.png', 'Figure 6.8  Live 12-step forecasts of SARIMA and LSTM returned by the deployed API', 6.2),
('h5', '6.3.2  Live monitoring: Grafana and Prometheus'),
('p', "Figure 6.9 shows the first panels of the live Grafana dashboard: inference p95 latency per model, inference requests per second per model, frontend request rate by status, frontend p95 latency, model load time and model-ready status. The latency of the LSTM (yellow) is visibly higher than that of SARIMA (blue), and the request-rate panel shows the traffic that was generated for this screenshot. Figure 6.10 shows the golden-output panels after the bit flip was injected; Figures 6.11 and 6.12 show the same counters directly in the Prometheus expression browser: the golden violation counter for the LSTM jumps when the fault is injected, and the per-tier valid-answer counters show that the service kept answering from the LSTM, the climatology tier and (during the fault) the fallback tiers."),
('fig', 'shot_grafana_live_top.jpg', 'Figure 6.9  Live Grafana dashboard, last 30 minutes (refresh 5 s)', 5.6),
('fig', 'shot_grafana_top.jpg', 'Figure 6.10  Grafana dashboard panels during the verification run', 5.4),
('fig', 'shot_grafana_golden.jpg', 'Figure 6.11  Golden-output integrity violations after an injected bit flip (Grafana panel)', 5.4),
('fig', 'shot_prom_golden.jpg', 'Figure 6.12  Prometheus: golden_violation_total for the LSTM backend (1 h)', 5.4),
('fig', 'shot_prom_tiers.jpg', 'Figure 6.13  Prometheus: valid answers served per tier (1 h)', 5.4),
('h5', '6.3.3  Distributed tracing'),
('p', "Figure 6.14 is the Jaeger view of one real request: the frontend handles GET /dashboard (1.81 s in total), and within the trace it calls the inference API three times (GET /predict, about 40 ms each), so the time that the user waits is dominated by the frontend work (database access and plotting) and not by the model service. Figure 6.15 is the trace search that lists traces crossing both services."),
('fig', 'shot_jaeger_trace.jpg', 'Figure 6.14  Jaeger trace of GET /dashboard with three inference calls', 5.4),
('fig', 'shot_jaeger.jpg', 'Figure 6.15  Jaeger trace search for the frontend service', 5.4),

'''
c6 = c6[:i] + new + c6[j:]
# renumber the deadline figure
c6 = c6.replace("Figure 6.7  Delay fault with and without", "Figure 6.16  Delay fault with and without")
io.open(R + 'c6.py', 'w', encoding='utf-8').write(c6)
print('patched')
