#!/usr/bin/env python3
"""A2 sem curador, ITERATION 2 — analysis WRITTEN BEFORE THE DATA (docs/A2_SEM_CURADOR_ITER2_V1.md).
Does the ladder climb without a curator? The iteration-1 adapter (own) with reasoning produced proofs at L4/L5/E of the training
instances; the cumulative set (60 prior + new) was consolidated into own2 (and the curated rows of the same cells into curm2).
Arms on the six held-out instances (same cells as before):
  six steps, no thinking: base, p2 (curated six forms), own (iteration 1), own2, curm2
  thinking 131k:          baset (L2/L3 from 14/09 + L4/L5/E new comparator), p2t (L2/L3), ownt (iteration 1, L2/L3), own2t and curm2t (L2..E)
rise(x, y, s): paired difference of solve rates over the six instances, sign-flip one-sided p < .05 (minimum 0.0156) AND pooled
difference >= 0.25; fall: the mirror.
  P_climb_think: own2t rises against baset at L4, L5 or E        (own proofs of the new steps, consolidated + reasoning, beat reasoning alone)
  P_climb_plain: own2 rises against base at L4, L5 or E
  retention_fall: own2t falls against ownt at L2 or L3, or own2 falls against own at L1   (descriptive: did the new data erase the old form)
  curation_value: curm2 rises against own2 at some step, or curm2t against own2t (descriptive)
Verdicts: ladder_climbs_without_curator (P_climb_think or P_climb_plain) | consolidation_does_not_climb (proofs were produced and
consolidated, nothing rises at L4/L5/E). The production gate (>= 12 new verified proofs) is applied BEFORE training; if it fails the node
closes as stalls_at_production without this read. Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import signflip  # noqa: E402
from analysis_a1 import counts, load  # noqa: E402

STEPS6 = ["L1", "L2", "L3", "L4", "L5", "E"]
SIX = ["base", "p2", "own", "own2", "curm2"]
THINK = ["baset", "p2t", "ownt", "own2t", "curm2t"]
ARMS = SIX + THINK
HIGH = ["L4", "L5", "E"]


def analyze(plans: dict, rows: dict, n_new: int | None, n_own: int | None) -> dict:
    inst = sorted({r["instance"] for r in rows["base"]})
    label = {a: (plans[a].get("main_budget_label") or "b16k") for a in ARMS}
    c = {a: counts(rows[a]) for a in ARMS}
    def nk(a, i, s):
        return c[a].get((i, s, "none", label[a]), [0, 0])
    out = {"mode": "a2_own_consolidation_iteration2", "instances": inst, "n_new_examples": n_new, "n_own_examples": n_own,
           "n_sessions": {a: len(rows[a]) for a in ARMS},
           "n_not_observed": {a: sum(1 for r in rows[a] if r["status"] in ("infrastructure_failure", "budget_accounting_error")) for a in ARMS},
           "rates": {a: {} for a in ARMS}, "contrasts": {}, "rises": {}, "falls": {}}
    for a in ARMS:
        for s in STEPS6:
            n = sum(nk(a, i, s)[0] for i in inst); k = sum(nk(a, i, s)[1] for i in inst)
            if n:
                out["rates"][a][s] = {"n": n, "k": k, "rate": k / n}
    def contrast(x, y, s):
        d = []
        for i in inst:
            a, b = nk(x, i, s), nk(y, i, s)
            if a[0] and b[0]:
                d.append(a[1] / a[0] - b[1] / b[0])
        d = np.asarray(d, float)
        if not len(d):
            return {"n": 0}, False, False
        up = signflip(d, "greater"); down = signflip(-d, "greater"); pooled = float(np.mean(d))
        return ({"n": int(len(d)), "mean_rate_diff": up["mean"], "p_greater": up["p"], "p_less": down["p"], "pooled_diff": pooled},
                bool(up["p"] < 0.05 and pooled >= 0.25), bool(down["p"] < 0.05 and pooled <= -0.25))
    pairs = [("own2", "base"), ("own2", "own"), ("curm2", "base"), ("curm2", "own2"), ("own2", "p2"),
             ("own2t", "baset"), ("curm2t", "baset"), ("curm2t", "own2t"), ("own2t", "ownt"), ("own2t", "p2t"), ("own2t", "own2")]
    for s in STEPS6:
        out["contrasts"][s] = {}; out["rises"][s] = {}; out["falls"][s] = {}
        for x, y in pairs:
            cc, r, f = contrast(x, y, s); key = f"{x}_vs_{y}"
            out["contrasts"][s][key] = cc; out["rises"][s][key] = r; out["falls"][s][key] = f
    R, F = out["rises"], out["falls"]
    climb_think = bool(any(R[s]["own2t_vs_baset"] for s in HIGH))
    climb_plain = bool(any(R[s]["own2_vs_base"] for s in HIGH))
    retention = bool(F["L2"]["own2t_vs_ownt"] or F["L3"]["own2t_vs_ownt"] or F["L1"]["own2_vs_own"])
    cur_val = bool(any(R[s]["curm2_vs_own2"] for s in STEPS6) or any(R[s]["curm2t_vs_own2t"] for s in STEPS6))
    cur_climbs = bool(any(R[s]["curm2_vs_base"] for s in HIGH) or any(R[s]["curm2t_vs_baset"] for s in HIGH))
    out["rules"] = {"P_climb_think": climb_think, "P_climb_plain": climb_plain, "retention_fall": retention, "curation_value": cur_val, "curated_matched_climbs": cur_climbs}
    out["verdict"] = "ladder_climbs_without_curator" if (climb_think or climb_plain) else "consolidation_does_not_climb"
    return out


def render(out: dict) -> str:
    L = ["# A2 sem curador, iteração 2 — leitura única (script escrito antes dos dados)", "",
         f"Instâncias retidas: {', '.join(out['instances'])}. Exemplos próprios: {out['n_own_examples']} (novos nesta iteração: {out['n_new_examples']}). Sessões por braço: {json.dumps(out['n_sessions'])}; não observadas: {json.dumps(out['n_not_observed'])}.", "",
         "## Taxas por braço e degrau (resolvidas/n)", "", "| braço | " + " | ".join(STEPS6) + " |", "|---|" + "---|" * len(STEPS6)]
    for a in ARMS:
        L.append(f"| {a} | " + " | ".join((f"{out['rates'][a][s]['k']}/{out['rates'][a][s]['n']}" if s in out["rates"][a] else "—") for s in STEPS6) + " |")
    L += ["", "## Contrastes (diferença de taxa por instância; permutação por sinal, unilateral; ↑ subida, ↓ queda pela regra)", ""]
    for s in STEPS6:
        parts = []
        for k, cc in out["contrasts"][s].items():
            if not cc.get("n"):
                continue
            mark = " ↑" if out["rises"][s][k] else (" ↓" if out["falls"][s][k] else "")
            parts.append(f"{k} {cc['pooled_diff']:+.2f} (p = {cc['p_greater']:.3f}){mark}")
        L.append(f"- **{s}**: " + ("; ".join(parts) if parts else "—"))
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ARMS:
        p.add_argument(f"--plan-{a}", type=Path, required=True); p.add_argument(f"--run-{a}", type=Path, required=True)
    p.add_argument("--plan-baset2", type=Path, default=None); p.add_argument("--run-baset2", type=Path, default=None)   # the L4/L5/E comparator run, merged into baset
    p.add_argument("--n-new-examples", type=int, default=None); p.add_argument("--n-own-examples", type=int, default=None)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plans, rows = {}, {}
    for arm in ARMS:
        plans[arm], rows[arm] = load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))
    if a.plan_baset2 is not None:
        p2, r2 = load(a.plan_baset2, a.run_baset2)
        assert (p2.get("main_budget_label") or "b16k") == (plans["baset"].get("main_budget_label") or "b16k"), "baset runs must share the budget label"
        rows["baset"] = rows["baset"] + r2
    out = analyze(plans, rows, a.n_new_examples, a.n_own_examples); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({"verdict": out["verdict"], "rules": out["rules"]}))


if __name__ == "__main__":
    main()
