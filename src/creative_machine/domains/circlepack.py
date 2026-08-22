"""Circle packing in the unit square (AlphaEvolve / ShinkaEvolve benchmark):
place n circles inside [0,1]^2, pairwise non-overlapping, maximizing the sum of
radii. Best known for n=26: ~2.635 (AlphaEvolve 2025), ~2.6359 (ShinkaEvolve 2025;
values to be re-verified against the sources). A candidate is a Python program
defining `construct(n) -> list[(x, y, r)]`. Verification is exact arithmetic with a
tolerance: every circle inside the square, no two overlapping; score = sum(r)."""
from __future__ import annotations
import math
from typing import Sequence

EPS = 1e-9

def verify(circles: Sequence[Sequence[float]], n: int) -> dict:
    if len(circles) != n:
        return {"ok": False, "error": f"expected {n} circles, got {len(circles)}"}
    cs = []
    for c in circles:
        if len(c) != 3:
            return {"ok": False, "error": "each circle must be (x, y, r)"}
        x, y, r = float(c[0]), float(c[1]), float(c[2])
        if not all(math.isfinite(v) for v in (x, y, r)) or r <= 0:
            return {"ok": False, "error": "non-finite or non-positive radius"}
        if x - r < -EPS or x + r > 1 + EPS or y - r < -EPS or y + r > 1 + EPS:
            return {"ok": False, "error": "circle outside the unit square"}
        cs.append((x, y, r))
    for i in range(n):
        xi, yi, ri = cs[i]
        for j in range(i + 1, n):
            xj, yj, rj = cs[j]
            if math.hypot(xi - xj, yi - yj) < ri + rj - 1e-7:
                return {"ok": False, "error": f"circles {i} and {j} overlap"}
    return {"ok": True, "score": float(sum(c[2] for c in cs))}
