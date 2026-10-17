"""X: Chaos Mesh experiments on the inference service (PodChaos pod-kill, NetworkChaos 300 ms delay).  Appends results/extras_chaosmesh.jsonl.
Measured from inside the frontend pod so port-forwards are not involved.   python analysis/extras_chaosmesh.py
"""
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
OUT = os.path.join(ROOT, 'results', 'extras_chaosmesh.jsonl')
CODE = ("import urllib.request,time,json\nlat=[];fail=0\nfor i in range(10):\n t=time.time()\n try:\n"
        "  urllib.request.urlopen('http://inference-api:5001/predict?model=sarima&steps=3',timeout=5).read();lat.append((time.time()-t)*1000)\n"
        " except Exception:\n  fail+=1\n time.sleep(0.3)\nlat.sort()\nprint(json.dumps({'ok':len(lat),'fail':fail,'p50_ms':round(lat[len(lat)//2]) if lat else None}))")


def probe():
    r = subprocess.run(['kubectl', '-n', 'climate', 'exec', 'deploy/frontend', '--', 'python', '-c', CODE], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {'ok': 0, 'fail': 10, 'p50_ms': None}


def apply(y):
    subprocess.run(['kubectl', 'apply', '-f', '-'], input=y, text=True, capture_output=True)


def main():
    rows = []
    base = probe()
    rows.append({'exp': 'baseline', **base})
    kill = """apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata: {name: kill-inference, namespace: climate}
spec: {action: pod-kill, mode: one, selector: {namespaces: [climate], labelSelectors: {app: inference-api}}}
"""
    for t in range(3):
        t0 = time.time()
        apply(kill)
        time.sleep(3)
        ok = ro.wait_ready(300)
        rows.append({'exp': 'pod_kill', 'trial': t + 1, 'ready_after_s': round(time.time() - t0, 1) if ok else None})
        K('-n', 'climate', 'delete', 'podchaos', 'kill-inference', '--ignore-not-found')
        time.sleep(10)
    delay = """apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata: {name: delay-inference, namespace: climate}
spec: {action: delay, mode: all, selector: {namespaces: [climate], labelSelectors: {app: inference-api}}, delay: {latency: 300ms}, duration: 120s}
"""
    apply(delay)
    time.sleep(8)
    rows.append({'exp': 'network_delay_300ms', **probe()})
    K('-n', 'climate', 'delete', 'networkchaos', 'delay-inference', '--ignore-not-found')
    time.sleep(8)
    rows.append({'exp': 'after_delay_removed', **probe()})
    with open(OUT, 'a') as f:
        for r in rows:
            r['ts'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            f.write(json.dumps(r) + '\n')
            print(json.dumps(r))


if __name__ == '__main__':
    main()
