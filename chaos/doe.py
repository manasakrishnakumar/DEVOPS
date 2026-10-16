"""DoE runner (Phase 7): central composite design over probe settings, 'hang' fault on config C/D.

Factors (coded -1/0/+1):  liveness periodSeconds {5,10,20}, failureThreshold {1,3,5}, replicas {1,2,3}.
Responses: recovery_s, failed_pct (probe.py output). Appends to results/doe.jsonl.
  python chaos/doe.py --config C --repeats 2
"""
import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402

LEVELS = {'period': [5, 10, 20], 'threshold': [1, 3, 5], 'replicas': [1, 2, 3]}


def design():
    try:
        from pyDOE2 import ccdesign
        d = ccdesign(3, center=(2, 2), face='ccf')
        pts = {tuple(int(round(x)) for x in row) for row in d}
    except Exception:
        pts = set(itertools.product([-1, 0, 1], repeat=3))
    return sorted(pts)


def apply(period, threshold, replicas):
    patch = json.dumps([{'op': 'replace', 'path': '/spec/template/spec/containers/0/livenessProbe/periodSeconds',
                         'value': period},
                        {'op': 'replace', 'path': '/spec/template/spec/containers/0/livenessProbe/failureThreshold',
                         'value': threshold}])
    run.kube('-n', run.KNS, 'patch', 'deploy/inference-api', '--type=json', '-p', patch)
    run.kube('-n', run.KNS, 'scale', 'deploy/inference-api', f'--replicas={replicas}')
    run.kube('-n', run.KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=400s')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', default='C', choices=['C', 'D', 'C4', 'D4', 'E4'])
    p.add_argument('--repeats', type=int, default=2)
    a = p.parse_args()
    run.switch_to(a.config)
    out = os.path.join(run.RES, 'doe.jsonl')
    for coded in design():
        pe, th, rp = (LEVELS[k][c + 1] for k, c in zip(('period', 'threshold', 'replicas'), coded))
        apply(pe, th, rp)
        for rep in range(a.repeats):
            res = run.run_probe(a.config, ['--mode', 'fault', '--base', 'http://inference-api:5001',
                                           '--probe-path', '/predict?model=sarima&steps=3', '--fault', 'hang',
                                           '--timeout', '300'])
            for r in res:
                r.update(config=a.config, period=pe, threshold=th, replicas=rp, coded=list(coded), rep=rep + 1)
                open(out, 'a').write(json.dumps(r) + '\n')
                print(r.get('recovery_s'), r.get('failed_pct'), pe, th, rp)
            run.reset(a.config)
    apply(10, 3, 1)   # restore default probe settings and one replica after the design
