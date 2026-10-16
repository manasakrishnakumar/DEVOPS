"""Phase 8: operator experiments on config E4 (image :5).  For each policy x fault, inject WITHOUT heal and
measure how long until full quality returns (restored_s), plus wrong/degraded/failed shares.
  policy none   : operator scaled to 0 (guard degrades, nothing restores)
  policy rules  : operator restarts after N consecutive invalid /health/semantic checks
  policy bandit : operator picks the action from analysis/policy.json (twin)
Appends to results/operator_trials.jsonl.   INFER_TAG=5 python chaos/run_operator.py --trials 5
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402

K = run.kube


def pod_get(path):
    code = f"import urllib.request;print(urllib.request.urlopen('http://localhost:5001{path}',timeout=30).read().decode())"
    r = subprocess.run(['kubectl', '-n', run.KNS, 'exec', 'deploy/inference-api', '--', 'python', '-c', code],
                       capture_output=True, text=True, timeout=90)
    return r.stdout.strip()


def wait_ready(limit=420):
    t = time.time()
    while time.time() - t < limit:
        r = K('-n', run.KNS, 'rollout', 'status', 'deploy/inference-api', '--timeout=30s')
        if r.returncode == 0:
            try:
                if json.loads(pod_get('/health/ready')).get('ready'):
                    return True
            except Exception:
                pass
        time.sleep(5)
    return False


def set_policy(policy):
    if policy == 'none':
        K('-n', run.KNS, 'scale', 'deploy/forecast-operator', '--replicas=0')
    else:
        K('-n', run.KNS, 'patch', 'forecastservice/climate-inference', '--type=merge', '-p',
          json.dumps({'spec': {'policy': policy}}))
        K('-n', run.KNS, 'scale', 'deploy/forecast-operator', '--replicas=1')
        K('-n', run.KNS, 'rollout', 'status', 'deploy/forecast-operator', '--timeout=120s')
        time.sleep(15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policies', nargs='+', default=['none', 'rules', 'bandit'])
    ap.add_argument('--faults', nargs='+', default=['corrupt', 'unitchange', 'scaler', 'flatline'])
    ap.add_argument('--trials', type=int, default=5)
    ap.add_argument('--window', type=float, default=150)
    a = ap.parse_args()
    run.switch_to('E4')
    out = os.path.join(run.RES, 'operator_trials.jsonl')
    for policy in a.policies:
        set_policy(policy)
        for fault in a.faults:
            for t in range(a.trials):
                if not wait_ready():
                    print('not ready; skipping', policy, fault, t, flush=True)
                    continue
                try:
                    pod_get('/fault?mode=heal')
                except Exception:
                    pass
                time.sleep(8)
                res = run.run_probe('E4', ['--mode', 'silent', '--base', 'http://inference-api:5001', '--probe-path',
                                           '/predict?model=auto&steps=6', '--fault', fault, '--rps', '5',
                                           '--warmup', '15', '--fault-window', str(a.window), '--heal-window', '2',
                                           '--no-heal'])
                hist = ''
                if policy != 'none':
                    r = K('-n', run.KNS, 'get', 'forecastservice/climate-inference', '-o', 'jsonpath={.status.history}')
                    hist = r.stdout[-400:]
                for r in res:
                    r.update(policy=policy, trial=t + 1, image_tag=os.environ.get('INFER_TAG', '5'),
                             operator_history=hist, ts=time.strftime('%Y-%m-%dT%H:%M:%S'))
                    with open(out, 'a') as f:
                        f.write(json.dumps(r) + '\n')
                    print(policy, fault, t + 1, r.get('restored_s'), r.get('fault_window'), flush=True)
                try:
                    pod_get('/fault?mode=heal')     # no-op if the operator already restarted the pod
                except Exception:
                    pass
    K('-n', run.KNS, 'scale', 'deploy/forecast-operator', '--replicas=0')


if __name__ == '__main__':
    main()
