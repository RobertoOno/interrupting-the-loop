#!/usr/bin/env python3
"""A2 Mathlib competence pilot — the cross-model rule, WRITTEN BEFORE THE DATA (docs/A2_PILOTO_MATHLIB_V1.md).
Models are tried in the pre-declared order (by size); each one's read is scripts/analysis_a2_pilot.py (competence
rate(L1) >= 0.5; headroom; example effect at L4/L5). The FIRST model whose three rules pass becomes the A2 substrate
and the models after it are NOT run (recorded as such). No result is chosen by effect size; ties cannot arise.
  analysis_a2_mathlib.py --order pythagoras4b goedel8b qwen38_27b pythagoras32b --results-dir docs/a2m_results --out ... --json ...
Per-model JSON files are <results-dir>/<model>.json (absent = not run).
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def analyze(order: list[str], results: dict[str, dict | None]) -> dict:
    out = {"mode": "a2_mathlib_pilot", "order": order, "models": {}, "substrate": None, "not_run": []}
    stopped = False
    for m in order:
        r = results.get(m)
        if stopped or r is None:
            out["models"][m] = {"ran": False}; out["not_run"].append(m); continue
        out["models"][m] = {"ran": True, "rules": r["rules"], "decision": r["decision"], "none_rates": r["none_rates"], "example": r["example"],
                            "n_sessions": r["n_sessions"], "n_not_observed": r["n_not_observed"], "session_mode": r.get("session_mode")}
        if r["decision"] == "admit_A2":
            out["substrate"] = m; stopped = True
    out["verdict"] = f"substrate_{out['substrate']}" if out["substrate"] else "no_open_model_admitted_A2_closes_in_this_domain"
    return out


def render(out: dict) -> str:
    L = ["# A2 — piloto de competência com Mathlib: leitura entre modelos (script escrito antes dos dados)", "",
         f"Ordem pré-declarada: {', '.join(out['order'])}. Regra: o primeiro admitido vira o substrato; os seguintes não rodam.", "",
         "| modelo | modo | sessões | L1 | L2 | L3 | L4 | L5 | E | margem | efeito do exemplo (bits, p) | decisão |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in out["order"]:
        x = out["models"][m]
        if not x["ran"]:
            L.append(f"| {m} | — | 0 | — | — | — | — | — | — | — | — | não rodou |"); continue
        rates = [x["none_rates"].get(s, {}).get("rate") for s in ("L1", "L2", "L3", "L4", "L5", "E")]
        cells = ["—" if v is None else f"{v:.2f}" for v in rates]
        eff = "; ".join(f"{a} {e['bits_saved_mean'] if e['bits_saved_mean'] is None else round(e['bits_saved_mean'], 2)} (p = {e['p']})" for a, e in x["example"].items())
        L.append(f"| {m} | {x['session_mode']} | {x['n_sessions']} | " + " | ".join(cells) + f" | {'sim' if x['rules']['headroom'] else 'não'} | {eff or '—'} | `{x['decision']}` |")
    L += ["", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--order", nargs="+", required=True); p.add_argument("--results-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    results = {m: (json.loads((a.results_dir / f"{m}.json").read_text()) if (a.results_dir / f"{m}.json").exists() else None) for m in a.order}
    out = analyze(a.order, results); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({"verdict": out["verdict"], "substrate": out["substrate"], "not_run": out["not_run"]}))


if __name__ == "__main__":
    main()
