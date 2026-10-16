"""Phase 13b: model-family comparison under identical faults. Deployment serves only SARIMA, only LSTM, or both
(MODELS env, image :8, guard off). Records start-up/load time, RSS, then crash / oom / hang recovery (5 trials each).
Appends to results/model_family.jsonl.   INFER_TAG=8 python chaos/run_family.py --trials 5
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402
import run_operator as ro  # noqa: E402

FAM = {'sarima': ('sarima', '/predict?model=sarima&steps=3'), 'lstm': ('lstm', '/predict?model=lstm&steps=3'),
       'both': ('sarima,lstm', '/predict?model=auto&steps=3')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=5)
    ap.add_argument('--faults', nargs='+', default=['crash', 'oom', 'hang'])
    a = ap.parse_args()
    run.switch_to('C4')                                   # image tag from INFER_TAG, guard off, FAULT_INJECTION on
    out = os.path.join(run.RES, 'model_family.jsonl')
    for fam, (models, path) in FAM.items():
        run.kube('-n', run.KNS, 'set', 'env', 'deploy/inference-api', f'MODELS={models}')
        run.kube('-n', run.KNS, 'rollout', 'restart', 'deploy/inference-api')
        time.sleep(10)
        ro.wait_ready()
        time.sleep(15)
        t = ro.pod_get('/metrics')
        g = lambda n: sum(float(m.group(1)) for m in re.finditer(rf'^{n}(?:{{[^}}]*}})? ([0-9.eE+-]+)$', t, re.M))
        meta = {'family': fam, 'kind': 'startup', 'startup_s': g('startup_seconds'), 'model_load_s_sum': g('model_load_seconds'),
                'rss_mb': round(g('process_rss_bytes') / 1e6, 1), 'image_tag': os.environ.get('INFER_TAG')}
        open(out, 'a').write(json.dumps(meta) + '\n')
        print(meta, flush=True)
        for fault in a.faults:
            for n in range(a.trials):
                res = run.run_probe('C4', ['--mode', 'fault', '--base', 'http://inference-api:5001', '--probe-path', path,
                                           '--fault', fault, '--timeout', '240'])
                for r in res:
                    r.update(family=fam, kind='fault', trial=n + 1)
                    open(out, 'a').write(json.dumps(r) + '\n')
                    print(fam, fault, n + 1, r.get('outcome'), r.get('recovery_s'), r.get('failed_pct'), flush=True)
                run.reset('C4')
                ro.wait_ready()
    run.kube('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'MODELS=sarima,lstm')


if __name__ == '__main__':
    main()
