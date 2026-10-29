#!/usr/bin/env python3
"""A1 ladder v2 (form vs idea) — analysis WRITTEN BEFORE THE DATA (protocol docs/A1_ESCADA_V2_V1.md).

Steps L4 and L5 only; arms: none | skeleton (a Lean worked example with the same proof skeleton and a mathematically
unrelated invariant) | content (the right idea in prose, no Lean). Unit = instance; p̂ = (k + ½)/(n + 1); bits = −log₂ p̂.
  P1 (primary)   mean over {L4, L5} of bits(none) − bits(skeleton); sign-flip over instances, one-sided (> 0)
  S1             mean over {L4, L5} of bits(none) − bits(content); one-sided (> 0)
  S2             mean over {L4, L5} of bits(content) − bits(skeleton); two-sided (form vs idea)
  S3, S4         skeleton effect at L4, L5; S5, S6 content effect at L4, L5; BH over S3–S6
Guards: prior_floor (none k = 0 at both steps in every instance), ceiling (k = n everywhere), instrument (> 10 % not observed).
Verdicts: close_no_skeleton_effect (P1 p ≥ .05 or a guard) | skeleton_saves_bits (P1 passes), with two qualifiers:
content_effect ∈ {also, not} (S1 p < .05) and form_vs_idea ∈ {skeleton_beats_content, content_beats_skeleton, undecided}
(S2 p < .05 and sign). Status: limite = close/guards; interessante = P1 passes; proveitoso = P1 passes and
form_vs_idea = skeleton_beats_content (the missing distance is the form of the proof, not the idea).
"""
from __future__ import annotations
import argparse, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import bh, boot_ci, signflip, t_ci  # noqa: E402
from analysis_a1 import NOT_OBSERVED, bits, counts, load, phat  # noqa: E402

STEPS = ["L4", "L5"]
ARMS = ("none", "skeleton", "content")


def contrast(values: dict, alt: str, label: str) -> dict:
    d = np.asarray([v for v in values.values() if v is not None], float)
    if len(d) == 0:
        return {"what": label, "alt": alt, "n": 0}
    sf = signflip(d, alt); lo, hi = boot_ci(d); m, tlo, thi = t_ci(d)
    return {"what": label, "alt": alt, "n": int(len(d)), "mean": sf["mean"], "p": sf["p"], "boot95": [lo, hi], "t95": [tlo, thi]}


def analyze_v2(plan, rows) -> dict:
    c = counts(rows); budget = plan.get("main_budget_label", "b8k"); inst = sorted({r["instance"] for r in rows})
    out = {"mode": "v2", "instances": inst, "n_sessions": len(rows), "n_not_observed": sum(1 for r in rows if r["status"] in NOT_OBSERVED),
           "cost_usd": round(sum(r["cost"] for r in rows), 2), "table": {}, "contrasts": {}}
    def nk(i, s, a):
        return c.get((i, s, a, budget), [0, 0])
    for i in inst:
        out["table"][i] = {s: {a: {"n": nk(i, s, a)[0], "k": nk(i, s, a)[1], "bits": (bits(*nk(i, s, a)) if nk(i, s, a)[0] else None)} for a in ARMS} for s in STEPS}
    def delta(i, s, a, b):   # bits(b) − bits(a): positive = a saves bits relative to b
        na, nb = nk(i, s, a), nk(i, s, b)
        return None if (na[0] == 0 or nb[0] == 0) else bits(*nb) - bits(*na)
    def per_instance(a, b, steps):
        vals = {}
        for i in inst:
            ds = [d for d in (delta(i, s, a, b) for s in steps) if d is not None]
            vals[i] = float(np.mean(ds)) if ds else None
        return vals
    C = out["contrasts"]
    C["P1"] = contrast(per_instance("skeleton", "none", STEPS), "greater", "bits(none) − bits(skeleton), mean L4–L5")
    C["S1"] = contrast(per_instance("content", "none", STEPS), "greater", "bits(none) − bits(content), mean L4–L5")
    C["S2"] = contrast(per_instance("skeleton", "content", STEPS), "two-sided", "bits(content) − bits(skeleton), mean L4–L5")
    C["S3"] = contrast(per_instance("skeleton", "none", ["L4"]), "greater", "skeleton effect at L4")
    C["S4"] = contrast(per_instance("skeleton", "none", ["L5"]), "greater", "skeleton effect at L5")
    C["S5"] = contrast(per_instance("content", "none", ["L4"]), "greater", "content effect at L4")
    C["S6"] = contrast(per_instance("content", "none", ["L5"]), "greater", "content effect at L5")
    fam = ["S3", "S4", "S5", "S6"]; ps = [C[k].get("p") for k in fam]
    if all(isinstance(x, float) for x in ps):
        for k, q in zip(fam, bh(ps)):
            C[k]["q_bh"] = float(q)
    pooled = {s: {a: [sum(nk(i, s, a)[1] for i in inst), sum(nk(i, s, a)[0] for i in inst)] for a in ARMS} for s in STEPS}
    out["pooled"] = pooled
    floor = all(nk(i, s, "none")[1] == 0 for i in inst for s in STEPS if nk(i, s, "none")[0]) if inst else False
    ceiling = all(nk(i, s, a)[1] == nk(i, s, a)[0] for i in inst for s in STEPS for a in ARMS if nk(i, s, a)[0]) if inst else False
    instr = out["n_not_observed"] > 0.10 * max(1, out["n_sessions"])
    out["guards"] = {"prior_floor": bool(floor), "ceiling": bool(ceiling), "instrument": bool(instr)}
    p1, s1, s2 = C["P1"], C["S1"], C["S2"]
    if p1.get("n", 0) == 0:
        v = "no_data"
    elif floor:
        v = "unmeasurable_prior_floor"
    elif ceiling:
        v = "unmeasurable_ceiling"
    elif instr or p1["p"] >= 0.05:
        v = "close_no_skeleton_effect"
    else:
        v = "skeleton_saves_bits"
    out["content_effect"] = "also" if (s1.get("n", 0) and s1["p"] < 0.05 and s1["mean"] > 0) else "not"
    out["form_vs_idea"] = ("skeleton_beats_content" if (s2.get("n", 0) and s2["p"] < 0.05 and s2["mean"] > 0)
                           else "content_beats_skeleton" if (s2.get("n", 0) and s2["p"] < 0.05 and s2["mean"] < 0) else "undecided")
    out["verdict"] = v
    out["status"] = ("proveitoso" if v == "skeleton_saves_bits" and out["form_vs_idea"] == "skeleton_beats_content"
                     else "interessante" if v == "skeleton_saves_bits" else "limite")
    return out


def render(out) -> str:
    def fmt(c):
        if c.get("n", 0) == 0:
            return f"{c['what']}: sem dados"
        q = f", q_BH = {c['q_bh']:.3f}" if "q_bh" in c else ""
        return f"{c['what']} ({c['alt']}, n = {c['n']}): {c['mean']:+.2f} bits [{c['boot95'][0]:+.2f}, {c['boot95'][1]:+.2f}] boot; p = {c['p']:.4f}{q}"
    L = ["# A1 v2 — forma vs ideia: leitura única (script escrito antes dos dados)", "",
         f"Sessões {out['n_sessions']}, não observadas {out['n_not_observed']}, custo ≈ US${out['cost_usd']}.", "",
         "## Taxas agrupadas (resolvidas/sessões)", "", "| degrau | nenhum | esqueleto | conteúdo |", "|---|---|---|---|"]
    for s in STEPS:
        L.append(f"| {s} | " + " | ".join(f"{out['pooled'][s][a][0]}/{out['pooled'][s][a][1]}" for a in ARMS) + " |")
    L += ["", "## Por instância (k:n por braço)", ""]
    for i, t in out["table"].items():
        L.append(f"- **{i}**: " + "; ".join(f"{s} " + "/".join(f"{a} {x['k']}:{x['n']}" for a, x in t[s].items() if x['n']) for s in STEPS))
    C = out["contrasts"]
    L += ["", "## Contrastes pré-registrados", ""] + [f"- **{k}**: {fmt(C[k])}" for k in ("P1", "S1", "S2", "S3", "S4", "S5", "S6")]
    L += ["", f"## Guardas: {json.dumps(out['guards'])}", "", f"## Veredito pré-declarado: `{out['verdict']}` — conteúdo: {out['content_effect']}; forma vs ideia: {out['form_vs_idea']} — status: **{out['status']}**", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", type=Path, required=True); p.add_argument("--run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plan, rows = load(a.plan, a.run); out = analyze_v2(plan, rows)
    a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("mode", "verdict", "content_effect", "form_vs_idea", "status", "n_sessions", "cost_usd")}, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
