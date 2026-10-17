"""Figures made from the real data file and the running service (no synthetic numbers)."""
import json
import os
import shutil
import urllib.request

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, 'assets')
ROOT = os.path.dirname(HERE)
TR = r'C:/Users/manas/.claude/projects/C--Users-manas-OneDrive-Desktop-bangalore-climate-app-final/61e8e464-9aa0-422e-bf4f-46976b50aeba/tool-results/'
SHOTS = {'shot_app_dashboard.jpg': 'mcp-Claude_Browser-blob-1792243803429-n2neup.jpg',
         'shot_app_dashboard_plots.jpg': 'mcp-Claude_Browser-blob-1792243825229-8jkvns.jpg',
         'shot_app_result_plots.jpg': 'mcp-Claude_Browser-blob-1792243851136-ccbuh8.jpg',
         'shot_app_analysis_gallery.jpg': 'mcp-Claude_Browser-blob-1792243894055-4mjlnt.jpg',
         'shot_grafana_live_top.jpg': 'mcp-Claude_Browser-blob-1792244015396-a1evfb.jpg',
         'shot_prom_golden.jpg': 'mcp-Claude_Browser-blob-1792243951232-q55m2c.jpg',
         'shot_prom_tiers.jpg': 'mcp-Claude_Browser-blob-1792243951233-fpfgk1.jpg',
         'shot_jaeger_trace.jpg': 'mcp-Claude_Browser-blob-1792243951231-gcorjj.jpg'}
for k, v in SHOTS.items():
    shutil.copy(TR + v, os.path.join(A, k))

df = pd.read_csv(os.path.join(ROOT, 'frontend', 'data.csv'), parse_dates=['Date'])
df['Rain'] = pd.to_numeric(df['Rain'], errors='coerce')
df['Temp'] = (df['Temp Max'] + df['Temp Min'].clip(upper=40)) / 2
m = df.set_index('Date').resample('MS').agg({'Rain': 'sum', 'Temp': 'mean', 'Humidity': 'mean'})
fig, ax = plt.subplots(3, 1, figsize=(9, 6.2), sharex=True)
for a, (col, lab, c) in zip(ax, (('Rain', 'Rainfall (mm / month)', '#2563eb'), ('Temp', 'Mean temperature (deg C)', '#ea580c'), ('Humidity', 'Humidity (%)', '#16a34a'))):
    a.plot(m.index, m[col], color=c, lw=0.7)
    a.plot(m.index, m[col].rolling(120, min_periods=12).mean(), color='black', lw=1.4, label='10-year moving mean')
    a.set_ylabel(lab, fontsize=8)
    a.legend(loc='upper left', fontsize=7)
ax[-1].set_xlabel('Year')
ax[0].set_title('Monthly series derived from data.csv (1951-2024)')
fig.tight_layout()
fig.savefig(os.path.join(A, 'fig_data_series.png'), dpi=150)
plt.close(fig)

clim = m.groupby(m.index.month).mean()
fig, ax = plt.subplots(1, 3, figsize=(9, 2.9))
for a, (col, lab, c) in zip(ax, (('Rain', 'Rainfall (mm)', '#2563eb'), ('Temp', 'Temperature (deg C)', '#ea580c'), ('Humidity', 'Humidity (%)', '#16a34a'))):
    a.bar(clim.index, clim[col], color=c)
    a.set_title(lab, fontsize=9)
    a.set_xlabel('Month', fontsize=8)
fig.suptitle('Monthly climatology (the "climatology" tier of the degradation chain)', fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(A, 'fig_climatology.png'), dpi=150)
plt.close(fig)


def get(url):
    return json.loads(urllib.request.urlopen(url, timeout=60).read().decode())


try:
    s = get('http://localhost:5001/predict?model=sarima&steps=12&interval=1')
    l = get('http://localhost:5001/predict?model=lstm&steps=12')
    fig, ax = plt.subplots(1, 3, figsize=(9.5, 3.0))
    for a, (v, lab) in zip(ax, (('Rainfall', 'Rainfall (mm)'), ('Temp_mean', 'Temperature (deg C)'), ('Humidity', 'Humidity (%)'))):
        a.plot(range(1, 13), s[v], 'o-', label='SARIMA (step 1 = Jan 2024)', color='#2563eb')
        a.plot(range(1, 13), l[v], 's--', label='LSTM (step 1 = Jul 2024)', color='#dc2626')
        a.set_title(lab, fontsize=9)
        a.set_xlabel('forecast step (month)', fontsize=8)
    ax[0].legend(fontsize=6)
    fig.suptitle('Live 12-step forecasts returned by the deployed inference API (tier: %s / %s)' % (s.get('tier'), l.get('tier')), fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(A, 'fig_live_forecasts.png'), dpi=150)
    plt.close(fig)
    print('live forecasts ok')
except Exception as e:
    print('live forecast failed', e)
print('ok')
