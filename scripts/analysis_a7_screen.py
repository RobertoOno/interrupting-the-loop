#!/usr/bin/env python3
"""A7 wall SCREEN — analysis WRITTEN BEFORE THE DATA (docs/A7_PAREDE_V1.md, phase 1).
Per candidate step (W1..W4), 2 held-out instances x 4 attempts = 8 cells per arm, thinking at 131 072 tokens:
  base_none  : base model, no example                 -> is it a wall?
  base_ref   : base model, the SIBLING's verified proof  -> is the target within reach when the form is given (expressibility)?
  own2_none  : the iteration-2 self-consolidated adapter -> early, descriptive signal of crossing
Classification per candidate (fixed before the data):
  not_a_wall      base_none >= 1/8
  tooling_wall    base_none == 0/8 and base_ref <= 1/8   (even with the form given the target is out of reach: not an idea wall)
  wall_candidate  base_none == 0/8 and base_ref >= 2/8   (goes to the confirmation stage)
  own2 descriptive: early_crossing_signal if a wall_candidate has own2_none >= 2/8 (not a claim; decided in phase 2).
Screen verdict: walls_found (>= 1 wall_candidate) | no_wall_in_family (none).
Sessions with infrastructure failure are not observed; a candidate with fewer than 8 observed cells in an arm is reported as incomplete.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_a1 import NOT_OBSERVED, load  # noqa: E402

STEPS = ["W1", "W2", "W3", "W4"]
SCHEMA = {"W1": "pell_mod (Pell form mod p)", "W2": "plane_lattice (trap: exact linear invariant does not separate)",
          "W3": "hyperbolic4 (4 fields, 4 offsets)", "W4": "lattice_mod_p (large prime modulus)"}


def tally(rows, step, arm):
    obs = [r for r in rows if r["step"] == step and r["arm"] == arm and r["status"] not in NOT_OBSERVED]
    return {"n": len(obs), "k": sum(1 for r in obs if r["solved"]), "instances_with_solve": len({r["instance"] for r in obs if r["solved"]})}


def analyze(base_rows, own_rows) -> dict:
    out = {"mode": "a7_wall_screen", "candidates": {}, "n_not_observed": sum(1 for r in base_rows + own_rows if r["status"] in NOT_OBSERVED)}
    for s in STEPS:
        bn, br, on = tally(base_rows, s, "none"), tally(base_rows, s, "reference"), tally(own_rows, s, "none")
        complete = bn["n"] == 8 and br["n"] == 8 and on["n"] == 8
        if bn["k"] >= 1:
            cls = "not_a_wall"
        elif br["k"] <= 1:
            cls = "tooling_wall"
        else:
            cls = "wall_candidate"
        out["candidates"][s] = {"schema": SCHEMA[s], "base_none": bn, "base_ref": br, "own2_none": on, "complete": complete, "class": cls,
                                "early_crossing_signal": bool(cls == "wall_candidate" and on["k"] >= 2)}
    walls = [s for s, c in out["candidates"].items() if c["class"] == "wall_candidate"]
    out["wall_candidates"] = walls
    out["verdict"] = "walls_found" if walls else "no_wall_in_family"
    return out


def render(out) -> str:
    L = ["# A7 — triagem de paredes: leitura única (script escrito antes dos dados)", "",
         f"Sessões não observadas (falha de infraestrutura): {out['n_not_observed']}.", "",
         "| candidato | forma | base, sem exemplo | base, prova irmã | own2, sem exemplo | classe |", "|---|---|---|---|---|---|"]
    for s, c in out["candidates"].items():
        f = lambda t: f"{t['k']}/{t['n']}"
        L.append(f"| {s} | {c['schema']} | {f(c['base_none'])} | {f(c['base_ref'])} | {f(c['own2_none'])} | `{c['class']}`{' (sinal precoce de travessia)' if c['early_crossing_signal'] else ''}{'' if c['complete'] else ' (incompleto)'} |")
    L += ["", f"## Candidatos a parede: {out['wall_candidates'] or 'nenhum'}", "", f"## Veredito pré-declarado da triagem: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan-base", type=Path, required=True); p.add_argument("--run-base", type=Path, required=True)
    p.add_argument("--plan-own2", type=Path, required=True); p.add_argument("--run-own2", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    _, base_rows = load(a.plan_base, a.run_base); _, own_rows = load(a.plan_own2, a.run_own2)
    out = analyze(base_rows, own_rows); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    print(json.dumps({"verdict": out["verdict"], "classes": {s: c["class"] for s, c in out["candidates"].items()}}))


if __name__ == "__main__":
    main()
