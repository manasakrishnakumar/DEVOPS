"""X10: bursty load under (a) fixed 1 replica, (b) reactive HPA (CPU 50 %, 1-3 replicas), (c) proactive pre-scaling to 3 replicas
60 s before the burst (lead time covers the measured pod start-up of about 25 s).  Appends to results/extras_scaling.jsonl.
  INFER_TAG=9 python analysis/extras_scaling.py --trials 3
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
import run  # noqa: E402
import run_operator as ro  # noqa: E402

K = run.kube
OUT = os.path.join(ROOT, 'results', 'extras_scaling.jsonl')


def burst():
    ov = json.dumps({'spec': {'containers': [{'name': 'b', 'image': 'climate-frontend:3', 'imagePullPolicy': 'Never',
                     'command': ['python', '/probe/burst_load.py', 'http://inference-api:5001', '/predict?model=lstm&steps=6'],
                     'volumeMounts': [{'name': 's', 'mountPath': '/probe'}]}],
                     'volumes': [{'name': 's', 'configMap': {'name': 'burst-script'}}]}})
    r = K('-n', run.KNS, 'run', f'burst-{int(time.time())}', '--rm', '-i', '--restart=Never', '--image=climate-frontend:3',
          '--image-pull-policy=Never', f'--overrides={ov}', '--quiet')
    lines = [l for l in r.stdout.splitlines() if l.startswith('{')]
    return json.loads(lines[-1]) if lines else {}


def reset():
    K('-n', run.KNS, 'delete', 'hpa', 'inference-api', '--ignore-not-found')
    K('-n', run.KNS, 'scale', 'deploy/inference-api', '--replicas=1')
    time.sleep(10)
    K('-n', run.KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=300s')
    ro.wait_ready()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3)
    a = ap.parse_args()
    subprocess.run(['minikube', 'addons', 'enable', 'metrics-server'], capture_output=True)
    K('-n', run.KNS, 'create', 'configmap', 'burst-script', '--from-file=burst_load.py=chaos/burst_load.py', '--dry-run=client', '-o', 'yaml')
    cm = K('-n', run.KNS, 'create', 'configmap', 'burst-script', '--from-file=burst_load.py=chaos/burst_load.py', '--dry-run=client', '-o', 'yaml').stdout
    subprocess.run(['kubectl', 'apply', '-f', '-'], input=cm, text=True, capture_output=True)
    run.switch_to('C4')
    K('-n', run.KNS, 'set', 'env', 'deploy/inference-api', 'SEMANTIC_GUARD=1', 'GUARD_MODE=envelope+inv')
    ro.wait_ready()
    for _ in range(18):                                     # wait for metrics-server to serve pod metrics
        if K('top', 'pods', '-n', run.KNS).returncode == 0:
            break
        time.sleep(10)
    for t in range(a.trials):
        for mode in ('fixed_1_replica', 'reactive_hpa', 'proactive_prescale'):
            reset()
            t0 = time.time()
            if mode == 'reactive_hpa':
                K('-n', run.KNS, 'autoscale', 'deploy/inference-api', '--cpu-percent=50', '--min=1', '--max=3')
            elif mode == 'proactive_prescale':
                K('-n', run.KNS, 'scale', 'deploy/inference-api', '--replicas=3')
                K('-n', run.KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=300s')
                time.sleep(15)
            res = burst()
            reps = K('-n', run.KNS, 'get', 'deploy/inference-api', '-o', 'jsonpath={.status.readyReplicas}').stdout
            row = {'mode': mode, 'trial': t + 1, 'ready_replicas_at_end': reps, **res, 'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}
            open(OUT, 'a').write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)
    reset()


if __name__ == '__main__':
    main()
