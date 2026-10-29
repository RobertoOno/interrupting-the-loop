"""Paired, premise-as-unit statistics shared by the branch-C analyses (a testable copy of the
helpers analysis_r4.py carried inline): exact sign-flip permutation for n <= 14, seeded Monte-Carlo
sign-flip beyond, bootstrap and t confidence intervals, two one-sided tests of equivalence (TOST),
its power at a true difference of zero, and Benjamini-Hochberg q-values."""

from __future__ import annotations

import itertools
import math

import numpy as np


def signflip(d, alt: str = "greater", exact_max: int = 14, mc: int = 200000, seed: int = 1) -> dict:
    """Sign-flip permutation test on paired differences d. alt: 'greater' (mean > 0) or 'two-sided'.
    Exact over all 2^n sign patterns for n <= exact_max; otherwise seeded Monte-Carlo with the +1
    correction. Returns mean, p, n, exact flag."""
    d = np.asarray(d, float)
    n = len(d)
    if n == 0:
        return {"mean": float("nan"), "p": float("nan"), "n": 0, "exact": False}
    obs = float(d.mean())
    if alt == "greater":
        stat = lambda m: m >= obs - 1e-12
    elif alt == "two-sided":
        stat = lambda m: abs(m) >= abs(obs) - 1e-12
    else:
        raise ValueError(alt)
    if n <= exact_max:
        cnt = sum(1 for sg in itertools.product((1, -1), repeat=n) if stat((d * np.array(sg)).mean()))
        return {"mean": obs, "p": cnt / 2 ** n, "n": n, "exact": True}
    sg = np.random.default_rng(seed).choice((1, -1), size=(mc, n))
    hits = int(np.sum([stat(m) for m in (d * sg).mean(1)]))
    return {"mean": obs, "p": (hits + 1) / (mc + 1), "n": n, "exact": False}


def boot_ci(d, conf: float = 0.95, n_boot: int = 20000, seed: int = 0):
    d = np.asarray(d, float)
    if len(d) == 0:
        return float("nan"), float("nan")
    idx = np.random.default_rng(seed).integers(0, len(d), (n_boot, len(d)))
    a = (1 - conf) / 2
    lo, hi = np.percentile(d[idx].mean(1), [100 * a, 100 * (1 - a)])
    return float(lo), float(hi)


def t_ci(d, conf: float = 0.95):
    from scipy import stats
    d = np.asarray(d, float)
    n = len(d)
    m = float(d.mean()) if n else float("nan")
    if n < 2:
        return m, float("nan"), float("nan")
    se = d.std(ddof=1) / math.sqrt(n)
    tc = stats.t.ppf(0.5 + conf / 2, n - 1)
    return m, float(m - tc * se), float(m + tc * se)


def tost(d, margin: float) -> dict:
    """Two one-sided t tests; equivalence when both p < .05 (the 90% t interval sits inside +-margin)."""
    from scipy import stats
    d = np.asarray(d, float)
    n = len(d)
    m, sd = float(d.mean()), float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    if se == 0:
        p = 0.0 if abs(m) < margin else 1.0
        return {"mean": m, "sd": sd, "n": n, "ic90": (m, m), "p_tost": p, "equiv": p < 0.05, "margin": margin}
    p_lo = 1 - stats.t.cdf((m + margin) / se, n - 1)
    p_hi = stats.t.cdf((m - margin) / se, n - 1)
    tcrit = stats.t.ppf(0.95, n - 1)
    return {"mean": m, "sd": sd, "n": n, "ic90": (m - tcrit * se, m + tcrit * se), "p_tost": max(p_lo, p_hi),
            "equiv": max(p_lo, p_hi) < 0.05, "margin": margin}


def power_tost(sd: float, n: int, margin: float) -> float:
    from scipy import stats
    se = sd / math.sqrt(n)
    half = stats.t.ppf(0.95, n - 1) * se
    if half >= margin:
        return 0.0
    return float(stats.norm.cdf((margin - half) / se) - stats.norm.cdf(-(margin - half) / se))


def bh(ps):
    """Benjamini-Hochberg q-values (monotone), same order as ps."""
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    q = np.empty(len(ps))
    prev = 1.0
    for rank, i in list(enumerate(order))[::-1]:
        prev = min(prev, ps[i] * len(ps) / (rank + 1))
        q[i] = prev
    return q
