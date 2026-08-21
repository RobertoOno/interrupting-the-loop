#!/usr/bin/env python3
"""Headroom sweep for battery C: on which item distributions is best fit
clearly beatable by simple online heuristics? Prints mean excess over the
lower bound per (distribution, heuristic); headroom = best fit minus the
best simple alternative (positive = beatable)."""
import sys, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from creative_machine.domains.binpack import evaluate, best_fit, first_fit, worst_fit

def dists():
    def uni(lo, hi):
        return lambda rng, n: list(np.clip(rng.uniform(lo, hi, n), 0.01, 1.0))
    def weib(shape, scale):
        return lambda rng, n: list(np.clip(rng.weibull(shape, n) * scale, 0.01, 1.0))
    def tri(lo, mode, hi):
        return lambda rng, n: list(np.clip(rng.triangular(lo, mode, hi, n), 0.01, 1.0))
    def bimodal(p, a, b):
        def g(rng, n):
            m = rng.random(n) < p
            return list(np.where(m, rng.uniform(*a, n), rng.uniform(*b, n)))
        return g
    def orlib():   # OR1-4 style: integer sizes 20..100, capacity 150
        return lambda rng, n: list(rng.integers(20, 101, n) / 150.0)
    return {
        "uni[0.10,0.70] (B v0)": uni(0.10, 0.70),
        "uni[0.05,0.50]": uni(0.05, 0.50),
        "uni[0.20,0.80]": uni(0.20, 0.80),
        "uni[0.35,0.50] spike": uni(0.35, 0.50),
        "uni[0.25,0.60]": uni(0.25, 0.60),
        "weibull(3,0.45)": weib(3.0, 0.45),
        "weibull(2,0.30)": weib(2.0, 0.30),
        "tri(0.05,0.40,0.75)": tri(0.05, 0.40, 0.75),
        "bimodal 0.6*[0.05,0.20]+0.4*[0.50,0.70]": bimodal(0.6, (0.05, 0.20), (0.50, 0.70)),
        "bimodal 0.5*[0.10,0.30]+0.5*[0.60,0.75]": bimodal(0.5, (0.10, 0.30), (0.60, 0.75)),
        "OR-lib 20..100/150": orlib(),
    }

# simple alternatives (recombination-shaped: the kind of thing a notebook writes)
def almost_full(t):   # prefer bins that become almost full; else best fit
    def f(item, rem):
        return [(10.0 if r - item <= t else 0.0) - (r - item) for r in rem]
    return f
def avoid_mid(lo, hi):  # avoid leaving a residual in a dead zone (too small for typical items, too big to waste)
    def f(item, rem):
        out = []
        for r in rem:
            left = r - item
            out.append(-left - (5.0 if lo < left < hi else 0.0))
        return out
    return f
def harmonic(k=4):      # prefer bins whose residual class matches the item's class
    def f(item, rem):
        ci = min(k - 1, int(item * k))
        out = []
        for r in rem:
            left = r - item
            cr = min(k - 1, int(left * k))
            out.append(-left + (1.0 if cr == ci else 0.0))
        return out
    return f
def second_best(item, rem):  # best fit but never perfect unless exact
    return [-(r - item) if r - item > 0.02 or r - item < 1e-9 else -(r - item) - 1.0 for r in rem]

HEUR = {"first_fit": first_fit, "best_fit": best_fit, "worst_fit": worst_fit,
        "almost_full_0.05": almost_full(0.05), "almost_full_0.10": almost_full(0.10),
        "avoid_mid_0.05_0.25": avoid_mid(0.05, 0.25), "avoid_mid_0.10_0.30": avoid_mid(0.10, 0.30),
        "harmonic4": harmonic(4), "harmonic6": harmonic(6), "second_best": second_best}

print(f"{'distribution':42s} {'BF':>7s} {'FF':>7s} {'best alt':>9s} {'alt name':22s} {'headroom':>9s}")
for name, gen in dists().items():
    rng = np.random.default_rng(123)
    inst = [gen(rng, 100) for _ in range(8)]
    res = {h: evaluate(f, inst)["mean_excess"] for h, f in HEUR.items()}
    bf = res["best_fit"]
    alt = min((v, h) for h, v in res.items() if h not in ("best_fit",))
    print(f"{name:42s} {bf:7.4f} {res['first_fit']:7.4f} {alt[0]:9.4f} {alt[1]:22s} {bf-alt[0]:+9.4f}")
