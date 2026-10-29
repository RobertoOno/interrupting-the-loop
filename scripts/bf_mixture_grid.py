#!/usr/bin/env python3
"""Is the beat-the-average wall the grid? Bellec-Fritz (arXiv:2412.15179):
nu = p d_0 + (1-p)/N sum_i d_{1-2^-i} gives P[strict] -> p(1-p)(2-p) = 0.3804 (Prop 4.1),
and Prop 3.3 lifts it to 0.400695 through the self-similar scale mixture
Y = X_1 + eta X_2 + eta^2 X_3 + ... (X_j iid ~ nu), whose infinitely many scales break
the ties X1+X2+X3 = 2X4. A finitely supported measure cannot be optimal. On an integer
grid of L points only ~log2(L) ladder atoms and ~log(L)/log(1/eta) mixture levels fit.
This script builds grid pmfs of the K-level mixture and evaluates them with the
harness objective (FFT convolutions), sweeping L, to see how the reachable value
grows with resolution. Loop finals for reference: 0.3876 (L=5000), 0.3899 (L=20000).

    python scripts/bf_mixture_grid.py
"""
import itertools
import numpy as np
from scipy.signal import fftconvolve


def score(p):
    p = np.maximum(np.asarray(p, float), 0); p = p / p.sum(); L = len(p)
    p12 = fftconvolve(p, p); py = fftconvolve(p12, p); py = np.maximum(py, 0)
    cdf = np.cumsum(py); probs = np.zeros(L); idx = 2 * np.arange(1, L) - 1; probs[1:] = cdf[np.minimum(idx, len(cdf) - 1)]
    tie = np.dot(p, py[np.minimum(2 * np.arange(L), len(py) - 1)])
    return float(np.dot(p, probs)), float(tie)


def ladder(p0, N, scale):
    """nu at scale: atom 0 (mass p0) + N atoms at (1-2^-i)*scale with mass (1-p0)/N; returns dict pos->mass (real positions)."""
    d = {0.0: p0}
    for i in range(1, N + 1):
        d[(1 - 0.5 ** i) * scale] = d.get((1 - 0.5 ** i) * scale, 0) + (1 - p0) / N
    return d


def mixture(L, p0, N, K, eta):
    """K-level mixture Y = X_1 + eta X_2 + ... on grid L; level-1 scale = top/(1+eta+...)."""
    top = L - 1; tot = sum(eta ** j for j in range(K)); s1 = top / tot
    levels = [ladder(p0, N, s1 * eta ** j) for j in range(K)]
    pmf = np.zeros(L)
    for combo in itertools.product(*[list(lv.items()) for lv in levels]):
        pos = sum(c[0] for c in combo); m = np.prod([c[1] for c in combo])
        pmf[min(int(round(pos)), top)] += m
    return pmf


if __name__ == "__main__":
    p0 = 0.474346
    print(f"Prop 4.1 limit (ladder alone): {p0*(1-p0)*(2-p0):.6f}; Prop 3.3 limit (mixture): {p0*(2-p0)/(1+p0+p0**2+p0**3):.6f}")
    print("\n L | best config (N, K, eta) | value | tie mass | ladder-only (K=1) best")
    for L in (5000, 20000, 1 << 17, 1 << 20, 1 << 22):
        best = (0, None); best1 = 0
        for N in (4, 6, 8, 10, 12, 14, 16, 20):
            for K in (1, 2, 3):
                for eta in ((1.0,) if K == 1 else (1/16, 1/64, 1/256, 1/1024)):
                    if (N + 1) ** K > 20000: continue
                    v, tie = score(mixture(L, p0, N, K, eta))
                    if K == 1: best1 = max(best1, v)
                    if v > best[0]: best = (v, (N, K, eta, tie))
        v, (N, K, eta, tie) = best
        print(f"{L:8d} | N={N:2d} K={K} eta=1/{int(round(1/eta)) if eta < 1 else 1:4d} | {v:.6f} | {tie:.4f} | {best1:.6f}")
