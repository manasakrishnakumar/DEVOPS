"""In-cluster bursty load: 40 s at 4 rps, 70 s at 24 rps, 40 s at 4 rps against the inference service. Prints one JSON line."""
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

base = sys.argv[1]
PHASES = [('base', 40, 3), ('burst', 70, 20), ('tail', 40, 3)]
PATH = sys.argv[2] if len(sys.argv) > 2 else '/predict?model=sarima&steps=3'
rec, lock = [], threading.Lock()


def one(phase):
    t = time.time()
    try:
        r = requests.get(base + PATH, timeout=5)
        ok = r.status_code == 200
    except Exception:
        ok = False
    with lock:
        rec.append((phase, ok, time.time() - t))


pool = ThreadPoolExecutor(max_workers=128)
for name, dur, rps in PHASES:
    end = time.time() + dur
    nxt = time.time()
    while time.time() < end:
        if time.time() >= nxt:
            pool.submit(one, name)
            nxt += 1.0 / rps
        time.sleep(0.002)
time.sleep(6)
out = {}
for name, _, _ in PHASES:
    v = [r for r in rec if r[0] == name]
    lat = sorted(r[2] for r in v if r[1]) or [0]
    out[name] = {'n': len(v), 'failed_pct': round(100 * sum(not r[1] for r in v) / max(len(v), 1), 1),
                 'p50_ms': round(1000 * statistics.median(lat)), 'p95_ms': round(1000 * lat[min(len(lat) - 1, int(0.95 * len(lat)))])}
print(json.dumps(out), flush=True)
