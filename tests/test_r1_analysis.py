"""Synthetic checks of the R1 analysis (scripts/r1_analysis.py), written before any replay data exists."""

import importlib.util
import json
import math
from pathlib import Path

spec = importlib.util.spec_from_file_location("r1_analysis", Path(__file__).resolve().parent.parent / "scripts/r1_analysis.py")
ra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ra)


def item(i, doc="P1", cls="NUM", sev="G2", primary=True):
    return {"id": i, "doc": doc, "class": cls, "severity": sev, "primary": primary}


def test_wilson_known_values():
    lo, hi = ra.wilson(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3
    lo, hi = ra.wilson(0, 10)
    assert lo == 0.0 and abs(hi - 0.2775) < 1e-3
    assert all(math.isnan(x) for x in ra.wilson(0, 0))


def test_chao1_with_and_without_doubletons():
    # items a,b caught once; c caught twice; d three times -> S=4, f1=2, f2=1, N = 4 + 4/2 = 6
    out = ra.chao1([{"a", "c", "d"}, {"b", "c", "d"}, {"d"}])
    assert (out["S"], out["f1"], out["f2"]) == (4, 2, 1) and out["N_hat"] == 6.0
    # f2 = 0: bias-corrected form S + f1(f1-1)/2
    out = ra.chao1([{"a"}, {"b"}, {"c", "d"}, {"d"}, {"d"}])
    assert (out["S"], out["f1"], out["f2"]) == (4, 3, 0) and out["N_hat"] == 4 + 3
    assert ra.chao1([set()])["S"] == 0


def test_recall_table_respects_docs_seen():
    ref = [item("a", "P1"), item("b", "P1", "META"), item("c", "P2")]
    occ = {"X": {"caught": ["a", "c"], "docs": ["P1"]}}
    rows = ra.recall_table(ref, occ, "class")
    allrow = next(r for r in rows if r["class"] == "ALL")
    assert (allrow["k"], allrow["n"]) == (1, 2)          # c is in P2, which X did not see


def test_second_opinion_song_style():
    occ = {"C1:opus:r1": {"caught": ["a", "b"]}, "C1:opus:r2": {"caught": ["a", "b"]},
           "C1:gpt:r1": {"caught": ["c"]}, "C1:gpt:r2": {"caught": ["a"]}}
    so = ra.second_opinion(occ)
    assert so["same_family_pair"] == 2
    assert so["cross_family_pair_mean"] == (3 + 3 + 2 + 2) / 4 and so["n_cross_pairs"] == 4


def test_predictions_and_continuation():
    ref = [item("m1", cls="META"), item("m2", cls="STATUS"), item("n1", cls="NUM"), item("n2", cls="NUM"),
           item("i1", cls="INTERNAL")]
    occ = {"C1:opus:r1": {"caught": ["i1"]}, "C1:opus:r2": {"caught": ["i1"]},
           "C1:gpt:r1": {"caught": ["i1", "n1"]}, "C1:gpt:r2": {"caught": []},
           "C2:opus": {"caught": ["m1", "m2"]}, "C3": {"caught": ["n1", "n2"], "findings": 20, "true_findings": 2}}
    preds = {p["id"]: p for p in ra.predictions(ref, occ)}
    assert preds[1]["holds"] and preds[2]["holds"] and preds[3]["holds"] and preds[4]["holds"]
    assert preds[5]["value"] == 2 / 5 and preds[5]["holds"]
    rule = ra.continuation_rule(ref, occ)
    assert rule["continue_to_R2"] and rule["gap"] == 1.0


def test_report_end_to_end(tmp_path):
    ref = [item("a"), item("b", cls="META"), item("c", primary=False)]
    (tmp_path / "ref.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ref))
    cap = {"occasions": {"H2": {"caught": ["a", "b"]}, "C1:opus:r1": {"caught": ["a"], "findings": 4, "true_findings": 1}},
           "added_items": [item("N-1", cls="TYPO")]}
    (tmp_path / "cap.json").write_text(json.dumps(cap))
    r, c = ra.load(tmp_path / "ref.jsonl", tmp_path / "cap.json")
    md, result = ra.report(r, c)
    assert result["n_primary"] == 2 and result["n_added"] == 1
    assert result["precision"]["C1:opus:r1"] == 0.25
    assert "Captura" in md
