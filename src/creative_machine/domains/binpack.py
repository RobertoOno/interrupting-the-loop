"""Online bin packing — the first hard-verifier domain (roadmap item 7).

The candidate is a priority function, FunSearch-style:

    def priority(item: float, remaining: list[float]) -> list[float]

``remaining`` holds the residual capacity of each bin the item FITS in (the
simulator pre-filters feasibility); the function returns one score per bin
and the item goes to the highest-scoring one. No feasible bin -> a new bin
opens. Reality does the judging here: fewer bins is better, full stop.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

PriorityFn = Callable[[float, list[float]], Sequence[float]]

CAPACITY = 1.0
EPS = 1e-9


def generate_instances(
    n_instances: int,
    n_items: int,
    rng: np.random.Generator,
    low: float = 0.1,
    high: float = 0.7,
) -> list[list[float]]:
    return [list(rng.uniform(low, high, size=n_items)) for _ in range(n_instances)]


def lower_bound(items: Sequence[float]) -> int:
    return max(1, math.ceil(sum(items) - EPS))


def simulate(priority_fn: PriorityFn, items: Sequence[float]) -> int:
    """Number of bins used packing ``items`` online under ``priority_fn``."""
    remaining: list[float] = []
    for item in items:
        feasible = [i for i, r in enumerate(remaining) if r >= item - EPS]
        if not feasible:
            remaining.append(CAPACITY - item)
            continue
        scores = np.asarray(
            priority_fn(item, [remaining[i] for i in feasible]), dtype=np.float64
        )
        if scores.shape != (len(feasible),):
            raise ValueError(f"priority returned {scores.shape}, expected ({len(feasible)},)")
        if not np.all(np.isfinite(scores)):
            raise ValueError("priority returned non-finite scores")
        remaining[feasible[int(np.argmax(scores))]] -= item
    return len(remaining)


def evaluate(priority_fn: PriorityFn, instances: list[list[float]]) -> dict:
    """Mean excess over the lower bound — the verifier's verdict (lower=better)."""
    excesses, total = [], 0
    for items in instances:
        bins = simulate(priority_fn, items)
        lb = lower_bound(items)
        excesses.append((bins - lb) / lb)
        total += bins
    return {"mean_excess": float(np.mean(excesses)), "total_bins": total}


# Classic baselines. argmax over equal scores picks the first feasible bin,
# so a constant priority IS first-fit.
def first_fit(item: float, remaining: list[float]) -> list[float]:
    return [0.0] * len(remaining)


def best_fit(item: float, remaining: list[float]) -> list[float]:
    return [-(r - item) for r in remaining]


def worst_fit(item: float, remaining: list[float]) -> list[float]:
    return [r - item for r in remaining]
