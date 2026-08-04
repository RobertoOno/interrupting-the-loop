import numpy as np
import pytest

from creative_machine.metrics import cosine_distances, entropy, log_softmax, token_rank


def test_log_softmax_normalizes():
    rng = np.random.default_rng(0)
    lp = log_softmax(rng.normal(size=10))
    assert np.isclose(np.sum(np.exp(lp)), 1.0)


def test_log_softmax_idempotent_on_logprobs():
    lp = log_softmax(np.array([3.0, 1.0, -2.0]))
    assert np.allclose(log_softmax(lp), lp)


def test_log_softmax_temperature():
    logits = np.array([2.0, 0.0, -1.0])
    assert np.allclose(log_softmax(logits, temperature=2.0), log_softmax(logits / 2.0))


def test_log_softmax_keeps_masked_tokens_masked():
    lp = log_softmax(np.array([1.0, -np.inf, 0.0]))
    assert lp[1] == -np.inf
    assert np.isclose(np.sum(np.exp(lp)), 1.0)


def test_log_softmax_all_masked_raises():
    with pytest.raises(ValueError):
        log_softmax(np.array([-np.inf, -np.inf]))


def test_entropy_uniform_is_log_v():
    v = 32
    lp = log_softmax(np.zeros(v))
    assert np.isclose(entropy(lp), np.log(v))


def test_entropy_peaked_is_near_zero():
    lp = log_softmax(np.array([100.0, 0.0, 0.0]))
    assert entropy(lp) < 1e-8


def test_entropy_with_mask_counts_valid_only():
    lp = log_softmax(np.array([0.0, 0.0, -np.inf, -np.inf]))
    assert np.isclose(entropy(lp), np.log(2))


def test_token_rank():
    lp = np.array([3.0, 1.0, 2.0])
    assert token_rank(lp, 0) == 0
    assert token_rank(lp, 2) == 1
    assert token_rank(lp, 1) == 2


def test_token_rank_ties_share_best_rank():
    lp = np.array([5.0, 5.0, 1.0])
    assert token_rank(lp, 0) == 0
    assert token_rank(lp, 1) == 0
    assert token_rank(lp, 2) == 2


def test_cosine_distances():
    ref = np.array([1.0, 0.0])
    vecs = np.array([[2.0, 0.0], [0.0, 3.0], [-1.0, 0.0], [0.0, 0.0]])
    d = cosine_distances(vecs, ref)
    assert np.allclose(d, [0.0, 1.0, 2.0, 0.0])


def test_cosine_distances_zero_reference():
    d = cosine_distances(np.array([[1.0, 0.0]]), np.array([0.0, 0.0]))
    assert np.allclose(d, [0.0])
