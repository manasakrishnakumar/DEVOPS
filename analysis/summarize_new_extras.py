"""Summaries, tables and figures for the three extras (bit-flip fuzzing, signed golden outputs, rollback/escalation).
Reads results/bitflip_fuzz.json, results/signed_golden_trials.jsonl, results/rollback_trials.jsonl
Writes results/new_extras_summary.json (headline numbers), results/new_extras_tables.md, results/figures/fig_*.png
    python analysis/summarize_new_extras.py
"""
import json
import math
import os
import statistics as st

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')
FIG = os.path.join(RES, 'figures')
os.makedirs(FIG, exist_ok=True)
CLASSES = ['sign', 'exp_msb', 'exp_other', 'mant_high', 'mant_low', 'any']
FLIPS = [1, 2, 4, 8, 16, 32, 64]


def jl(name):
    p = os.path.join(RES, name)
    return [json.loads(x.lstrip('\ufeff')) for x in open(p, encoding='utf-8-sig') if x.strip().lstrip('\ufeff').startswith('{')] if os.path.exists(p) else []


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(k, n):
    return f'{100 * k / n:.1f}' if n else 'n/a'


S, T = {}, []
# ------------------------------------------------------------------ 1. bit-flip fuzzing
fz = json.load(open(os.path.join(RES, 'bitflip_fuzz.json'), encoding='utf8')) if os.path.exists(os.path.join(RES, 'bitflip_fuzz.json')) else None
if fz:
    cells = fz['cells']

    def agg(keys):
        out = {f: sum(cells[k][f] for k in keys) for f in ('trials', 'wrong', 'error_loud', 'env_detect', 'golden_detect', 'env_detect_given_wrong',
                                                          'golden_detect_given_wrong', 'silent_wrong_env', 'silent_wrong_golden', 'golden_alarm_harmless')}
        return out
    allk = list(cells)
    A = agg(allk)
    S['fuzz'] = {'trials_total': A['trials'], 'cells': len(cells), 'trials_per_cell': fz['meta']['trials_per_cell'], 'control': fz['control'],
                 'wrong': A['wrong'], 'error_loud': A['error_loud'], 'silent_wrong_env': A['silent_wrong_env'],
                 'silent_wrong_golden': A['silent_wrong_golden'], 'golden_alarm_harmless': A['golden_alarm_harmless'],
                 'wrong_detected_by_env': A['env_detect_given_wrong'], 'wrong_detected_by_golden': A['golden_detect_given_wrong'],
                 'by_class': {}, 'by_flips': {}}
    T.append('## Table X.1  Bit-flip fuzzing of the real LSTM weights (' + f"{A['trials']} trials, {fz['meta']['trials_per_cell']} per cell)\n")
    T.append('| bit class | trials | wrong answer % [95 % CI] | loud failure (HTTP 500) % | wrong, missed by envelope % | wrong, missed by golden % | golden alarm on harmless change % |')
    T.append('|---|---|---|---|---|---|---|')
    for c in CLASSES:
        a = agg([k for k in allk if cells[k]['class'] == c])
        lo, hi = wilson(a['wrong'], a['trials'])
        S['fuzz']['by_class'][c] = {**a, 'wrong_ci': [round(lo, 4), round(hi, 4)]}
        T.append(f"| {c} | {a['trials']} | {pct(a['wrong'], a['trials'])} [{100 * lo:.1f}, {100 * hi:.1f}] | {pct(a['error_loud'], a['trials'])} | "
                 f"{pct(a['silent_wrong_env'], a['trials'])} | {pct(a['silent_wrong_golden'], a['trials'])} | {pct(a['golden_alarm_harmless'], a['trials'])} |")
    T.append('\n## Table X.2  Same study by number of flipped bits (all bit classes)\n')
    T.append('| flips | trials | wrong answer % | wrong, missed by envelope % | detection of wrong answers: envelope % | detection of wrong answers: golden % |')
    T.append('|---|---|---|---|---|---|')
    for n in FLIPS:
        a = agg([k for k in allk if cells[k]['flips'] == n])
        S['fuzz']['by_flips'][str(n)] = a
        T.append(f"| {n} | {a['trials']} | {pct(a['wrong'], a['trials'])} | {pct(a['silent_wrong_env'], a['trials'])} | "
                 f"{pct(a['env_detect_given_wrong'], a['wrong'])} | {pct(a['golden_detect_given_wrong'], a['wrong'])} |")
    # figure
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for c in CLASSES:
        ax[0].plot(FLIPS, [100 * cells[f'{c}|{n}']['wrong'] / cells[f'{c}|{n}']['trials'] for n in FLIPS], marker='o', label=c)
    ax[0].set_xscale('log', base=2); ax[0].set_xlabel('flipped bits'); ax[0].set_ylabel('wrong answers (%)'); ax[0].set_title('(a) how often a flip is harmful'); ax[0].legend(fontsize=8)
    ax[1].plot(FLIPS, [100 * S['fuzz']['by_flips'][str(n)]['env_detect_given_wrong'] / max(1, S['fuzz']['by_flips'][str(n)]['wrong']) for n in FLIPS], marker='s', label='envelope + invariants')
    ax[1].plot(FLIPS, [100 * S['fuzz']['by_flips'][str(n)]['golden_detect_given_wrong'] / max(1, S['fuzz']['by_flips'][str(n)]['wrong']) for n in FLIPS], marker='o', label='golden-output check')
    ax[1].set_xscale('log', base=2); ax[1].set_ylim(0, 105); ax[1].set_xlabel('flipped bits'); ax[1].set_ylabel('wrong answers detected (%)'); ax[1].set_title('(b) detection of harmful flips'); ax[1].legend(fontsize=8)
    grid = [[100 * cells[f'{c}|{n}']['silent_wrong_env'] / cells[f'{c}|{n}']['trials'] for n in FLIPS] for c in CLASSES]
    im = ax[2].imshow(grid, aspect='auto', cmap='Reds', vmin=0)
    ax[2].set_xticks(range(len(FLIPS))); ax[2].set_xticklabels(FLIPS); ax[2].set_yticks(range(len(CLASSES))); ax[2].set_yticklabels(CLASSES)
    ax[2].set_xlabel('flipped bits'); ax[2].set_title('(c) wrong AND missed by the envelope (%)'); plt.colorbar(im, ax=ax[2])
    plt.tight_layout(); plt.savefig(os.path.join(FIG, 'fig_bitflip_fuzz.png'), dpi=140); plt.close()

    # ---- golden-check tolerance sweep: the detection / harmless-alarm trade-off (needs the per-trial deviations)
    if all('trial_dev' in c for c in cells.values()):
        TOLS = [0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
        trials = [(d, w) for c in cells.values() for d, w, e in zip(c['trial_dev'], c['trial_wrong'], c['trial_error']) if not e]
        n_w = sum(w for _, w in trials)
        n_h = len(trials) - n_w
        sweep = []
        for t in TOLS:
            det = sum(1 for d, w in trials if w and (d is None or d > t))
            fa = sum(1 for d, w in trials if (not w) and (d is None or d > t))
            sweep.append({'tolerance': t, 'wrong_detected': det, 'wrong': n_w, 'harmless_alarm': fa, 'harmless': n_h,
                          'detect_pct': round(100 * det / max(1, n_w), 1), 'harmless_alarm_pct': round(100 * fa / max(1, n_h), 1)})
        ctl_max = fz['control']['max_dev']
        S['fuzz']['golden_sweep'] = {'rows': sweep, 'control_max_dev': ctl_max, 'default_tolerance': fz['meta']['golden_tol_history_std']}
        T.append('\n## Table X.5  Golden-output check: detection of wrong answers vs alarms on harmless changes, by tolerance '
                 f"(history-std units; default {fz['meta']['golden_tol_history_std']}; largest deviation of the unmodified models {ctl_max:.4f})\n")
        T.append('| tolerance | wrong answers detected % | alarms on harmless changes % |')
        T.append('|---|---|---|')
        for r in sweep:
            T.append(f"| {r['tolerance']} | {r['detect_pct']} ({r['wrong_detected']}/{r['wrong']}) | {r['harmless_alarm_pct']} ({r['harmless_alarm']}/{r['harmless']}) |")
        fig, ax = plt.subplots(figsize=(6.2, 4))
        ax.plot(TOLS, [r['detect_pct'] for r in sweep], marker='o', label='wrong answers detected')
        ax.plot(TOLS, [r['harmless_alarm_pct'] for r in sweep], marker='s', label='alarms on harmless changes')
        ax.axvline(fz['meta']['golden_tol_history_std'], color='grey', ls=':', label='default tolerance')
        ax.set_xscale('log'); ax.set_xlabel('golden tolerance (history std)'); ax.set_ylabel('%'); ax.set_ylim(-2, 104); ax.legend(fontsize=8)
        ax.set_title('Golden-output check: tolerance trade-off')
        plt.tight_layout(); plt.savefig(os.path.join(FIG, 'fig_golden_tolerance.png'), dpi=140); plt.close()

    # ---- same study inside a pod of the production image (fewer trials per cell)
    pp = os.path.join(RES, 'bitflip_fuzz_in_pod.json')
    if os.path.exists(pp):
        fp = json.load(open(pp, encoding='utf8'))
        T.append(f"\n## Table X.6  Bit-flip fuzzing: host process vs a pod of the production image ({fz['meta']['trials_per_cell']} vs {fp['meta']['trials_per_cell']} trials per cell)\n")
        T.append('| bit class | host: trials | host: wrong % | pod: trials | pod: wrong % | pod: wrong, missed by envelope | pod: wrong, missed by golden |')
        T.append('|---|---|---|---|---|---|---|')
        S['fuzz']['in_pod'] = {}
        for c in CLASSES + ['all']:
            ks = [k for k in cells if c == 'all' or cells[k]['class'] == c]
            h = {f: sum(cells[k][f] for k in ks) for f in ('trials', 'wrong')}
            p = {f: sum(fp['cells'][k][f] for k in ks) for f in ('trials', 'wrong', 'silent_wrong_env', 'silent_wrong_golden')}
            S['fuzz']['in_pod'][c] = {'host': h, 'pod': p}
            T.append(f"| {c} | {h['trials']} | {pct(h['wrong'], h['trials'])} | {p['trials']} | {pct(p['wrong'], p['trials'])} | {p['silent_wrong_env']} | {p['silent_wrong_golden']} |")
        S['fuzz']['in_pod']['control'] = fp['control']

# ------------------------------------------------------------------ 2. signed golden outputs
sg = jl('signed_golden_trials.jsonl')
if sg:
    S['signed'] = {}
    T.append('\n## Table X.3  Signed golden outputs vs the start-up reference (30 s window, 5 requests per second)\n')
    T.append('| condition | trials | wrong % | fallback (valid) % | correct % | failed % (transport resets) | semantic health | reference source | new pod Ready |')
    T.append('|---|---|---|---|---|---|---|---|---|')
    names = {'C0': 'healthy, signed reference', 'C1': 'corrupt at start-up, start-up reference', 'C2': 'corrupt at start-up, signed reference',
             'C3': 'golden.json tampered after signing', 'C4': 'model file differs from signed hash'}
    for cond in ('C0', 'C1', 'C2', 'C3', 'C4'):
        rows = [r for r in sg if r['cond'] == cond]
        if not rows:
            continue
        if cond in ('C3', 'C4'):
            nr = sum(1 for r in rows if r.get('new_pod_ready') is False)
            served = [r['served'] for r in rows]
            S['signed'][cond] = {'trials': len(rows), 'new_pod_never_ready': nr,
                                 'old_pod_correct_pct': round(st.mean(s['correct_pct'] for s in served), 1),
                                 'reasons': sorted({r['new_pod_reason'][:110] for r in rows})}
            T.append(f"| {names[cond]} | {len(rows)} | {round(st.mean(s['wrong_pct'] for s in served), 1)} | {round(st.mean(s['fallback_pct'] for s in served), 1)} | "
                     f"{round(st.mean(s['correct_pct'] for s in served), 1)} (served by the old pod) | {round(st.mean(s['failed_pct'] for s in served), 1)} | n/a | n/a | never Ready in {nr}/{len(rows)} |")
            continue
        w = [r['window'] for r in rows if 'window' in r]
        sem = [r.get('semantic_ok') for r in rows]
        unavailable = sum(1 for s in sem if s is None)
        S['signed'][cond] = {'trials': len(rows), 'wrong_pct': round(st.mean(x['wrong_pct'] for x in w), 1),
                             'fallback_pct': round(st.mean(x['fallback_pct'] for x in w), 1), 'correct_pct': round(st.mean(x['correct_pct'] for x in w), 1),
                             'degraded_pct': round(st.mean(x['degraded_pct'] for x in w), 1), 'failed_pct': round(st.mean(x['failed_pct'] for x in w), 1),
                             'semantic_ok_true': sum(1 for s in sem if s is True), 'semantic_ok_false': sum(1 for s in sem if s is False), 'semantic_unavailable': unavailable,
                             'sources': sorted({str(r.get('reference_source')) for r in rows if r.get('reference_source')}),
                             'wrong_trials': sum(1 for x in w if x['wrong_pct'] > 0)}
        d = S['signed'][cond]
        T.append(f"| {names[cond]} | {len(rows)} | {d['wrong_pct']} | {d['fallback_pct']} | {d['correct_pct']} | {d['failed_pct']} | OK {d['semantic_ok_true']}, not OK {d['semantic_ok_false']}, no reply {d['semantic_unavailable']} | {', '.join(d['sources'])} | yes |")
    c1, c2 = S['signed'].get('C1'), S['signed'].get('C2')
    if c1 and c2:
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        xs = ['corrupt at start-up\nstart-up reference', 'corrupt at start-up\nsigned reference']
        ax.bar(xs, [c1['wrong_pct'], c2['wrong_pct']], color=['#c0392b', '#27ae60'])
        ax.set_ylabel('wrong answers served (%)'); ax.set_ylim(0, 105); ax.set_title('Closing the trusted-start-up gap')
        plt.tight_layout(); plt.savefig(os.path.join(FIG, 'fig_signed_golden.png'), dpi=140); plt.close()

# ------------------------------------------------------------------ 3. rollback / escalation
rb = jl('rollback_trials.jsonl')
rb = [r for r in rb if 'error' not in r]
if rb:
    S['rollback'] = {}
    T.append('\n## Table X.4  Recovery of two fault classes under four operator policies\n')
    T.append('| fault | policy | trials | restored | median time to full quality (s) | mean failed % | actions taken (typical) |')
    T.append('|---|---|---|---|---|---|---|')
    for klass in ('transient', 'bad_release'):
        for pol in ('none', 'rules', 'release_aware', 'escalate'):
            rows = [r for r in rb if r['fault'] == klass and r['policy'] == pol]
            if not rows:
                continue
            rest = [r['restored_s'] for r in rows if r.get('restored_s') is not None]
            fails = [r['window']['failed_pct'] for r in rows]
            seq = max((tuple(r.get('actions') or []) for r in rows), key=lambda a: sum(1 for r in rows if tuple(r.get('actions') or []) == a), default=())
            S['rollback'][f'{klass}|{pol}'] = {'trials': len(rows), 'restored': len(rest), 'median_s': round(st.median(rest), 1) if rest else None,
                                               'mean_s': round(st.mean(rest), 1) if rest else None, 'mean_failed_pct': round(st.mean(fails), 1),
                                               'actions': list(seq), 'times': rest}
            T.append(f"| {klass} | {pol} | {len(rows)} | {len(rest)}/{len(rows)} | {round(st.median(rest), 1) if rest else 'never'} | {round(st.mean(fails), 1)} | {' -> '.join(seq) or 'none'} |")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for i, klass in enumerate(('transient', 'bad_release')):
        pols = [p for p in ('none', 'rules', 'release_aware', 'escalate') if f'{klass}|{p}' in S['rollback']]
        data = [S['rollback'][f'{klass}|{p}']['times'] for p in pols]
        for j, d in enumerate(data):
            ax[i].scatter([j] * len(d), d, color='#2c7fb8', zorder=3)
            nrest = len(d); ntr = S['rollback'][f'{klass}|{pols[j]}']['trials']
            ax[i].text(j, -8, f'{nrest}/{ntr} restored', ha='center', fontsize=8)
        ax[i].set_xticks(range(len(pols))); ax[i].set_xticklabels(pols); ax[i].set_ylabel('seconds to full quality'); ax[i].set_title(klass.replace('_', ' ') + ' fault')
        ax[i].set_ylim(-14, WIN if (WIN := 220) else 220); ax[i].axhline(0, color='k', lw=0.5)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, 'fig_rollback_restore.png'), dpi=140); plt.close()

json.dump(S, open(os.path.join(RES, 'new_extras_summary.json'), 'w'), indent=1)
open(os.path.join(RES, 'new_extras_tables.md'), 'w', encoding='utf8').write('\n'.join(T) + '\n')
print('\n'.join(T))
