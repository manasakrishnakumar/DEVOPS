"""Phase 9 validation: do the DoE/RSM/BO-recommended probe settings really beat the defaults on fresh runs?
Settings compared (liveness period s, failureThreshold, replicas), hang fault, config C4 (image :4, guard off):
  default 10/3/1, recommended (analysis/bo_result.json), observed_best (best DoE run)
Appends to results/probe_validation.jsonl.   python chaos/validate_probe.py --trials 5
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doe  # noqa: E402
import run  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument('--trials', type=int, default=5)
a = ap.parse_args()
bo = json.load(open(os.path.join(ROOT, 'analysis', 'bo_result.json')))
rec, best = bo['recommended'], bo['observed_best']
settings = {'default': (10, 3, 1),
            'recommended': (int(rec['period']), int(rec['threshold']), int(rec['replicas'])),
            'observed_best': tuple(int(x) for x in best)}
print('settings', settings, flush=True)
run.switch_to('C4')
out = os.path.join(run.RES, 'probe_validation.jsonl')
for name, (pe, th, rp) in settings.items():
    doe.apply(pe, th, rp)
    for t in range(a.trials):
        res = run.run_probe('C4', ['--mode', 'fault', '--base', 'http://inference-api:5001', '--probe-path',
                                   '/predict?model=sarima&steps=3', '--fault', 'hang', '--timeout', '300'])
        for r in res:
            r.update(setting=name, period=pe, threshold=th, replicas=rp, trial=t + 1)
            with open(out, 'a') as f:
                f.write(json.dumps(r) + '\n')
            print(name, t + 1, r.get('recovery_s'), r.get('failed_pct'), flush=True)
        run.reset('C4')
doe.apply(10, 3, 1)
