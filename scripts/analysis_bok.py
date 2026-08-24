#!/usr/bin/env python3
"""Equal-budget analyses for battery C requested by the external review: best-of-k by
subsampling (k = 10/20/40), pass@k vs the better classic, and quantiles of valid-candidate
test excess, per arm at cycle 5 on the held-out variants. Writes docs/APPENDIX_C_BOK.md."""
import json, sys
from pathlib import Path
import numpy as np
R = Path("runs/dream_c")
ARMS = {"base": "base_c5", "attract": "attract_c5", "random": "random_c5"}
rng = np.random.default_rng(0)
md = ["# Appendix — Battery C equal-budget analyses (best-of-k, pass@k, quantiles)\n",
      "Held-out variants, cycle-5 arms, test excess of valid candidates. best-of-k: mean over 2000 subsamples "
      "of k candidates per variant (variants with fewer than k valid candidates are skipped for that k). "
      "pass@k: probability that a subsample of k contains a candidate beating min(BF, FF) on test.\n"]
for k_ in (10, 20, 40):
    md.append(f"\n## k = {k_}\n")
    md.append("| arm | variants used | best-of-k (mean excess of subsample best) | pass@k vs classics |")
    md.append("|---|---|---|---|")
    for arm, d in ARMS.items():
        c = json.loads((R / d / "candidates.json").read_text())
        boks, passes, used = [], [], 0
        for v in range(8):
            xs = np.array([x["test"] for x in c.values() if x["which"] == "heldout" and x["variant"] == v and x["ok"] and x.get("test") is not None])
            refs = [min(x["bf_test"], x["ff_test"]) for x in c.values() if x["which"] == "heldout" and x["variant"] == v and x["ok"] and x.get("test") is not None]
            if len(xs) < k_:
                continue
            used += 1; ref = refs[0]
            idx = rng.integers(0, len(xs), (2000, k_))
            best = xs[idx].min(axis=1)
            boks.append(best.mean()); passes.append(float((best < ref - 1e-9).mean()))
        if boks:
            md.append(f"| {arm} | {used}/8 | {np.mean(boks):.4f} | {np.mean(passes):.4f} |")
md.append("\n## Quantiles of valid-candidate test excess (pooled over held-out variants)\n")
md.append("| arm | n | p10 | p50 | p90 | p99 |"); md.append("|---|---|---|---|---|---|")
for arm, d in ARMS.items():
    c = json.loads((R / d / "candidates.json").read_text())
    xs = np.array([x["test"] for x in c.values() if x["which"] == "heldout" and x["ok"] and x.get("test") is not None])
    md.append(f"| {arm} | {len(xs)} | {np.percentile(xs,10):.4f} | {np.percentile(xs,50):.4f} | {np.percentile(xs,90):.4f} | {np.percentile(xs,99):.4f} |")
Path("docs/APPENDIX_C_BOK.md").write_text("\n".join(md) + "\n"); print("\n".join(md[-12:]))
