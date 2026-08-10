"""Heuristic generation for verifier domains: prompt + function extraction.

The prompt is completion-style (base models, not chat): a module docstring,
two classic baselines as worked examples, then the header of `priority` for
the model to complete. Extraction cuts the completion at the first dedent —
the point where the function body ends.
"""

from __future__ import annotations

BINPACK_PROMPT = '''"""Online bin packing heuristics.

An item arrives; `remaining` lists the residual capacity of each bin the
item currently fits in. Return one score per feasible bin: the item is
placed in the bin with the highest score. If no bin fits, a new bin is
opened. Goal: use as few bins as possible over the whole stream.
"""

import math


def priority_first_fit(item: float, remaining: list[float]) -> list[float]:
    """First fit: take the oldest feasible bin."""
    return [0.0] * len(remaining)


def priority_best_fit(item: float, remaining: list[float]) -> list[float]:
    """Best fit: prefer the tightest feasible bin."""
    return [-(r - item) for r in remaining]


def priority(item: float, remaining: list[float]) -> list[float]:
    """A better heuristic than best fit for uniformly distributed item sizes."""
'''

HEADER = 'def priority(item: float, remaining: list[float]) -> list[float]:\n    """A better heuristic than best fit for uniformly distributed item sizes."""\n'


def extract_function(completion: str) -> str | None:
    """Body lines of the completed function, cut at the first dedent.

    Returns the full `def priority` source, or None when no real body was
    generated (empty, or dedents immediately).
    """
    body_lines: list[str] = []
    for line in completion.splitlines():
        if line.strip() == "":
            body_lines.append(line)
            continue
        if line.startswith((" ", "\t")):
            body_lines.append(line)
            continue
        break
    while body_lines and body_lines[-1].strip() == "":
        body_lines.pop()
    indents = [
        (i, len(line) - len(line.lstrip())) for i, line in enumerate(body_lines) if line.strip()
    ]
    if not indents:
        return None
    # Streaming detokenizers can drop a space at the completion boundary:
    # the FIRST body line arrives one space short while the rest are fine.
    # Realign only the first content line to the rest's base level.
    first_i, first_ind = indents[0]
    rest = [ind for _, ind in indents[1:]]
    level = min(rest) if rest else 4
    if first_ind != level:
        body_lines[first_i] = " " * level + body_lines[first_i].lstrip()
    return HEADER + "\n".join(body_lines) + "\n"
