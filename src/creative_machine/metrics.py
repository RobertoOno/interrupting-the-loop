"""Pure numpy metrics over next-token distributions and embeddings."""

from __future__ import annotations

import numpy as np


def log_softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Numerically stable log-softmax. Accepts -inf entries (masked tokens).

    Idempotent on already-normalized logprobs when temperature == 1.
    """
    x = np.asarray(logits, dtype=np.float64) / temperature
    m = np.max(x)
    if not np.isfinite(m):
        raise ValueError("all logits are -inf or non-finite")
    z = x - m
    return z - np.log(np.sum(np.exp(z)))


def entropy(logprobs: np.ndarray) -> float:
    """Shannon entropy in nats of a log-probability vector."""
    logprobs = np.asarray(logprobs, dtype=np.float64)
    p = np.exp(logprobs)
    mask = p > 0
    return float(-np.sum(p[mask] * logprobs[mask]))


def token_rank(logprobs: np.ndarray, token_id: int) -> int:
    """0-based rank of a token in the distribution (0 = most probable)."""
    logprobs = np.asarray(logprobs)
    return int(np.sum(logprobs > logprobs[token_id]))


def cosine_distances(vectors: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Cosine distance (1 - cos) of each row of ``vectors`` to ``reference``.

    Zero-norm rows or a zero-norm reference yield distance 0 — no information,
    no novelty bonus.
    """
    vectors = np.asarray(vectors, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    out = np.zeros(vectors.shape[0])
    ref_norm = np.linalg.norm(reference)
    if ref_norm == 0:
        return out
    norms = np.linalg.norm(vectors, axis=1)
    valid = norms > 0
    out[valid] = 1.0 - (vectors[valid] @ reference) / (norms[valid] * ref_norm)
    return out
