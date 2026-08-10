"""The evaluator organ, minimal version: filter before you rank.

Two cheap signals feed the selection funnel:

- Genre-collapse score from telemetry: register collapses (math-exercise,
  factual-recitation modes) crystallize the distribution — mean entropy in
  the 2nd half drops far below the 1st half's. Healthy narratives settle
  gently (~20% drop); collapses crater (~45%+). A continuous score, not an
  oracle: rank by it, read the top.
- Coherence under a second model (the judge): perplexity of the continuation
  given the prompt, scored by a different model family. Resolves the
  same-judge paradox: the generator cannot grade its own coherence.
"""

from __future__ import annotations

import numpy as np


def entropy_drop_score(entropies) -> float:
    """1 - (2nd-half mean entropy / 1st-half mean entropy), clamped to [0, 1].

    ~0.2 is a narrative settling; >0.35 smells like a register collapse.
    Returns 0.0 when there are fewer than 4 steps or the 1st half is ~zero.
    """
    xs = np.asarray(list(entropies), dtype=np.float64)
    if len(xs) < 4:
        return 0.0
    mid = len(xs) // 2
    first = xs[:mid].mean()
    if first < 1e-9:
        return 0.0
    return float(np.clip(1.0 - xs[mid:].mean() / first, 0.0, 1.0))


def record_entropies(records) -> list[float]:
    """Entropy series from telemetry records (StepRecord or JSONL dicts)."""
    return [r["entropy"] if isinstance(r, dict) else r.entropy for r in records]


def judge_perplexity(model, tokenizer, full_text: str, prompt: str) -> dict:
    """Perplexity of the continuation given the prompt, under the judge model.

    One forward pass; only tokens after the prompt are scored. The prompt
    boundary is found by tokenizing the prompt alone — a merge at the
    boundary can shift it by one token, negligible over ~150 scored tokens.
    """
    import mlx.core as mx

    full_ids = tokenizer.encode(full_text)
    prompt_len = len(tokenizer.encode(prompt))
    if len(full_ids) - prompt_len < 2:
        return {"judge_ppl": float("nan"), "n_scored": 0}

    inputs = mx.array([full_ids[:-1]])
    logits = model(inputs).astype(mx.float32)
    logprobs = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    targets = mx.array([full_ids[1:]])
    token_lp = mx.take_along_axis(logprobs, targets[..., None], axis=-1)[0, :, 0]
    scored = np.array(token_lp[prompt_len - 1 :])
    mean_lp = float(scored.mean())
    return {"judge_ppl": float(np.exp(-mean_lp)), "n_scored": len(scored)}
