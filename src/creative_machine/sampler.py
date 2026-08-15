"""Entropy-adaptive anti-probable sampler — the perturbator organ.

Coherence lives disproportionately in the low-entropy steps (syntax, names,
arithmetic), so those are left untouched. The fertile points are high-entropy
branchings, where the model itself admits many continuations; only there does
the sampler reach into the tail, pulled by semantic distance and held by the
coherence floor:

    score(token) = log P(token | context) + lam * push(token)

where push is the candidate's semantic distance to the context, by default
standardized across the step's candidates (see SamplerConfig.distance_scale).
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
        self._recent: list[int] = []  # recent token ids for the repetition penalty
        self._anchors: np.ndarray | None = None  # (k, d) old regions for the bridge term

    def set_anchors(self, anchors: np.ndarray | None) -> None:
        """Old-region vectors (k, d) the bridge term may pull toward. None clears."""
        self._anchors = None if anchors is None or len(anchors) == 0 else np.asarray(anchors, dtype=np.float64)

    def reset(self) -> None:
        """Clear context and step counter (telemetry is left to its owner)."""
        self._context = None
        self._step = 0
        self._recent = []

    def switch_regime(self, config: SamplerConfig) -> None:
        """Swap the decoding policy mid-stream, keeping the context EMA.

        The reverie loop alternates a drift regime (wide band, high lam) and
        an escalate regime (narrow band, low lam) by internal signal; the
        thought's memory must survive the switch, so only the policy and
        its derived decay change.
        """
        self.config = config
        self._decay = 0.5 ** (1.0 / config.context_halflife)

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
        """Choose the next token for one step's logits (or logprobs).

        The coherence floor applies at every step — it is the permanent
        guard. Only the distance push is entropy-gated: an unguarded
        categorical draw can fall 500 ranks deep by accident, a dumb
        accident rather than a fertile error.
        """
        cfg = self.config
        logprobs = log_softmax(logits, cfg.temperature)
        # Habituation: suppress what was just said. A closed loop feeding on
        # its own output otherwise locks into short literal orbits where the
        # distribution is peaked and the entropy band never opens.
        if cfg.repetition_window > 0 and self._recent:
            # graded by recent frequency: the more often said, the more suppressed
            ids, counts = np.unique(np.asarray(self._recent[-cfg.repetition_window :]), return_counts=True)
            logprobs = logprobs.copy()
            logprobs[ids] -= counts * np.log(cfg.repetition_penalty)
            logprobs = log_softmax(logprobs)
        h = entropy(logprobs)

        p = np.exp(logprobs)
        candidates = np.flatnonzero(p >= cfg.coherence_floor * p.max())
        n_candidates = len(candidates)

        perturbed = h >= cfg.entropy_trigger and (
            cfg.entropy_ceiling is None or h < cfg.entropy_ceiling
        )
        if perturbed:
            token, distance, spread = self._perturb(logprobs, candidates)
        else:
            token = int(candidates[self._gumbel_argmax(logprobs[candidates])])
            distance, spread = None, None

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
                distance_spread=spread,
                n_candidates=n_candidates,
            )
        )
        self._step += 1
        self._recent.append(token)
        if len(self._recent) > 4096:
            self._recent = self._recent[-2048:]
        self.observe(token)
        return token

    def _perturb(
        self, logprobs: np.ndarray, candidates: np.ndarray
    ) -> tuple[int, float | None, float | None]:
        cfg = self.config
        if len(candidates) > cfg.max_candidates:
            p = np.exp(logprobs[candidates])
            keep = np.argsort(p)[::-1][: cfg.max_candidates]
            candidates = candidates[keep]

        if self.embed_fn is not None and self._context is not None:
            vecs = np.asarray(self.embed_fn(candidates), dtype=np.float64)
            distances = cosine_distances(vecs, self._context)
        else:
            distances = np.zeros(len(candidates))

        # Telemetry reports real distances; the push is computed over the
        # non-exempt candidates only (exempt ones stay neutral at 0).
        exempt = (
            np.isin(candidates, cfg.no_push_ids)
            if cfg.no_push_ids
            else np.zeros(len(candidates), dtype=bool)
        )
        active = ~exempt
        push = np.zeros(len(candidates))
        spread = float(np.std(distances[active])) if active.any() else 0.0
        if cfg.distance_scale == "standardize":
            if spread > 1e-9:
                push[active] = (distances[active] - np.mean(distances[active])) / spread
        else:
            push[active] = distances[active]

        scores = logprobs[candidates] + cfg.lam * push
        if cfg.bridge > 0 and self._anchors is not None and self._context is not None and self.embed_fn is not None:
            scores = scores + cfg.bridge * self._bridge_push(vecs, active)
        if cfg.perturb_choice == "argmax":
            pick = int(np.argmax(scores))
        else:
            pick = self._gumbel_argmax(scores)
        if self.embed_fn is not None:
            return int(candidates[pick]), float(distances[pick]), spread
        return int(candidates[pick]), None, None

    def _bridge_push(self, vecs: np.ndarray, active: np.ndarray) -> np.ndarray:
        """Standardized bridge bonus per candidate.

        For each anchor a: weight w_a = distance(a, recent context) — only
        far banks count. Candidate c's raw bridge = max_a w_a * (1 - dist(c, a))
        (how much c moves toward the farthest-from-here old region). Z-scored
        across active candidates like the distance push, so `bridge` reads in
        the same units as `lam` (nats per sigma).
        """
        anchors = self._anchors
        w = cosine_distances(anchors, self._context)          # (k,) far banks weigh more
        if not np.any(w > 1e-9):
            return np.zeros(len(vecs))
        norms_c = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        norms_a = np.linalg.norm(anchors, axis=1, keepdims=True) + 1e-12
        sims = (vecs / norms_c) @ (anchors / norms_a).T           # (n, k) cosine similarity
        raw = np.max(sims * w[None, :], axis=1)                    # toward the far bank
        out = np.zeros(len(vecs))
        if active.any():
            spread = float(np.std(raw[active]))
            if spread > 1e-9:
                out[active] = (raw[active] - np.mean(raw[active])) / spread
        return out

    def _gumbel_argmax(self, scores: np.ndarray) -> int:
        """Draw from softmax(scores) via the Gumbel-max trick."""
        return int(np.argmax(scores + self.rng.gumbel(size=scores.shape)))

    def _update_context(self, vec: np.ndarray) -> None:
        if self._context is None:
            self._context = vec.copy()
        else:
            self._context = self._decay * self._context + (1.0 - self._decay) * vec
