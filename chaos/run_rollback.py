"""Extra 2 experiment: richer operator actions (rollback to the last known-good release) vs restart-only.

Two fault classes that look identical to the operator (/health/semantic says invalid:lstm) but need different actions:
  transient    silent fault injected into the running process (/fault?mode=corrupt): a RESTART fixes it, a rollback has nothing to roll back to
  bad_release  a bad release is rolled out (Deployment env CORRUPT_AT_STARTUP=scaler: the model is corrupt on every start):
               a restart can never fix it, ONLY a rollback to the last known-good release does
Policies: none | rules (restart only) | release_aware | escalate (restart, then rollback, then pin the surviving tier)
The operator runs with failureThreshold 3, cooldownSeconds 30, goodAfter 3. The client (5 requests per second) runs on the host
through a minikube service tunnel, so it survives the pod replacements.   Appends to results/rollback_trials.jsonl

    python chaos/run_rollback.py --trials 5
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hostclient as H  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
K = H.kube
CR = 'forecastservice/climate-inference'
WINDOW = {'transient': 150, 'bad_release': 210}


def cr_status():
    r = K('-n', H.NS, 'get', CR, '-o', 'json')
    try:
        return json.loads(r.stdout).get('status', {})
    except Exception:
        return {}


def current_hash():
    d = json.loads(K('-n', H.NS, 'get', 'deploy/inference-api', '-o', 'json').stdout)
    rev = d['metadata']['annotations'].get('deployment.kubernetes.io/revision')
    rss = json.loads(K('-n', H.NS, 'get', 'rs', '-l', 'app=inference-api', '-o', 'json').stdout)['items']
    for rs in rss:
        if rs['metadata']['annotations'].get('deployment.kubernetes.io/revision') == rev:
            return rs['metadata']['labels'].get('pod-template-hash')
    return None


def set_policy(policy):
    if policy == 'none':
        K('-n', H.NS, 'scale', 'deploy/forecast-operator', '--replicas=0')
        return
    spec = {'spec': {'policy': policy, 'failureThreshold': 3, 'cooldownSeconds': 30, 'goodAfter': 3}}
    K('-n', H.NS, 'patch', CR, '--type=merge', '-p', json.dumps(spec))
    K('-n', H.NS, 'scale', 'deploy/forecast-operator', '--replicas=1')
    K('-n', H.NS, 'rollout', 'status', 'deploy/forecast-operator', '--timeout=120s')


def clear_status():
    K('-n', H.NS, 'patch', CR, '--subresource=status', '--type=merge', '-p',
      json.dumps({'status': {'attempt': 0, 'consecutiveBad': 0, 'okStreak': 0, 'lastActionAt': None, 'history': []}}))      # lastGoodHash is KEPT: it is the operator's memory of the healthy release, wiping it would make rollback impossible


def make_healthy(base, limit=420):
    """Healthy template (no corruption env), pod Ready, and (when an operator is running) lastGoodHash == current release."""
    K('-n', H.NS, 'set', 'env', 'deploy/inference-api', 'CORRUPT_AT_STARTUP-')
    K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=240s')
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            if H.requests.get(base + '/health/ready', timeout=3).status_code == 200 and \
               H.requests.get(base + '/health/semantic', timeout=20).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(3)
    else:
        return False
    op = K('-n', H.NS, 'get', 'deploy/forecast-operator', '-o', 'jsonpath={.spec.replicas}').stdout.strip()
    if op == '0':
        return True
    while time.time() - t0 < limit:
        if cr_status().get('lastGoodHash') and cr_status().get('lastGoodHash') == current_hash():
            return True
        time.sleep(4)
    return False


def trial(policy, klass, base, gold, k):
    set_policy(policy)
    if not make_healthy(base):
        return {'policy': policy, 'fault': klass, 'trial': k, 'error': 'could not reach a healthy baseline'}
    clear_status()
    rev0 = current_hash()
    if klass == 'transient':
        inject = lambda: H.requests.get(base + '/fault?mode=corrupt', timeout=5)       # noqa: E731
    else:
        inject = lambda: K('-n', H.NS, 'set', 'env', 'deploy/inference-api', 'CORRUPT_AT_STARTUP=scaler')   # noqa: E731
    t_inject = {}

    def do_inject():
        t_inject['t'] = time.time()
        inject()
    recs, t0 = H.run_window(base, WINDOW[klass] + 10, events=[(10.0, do_inject)])
    t_f = t_inject.get('t', t0 + 10)
    out = H.summarize(recs, gold, t_f)
    st = cr_status()
    return {'policy': policy, 'fault': klass, 'trial': k, 'ts': datetime.datetime.now().isoformat(timespec='seconds'),
            'restored_s': out['restored_s'], 'window': out, 'actions': [h.get('action') for h in (st.get('history') or [])],
            'last_good_hash_before': rev0, 'image': K('-n', H.NS, 'get', 'deploy/inference-api', '-o',
                                                       'jsonpath={.spec.template.spec.containers[0].image}').stdout.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=5)
    ap.add_argument('--policies', nargs='+', default=['rules', 'release_aware', 'escalate'])
    ap.add_argument('--faults', nargs='+', default=['transient', 'bad_release'])
    ap.add_argument('--none-trials', type=int, default=3)
    a = ap.parse_args()
    tun = H.Tunnel()
    try:
        set_policy('rules')
        make_healthy(tun.url)
        gold = H.healthy_reference(tun.url)
        with open(os.path.join(RES, 'rollback_trials.jsonl'), 'a') as f:
            plan = [(p, k, a.trials) for k in a.faults for p in a.policies]
            if 'bad_release' in a.faults and a.none_trials:
                plan.append(('none', 'bad_release', a.none_trials))
            for policy, klass, n in plan:
                for k in range(1, n + 1):
                    r = trial(policy, klass, tun.url, gold, k)
                    f.write(json.dumps(r) + '\n')
                    f.flush()
                    print(policy, klass, k, 'restored_s=', r.get('restored_s'), 'actions=', r.get('actions'), flush=True)
    finally:
        K('-n', H.NS, 'set', 'env', 'deploy/inference-api', 'CORRUPT_AT_STARTUP-')
        set_policy('rules')
        tun.close()


if __name__ == '__main__':
    main()
