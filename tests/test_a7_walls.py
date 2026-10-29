"""A7 wall candidates: certificates, determinism, falsification worlds, and the screen classification rule (no Lean, no model)."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import ladder_walls_v1 as W  # noqa: E402
import analysis_a7_screen as A  # noqa: E402


def test_certificates_are_clean_on_several_seeds():
    for step in W.WALLS:
        for i in range(5):
            c = W.certify(W.make_wall(f"test-{i}", step))
            assert c["clean"], (step, i, c["unintended_shortcuts"][:3], c["exact_separating"])


def test_intended_invariants_are_found_where_linear():
    w2 = W.make_wall("test-0", "W2"); c2 = W.certify(w2)
    assert c2["exact_linear_invariants"] and not c2["exact_separating"]          # the plane form exists and does not separate
    assert any(s["intended_family"] and s["m"] == w2.params["k"] for s in c2["modular_shortcuts"])
    w4 = W.make_wall("test-0", "W4"); c4 = W.certify(w4)
    assert any(s["intended_family"] and s["m"] == w4.params["n"] for s in c4["modular_shortcuts"])


def test_deterministic_and_instance_id_covers_the_step():
    a, b = W.make_wall("same-seed", "W1"), W.make_wall("same-seed", "W1")
    assert (a.moves, a.start, a.statement, a.measure) == (b.moves, b.start, b.statement, b.measure)
    assert len({W.make_wall("same-seed", s).instance for s in W.WALLS}) == len(W.WALLS)


def test_mutated_worlds_are_different():
    for step in W.WALLS:
        w = W.make_wall("test-0", step); m, witness = W.mutated_wall(w)
        assert (m.start, m.statement) != (w.start, w.statement) and "Reaches.refl" in witness


def _rows(step, arm, k, n=8):
    return [{"step": step, "arm": arm, "instance": f"I{i % 2}", "status": "solved" if i < k else "turn_limit", "solved": i < k} for i in range(n)]


def test_screen_classification_rule():
    base = _rows("W1", "none", 0) + _rows("W1", "reference", 3) + _rows("W2", "none", 1) + _rows("W2", "reference", 8) \
         + _rows("W3", "none", 0) + _rows("W3", "reference", 1) + _rows("W4", "none", 0) + _rows("W4", "reference", 2)
    own = _rows("W1", "none", 2) + _rows("W2", "none", 0) + _rows("W3", "none", 0) + _rows("W4", "none", 1)
    out = A.analyze(base, own)
    cls = {s: c["class"] for s, c in out["candidates"].items()}
    assert cls == {"W1": "wall_candidate", "W2": "not_a_wall", "W3": "tooling_wall", "W4": "wall_candidate"}
    assert out["candidates"]["W1"]["early_crossing_signal"] and not out["candidates"]["W4"]["early_crossing_signal"]
    assert out["verdict"] == "walls_found" and out["wall_candidates"] == ["W1", "W4"]
    empty = A.analyze(_rows("W1", "none", 1) + _rows("W1", "reference", 8), [])
    assert empty["verdict"] == "no_wall_in_family"


import analysis_a7_confirm as C  # noqa: E402


def _cells(step, arm, per_instance_solved, attempts):
    rows = []
    for i, k in enumerate(per_instance_solved):
        for a in range(attempts):
            rows.append({"step": step, "arm": arm, "instance": f"I{i}", "status": "solved" if a < k else "turn_limit", "solved": a < k})
    return rows


def test_confirmation_rules():
    base = _cells("W1", "none", [0] * 6, 8) + _cells("W2", "none", [0] * 6, 8) + _cells("W3", "none", [0, 0, 0, 0, 0, 1], 8)
    own = _cells("W1", "none", [4, 3, 5, 2, 6, 3], 8) + _cells("W2", "none", [1, 0, 0, 2, 0, 0], 8) + _cells("W3", "none", [8] * 6, 8)
    ref = _cells("W1", "reference", [2] * 6, 4) + _cells("W2", "reference", [3] * 6, 4) + _cells("W3", "reference", [4] * 6, 4)
    curm = _cells("W1", "none", [0] * 6, 4) + _cells("W2", "none", [0] * 6, 4) + _cells("W3", "none", [0] * 6, 4)
    out = C.analyze(["W1", "W2", "W3"], base, own, ref, curm)
    v = {w: out["walls"][w]["verdict"] for w in out["walls"]}
    assert v == {"W1": "loop_crosses_a_wall", "W2": "wall_holds_for_the_loop", "W3": "not_a_wall_at_scale"}
    assert out["walls"]["W1"]["own2_vs_base"]["p"] <= 0.0157 and out["verdict"] == "new_for_the_system_in_this_family"
    assert not out["walls"]["W1"]["curm2_vs_base_descriptive"]["rise"]
    none = C.analyze(["W2"], base, own, ref, curm)
    assert none["verdict"] == "no_crossing"


import analysis_a8_narrow as N  # noqa: E402


def _a8(family, solved_per_instance, attempts=3):
    return [{"step": family, "arm": "none", "instance": f"I{i}", "status": "solved" if a < k else "turn_limit", "solved": a < k}
            for i, k in enumerate(solved_per_instance) for a in range(attempts)]


def test_a8_narrowing_rules():
    base = _a8("W1", [0, 0, 1, 0, 0, 1]) + _a8("W2", [2, 2, 3, 2, 2, 2]) + _a8("W3", [1, 2, 1, 1, 2, 1]) + _a8("W4", [2, 1, 2, 2, 1, 2])
    own = _a8("W1", [2, 2, 3, 2, 2, 3]) + _a8("W2", [3, 3, 3, 3, 3, 3]) + _a8("W3", [2, 3, 2, 2, 3, 2]) + _a8("W4", [2, 1, 2, 2, 1, 2])
    curm = _a8("W1", [0, 0, 0, 0, 0, 0]) + _a8("W2", [0, 0, 0, 0, 0, 0]) + _a8("W3", [0, 0, 0, 0, 0, 0]) + _a8("W4", [2, 1, 2, 2, 1, 2])
    out = N.analyze(base, own, curm)
    assert out["rules"]["P_narrow"] and out["rules"]["P_generalise"]
    assert out["verdict"] == "curation_narrows_and_self_generalises"
    assert out["families"]["W1"]["floor_for_fall"] and not out["families"]["W1"]["curm2_vs_base"]["fall"]   # floor: base below 0.25
    assert set(out["rules"]["families_narrowed"]) == {"W2", "W3"} and "W4" not in out["rules"]["families_generalised"]
    flat = N.analyze(base, base, base)
    assert flat["verdict"] == "neither_moves"
