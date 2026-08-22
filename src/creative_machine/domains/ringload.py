"""Ring loading constant (AlphaEvolve repository problem 61).
Candidate: `construct(m)` -> list of m pairs (u_i, v_i), u_i, v_i >= 0, u_i + v_i <= 1.
Score (MAXIMIZE): alpha(u, v) = min over z in prod{v_i, -u_i} of max_k |sum(z[:k]) - sum(z[k:])|, exact by 2^m enumeration.
Records: AlphaEvolve alpha ~ 1.1190 at m = 15 (new result, 2025); the prompt says > 1.101 is 'easily possible'."""
import itertools, math

def verify(params, m):
    if not isinstance(params, (list, tuple)) or len(params) != m:
        return {"ok": False, "error": f"need a list of exactly {m} pairs"}
    u, v = [], []
    for it in params:
        if not isinstance(it, (list, tuple)) or len(it) != 2:
            return {"ok": False, "error": "each item must be a pair (u, v)"}
        try:
            a, b = float(it[0]), float(it[1])
        except Exception:
            return {"ok": False, "error": "non-numeric pair"}
        if not (math.isfinite(a) and math.isfinite(b)) or a < 0 or b < 0 or a + b > 1.000001:
            return {"ok": False, "error": "need u, v >= 0 and u + v <= 1"}
        u.append(a); v.append(b)
    best = float("inf")
    total_cache = None
    for z in itertools.product(*[(vi, -ui) for ui, vi in zip(u, v)]):
        tot = sum(z); pre = 0.0; mx = 0.0
        for k in range(1, m):
            pre += z[k - 1]
            d = abs(pre - (tot - pre))
            if d > mx:
                mx = d
        if mx < best:
            best = mx
    return {"ok": True, "score": float(best)}
