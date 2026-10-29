"""A9 analysis rules on synthetic rows (no Lean, no model): composes / cheapens_only / saturates, forgetting, missing arms; and the W5 family."""
from __future__ import annotations
import itertools, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import ladder_walls_v1 as W  # noqa: E402
import analysis_a9 as A  # noqa: E402


def rows(step, per_instance_k, n=3):
    out = []
    for i, k in enumerate(per_instance_k):
        out += [{"step": step, "instance": f"I{i}", "status": "solved" if j < k else "turn_limit", "solved": j < k} for j in range(n)]
    return out


def base_rows():
    r = {a: [] for a in A.ARMS}
    for f in A.WALLS:
        r["own2t"] += rows(f, [2] * 6); r["own3t"] += rows(f, [2] * 6); r["basen"] += rows(f, [0] * 6); r["own2n"] += rows(f, [0] * 6); r["own3n"] += rows(f, [0] * 6)
    for s in A.LADDER:
        r["own2lad"] += rows(s, [3] * 6, 4); r["own3lad"] += rows(s, [3] * 6, 4)
    r["w5base"] = rows("W5", [0] * 6); r["w5own2"] = rows("W5", [1] * 6); r["w5own3"] = rows("W5", [1] * 6); r["w5own2n"] = rows("W5", [0] * 6); r["w5own3n"] = rows("W5", [0] * 6)
    return r


def test_saturates_when_nothing_moves():
    out = A.analyze(base_rows())
    assert out["verdict"] == "saturates" and out["rules"]["P_retain"] and out["W5_base_is_wall_candidate"]


def test_composes_when_own3_rises_on_w5():
    r = base_rows(); r["w5own3"] = rows("W5", [3, 3, 2, 3, 2, 3])
    out = A.analyze(r); assert out["verdict"] == "composes" and out["rules"]["P_compose"]


def test_cheapens_only_needs_two_families():
    r = base_rows(); r["own3n"] = [x for x in r["own3n"] if x["step"] not in ("W1", "W3")] + rows("W1", [3] * 6) + rows("W3", [3, 2, 3, 3, 2, 3])
    out = A.analyze(r); assert out["verdict"] == "cheapens_only" and out["rules"]["families_cheapened"] == ["W1", "W3"]
    r["own3n"] = [x for x in r["own3n"] if x["step"] != "W3"] + rows("W3", [0] * 6)
    assert A.analyze(r)["verdict"] == "saturates"


def test_forgetting_is_flagged_on_the_ladder_and_on_the_walls():
    r = base_rows(); r["own3lad"] = [x for x in r["own3lad"] if x["step"] != "E"] + rows("E", [0, 1, 0, 1, 0, 0], 4)
    out = A.analyze(r); assert out["verdict"] == "saturates_with_forgetting" and out["rules"]["blocks_fallen"] == ["E"]
    r = base_rows(); r["own3t"] = [x for x in r["own3t"] if x["step"] != "W2"] + rows("W2", [0] * 6)
    assert A.analyze(r)["rules"]["blocks_fallen"] == ["W2"]


def test_missing_arm_is_not_a_rise_and_render_works():
    r = base_rows(); r["w5own2"] = []
    out = A.analyze(r); assert not out["rules"]["P_compose"] and "W5" in A.render(out)


def test_w5_is_clean_conserved_mod_p_and_separating_and_leaves_w1_w4_untouched():
    for i in range(8):
        w = W.make_wall(f"test-{i}", "W5"); c = W.certify(w); P = w.params; p = P["p"]; cx, cy, cz, cw = P["offsets"]
        q = lambda s: ((s[0] - cx) * (s[3] - cw) - (s[1] - cy) * (s[2] - cz)) % p
        assert c["clean"] and not c["exact_linear_invariants"], (i, c)
        for s in itertools.product(range(-1, 2), repeat=4):
            for mv in P["affine"]:
                t = tuple(sum(mv["M"][a][b] * s[b] for b in range(4)) + mv["c"][a] for a in range(4))
                assert q(t) == q(s)
        assert q(tuple(P["start"])) != q(tuple(P["target"])) and "W5" not in W.WALLS
    m, witness = W.mutated_wall(W.make_wall("test-0", "W5")); assert "Reaches.refl" in witness
