"""Promotion gate: query Prometheus for shadow-candidate quality; exit 0 = promote, 1 = reject, 2 = not enough data.
  python analysis/shadow_gate.py --prom http://localhost:9090 --max-reject 0.05 --min-samples 20"""
import argparse
import sys

import requests

p = argparse.ArgumentParser()
p.add_argument('--prom', default='http://localhost:9090')
p.add_argument('--max-reject', type=float, default=0.05)
p.add_argument('--min-samples', type=int, default=20)
a = p.parse_args()


def q(expr):
    r = requests.get(a.prom + '/api/v1/query', params={'query': expr}, timeout=10).json()['data']['result']
    return float(r[0]['value'][1]) if r else 0.0


total, rej = q('sum(shadow_total_total)'), q('sum(shadow_reject_total)')
ratio = rej / max(total, 1)
print(f'samples={total:.0f} rejects={rej:.0f} ratio={ratio:.3f}')
if total < a.min_samples:
    print('not enough shadow traffic')
    sys.exit(2)
sys.exit(0 if ratio <= a.max_reject else 1)
