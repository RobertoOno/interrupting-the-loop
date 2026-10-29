#!/usr/bin/env python3
"""Is the beat-the-average wall a missing idea or the continuum limit?
Bellec-Fritz (arXiv:2412.15179, Prop. 4.1): nu = p d_0 + (1-p)/N sum_{i=1..N} d_{1-2^-i},
value -> p(1-p)(2-p) = 0.400695 as N -> inf (p = 0.474346). On an integer grid of
L points the ladder 1-2^-i collides with the top at i ~ log2(L): N is capped at
~12 (L=5000) / ~14 (L=20000). This script computes the EXACT objective for
sparse atoms (no grid) at each N, with uniform and with optimized weights, and
the same on the grid-rounded ladder, to compare with the loops' finals
(0.3876 at L=5000, 0.3899 at L=20000).

    python scripts/bf_ladder_limit.py
"""
import numpy as np
from scipy.optimize import minimize


def exact(a, w):
    """P[X1+X2+X3 < 2 X4] for atoms a with weights w (exact, O(k^3 log k))."""
    a = np.asarray(a, float); w = np.asarray(w, float); w = w / w.sum()
    s3 = (a[:, None, None] + a[None, :, None] + a[None, None, :]).ravel()
    w3 = (w[:, None, None] * w[None, :, None] * w[None, None, :]).ravel()
    o = np.argsort(s3, kind="stable"); s3, w3 = s3[o], np.concatenate(([0.0], np.cumsum(w3[o])))
    return float(w @ w3[np.searchsorted(s3, 2 * a, side="left")])


def optimize_weights(a, w0, iters=3):
    best = (exact(a, w0), np.asarray(w0, float))
    for _ in range(iters):
        z0 = np.log(best[1] + 1e-12) + np.random.default_rng(_).normal(0, 0.05, len(a))
        res = minimize(lambda z: -exact(a, np.exp(z - z.max())), z0, method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-8, "fatol": 1e-10})
        w = np.exp(res.x - res.x.max()); w /= w.sum(); v = exact(a, w)
        if v > best[0]: best = (v, w)
    return best


p = 0.474346
print("Bellec-Fritz limit p(1-p)(2-p) =", round(p * (1 - p) * (2 - p), 6))
print("\nContinuous ladder 1-2^-i, exact objective:")
print(" N | uniform (1-p)/N | optimized weights (same atoms)")
for N in (6, 8, 10, 12, 14, 16, 20, 30):
    a = np.concatenate(([0.0], 1 - 0.5 ** np.arange(1, N + 1)))
    w = np.concatenate(([p], np.full(N, (1 - p) / N)))
    u = exact(a, w); v, _ = optimize_weights(a, w, iters=2 if N <= 16 else 1)
    print(f"{N:3d} | {u:.6f} | {v:.6f}")
print("\nGrid-rounded ladder (integer positions on {0..L-1}; atoms collide near the top):")
for L in (5000, 20000):
    top = L - 1
    pos = sorted({int(round((1 - 0.5 ** i) * top)) for i in range(1, 40)} - {top})  # distinct grid atoms
    a = np.array([0.0] + pos, float); N = len(pos)
    w = np.concatenate(([p], np.full(N, (1 - p) / N)))
    u = exact(a, w); v, _ = optimize_weights(a, w, iters=2)
    print(f"L={L}: distinct ladder atoms N={N} (cap ~ log2 L); uniform {u:.6f}; optimized weights {v:.6f}"
          f"  | loop finals: {'0.3876 (30B/27B, L=5000)' if L == 5000 else '0.3899 (Claude, L=20000)'}")
