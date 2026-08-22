"""First autocorrelation inequality (AlphaEvolve repository problem 2; Matolcsi-Vinuesa 2009).
Candidate: `construct()` -> list of n non-negative floats (heights of equal-width steps on [-1/4, 1/4]).
Score (MINIMIZE): 2 n max(a*a) / (sum a)^2, an upper bound on the constant C1.
Records: MV 2009 1.50992; AlphaEvolve 1.5053 (May 2025), 1.5032 (Dec 2025); Yuksekgonul et al. 1.5029 (Jan 2026)."""
import math
import numpy as np

def verify(seq, *_):
    if not isinstance(seq, (list, tuple)) or len(seq) < 300 or len(seq) > 5000:
        return {"ok": False, "error": "need a list of 300..5000 numbers"}
    try:
        a = np.asarray([float(x) for x in seq], dtype=np.float64)
    except Exception:
        return {"ok": False, "error": "non-numeric entry"}
    if not np.all(np.isfinite(a)) or np.any(a < 0) or np.any(a > 1000):
        return {"ok": False, "error": "entries must be finite, non-negative and <= 1000"}
    s = float(a.sum())
    if s < 0.01:
        return {"ok": False, "error": "sum too small"}
    n = len(a)
    b = np.convolve(a, a)
    return {"ok": True, "score": float(2 * n * b.max() / (s * s))}
