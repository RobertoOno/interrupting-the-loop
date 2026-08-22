"""Sum-difference problem III (AlphaEvolve repository problem 44; Gyarmati-Hennecart-Ruzsa).
Candidate: `construct()` -> list of distinct non-negative integers U containing 0 (|U| <= 4000).
Score (MAXIMIZE): log(|U-U| / |U+U|) / log(2 max(U) + 1) + 1, a lower bound on the constant.
Records: Gyarmati et al. 2007 1.14465; AlphaEvolve 1.1479 (2003 ints), 1.1584 (54265 ints); later improved by
Gerbicz (arXiv 2505.16105) and Zheng (arXiv 2506.01896)."""
import math
import numpy as np

def verify(U, *_):
    if not isinstance(U, (list, tuple)) or len(U) < 2 or len(U) > 4000:
        return {"ok": False, "error": "need a list of 2..4000 integers"}
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in U):
        return {"ok": False, "error": "entries must be ints"}
    u = sorted(set(int(x) for x in U))
    if u[0] != 0 or any(x < 0 for x in u) or u[-1] > 2_000_000_000:
        return {"ok": False, "error": "need non-negative ints including 0"}
    M = u[-1]
    arr = np.asarray(u, dtype=np.int64)
    minus = np.zeros(2 * M + 1, dtype=bool); plus = np.zeros(2 * M + 1, dtype=bool)
    for x in u:
        minus[x - arr + M] = True; plus[x + arr] = True
    nm, npl = int(minus.sum()), int(plus.sum())
    return {"ok": True, "score": float(math.log(nm / npl) / math.log(2 * M + 1) + 1.0)}
