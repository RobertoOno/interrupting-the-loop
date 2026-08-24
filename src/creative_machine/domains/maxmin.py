"""Max/min distance ratio (AlphaEvolve repository problem 50; Friedman's maxmin tables).
Candidate: `construct(n, d)` -> n points in d dimensions. Score (MINIMIZE): (max pairwise
distance / min pairwise distance)^2 — the squared-ratio convention of the reference tables.
Records (2D, n=16): 12.89 (Friedman) -> 12.889266112 (AlphaEvolve 2025)."""
import numpy as np
from scipy.spatial.distance import pdist

def verify(points, n, d):
    if not isinstance(points, (list, tuple)) or len(points) != n:
        return {"ok": False, "error": f"need exactly {n} points"}
    try:
        P = np.asarray([[float(c) for c in p] for p in points], dtype=np.float64)
    except Exception:
        return {"ok": False, "error": "non-numeric point"}
    if P.shape != (n, d) or not np.all(np.isfinite(P)):
        return {"ok": False, "error": f"each point needs {d} finite coordinates"}
    dist = pdist(P)
    mn = float(dist.min())
    if mn <= 1e-12:
        return {"ok": False, "error": "duplicate points"}
    return {"ok": True, "score": float((dist.max() / mn) ** 2)}
