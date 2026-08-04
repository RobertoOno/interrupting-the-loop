"""Sampler configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SamplerConfig:
    """Parameters of the entropy-adaptive anti-probable sampler.

    The decoding policy: at each step, compute the entropy of the model's
    next-token distribution. Below ``entropy_trigger`` (peaked distribution:
    syntax, names, arithmetic) sample normally. At or above it (a genuine
    branching point), restrict to tokens that pass the coherence floor and
    re-score them by ``log P(token) + lam * semantic_distance(token, context)``,
    deliberately favoring the improbable-but-possible tail.

    Attributes:
        temperature: Softmax temperature applied to incoming logits.
        entropy_trigger: Entropy threshold in nats. Steps with entropy >= this
            value enter perturbation mode; below it, plain sampling.
        coherence_floor: Relative probability floor (min-p style). A token is a
            perturbation candidate only if p(token) >= coherence_floor * p(top).
            Relative (not absolute) so the floor scales with how confident the
            model is at this step.
        lam: Weight (the plan's λ) of semantic distance in the perturbation
            score. 0 disables the distance pull, reducing perturbation mode to
            min-p sampling.
        context_halflife: Half-life, in tokens, of the exponential moving
            average over token embeddings that represents "the context" for
            distance measurement.
        perturb_choice: How to pick among scored candidates: "sample" draws
            from softmax(scores); "argmax" takes the top score deterministically.
        max_candidates: Cap on candidates entering the embedding lookup and
            scoring, keeping the per-step cost bounded. Candidates are the
            highest-probability tokens passing the floor.
        seed: Seed for the sampler's RNG when no generator is supplied.
    """

    temperature: float = 1.0
    entropy_trigger: float = 2.0
    coherence_floor: float = 0.05
    lam: float = 3.0
    context_halflife: float = 16.0
    perturb_choice: str = "sample"
    max_candidates: int = 128
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.temperature <= 0:
            raise ValueError("temperature must be > 0")
        if self.entropy_trigger < 0:
            raise ValueError("entropy_trigger must be >= 0")
        if not 0 < self.coherence_floor <= 1:
            raise ValueError("coherence_floor must be in (0, 1]")
        if self.lam < 0:
            raise ValueError("lam must be >= 0")
        if self.context_halflife <= 0:
            raise ValueError("context_halflife must be > 0")
        if self.perturb_choice not in ("sample", "argmax"):
            raise ValueError('perturb_choice must be "sample" or "argmax"')
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
