"""Phase 11: in-cluster shadow-gate experiment. Each candidate set is copied into the running pod, loaded as the shadow
model (never served), scored on mirrored live requests (5 rps) and gated (reject ratio <= 5 %, >= 20 samples).
Appends to results/shadow_gate_cluster.jsonl.   INFER_TAG=8 python analysis/shadow_gate_cluster.py --trials 3
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
import run  # noqa: E402
import run_operator as ro  # noqa: E402

CAND = os.path.join(ROOT, 'results', 'candidates')
EXPECT = {'good_copy': 'promote', 'good_noise': 'promote', 'bad_scaler': 'reject', 'bad_swap': 'reject',
          'bad_bitflip': 'reject', 'bad_nan': 'reject', 'bad_undertrained': 'reject', 'retrain_40ep': None}


def pod():
    r = run.kube('-n', run.KNS, 'get', 'pods', '-l', 'app=inference-api', '-o', 'jsonpath={.items[0].metadata.name}')
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3)
    a = ap.parse_args()
    run.switch_to('E4')
    out = os.path.join(ROOT, 'results', 'shadow_gate_cluster.jsonl')
    for name in EXPECT:
        for t in range(a.trials):
            ro.wait_ready()
            p = pod()
            run.kube('-n', run.KNS, 'exec', p, '--', 'rm', '-rf', f'/tmp/cand_{name}')
            # relative source path: a Windows drive letter ("C:") makes kubectl cp misread the argument
            c = run.kube('-n', run.KNS, 'cp', f'results/candidates/{name}', f'{run.KNS}/{p}:/tmp/cand_{name}')
            if c.returncode:
                print('cp failed', name, c.stderr[-200:], flush=True)
                continue
            ld = json.loads(ro.pod_get(f'/shadow/load?dir=/tmp/cand_{name}'))
            th = threading.Thread(target=lambda: run.run_probe('E4', [
                '--mode', 'silent', '--base', 'http://inference-api:5001', '--probe-path', '/predict?model=auto&steps=6',
                '--fault', 'none', '--rps', '5', '--warmup', '5', '--fault-window', '75', '--heal-window', '2']))
            th.start()
            t0, st = time.time(), {}
            while time.time() - t0 < 110:
                time.sleep(3)
                try:
                    st = json.loads(ro.pod_get('/shadow/status'))
                except Exception:
                    continue
                if st.get('decision'):
                    break
            row = {'candidate': name, 'trial': t + 1, 'loaded': ld.get('ready'), 'expected': EXPECT[name], **st,
                   'image_tag': os.environ.get('INFER_TAG'), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}
            open(out, 'a').write(json.dumps(row) + '\n')
            print(name, t + 1, st.get('decision'), st.get('reject_ratio'), st.get('time_to_decision_s'), flush=True)
            th.join(timeout=200)
            ro.pod_get('/shadow/clear')


if __name__ == '__main__':
    main()
