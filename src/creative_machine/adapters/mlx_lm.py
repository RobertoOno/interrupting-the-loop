"""mlx-lm adapter: plug the anti-probable sampler into ``generate``/``stream_generate``.

mlx is imported lazily so the package (and the synthetic test suite) works on
machines without Apple silicon. Semantic distance uses the model's own input
embedding table — free, and always in-vocabulary.

Usage:

    from mlx_lm import load, stream_generate
    from creative_machine import SamplerConfig
    from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler

    model, tokenizer = load("Qwen/Qwen3-8B-Base")  # a *base* model
    sampler = MLXAntiprobableSampler(model, config=SamplerConfig(lam=3.0))
    sampler.observe_prompt(tokenizer.encode(prompt))
    for out in stream_generate(model, tokenizer, prompt, sampler=sampler):
        print(out.text, end="")
    print(sampler.telemetry.summary())
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ..config import SamplerConfig
from ..sampler import AntiprobableSampler
from ..telemetry import Telemetry

# Attribute paths where mlx-lm architectures keep the input embedding module.
_EMBED_PATHS = ("model.embed_tokens", "embed_tokens", "transformer.wte", "model.model.embed_tokens")


def find_embed_module(model):
    """Locate the input-embedding module (works for quantized ones too)."""
    for path in _EMBED_PATHS:
        obj = model
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if obj is not None and callable(obj):
            return obj
    raise AttributeError(
        f"could not find an embedding module on {type(model).__name__}; "
        "pass the embedding module or matrix explicitly"
    )


def _to_numpy(x) -> np.ndarray:
    """mx.array -> float64 numpy (via float32: numpy has no bfloat16)."""
    if isinstance(x, np.ndarray):
        return x.astype(np.float64)
    import mlx.core as mx

    return np.array(x.astype(mx.float32), dtype=np.float64)


def _make_embed_fn(source):
    """Build the core's embed_fn from a model, embedding module, or matrix."""
    try:
        source = find_embed_module(source)
    except AttributeError:
        pass

    if hasattr(source, "ndim") and source.ndim == 2 and not callable(source):
        matrix = source
        if isinstance(matrix, np.ndarray):
            return lambda ids: matrix[np.asarray(ids)].astype(np.float64)

        def lookup(ids: np.ndarray) -> np.ndarray:
            import mlx.core as mx

            return _to_numpy(matrix[mx.array(np.asarray(ids))])

        return lookup

    if callable(source):
        # Embedding modules do a dequantizing lookup in __call__, so this
        # path is correct for both nn.Embedding and nn.QuantizedEmbedding.
        def embed(ids: np.ndarray) -> np.ndarray:
            import mlx.core as mx

            return _to_numpy(source(mx.array(np.asarray(ids))))

        return embed

    raise TypeError(f"cannot build an embed_fn from {type(source).__name__}")


class MLXAntiprobableSampler:
    """Callable sampler for mlx-lm's ``generate_step`` (batch size 1).

    Args:
        embed_source: The mlx-lm model (its embedding table is found
            automatically), an embedding module, or a (V, d) matrix. None
            disables semantic distance (min-p behavior at high entropy).
        config: Decoding policy parameters.
        telemetry: Optional shared Telemetry.
        rng: Optional numpy Generator.
    """

    def __init__(
        self,
        embed_source=None,
        config: SamplerConfig | None = None,
        telemetry: Telemetry | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        embed_fn = None if embed_source is None else _make_embed_fn(embed_source)
        self.core = AntiprobableSampler(config=config, embed_fn=embed_fn, rng=rng, telemetry=telemetry)

    @property
    def telemetry(self) -> Telemetry:
        return self.core.telemetry

    def observe_prompt(self, token_ids: Sequence[int]) -> None:
        """Fold the prompt into the context EMA before generating."""
        self.core.observe_many(np.asarray(token_ids, dtype=np.int64))

    def reset(self, prompt_ids: Sequence[int] | None = None) -> None:
        """Clear context between generations; optionally observe a new prompt."""
        self.core.reset()
        if prompt_ids is not None:
            self.observe_prompt(prompt_ids)

    def switch_regime(self, config: SamplerConfig) -> None:
        """Swap decoding policy mid-stream (context EMA preserved)."""
        self.core.switch_regime(config)

    def __call__(self, logprobs):
        import mlx.core as mx

        arr = _to_numpy(logprobs)
        if arr.ndim == 2:
            if arr.shape[0] != 1:
                raise ValueError("MLXAntiprobableSampler is stateful; batch size must be 1")
            return mx.array([self.core.step(arr[0])], dtype=mx.uint32)
        return mx.array(self.core.step(arr), dtype=mx.uint32)
