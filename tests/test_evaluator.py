import numpy as np

from creative_machine.evaluator import entropy_drop_score, record_entropies
from creative_machine.telemetry import StepRecord


def test_collapse_signature_scores_high():
    entropies = [2.2] * 20 + [1.1] * 20  # crystallizing 2nd half
    assert entropy_drop_score(entropies) == np.float64(0.5)


def test_healthy_settling_scores_low():
    entropies = [2.2] * 20 + [1.8] * 20
    assert entropy_drop_score(entropies) < 0.2


def test_rising_entropy_clamps_to_zero():
    assert entropy_drop_score([1.0] * 10 + [2.0] * 10) == 0.0


def test_too_short_returns_zero():
    assert entropy_drop_score([2.0, 1.0]) == 0.0


def test_record_entropies_accepts_dicts_and_records():
    rec = StepRecord(
        step=0, token_id=1, perturbed=False, entropy=1.5, logprob=-1.0,
        prob=0.37, rank=0, distance=None, distance_spread=None, n_candidates=2,
    )
    assert record_entropies([rec, {"entropy": 2.5}]) == [1.5, 2.5]
