#!/usr/bin/env python3
"""A9 — do the walls become steps? Analysis WRITTEN BEFORE THE DATA (docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md).

The third adapter of the loop, `a9-own3`, is `a2c4-own2`'s training data plus the 52 proofs that own2 itself produced, with thinking, on
the wall families W1..W4 (A8's instances, from now on training instances). Test cells are fresh: 24 new instances of W1..W4 and 6
instances of a NEW family, W5, which composes two of them (the bilinear form of W3 conserved only modulo a prime, as in W1).

rise(x, y, block): paired difference of solve rates x - y over the instances of the block, sign-flip one-sided p < .05 (minimum 0.0156
with six instances) AND mean difference >= 0.25; fall: the mirror.
  P_compose  : on W5, with thinking, own3 RISES against own2.
  P_cheapen  : on W1..W4 WITHOUT thinking, own3 RISES against own2 in at least 2 of the 4 families.
  P_retain   : own3 does not FALL against own2 in any of the six ladder steps without thinking (own2's run of 16/09, same cells) nor in any
               of W1..W4 with thinking.
Verdict: composes | cheapens_only | saturates, with "_with_forgetting" appended when P_retain fails.
Descriptive, no rule: the base on W5 (is it a wall?), own2 and own3 against the base on W5, W5 without thinking, W1..W4 with thinking,
ceilings (a rise of 0.25 is impossible where the comparator is above 0.75) and floors. Sessions with infrastructure failure are not observed.
An arm the deadline cut short is read with its observed n, which is printed; a contrast with no common instance evaluates to False.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_a1 import NOT_OBSERVED, load  # noqa: E402
from analysis_a8_narrow import contrast, per_instance, total  # noqa: E402

WALLS = ["W1", "W2", "W3", "W4"]; LADDER = ["L1", "L2", "L3", "L4", "L5", "E"]
ARMS = ["w5base", "w5own2", "w5own3", "w5own2n", "w5own3n", "own2t", "own3t", "basen", "own2n", "own3n", "own3lad", "own2lad"]


def block(rows_x, rows_y, step) -> dict:
    x, y = per_instance(rows_x, step), per_instance(rows_y, step); ty = total(y)
    return {"x": total(x), "y": ty, "contrast": contrast(x, y), "ceiling_for_rise": bool(ty["rate"] is not None and ty["rate"] > 0.75),
            "floor_for_fall": bool(ty["rate"] is not None and ty["rate"] < 0.25)}


def analyze(rows: dict) -> dict:
    out = {"mode": "a9_walls_become_steps", "n_not_observed": {a: sum(1 for r in rows.get(a, []) if r["status"] in NOT_OBSERVED) for a in ARMS},
           "n_observed": {a: sum(1 for r in rows.get(a, []) if r["status"] not in NOT_OBSERVED) for a in ARMS}}
    g = lambda a: rows.get(a, [])
    out["W5_thinking"] = {"own3_vs_own2": block(g("w5own3"), g("w5own2"), "W5"), "own3_vs_base": block(g("w5own3"), g("w5base"), "W5"), "own2_vs_base": block(g("w5own2"), g("w5base"), "W5")}
    out["W5_no_thinking"] = {"own3_vs_own2": block(g("w5own3n"), g("w5own2n"), "W5")}
    out["walls_no_thinking"] = {f: {"own3_vs_own2": block(g("own3n"), g("own2n"), f), "own3_vs_base": block(g("own3n"), g("basen"), f)} for f in WALLS}
    out["walls_thinking"] = {f: {"own3_vs_own2": block(g("own3t"), g("own2t"), f)} for f in WALLS}
    out["ladder_no_thinking"] = {s: {"own3_vs_own2": block(g("own3lad"), g("own2lad"), s)} for s in LADDER}
    base5 = out["W5_thinking"]["own3_vs_base"]["y"]
    out["W5_base_is_wall_candidate"] = bool(base5["n"] and base5["k"] == 0)
    cheap = [f for f in WALLS if out["walls_no_thinking"][f]["own3_vs_own2"]["contrast"].get("rise")]
    falls = [s for s in LADDER if out["ladder_no_thinking"][s]["own3_vs_own2"]["contrast"].get("fall")] + \
            [f for f in WALLS if out["walls_thinking"][f]["own3_vs_own2"]["contrast"].get("fall")]
    rules = {"P_compose": bool(out["W5_thinking"]["own3_vs_own2"]["contrast"].get("rise")), "P_cheapen": len(cheap) >= 2, "P_retain": not falls,
             "families_cheapened": cheap, "blocks_fallen": falls}
    out["rules"] = rules
    v = "composes" if rules["P_compose"] else "cheapens_only" if rules["P_cheapen"] else "saturates"
    out["verdict"] = v + ("" if rules["P_retain"] else "_with_forgetting")
    return out


def _cell(b: dict) -> str:
    c = b["contrast"]; r = lambda t: f"{t['k']}/{t['n']}"
    if not c.get("n_instances"):
        return f"{r(b['x'])} vs {r(b['y'])} | —"
    mark = " ↑" if c["rise"] else (" ↓" if c["fall"] else ""); p = c["p_fall"] if c["fall"] or c["mean_rate_diff"] < 0 else c["p_rise"]
    flags = (" (teto)" if b["ceiling_for_rise"] else "") + (" (piso)" if b["floor_for_fall"] else "")
    return f"{r(b['x'])} vs {r(b['y'])} | {c['mean_rate_diff']:+.2f} (p = {p:.3f}){mark}{flags}"


def render(out) -> str:
    L = ["# A9 — as paredes viram degraus? Leitura única (script escrito antes dos dados)", "",
         f"Observadas por braço: {json.dumps(out['n_observed'])}", f"Não observadas (falha de infraestrutura): {json.dumps({k: v for k, v in out['n_not_observed'].items() if v})}", "",
         "## W5 (família nova, composição), com pensamento", "", "| contraste | x vs y | diferença pareada |", "|---|---|---|"]
    for k, b in out["W5_thinking"].items():
        L.append(f"| {k} | {_cell(b).split(' | ')[0]} | {_cell(b).split(' | ')[1]} |")
    L += ["", f"Base em W5 é candidata a parede (0 resolvidas): {out['W5_base_is_wall_candidate']}", "", "## W5 sem pensamento", "", f"- own3 vs own2: {_cell(out['W5_no_thinking']['own3_vs_own2'])}", "",
          "## W1–W4 (instâncias novas) sem pensamento", "", "| família | own3 vs own2 | own3 vs base |", "|---|---|---|"]
    for f, v in out["walls_no_thinking"].items():
        L.append(f"| {f} | {_cell(v['own3_vs_own2'])} | {_cell(v['own3_vs_base'])} |")
    L += ["", "## W1–W4 (instâncias novas) com pensamento", "", "| família | own3 vs own2 |", "|---|---|"]
    for f, v in out["walls_thinking"].items():
        L.append(f"| {f} | {_cell(v['own3_vs_own2'])} |")
    L += ["", "## Escada original (retidas da iteração 2) sem pensamento: retenção", "", "| degrau | own3 vs own2 (16/09) |", "|---|---|"]
    for s, v in out["ladder_no_thinking"].items():
        L.append(f"| {s} | {_cell(v['own3_vs_own2'])} |")
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", type=Path, default=Path("runs/a9")); p.add_argument("--docs", type=Path, default=Path("docs"))
    p.add_argument("--plan-own2lad", type=Path, default=Path("docs/a2c4_own2_plan_v1.json")); p.add_argument("--run-own2lad", type=Path, default=Path("runs/a2c4/a2c4_own2_v1"))
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args(); rows = {}
    for arm in ARMS:
        if arm == "own2lad":
            plan, run = a.plan_own2lad, a.run_own2lad
        else:
            plan, run = a.docs / f"a9_{arm}_v1_plan.json", a.runs / f"a9_{arm}_v1"
        rows[arm] = load(plan, run)[1] if plan.exists() and run.exists() else []
    out = analyze(rows); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    print(json.dumps({"verdict": out["verdict"], "rules": out["rules"]}))


if __name__ == "__main__":
    main()
