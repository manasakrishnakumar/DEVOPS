"""Novelty 3: digital twin of recovery + contextual bandit that picks a recovery action per fault signature.

The twin is empirical: for every (fault, action) it resamples measured trials from results/fault_trials.jsonl.
  action 'restart_only' <- config C  (default Kubernetes, no semantic guard)
  action 'tier_switch'  <- config D  (semantic guard + tier fall-through)
Cost per episode = recovery_s + W_FAIL * failed_pct + W_DEG * degraded_share * 100 + W_Q * seconds_below_full_quality
(the last term charges a policy that leaves the service on a fallback tier forever; without it tier_switch looked cheapest)
(W_* are policy knobs; defaults penalise a failed request more than a degraded-but-valid answer).
Writes analysis/policy.json (signature -> {action: mean cost}) for the operator and analysis/bandit_eval.json.
"""
import json
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W_FAIL, W_DEG = 0.3, 0.05
W_Q, HORIZON = 0.5, 240.0     # cost per second spent below full quality; horizon charged when full quality never returns
SILENT = ('corrupt', 'unitchange', 'flatline', 'scaler')
ACTION_OF = {'C': 'restart_only', 'D': 'tier_switch'}
SIGNATURE = {'crash': 'unreachable', 'oom': 'unreachable', 'hang': 'timeout', 'corrupt': 'invalid:lstm,sarima',
             'unitchange': 'invalid:lstm,sarima', 'flatline': 'invalid:lstm,sarima', 'scaler': 'invalid:lstm'}


def load():
    eps = defaultdict(list)
    path = os.path.join(ROOT, 'results', 'fault_trials.jsonl')
    for line in open(path):
        r = json.loads(line)
        act = ACTION_OF.get(r.get('config'))
        if not act:
            continue
        rec = r.get('recovery_s')
        if rec is None:                      # never recovered inside the window: charge the full timeout
            rec = 240.0
        total = max(1, r.get('total') or 1)
        tiers = r.get('tiers_after_fault') or {}
        deg = sum(v for k, v in tiers.items() if k in ('climatology', 'cache')) / max(1, sum(tiers.values()) or 1)
        full = HORIZON if (act == 'tier_switch' and r['fault'] in SILENT) else rec      # a tier switch never restores full quality for silent faults
        cost = rec + W_FAIL * (r.get('failed_pct') or 0.0) + W_DEG * deg * 100 + W_Q * full
        eps[(r['fault'], act)].append(cost)
    op = os.path.join(ROOT, 'results', 'operator_trials.jsonl')    # Phase 8 live-operator experiments
    if os.path.exists(op):
        for line in open(op):
            r = json.loads(line)
            act = {'none': 'tier_switch', 'rules': 'switch_then_restart'}.get(r.get('policy'))
            fw = r.get('fault_window')
            if not act or not fw:
                continue
            rec = r.get('restored_s')
            rec = 240.0 if rec is None else rec          # full quality never came back inside the window
            eps[(r['fault'], act)].append(rec + W_FAIL * fw['failed_pct'] + W_DEG * fw['degraded_pct'] + W_Q * rec)
    return eps


def main():
    eps = load()
    faults = sorted({f for f, _ in eps})
    actions = sorted({a for _, a in eps})
    print('episodes:', {f'{f}/{a}': len(v) for (f, a), v in eps.items()})
    if len(actions) < 2:
        print('Need data for at least two actions (run config C and config D); only', actions)
        return
    table = defaultdict(dict)
    for (f, a), v in eps.items():
        table[SIGNATURE[f]].setdefault(a, [])
        table[SIGNATURE[f]][a] += v
    policy = {s: {a: sum(v) / len(v) for a, v in d.items()} for s, d in table.items()}
    json.dump(policy, open(os.path.join(ROOT, 'analysis', 'policy.json'), 'w'), indent=1)

    # online simulation: UCB1 per fault context vs fixed policies and the oracle
    rng = random.Random(0)
    T = 600
    sig_faults = [f for f in faults if all((f, a) in eps for a in actions)]
    if not sig_faults:
        print('No fault has data for every action; skipping bandit simulation.')
        return
    cnt = {(f, a): 0 for f in sig_faults for a in actions}
    tot = {(f, a): 0.0 for f in sig_faults for a in actions}
    res = {'bandit': 0.0, 'oracle': 0.0, **{f'always_{a}': 0.0 for a in actions}}
    best = {f: min(actions, key=lambda a: sum(eps[(f, a)]) / len(eps[(f, a)])) for f in sig_faults}
    for t in range(1, T + 1):
        f = rng.choice(sig_faults)
        untried = [a for a in actions if cnt[(f, a)] == 0]
        if untried:
            a = untried[0]
        else:   # UCB on cost (lower is better); bonus scaled by the observed cost range
            n = sum(cnt[(f, x)] for x in actions)
            span = max(max(eps[(f, x)]) for x in actions) or 1.0
            a = min(actions, key=lambda x: tot[(f, x)] / cnt[(f, x)] - span * (2 * __import__('math').log(n) / cnt[(f, x)]) ** 0.5)
        c = rng.choice(eps[(f, a)])
        cnt[(f, a)] += 1
        tot[(f, a)] += c
        res['bandit'] += c
        res['oracle'] += sum(eps[(f, best[f])]) / len(eps[(f, best[f])])
        for x in actions:
            res[f'always_{x}'] += rng.choice(eps[(f, x)])
    out = {'rounds': T, 'avg_cost_per_episode': {k: round(v / T, 2) for k, v in res.items()},
           'best_action_per_fault': best, 'weights': {'W_FAIL': W_FAIL, 'W_DEG': W_DEG}}
    json.dump(out, open(os.path.join(ROOT, 'analysis', 'bandit_eval.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
