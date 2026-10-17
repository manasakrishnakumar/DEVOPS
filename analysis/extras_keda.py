"""X: KEDA (request-rate trigger) under the same LSTM burst as analysis/extras_scaling.py.  Appends results/extras_keda.jsonl.
  INFER_TAG=10 python analysis/extras_keda.py --trials 3
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import run  # noqa: E402
import run_operator as ro  # noqa: E402
import extras_scaling as xs  # noqa: E402

K = run.kube
OUT = os.path.join(ROOT, 'results', 'extras_keda.jsonl')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3)
    a = ap.parse_args()
    for t in range(a.trials):
        K('-n', run.KNS, 'delete', 'scaledobject', 'inference-api', '--ignore-not-found')
        xs.reset()
        subprocess.run(['kubectl', 'apply', '-f', os.path.join(ROOT, 'k8s', 'keda-scaledobject.yaml')], capture_output=True)
        time.sleep(20)
        peak = [1]
        stop = threading.Event()

        def watch():
            while not stop.is_set():
                r = K('-n', run.KNS, 'get', 'deploy/inference-api', '-o', 'jsonpath={.status.readyReplicas}').stdout
                peak[0] = max(peak[0], int(r or 1))
                time.sleep(5)
        th = threading.Thread(target=watch)
        th.start()
        res = xs.burst()
        stop.set()
        th.join()
        row = {'mode': 'keda_prometheus', 'trial': t + 1, 'peak_ready_replicas': peak[0], **res, 'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}
        open(OUT, 'a').write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)
    K('-n', run.KNS, 'delete', 'scaledobject', 'inference-api', '--ignore-not-found')
    xs.reset()


if __name__ == '__main__':
    main()
