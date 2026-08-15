"""Salience monitor on synthetic streams: each detector fires on the pattern
it was built for and stays quiet otherwise; refractory spacing holds."""

import numpy as np

from creative_machine.salience import SalienceConfig, SalienceMonitor, genre_collapse_score


def test_genre_collapse_score_separates_prose_from_boilerplate():
    prose = ("She kept a notebook of things that had almost happened, the storm that "
             "nearly took the poplar, the neighbor who almost sold the house, and every "
             "evening she read it back to herself as if it were the news of another town "
             "where luck ran differently and nobody was ever quite surprised by anything.")
    boiler = ("Terms of Service | Privacy Policy | Report DMCA Infringement | Become Affiliate "
              "Partner | © 2017-present Inventive Fields LLC ™ | Popular Books | Short Stories "
              "Mystery Romance Horror Poetry Fantasy Thriller | Add Picture | Tags & Keywords")
    assert genre_collapse_score(prose) < 0.3
    assert genre_collapse_score(boiler) > 0.45
    assert genre_collapse_score("too short") == 0.0


def _unit(theta: float) -> np.ndarray:
    return np.array([np.cos(theta), np.sin(theta)])


def run(monitor: SalienceMonitor, contexts, entropies):
    return [monitor.observe(c, h) for c, h in zip(contexts, entropies)]


def test_quiet_stream_fires_nothing():
    m = SalienceMonitor(SalienceConfig())
    ctx = [_unit(0.0) + 0.001 * np.random.default_rng(0).normal(size=2) for _ in range(300)]
    run(m, ctx, [1.0] * 300)
    assert m.events == []


def test_jump_fires_when_context_changes_region():
    m = SalienceMonitor(SalienceConfig(jump_lag=16, jump_threshold=0.5, snapshot_every=4))
    ctx = [_unit(0.0)] * 60 + [_unit(np.pi / 2)] * 60  # 90 degrees = cosine distance 1.0
    run(m, ctx, [1.0] * 120)
    kinds = [e.kind for e in m.events]
    assert "jump" in kinds
    first = next(e for e in m.events if e.kind == "jump")
    assert 60 <= first.step < 60 + 16 + 4  # fires within lag+snapshot granularity


def test_crystallize_fires_on_entropy_drop_after_wandering():
    cfg = SalienceConfig(entropy_window=10, entropy_drop=0.4, entropy_high=2.0, jump_threshold=9.0)
    m = SalienceMonitor(cfg)
    ctx = [_unit(0.0)] * 40
    ent = [3.0] * 20 + [1.0] * 20  # wandering then settled
    run(m, ctx, ent)
    assert any(e.kind == "crystallize" for e in m.events)


def test_crystallize_needs_prior_wandering():
    cfg = SalienceConfig(entropy_window=10, entropy_drop=0.4, entropy_high=2.0, jump_threshold=9.0)
    m = SalienceMonitor(cfg)
    ent = [1.5] * 20 + [0.5] * 20  # big relative drop, but never wandering
    run(m, [_unit(0.0)] * 40, ent)
    assert not any(e.kind == "crystallize" for e in m.events)


def test_recurrence_fires_on_return_to_old_region():
    cfg = SalienceConfig(
        jump_threshold=9.0, recurrence_min_age=40, recurrence_recent=16,
        recurrence_threshold=0.05, snapshot_every=4, refractory=1,
    )
    m = SalienceMonitor(cfg)
    ctx = [_unit(0.0)] * 30 + [_unit(2.0)] * 40 + [_unit(0.0)] * 20  # A, then B, then back to A
    run(m, ctx, [1.0] * 90)
    rec = [e for e in m.events if e.kind == "recurrence"]
    assert rec, "expected a recurrence when returning to region A"
    assert rec[0].step >= 70
    assert rec[0].ref_step is not None and rec[0].ref_step < 30


def test_stagnation_fires_when_context_never_moves():
    cfg = SalienceConfig(stagnation_window=50, stagnation_threshold=0.05, jump_threshold=9.0,
                         entropy_high=99.0, refractory=1)
    m = SalienceMonitor(cfg)
    run(m, [_unit(0.0)] * 120, [2.0] * 120)  # same region for 120 steps
    assert any(e.kind == "stagnation" for e in m.events)


def test_no_stagnation_while_moving():
    cfg = SalienceConfig(stagnation_window=50, stagnation_threshold=0.05, jump_threshold=9.0,
                         entropy_high=99.0, refractory=1, recurrence_threshold=-1.0)
    m = SalienceMonitor(cfg)
    ctx = [_unit(0.01 * i) for i in range(160)]  # slow continuous drift, never stuck
    run(m, ctx, [2.0] * 160)
    assert not any(e.kind == "stagnation" for e in m.events)


def test_refractory_spacing():
    m = SalienceMonitor(SalienceConfig(jump_lag=8, jump_threshold=0.5, snapshot_every=2, refractory=30))
    # alternate regions every 12 steps: many jumps, but events must be >= 30 apart
    ctx = []
    for block in range(12):
        ctx += [_unit(0.0 if block % 2 == 0 else np.pi / 2)] * 12
    run(m, ctx, [1.0] * len(ctx))
    steps = [e.step for e in m.events]
    assert len(steps) >= 2
    assert all(b - a >= 30 for a, b in zip(steps, steps[1:]))
