"""Offline checks of the R1 judging helpers (scripts/r1_judging.py); no model is called."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("r1_judging", Path(__file__).resolve().parent.parent / "scripts/r1_judging.py")
rj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rj)


def test_parse_json_variants():
    assert rj.parse_json('[{"a": 1}]') == [{"a": 1}]
    assert rj.parse_json('Here:\n```json\n[{"a": 2}]\n```') == [{"a": 2}]
    assert rj.parse_json('noise {"quote": "x", "problem": "y"} tail') == {"quote": "x", "problem": "y"}
    assert rj.parse_json("no json here") is None


def test_kappa():
    assert rj.kappa(["A", "B", "A", "B"], ["A", "B", "A", "B"]) == 1.0
    assert abs(rj.kappa(["A", "A", "B", "B"], ["A", "B", "A", "B"])) < 1e-12


def test_occasion_names():
    assert rj.occasion_of("c1_deepseek_P3_r2") == "C1:deepseek:r2"
    assert rj.occasion_of("c2_opus_PS") == "C2:opus"
    assert rj.occasion_of("c3_P6") == "C3" and rj.occasion_of("c4_P1") == "C4"


def test_severity_normalization():
    assert rj.severity_of({"severity": "High"}) == "high"
    assert rj.severity_of({"severity": "minor (style)"}) == "low"
    assert rj.severity_of({"severity": "Major."}) == "high"
    assert rj.severity_of({}) == ""


def test_lenient_parser_repairs_latex_backslashes():
    raw = '```json\n[{"quote": "gain of 65--80\\% with \\ci{+0.43}{+2.11}", "problem": "x", "severity": "high"}]\n```'
    assert rj.rr.parse_findings(raw) is None
    got = rj.parse_findings_lenient(raw)
    assert got and got[0]["quote"] == "gain of 65--80\\% with \\ci{+0.43}{+2.11}"
    assert rj.parse_findings_lenient('{"errors": [{"quote": "a", "problem": "b"}]}') == [{"quote": "a", "problem": "b"}]
    assert rj.parse_findings_lenient('[{"quote": "line\\nbreak"}]')[0]["quote"] == "line\nbreak"
    assert rj.parse_findings_lenient("nothing to see") is None


def test_repair_keeps_escaped_pairs():
    assert rj.json.loads(rj.repair_backslashes('["a \\\\ci{1}"]')) == ["a \\ci{1}"]
    assert rj.json.loads(rj.repair_backslashes('["\\\\\\ci"]')) == ["\\\\ci"]
    assert rj.json.loads(rj.repair_backslashes('["\\textbf{x} \\u00e9 \\" q"]')) == ['\\textbf{x} é " q']
