"""Recomputes every novelty claim of the report from the raw result files (results/*.jsonl|json) and compares it with the reported value.
Usage: python validation/validate_novelty.py   (no cluster needed)"""
import json, os, statistics as st, sys, math
R = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
def jl(n):
    p = os.path.join(R, n)
    return [json.loads(l) for l in open(p, encoding="utf8") if l.strip().startswith("{")]
def js(n): return json.load(open(os.path.join(R, n), encoding="utf8"))
res = []
def chk(nov, claim, got, exp, tol=1.0):
    ok = abs(got - exp) <= tol if isinstance(exp, (int, float)) else got == exp
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {claim}: computed={got}  report={exp}")
mean = lambda x: round(sum(x)/len(x), 2) if x else None

# ---------------- N1 SilentBench + HBW/MTTC
print("N1  SilentBench + HBW/MTTC (silentbench.jsonl, hbw_mttc.json)")
sb = [r for r in jl("silentbench.jsonl") if r.get("fault") != "none"]
def cell(cfg, f): return [r for r in sb if r["config"] == cfg and r["fault"] == f]
silent = ["corrupt","unitchange","flatline","scaler","stale","bitflip","bitflip_severe"]
for f in silent:
    c = cell("C4", f)
    chk(1, f"C4 {f}: wrong% (n={len(c)}), detected={sum(1 for r in c if r.get('detect_s') is not None and r['fault_window']['wrong_pct']<100)}", mean([r["fault_window"]["wrong_pct"] for r in c]), 100.0, 0.5)
g = [r for f in silent for r in cell("G4", f)]
chk(1, f"G4 all 7 silent faults mean wrong% over {len(g)} trials", mean([r["fault_window"]["wrong_pct"] for r in g]), 0.0, 0.01)
h = js("hbw_mttc.json")
chk(1, "HBW C4 corrupt (s)", h["C4|corrupt"]["hbw_s_mean"], 30.0, 0.01)
chk(1, "HBW G4 corrupt (s)", h["G4|corrupt"]["hbw_s_mean"], 0.0, 0.01)
chk(1, "HBW E4 bitflip (s)", h["E4|bitflip"]["hbw_s_mean"], 30.0, 0.01)

# ---------------- N2 probe design
print("N2  Correctness-aware probe design (extras_cluster.jsonl)")
ex = jl("extras_cluster.jsonl")
exps = sorted(set((r["exp"], r.get("variant")) for r in ex)); print("   experiments found:", exps)
def grp(exp, variant=None, fault=None):
    return [r for r in ex if r["exp"] == exp and (variant is None or r.get("variant") == variant) and (fault is None or r.get("fault") == fault)]
for var in ("D1_default", "D3_semantic_readiness", "D2_semantic_readiness_and_liveness"):
    g2 = grp("e1_semantic_probes", var)
    rest = [r["restored_s"] for r in g2 if r.get("restored_s") is not None]
    fp = mean([r["fault_window"]["failed_pct"] for r in g2])
    print(f"   {var}: trials={len(g2)} restored={len(rest)}/{len(g2)} median_restored_s={st.median(rest) if rest else None} failed%={fp}")
d3 = grp("e1_semantic_probes", "D3_semantic_readiness"); d2 = grp("e1_semantic_probes", "D2_semantic_readiness_and_liveness")
chk(2, "readiness alone: mean failed% (report ~92)", mean([r["fault_window"]["failed_pct"] for r in d3]), 92.0, 2.0)
chk(2, "readiness alone: restored trials", sum(1 for r in d3 if r.get("restored_s") is not None), 0, 0)
chk(2, "readiness+liveness: median restoration s (report 36)", st.median([r["restored_s"] for r in d2 if r.get("restored_s") is not None]), 36.0, 2.0)
pr = [r for r in ex if "partial" in r["exp"].lower() or "partial" in str(r.get("variant")).lower() or r["exp"].startswith("e2")]
for v in sorted(set(r.get("variant") for r in pr)):
    vv = [r for r in pr if r.get("variant") == v]
    print(f"   partial-readiness {v}: trials={len(vv)} failed%={mean([r['fault_window']['failed_pct'] for r in vv])}")
strict = [r for r in pr if "strict" in str(r.get("variant")).lower()]; part = [r for r in pr if "partial" in str(r.get("variant")).lower()]
if strict and part:
    chk(2, "strict readiness failed% (report 81)", mean([r["fault_window"]["failed_pct"] for r in strict]), 81.0, 2.0)
    chk(2, "partial readiness failed% (report 0)", mean([r["fault_window"]["failed_pct"] for r in part]), 0.0, 0.5)

# ---------------- N3 compound faults
print("N3  Compound faults (compound_faults.json)")
cf = js("compound_faults.json")
chk(3, "E4 bitflip+delay wrong%", cf["E4|bitflip+delay"]["wrong_pct"], 100.0, 0.1)
chk(3, "G4 bitflip+delay wrong%", cf["G4|bitflip+delay"]["wrong_pct"], 0.0, 0.1)
chk(3, "G4 bitflip+delay p95 ms (report 1615)", cf["G4|bitflip+delay"]["p95_ms"], 1615, 5)
chk(3, "H4 bitflip+delay wrong%", cf["H4|bitflip+delay"]["wrong_pct"], 0.0, 0.1)
chk(3, "H4 bitflip+delay p95 ms (report 768)", cf["H4|bitflip+delay"]["p95_ms"], 768, 5)

# ---------------- N4 baselines / cost-coverage
print("N4  Baselines and cost-coverage (baselines_pareto.json)")
bp = js("baselines_pareto.json"); print("   keys:", list(bp.keys()))
chk(4, "range check detects bitflip %", bp["detection_pct"]["bitflip"]["range"], 0.0, 0.01)
chk(4, "golden detects bitflip %", bp["detection_pct"]["golden"] if False else bp["detection_pct"]["bitflip"]["golden"], 100.0, 0.01)
chk(4, "envelope detects bitflip % (report 2.5)", bp["detection_pct"]["bitflip"]["envelope"], 2.5, 0.01)
for k in bp:
    if "false" in k.lower(): print("   ", k, bp[k]); fa = bp[k]; chk(4, "z-score false alarms % (report 12.3)", fa.get("zscore3"), 12.3, 0.1)
for k in bp:
    if "cost" in k.lower() or "ms" in k.lower(): print("   ", k, bp[k])

# ---------------- N5 operator / quality-aware recovery
print("N5  Quality-aware recovery (operator_trials*.jsonl)")
op = jl("operator_trials.jsonl")
for pol in ("none", "rules", "bandit"):
    o = [r for r in op if r["policy"] == pol]
    rest = [r["restored_s"] for r in o if r.get("restored_s") is not None]
    print(f"   policy={pol}: trials={len(o)} restored={len(rest)}  mean_s={mean(rest)}  tags={sorted(set(r.get('image_tag') for r in o))}")
none = [r for r in op if r["policy"] == "none"]; rules = [r for r in op if r["policy"] == "rules"]; ban = [r for r in op if r["policy"] == "bandit"]
chk(5, "no operator: restored trials (report 0/20)", sum(1 for r in none if r.get("restored_s") is not None), 0, 0)
chk(5, "rules: restored trials (report 20/20)", sum(1 for r in rules if r.get("restored_s") is not None), 20, 0)
chk(5, "rules: mean restoration s (report 23.6)", mean([r["restored_s"] for r in rules if r.get("restored_s") is not None]), 23.6, 1.5)
v1 = jl("operator_trials_bandit_v1_superseded.jsonl")
chk(5, "bandit v1 (cost-blind) restored trials (report 5/20)", sum(1 for r in v1 if r.get("restored_s") is not None), 5, 0)
b2 = [r for r in ban if r.get("restored_s") is not None]
chk(5, "bandit v2 restored trials (report 20/20)", len(b2) if len(b2) >= 20 else len(b2), 20, 0)
chk(5, "bandit v2 mean restoration s (report 21.6)", mean([r["restored_s"] for r in b2]), 21.6, 1.5)

# ---------------- N6 deadline-aware degradation
print("N6  Deadline/load-aware degradation (silentbench.jsonl delay, G4 vs H4)")
for cfg in ("G4", "H4"):
    d = [r for r in sb if r["config"] == cfg and r["fault"] == "delay"]
    print(f"   {cfg} delay: trials={len(d)} failed%={mean([r['fault_window']['failed_pct'] for r in d])} degraded%={mean([r['fault_window']['degraded_pct'] for r in d])} wrong%={mean([r['fault_window']['wrong_pct'] for r in d])} p95={mean([r['fault_window']['p95_ms'] for r in d])}")
dg = [r for r in sb if r["config"] == "G4" and r["fault"] == "delay"]; dh = [r for r in sb if r["config"] == "H4" and r["fault"] == "delay"]
chk(6, "G4 delay failed% (report 96.8)", mean([r["fault_window"]["failed_pct"] for r in dg]), 96.8, 0.6)
chk(6, "H4 delay failed% (report 0)", mean([r["fault_window"]["failed_pct"] for r in dh]), 0.0, 0.3)
chk(6, "H4 delay degraded% (report 94)", mean([r["fault_window"]["degraded_pct"] for r in dh]), 94.0, 1.5)

# ---------------- statistics helper: exact one-sided 95% upper bound for 0 wrong in n trials
print("EXACT BINOMIAL one-sided 95% upper bound for 0 events in n trials (replaces degenerate [0,0] bootstrap CI)")
for n in (5, 9, 10): print(f"   n={n}: {100*(1-0.05**(1/n)):.1f}%")
print(f"\nSUMMARY: {sum(res)}/{len(res)} checks passed")
sys.exit(0 if all(res) else 1)
