#!/usr/bin/env python3
"""A2 sem curador — analysis WRITTEN BEFORE THE DATA (docs/A2_SEM_CURADOR_V1.md).
Does consolidating the model's OWN verified proofs (no human curation; the verifier is the only filter) move the model on held-out
instances? Arms on the six held-out instances (same cells as the replication):
  existing comparators (14/09): base (no thinking, 16k, six steps), baset (thinking 131k, L2/L3), p2 (curated six forms), p2t
  new: own   = LoRA on the base's own verified proofs from L1-L3 of the 48 training instances (no thinking, 16k, six steps)
       ownt  = the same adapter with thinking 131k on L2/L3
       curm  = LoRA on the CURATED reference proofs of exactly the same (instance, step) cells the base solved (matched control)
       curmt = curm with thinking 131k on L2/L3
rise(x, y, s): paired difference of solve rates x - y over the six instances, sign-flip one-sided p < .05 (minimum 0.0156) AND pooled
difference >= 0.25. fall(x, y, s): the mirror (p < .05 one-sided 'less' AND pooled <= -0.25).
  P_own_think: ownt rises against baset at L2 or at L3            (own form in the weights + reasoning in context beats reasoning alone)
  P_own_plain: own rises against base at L1, L2 or L3             (own form in the weights transfers to new instances of the same steps)
  negative_transfer: own falls against base at any step           (own form applied where it does not belong, as p1 at L1)
  curation_value: curm rises against own at some step, or curmt against ownt at L2/L3 (descriptive: what curation adds at equal data)
Verdicts: self_consolidation_moves (P_own_think or P_own_plain) | needs_curator (neither, but curm rises against base somewhere or curmt
against baset at L2/L3) | nothing_moves_at_matched_size (neither own nor curm rises anywhere: the matched set is too small to write a
form; inconclusive about curation). The production yield gate (>= 24 verified own proofs) is applied BEFORE training, not here.
Sessions with infrastructure failure are not observed.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.paired_stats import signflip  # noqa: E402
from analysis_a1 import counts, load  # noqa: E402

STEPS6 = ["L1", "L2", "L3", "L4", "L5", "E"]
SIX = ["base", "p2", "own", "curm"]
THINK = ["baset", "p2t", "ownt", "curmt"]
ARMS = SIX + THINK


def analyze(plans: dict, rows: dict, n_own_examples: int | None) -> dict:
    inst = sorted({r["instance"] for r in rows["base"]})
    label = {a: (plans[a].get("main_budget_label") or "b16k") for a in ARMS}
    c = {a: counts(rows[a]) for a in ARMS}
    def nk(a, i, s):
        return c[a].get((i, s, "none", label[a]), [0, 0])
    out = {"mode": "a2_own_consolidation", "instances": inst, "n_own_examples": n_own_examples,
           "n_sessions": {a: len(rows[a]) for a in ARMS},
           "n_not_observed": {a: sum(1 for r in rows[a] if r["status"] in ("infrastructure_failure", "budget_accounting_error")) for a in ARMS},
           "rates": {a: {} for a in ARMS}, "contrasts": {}, "rises": {}, "falls": {}}
    for a in ARMS:
        for s in (STEPS6 if a in SIX else ["L2", "L3"]):
            n = sum(nk(a, i, s)[0] for i in inst); k = sum(nk(a, i, s)[1] for i in inst)
            out["rates"][a][s] = {"n": n, "k": k, "rate": (k / n if n else None)}
    def contrast(x, y, s):
        d = []
        for i in inst:
            a, b = nk(x, i, s), nk(y, i, s)
            if a[0] and b[0]:
                d.append(a[1] / a[0] - b[1] / b[0])
        d = np.asarray(d, float)
        if not len(d):
            return {"n": 0}, False, False
        up = signflip(d, "greater"); down = signflip(-d, "greater"); pooled = float(np.mean(d))   # fall = rise of the negated differences
        return ({"n": int(len(d)), "mean_rate_diff": up["mean"], "p_greater": up["p"], "p_less": down["p"], "pooled_diff": pooled},
                bool(up["p"] < 0.05 and pooled >= 0.25), bool(down["p"] < 0.05 and pooled <= -0.25))
    pairs6 = [("own", "base"), ("curm", "base"), ("curm", "own"), ("own", "p2")]
    pairsT = [("ownt", "baset"), ("curmt", "baset"), ("curmt", "ownt"), ("ownt", "p2t"), ("ownt", "own"), ("curmt", "curm")]
    for s in STEPS6:
        out["contrasts"][s] = {}; out["rises"][s] = {}; out["falls"][s] = {}
        for x, y in pairs6 + (pairsT if s in ("L2", "L3") else []):
            cc, r, f = contrast(x, y, s); key = f"{x}_vs_{y}"
            out["contrasts"][s][key] = cc; out["rises"][s][key] = r; out["falls"][s][key] = f
    R, F = out["rises"], out["falls"]
    p_think = bool(R["L2"]["ownt_vs_baset"] or R["L3"]["ownt_vs_baset"])
    p_plain = bool(any(R[s]["own_vs_base"] for s in ("L1", "L2", "L3")))
    neg = bool(any(F[s]["own_vs_base"] for s in STEPS6))
    cur_val = bool(any(R[s]["curm_vs_own"] for s in STEPS6) or R["L2"]["curmt_vs_ownt"] or R["L3"]["curmt_vs_ownt"])
    cur_base = bool(any(R[s]["curm_vs_base"] for s in STEPS6) or R["L2"]["curmt_vs_baset"] or R["L3"]["curmt_vs_baset"])
    out["rules"] = {"P_own_think": p_think, "P_own_plain": p_plain, "negative_transfer": neg, "curation_value": cur_val, "curated_matched_rises": cur_base}
    out["verdict"] = ("self_consolidation_moves" if (p_think or p_plain) else "needs_curator" if cur_base else "nothing_moves_at_matched_size")
    return out


def render(out: dict) -> str:
    L = ["# A2 sem curador — leitura única (script escrito antes dos dados)", "",
         f"Instâncias retidas: {', '.join(out['instances'])}. Exemplos próprios consolidados: {out['n_own_examples']}. Sessões por braço: {json.dumps(out['n_sessions'])}; não observadas: {json.dumps(out['n_not_observed'])}.", "",
         "## Taxas por braço e degrau (resolvidas/n)", "", "| braço | " + " | ".join(STEPS6) + " |", "|---|" + "---|" * len(STEPS6)]
    for a in ARMS:
        L.append(f"| {a} | " + " | ".join((f"{out['rates'][a][s]['k']}/{out['rates'][a][s]['n']}" if s in out["rates"][a] else "—") for s in STEPS6) + " |")
    L += ["", "## Contrastes (diferença de taxa por instância; permutação por sinal, unilateral; ↑ subida, ↓ queda pela regra)", ""]
    for s in STEPS6:
        parts = []
        for k, cc in out["contrasts"][s].items():
            if not cc.get("n"):
                parts.append(f"{k} —"); continue
            mark = " ↑" if out["rises"][s][k] else (" ↓" if out["falls"][s][k] else "")
            parts.append(f"{k} {cc['pooled_diff']:+.2f} (p = {cc['p_greater']:.3f}){mark}")
        L.append(f"- **{s}**: " + "; ".join(parts))
    L += ["", f"## Regras: {json.dumps(out['rules'])}", "", f"## Veredito pré-declarado: `{out['verdict']}`", ""]
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ARMS:
        p.add_argument(f"--plan-{a}", type=Path, required=True); p.add_argument(f"--run-{a}", type=Path, required=True)
    p.add_argument("--n-own-examples", type=int, default=None); p.add_argument("--out", type=Path, required=True); p.add_argument("--json", type=Path, default=None)
    a = p.parse_args()
    plans, rows = {}, {}
    for arm in ARMS:
        plans[arm], rows[arm] = load(getattr(a, f"plan_{arm}"), getattr(a, f"run_{arm}"))
    out = analyze(plans, rows, a.n_own_examples); a.out.write_text(render(out))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({"verdict": out["verdict"], "rules": out["rules"]}))


if __name__ == "__main__":
    main()
