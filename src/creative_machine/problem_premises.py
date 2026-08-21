"""The interrupted loop over a PROBLEM with a verifier (roadmap item 8).

The 'premise' is a Python working notebook for online bin packing: the
module docstring states the item-size distribution of the variant, two
classic baselines are given as worked examples, and the notebook opens with
an idea heading. A base model continues it for thousands of tokens, writing
ideas and `def priority(...)` implementations; every complete function is
extracted afterwards and scored by the verifier (mean excess over the lower
bound on held-out instances of the same variant). Ten variants = ten cells.

Interruptions here are 'new angle' comments, all distinct (no rotation, so
the self-copy cycle of the narrative batteries cannot form), injected as
top-level comments so that they read as the next entry of the notebook.
"""

from __future__ import annotations

# ten item-size distributions (low, high) of the uniform draw; each variant is one cell
VARIANTS = [
    (0.10, 0.70), (0.05, 0.50), (0.20, 0.80), (0.10, 0.90), (0.30, 0.60),
    (0.05, 0.95), (0.15, 0.45), (0.25, 0.75), (0.10, 0.40), (0.40, 0.80),
]


def premise(low: float, high: float) -> str:
    return f'''"""Online bin packing heuristics: a working notebook.

An item arrives; `remaining` lists the residual capacity of each bin the
item currently fits in (bin capacity is 1.0). Return one score per feasible
bin: the item is placed in the bin with the highest score. If no bin fits, a
new bin is opened. Goal: use as few bins as possible over the whole stream.
In this variant item sizes are drawn uniformly from [{low:.2f}, {high:.2f}].
"""

import math


def priority_first_fit(item: float, remaining: list[float]) -> list[float]:
    """First fit: take the oldest feasible bin."""
    return [0.0] * len(remaining)


def priority_best_fit(item: float, remaining: list[float]) -> list[float]:
    """Best fit: prefer the tightest feasible bin."""
    return [-(r - item) for r in remaining]


# Below: ideas for priority functions that beat best fit on this variant,
# each idea written out as a comment and then implemented as `def priority`.

# Idea 1:'''


# fifteen distinct 'new angle' interruptions (one per 300-token segment of a 4,500-token stream)
ANGLES = [
    "\n\n# A completely different approach. Instead of the tightness of the fit, think about what the bin will be able to take later:",
    "\n\n# What if the score depends on how many bins are currently open, not only on the bin itself?",
    "\n\n# An idea borrowed from scheduling: reserve the large gaps for the large items that are still to come.",
    "\n\n# Think about the worst case for best fit on this size distribution, and score against it:",
    "\n\n# A probabilistic view: the expected number of future items that will fit in the leftover space.",
    "\n\n# Combine two of the ideas above into one score with a weight, and say why the weight should be what it is:",
    "\n\n# Forget the bins for a moment and look at the item: small items and large items may deserve different rules.",
    "\n\n# What would a human packer do with a half-empty bin that nothing has fit into for a while?",
    "\n\n# A threshold rule: treat a bin as 'closed' once its residual capacity falls below a value tied to the distribution.",
    "\n\n# Score the bins by how close the residual would land on a 'useful' size for the items to come:",
    "\n\n# Another angle entirely: penalize leaving a residual that no item in the range can ever fill.",
    "\n\n# Something that uses the exact bounds of the distribution given in the docstring:",
    "\n\n# A two-level rule: a primary criterion, and a tie-break that is not first-fit.",
    "\n\n# Take the best idea so far and make it more extreme; then make it less extreme; keep the better one:",
    "\n\n# Last idea, from the opposite direction: what is the simplest rule that could still beat best fit here?",
]

SHAM = ("\n\n#\n",)


# Battery C (consolidation): the small-item family, where best fit is beatable
# (headroom sweep, scripts/headroom2.py, 2026-08-21). Train variants are used for
# generation + consolidation; held-out variants measure transfer of the prior.
VARIANTS_C_TRAIN = [(0.02, 0.40), (0.04, 0.40), (0.06, 0.50), (0.08, 0.40), (0.10, 0.35),
                    (0.10, 0.50), (0.06, 0.55), (0.04, 0.45), (0.08, 0.35), (0.02, 0.55)]
VARIANTS_C_HELDOUT = [(0.05, 0.45), (0.07, 0.38), (0.03, 0.52), (0.09, 0.47), (0.05, 0.58),
                      (0.04, 0.50), (0.08, 0.55), (0.06, 0.42)]
