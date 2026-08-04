"""Entropy-adaptive anti-probable sampler — the perturbator organ.

Coherence lives disproportionately in the low-entropy steps (syntax, names,
arithmetic), so those are left untouched. The fertile points are high-entropy
branchings, where the model itself admits many continuations; only there does
the sampler reach into the tail, pulled by semantic distance and held by the
coherence floor:

    score(token) = log P(token | context) + lam * distance(token, context)

"Context" is an exponential moving average over the embeddings of tokens seen
so far (prompt included, via :meth:`AntiprobableSampler.observe_many`).
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

import numpy as np

from .config import SamplerConfig
from .metrics import cosine_distances, entropy, log_softmax, token_rank
from .telemetry import StepRecord, Telemetry

# Maps an array of token ids (k,) to their embedding vectors (k, d).
EmbedFn = Callable[[np.ndarray], np.ndarray]


class AntiprobableSampler:
    """Stateful sampler: feed logits step by step, get token ids back.

    Args:
        config: Decoding policy parameters.
        embed_fn: Token-id -> embedding lookup used for semantic distance.
            When None, distances are 0 and perturbation mode degenerates to
            min-p sampling at high-entropy steps.
        rng: Optional numpy Generator; defaults to one seeded from config.seed.
        telemetry: Optional shared Telemetry; one is created if omitted.
    """

    def __init__(
        self,
        config: SamplerConfig | None = None,
        embed_fn: Optional[EmbedFn] = None,
        rng: np.random.Generator | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.config = config or SamplerConfig()
        self.embed_fn = embed_fn
        self.rng = rng or np.random.default_rng(self.config.seed)
        self.telemetry = telemetry or Telemetry()
        self._decay = 0.5 ** (1.0 / self.config.context_halflife)
        self._context: np.ndarray | None = None
        self._step = 0

    def reset(self) -> None:
        """Clear context and step counter (telemetry is left to its owner)."""
        self._context = None
        self._step = 0

    @property
    def context(self) -> np.ndarray | None:
        """Current context EMA vector (None before any observation)."""
        return self._context

    def observe(self, token_id: int) -> None:
        """Fold one token's embedding into the context EMA without sampling."""
        if self.embed_fn is None:
            return
        vec = np.asarray(self.embed_fn(np.array([token_id])), dtype=np.float64)[0]
        self._update_context(vec)

    def observe_many(self, token_ids: Sequence[int]) -> None:
        """Fold a token sequence (e.g. the prompt) into the context EMA.

        One batched embedding lookup, then sequential EMA updates.
        """
        if self.embed_fn is None or len(token_ids) == 0:
            return
        vecs = np.asarray(self.embed_fn(np.asarray(token_ids)), dtype=np.float64)
        for vec in vecs:
            self._update_context(vec)

    def step(self, logits: np.ndarray) -> int:
        """Choose the next token for one step's logits (or logprobs)."""
        cfg = self.config
        logprobs = log_softmax(logits, cfg.temperature)
        h = entropy(logprobs)

        if h >= cfg.entropy_trigger:
            token, distance, n_candidates = self._perturb(logprobs)
            perturbed = True
        else:
            token = self._gumbel_argmax(logprobs)
            distance, n_candidates = None, None
            perturbed = False

        self.telemetry.record(
            StepRecord(
                step=self._step,
                token_id=token,
                perturbed=perturbed,
                entropy=h,
                logprob=float(logprobs[token]),
                prob=float(np.exp(logprobs[token])),
                rank=token_rank(logprobs, token),
                distance=distance,
                n_candidates=n_candidates,
            )
        )
        self._step += 1
        self.observe(token)
        return token

    def _perturb(self, logprobs: np.ndarray) -> tuple[int, float | None, int]:
        cfg = self.config
        p = np.exp(logprobs)
        candidates = np.flatnonzero(p >= cfg.coherence_floor * p.max())
        n_candidates = len(candidates)
        if n_candidates > cfg.max_candidates:
            keep = np.argsort(p[candidates])[::-1][: cfg.max_candidates]
            candidates = candidates[keep]

        if self.embed_fn is not None and self._context is not None:
            vecs = np.asarray(self.embed_fn(candidates), dtype=np.float64)
            distances = cosine_distances(vecs, self._context)
        else:
            distances = np.zeros(len(candidates))

        scores = logprobs[candidates] + cfg.lam * distances
        if cfg.perturb_choice == "argmax":
            pick = int(np.argmax(scores))
        else:
            pick = self._gumbel_argmax(scores)
        chosen_distance = float(distances[pick]) if self.embed_fn is not None else None
        return int(candidates[pick]), chosen_distance, n_candidates

    def _gumbel_argmax(self, scores: np.ndarray) -> int:
        """Draw from softmax(scores) via the Gumbel-max trick."""
        return int(np.argmax(scores + self.rng.gumbel(size=scores.shape)))

    def _update_context(self, vec: np.ndarray) -> None:
        if self._context is None:
            self._context = vec.copy()
        else:
            self._context = self._decay * self._context + (1.0 - self._decay) * vec
