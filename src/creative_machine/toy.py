"""Deterministic toy language model — the cloud workshop's test rig.

Ported (adapted) from the old session branch. Two properties make it a good
rig for the perturbator, with no weights and no GPU:

- Controllable entropy alternation: steps at even context lengths are peaked
  (low entropy), odd ones are flat (high entropy), so the entropy band has
  something real to react to over a full generation loop.
- Clustered embeddings: tokens live in a few well-separated clusters, so
  semantic distance is structured rather than uniform noise.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


class ToyLM:
    def __init__(
        self,
        vocab_size: int = 64,
        dim: int = 16,
        n_clusters: int = 4,
        seed: int = 0,
        beta_flat: float = 0.3,
        beta_peaked: float = 8.0,
    ) -> None:
        rng = np.random.default_rng(seed)
        centers = rng.normal(size=(n_clusters, dim)) * 3.0
        assignment = np.arange(vocab_size) % n_clusters
        self._embeddings = centers[assignment] + rng.normal(size=(vocab_size, dim)) * 0.5
        # Fixed random bigram preference matrix: row = last token, col = next.
        self._bigram = rng.normal(size=(vocab_size, vocab_size))
        self._beta_flat = beta_flat
        self._beta_peaked = beta_peaked
        self.vocab_size = vocab_size

    def next_logits(self, ids: Sequence[int]) -> np.ndarray:
        last = ids[-1] if len(ids) else 0
        beta = self._beta_peaked if len(ids) % 2 == 0 else self._beta_flat
        return self._bigram[last] * beta

    def embed(self, ids: np.ndarray) -> np.ndarray:
        """Embedding lookup with the core sampler's EmbedFn signature."""
        return self._embeddings[np.asarray(ids)]
