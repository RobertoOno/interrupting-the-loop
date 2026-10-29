#!/usr/bin/env python3
"""A6 — π (what the first submission declares) separated from θ (whether the session then succeeds), per condition and step, with a
Bayesian bootstrap over INSTANCES (docs/A6_PRIOR_SOBRE_FORMAS_V1.md). Reads docs/a6_results/sessions.jsonl (scripts/a6_forms.py table).

For a condition c and a step s, with per-instance counts (n_i sessions, r_i with the right type first, k_i solved, and the solved counts
inside the right-type and the other sessions): for each replicate, weights w ~ Dirichlet(1,...,1) over the instances (scaled to sum to the
number of instances) and   π = (Σ w r + ½)/(Σ w n + 1),   θ_right = (Σ w k_right + ½)/(Σ w n_right + 1),   θ_wrong likewise.
Contrasts between two conditions measured on the SAME instances use the same weights in both (paired); otherwise independent weights.
Reported: median and 90 % interval of π, θ_right, θ_wrong and of Δlogit π, Δlogit θ_right (nats). 4 000 replicates, seed 20260919.
"""
from __future__ import annotations
import argparse, collections, json, math
from pathlib import Path
import numpy as np

REPS, SEED = 4000, 20260919
LADDER = ["L1", "L2", "L3", "L4", "L5", "E"]; WALLS = ["W1", "W2", "W3", "W4"]


def logit(p):
    return np.log(p / (1 - p))


def counts(rows):
    c = collections.OrderedDict()
    for r in rows:
        d = c.setdefault(r["instance"], dict(n=0, r=0, k=0, nr=0, kr=0, nw=0, kw=0))
        d["n"] += 1; d["k"] += r["solved"]; d["r"] += r["right_first"]
        if r["right_first"]:
            d["nr"] += 1; d["kr"] += r["solved"]
        else:
            d["nw"] += 1; d["kw"] += r["solved"]
    return c


def draws(c, W):
    A = {k: np.array([v[k] for v in c.values()], float) for k in ("n", "r", "k", "nr", "kr", "nw", "kw")}
    f = lambda num, den: (W @ A[num] + 0.5) / (W @ A[den] + 1.0)
    return {"pi": f("r", "n"), "theta_right": f("kr", "nr"), "theta_wrong": f("kw", "nw"), "rate": f("k", "n"), "n_right": float(A["nr"].sum()), "n_wrong": float(A["nw"].sum()), "n": float(A["n"].sum()),
            "k": float(A["k"].sum()), "r": float(A["r"].sum())}


def q(x):
    return [round(float(v), 3) for v in np.quantile(x, [0.05, 0.5, 0.95])]


def summarize(rows, rng):
    c = counts(rows); m = len(c); W = rng.dirichlet(np.ones(m), REPS) * m; d = draws(c, W)
    out = {"n": int(d["n"]), "instances": m, "solved": int(d["k"]), "right_first": int(d["r"]), "forms_first": dict(collections.Counter(r["form_first"] for r in rows)),
           "pi": q(d["pi"]), "rate": q(d["rate"])}
    out["theta_right"] = q(d["theta_right"]) if d["n_right"] else None; out["theta_wrong"] = q(d["theta_wrong"]) if d["n_wrong"] else None
    return out


def contrast(rows_a, rows_b, rng):
    ca, cb = counts(rows_a), counts(rows_b); paired = list(ca) == list(cb) or set(ca) == set(cb)
    if paired:
        keys = sorted(set(ca)); ca = collections.OrderedDict((k, ca[k]) for k in keys); cb = collections.OrderedDict((k, cb[k]) for k in keys)
        W = rng.dirichlet(np.ones(len(keys)), REPS) * len(keys); da, db = draws(ca, W), draws(cb, W)
    else:
        da = draws(ca, rng.dirichlet(np.ones(len(ca)), REPS) * len(ca)); db = draws(cb, rng.dirichlet(np.ones(len(cb)), REPS) * len(cb))
    out = {"paired_by_instance": paired, "dlogit_pi": q(logit(da["pi"]) - logit(db["pi"])), "dlogit_rate": q(logit(da["rate"]) - logit(db["rate"]))}
    out["dlogit_theta_right"] = q(logit(da["theta_right"]) - logit(db["theta_right"])) if da["n_right"] >= 3 and db["n_right"] >= 3 else None
    return out


def sel(rows, arm, step, example="none"):
    return [r for r in rows if r["arm"] == arm and r["step"] == step and (example is None or r["example"] == example)]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--table", type=Path, default=Path("docs/a6_results/sessions.jsonl")); p.add_argument("--out", type=Path, default=Path("docs/a6_results/report.md")); p.add_argument("--json", type=Path, default=Path("docs/a6_results/report.json"))
    a = p.parse_args(); rows = [json.loads(l) for l in a.table.read_text().splitlines() if l.strip()]; rng = np.random.default_rng(SEED)
    arms = sorted({r["arm"] for r in rows}); cur = "a8c_curm2_v1" if any(r["node"] == "a8c" for r in rows) else "a8_curm2_v1"
    if cur == "a8c_curm2_v1":   # the completed curated arm replaces the partial one
        rows = [r for r in rows if not (r["node"] == "a8" and r["arm"] == "a8_curm2_v1")]
        for r in rows:
            if r["node"] == "a8c":
                r["arm"] = "a8c_curm2_v1"
    per = {}
    for arm in sorted({r["arm"] for r in rows}):
        for step in sorted({r["step"] for r in rows if r["arm"] == arm}):
            s = sel(rows, arm, step)
            if s:
                per[f"{arm}|{step}"] = summarize(s, rng)
    Q = collections.OrderedDict()
    Q["Q1 curated consolidation p2 vs base, no thinking (A2)"] = {s: contrast(sel(rows, "a2c_p2_v1", s), sel(rows, "a2c_base_v1", s), rng) for s in LADDER}
    Q["Q1 replication p2 vs base, no thinking (A2 replica)"] = {s: contrast(sel(rows, "a2c2_p2_v1", s), sel(rows, "a2c2_base_v1", s), rng) for s in LADDER}
    Q["Q2 A8 own2 vs base, thinking"] = {s: contrast(sel(rows, "a8_own2_v1", s), sel(rows, "a8_base_v1", s), rng) for s in WALLS}
    Q["Q2 A8 curm2 vs base, thinking"] = {s: contrast(sel(rows, cur, s), sel(rows, "a8_base_v1", s), rng) for s in WALLS if sel(rows, cur, s)}
    Q["Q2 A8 own2 vs curm2, thinking"] = {s: contrast(sel(rows, "a8_own2_v1", s), sel(rows, cur, s), rng) for s in WALLS if sel(rows, cur, s)}
    Q["Q3 L4: own2 vs curm2, no thinking (iteration 2)"] = {"L4": contrast(sel(rows, "a2c4_own2_v1", "L4"), sel(rows, "a2c4_curm2_v1", "L4"), rng)}
    Q["Q3 L4: own2t131 vs baset131 (iteration 2)"] = {"L4": contrast(sel(rows, "a2c4_own2t131_v1", "L4"), sel(rows, "a2c4_baset131_v1", "L4"), rng)}
    Q["Q4 thinking given the form: p2t131 vs p2n131 (same config but thinking)"] = {s: contrast(sel(rows, "a2c2_p2t131_v1", s), sel(rows, "a2c2_p2n131_v1", s), rng) for s in ("L2", "L3")}
    Q["Q4 thinking without the form: baset131 vs basen131"] = {s: contrast(sel(rows, "a2c2_baset131_v1", s), sel(rows, "a2c2_basen131_v1", s), rng) for s in ("L2", "L3")}
    sep = [f"{k} / {s}" for k, v in Q.items() for s, c in v.items() if c.get("dlogit_theta_right") and (c["dlogit_theta_right"][0] > 0 or c["dlogit_theta_right"][2] < 0)]
    out = {"sessions": len(rows), "per_condition_step": per, "questions": Q, "theta_contrasts_excluding_zero": sep, "death_criterion_2_pi_theta_indistinguishable": not sep}
    a.json.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    L = ["# A6 — π e θ por condição e degrau (bootstrap bayesiano sobre instâncias; mediana e intervalo de 90 %)", "", f"Sessões: {len(rows)}. π = tipo certo na primeira submissão; θ_certo = sucesso dado o tipo certo; θ_errado = sucesso dado outro tipo.", ""]
    for k, v in Q.items():
        L += [f"## {k}", "", "| degrau | Δlogit π | Δlogit θ_certo | Δlogit taxa | pareado |", "|---|---|---|---|---|"]
        for s, c in v.items():
            fmt = lambda x: "—" if x is None else f"{x[1]:+.2f} [{x[0]:+.2f}, {x[2]:+.2f}]"
            L.append(f"| {s} | {fmt(c['dlogit_pi'])} | {fmt(c['dlogit_theta_right'])} | {fmt(c['dlogit_rate'])} | {'sim' if c['paired_by_instance'] else 'não'} |")
        L.append("")
    L += ["## Por condição e degrau", "", "| condição | degrau | n | resolvidas | π | θ_certo | θ_errado | formas na 1ª submissão |", "|---|---|---|---|---|---|---|---|"]
    for key, v in per.items():
        arm, step = key.split("|"); f = lambda x: "—" if x is None else f"{x[1]:.2f} [{x[0]:.2f}, {x[2]:.2f}]"
        L.append(f"| {arm} | {step} | {v['n']} | {v['solved']} | {f(v['pi'])} | {f(v['theta_right'])} | {f(v['theta_wrong'])} | {json.dumps(v['forms_first'])} |")
    L += ["", f"Contrastes de θ_certo cujo intervalo de 90 % exclui zero: {len(sep)}.", *[f"- {x}" for x in sep], "", f"Critério de morte 2 (π e θ indistinguíveis): {'SIM' if not sep else 'não'}.", ""]
    a.out.write_text("\n".join(L)); print(json.dumps({"sessions": len(rows), "theta_contrasts_excluding_zero": len(sep), "death2": not sep}))


if __name__ == "__main__":
    main()
