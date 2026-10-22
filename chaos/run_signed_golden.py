"""Extra 3 experiment: signed golden outputs vs the start-up reference, on the Kubernetes cluster.

Conditions (inference image with GUARD + GOLDEN_CHECK, operator scaled to 0, 5 requests per second, 30 s window after the pod is Ready):
  C0 healthy_signed          signed reference, healthy models            -> no false alarm
  C1 corrupt_startup         model corrupt BEFORE start, start-up reference (the known blind spot)
  C2 corrupt_startup_signed  same corruption, signed reference           -> detected from the first request
  C3 tampered_golden         golden.json modified after signing          -> fail closed (new pod never Ready, old pod keeps serving)
  C4 model_hash_mismatch     signed manifest names a different model file -> fail closed

Prerequisites: ConfigMaps signed-golden (good) in namespace climate, created by chaos/release_signed_golden.ps1;
the deployment patched with k8s/12-signed-golden-patch.yaml; NodePort service inference-api-np.
    python chaos/run_signed_golden.py --trials 10          appends to results/signed_golden_trials.jsonl
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hostclient as H  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
K = H.kube
GOOD, TAMPER, WRONGHASH = os.environ.get('GOLD_GOOD'), os.environ.get('GOLD_TAMPER'), os.environ.get('GOLD_WRONGHASH')


def set_cm(dirpath):
    r = subprocess.run(f'kubectl -n climate create configmap signed-golden --from-file="{dirpath}" --dry-run=client -o yaml | kubectl apply -f -',
                       shell=True, capture_output=True, text=True)
    return r.returncode == 0


def configure(cond):
    env = {'C0': ('CORRUPT_AT_STARTUP-', 'SIGNED_GOLDEN_DIR=/golden'), 'C1': ('CORRUPT_AT_STARTUP=bitflip', 'SIGNED_GOLDEN_DIR-'),
           'C2': ('CORRUPT_AT_STARTUP=bitflip', 'SIGNED_GOLDEN_DIR=/golden'), 'C3': ('CORRUPT_AT_STARTUP-', 'SIGNED_GOLDEN_DIR=/golden'),
           'C4': ('CORRUPT_AT_STARTUP-', 'SIGNED_GOLDEN_DIR=/golden')}[cond]
    set_cm({'C3': TAMPER, 'C4': WRONGHASH}.get(cond, GOOD))
    K('-n', H.NS, 'set', 'env', 'deploy/inference-api', *env)
    time.sleep(3)


def newest_pod():
    r = K('-n', H.NS, 'get', 'pods', '-l', 'app=inference-api', '-o', 'json')
    items = json.loads(r.stdout)['items']
    items.sort(key=lambda p: p['metadata']['creationTimestamp'])
    return items[-1] if items else None


def pod_ready_reason(pod):
    code = ("import urllib.request,urllib.error\n"
            "try:\n r=urllib.request.urlopen('http://localhost:5001/health/ready',timeout=10);print(r.status, r.read().decode())\n"
            "except urllib.error.HTTPError as e:\n print(e.code, e.read().decode())\n")
    r = K('-n', H.NS, 'exec', pod['metadata']['name'], '--', 'python', '-c', code, timeout=60)
    return (r.stdout or r.stderr).strip()[:300]


def wait_ready(base, limit=240):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            if H.requests.get(base + '/health/ready', timeout=3).status_code == 200:
                return round(time.time() - t0, 1)
        except Exception:
            pass
        time.sleep(2)
    return None


def trial(cond, base, gold, k):
    K('-n', H.NS, 'rollout', 'restart', 'deploy/inference-api')
    t_start = time.time()
    rec = {'cond': cond, 'trial': k, 'ts': datetime.datetime.now().isoformat(timespec='seconds')}
    if cond in ('C3', 'C4'):                                     # fail closed: the new pod must never become Ready
        recs, t0 = H.run_window(base, 75)
        pod = newest_pod()
        ready = next((c['status'] for c in pod['status'].get('conditions', []) if c['type'] == 'Ready'), 'Unknown')
        rec.update(new_pod_ready=(ready == 'True'), new_pod_reason=pod_ready_reason(pod), served=H.summarize(recs, gold, t0))
        K('-n', H.NS, 'rollout', 'undo', 'deploy/inference-api')
        K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=180s')
        wait_ready(base)
        return rec
    # wait until the rollout has finished, so that the pod that answers is the FRESH pod (not the one it replaces)
    K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=300s', timeout=330)
    ready_after = wait_ready(base)
    rec['ready_after_s'] = None if ready_after is None else round(time.time() - t_start, 1)
    if ready_after is None:
        rec['error'] = 'not ready'
        return rec
    for attempt in (1, 2, 3):          # the tunnel may reset a connection just after a pod swap: retry, and record that it was needed
        try:
            sem = H.requests.get(base + '/health/semantic', timeout=20)
            rec['semantic_http'] = sem.status_code
            j = sem.json()
            rec['semantic_ok'] = j.get('semantic_ok')
            rec['lstm_valid'] = j.get('backends', {}).get('lstm', {}).get('valid')
            rec['golden_dev_lstm'] = j.get('backends', {}).get('lstm', {}).get('golden_dev')
            rec['reference_source'] = (j.get('golden_reference') or {}).get('source')
            rec.pop('semantic_error', None)
            rec['semantic_attempts'] = attempt
            break
        except Exception as e:
            rec['semantic_error'] = str(e)[:80]
            time.sleep(3)
    recs, t0 = H.run_window(base, 30)
    rec['window'] = H.summarize(recs, gold, t0)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=10)
    ap.add_argument('--conds', nargs='+', default=['C0', 'C1', 'C2', 'C3', 'C4'])
    ap.add_argument('--trials-failclosed', type=int, default=5)
    a = ap.parse_args()
    K('-n', H.NS, 'scale', 'deploy/forecast-operator', '--replicas=0')
    tun = H.Tunnel()
    try:
        configure('C0')
        K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=240s')
        wait_ready(tun.url)
        gold = H.healthy_reference(tun.url)
        json.dump(gold, open(os.path.join(RES, 'signed_golden_reference.json'), 'w'))
        with open(os.path.join(RES, 'signed_golden_trials.jsonl'), 'a') as f:
            for cond in a.conds:
                if cond in ('C3', 'C4'):                          # the pod that keeps serving must be a healthy one
                    configure('C0')
                    K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=240s')
                    wait_ready(tun.url)
                configure(cond)
                if cond not in ('C3', 'C4'):
                    K('-n', H.NS, 'rollout', 'status', 'deploy/inference-api', '--timeout=240s')
                n = a.trials_failclosed if cond in ('C3', 'C4') else a.trials
                for k in range(1, n + 1):
                    r = trial(cond, tun.url, gold, k)
                    f.write(json.dumps(r) + '\n')
                    f.flush()
                    print(cond, k, json.dumps(r)[:240], flush=True)
                if cond in ('C3', 'C4'):
                    set_cm(GOOD)
    finally:
        configure('C0')
        tun.close()


if __name__ == '__main__':
    main()
