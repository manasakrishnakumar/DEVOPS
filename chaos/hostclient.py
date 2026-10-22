"""Host-side client for experiments in which the pod is REPLACED during a trial (rollout, rollback, restart).
A kubectl port-forward dies with the pod, so the client talks to a NodePort service through a minikube service tunnel
(`minikube service inference-api-np -n climate --url`), which survives pod replacement.

Classification of every answer is the same as chaos/probe.py::silent_trial:
  correct   the golden tier (LSTM) answered inside the tolerance of the healthy reference
  wrong     finite numbers outside the tolerance (or non-finite)
  fallback  valid answer from another tier (e.g. SARIMA)
  degraded  answer labelled degraded (climatology / cache)
  failed    HTTP error or timeout
"""
import math
import re
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

NS = 'climate'
TOL = {'Rainfall': (25.0, 0.10), 'Temp_mean': (1.5, 0.05), 'Humidity': (6.0, 0.05)}
VARS3 = ['Rainfall', 'Temp_mean', 'Humidity']
PROBE = '/predict?model=auto&steps=6'


def kube(*a, timeout=180):
    return subprocess.run(['kubectl', *a], capture_output=True, text=True, timeout=timeout)


class Tunnel:
    def __init__(self, svc='inference-api-np'):
        self.proc = subprocess.Popen(['minikube', 'service', svc, '-n', NS, '--url'], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True)
        self.url = None
        t0 = time.time()
        while time.time() - t0 < 90 and not self.url:
            m = re.search(r'http://127\.0\.0\.1:\d+', self.proc.stdout.readline() or '')
            if m:
                self.url = m.group(0)
        if not self.url:
            raise RuntimeError('minikube service tunnel did not start')
        threading.Thread(target=lambda: [None for _ in self.proc.stdout], daemon=True).start()   # keep the pipe drained

    def close(self):
        self.proc.terminate()


def _finite(vals):
    return vals is not None and all(x is not None and math.isfinite(x) for v in VARS3 for x in vals[v])


def within(vals, gold):
    if not _finite(vals):
        return False
    for v in VARS3:
        for x, g in zip(vals[v], gold[v]):
            if abs(x - g) > TOL[v][0] + TOL[v][1] * abs(g):
                return False
    return True


def classify(r, gold, gtier='lstm'):
    if r['status'] != 200:
        return 'failed'
    if r['degraded']:
        return 'degraded'
    if r['tier'] == gtier:
        return 'correct' if within(r['vals'], gold) else 'wrong'
    return 'fallback' if _finite(r['vals']) else 'wrong'


def one_request(base, timeout=2.0):
    """One probe request. A connection that the minikube tunnel resets while a pod is being replaced ('Connection aborted' /
    ConnectionReset) is a property of the measurement channel, not of the service: it is retried once. A refused connection or a
    timeout (a real outage) is NOT retried and counts as failed."""
    rec = {'ts': time.time(), 'status': 0, 'tier': None, 'degraded': False, 'vals': None, 'retried': False}
    for attempt in (1, 2):
        try:
            r = requests.get(base + PROBE, timeout=timeout)
            rec['status'] = r.status_code
            if r.status_code == 200:
                d = r.json()
                rec.update(tier=d.get('tier'), degraded=bool(d.get('degraded')), vals={v: d[v] for v in VARS3})
            return rec
        except requests.exceptions.ConnectionError as e:
            if attempt == 1 and ('Connection aborted' in str(e) or 'ConnectionResetError' in str(e)):
                rec['retried'] = True
                continue
            return rec
        except Exception:
            return rec
    return rec


def healthy_reference(base, n=12):
    """Median LSTM-tier forecast of a healthy service."""
    rows = [one_request(base) for _ in range(n)]
    rows = [r for r in rows if r['status'] == 200 and r['tier'] == 'lstm' and _finite(r['vals'])]
    if len(rows) < 5:
        raise RuntimeError('service is not healthy: cannot take a reference')
    return {v: [statistics.median(r['vals'][v][k] for r in rows) for k in range(len(rows[0]['vals'][v]))] for v in VARS3}


def run_window(base, seconds, rps=5.0, events=()):
    """Send requests at `rps` for `seconds`; events = [(t_rel, callable)] run in their own threads. Returns (records, t0)."""
    recs, lock = [], threading.Lock()
    pool = ThreadPoolExecutor(max_workers=24)

    def go():
        r = one_request(base)
        with lock:
            recs.append(r)
    t0 = time.time()
    pend = sorted(events, key=lambda e: e[0])
    nxt = t0
    while time.time() - t0 < seconds:
        now = time.time()
        while pend and now - t0 >= pend[0][0]:
            threading.Thread(target=pend.pop(0)[1], daemon=True).start()
        if now >= nxt:
            pool.submit(go)
            nxt += 1.0 / rps
        time.sleep(0.005)
    time.sleep(2.5)
    pool.shutdown(wait=False, cancel_futures=True)
    with lock:
        return sorted(recs, key=lambda r: r['ts']), t0


def summarize(recs, gold, t_from, gtier='lstm'):
    """Shares of every class after t_from and restoration time (5 consecutive correct answers after a non-correct one)."""
    rows = [(r['ts'], classify(r, gold, gtier)) for r in recs if r['ts'] >= t_from]
    n = max(1, len(rows))
    out = {k + '_pct': round(100.0 * sum(1 for _, c in rows if c == k) / n, 1)
           for k in ('correct', 'wrong', 'fallback', 'degraded', 'failed')}
    out['n'] = len(rows)
    seen_bad, run, restored = False, 0, None
    for ts, c in rows:
        if c != 'correct':
            seen_bad = True
        run = run + 1 if c == 'correct' else 0
        if run >= 5 and seen_bad:
            restored = round(ts - t_from, 1)
            break
    out['restored_s'] = restored
    out['ever_non_correct'] = seen_bad
    return out
