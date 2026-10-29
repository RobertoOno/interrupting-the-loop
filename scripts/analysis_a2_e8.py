#!/usr/bin/env python3
"""A2 consolidation, REPLICATION, amendment E8 — analysis WRITTEN BEFORE THE DATA (docs/A2_CONSOLIDACAO_REPLICACAO_V1.md, E8).
Same-configuration completion of the thinking comparison. Six arms on the six held-out instances, steps L2 and L3:
  base   (no adapter, thinking off, T 0.7/top-p 0.8, 16k tokens, 900 s)     p2   (p2 adapter, same)
  baset  (no adapter, thinking on,  T 1.0/top-p 0.95, 131k tokens, 3600 s)  p2t  (p2 adapter, same)
  basen  (no adapter, thinking OFF, T 1.0/top-p 0.95, 131k tokens, 3600 s)  p2n  (p2 adapter, same)   <- the E8 arms
Rule P4_clean_L2: p2t rises at L2 against p2n (sign-flip one-sided p < .05 over the six instances AND pooled difference
  >= 0.25). The only factor between p2n and p2t is `enable_thinking`, so a rise attributes the P4 gain to the reasoning.
Flag config_alone_moves_L2: p2n rises at L2 against p2 (sampling, budget and time alone move the adapter). If true, the
  attribution of P4 to the reasoning is not clean and the reverse diagonal (thinking on at T 0.7/top-p 0.8) is recorded
  as pending before publication.
Descriptive, no rule: baset vs basen (reasoning on the base under the same configuration), basen vs base (configuration
  alone on the base), p2t vs baset and p2t vs p2 (the P4 contrasts, repeated here for the table), everything also at L3.
Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import signflip  # noqa: E402
from analysis_a1 import counts, load  # noqa: E402

ARMS = ["base", "p2", "baset", "p2t", "basen", "p2n"]
STEPS = ["L2", "L3"]
CONTRASTS = [("p2t", "p2n"), ("p2n", "p2"), ("baset", "basen"), ("basen", "base"), ("p2t", "baset"), ("p2t", "p2")]


def analyze(plans: dict, rows: dict) -> dict:
    inst = sorted({r["instance"] for r in rows["p2t"]})
    label = {a: (plans[a].get("main_budget_label") or "b16k") for a in ARMS}
    c = {a: counts(rows[a]) for a in ARMS}
    def nk(a, i, s):
        return c[a].get((i, s, "none", label[a]), [0, 0])
    out = {"mode": "a2_consolidation_e8_same_config", "instances": inst, "n_sessions": {a: len(rows[a]) for a in ARMS},
           "n_not_observed": {a: sum(1 for r in rows[a] if r["status"] in ("infrastructure_failure", "budget_accounting_error")) for a in ARMS},
           "config": {a: {**{k: plans[a]["agent"].get(k) for k in ("model", "temperature", "top_p", "timeout_seconds", "extra_body")}, "budgets": plans[a]["budgets"]} for a in ARMS},
           "rates": {a: {} for a in ARMS}, "contrasts": {}, "rises": {}}
    for a in ARMS:
        for s in STEPS:
            n = sum(nk(a, i, s)[0] for i in inst); k = sum(nk(a, i, s)[1] for i in inst)
            out["rates"][a][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
    for s in STEPS:
        out["contrasts"][s] = {}; out["rises"][s] = {}
        for x, y in CONTRASTS:
            d = []
            for i in inst:
                a, b = nk(x, i, s), nk(y, i, s)
                if a[0] and b[0]:
                    d.append(a[1] / a[0] - b[1] / b[0])
            d = np.asarray(d, float); key = f"{x}_vs_{y}"
            if len(d):
                sf = signflip(d, "greater"); pooled = float(np.mean(d))
                out["contrasts"][s][key] = {"n": int(len(d)), "mean_rate_diff": sf["mean"], "p": sf["p"], "pooled_diff": pooled}
                out["rises"][s][key] = bool(sf["p"] < 0.05 and pooled >= 0.25)
            else:
                out["contrasts"][s][key] = {"n": 0}; out["rises"][s][key] = False
    r = out["rises"]
    out["rules"] = {"P4_clean_L2": r["L2"]["p2t_vs_p2n"], "config_alone_moves_L2": r["L2"]["p2n_vs_p2"], "P4_clean_L3_descriptive": r["L3"]["p2t_vs_p2n"]}
    if out["rules"]["P4_clean_L2"] and not out["rules"]["config_alone_moves_L2"]:
        v = "reasoning_is_the_active_ingredient_given_the_form"
    elif out["rules"]["P4_clean_L2"]:
        v = "reasoning_rises_but_configuration_also_moves_reverse_diagonal_pending"
    elif out["rules"]["config_alone_moves_L2"]:
        v = "configuration_not_reasoning"
    else:
        v = "no_clean_rise"
    out["verdict"] = v
    return out


def render(out: dict) -> str:
    L = ["# A2 — réplica, emenda E8: braços sem pensamento na configuração dos braços de pensamento (script escrito antes dos dados)", "",
         f"Instâncias retidas: {', '.join(out['instances'])}. Sessões por braço: {json.dumps(out['n_sessions'])}; não observadas: {json.dumps(out['n_not_observed'])}.", "",
         "## Taxas por braço (resolvidas/n)", "", "| braço | pensamento | amostragem | orçamento | L2 | L3 |", "|---|---|---|---|---|---|"]
    for a in ARMS:
        cfg = out["config"][a]; think = ((cfg.get("extra_body") or {}).get("chat_template_kwargs") or {}).get("enable_thinking")
        L.append(f"| {a} | {'ligado' if think else 'desligado'} | T {cfg['temperature']} / top-p {cfg['top_p']} | {list(cfg['budgets'].values())[0]} | "
                 f"{out['rates'][a]['L2']['k']}/{out['rates'][a]['L2']['n']} | {out['rates'][a]['L3']['k']}/{out['rates'][a]['L3']['n']} |")
    L += ["", "## Contrastes (diferença de taxa por instância; permutação por sinal, unilateral; ↑ = subida pela regra)", ""]
    for s in STEPS:
        L.append(f"- **{s}**: " + "; ".join(f"{k} {c['pooled_diff']:+.2f} (p = {c['p']:.3f}){' ↑' if out['rises'][s][k] else ''}" if c.get("n") else f"{k} —" for k, c in out["contrasts"][s].items()))
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ARMS:
        p.add_argument(f"--plan-{a}", type=Path, required=True); p.add_argument(f"--run-{a}", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plans, rows = {}, {}
    for arm in ARMS:
        plans[arm], rows[arm] = load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))
    out = analyze(plans, rows); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({"verdict": out["verdict"], "rules": out["rules"]}))


if __name__ == "__main__":
    main()
