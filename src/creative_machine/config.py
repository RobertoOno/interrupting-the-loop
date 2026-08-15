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
        entropy_ceiling: Upper bound (nats) of the fertile band, or None for
            no bound. Very-high-entropy steps are document/genre forks — the
            observed collapse points (EOS bait, register switches into
            quiz/translation modes) — so above the ceiling the sampler stays
            on plain (floored) sampling: deviate inside the narrative, hold
            the rails at genre crossroads.
        coherence_floor: Relative probability floor (min-p style). A token is a
            perturbation candidate only if p(token) >= coherence_floor * p(top).
            Relative (not absolute) so the floor scales with how confident the
            model is at this step.
        lam: Weight (the plan's λ) of semantic distance in the perturbation
            score. 0 disables the distance pull, reducing perturbation mode to
            min-p sampling. With distance_scale="standardize", lam reads as
            nats per sigma of distance; useful range is roughly 0.5-3.
        distance_scale: How the distance term enters the score.
            "standardize" (default) z-scores distances across the step's
            candidates, giving lam a model-independent meaning and full
            resolution even when raw distances barely differ (token-embedding
            spaces are anisotropic: raw candidate spreads run ~0.1).
            "raw" uses cosine distances as-is.
        no_push_ids: Token ids (e.g. EOS) that never receive the distance
            bonus. They can still win a step on their own log-probability, in
            any mode — the perturbator just must not push the text into
            ending: leaving the text is not a deviation inside it.
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
    entropy_ceiling: float | None = None
    coherence_floor: float = 0.05
    lam: float = 1.5
    distance_scale: str = "standardize"
    no_push_ids: tuple[int, ...] = ()
    context_halflife: float = 16.0
    perturb_choice: str = "sample"
    max_candidates: int = 128
    repetition_window: int = 0       # 0 = off; else penalize tokens seen in the last N steps
    repetition_penalty: float = 1.5  # divisor on p for penalized tokens (>1 suppresses)
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.repetition_window < 0 or self.repetition_penalty <= 0:
            raise ValueError("repetition_window must be >= 0 and repetition_penalty > 0")
        self.no_push_ids = tuple(self.no_push_ids)
        if self.distance_scale not in ("raw", "standardize"):
            raise ValueError('distance_scale must be "raw" or "standardize"')
        if self.temperature <= 0:
            raise ValueError("temperature must be > 0")
        if self.entropy_trigger < 0:
            raise ValueError("entropy_trigger must be >= 0")
        if self.entropy_ceiling is not None and self.entropy_ceiling <= self.entropy_trigger:
            raise ValueError("entropy_ceiling must be > entropy_trigger (or None)")
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
