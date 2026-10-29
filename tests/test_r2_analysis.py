"""Synthetic checks of the R2 analysis and of the R2 writers' rendering, before any model call on the records."""

import importlib.util
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ra = load("r2_analysis", "scripts/r2_analysis.py")


def brute(diffs):
    obs = sum(diffs)
    hits = sum(1 for signs in itertools.product([1, -1], repeat=len(diffs))
               if sum(s * abs(d) for s, d in zip(signs, diffs)) <= obs + 1e-9)
    return hits / 2 ** len(diffs)


def test_exact_signflip_matches_brute_force():
    for diffs in ([-1, -1, -1, -1], [-2, 1, -3, 0, -1], [0.5, -1.5, -2.0, 1.0, -0.5, -3.0], [1, 2, 3]):
        assert abs(ra.exact_signflip_less(diffs) - brute(diffs)) < 1e-12
    assert ra.exact_signflip_less([-1] * 4) == 1 / 16


def test_signflip_more_than_twenty_pairs():
    diffs = [-1] * 22
    assert abs(ra.exact_signflip_less(diffs) - 1 / 2 ** 22) < 1e-15


def test_bh():
    q = ra.bh({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert abs(q["a"] - 0.04) < 1e-12 and abs(q["c"] - 0.0533333333) < 1e-6 and q["d"] == 0.5 and q["b"] == q["c"]


def make_scores(err_by_arm):
    scores = {}
    labels_all = {}
    for arm, errs in err_by_arm.items():
        for w in ("opus", "gpt"):
            for r in ("R01", "R02"):
                labels = {str(f): {"label": "stale" if f <= errs else "correct", "quote": ""} for f in range(1, 13)}
                scores[(arm, w, r)] = {"arm": arm, "writer": w, "record": r, "labels": labels,
                                       "mechanical": {"provisional_present": ["1.23"] if errs else [], "final_present": True}}
                labels_all[(arm, w, r)] = labels
    return scores


def test_analysis_end_to_end_and_floor():
    truth = {"R01": {"stale_manifest": True, "k": 1}, "R02": {"stale_manifest": False, "k": 3}}
    scores = make_scores({"W0": 4, "W1": 2, "W2": 1, "W3": 3})
    res = ra.analyse(scores, {}, {}, truth)
    assert res["mean_E"]["W0"] == 4 and not res["floor"]
    assert res["tests"]["H1"]["n_pairs"] == 4 and res["tests"]["H1"]["mean_diff"] == -3
    assert res["tests"]["H1"]["p_one_sided"] == 1 / 16
    floor = ra.analyse(make_scores({"W0": 1, "W1": 1, "W2": 0, "W3": 1}), {}, {}, truth)
    assert floor["floor"]
    # W3 corrections: W0 has facts 1-4 stale, W3 facts 1-3 stale -> fact 4 corrected in each of 4 pairs
    assert res["W3"]["opus"]["corrections"] == 2 and res["W3"]["opus"]["new_errors"] == 0


def test_partial_labels_scaled():
    s = {"labels": {"1": {"label": "stale"}, "2": {"label": "correct"}, "3": {"label": "correct"}}}
    assert ra.E(s) == 4.0


def test_render_placeholders(tmp_path, monkeypatch):
    rw = load("r2_write", "scripts/r2_write.py")
    truth = {"keyed_values": {"main": 0.93, "ci_lo": 0.64, "ci_hi": 1.22, "n": 16, "h2_est": 0.2, "h2_p": 0.174, "scope_pos": 8,
                              "scope_total": 9, "mean_per_family": 0.373, "mean_pooled": 0.852},
             "claims_rendered": {"release": "Code and aggregate data are released.", "review": "R.", "status_sweep": "S.",
                                 "registration": "G.", "companion": "+0.70", "model": "Shrike-14B-Base"}}
    (tmp_path / "R99.json").write_text(json.dumps(truth))
    monkeypatch.setattr(rw, "TRUTH", tmp_path)
    text, unknown = rw.render("Gain {{val:main}} [{{val:ci_lo}}, {{ val : ci_hi }}], n = {{val:n}}; {{claim:release}} "
                              "{{claim:model}} {{val:nope}}", "R99")
    assert text == "Gain +0.93 [+0.64, +1.22], n = 16; Code and aggregate data are released. Shrike-14B-Base {{val:nope}}"
    assert unknown == ["{{val:nope}}"]
    assert rw.strip_fence("```markdown\n# T\nx\n```") == "# T\nx"
