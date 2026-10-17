import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import json, os
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
C = {'a': '#dbeafe', 'b': '#dcfce7', 'c': '#fef3c7', 'd': '#fee2e2', 'e': '#ede9fe'}


def box(ax, x, y, w, h, t, c='a', fs=8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02', fc=C[c], ec='#334155', lw=1))
    ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle='->', color='#334155', lw=1.2))


# 1 architecture
fig, ax = plt.subplots(figsize=(9, 5.2)); ax.axis('off'); ax.set_xlim(0, 10); ax.set_ylim(0, 6)
box(ax, 0.2, 4.6, 1.8, 0.9, 'Browser\n(user)', 'e')
box(ax, 2.6, 4.6, 2.2, 0.9, 'Frontend (Flask)\ninput guard, UI, history', 'a')
box(ax, 2.6, 3.0, 2.2, 0.9, 'PostgreSQL\n(users, history)', 'c')
box(ax, 5.4, 4.2, 4.2, 1.5, 'Inference API (Flask + gunicorn)\nguard | golden check | tiers | deadline\nSARIMA, LSTM, climatology, cache', 'b')
box(ax, 5.4, 2.2, 1.9, 0.9, 'Forecast operator\n(kopf, CRD)', 'd')
box(ax, 7.7, 2.2, 1.9, 0.9, 'Failure predictor\n+ shadow gate', 'd')
box(ax, 0.2, 0.4, 2.4, 1.0, 'Prometheus\n(scrape 5 s, SLO rules)', 'c')
box(ax, 3.0, 0.4, 2.0, 1.0, 'Grafana\n15 live panels', 'c')
box(ax, 5.4, 0.4, 2.0, 1.0, 'Jaeger\n(OpenTelemetry)', 'c')
box(ax, 7.8, 0.4, 1.8, 1.0, 'Chaos / probe\nexperiment drivers', 'e')
for a in [(2.0, 5.05, 2.6, 5.05), (4.8, 5.05, 5.4, 5.0), (3.7, 4.6, 3.7, 3.9), (6.3, 3.1, 6.3, 4.2), (8.6, 3.1, 8.0, 4.2), (1.4, 1.4, 5.6, 4.3), (4.0, 1.4, 4.0, 1.4)]:
    arrow(ax, *a)
ax.text(5, 5.9, 'Kubernetes (Minikube) - namespace climate / monitoring', ha='center', fontsize=9, style='italic')
fig.savefig(os.path.join(A, 'fig_architecture.png'), dpi=160, bbox_inches='tight'); plt.close(fig)

# 2 guard + tier chain
fig, ax = plt.subplots(figsize=(9, 3.6)); ax.axis('off'); ax.set_xlim(0, 12); ax.set_ylim(0, 4)
box(ax, 0.1, 1.5, 1.4, 1.0, 'Request\n/predict', 'e')
for i, (t, c) in enumerate([('1. LSTM\nforecast', 'a'), ('2. SARIMA\nforecast', 'a'), ('3. Climatology\n(month mean)', 'c'), ('4. Cache\n(last valid)', 'c')]):
    box(ax, 2.0 + i * 2.5, 2.6, 1.8, 1.0, t, c)
    box(ax, 2.0 + i * 2.5, 0.4, 1.8, 1.6, 'Guard checks:\nenvelope, invariants,\ngolden output,\ndeadline / queue', 'd', 7)
    arrow(ax, 2.9 + i * 2.5, 2.6, 2.9 + i * 2.5, 2.0)
    if i < 3:
        arrow(ax, 3.8 + i * 2.5, 3.1, 4.5 + i * 2.5, 3.1)
        ax.text(4.15 + i * 2.5, 3.3, 'reject', fontsize=7, ha='center')
arrow(ax, 1.5, 2.0, 2.0, 3.0)
ax.text(6, 3.9, 'Tiered degradation: first tier that passes every check answers', ha='center', fontsize=9, style='italic')
fig.savefig(os.path.join(A, 'fig_tiers.png'), dpi=160, bbox_inches='tight'); plt.close(fig)

# 3 methodology
fig, ax = plt.subplots(figsize=(9, 2.8)); ax.axis('off'); ax.set_xlim(0, 12); ax.set_ylim(0, 3)
steps = ['Baselines\nA monolith\nB Compose\nC Kubernetes', 'Silent-fault\nbenchmark\n8 faults x 4 configs', 'Guard design\nenvelope, invariants,\ncanary, golden', 'Recovery\noperator, SLO,\nprobes, DoE', 'Prediction &\ndelivery\nshadow gate', 'Statistics\nCIs, Fisher,\nMann-Whitney']
for i, s in enumerate(steps):
    box(ax, 0.1 + i * 1.95, 0.7, 1.7, 1.6, s, ['e', 'd', 'b', 'a', 'c', 'e'][i])
    if i < 5:
        arrow(ax, 1.8 + i * 1.95, 1.5, 2.05 + i * 1.95, 1.5)
fig.savefig(os.path.join(A, 'fig_methodology.png'), dpi=160, bbox_inches='tight'); plt.close(fig)

# 4 deadline comparison
sb = [json.loads(l) for l in open(os.path.join(A, '..', '..', 'results', 'silentbench.jsonl'))]
fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
g = [r['fault_window'] for r in sb if r['config'] == 'G4' and r['fault'] == 'delay']
h = [r['fault_window'] for r in sb if r['config'] == 'H4' and r['fault'] == 'delay']
m = lambda L, k: sum(x[k] for x in L) / len(L)
ax[0].bar(['G4 (no deadline)', 'H4 (deadline)'], [m(g, 'failed_pct'), m(h, 'failed_pct')], color=['#ef4444', '#22c55e'])
ax[0].set_ylabel('failed requests (%)'); ax[0].set_title('Delay fault: failed requests')
ax[1].bar(['G4', 'H4'], [m(g, 'p95_ms'), m(h, 'p95_ms')], color=['#ef4444', '#22c55e'])
ax[1].set_ylabel('p95 latency (ms)'); ax[1].set_title('Delay fault: p95 latency')
fig.tight_layout(); fig.savefig(os.path.join(A, 'fig_deadline.png'), dpi=160); plt.close(fig)
print('figs ok')
