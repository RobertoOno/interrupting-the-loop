"""Synthetic-distribution tests for the anti-probable sampler.

Small hand-built vocabularies and 2-D embeddings make every behavior
assertable without model weights.
"""

import numpy as np
import pytest

from creative_machine import AntiprobableSampler, SamplerConfig


def make_embed(table: np.ndarray):
    return lambda ids: table[np.asarray(ids)]

# Vocabulary of 6: tokens 0-4 share one direction, token 5 is orthogonal.
CLUSTER_TABLE = np.array([[1.0, 0.0]] * 5 + [[0.0, 1.0]])


def test_low_entropy_never_perturbs():
    logits = np.full(16, -10.0)
    logits[0] = 10.0  # peaked: entropy ~ 0
    s = AntiprobableSampler(SamplerConfig(entropy_trigger=2.0, seed=0))
    for _ in range(50):
        assert s.step(logits) == 0
    assert all(not r.perturbed for r in s.telemetry.records)


def test_high_entropy_argmax_picks_distant_token():
    logits = np.zeros(6)  # uniform: entropy = log 6 ~ 1.79
    cfg = SamplerConfig(entropy_trigger=1.5, lam=3.0, perturb_choice="argmax", seed=0)
    s = AntiprobableSampler(cfg, embed_fn=make_embed(CLUSTER_TABLE))
    s.observe(0)  # context sits in the cluster direction
    token = s.step(logits)
    rec = s.telemetry.records[0]
    assert token == 5
    assert rec.perturbed
    assert rec.n_candidates == 6
    assert np.isclose(rec.distance, 1.0)


def test_sample_mode_prefers_distant_token():
    # Independent fresh-context trials: sampling follows softmax(score),
    # which puts ~99.8% of the mass on the distant token here.
    logits = np.zeros(6)
    picks = []
    for seed in range(100):
        cfg = SamplerConfig(entropy_trigger=1.5, lam=8.0, perturb_choice="sample", seed=seed)
        s = AntiprobableSampler(cfg, embed_fn=make_embed(CLUSTER_TABLE))
        s.observe(0)
        picks.append(s.step(logits))
    assert picks.count(5) >= 90


def test_context_follows_deviation_and_oscillates():
    # The sampler observes its own deviations, so the context EMA drifts
    # toward whatever it picks: yesterday's deviation becomes today's normal,
    # and the old cluster becomes the distant pole — a built-in anti-attractor.
    logits = np.zeros(6)
    cfg = SamplerConfig(
        entropy_trigger=1.5, lam=3.0, perturb_choice="argmax", context_halflife=1.0
    )
    s = AntiprobableSampler(cfg, embed_fn=make_embed(CLUSTER_TABLE))
    s.observe(0)
    picks = [s.step(logits) for _ in range(6)]
    assert picks[0] == 5  # first pick: the orthogonal token
    assert 0 in picks[1:]  # then the old cluster becomes "distant" again
    assert picks == [5, 0, 5, 0, 5, 0]


def test_coherence_floor_blocks_improbable_distant_token():
    # tokens 0-2 equiprobable; token 3 distant but far below the floor
    logits = np.array([5.0, 5.0, 5.0, -5.0])
    table = np.array([[1.0, 0.0]] * 3 + [[0.0, 1.0]])
    cfg = SamplerConfig(entropy_trigger=1.0, lam=100.0, perturb_choice="argmax", seed=0)
    s = AntiprobableSampler(cfg, embed_fn=make_embed(table))
    s.observe(0)
    for _ in range(20):
        assert s.step(logits) != 3
    assert all(r.perturbed and r.n_candidates == 3 for r in s.telemetry.records)


def test_lambda_zero_argmax_reduces_to_top_candidate():
    logits = np.array([1.0, 0.9, 0.5, 0.0])  # entropy ~ 1.31
    cfg = SamplerConfig(entropy_trigger=1.2, lam=0.0, perturb_choice="argmax", seed=0)
    s = AntiprobableSampler(cfg, embed_fn=make_embed(np.eye(4)))
    s.observe(1)
    assert s.step(logits) == 0


def test_max_candidates_caps_scored_set():
    logits = np.linspace(1.0, 0.0, 50)  # all pass the floor (ratio 0.37)
    table = np.tile([1.0, 0.0], (50, 1))
    table[49] = [0.0, 1.0]  # distant, but outside the top-10 by probability
    cfg = SamplerConfig(
        entropy_trigger=3.0, lam=1000.0, perturb_choice="argmax", max_candidates=10, seed=0
    )
    s = AntiprobableSampler(cfg, embed_fn=make_embed(table))
    s.observe(0)
    token = s.step(logits)
    rec = s.telemetry.records[0]
    assert rec.perturbed
    assert rec.n_candidates == 50  # floor survivors, before the cap
    assert token < 10  # the distant token never entered scoring


def test_masked_tokens_never_chosen():
    logits = np.array([0.0] * 4 + [-np.inf] * 4)  # entropy = log 4
    for trigger in (1.2, 10.0):  # perturbation mode and plain mode
        s = AntiprobableSampler(
            SamplerConfig(entropy_trigger=trigger, seed=3),
            embed_fn=make_embed(np.eye(8)),
        )
        assert all(s.step(logits) < 4 for _ in range(30))


def test_first_step_without_context_uses_zero_distance():
    logits = np.array([1.0, 0.5, 0.0])  # entropy ~ 1.0
    cfg = SamplerConfig(entropy_trigger=0.9, lam=50.0, perturb_choice="argmax", seed=0)
    s = AntiprobableSampler(cfg, embed_fn=make_embed(np.eye(3)))
    token = s.step(logits)  # no context yet: distances all 0 -> top candidate
    assert token == 0
    assert s.telemetry.records[0].distance == 0.0


def test_no_embed_fn_degenerates_to_min_p():
    logits = np.zeros(8)
    s = AntiprobableSampler(SamplerConfig(entropy_trigger=1.0, seed=0))
    token = s.step(logits)
    rec = s.telemetry.records[0]
    assert 0 <= token < 8
    assert rec.perturbed
    assert rec.distance is None


def test_temperature_moves_entropy_across_trigger():
    logits = np.array([2.0, 1.0, 0.0, -1.0])
    cold = AntiprobableSampler(SamplerConfig(temperature=1.0, entropy_trigger=1.2, seed=0))
    hot = AntiprobableSampler(SamplerConfig(temperature=3.0, entropy_trigger=1.2, seed=0))
    cold.step(logits)
    hot.step(logits)
    assert not cold.telemetry.records[0].perturbed
    assert hot.telemetry.records[0].perturbed


def test_context_ema_halflife():
    table = np.array([[1.0, 0.0], [0.0, 1.0]])
    cfg = SamplerConfig(context_halflife=1.0)  # decay = 0.5
    s = AntiprobableSampler(cfg, embed_fn=make_embed(table))
    s.observe_many([0, 1])
    assert np.allclose(s.context, [0.5, 0.5])


def test_reset_clears_state():
    s = AntiprobableSampler(SamplerConfig(), embed_fn=make_embed(np.eye(4)))
    s.observe(2)
    s.step(np.array([5.0, 0.0, 0.0, 0.0]))
    s.reset()
    assert s.context is None
    next_step = s.step(np.array([5.0, 0.0, 0.0, 0.0]))
    assert s.telemetry.records[-1].step == 0
    assert next_step == 0


def test_same_seed_same_trajectory():
    rng = np.random.default_rng(42)
    logit_seq = rng.normal(scale=3.0, size=(50, 32))
    table = rng.normal(size=(32, 8))

    def run(seed):
        s = AntiprobableSampler(
            SamplerConfig(entropy_trigger=1.5, lam=3.0, seed=seed),
            embed_fn=make_embed(table),
        )
        return [s.step(logits) for logits in logit_seq]

    assert run(7) == run(7)
    assert run(7) != run(8)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": 0.0},
        {"coherence_floor": 0.0},
        {"coherence_floor": 1.5},
        {"lam": -1.0},
        {"entropy_trigger": -0.1},
        {"context_halflife": 0.0},
        {"perturb_choice": "greedy"},
        {"max_candidates": 0},
    ],
)
def test_config_validation(kwargs):
    with pytest.raises(ValueError):
        SamplerConfig(**kwargs)
