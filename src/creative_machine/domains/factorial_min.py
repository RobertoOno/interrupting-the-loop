"""Factoring N! into N factors maximizing the smallest factor (AlphaEvolve repository
problem 38; OEIS A034258 family). Candidate: `construct(n)` -> a list of n positive
integers whose product is EXACTLY n! (verified in exact arithmetic).
Score (MAXIMIZE): the minimum factor. Records (N = 180): 51 -> 54 (AlphaEvolve, exact;
since improved by others)."""
import math

def verify(factors, n):
    if not isinstance(factors, (list, tuple)) or len(factors) != n:
        return {"ok": False, "error": f"need exactly {n} integers"}
    if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in factors):
        return {"ok": False, "error": "entries must be positive ints"}
    prod = 1
    for x in factors:
        prod *= x
    if prod != math.factorial(n):
        return {"ok": False, "error": "product is not exactly n!"}
    return {"ok": True, "score": float(min(factors))}
