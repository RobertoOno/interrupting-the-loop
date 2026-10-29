#!/usr/bin/env python3
"""A7 wall CONFIRMATION — analysis WRITTEN BEFORE THE DATA (docs/A7_PAREDE_V1.md, phase 2 and E1).
For each confirmed candidate W (at most three, fixed order W1, W2, W3, W4 among the screen's wall_candidates), six new held-out instances:
  base_none  : base, no example, 8 attempts per instance (48 cells)
  own2_none  : the self-consolidated adapter a2c4-own2, no example, 8 attempts (48)
  base_ref   : base with the sibling's verified proof, 4 attempts (24)     descriptive (expressibility at scale)
  curm2_none : the curated matched adapter a2c4-curm2, no example, 4 attempts (24)   descriptive
Rules (fixed before the data):
  wall_confirmed : base_none solves 0 of its observed cells (reported with n; incomplete if n < 48)
  rise(x, base)  : per-instance paired difference of solve rates x - base_none, sign-flip one-sided p < .05 (minimum 0.0156 with six
                   instances) AND mean difference >= 0.25
  verdict per W  : not_a_wall_at_scale (base_none >= 1 solve) | loop_crosses_a_wall (confirmed and own2 rises) | wall_holds_for_the_loop
  descriptive    : curm2 rises by the same rule (if both own2 and curm2 cross, the crossing is consolidation in general, not the loop)
Program verdict: new_for_the_system_in_this_family if any W is loop_crosses_a_wall; else no_crossing.
Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import signflip  # noqa: E402
from analysis_a1 import NOT_OBSERVED, load  # noqa: E402


def per_instance(rows, step, arm="none"):
    out = {}
    for r in rows:
        if r["step"] != step or r["arm"] != arm or r["status"] in NOT_OBSERVED:
            continue
        n, k = out.get(r["instance"], (0, 0)); out[r["instance"]] = (n + 1, k + int(r["solved"]))
    return out


def rise(x: dict, base: dict) -> dict:
    inst = sorted(set(x) & set(base))
    d = np.asarray([x[i][1] / x[i][0] - base[i][1] / base[i][0] for i in inst], float)
    if not len(d):
        return {"n_instances": 0, "rise": False}
    sf = signflip(d, "greater"); mean = float(np.mean(d))
    return {"n_instances": int(len(d)), "mean_rate_diff": mean, "p": sf["p"], "rise": bool(sf["p"] < 0.05 and mean >= 0.25)}


def total(t: dict) -> dict:
    return {"n": sum(v[0] for v in t.values()), "k": sum(v[1] for v in t.values()), "instances": len(t)}


def analyze(walls: list[str], base_rows, own_rows, ref_rows, curm_rows) -> dict:
    out = {"mode": "a7_wall_confirmation", "walls": {}, "n_not_observed": sum(1 for r in base_rows + own_rows + ref_rows + curm_rows if r["status"] in NOT_OBSERVED)}
    for w in walls:
        b, o, rf, c = per_instance(base_rows, w), per_instance(own_rows, w), per_instance(ref_rows, w, "reference"), per_instance(curm_rows, w)
        tb = total(b); confirmed = tb["k"] == 0
        own_rise, curm_rise = rise(o, b), rise(c, b)
        verdict = "not_a_wall_at_scale" if not confirmed else ("loop_crosses_a_wall" if own_rise["rise"] else "wall_holds_for_the_loop")
        out["walls"][w] = {"base_none": tb, "own2_none": total(o), "base_ref": total(rf), "curm2_none": total(c), "complete_base": tb["n"] == 48,
                           "wall_confirmed": confirmed, "own2_vs_base": own_rise, "curm2_vs_base_descriptive": curm_rise, "verdict": verdict}
    crossed = [w for w, v in out["walls"].items() if v["verdict"] == "loop_crosses_a_wall"]
    out["crossed"] = crossed
    out["verdict"] = "new_for_the_system_in_this_family" if crossed else "no_crossing"
    return out


def render(out) -> str:
    L = ["# A7 — confirmação das paredes: leitura única (script escrito antes dos dados)", "",
         f"Sessões não observadas (falha de infraestrutura): {out['n_not_observed']}.", "",
         "| parede | base, sem exemplo | own2, sem exemplo | base, prova irmã | curm2, sem exemplo | own2 contra base | veredito |", "|---|---|---|---|---|---|---|"]
    for w, v in out["walls"].items():
        f = lambda t: f"{t['k']}/{t['n']}"
        r = v["own2_vs_base"]
        rs = f"{r['mean_rate_diff']:+.2f} (p = {r['p']:.3f}){' ↑' if r['rise'] else ''}" if r.get("n_instances") else "—"
        L.append(f"| {w} | {f(v['base_none'])} | {f(v['own2_none'])} | {f(v['base_ref'])} | {f(v['curm2_none'])} | {rs} | `{v['verdict']}`{'' if v['complete_base'] else ' (base incompleta)'} |")
    L += ["", f"## Veredito pré-declarado do programa: `{out['verdict']}`" + (f" (paredes atravessadas: {', '.join(out['crossed'])})" if out["crossed"] else ""), ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--walls", nargs="+", required=True)
    for arm in ("base", "own2", "ref", "curm2"):
        p.add_argument(f"--plan-{arm}", type=Path, required=True); p.add_argument(f"--run-{arm}", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    rows = {arm: load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))[1] for arm in ("base", "own2", "ref", "curm2")}
    out = analyze(a.walls, rows["base"], rows["own2"], rows["ref"], rows["curm2"]); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    print(json.dumps({"verdict": out["verdict"], "per_wall": {w: v["verdict"] for w, v in out["walls"].items()}}))


if __name__ == "__main__":
    main()
