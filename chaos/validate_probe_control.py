"""Phase 9 controls: separate the effect of replicas from the effect of probe period/threshold.
  control_default_3rep : 10 s / 3 / 3 replicas   (default probes, tuned replicas)
  recommended_1rep     : 7 s / 5 / 1 replica     (tuned probes, default replicas)
Appends to results/probe_validation.jsonl (same file as validate_probe.py).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doe  # noqa: E402
import run  # noqa: E402

settings = {'control_default_3rep': (10, 3, 3), 'recommended_1rep': (7, 5, 1)}
run.switch_to('C4')
out = os.path.join(run.RES, 'probe_validation.jsonl')
for name, (pe, th, rp) in settings.items():
    doe.apply(pe, th, rp)
    for t in range(5):
        res = run.run_probe('C4', ['--mode', 'fault', '--base', 'http://inference-api:5001', '--probe-path',
                                   '/predict?model=sarima&steps=3', '--fault', 'hang', '--timeout', '300'])
        for r in res:
            r.update(setting=name, period=pe, threshold=th, replicas=rp, trial=t + 1)
            with open(out, 'a') as f:
                f.write(json.dumps(r) + '\n')
            print(name, t + 1, r.get('recovery_s'), r.get('failed_pct'), flush=True)
        run.reset('C4')
doe.apply(10, 3, 1)
