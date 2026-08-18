#!/usr/bin/env python3
"""Score a blind rating against its key: human vs LLM-judge agreement
(Spearman per dimension), and per-condition human means with bootstrap CIs.

    python scripts/blind_score.py runs/blind/key_v1.json ratings_v1.json [ratings_rater2.json ...]

With several rating files (same pack), also reports human–human agreement
(pairwise Spearman and Krippendorff's alpha, interval) and the mean-of-raters
vs Opus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.stats import bootstrap_diff_ci  # noqa: E402


def krippendorff_alpha_interval(matrix):
    """matrix: raters x items with np.nan for missing. Interval metric."""
    m = np.asarray(matrix, dtype=float)
    items = [m[:, j][~np.isnan(m[:, j])] for j in range(m.shape[1])]
    items = [v for v in items if len(v) >= 2]
    if not items:
        return float("nan")
    n = sum(len(v) for v in items)
    Do = sum(((v[:, None] - v[None, :]) ** 2).sum() / (len(v) - 1) for v in items) / n
    allv = np.concatenate(items)
    De = ((allv[:, None] - allv[None, :]) ** 2).sum() / (n - 1) / n
    return float(1 - Do / De) if De > 0 else float("nan")


def main() -> None:
    key = json.loads(Path(sys.argv[1]).read_text())
    rating_files = sys.argv[2:]
    all_ratings = [json.loads(Path(f).read_text())["ratings"] for f in rating_files]
    DIMS = tuple(d for d in ("surprise", "connection", "coherence")
                 if any(d in v for r in all_ratings for v in r.values()))
    if len(all_ratings) > 1:
        print(f"{len(all_ratings)} raters; dimensions rated: {DIMS}")
        for dim in DIMS:
            ids = [it["id"] for it in key]
            M = np.array([[r.get(i, {}).get(dim, np.nan) for i in ids] for r in all_ratings], dtype=float)
            pair = []
            for a in range(len(all_ratings)):
                for b in range(a + 1, len(all_ratings)):
                    ok = ~np.isnan(M[a]) & ~np.isnan(M[b])
                    if ok.sum() >= 5:
                        pair.append(spearmanr(M[a][ok], M[b][ok])[0])
            print(f"  {dim:<10} human–human: pairwise Spearman {np.round(pair, 2).tolist()}; Krippendorff α (interval) = {krippendorff_alpha_interval(M):.2f}")
        # mean of raters as the human score
        ratings = {}
        for it in key:
            vals = {d: [r[it["id"]][d] for r in all_ratings if it["id"] in r and d in r[it["id"]]] for d in DIMS}
            if vals["surprise"]:
                ratings[it["id"]] = {d: float(np.mean(v)) for d, v in vals.items() if v}
        print("  (below: mean of raters vs Opus)")
    else:
        ratings = all_ratings[0]
    rows = [{**it, **ratings[it["id"]]} for it in key if it["id"] in ratings and "surprise" in ratings[it["id"]]]
    print(f"{len(rows)} rated of {len(key)}")
    for dim in DIMS:
        jkey = "judge_" + dim
        h = [r[dim] for r in rows if r.get(jkey) is not None and r.get(dim) is not None]
        j = [r[jkey] for r in rows if r.get(jkey) is not None and r.get(dim) is not None]
        rho, p = spearmanr(h, j)
        print(f"{dim:<10} human vs Opus: Spearman ρ={rho:+.2f} (p={p:.1e}, n={len(h)}); mean human {np.mean(h):.2f} vs Opus {np.mean(j):.2f}")
    conds = sorted({r["cond"] for r in rows})
    print("\nper condition (human): mean " + " / ".join(DIMS) + " [n windows]   (Opus surprise on the same windows)")
    by = {c: [r for r in rows if r["cond"] == c] for c in conds}
    for c in conds:
        rs = by[c]
        means = "  ".join(f"{d[0].upper()} {np.mean([r[d] for r in rs if r.get(d) is not None]):.2f}" for d in DIMS)
        print(f"  {c:<16} {means}  [n={len(rs)}]   (Opus: S {np.mean([r['judge_surprise'] for r in rs]):.2f})")
    # seed-level view: one value per (condition, cell) = mean over that cell's windows
    print("\nper condition, unit = cell (mean of the cell's windows): mean surprise [n cells]")
    for c in conds:
        cells = {}
        for r in by[c]:
            cells.setdefault(r["cell"], []).append(r["surprise"])
        v = [np.mean(x) for x in cells.values()]
        print(f"  {c:<16} S {np.mean(v):.2f}  [n cells={len(v)}]")
    if "bare" in by:
        for c in conds:
            if c == "bare" or len(by[c]) < 2:
                continue
            lo, hi = bootstrap_diff_ci([r["surprise"] for r in by[c]], [r["surprise"] for r in by["bare"]])
            print(f"  surprise {c} − bare: [{lo:+.2f}, {hi:+.2f}]")


if __name__ == "__main__":
    main()
