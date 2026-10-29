"""A1 sibling ladder: generator determinism and structure (no Lean), Lean verification of one instance
(skipped without lake), and the pre-data analysis on synthetic outcomes."""
from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path
import numpy as np, pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
import analysis_a1 as A  # noqa: E402


def test_steps_are_deterministic_and_seeded():
    a = [L.make_step("t-1", s) for s in L.STEPS]; b = [L.make_step("t-1", s) for s in L.STEPS]; c = [L.make_step("t-2", s) for s in L.STEPS]
    assert [w.params for w in a] == [w.params for w in b]
    assert any(x.params != y.params for x, y in zip(a, c))
    assert L.instance_id("t-1") != L.instance_id("t-2") and L.instance_id("t-1").startswith("S")


def test_schema_invariants_hold_by_construction():
    for seed in ("t-1", "t-2", "t-3", "t-4"):
        w2 = L.make_step(seed, "L2"); al, be = w2.params["alpha"], w2.params["beta"]
        for m in (w2.params["m1"], w2.params["m2"]):
            assert al * m[0] + be * m[1] + m[2] == 0
        st, t = w2.params["start"], w2.params["target"]
        assert al * st[0] + be * st[1] + st[2] != al * t[0] + be * t[1] + t[2]
        w3 = L.make_step(seed, "L3"); n, c2 = w3.params["n"], w3.params["c2"]
        for m in (w3.params["m1"], w3.params["m2"]):
            assert (m[0] + c2 * m[1]) % n == 0
        assert (w3.params["start"][0] + c2 * w3.params["start"][1]) % n != (w3.params["target"][0] + c2 * w3.params["target"][1]) % n
        assert L.make_step(seed, "L4").params["start_measure"] >= 1 and L.make_step(seed, "L5").params["start_measure"] < 0
        assert L.make_step(seed, "L1").params["d"] != 0


def test_build_instance_layout_and_sources(tmp_path):
    dirs = L.build_instance("t-1", tmp_path, phase="development")
    assert [d.name for d in dirs] == list(L.STEPS)
    for i, d in enumerate(dirs):
        meta = L.load_step(d)
        assert meta["roles"]["statement"] == "LadderStatement" and meta["step_index"] == i + 1
        assert (d / "World/ChallengeEvaluation.lean").read_text().count("def LadderStatement : Prop") == 1
        assert (d / "Sources/Sham.lean").read_text() == L.SHAM_ASSET.read_text()
        if i == 0:
            assert not (d / "Sources/Ladder.lean").exists() and meta["source_files"]["ladder"] is None
        else:
            src = (d / "Sources/Ladder.lean").read_text()
            prev = L.make_step("t-1", L.STEPS[i - 1])
            assert "namespace Source" in src and "source_solution" in src and "s.u" in src and prev.namespace not in src
            assert abs(src.count("\n") - (d / "Sources/Sham.lean").read_text().count("\n")) <= 25
    with pytest.raises(FileExistsError):
        L.build_instance("t-1", tmp_path, phase="development")


def test_mutations_make_the_start_a_target():
    for seed in ("t-1", "t-2"):
        for s in L.STEPS:
            w = L.make_step(seed, s); m, witness = L.mutated(w)
            assert "Reaches.refl start" in witness and (m.start != w.start or m.statement != w.statement)


@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean toolchain not available")
def test_lean_verifies_reference_and_rejects_mutation(tmp_path):
    dirs = L.build_instance("t-lean", tmp_path, phase="development")
    for d in dirs:
        r = L.verify_step(d); assert r["modules_ok"] and r["reference_ok"], r
        m = L.mutation_check(d); assert m["reference_rejected"] and m["witness_ok"], m


# ------------------------------------------------------------------------------------------- analysis (synthetic)

def synth_plan_and_rows(p_none, p_ladder, p_sham, instances=6, n=4, seed=0, budget="b16k", fail=0):
    rng = np.random.default_rng(seed); cells, rows = [], []
    for i in range(instances):
        inst = f"S{i:08d}"
        for s in A.STEPS:
            for arm in ("none", "ladder", "sham"):
                if arm != "none" and s == "L1":
                    continue
                for a in range(n):
                    cid = f"{inst}_{s}_{arm}_{a}"; cells.append({"cell_id": cid, "instance": inst, "step": s, "arm": arm, "attempt": a, "budget_label": budget})
                    p = {"none": p_none, "ladder": p_ladder, "sham": p_sham}[arm][s]
                    status = "solved" if rng.random() < p else "unsolved"
                    if fail and rng.random() < fail:
                        status = "infrastructure_failure"
                    rows.append({**cells[-1], "status": status, "solved": status == "solved", "cost": 0.3, "tokens_out": 5000})
    return {"cells": cells, "main_budget_label": budget}, rows


def test_main_analysis_detects_a_ladder_effect_and_null():
    none = {"L1": 0.9, "L2": 0.6, "L3": 0.4, "L4": 0.25, "L5": 0.1}
    ladder = {"L1": 0.9, "L2": 0.95, "L3": 0.9, "L4": 0.8, "L5": 0.6}
    plan, rows = synth_plan_and_rows(none, ladder, none, instances=8, n=6)
    out = A.analyze_main(plan, rows)
    assert out["contrasts"]["P1"]["mean"] > 0 and out["contrasts"]["P1"]["p"] < 0.05
    assert out["verdict"] == "ladder_saves_bits_beyond_generic_example" and out["status"] in ("interessante", "proveitoso")
    assert out["chain_vs_width"]["mean_chain"] is not None
    plan, rows = synth_plan_and_rows(none, none, none, instances=8, n=6, seed=1)
    out = A.analyze_main(plan, rows)
    assert out["verdict"] == "close_no_bits_saved" and out["status"] == "limite"
    md = A.render(out); assert "Veredito pré-declarado" in md and "P1" in md


def test_main_guards_and_not_observed():
    zero = {s: 0.0 for s in A.STEPS}; one = {s: 1.0 for s in A.STEPS}
    plan, rows = synth_plan_and_rows(zero, zero, zero); out = A.analyze_main(plan, rows)
    assert out["guards"]["prior_floor"] and out["verdict"] == "unmeasurable_prior_floor" and out["status"] == "limite"
    plan, rows = synth_plan_and_rows(one, one, one); out = A.analyze_main(plan, rows)
    assert out["guards"]["ceiling"] and out["verdict"] == "unmeasurable_ceiling"
    half = {s: 0.5 for s in A.STEPS}
    plan, rows = synth_plan_and_rows(half, half, half, fail=0.3, seed=2); out = A.analyze_main(plan, rows)
    assert out["n_not_observed"] > 0 and out["guards"]["instrument"] and out["verdict"] == "close_no_bits_saved"
    assert A.bits(4, 0) > A.bits(4, 2) > A.bits(4, 4) and abs(A.phat(4, 2) - 0.5) < 1e-9
    # the session's own output cap is an observed failed attempt, not an infrastructure failure
    rows2 = [dict(r, status="budget_exhausted", solved=False) for r in rows]
    out2 = A.analyze_main(plan, rows2)
    assert out2["n_not_observed"] == 0 and not out2["guards"]["instrument"] and out2["guards"]["prior_floor"]


def test_pilot_analysis_budget_rule():
    rows, cells = [], []
    rates = {"b8k": {"L1": 0.5, "L2": 0.25, "L3": 0.0, "L4": 0.0, "L5": 0.0}, "b16k": {"L1": 1.0, "L2": 0.75, "L3": 0.5, "L4": 0.25, "L5": 0.0}}
    for b, rs in rates.items():
        for i in range(2):
            for s, r in rs.items():
                for a in range(4):
                    c = {"cell_id": f"{i}_{s}_{b}_{a}", "instance": f"S{i}", "step": s, "arm": "none", "attempt": a, "budget_label": b}
                    cells.append(c); rows.append({**c, "status": "solved" if a < round(4 * r) else "unsolved", "solved": a < round(4 * r), "cost": 0.2, "tokens_out": 100})
    out = A.analyze_pilot({"cells": cells}, rows)
    assert out["decision"]["budget_for_main"] == "b16k" and out["decision"]["gradient_L1_gt_L5"] and out["decision"]["proceed_to_main"]
    assert "Decisão pré-declarada" in A.render(out)


# ------------------------------------------------------------------------------------------- v2 (form vs idea)
import analysis_a1v2 as V2  # noqa: E402


def test_content_hint_has_the_idea_and_no_lean():
    for seed in ("t-1", "t-2"):
        for s in L.STEPS:
            w = L.make_step(seed, s); h = L.render_content_hint(w)
            assert "theorem" not in h and "grind" not in h and "omega" not in h and ":= by" not in h and "import" not in h
            assert f"Q = " in h and str(L.start_value(w)) in h and w.hint_target in h
        assert L.start_value(L.make_step(seed, "L4")) == L.make_step(seed, "L4").params["start_measure"]


def test_build_writes_content_source_and_metadata(tmp_path):
    d = L.build_instance("t-v2", tmp_path, phase="main_v2")[3]
    meta = L.load_step(d)
    assert meta["source_files"]["content"] == "Sources/Content.md" and meta["source_files"]["skeleton"] == "Sources/Sham.md"
    assert (d / "Sources/Content.md").read_text().startswith("# Hint")


def synth_v2(p, instances=6, n=4, seed=0):
    rng = np.random.default_rng(seed); cells, rows = [], []
    for i in range(instances):
        inst = f"S{i:08d}"
        for s in V2.STEPS:
            draws = [rng.random() for _ in range(n)]   # one draw per attempt, shared across arms: equal p -> identical outcomes
            for arm in V2.ARMS:
                for a in range(n):
                    c = {"cell_id": f"{inst}_{s}_{arm}_{a}", "instance": inst, "step": s, "arm": arm, "attempt": a, "budget_label": "b8k"}
                    status = "solved" if draws[a] < p[arm][s] else "output_limit"
                    cells.append(c); rows.append({**c, "status": status, "solved": status == "solved", "cost": 0.2, "tokens_out": 3000})
    return {"cells": cells, "main_budget_label": "b8k"}, rows


def test_v2_verdicts():
    none = {"L4": 0.15, "L5": 0.4}; skel = {"L4": 0.7, "L5": 1.0}; cont = {"L4": 0.2, "L5": 0.5}
    out = V2.analyze_v2(*synth_v2({"none": none, "skeleton": skel, "content": cont}, instances=8, n=6))
    assert out["verdict"] == "skeleton_saves_bits" and out["form_vs_idea"] == "skeleton_beats_content" and out["status"] == "proveitoso"
    out = V2.analyze_v2(*synth_v2({"none": none, "skeleton": skel, "content": skel}, instances=8, n=6, seed=1))
    assert out["verdict"] == "skeleton_saves_bits" and out["content_effect"] == "also" and out["status"] == "interessante"
    out = V2.analyze_v2(*synth_v2({"none": none, "skeleton": none, "content": none}, instances=8, n=6, seed=2))
    assert out["verdict"] == "close_no_skeleton_effect" and out["status"] == "limite"
    zero = {"L4": 0.0, "L5": 0.0}
    out = V2.analyze_v2(*synth_v2({"none": zero, "skeleton": zero, "content": zero}))
    assert out["guards"]["prior_floor"] and out["status"] == "limite"
    assert "Veredito pré-declarado" in V2.render(out)


# ------------------------------------------------------------------------------------------- v3 (self-ladder)
import analysis_a1v3 as V3  # noqa: E402


def test_pell_world_E_and_extra_build(tmp_path):
    for seed in ("t-1", "t-2", "t-3"):
        w = L.make_step(seed, "E"); D, (a, b) = w.params["D"], w.params["unit"]
        assert a * a - D * b * b == 1 and w.params["start_measure"] < 0 and w.step_tactic == "grind" and w.solution_close.startswith("grind")
    dirs = L.build_instance("t-e", tmp_path, phase="main_v3", extra=("E",))
    assert [d.name for d in dirs] == list(L.STEPS) + ["E"]
    meta = L.load_step(dirs[-1]); assert meta["step_index"] == 0 and meta["source_files"]["ladder"] is None and (dirs[-1] / "Hidden/Reference.lean").exists()
    m, witness = L.mutated(L.make_step("t-e", "E")); assert m.start == (1, 0) and "Reaches.refl" in witness


def synth_v3(pE, p, instances=6, n=4, seed=0):
    rng = np.random.default_rng(seed); cells1, rows1, cells2, rows2 = [], [], [], []
    for i in range(instances):
        inst = f"S{i:08d}"
        for a in range(n):
            c = {"cell_id": f"{inst}_E_none_{a}", "instance": inst, "step": "E", "arm": "none", "attempt": a, "budget_label": "b8k"}
            st = "solved" if rng.random() < pE else "output_limit"; cells1.append(c); rows1.append({**c, "status": st, "solved": st == "solved", "cost": 0.1, "tokens_out": 1000})
        for s in V3.STEPS:
            draws = [rng.random() for _ in range(n)]
            for arm in V3.ARMS:
                for a in range(n):
                    c = {"cell_id": f"{inst}_{s}_{arm}_{a}", "instance": inst, "step": s, "arm": arm, "attempt": a, "budget_label": "b8k"}
                    st = "solved" if draws[a] < p[arm][s] else "output_limit"; cells2.append(c); rows2.append({**c, "status": st, "solved": st == "solved", "cost": 0.2, "tokens_out": 3000})
    return {"cells": cells2, "main_budget_label": "b8k"}, rows2, {"cells": cells1, "main_budget_label": "b8k"}, rows1


def test_v3_verdicts():
    none = {"L4": 0.15, "L5": 0.2}; own = {"L4": 0.6, "L5": 0.95}
    out = V3.analyze_v3(*synth_v3(0.9, {"none": none, "own": own, "reference": own}, instances=8, n=6))
    assert out["verdict"] == "own_saves_bits" and out["own_vs_reference"] == "own_matches_reference" and out["status"] == "proveitoso"
    assert out["chain_vs_width"]["L5"]["mean_chain"] > out["chain_vs_width"]["L5"]["mean_width"] and out["pooled"]["E"]["none"][1] == 48
    out = V3.analyze_v3(*synth_v3(0.9, {"none": none, "own": none, "reference": own}, instances=8, n=6, seed=1))
    assert out["verdict"] == "close_no_own_effect" and out["status"] == "limite"
    weak = {"L4": 0.35, "L5": 0.5}
    out = V3.analyze_v3(*synth_v3(0.9, {"none": none, "own": weak, "reference": own}, instances=8, n=8, seed=3))
    assert out["contrasts"]["S1"]["mean"] < 0 and out["own_vs_reference"] == "reference_better"
    out = V3.analyze_v3(*synth_v3(0.0, {"none": none, "own": none, "reference": own}, instances=8, n=6, seed=2))
    assert out["guards"]["stage1_floor"] and out["status"] == "limite"
    assert "Veredito pré-declarado" in V3.render(out)


# ------------------------------------------------------------------------------------------- Mathlib flavor (A2)
def test_mathlib_flavor_renders_and_shared_lake_hook(tmp_path, monkeypatch):
    from creative_machine.formal_routes.submission import attach_shared_lake
    dirs = L.build_instance("t-m", tmp_path / "w", phase="a2_mathlib", env="mathlib")
    base = (dirs[3] / "World/Base.lean").read_text(); lake = (dirs[3] / "lakefile.toml").read_text()
    assert base.startswith("import Mathlib") and 'name = "mathlib"' in lake and L.MATHLIB_REV in lake and L.load_step(dirs[3])["env"] == "mathlib"
    assert (L.build_instance("t-s", tmp_path / "w2", phase="x")[0] / "World/Base.lean").read_text().startswith("import Std")
    shared = tmp_path / "shared"; (shared / ".lake/packages").mkdir(parents=True); (shared / "lake-manifest.json").write_text("{}")
    staged = tmp_path / "staged"; staged.mkdir(); (staged / "lakefile.toml").write_text(lake)
    monkeypatch.delenv("CM_LAKE_SHARED", raising=False); assert attach_shared_lake(staged) is False
    monkeypatch.setenv("CM_LAKE_SHARED", str(shared)); assert attach_shared_lake(staged) is True
    assert (staged / ".lake/packages").is_symlink() and (staged / "lake-manifest.json").exists()
    std_staged = tmp_path / "std"; std_staged.mkdir(); (std_staged / "lakefile.toml").write_text('name = "x"\n[[lean_lib]]\nname = "World"\n')
    assert attach_shared_lake(std_staged) is False
