import numpy as np

from creative_machine.code_exec import run_heuristic_code
from creative_machine.domains.binpack import generate_instances
from creative_machine.heuristic_gen import extract_function


def test_extracts_body_and_stops_at_dedent():
    completion = (
        "    scores = []\n"
        "    for r in remaining:\n"
        "        scores.append(-(r - item) * r)\n"
        "    return scores\n"
        "\n"
        "def priority_other(item, remaining):\n"
        "    return []\n"
    )
    fn = extract_function(completion)
    assert fn is not None
    assert fn.startswith("def priority(item: float")
    assert "priority_other" not in fn
    assert fn.rstrip().endswith("return scores")


def test_extracted_function_runs_in_verifier():
    completion = "    return [-(r - item) for r in remaining]\n"
    fn = extract_function(completion)
    out = run_heuristic_code(fn, generate_instances(2, 30, np.random.default_rng(0)))
    assert out["ok"]
    assert out["mean_excess"] >= 0.0


def test_boundary_space_loss_first_line_realigned():
    # First line 3 spaces (detokenizer boundary loss); rest correct at 4/8.
    completion = (
        "   scores = []\n"
        "    for r in remaining:\n"
        "        scores.append(r * item)\n"
        "    return scores\n"
    )
    fn = extract_function(completion)
    assert fn is not None
    compile(fn, "<candidate>", "exec")
    assert "\n    scores = []\n" in fn  # realigned to 4
    assert "\n        scores.append(r * item)\n" in fn  # inner level untouched


def test_single_short_line_gets_standard_indent():
    fn = extract_function("   return [r for r in remaining]\n")
    assert fn is not None
    compile(fn, "<candidate>", "exec")
    assert "\n    return [r for r in remaining]\n" in fn


def test_empty_or_immediate_dedent_returns_none():
    assert extract_function("") is None
    assert extract_function("\n\n") is None
    assert extract_function("def somethingelse():\n    pass\n") is None
