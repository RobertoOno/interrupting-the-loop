"""Adapter tests. The mx-dependent ones run only where mlx is installed (Mac)."""

import numpy as np
import pytest

from creative_machine import SamplerConfig
from creative_machine.adapters.mlx_lm import (
    MLXAntiprobableSampler,
    _make_embed_fn,
    find_embed_module,
)

try:
    import mlx.core as mx

    HAS_MLX = True
except ImportError:
    HAS_MLX = False

requires_mlx = pytest.mark.skipif(not HAS_MLX, reason="mlx not installed")


class FakeEmbed:
    def __init__(self, table):
        self.table = table

    def __call__(self, ids):
        return self.table[ids]


def test_find_embed_module_common_paths():
    embed = FakeEmbed(np.eye(4))

    class Inner:
        embed_tokens = embed

    class Model:
        model = Inner()

    assert find_embed_module(Model()) is embed

    class Flat:
        embed_tokens = embed

    assert find_embed_module(Flat()) is embed


def test_find_embed_module_missing_raises():
    with pytest.raises(AttributeError):
        find_embed_module(object())


def test_numpy_matrix_embed_fn():
    fn = _make_embed_fn(np.arange(8.0).reshape(4, 2))
    out = fn(np.array([1, 3]))
    assert out.dtype == np.float64
    assert np.allclose(out, [[2.0, 3.0], [6.0, 7.0]])


def test_sampler_with_numpy_source_no_mlx_needed_until_call():
    # Construction and prompt observation are pure numpy.
    s = MLXAntiprobableSampler(np.eye(8), config=SamplerConfig(seed=0))
    s.observe_prompt([1, 2, 3])
    assert s.core.context is not None


@requires_mlx
def test_call_with_batched_logprobs():
    rng = np.random.default_rng(0)
    table = mx.array(rng.normal(size=(32, 8)).astype(np.float32))
    s = MLXAntiprobableSampler(table, config=SamplerConfig(entropy_trigger=1.0, seed=0))
    s.observe_prompt([0, 1, 2])
    logprobs = mx.zeros((1, 32))
    out = s(logprobs)
    assert out.shape == (1,)
    assert out.dtype == mx.uint32
    assert 0 <= int(out[0]) < 32
    assert len(s.telemetry.records) == 1


@requires_mlx
def test_call_with_flat_logprobs():
    s = MLXAntiprobableSampler(mx.eye(16), config=SamplerConfig(seed=0))
    out = s(mx.zeros(16))
    assert out.ndim == 0
    assert 0 <= int(out) < 16


@requires_mlx
def test_batch_greater_than_one_rejected():
    s = MLXAntiprobableSampler(mx.eye(8), config=SamplerConfig(seed=0))
    with pytest.raises(ValueError):
        s(mx.zeros((2, 8)))


@requires_mlx
def test_quantized_style_module_source():
    # Any callable module works as the embedding source (QuantizedEmbedding
    # dequantizes inside __call__, mirrored here by a plain lookup).
    table = mx.array(np.eye(8, dtype=np.float32))
    s = MLXAntiprobableSampler(lambda ids: table[ids], config=SamplerConfig(seed=0))
    s.observe_prompt([1])
    assert np.allclose(s.core.context, np.eye(8)[1])
