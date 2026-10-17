"""Novelty 6: deadline- and load-aware degradation.  LSTM burst (3 -> 20 -> 3 rps, 1 replica) with the guard + golden check, deadline off (G4)
vs on (H4, DEADLINE_MS=800, per-tier concurrency caps).  Appends results/extras_deadline.jsonl.
  INFER_TAG=12 python analysis/extras_deadline.py --trials 3
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'chaos'))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
import run  # noqa: E402
import extras_scaling as xs  # noqa: E402

OUT = os.path.join(ROOT, 'results', 'extras_deadline.jsonl')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=3)
    a = ap.parse_args()
    for cfg in ('G4', 'H4'):
        run.switch_to(cfg)
        for t in range(a.trials):
            xs.reset()
            res = xs.burst()
            row = {'config': cfg, 'trial': t + 1, **res, 'ts': time.strftime('%Y-%m-%dT%H:%M:%S')}
            open(OUT, 'a').write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
