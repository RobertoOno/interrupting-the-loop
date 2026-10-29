#!/usr/bin/env python3
"""A2 competence pilot — analysis WRITTEN BEFORE THE DATA (docs/A2_PILOTO_COMPETENCIA_V1.md).
Plan A: none on L1..L5 and E; plan B: skeleton and reference on L4/L5. Rules: competence rate(L1) >= 0.5; headroom = some
step in {L3, L4, L5, E} with 0 < pooled rate < 1; example effect = reference or skeleton saves bits at L4/L5 (sign-flip
over instances, one-sided, p < .05). Admission = all three. Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import boot_ci, signflip  # noqa: E402
from analysis_a1 import NOT_OBSERVED, bits, counts, load  # noqa: E402

STEPS_A = ["L1", "L2", "L3", "L4", "L5", "E"]


def analyze(planA, rowsA, planB, rowsB) -> dict:
    cA, cB = counts(rowsA), counts(rowsB or []); inst = sorted({r["instance"] for r in rowsA})
    label = planA.get("main_budget_label") or "b8k"   # the session budget of the pilot (b8k in the Std pilot, b16k in the Mathlib pilot)
    out = {"mode": "a2_pilot", "instances": inst, "model": (planA.get("agent") or {}).get("model"), "session_mode": (planA.get("agent") or {}).get("mode", "tool"),
           "n_sessions": len(rowsA) + len(rowsB or []),
           "n_not_observed": sum(1 for r in rowsA + (rowsB or []) if r["status"] in NOT_OBSERVED), "none_rates": {}, "example": {}}
    for s in STEPS_A:
        n = sum(cA.get((i, s, "none", label), [0, 0])[0] for i in inst); k = sum(cA.get((i, s, "none", label), [0, 0])[1] for i in inst)
        out["none_rates"][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
    def nk(c, i, s, a):
        return c.get((i, s, a, label), [0, 0])
    for arm in ("skeleton", "reference"):
        pooled = {s: [sum(nk(cB, i, s, arm)[1] for i in inst), sum(nk(cB, i, s, arm)[0] for i in inst)] for s in ("L4", "L5")}
        d = []
        for i in inst:
            ds = []
            for s in ("L4", "L5"):
                a, b = nk(cB, i, s, arm), nk(cA, i, s, "none")
                if a[0] and b[0]:
                    ds.append(bits(*b) - bits(*a))
            if ds:
                d.append(float(np.mean(ds)))
        d = np.asarray(d, float)
        sf = signflip(d, "greater") if len(d) else {"mean": None, "p": None}
        out["example"][arm] = {"pooled": pooled, "bits_saved_mean": sf["mean"], "p": sf["p"], "n": int(len(d)),
                               "boot95": list(boot_ci(d)) if len(d) else None,
                               "pooled_gain": {s: ((pooled[s][0] / pooled[s][1]) - (out["none_rates"][s]["rate"] or 0)) if pooled[s][1] and out["none_rates"][s]["rate"] is not None else None for s in ("L4", "L5")}}
    r1 = out["none_rates"]["L1"]["rate"]
    competence = r1 is not None and r1 >= 0.5
    headroom = any(out["none_rates"][s]["rate"] is not None and 0 < out["none_rates"][s]["rate"] < 1 for s in ("L3", "L4", "L5", "E"))
    effect = any(e["p"] is not None and e["p"] < 0.05 and (e["bits_saved_mean"] or 0) > 0 for e in out["example"].values())
    out["rules"] = {"competence": bool(competence), "headroom": bool(headroom), "example_effect": bool(effect)}
    out["decision"] = ("admit_A2" if competence and headroom and effect else "no_competence_try_second_model" if not competence
                       else "no_headroom" if not headroom else "no_example_effect_close_A2")
    return out


def render(out) -> str:
    L = ["# A2 — piloto de competência: leitura única (script escrito antes dos dados)", "",
         f"Sessões {out['n_sessions']}, não observadas {out['n_not_observed']}.", "", "## Sem exemplo, por degrau", "", "| degrau | n | resolvidas | taxa |", "|---|---|---|---|"]
    for s, x in out["none_rates"].items():
        L.append(f"| {s} | {x['n']} | {x['k']} | {'—' if x['rate'] is None else '%.2f' % x['rate']} |")
    L += ["", "## Exemplos em L4/L5", ""]
    for arm, e in out["example"].items():
        L.append(f"- **{arm}**: L4 {e['pooled']['L4'][0]}/{e['pooled']['L4'][1]}, L5 {e['pooled']['L5'][0]}/{e['pooled']['L5'][1]}; bits poupados {e['bits_saved_mean']} (n = {e['n']}, p = {e['p']})")
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Decisão pré-declarada: `{out['decision']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan-a", type=Path, required=True); p.add_argument("--run-a", type=Path, required=True)
    p.add_argument("--plan-b", type=Path, default=None); p.add_argument("--run-b", type=Path, default=None)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    planA, rowsA = load(a.plan_a, a.run_a); planB, rowsB = (load(a.plan_b, a.run_b) if a.plan_b else (None, []))
    out = analyze(planA, rowsA, planB, rowsB); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("decision", "rules", "n_sessions")}))


if __name__ == "__main__":
    main()
