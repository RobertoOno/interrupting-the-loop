"""Minimal statistics for experiment aggregation (numpy only)."""

from __future__ import annotations

import numpy as np


def bootstrap_diff_ci(
    a,
    b,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Nonparametric bootstrap CI for mean(a) - mean(b).

    If the interval excludes 0, the difference is significant at level alpha.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if len(a) == 0 or len(b) == 0:
        raise ValueError("both samples must be non-empty")
    rng = rng or np.random.default_rng(0)
    ia = rng.integers(0, len(a), size=(n_resamples, len(a)))
    ib = rng.integers(0, len(b), size=(n_resamples, len(b)))
    diffs = a[ia].mean(axis=1) - b[ib].mean(axis=1)
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def mean_std(xs) -> tuple[float, float]:
    xs = np.asarray(xs, dtype=np.float64)
    return float(xs.mean()), float(xs.std(ddof=1)) if len(xs) > 1 else 0.0
