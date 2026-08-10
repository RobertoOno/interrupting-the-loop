"""Phase 2 perturbator: sample concept pairs from the fertile distance band.

We are the perturbator here — the deliberate accident is choosing which two
concepts must marry. Distance is measured with an injected embedding function
(the house ruler: the local model's input embeddings, averaged over the
concept's tokens). Pairs are sampled from a percentile band of the pairwise
distance distribution: far enough to surprise, not so far that nothing can
weave them (the entropy band's philosophy, one level up).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import numpy as np


def load_concepts(path: str | Path) -> list[str]:
    lines = [ln.strip() for ln in Path(path).read_text().splitlines()]
    seen: dict[str, None] = {}
    for ln in lines:
        if ln and not ln.startswith("#"):
            seen.setdefault(ln)
    return list(seen)


def pairwise_cosine_distances(embeddings: np.ndarray) -> np.ndarray:
    """Full (n, n) cosine-distance matrix; zero-norm rows treated as distance 0."""
    x = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    safe = np.where(norms > 0, norms, 1.0)
    unit = x / safe
    d = 1.0 - unit @ unit.T
    zero = (norms[:, 0] == 0)
    d[zero, :] = 0.0
    d[:, zero] = 0.0
    np.fill_diagonal(d, 0.0)
    return d


def sample_distant_pairs(
    embeddings: np.ndarray,
    n_pairs: int,
    band: tuple[float, float] = (0.75, 0.95),
    rng: np.random.Generator | None = None,
) -> list[tuple[int, int, float]]:
    """Sample distinct index pairs whose distance lies in the percentile band.

    Returns (i, j, distance) triples, i < j, no pair repeated. Raises if the
    band holds fewer candidates than requested.
    """
    rng = rng or np.random.default_rng(0)
    d = pairwise_cosine_distances(embeddings)
    iu, ju = np.triu_indices(len(d), k=1)
    dists = d[iu, ju]
    lo, hi = np.percentile(dists, [100 * band[0], 100 * band[1]])
    in_band = np.flatnonzero((dists >= lo) & (dists <= hi))
    if len(in_band) < n_pairs:
        raise ValueError(f"band holds {len(in_band)} pairs, need {n_pairs}")
    picks = rng.choice(in_band, size=n_pairs, replace=False)
    return [(int(iu[k]), int(ju[k]), float(dists[k])) for k in picks]


def make_word_embedder(
    embed_fn: Callable[[np.ndarray], np.ndarray],
    encode: Callable[[str], Sequence[int]],
) -> Callable[[list[str]], np.ndarray]:
    """Word -> mean of its token embeddings, using the Phase 1 house ruler."""

    def embed_words(words: list[str]) -> np.ndarray:
        vecs = []
        for w in words:
            ids = np.asarray(encode(w))
            vecs.append(np.asarray(embed_fn(ids), dtype=np.float64).mean(axis=0))
        return np.stack(vecs)

    return embed_words
