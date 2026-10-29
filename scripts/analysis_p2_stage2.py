#!/usr/bin/env python3
"""Programa 2 stage-2 analysis (written 2026-09-04 04:00, before the runs finished; read once).
Runs: runs/p2/stage2/<arm>_k<k>_s<s> (seeded from stage-1 transplants) and A_s<s> (no seed).
Per run: best theta, valid count, seed theta, improved-over-seed, family of the final (classifier
with the carry-free bound 2001), family exit (theta >= 1.10 and not F0), bits to 50/90% of the
gap seed -> 1.1479 (AlphaEvolve within the cap). Per arm: means and exit fractions; tests:
Fisher exact on exits (D vs C2, D vs C1, D vs D0 per model) and Mann-Whitney on best theta.
Writes docs/APPENDIX_P2_STAGE2.md.

    PYTHONPATH=src python scripts/analysis_p2_stage2.py
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
R = ROOT / "runs/p2/stage2"
EXIT_T, REF, SEED0 = 1.10, 1.1479, None


def classify(code: str):
    from transfer_correspond import get_object
    from family_sumdiff3 import features
    nums = get_object(code, "construct", [], 25)
    if not nums:
        return None
    U = sorted({int(round(x)) for x in nums})
    if len(U) < 2 or len(U) > 4000:
        return None
    f = features(U)
    f["family"] = "F0" if f["frac_pow2_sums_le3"] >= 0.8 else ("F_rec" if (f["carry_free_base"] and f["n"] >= 50) else "other")
    return f


def one(run: Path):
    st = json.loads((run / "state.json").read_text())
    hist = [json.loads(l) for l in (run / "history.jsonl").read_text().splitlines()]
    log = (run.with_suffix(".log")).read_text() if run.with_suffix(".log").exists() else ""
    seed = None
    for l in log.splitlines():
        if l.startswith("sumdiff3: seed score"):
            seed = float(l.split("seed score")[1].split(";")[0])
    best = st["best"]; valid = [r for r in hist if r.get("ok")]
    # first valid sample index reaching fraction f of the gap seed -> REF (bits = log2 index), censored at n
    bits = {}
    run_best = -1e9
    for f in (0.5, 0.9):
        target = (seed if seed is not None else 0) + f * (REF - (seed if seed is not None else 0)); bits[f] = None
    for i, r in enumerate(hist, 1):
        if r.get("ok") and r.get("score") is not None:
            run_best = max(run_best, r["score"])
            for f in (0.5, 0.9):
                if bits[f] is None and run_best >= (seed + f * (REF - seed) if seed is not None else 1e9):
                    bits[f] = math.log2(i)
    fam = classify((run / "best.py").read_text()) if (run / "best.py").exists() else None
    name = run.name; arm = name.rsplit("_k", 1)[0] if "_k" in name else "A"
    return {"run": name, "arm": arm, "best": best, "seed": seed, "improved": (seed is not None and best > seed + 1e-9),
            "n_valid": len(valid), "n": len(hist), "family": fam["family"] if fam else None,
            "exit": bool(fam and best >= EXIT_T and fam["family"] != "F0"), "bits50": bits[0.5], "bits90": bits[0.9]}


def fisher(a1, a0, b1, b0):
    from math import comb
    n = a1 + a0 + b1 + b0; r1 = a1 + a0; c1 = a1 + b1
    def p(k): return comb(r1, k) * comb(n - r1, c1 - k) / comb(n, c1)
    obs = p(a1); return min(1.0, sum(p(k) for k in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(k) <= obs + 1e-12))


def mannwhitney(x, y):
    try:
        from scipy.stats import mannwhitneyu
        return float(mannwhitneyu(x, y, alternative="two-sided").pvalue)
    except Exception:
        return float("nan")


def main():
    runs = sorted(p for p in R.iterdir() if p.is_dir() and (p / "state.json").exists() and not p.name.startswith("smoke"))
    with ProcessPoolExecutor(6) as ex:
        rows = list(ex.map(one, runs))
    by = defaultdict(list)
    for r in rows: by[r["arm"]].append(r)
    L = ["# Programa 2 — etapa 2 (laço a partir dos transplantes), leitura única\n",
         f"{len(rows)} corridas; saída de família = final com θ ≥ {EXIT_T} fora de F0; bits = log2 do índice da primeira amostra válida que atinge a fração do gap semente → {REF} (AE no teto), censurado.\n",
         "| braço | corridas | válidos/corrida | θ semente (média) | melhor θ (média) | melhor do braço | melhorou a semente | saídas | F_rec | bits50 (média) | bits90 (média) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, rs in sorted(by.items()):
        m = lambda k: (sum(r[k] for r in rs if r[k] is not None) / max(1, sum(1 for r in rs if r[k] is not None))) if any(r[k] is not None for r in rs) else float("nan")
        L.append(f"| {arm} | {len(rs)} | {m('n_valid'):.0f} | {m('seed'):.4f} | {m('best'):.4f} | {max(r['best'] for r in rs):.5f} | {sum(r['improved'] for r in rs)} | "
                 f"{sum(r['exit'] for r in rs)} | {sum(1 for r in rs if r['family']=='F_rec')} | {m('bits50'):.2f} ({sum(1 for r in rs if r['bits50'] is not None)} atingem) | {m('bits90'):.2f} ({sum(1 for r in rs if r['bits90'] is not None)} atingem) |")
    L.append("\n## S2 (primário): saídas de família por corrida, Fisher exato; melhor θ, Mann–Whitney\n")
    L.append("| contraste | saídas | p Fisher | melhor θ (médias) | p MW |"); L.append("|---|---|---|---|---|")
    for a, b in (("D_opus", "C2_opus"), ("D_opus", "C1_none"), ("D_opus", "D0_opus"), ("D_kimi", "C2_kimi"), ("D_kimi", "D0_kimi"), ("D0_opus", "A"), ("D_opus", "A")):
        if a not in by or b not in by: continue
        xa, xb = by[a], by[b]; e1, e0 = sum(r["exit"] for r in xa), sum(not r["exit"] for r in xa); f1, f0 = sum(r["exit"] for r in xb), sum(not r["exit"] for r in xb)
        L.append(f"| {a} vs {b} | {e1}/{len(xa)} vs {f1}/{len(xb)} | {fisher(e1, e0, f1, f0):.4f} | {sum(r['best'] for r in xa)/len(xa):.4f} vs {sum(r['best'] for r in xb)/len(xb):.4f} | {mannwhitney([r['best'] for r in xa], [r['best'] for r in xb]):.4f} |")
    L.append("\n## Corridas\n"); L.append("| corrida | semente | melhor | válidos | família | saída | bits50 | bits90 |"); L.append("|---|---|---|---|---|---|---|---|")
    def fmt(v, spec):
        return "—" if v is None else format(v, spec)
    for r in sorted(rows, key=lambda r: (r["arm"], -r["best"])):
        L.append("| %s | %s | %.5f | %d/%d | %s | %s | %s | %s |" % (r["run"], fmt(r["seed"], ".4f"), r["best"], r["n_valid"], r["n"], r["family"],
                 "sim" if r["exit"] else "não", fmt(r["bits50"], ".1f"), fmt(r["bits90"], ".1f")))
    (ROOT / "docs/APPENDIX_P2_STAGE2.md").write_text("\n".join(L) + "\n"); print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
