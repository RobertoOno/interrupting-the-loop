"""Beat-the-average game (AlphaEvolve repository problem 39).
Candidate: `construct(L)` -> list of L non-negative floats (a pmf on {0, ..., L-1}, normalized by the verifier).
Score (MAXIMIZE): P[X1 + X2 + X3 < 2 X4] for i.i.d. X ~ pmf.
Records: Bellec-Fritz 0.400695 (best known, continuous); AlphaEvolve 0.3890 at L = 20000."""
import numpy as np

def verify(pmf, L):
    if not isinstance(pmf, (list, tuple)) or len(pmf) != L:
        return {"ok": False, "error": f"need a list of exactly {L} numbers"}
    try:
        p = np.asarray([float(x) for x in pmf], dtype=np.float64)
    except Exception:
        return {"ok": False, "error": "non-numeric entry"}
    if not np.all(np.isfinite(p)):
        return {"ok": False, "error": "non-finite entry"}
    p = np.maximum(p, 0.0)
    s = p.sum()
    if s <= 1e-8:
        return {"ok": False, "error": "zero mass"}
    p = p / s
    p12 = np.convolve(p, p); py = np.convolve(p12, p); cdf = np.cumsum(py)
    probs = np.zeros(L); idx = 2 * np.arange(1, L) - 1; probs[1:] = cdf[idx]
    return {"ok": True, "score": float(np.dot(p, probs))}
