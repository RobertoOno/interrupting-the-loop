#!/usr/bin/env python3
"""A8 — does curated consolidation NARROW the model out of its training distribution? Analysis WRITTEN BEFORE THE DATA
(docs/A8_CURADORIA_ESTREITA_V1.md).

Two adapters trained on exactly the same cells (docs/a2c4_data): `a2c4-own2` on the proofs the model itself produced and the verifier
accepted, `a2c4-curm2` on our curated proofs of those same cells. Both are tested, together with the base, on FOUR step families none of
them saw in training (W1..W4 of ladder_walls_v1), six fresh held-out instances each, three attempts, thinking at 131 072 tokens.

rise(x, y, family): paired difference of solve rates x - y over the six instances of the family, sign-flip one-sided p < .05 (minimum
0.0156 with six instances) AND pooled difference >= 0.25; fall: the mirror (the negated differences rise).
  P_narrow      : curm2 FALLS against the base in at least 2 of the 4 families
  P_generalise  : own2 RISES against the base in at least 2 of the 4 families
  descriptive   : own2 vs curm2 per family; per-family rates; no rule attached
Verdicts: curation_narrows_and_self_generalises | curation_narrows_only | self_generalises_only | neither_moves.
A family where the base rate is below 0.25 cannot show a fall by this rule (floor); that is reported per family, not worked around.
Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import signflip  # noqa: E402
from analysis_a1 import NOT_OBSERVED, load  # noqa: E402

FAMILIES = ["W1", "W2", "W3", "W4"]
SCHEMA = {"W1": "pell_mod", "W2": "plane_lattice", "W3": "hyperbolic4", "W4": "lattice_mod_p"}


def per_instance(rows, family):
    out = {}
    for r in rows:
        if r["step"] != family or r["status"] in NOT_OBSERVED:
            continue
        n, k = out.get(r["instance"], (0, 0)); out[r["instance"]] = (n + 1, k + int(r["solved"]))
    return out


def contrast(x: dict, y: dict) -> dict:
    inst = sorted(set(x) & set(y))
    d = np.asarray([x[i][1] / x[i][0] - y[i][1] / y[i][0] for i in inst], float)
    if not len(d):
        return {"n_instances": 0, "rise": False, "fall": False}
    up, down = signflip(d, "greater"), signflip(-d, "greater"); mean = float(np.mean(d))
    return {"n_instances": int(len(d)), "mean_rate_diff": mean, "p_rise": up["p"], "p_fall": down["p"],
            "rise": bool(up["p"] < 0.05 and mean >= 0.25), "fall": bool(down["p"] < 0.05 and mean <= -0.25)}


def total(t: dict) -> dict:
    return {"n": sum(v[0] for v in t.values()), "k": sum(v[1] for v in t.values()), "instances": len(t),
            "rate": (sum(v[1] for v in t.values()) / sum(v[0] for v in t.values()) if t else None)}


def analyze(base_rows, own_rows, curm_rows) -> dict:
    out = {"mode": "a8_curation_narrowing", "families": {},
           "n_not_observed": sum(1 for r in base_rows + own_rows + curm_rows if r["status"] in NOT_OBSERVED)}
    for f in FAMILIES:
        b, o, c = per_instance(base_rows, f), per_instance(own_rows, f), per_instance(curm_rows, f)
        tb = total(b)
        out["families"][f] = {"schema": SCHEMA[f], "base": tb, "own2": total(o), "curm2": total(c),
                              "curm2_vs_base": contrast(c, b), "own2_vs_base": contrast(o, b), "own2_vs_curm2": contrast(o, c),
                              "floor_for_fall": bool(tb["rate"] is not None and tb["rate"] < 0.25)}
    narrow = [f for f, v in out["families"].items() if v["curm2_vs_base"]["fall"]]
    gener = [f for f, v in out["families"].items() if v["own2_vs_base"]["rise"]]
    out["rules"] = {"P_narrow": len(narrow) >= 2, "P_generalise": len(gener) >= 2, "families_narrowed": narrow, "families_generalised": gener}
    n, g = out["rules"]["P_narrow"], out["rules"]["P_generalise"]
    out["verdict"] = ("curation_narrows_and_self_generalises" if n and g else "curation_narrows_only" if n else "self_generalises_only" if g else "neither_moves")
    return out


def render(out) -> str:
    L = ["# A8 — a curadoria estreita? Leitura única (script escrito antes dos dados)", "",
         f"Sessões não observadas (falha de infraestrutura): {out['n_not_observed']}.", "",
         "| família | base | own2 (laço) | curm2 (curado) | curm2 contra base | own2 contra base | own2 contra curm2 |", "|---|---|---|---|---|---|---|"]
    for f, v in out["families"].items():
        r = lambda t: f"{t['k']}/{t['n']}"
        def c(x, key):
            if not x.get("n_instances"):
                return "—"
            mark = " ↑" if x["rise"] else (" ↓" if x["fall"] else "")
            p = x["p_fall"] if x["fall"] else x["p_rise"]
            return f"{x['mean_rate_diff']:+.2f} (p = {p:.3f}){mark}"
        L.append(f"| {f} {v['schema']} | {r(v['base'])}{' (piso)' if v['floor_for_fall'] else ''} | {r(v['own2'])} | {r(v['curm2'])} | "
                 f"{c(v['curm2_vs_base'], 'fall')} | {c(v['own2_vs_base'], 'rise')} | {c(v['own2_vs_curm2'], 'rise')} |")
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for arm in ("base", "own2", "curm2"):
        p.add_argument(f"--plan-{arm}", type=Path, required=True); p.add_argument(f"--run-{arm}", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    rows = {arm: load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))[1] for arm in ("base", "own2", "curm2")}
    out = analyze(rows["base"], rows["own2"], rows["curm2"]); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    print(json.dumps({"verdict": out["verdict"], "rules": out["rules"]}))


if __name__ == "__main__":
    main()
