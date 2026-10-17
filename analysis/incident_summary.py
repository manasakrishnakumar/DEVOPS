"""X24: template-based incident summariser (NOT an LLM). Turns operator history, benchmark rows and predictor results into
plain-language incident reports.  Writes results/incident_reports.md.   python analysis/incident_summary.py
"""
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rows(fn):
    p = os.path.join(ROOT, 'results', fn)
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


L = ['# Incident reports (generated from measured data; template-based, not an LLM)', '']
op = rows('operator_trials.jsonl')
for fault in ('corrupt', 'unitchange', 'flatline', 'scaler'):
    for pol in ('none', 'rules'):
        v = [r for r in op if r['fault'] == fault and r['policy'] == pol]
        if not v:
            continue
        rs = [r['restored_s'] for r in v if r.get('restored_s') is not None]
        fw = lambda k: statistics.mean(r['fault_window'][k] for r in v)
        act = ''
        for r in v:
            if r.get('operator_history'):
                act = r['operator_history'][:160]
                break
        if rs:
            outcome = f"Full quality was restored in a median of {statistics.median(rs):.1f} s ({len(rs)}/{len(v)} trials)."
        else:
            outcome = 'Full quality was never restored; the service stayed in the degraded tier until the fault was cleared by hand.'
        L += [f'## {fault} under policy `{pol}`',
              f'- What happened: a silent `{fault}` fault was injected into the forecasting model; the service kept answering HTTP 200.',
              f'- User impact during the 150 s window: {fw("correct_pct"):.0f} % correct, {fw("degraded_pct"):.0f} % degraded (valid but lower quality), '
              f'{fw("wrong_pct"):.0f} % wrong, {fw("failed_pct"):.1f} % failed.',
              f'- Response: {"operator restart" if pol != "none" else "no operator"}{(" (history: " + act + ")") if act else ""}.',
              f'- Outcome: {outcome}', '']
sb = rows('silentbench.jsonl')
for fault in ('bitflip', 'flatline'):
    c4 = [r for r in sb if r['config'] == 'C4' and r['fault'] == fault]
    e4 = [r for r in sb if r['config'] == 'E4' and r['fault'] == fault]
    if c4 and e4:
        L += [f'## {fault}: guard off vs guard on',
              f"- Guard off (C4): {statistics.mean(r['fault_window']['wrong_pct'] for r in c4):.0f} % wrong answers served, detected in "
              f"{sum(r.get('detect_s') is not None for r in c4)}/{len(c4)} trials.",
              f"- Guard on (E4): {statistics.mean(r['fault_window']['wrong_pct'] for r in e4):.0f} % wrong, "
              f"{statistics.mean(r['fault_window']['degraded_pct'] for r in e4):.0f} % degraded, detected in "
              f"{sum(r.get('detect_s') is not None for r in e4)}/{len(e4)} trials.", '']
pr = os.path.join(ROOT, 'results', 'predictor_results.json')
if os.path.exists(pr):
    d = json.load(open(pr))
    for kind, v in d['scenarios'].items():
        s = v['summary']
        L += [f'## precursor warning: {kind}',
              f"- Isolation Forest alarmed before the failure in {s['iforest_lead_s']['early_before_failure']} runs "
              f"(median lead {s['iforest_lead_s']['median_lead_s']} s); a static memory threshold gave {s['memory_threshold_lead_s']['early_before_failure']}; "
              f"the reactive guard gave {s['reactive_guard_lead_s']['early_before_failure']}.", '']
open(os.path.join(ROOT, 'results', 'incident_reports.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('wrote results/incident_reports.md with', sum(1 for l in L if l.startswith('## ')), 'reports')
