"""Synthetic checks of the R1 mechanical checks (scripts/r1_mechanical.py); no network, no real document."""

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("r1_mech", Path(__file__).resolve().parent.parent / "scripts/r1_mechanical.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)


def test_numbers_and_tolerance():
    assert rm.numbers(r"gain +0.71 \ci{+0.36}{+1.09}, 65\% of windows, see \cite{x2026.1234} and 2026") == \
        ["+0.71", "+0.36", "+1.09", "65"]
    assert rm.found("0.71", [0.7123]) and not rm.found("0.75", [0.7123])
    assert rm.found("-1.2", [1.24]) and not rm.found("1.3", [1.24])


def test_split_body_tables_and_appendix():
    lines = ["Body 1.50 here", r"\begin{table}", "1.50 & 2.25 \\\\", r"\end{table}", "More 2.25", r"\appendix", "App 3.75"]
    body, ref = rm.split_body(lines)
    assert [n for n, _ in body] == [1, 5]
    assert ref == [r"\begin{table}", "1.50 & 2.25 \\\\", r"\end{table}", r"\appendix", "App 3.75"]


def test_c3_flags_only_missing_numbers(tmp_path):
    d = tmp_path / "PX"
    d.mkdir()
    (d / "flat.tex").write_text("The gain is +0.71 (table) and +0.75 (old run).\n% comment 9.99\n"
                                "\\begin{tabular}\n x & 0.71 \\\\\n\\end{tabular}\n")
    res = rm.c3(tmp_path, "PX")
    assert res["n_findings"] == 1 and "0.75" in res["findings"][0]["problem"] and "0.71" not in res["findings"][0]["problem"]


def test_bib_parsing_and_c4_without_network(tmp_path, monkeypatch):
    src = tmp_path / "PX" / "src"
    src.mkdir(parents=True)
    (src / "references.bib").write_text(
        "@misc{a2023, title = {Scaling {LLM} Things}, author = {Singh, Avi and Stanton, Ankesh}, eprint = {2312.06585},"
        " primaryClass = {cs.AI}}\n@article{b, title={Other}, author={Doe, J.}, doi={10.1/x}}\n@book{c, title={No ids}}\n")
    entries = rm.parse_bib((src / "references.bib").read_text())
    assert [e["key"] for e in entries] == ["a2023", "b", "c"] and rm.arxiv_id(entries[0]) == "2312.06585"
    assert rm.surname("Singh, Avi and Stanton, Ankesh") == "singh" and rm.surname("Avi Singh") == "singh"
    monkeypatch.setattr(rm, "arxiv_meta", lambda ids: {"2312.06585": {"title": "Scaling LLM things",
                                                                      "authors": ["Avi Singh", "Ankesh Anand"],
                                                                      "primary": "cs.LG"}})
    monkeypatch.setattr(rm, "crossref_meta", lambda doi: {"title": "Something else entirely", "authors": ["Doe"]})
    res = rm.c4(tmp_path, "PX")
    probs = {f["bib_key"]: f["problem"] for f in res["findings"]}
    assert "primaryClass cs.AI vs arXiv cs.LG" in probs["a2023"] and "title differs" in probs["b"] and "c" not in probs
    assert "stanton" in probs["a2023"] and "singh" not in probs["a2023"].split("record")[0]
    assert res["n_resolvable"] == 2
