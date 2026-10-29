#!/usr/bin/env python3
"""A2 consolidation, REPLICATION — analysis WRITTEN BEFORE THE DATA (docs/A2_CONSOLIDACAO_REPLICACAO_V1.md).
Same four-arm read as v1 (base, p1, p2, p3 on six held-out instances); plus two optional arms on L2 and L3 only:
baset (base with thinking on) and p2t (the p2 adapter with thinking on).
  P4 (form in weights + reasoning at inference fills the parameters): p2t rises at L2 against p2 AND against baset
     (same rise rule: sign-flip one-sided p < .05 over instances and pooled difference >= 0.25). Reported also at L3.
Replication verdict: `replicated` if the four-arm verdict is form_written_and_form_specific again; else the verdict found.
Four arms on the same held-out instances and steps: base (no adapter), p1 (curated skeleton of E and L5), p2 (curated
skeleton of all six steps), p3 (syntax control: same worlds, non-inductive target). Unit = held-out instance (6).
  rises(arm, step): paired difference of solve rates arm - base over instances, sign-flip one-sided p < .05 (minimum
                    0.0156 with six instances) AND pooled difference >= 0.25
  P1 confirmed: p1 rises at E or L5, and rises at none of L1, L2, L3, L4
  P2 confirmed: p2 rises at >= 4 of the six steps
  P3 clean:     p3 rises at no step (if p3 rises where p1/p2 rise, the gain is syntax, not form)
Verdicts: form_written_and_form_specific (P1 and P3 clean) | form_written_not_specific (p1 rises at some step outside
E/L5, P3 clean) | curriculum_only (P2 but not P1) | syntax_not_form (P3 not clean) | nothing_written (no arm rises
anywhere). Sessions with infrastructure failure are not observed. Descriptive: bits saved per arm and step.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import boot_ci, signflip  # noqa: E402
from analysis_a1 import bits, counts, load  # noqa: E402

STEPS6 = ["L1", "L2", "L3", "L4", "L5", "E"]
ARMS = ["base", "p1", "p2", "p3"]
THINK_ARMS = ["baset", "p2t"]


def analyze(plans: dict, rows: dict) -> dict:
    """plans/rows: arm -> (plan, rows) as loaded by analysis_a1.load (rows carry instance/step/arm/budget_label/solved).
    Thinking arms are optional (keys absent = not run)."""
    label = {a: (plans[a].get("main_budget_label") or "b16k") for a in ARMS}
    inst = sorted({r["instance"] for r in rows["base"]})
    c = {a: counts(rows[a]) for a in ARMS}
    def nk(a, i, s):
        return c[a].get((i, s, "none", label[a]), [0, 0])
    out = {"mode": "a2_consolidation", "instances": inst, "n_sessions": {a: len(rows[a]) for a in ARMS},
           "n_not_observed": {a: sum(1 for r in rows[a] if r["status"] in ("infrastructure_failure", "budget_accounting_error")) for a in ARMS},
           "rates": {}, "contrasts": {}, "rises": {}}
    for a in ARMS:
        out["rates"][a] = {}
        for s in STEPS6:
            n = sum(nk(a, i, s)[0] for i in inst); k = sum(nk(a, i, s)[1] for i in inst)
            out["rates"][a][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
    for a in ("p1", "p2", "p3"):
        out["contrasts"][a] = {}; out["rises"][a] = {}
        for s in STEPS6:
            d = []; db = []
            for i in inst:
                x, b = nk(a, i, s), nk("base", i, s)
                if x[0] and b[0]:
                    d.append(x[1] / x[0] - b[1] / b[0]); db.append(bits(*b) - bits(*x))
            d = np.asarray(d, float)
            if len(d):
                sf = signflip(d, "greater"); lo, hi = boot_ci(d)
                pooled = (out["rates"][a][s]["rate"] or 0) - (out["rates"]["base"][s]["rate"] or 0)
                rise = bool(sf["p"] < 0.05 and pooled >= 0.25)
                out["contrasts"][a][s] = {"n": int(len(d)), "mean_rate_diff": sf["mean"], "p": sf["p"], "boot95": [lo, hi], "pooled_diff": pooled,
                                          "bits_saved_mean": float(np.mean(db))}
            else:
                out["contrasts"][a][s] = {"n": 0}; rise = False
            out["rises"][a][s] = rise
    r1, r2, r3 = out["rises"]["p1"], out["rises"]["p2"], out["rises"]["p3"]
    p1_form = (r1["E"] or r1["L5"]) and not any(r1[s] for s in ("L1", "L2", "L3", "L4"))
    p1_any = any(r1.values()); p2_ok = sum(r2.values()) >= 4; p3_clean = not any(r3.values())
    out["rules"] = {"P1_form_specific": bool(p1_form), "P1_rises_anywhere": bool(p1_any), "P2_curriculum": bool(p2_ok), "P3_clean": bool(p3_clean)}
    if not p3_clean:
        v = "syntax_not_form"
    elif p1_form:
        v = "form_written_and_form_specific"
    elif p1_any:
        v = "form_written_not_specific"
    elif p2_ok:
        v = "curriculum_only"
    elif any(any(out["rises"][a].values()) for a in ("p1", "p2")):
        v = "partial_rise_below_rules"
    else:
        v = "nothing_written"
    out["verdict"] = v
    # --- P4: thinking arms on L2/L3 (optional)
    if all(a in rows for a in THINK_ARMS):
        lab = {a: (plans[a].get("main_budget_label") or "b16k") for a in THINK_ARMS}
        ct = {a: counts(rows[a]) for a in THINK_ARMS}
        def nkt(a, i, s):
            return ct[a].get((i, s, "none", lab[a]), [0, 0])
        out["think"] = {"n_sessions": {a: len(rows[a]) for a in THINK_ARMS}, "rates": {}, "contrasts": {}, "rises": {}}
        for a in THINK_ARMS:
            out["think"]["rates"][a] = {}
            for s in ("L2", "L3"):
                n = sum(nkt(a, i, s)[0] for i in inst); k = sum(nkt(a, i, s)[1] for i in inst)
                out["think"]["rates"][a][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
        def contrast(getx, gety, s):
            d = []
            for i in inst:
                x, y = getx(i, s), gety(i, s)
                if x[0] and y[0]:
                    d.append(x[1] / x[0] - y[1] / y[0])
            d = np.asarray(d, float)
            if not len(d):
                return {"n": 0}, False
            sf = signflip(d, "greater"); pooled = float(np.mean(d))
            return {"n": int(len(d)), "mean_rate_diff": sf["mean"], "p": sf["p"], "pooled_diff": pooled}, bool(sf["p"] < 0.05 and pooled >= 0.25)
        for s in ("L2", "L3"):
            c1, r1 = contrast(lambda i, s: nkt("p2t", i, s), lambda i, s: nk("p2", i, s), s)
            c2, r2 = contrast(lambda i, s: nkt("p2t", i, s), lambda i, s: nkt("baset", i, s), s)
            c3, r3 = contrast(lambda i, s: nkt("baset", i, s), lambda i, s: nk("base", i, s), s)
            out["think"]["contrasts"][s] = {"p2t_vs_p2": c1, "p2t_vs_baset": c2, "baset_vs_base": c3}
            out["think"]["rises"][s] = {"p2t_vs_p2": r1, "p2t_vs_baset": r2, "baset_vs_base": r3}
        out["rules"]["P4_form_plus_reasoning_L2"] = bool(out["think"]["rises"]["L2"]["p2t_vs_p2"] and out["think"]["rises"]["L2"]["p2t_vs_baset"])
    out["replication"] = "replicated" if v == "form_written_and_form_specific" else v
    return out


def render(out: dict) -> str:
    L = ["# A2 — consolidação da forma em pesos: leitura única (script escrito antes dos dados)", "",
         f"Instâncias retidas: {', '.join(out['instances'])}. Sessões por braço: {json.dumps(out['n_sessions'])}; não observadas: {json.dumps(out['n_not_observed'])}.", "",
         "## Taxas por braço e degrau (resolvidas/n)", "", "| braço | " + " | ".join(STEPS6) + " |", "|---|" + "---|" * len(STEPS6)]
    for a in ARMS:
        L.append(f"| {a} | " + " | ".join(f"{out['rates'][a][s]['k']}/{out['rates'][a][s]['n']}" for s in STEPS6) + " |")
    L += ["", "## Contrastes contra a base (diferença de taxa por instância; permutação por sinal, unilateral)", ""]
    for a in ("p1", "p2", "p3"):
        cells = []
        for s in STEPS6:
            c = out["contrasts"][a][s]
            cells.append("—" if not c.get("n") else f"{c['pooled_diff']:+.2f} (p = {c['p']:.3f}){' ↑' if out['rises'][a][s] else ''}")
        L.append(f"- **{a}**: " + "; ".join(f"{s} {x}" for s, x in zip(STEPS6, cells)))
    if out.get("think"):
        T = out["think"]; L += ["", "## Braços com pensamento em L2/L3 (P4)", "", "| braço | L2 | L3 |", "|---|---|---|"]
        L.append(f"| p2 (sem pensamento) | {out['rates']['p2']['L2']['k']}/{out['rates']['p2']['L2']['n']} | {out['rates']['p2']['L3']['k']}/{out['rates']['p2']['L3']['n']} |")
        for a in THINK_ARMS:
            L.append(f"| {a} | {T['rates'][a]['L2']['k']}/{T['rates'][a]['L2']['n']} | {T['rates'][a]['L3']['k']}/{T['rates'][a]['L3']['n']} |")
        for s in ("L2", "L3"):
            L.append(f"- {s}: " + "; ".join(f"{k} {c['pooled_diff']:+.2f} (p = {c['p']:.3f}){' ↑' if T['rises'][s][k] else ''}" if c.get("n") else f"{k} —" for k, c in T["contrasts"][s].items()))
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}` (replicação: `{out.get('replication')}`)", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ARMS:
        p.add_argument(f"--plan-{a}", type=Path, required=True); p.add_argument(f"--run-{a}", type=Path, required=True)
    for a in THINK_ARMS:
        p.add_argument(f"--plan-{a}", type=Path, default=None); p.add_argument(f"--run-{a}", type=Path, default=None)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plans, rows = {}, {}
    for arm in ARMS + THINK_ARMS:
        if getattr(a, f"plan_{arm}") is not None:
            plans[arm], rows[arm] = load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))
    out = analyze(plans, rows); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({"verdict": out["verdict"], "replication": out.get("replication"), "rules": out["rules"]}))


if __name__ == "__main__":
    main()
