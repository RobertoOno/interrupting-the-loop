"""Semantic improbability of an input: its distance from real prompts.

The improbable-input pilot showed token perplexity ranks inputs backwards
(bare word pairs look "strange" to a LM but are ordinary requests; fluent
alien prose looks ordinary but is a request nobody makes). The quantity we
want is positional: how far the input sits from the distribution of prompts
people actually write.

Ruler: a contrastively-trained sentence embedder (sentence-transformers,
CPU/MPS). Mean-pooled hidden states of the causal base model were tried
first and rejected: anisotropy puts everything at cosine ~0.99 of
everything (same failure as raw token embeddings in Phase 1) — kept below
as `causal_sentence_embed` for the record.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_ST_MODEL = "sentence-transformers/all-mpnet-base-v2"


class SentenceEmbedder:
    """Thin wrapper over sentence-transformers; L2-normalized outputs."""

    def __init__(self, model_name: str = DEFAULT_ST_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def __call__(self, texts: list[str]) -> np.ndarray:
        emb = self.model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        return np.asarray(emb, dtype=np.float64)


def causal_sentence_embed(model, tokenizer, texts: list[str], batch_size: int = 16) -> np.ndarray:
    """(Rejected ruler) Mean-pooled last hidden state of a causal LM, via mlx."""
    import mlx.core as mx

    out = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        ids = [tokenizer.encode(t) for t in batch]
        max_len = max(len(x) for x in ids)
        arr = np.zeros((len(ids), max_len), dtype=np.int64)
        mask = np.zeros((len(ids), max_len), dtype=np.float32)
        for i, x in enumerate(ids):
            arr[i, : len(x)] = x
            mask[i, : len(x)] = 1.0
        # right padding + causal attention: padded positions never influence
        # real tokens; the mask excludes them from the pool.
        hidden = model.model(mx.array(arr))
        h = np.array(hidden.astype(mx.float32), dtype=np.float64)
        m = mask[..., None]
        pooled = (h * m).sum(axis=1) / m.sum(axis=1)
        pooled /= np.linalg.norm(pooled, axis=1, keepdims=True) + 1e-12
        out.append(pooled)
    return np.concatenate(out, axis=0)


class PromptSpace:
    """Reference corpus of real prompts embedded once; distances on demand."""

    def __init__(self, embeddings: np.ndarray) -> None:
        self.embeddings = np.asarray(embeddings, dtype=np.float64)
        centroid = self.embeddings.mean(axis=0)
        self.centroid = centroid / (np.linalg.norm(centroid) + 1e-12)

    @classmethod
    def build(cls, embed, prompts: list[str], cache: Path | None = None) -> "PromptSpace":
        """``embed`` maps list[str] -> (n, d) normalized array (e.g. SentenceEmbedder)."""
        if cache is not None and cache.exists():
            return cls(np.load(cache))
        emb = embed(prompts)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, emb)
        return cls(emb)

    def distances(self, query_embeddings: np.ndarray, k: int = 10) -> list[dict]:
        """Per query: cosine distance to the centroid and mean distance to the
        k nearest real prompts (the local-density notion of improbability)."""
        q = np.asarray(query_embeddings, dtype=np.float64)
        sims = q @ self.embeddings.T
        out = []
        for i in range(len(q)):
            top = np.sort(sims[i])[::-1][:k]
            out.append(
                {
                    "centroid_distance": float(1.0 - q[i] @ self.centroid),
                    "knn_distance": float(1.0 - top.mean()),
                }
            )
        return out
