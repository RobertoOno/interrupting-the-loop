"""Per-step telemetry: what lets you watch the instrument while it plays."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class StepRecord:
    """One decoding step.

    Attributes:
        step: 0-based step index within the current generation.
        token_id: Chosen token.
        perturbed: Whether this step entered perturbation mode.
        entropy: Entropy (nats) of the full next-token distribution.
        logprob: Model log-probability of the chosen token.
        prob: Model probability of the chosen token.
        rank: 0-based rank of the chosen token (0 = model's top choice).
        distance: Semantic distance of the chosen token to the context EMA.
            None when the step did not compute distances (not perturbed, or no
            embeddings available).
        n_candidates: Number of tokens that passed the coherence floor.
            None when the step was not perturbed.
    """

    step: int
    token_id: int
    perturbed: bool
    entropy: float
    logprob: float
    prob: float
    rank: int
    distance: float | None
    n_candidates: int | None


class Telemetry:
    """Accumulates step records; serializes to JSONL; summarizes a run."""

    def __init__(self) -> None:
        self.records: list[StepRecord] = []

    def record(self, rec: StepRecord) -> None:
        self.records.append(rec)

    def reset(self) -> None:
        self.records = []

    def dumps_jsonl(self) -> str:
        return "\n".join(json.dumps(asdict(r)) for r in self.records)

    def to_jsonl(self, path: str | Path) -> None:
        Path(path).write_text(self.dumps_jsonl() + "\n")

    def summary(self) -> dict:
        n = len(self.records)
        if n == 0:
            return {"n_steps": 0}
        perturbed = [r for r in self.records if r.perturbed]
        mean_logprob = sum(r.logprob for r in self.records) / n
        out = {
            "n_steps": n,
            "perturb_rate": len(perturbed) / n,
            "mean_entropy": sum(r.entropy for r in self.records) / n,
            "mean_rank": sum(r.rank for r in self.records) / n,
            "mean_logprob": mean_logprob,
            "perplexity": math.exp(-mean_logprob),
        }
        if perturbed:
            out["mean_rank_perturbed"] = sum(r.rank for r in perturbed) / len(perturbed)
            distances = [r.distance for r in perturbed if r.distance is not None]
            if distances:
                out["mean_distance_perturbed"] = sum(distances) / len(distances)
        return out
