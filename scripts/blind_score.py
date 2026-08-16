#!/usr/bin/env python3
"""Score a blind rating against its key: human vs LLM-judge agreement
(Spearman per dimension), and per-condition human means with bootstrap CIs.

    python scripts/blind_score.py runs/blind/key_v1.json ratings_v1.json
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


def main() -> None:
    key = json.loads(Path(sys.argv[1]).read_text())
    ratings = json.loads(Path(sys.argv[2]).read_text())["ratings"]
    rows = [{**it, **ratings[it["id"]]} for it in key if it["id"] in ratings and "surprise" in ratings[it["id"]]]
    print(f"{len(rows)} rated of {len(key)}")
    for dim, jkey in (("surprise", "judge_surprise"), ("coherence", "judge_coherence")):
        h = [r[dim] for r in rows if r.get(jkey) is not None]
        j = [r[jkey] for r in rows if r.get(jkey) is not None]
        rho, p = spearmanr(h, j)
        print(f"{dim:<10} human vs Opus: Spearman ρ={rho:+.2f} (p={p:.1e}, n={len(h)}); mean human {np.mean(h):.2f} vs Opus {np.mean(j):.2f}")
    conds = sorted({r["cond"] for r in rows})
    print("\nper condition (human): mean surprise / coherence [n]")
    by = {c: [r for r in rows if r["cond"] == c] for c in conds}
    for c in conds:
        rs = by[c]
        print(f"  {c:<14} S {np.mean([r['surprise'] for r in rs]):.2f}  H {np.mean([r['coherence'] for r in rs]):.2f}  [n={len(rs)}]"
              f"   (Opus: S {np.mean([r['judge_surprise'] for r in rs]):.2f})")
    if "bare" in by:
        for c in conds:
            if c == "bare" or len(by[c]) < 2:
                continue
            lo, hi = bootstrap_diff_ci([r["surprise"] for r in by[c]], [r["surprise"] for r in by["bare"]])
            print(f"  surprise {c} − bare: [{lo:+.2f}, {hi:+.2f}]")


if __name__ == "__main__":
    main()
