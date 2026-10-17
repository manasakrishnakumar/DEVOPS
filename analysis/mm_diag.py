import os, sys, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'inference-api')); os.chdir(os.path.join(ROOT, 'inference-api'))
os.environ.update({'SEMANTIC_GUARD': '0', 'FAULT_INJECTION': '1'})
import app as A, metamorphic as M
B = A.BACKENDS['lstm']; SD = {v: float(np.std(A.SERIES[v])) for v in M.VARS}
years = A.monthly['Year'].values.astype(int); N = len(years)
fn = lambda s, k: A._apply_output_fault(B.forecast(s, k))
P = M.MetamorphicProbe()
for label, ends in (('cal<=2018', range(40, N - 6, 25)), ('hold>2018', [e for e in range(36, N - 6, 4) if years[e - 1] > 2018])):
    r1 = {v: [] for v in M.VARS}; r2 = []
    for e in ends:
        st = M.window_stats(fn, A.SERIES, e, SD)
        for v in M.VARS:
            r1[v].append(M.profile_distance(P.cfg['band'][v], st[v][0]) / P.cfg['band'][v]['q'])
        r2.append(max(st[v][1] for v in M.VARS) / P.cfg['q2'])
    print(label, 'n', len(r2), 'profile max/p90', {v: (round(max(r1[v]), 2), round(float(np.percentile(r1[v], 90)), 2)) for v in M.VARS}, 'recursive max', round(max(r2), 2), flush=True)
