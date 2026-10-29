"""A2 consolidation: the pre-data analysis on synthetic rows (rules, verdicts), and the data preparer's rendering."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
import analysis_a2_consolidation as C  # noqa: E402
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402

INST = ["H1", "H2", "H3", "H4", "H5", "H6"]


def rows_for(k_by_step: dict, arm_label="none"):
    out = []
    for i in INST:
        for s, k in k_by_step.items():
            for a in range(4):
                out.append({"instance": i, "step": s, "arm": arm_label, "budget_label": "b16k", "attempt": a, "status": "solved" if a < k else "unsolved", "solved": a < k, "cost": 0.0, "tokens_out": 100})
    return out


def plans():
    return {a: {"main_budget_label": "b16k", "agent": {"model": a, "mode": "prover"}} for a in C.ARMS}


def test_form_written_and_specific():
    base = rows_for({"L1": 1, "L2": 1, "L3": 0, "L4": 0, "L5": 0, "E": 0})
    rows = {"base": base, "p1": rows_for({"L1": 1, "L2": 1, "L3": 0, "L4": 0, "L5": 3, "E": 3}), "p2": rows_for({s: 3 for s in C.STEPS6}), "p3": base}
    out = C.analyze(plans(), rows)
    assert out["rises"]["p1"]["L5"] and out["rises"]["p1"]["E"] and not out["rises"]["p1"]["L4"] and not out["rises"]["p1"]["L1"]
    assert out["rules"]["P1_form_specific"] and out["rules"]["P2_curriculum"] and out["rules"]["P3_clean"] and out["verdict"] == "form_written_and_form_specific"
    assert out["contrasts"]["p1"]["L5"]["p"] <= 0.016 and out["contrasts"]["p1"]["L5"]["pooled_diff"] == 0.75
    md = C.render(out); assert "form_written_and_form_specific" in md and "| p1 |" in md


def test_syntax_not_form_and_nothing_written():
    base = rows_for({s: 0 for s in C.STEPS6}); up = rows_for({"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 2, "E": 2})
    assert C.analyze(plans(), {"base": base, "p1": up, "p2": up, "p3": up})["verdict"] == "syntax_not_form"
    assert C.analyze(plans(), {"base": base, "p1": base, "p2": base, "p3": base})["verdict"] == "nothing_written"
    out = C.analyze(plans(), {"base": base, "p1": rows_for({"L1": 3, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "E": 0}), "p2": base, "p3": base})
    assert out["verdict"] == "form_written_not_specific" and not out["rules"]["P1_form_specific"]
    # a small rise (pooled diff < 0.25) does not count even if consistent
    small = rows_for({"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "E": 0}); small[0]["solved"] = True; small[0]["status"] = "solved"
    out = C.analyze(plans(), {"base": base, "p1": small, "p2": base, "p3": base}); assert out["verdict"] == "nothing_written"


def test_prepare_renders_exact_prover_format(tmp_path, monkeypatch):
    import a2c_prepare as P
    inst = L.build_instance("a2c-t", tmp_path / "w", phase="test", extra=("E",), env="mathlib")[0].parent
    monkeypatch.setattr(P, "ROOT", tmp_path); (tmp_path / "worlds/ladder").mkdir(parents=True); (tmp_path / "worlds/ladder" / inst.name).symlink_to(inst)
    m = P.render([inst.name], tmp_path / "data")
    assert m["counts"] == {"p1": 2, "p2": 6, "p3": 6}
    p1 = [json.loads(l) for l in (tmp_path / "data/p1.jsonl").read_text().splitlines()]
    assert {r["step"] for r in p1} == {"L5", "E"}
    r = p1[0]; assert r["prompt"].startswith("Complete the following Lean 4 code") and r["completion"].startswith("import Mathlib")
    assert "theorem bridge" in r["completion"] and "theorem step_measure" in r["completion"] and "theorem evaluation_solution :" in r["completion"] and "```" not in r["completion"]
    # the completion is the completed file: the prompt's formal statement is a prefix of it (modulo the trailing newline)
    formal = r["prompt"].split("```lean4\n", 1)[1].split("```", 1)[0]
    assert r["completion"].startswith(formal.rsplit("theorem evaluation_solution", 1)[0])
    p3 = [json.loads(l) for l in (tmp_path / "data/p3.jsonl").read_text().splitlines()]
    assert all("induction" not in x["completion"] and "measure" not in x["completion"] and "move1 s) = s" in x["completion"] for x in p3)
    assert P.control_statement("L2") == "∀ s : State, move3 (move1 s) = s"


def test_v2_replication_and_p4():
    import analysis_a2_consolidation_v2 as V
    base = rows_for({"L1": 1, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "E": 0})
    p1 = rows_for({"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 4, "E": 4}); p2 = rows_for({"L1": 4, "L2": 0, "L3": 1, "L4": 4, "L5": 4, "E": 4})
    plans = {a: {"main_budget_label": "b16k", "agent": {"model": a}} for a in V.ARMS + V.THINK_ARMS}
    out = V.analyze(plans, {"base": base, "p1": p1, "p2": p2, "p3": base})
    assert out["verdict"] == "form_written_and_form_specific" and out["replication"] == "replicated" and "think" not in out
    baset = rows_for({"L2": 0, "L3": 0}); p2t = rows_for({"L2": 3, "L3": 3})
    out = V.analyze(plans, {"base": base, "p1": p1, "p2": p2, "p3": base, "baset": baset, "p2t": p2t})
    assert out["rules"]["P4_form_plus_reasoning_L2"] and out["think"]["rises"]["L2"]["p2t_vs_p2"] and out["think"]["rises"]["L2"]["p2t_vs_baset"]
    assert out["think"]["rates"]["p2t"]["L2"]["k"] == 18 and not out["think"]["rises"]["L2"]["baset_vs_base"]
    md = V.render(out); assert "P4" in md and "replicação: `replicated`" in md
    # thinking alone explains it: p2t rises vs p2 but not vs baset -> P4 false
    out = V.analyze(plans, {"base": base, "p1": p1, "p2": p2, "p3": base, "baset": rows_for({"L2": 3, "L3": 0}), "p2t": p2t})
    assert not out["rules"]["P4_form_plus_reasoning_L2"]
