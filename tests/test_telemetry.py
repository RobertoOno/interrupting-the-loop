import json
import math

from creative_machine.telemetry import StepRecord, Telemetry


def _rec(step, perturbed, logprob=-1.0, rank=0, distance=None, n_candidates=None):
    return StepRecord(
        step=step,
        token_id=step,
        perturbed=perturbed,
        entropy=2.0,
        logprob=logprob,
        prob=math.exp(logprob),
        rank=rank,
        distance=distance,
        n_candidates=n_candidates,
    )


def test_empty_summary():
    assert Telemetry().summary() == {"n_steps": 0}


def test_summary_mixed():
    t = Telemetry()
    t.record(_rec(0, perturbed=False, logprob=-0.5, rank=0))
    t.record(_rec(1, perturbed=True, logprob=-2.5, rank=7, distance=0.8, n_candidates=12))
    s = t.summary()
    assert s["n_steps"] == 2
    assert s["perturb_rate"] == 0.5
    assert s["mean_rank"] == 3.5
    assert math.isclose(s["mean_logprob"], -1.5)
    assert math.isclose(s["perplexity"], math.exp(1.5))
    assert s["mean_rank_perturbed"] == 7
    assert math.isclose(s["mean_distance_perturbed"], 0.8)


def test_summary_perturbed_without_distance():
    t = Telemetry()
    t.record(_rec(0, perturbed=True, rank=3, distance=None, n_candidates=5))
    s = t.summary()
    assert s["mean_rank_perturbed"] == 3
    assert "mean_distance_perturbed" not in s


def test_jsonl_roundtrip(tmp_path):
    t = Telemetry()
    t.record(_rec(0, perturbed=False))
    t.record(_rec(1, perturbed=True, distance=0.5, n_candidates=3))
    lines = t.dumps_jsonl().splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["distance"] is None
    assert second["n_candidates"] == 3

    path = tmp_path / "run.jsonl"
    t.to_jsonl(path)
    assert path.read_text().strip() == t.dumps_jsonl()


def test_reset():
    t = Telemetry()
    t.record(_rec(0, perturbed=False))
    t.reset()
    assert t.records == []
    assert t.summary() == {"n_steps": 0}
