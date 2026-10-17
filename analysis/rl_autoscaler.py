"""X: RL autoscaler (tabular Q-learning) in a simulator of bursty load.  SIMULATION ONLY - not validated on the cluster.
Model: per-replica capacity CAP rps (LSTM endpoint, measured order of magnitude), pod start delay 5 steps (25 s at 5 s steps).
Reward per step = -(10 * dropped_fraction + 0.3 * replicas).  Trains on random bursty traces, evaluates on held-out traces
against fixed-1, fixed-3 and a reactive threshold rule.  Writes results/extras_rl_autoscaler.json.
"""
import json
import os
import random
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP, DELAY, MAXR, T = 4.0, 5, 4, 120


def trace(rng):
    base = rng.uniform(1, 3)
    start, length, peak = rng.randint(20, 70), rng.randint(15, 40), rng.uniform(8, 20)
    return [base + (peak if start <= t < start + length else 0) + rng.gauss(0, 0.3) for t in range(T)]


def bucket(x):
    return min(5, int(x // 3))


def run(policy, tr, q=None, eps=0.0, rng=None):
    rep, pending, tot, drops = 1, [], 0.0, 0.0
    prev = tr[0]
    for t, load in enumerate(tr):
        s = (rep + sum(1 for p in pending), bucket(load), 1 if load > prev + 0.5 else 0)
        if policy == 'q':
            a = rng.choice((-1, 0, 1)) if rng and rng.random() < eps else int(np.argmax(q[s])) - 1
        elif policy == 'reactive':
            a = 1 if load / (rep * CAP) > 0.8 else (-1 if load / (rep * CAP) < 0.3 else 0)
        else:
            a = 0
        if policy == 'fixed3':
            rep = 3
        elif policy == 'fixed1':
            rep = 1
        elif a == 1 and rep + len(pending) < MAXR:
            pending.append(DELAY)
        elif a == -1 and rep > 1:
            rep -= 1
        pending = [p - 1 for p in pending]
        rep += sum(1 for p in pending if p <= 0)
        pending = [p for p in pending if p > 0]
        drop = max(0.0, load - rep * CAP) / load
        r = -(10 * drop + 0.3 * rep)
        tot += r
        drops += drop
        if policy == 'q' and q is not None and eps > 0:
            s2 = (rep + len(pending), bucket(tr[min(t + 1, T - 1)]), 1 if tr[min(t + 1, T - 1)] > load + 0.5 else 0)
            q[s][a + 1] += 0.1 * (r + 0.95 * q[s2].max() - q[s][a + 1])
        prev = load
    return tot, drops / T


def main():
    rng = random.Random(0)
    from collections import defaultdict
    q = defaultdict(lambda: np.zeros(3))
    for ep in range(4000):
        run('q', trace(rng), q, eps=max(0.05, 1 - ep / 3000), rng=rng)
    test = [trace(random.Random(1000 + i)) for i in range(200)]
    out = {}
    for pol in ('fixed1', 'fixed3', 'reactive', 'q'):
        rs = [run(pol, tr, q if pol == 'q' else None) for tr in test]
        out[pol] = {'mean_reward': round(float(np.mean([r[0] for r in rs])), 2), 'mean_drop_pct': round(100 * float(np.mean([r[1] for r in rs])), 2)}
    out['note'] = 'simulation only; capacity/delay assumed; single-node cluster could not show scaling gains (K37)'
    json.dump(out, open(os.path.join(ROOT, 'results', 'extras_rl_autoscaler.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
