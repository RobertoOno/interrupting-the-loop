#!/usr/bin/env python3
"""A1 v3 (self-ladder) — analysis WRITTEN BEFORE THE DATA (protocol docs/A1_ESCADA_PROPRIA_V3_V1.md).

Stage 1: the easy same-form world E, none arm (the model's own verified proofs). Stage 2: L4 and L5 with arms
none | own (SOURCE.md = the model's own verified proof of E) | reference (SOURCE.md = E's reference proof, same format).
Unit = instance; p̂ = (k + ½)/(n + 1); bits = −log₂ p̂. Instances without a verified own proof have no own cells: they
count in the chain (P_E = 0 contribution) but not in the paired own contrasts (reported).
  P1 (primary)  mean over {L4, L5} of bits(none) − bits(own); sign-flip over instances, one-sided (> 0)
  S1            mean over {L4, L5} of bits(reference) − bits(own); two-sided (own vs curated)
  S2            mean over {L4, L5} of bits(none) − bits(reference); one-sided
  S3–S6         own effect at L4, L5; reference effect at L4, L5; BH over the four
  chain         P_chain(L5) = p̂_E(none) · p̂_L5(own) per instance (two sessions: solve E, then L5 with the own proof);
                P_width(L5) = 1 − (1 − p̂_L5(none))² (two sessions at L5 alone); same for L4. Descriptive means.
Guards: prior_floor (none k = 0 at both steps everywhere); ceiling; instrument (> 10 % not observed); stage1_floor
(no instance produced a verified own proof of E: the self-ladder has no first rung).
Verdicts: close_no_own_effect (P1 p ≥ .05 or a guard) | own_saves_bits, qualifier own_vs_reference ∈
{own_matches_reference (S1 p ≥ .05 and |mean| < 0.5 bits), reference_better, own_better, undecided}.
Status: limite = close/guards; interessante = P1 passes; proveitoso = P1 passes and mean P_chain(L5) > mean P_width(L5)
(the model climbs on its own verified proof better than it would by trying the top twice).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import bh, boot_ci, signflip, t_ci  # noqa: E402
from analysis_a1 import NOT_OBSERVED, bits, counts, load, phat  # noqa: E402

STEPS = ["L4", "L5"]
ARMS = ("none", "own", "reference")


def contrast(values: dict, alt: str, label: str) -> dict:
    d = np.asarray([v for v in values.values() if v is not None], float)
    if len(d) == 0:
        return {"what": label, "alt": alt, "n": 0}
    sf = signflip(d, alt); lo, hi = boot_ci(d); m, tlo, thi = t_ci(d)
    return {"what": label, "alt": alt, "n": int(len(d)), "mean": sf["mean"], "p": sf["p"], "boot95": [lo, hi], "t95": [tlo, thi]}


def analyze_v3(plan2, rows2, plan1=None, rows1=None) -> dict:
    c = counts(rows2); budget = plan2.get("main_budget_label", "b8k"); inst = sorted({r["instance"] for r in rows2})
    c1 = counts(rows1 or [])
    out = {"mode": "v3", "instances": inst, "n_sessions": len(rows2) + len(rows1 or []), "n_not_observed": sum(1 for r in (rows2 + (rows1 or [])) if r["status"] in NOT_OBSERVED),
           "cost_usd": round(sum(r["cost"] for r in rows2 + (rows1 or [])), 2), "table": {}, "contrasts": {}, "stage1": {}}
    def nk(i, s, a):
        return c.get((i, s, a, budget), [0, 0])
    def nkE(i):
        return c1.get((i, "E", "none", budget), [0, 0])
    for i in inst:
        out["stage1"][i] = {"n": nkE(i)[0], "k": nkE(i)[1]}
        out["table"][i] = {s: {a: {"n": nk(i, s, a)[0], "k": nk(i, s, a)[1], "bits": (bits(*nk(i, s, a)) if nk(i, s, a)[0] else None)} for a in ARMS} for s in STEPS}
    def delta(i, s, a, b):
        na, nb = nk(i, s, a), nk(i, s, b)
        return None if (na[0] == 0 or nb[0] == 0) else bits(*nb) - bits(*na)
    def per_instance(a, b, steps):
        vals = {}
        for i in inst:
            ds = [d for d in (delta(i, s, a, b) for s in steps) if d is not None]
            vals[i] = float(np.mean(ds)) if ds else None
        return vals
    C = out["contrasts"]
    C["P1"] = contrast(per_instance("own", "none", STEPS), "greater", "bits(none) − bits(own), mean L4–L5")
    C["S1"] = contrast(per_instance("own", "reference", STEPS), "two-sided", "bits(reference) − bits(own), mean L4–L5")
    C["S2"] = contrast(per_instance("reference", "none", STEPS), "greater", "bits(none) − bits(reference), mean L4–L5")
    C["S3"] = contrast(per_instance("own", "none", ["L4"]), "greater", "own effect at L4")
    C["S4"] = contrast(per_instance("own", "none", ["L5"]), "greater", "own effect at L5")
    C["S5"] = contrast(per_instance("reference", "none", ["L4"]), "greater", "reference effect at L4")
    C["S6"] = contrast(per_instance("reference", "none", ["L5"]), "greater", "reference effect at L5")
    fam = ["S3", "S4", "S5", "S6"]; ps = [C[k].get("p") for k in fam]
    if all(isinstance(x, float) for x in ps):
        for k, q in zip(fam, bh(ps)):
            C[k]["q_bh"] = float(q)
    out["pooled"] = {s: {a: [sum(nk(i, s, a)[1] for i in inst), sum(nk(i, s, a)[0] for i in inst)] for a in ARMS} for s in STEPS}
    out["pooled"]["E"] = {"none": [sum(nkE(i)[1] for i in inst), sum(nkE(i)[0] for i in inst)]}
    chain, width = {}, {}
    for s in STEPS:
        chain[s] = {i: (phat(*nkE(i)) if nkE(i)[0] else 0.0) * (phat(*nk(i, s, "own")) if nk(i, s, "own")[0] else 0.0) for i in inst if nkE(i)[0]}
        width[s] = {i: 1 - (1 - phat(*nk(i, s, "none"))) ** 2 for i in inst if nk(i, s, "none")[0]}
    out["chain_vs_width"] = {s: {"mean_chain": float(np.mean(list(chain[s].values()))) if chain[s] else None, "mean_width": float(np.mean(list(width[s].values()))) if width[s] else None,
                                 "chain": chain[s], "width": width[s]} for s in STEPS}
    floor = all(nk(i, s, "none")[1] == 0 for i in inst for s in STEPS if nk(i, s, "none")[0]) if inst else False
    ceiling = all(nk(i, s, a)[1] == nk(i, s, a)[0] for i in inst for s in STEPS for a in ARMS if nk(i, s, a)[0]) if inst else False
    instr = out["n_not_observed"] > 0.10 * max(1, out["n_sessions"])
    stage1_floor = bool(inst) and all(nkE(i)[1] == 0 for i in inst)
    out["guards"] = {"prior_floor": bool(floor), "ceiling": bool(ceiling), "instrument": bool(instr), "stage1_floor": stage1_floor,
                     "instances_without_own": [i for i in inst if not nk(i, "L5", "own")[0]]}
    p1, s1 = C["P1"], C["S1"]
    if p1.get("n", 0) == 0:
        v = "no_data" if not stage1_floor else "unmeasurable_stage1_floor"
    elif floor:
        v = "unmeasurable_prior_floor"
    elif ceiling:
        v = "unmeasurable_ceiling"
    elif instr or p1["p"] >= 0.05:
        v = "close_no_own_effect"
    else:
        v = "own_saves_bits"
    if s1.get("n", 0) == 0:
        q = "undecided"
    elif s1["p"] >= 0.05 and abs(s1["mean"]) < 0.5:
        q = "own_matches_reference"
    elif s1["p"] < 0.05:
        # S1 = bits(reference) − bits(own): positive means the OWN proof saves more bits. Label mapping corrected on
        # 2026-09-13 08:10 after the read showed the inverted label; no number, verdict or status depends on it.
        q = "own_better" if s1["mean"] > 0 else "reference_better"
    else:
        q = "undecided"
    out["own_vs_reference"] = q; out["verdict"] = v
    cw = out["chain_vs_width"]["L5"]
    out["status"] = ("proveitoso" if v == "own_saves_bits" and cw["mean_chain"] is not None and cw["mean_width"] is not None and cw["mean_chain"] > cw["mean_width"]
                     else "interessante" if v == "own_saves_bits" else "limite")
    return out


def render(out) -> str:
    def fmt(c):
        if c.get("n", 0) == 0:
            return f"{c['what']}: sem dados"
        q = f", q_BH = {c['q_bh']:.3f}" if "q_bh" in c else ""
        return f"{c['what']} ({c['alt']}, n = {c['n']}): {c['mean']:+.2f} bits [{c['boot95'][0]:+.2f}, {c['boot95'][1]:+.2f}] boot; p = {c['p']:.4f}{q}"
    L = ["# A1 v3 — escada própria: leitura única (script escrito antes dos dados)", "",
         f"Sessões {out['n_sessions']} (etapas 1 e 2), não observadas {out['n_not_observed']}, custo ≈ US${out['cost_usd']}.", "",
         "## Etapa 1 (E, sem exemplo): provas próprias verificadas", "", "| instância | resolvidas | n |", "|---|---|---|"]
    for i, e in out["stage1"].items():
        L.append(f"| {i} | {e['k']} | {e['n']} |")
    L += ["", "## Etapa 2, taxas agrupadas (resolvidas/sessões)", "", "| degrau | nenhum | própria | referência |", "|---|---|---|---|"]
    for s in STEPS:
        L.append(f"| {s} | " + " | ".join(f"{out['pooled'][s][a][0]}/{out['pooled'][s][a][1]}" for a in ARMS) + " |")
    L += ["", "## Por instância (k:n por braço)", ""]
    for i, t in out["table"].items():
        L.append(f"- **{i}**: " + "; ".join(f"{s} " + "/".join(f"{a} {x['k']}:{x['n']}" for a, x in t[s].items() if x['n']) for s in STEPS))
    C = out["contrasts"]
    L += ["", "## Contrastes pré-registrados", ""] + [f"- **{k}**: {fmt(C[k])}" for k in ("P1", "S1", "S2", "S3", "S4", "S5", "S6")]
    cw = out["chain_vs_width"]
    L += ["", "## Escada própria vs largura (duas sessões cada; descritivo)", ""] + [f"- {s}: P_escada média {cw[s]['mean_chain']} vs P_largura média {cw[s]['mean_width']}" for s in STEPS]
    L += ["", f"## Guardas: {json.dumps(out['guards'])}", "", f"## Veredito pré-declarado: `{out['verdict']}` — própria vs referência: {out['own_vs_reference']} — status: **{out['status']}**", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", type=Path, required=True); p.add_argument("--run", type=Path, required=True)
    p.add_argument("--stage1-plan", type=Path, default=None); p.add_argument("--stage1-run", type=Path, default=None)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plan2, rows2 = load(a.plan, a.run)
    plan1, rows1 = (load(a.stage1_plan, a.stage1_run) if a.stage1_plan else (None, None))
    out = analyze_v3(plan2, rows2, plan1, rows1)
    a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("mode", "verdict", "own_vs_reference", "status", "n_sessions", "cost_usd")}, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
