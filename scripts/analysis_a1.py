#!/usr/bin/env python3
"""A1 (sibling ladder) — analysis WRITTEN BEFORE THE DATA (protocol docs/A1_ESCADA_DE_IRMAOS_V1.md).

Input: a plan JSON and its run directory (one result.json per cell, from ladder_runner_v1). Unit = instance
(a seeded sibling family of five steps). Outcome per session: solved (verified proof) or not; sessions with
infrastructure failure are NOT observations (excluded, counted).

Estimates. For (instance, step, arm): n sessions, k solved; p̂ = (k + 1/2) / (n + 1) (Krichevsky–Trofimov,
declared before data so that 0/n and n/n stay finite); bits = -log2 p̂ = "distance in bits" per attempt.
  P1 (primary, main)  mean over steps L2..L5 of [bits(none) - bits(ladder)] per instance; sign-flip
                      permutation over instances, one-sided (> 0: the previous step's proof saves bits)
  S1                  bits(sham) - bits(ladder), same aggregation, one-sided (adjacent example beats generic)
  S2..S5              the per-step none - ladder contrasts (L2..L5), one-sided, BH over the four
  chain vs width      P_chain = p̂_1(none) * Π_{k>=2} p̂_k(ladder); P_width = 1 - (1 - p̂_5(none))^5 (five sessions
                      spent at the top alone); descriptive, per instance and mean. Assumes the model's own verified
                      proof works as well as the reference proof used as the example (stated limitation).
Guards (death criteria, declared): 'prior_floor' if p̂(none) has k = 0 at every step >= 2 in every instance;
'ceiling' if k = n at every step in every instance; 'instrument' if > 10 % of sessions are infrastructure failures.
Verdicts: close_no_bits_saved (P1 p >= .05, or a guard) | ladder_saves_bits_not_beyond_sham (P1 passes, S1 not)
| ladder_saves_bits_beyond_generic_example (both pass). Status: limite = close/guards; interessante = P1 passes;
proveitoso = P1 and S1 pass and mean P_chain > mean P_width.
Pilot mode (--pilot): none-arm pass rates by step and budget; the pre-declared budget rule (see protocol) and
the gradient check p̂(L1) > p̂(L5); no verdict on the ladder.
"""
from __future__ import annotations
import argparse, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from creative_machine.paired_stats import bh, boot_ci, signflip, t_ci  # noqa: E402

STEPS = ["L1", "L2", "L3", "L4", "L5"]
# Not observed = the provider or the accounting failed. `budget_exhausted` is the session's OWN output cap reached
# without a verified proof (a failed attempt, observed), like output_limit / turn_limit / timeout; corrected on
# 2026-09-12 23:15, before any read, when the first such session appeared in the pilot.
NOT_OBSERVED = {"infrastructure_failure", "budget_accounting_error"}


def load(plan_path: Path, run_root: Path):
    plan = json.loads(plan_path.read_text())
    rows = []
    for cell in plan["cells"]:
        f = run_root / cell["cell_id"] / "result.json"
        if f.exists():
            r = json.loads(f.read_text()); rows.append({**cell, "status": r["result"]["status"], "solved": bool(r["result"]["target_solved"]),
                                                        "cost": float(r["result"].get("cost_usd_at_published_rates", 0.0)),
                                                        "tokens_out": int(r["result"]["tokens"]["output_tokens"])})
    return plan, rows


def counts(rows):
    """(instance, step, arm, budget) -> [n, k]; infrastructure failures excluded."""
    c = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["status"] in NOT_OBSERVED:
            continue
        key = (r["instance"], r["step"], r["arm"], r.get("budget_label", "b"))
        c[key][0] += 1; c[key][1] += int(r["solved"])
    return c


def phat(n: int, k: int) -> float:
    return (k + 0.5) / (n + 1)


def bits(n: int, k: int) -> float:
    return -math.log2(phat(n, k))


def contrast(values: dict, alt: str, label: str) -> dict:
    d = np.asarray([v for v in values.values() if v is not None], float)
    if len(d) == 0:
        return {"what": label, "alt": alt, "n": 0}
    sf = signflip(d, alt); lo, hi = boot_ci(d); m, tlo, thi = t_ci(d)
    return {"what": label, "alt": alt, "n": int(len(d)), "mean": sf["mean"], "p": sf["p"], "boot95": [lo, hi], "t95": [tlo, thi], "exact": sf.get("exact")}


def analyze_main(plan, rows) -> dict:
    c = counts(rows); budget = plan.get("main_budget_label", "b")
    inst = sorted({r["instance"] for r in rows})
    out = {"mode": "main", "instances": inst, "n_sessions": len(rows), "n_not_observed": sum(1 for r in rows if r["status"] in NOT_OBSERVED),
           "cost_usd": round(sum(r["cost"] for r in rows), 2), "table": {}, "contrasts": {}}
    def nk(i, s, a):
        return c.get((i, s, a, budget), [0, 0])
    for i in inst:
        out["table"][i] = {s: {a: {"n": nk(i, s, a)[0], "k": nk(i, s, a)[1], "bits": (bits(*nk(i, s, a)) if nk(i, s, a)[0] else None)}
                               for a in ("none", "ladder", "sham")} for s in STEPS}
    def delta(i, s, a, b):
        na, nb = nk(i, s, a), nk(i, s, b)
        return None if (na[0] == 0 or nb[0] == 0) else bits(*nb) - bits(*na)   # bits(b) - bits(a): positive = a saves bits vs b
    def per_instance(a, b, steps):
        vals = {}
        for i in inst:
            ds = [delta(i, s, a, b) for s in steps]; ds = [d for d in ds if d is not None]
            vals[i] = float(np.mean(ds)) if ds else None
        return vals
    C = out["contrasts"]
    C["P1"] = contrast(per_instance("ladder", "none", STEPS[1:]), "greater", "bits(none) − bits(ladder), mean over L2–L5")
    C["S1"] = contrast(per_instance("ladder", "sham", STEPS[1:]), "greater", "bits(sham) − bits(ladder), mean over L2–L5")
    fam = []
    for j, s in enumerate(STEPS[1:], start=2):
        C[f"S{j}"] = contrast(per_instance("ladder", "none", [s]), "greater", f"bits(none) − bits(ladder) at {s}"); fam.append(f"S{j}")
    ps = [C[k].get("p") for k in fam]
    if all(isinstance(x, float) for x in ps):
        for k, q in zip(fam, bh(ps)):
            C[k]["q_bh"] = float(q)
    # chain vs width (descriptive)
    chain, width = {}, {}
    for i in inst:
        ok = nk(i, "L1", "none")[0] and all(nk(i, s, "ladder")[0] for s in STEPS[1:]) and nk(i, "L5", "none")[0]
        if ok:
            chain[i] = phat(*nk(i, "L1", "none")) * float(np.prod([phat(*nk(i, s, "ladder")) for s in STEPS[1:]]))
            width[i] = 1 - (1 - phat(*nk(i, "L5", "none"))) ** 5
    out["chain_vs_width"] = {"chain": chain, "width": width, "mean_chain": float(np.mean(list(chain.values()))) if chain else None,
                             "mean_width": float(np.mean(list(width.values()))) if width else None}
    # guards
    floor = all(nk(i, s, "none")[1] == 0 for i in inst for s in STEPS[1:] if nk(i, s, "none")[0]) if inst else False
    ceiling = all(nk(i, s, "none")[1] == nk(i, s, "none")[0] for i in inst for s in STEPS if nk(i, s, "none")[0]) if inst else False
    instr = out["n_not_observed"] > 0.10 * max(1, out["n_sessions"])
    out["guards"] = {"prior_floor": bool(floor), "ceiling": bool(ceiling), "instrument": bool(instr)}
    p1 = C["P1"]
    if p1.get("n", 0) == 0:
        v = "no_data"
    elif floor:
        v = "unmeasurable_prior_floor"
    elif ceiling:
        v = "unmeasurable_ceiling"
    elif instr or p1["p"] >= 0.05:
        v = "close_no_bits_saved"
    elif C["S1"].get("n", 0) and C["S1"]["p"] < 0.05 and C["S1"]["mean"] > 0:
        v = "ladder_saves_bits_beyond_generic_example"
    else:
        v = "ladder_saves_bits_not_beyond_sham"
    out["verdict"] = v
    cw = out["chain_vs_width"]
    out["status"] = ("proveitoso" if v == "ladder_saves_bits_beyond_generic_example" and cw["mean_chain"] is not None and cw["mean_chain"] > cw["mean_width"]
                     else "interessante" if v.startswith("ladder_saves") else "limite")
    return out


def analyze_pilot(plan, rows) -> dict:
    c = counts(rows); budgets = sorted({r.get("budget_label", "b") for r in rows}); inst = sorted({r["instance"] for r in rows})
    out = {"mode": "pilot", "instances": inst, "budgets": budgets, "n_sessions": len(rows),
           "n_not_observed": sum(1 for r in rows if r["status"] in NOT_OBSERVED), "cost_usd": round(sum(r["cost"] for r in rows), 2),
           "none_rates": {}, "ladder_smoke": {}}
    for b in budgets:
        out["none_rates"][b] = {}
        for s in STEPS:
            n = sum(c.get((i, s, "none", b), [0, 0])[0] for i in inst); k = sum(c.get((i, s, "none", b), [0, 0])[1] for i in inst)
            out["none_rates"][b][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
        for s in STEPS[1:]:
            n = sum(c.get((i, s, "ladder", b), [0, 0])[0] for i in inst); k = sum(c.get((i, s, "ladder", b), [0, 0])[1] for i in inst)
            if n:
                out["ladder_smoke"].setdefault(b, {})[s] = {"n": n, "k": k}
    # pre-declared budget rule: the budget whose mean none-rate over L1..L5 is closest to 0.5; ties -> the cheaper
    def mean_rate(b):
        v = [x["rate"] for x in out["none_rates"][b].values() if x["rate"] is not None]
        return float(np.mean(v)) if v else None
    scored = sorted((abs(mean_rate(b) - 0.5), b) for b in budgets if mean_rate(b) is not None)
    chosen = scored[0][1] if scored else None
    grad = None
    if chosen:
        r1, r5 = out["none_rates"][chosen]["L1"]["rate"], out["none_rates"][chosen]["L5"]["rate"]
        grad = (r1 is not None and r5 is not None and r1 > r5)
    out["decision"] = {"budget_for_main": chosen, "mean_none_rate": {b: mean_rate(b) for b in budgets}, "gradient_L1_gt_L5": grad,
                       "proceed_to_main": bool(chosen and grad),
                       "rule": "budget with mean none-rate closest to 0.5; main only if rate(L1) > rate(L5) at that budget; otherwise redesign the steps"}
    return out


def render(out) -> str:
    L = [f"# A1 — {'piloto' if out['mode'] == 'pilot' else 'principal'}: leitura única (script escrito antes dos dados)", ""]
    L.append(f"Sessões {out['n_sessions']}, não observadas (falha de infraestrutura) {out['n_not_observed']}, custo ≈ US${out['cost_usd']}.")
    if out["mode"] == "pilot":
        for b, rates in out["none_rates"].items():
            L += ["", f"## Braço sem exemplo, orçamento {b}", "", "| degrau | n | resolvidas | taxa |", "|---|---|---|---|"]
            for s, x in rates.items():
                rate = "—" if x["rate"] is None else "%.2f" % x["rate"]
                L.append(f"| {s} | {x['n']} | {x['k']} | {rate} |")
        if out["ladder_smoke"]:
            L += ["", "## Fumaça do braço escada (exemplo = degrau anterior)", ""]
            for b, d in out["ladder_smoke"].items():
                L.append(f"- {b}: " + ", ".join(f"{s} {x['k']}/{x['n']}" for s, x in d.items()))
        L += ["", f"## Decisão pré-declarada: {json.dumps(out['decision'], ensure_ascii=False)}", ""]
        return "\n".join(L) + "\n"
    L += ["", "## Bits por instância, degrau e braço (p̂ = (k+½)/(n+1); bits = −log₂ p̂)", ""]
    for i, t in out["table"].items():
        L.append(f"- **{i}**: " + "; ".join(f"{s} " + "/".join(f"{a} {x['k']}:{x['n']}" for a, x in t[s].items() if x['n']) for s in STEPS))
    C = out["contrasts"]
    def fmt(c):
        if c.get("n", 0) == 0:
            return f"{c['what']}: sem dados"
        q = f", q_BH = {c['q_bh']:.3f}" if "q_bh" in c else ""
        return f"{c['what']} ({c['alt']}, n = {c['n']}): {c['mean']:+.2f} bits [{c['boot95'][0]:+.2f}, {c['boot95'][1]:+.2f}] boot; p = {c['p']:.4f}{q}"
    L += ["", "## Contrastes pré-registrados", "", f"- **P1**: {fmt(C['P1'])}", f"- **S1**: {fmt(C['S1'])}"]
    for k in ("S2", "S3", "S4", "S5"):
        L.append(f"- **{k}**: {fmt(C[k])}")
    cw = out["chain_vs_width"]
    L += ["", f"## Escada vs largura a orçamento igual (descritivo): P_escada média {cw['mean_chain']} vs P_largura média {cw['mean_width']}",
          "", f"## Guardas: {json.dumps(out['guards'])}", "", f"## Veredito pré-declarado: `{out['verdict']}` — status: **{out['status']}**", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", type=Path, required=True); p.add_argument("--run", type=Path, required=True)
    p.add_argument("--pilot", action="store_true"); p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plan, rows = load(a.plan, a.run)
    out = analyze_pilot(plan, rows) if a.pilot else analyze_main(plan, rows)
    a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in out if k in ("mode", "verdict", "status", "decision", "n_sessions", "cost_usd")}, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
