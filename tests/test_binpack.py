import numpy as np
import pytest

from creative_machine.code_exec import run_heuristic_code
from creative_machine.domains.binpack import (
    best_fit,
    evaluate,
    first_fit,
    generate_instances,
    lower_bound,
    simulate,
    worst_fit,
)


def test_lower_bound():
    assert lower_bound([0.5, 0.5, 0.5]) == 2
    assert lower_bound([0.1]) == 1


def test_simulate_reaches_lower_bound_on_crafted_instance():
    items = [0.3, 0.6, 0.4, 0.6]  # packs perfectly into 2 bins
    assert simulate(best_fit, items) == 2 == lower_bound(items)
    assert simulate(first_fit, items) == 2


def test_constant_priority_is_first_fit():
    rng = np.random.default_rng(0)
    for items in generate_instances(5, 60, rng):
        assert simulate(lambda i, r: [7.0] * len(r), items) == simulate(first_fit, items)


def test_evaluate_orders_classic_baselines():
    rng = np.random.default_rng(1)
    instances = generate_instances(20, 120, rng)
    bf = evaluate(best_fit, instances)["mean_excess"]
    ff = evaluate(first_fit, instances)["mean_excess"]
    wf = evaluate(worst_fit, instances)["mean_excess"]
    assert 0.0 <= bf <= ff <= wf


def test_bad_priority_outputs_rejected():
    items = [0.6, 0.6, 0.3]  # third item fits in BOTH open bins
    with pytest.raises(ValueError):
        simulate(lambda i, r: [1.0], items)  # wrong length
    with pytest.raises(ValueError):
        simulate(lambda i, r: [float("nan")] * len(r), items)


BEST_FIT_CODE = """
def priority(item, remaining):
    return [-(r - item) for r in remaining]
"""


def test_run_heuristic_code_matches_native():
    rng = np.random.default_rng(2)
    instances = generate_instances(4, 50, rng)
    out = run_heuristic_code(BEST_FIT_CODE, instances)
    assert out["ok"]
    assert out["mean_excess"] == pytest.approx(evaluate(best_fit, instances)["mean_excess"])


def test_run_heuristic_code_failure_modes():
    instances = [[0.5, 0.5]]
    assert not run_heuristic_code("x = 1", instances)["ok"]  # no priority()
    out = run_heuristic_code("def priority(item, remaining):\n    return undefined_name", instances)
    assert not out["ok"] and "NameError" in out["error"]
    out = run_heuristic_code(
        "def priority(item, remaining):\n"
        "    while True:\n        pass",
        instances,
        timeout_s=2.0,
    )
    assert not out["ok"] and "timeout" in out["error"]
