"""Programa 4 — Encaixe: the frozen family detector, the handed programs, and the --hint-file plumbing."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("slot", ROOT / "scripts/analysis_slot.py")
slot = importlib.util.module_from_spec(spec); spec.loader.exec_module(slot)
L = 5000


def pmf(atoms: dict[int, float]) -> np.ndarray:
    p = np.zeros(L)
    for i, m in atoms.items():
        p[i] += m
    return p / p.sum()


def dyadic(p0: float, levels: int, r: float = 0.5) -> np.ndarray:
    top = L - 1
    at = {0: p0}
    for i in range(1, levels + 1):
        at[int(round((1 - r ** i) * top))] = at.get(int(round((1 - r ** i) * top)), 0) + (1 - p0) / levels
    return pmf(at)


def test_detector_geometric_ladders_of_any_ratio_are_family():
    assert slot.is_family(dyadic(0.25, 3))["family"]          # the crude seed: three dyadic rungs + atom at zero
    assert slot.is_family(dyadic(0.45, 12))["family"]         # the oracle's shape
    assert slot.is_family(dyadic(0.34, 30, r=0.92))["family"]   # the proposer's r = 0.92 implementation (structural s12)
    assert slot.is_family(dyadic(0.55, 15, r=0.4))["family"]    # structural s13's ratio
    f = slot.is_family(dyadic(0.45, 12))
    assert f["rungs"] >= 10 and abs(f["ratio"] - 0.5) < 0.1


def test_detector_rejects_the_unaided_sparse_family_and_dense_blocks():
    # nohint s13 of 27/08: mass at 0/1, the top four positions and L//2 — no geometric ladder
    assert not slot.is_family(pmf({0: 0.4, 1: 0.15, L - 1: 0.25, L - 2: 0.05, L - 3: 0.05, L - 4: 0.05, L // 2: 0.1}))["family"]
    # nohint s11: a bottom cluster and three atoms just above the middle + the top
    assert not slot.is_family(pmf({0: .2, 1: .15, 2: .1, 3: .05, 4: .03, L // 2 + 50: .15, L // 2 + 100: .1, L // 2 + 200: .08, L - 1: .14}))["family"]
    # a uniform block over the top decile (famseed s12 of 27/08): hundreds of atoms, ratios ~1 -> no ladder
    p = np.zeros(L); p[0] = .25; p[1] = .1; p[2] = .05; p[L // 2] = .1; p[3 * L // 4] = .1; p[9 * L // 10:] = .4 / (L - 9 * L // 10)
    assert not slot.is_family(p / p.sum())["family"]
    # a ladder WITHOUT the atom at zero is a ladder, not the family
    q = dyadic(0.45, 12); q[0] = 0; q = q / q.sum()
    f = slot.is_family(q); assert f["ladder"] and not f["family"]


def test_detector_accepts_mersenne_ladder_written_by_the_proposer():
    # famseed s13 (27/08): atoms at L-1, L-3, L-7, ..., L-255 with halving weights, mass 0.495 at zero
    at = {0: 0.495, 1: 0.005}
    for k, w in zip((1, 3, 7, 15, 31, 63, 127, 255), (.3, .15, .075, .0375, .01875, .009375, .0046875, .0046875)):
        at[L - k] = w
    f = slot.is_family(pmf(at)); assert f["family"] and f["rungs"] >= 7


def test_copy_signature_matches_the_verifier_convention():
    p = dyadic(0.25, 3)
    assert slot.sig_of(p) == slot.sig_of(p.copy()) and len(slot.sig_of(p)) == 12
    assert slot.sig_of(p) != slot.sig_of(dyadic(0.26, 3))


@pytest.mark.parametrize("name,score", [("seed_family_poor.py", 0.2734), ("seed_family_oracle.py", 0.3742), ("seed_self_s11.py", 0.3284),
                                        ("seed_words.py", 0.2708)])
def test_handed_programs_evaluate_to_their_recorded_scores(name, score):
    sys.path.insert(0, str(ROOT / "src"))
    from creative_machine.frontier_exec import run_candidate
    r = run_candidate((ROOT / "docs/hint" / name).read_text(), "beatavg", "construct", (L,), timeout_s=60)
    assert r.get("ok") and abs(r["score"] - score) < 5e-4


def test_hint_slot_carries_the_famseed_bytes():
    crude = (ROOT / "docs/hint/seed_family_poor.py").read_text()
    hint = (ROOT / "docs/hint/hint_code_poor.txt").read_text()
    assert hint.endswith(crude) and hint.startswith("a crude, unoptimized member")
    assert "One known family of strong constructions places an atom at zero" in (ROOT / "docs/hint/seed_words.py").read_text()


def test_hint_file_reaches_the_statement_without_loading_a_model(tmp_path):
    out = tmp_path / "run"
    cmd = [sys.executable, str(ROOT / "scripts/frontier_search.py"), "--problem", "beatavg", "--oai-base", "http://127.0.0.1:1/v1",
           "--gens", "0", "--hint-file", str(ROOT / "docs/hint/hint_code_poor.txt"), "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    assert "DONE best" in r.stdout, r.stdout + r.stderr
    assert "seed score 0.2708" in r.stdout


def test_transient_hint_and_pinned_seed_prompting():
    sys.path.insert(0, str(ROOT / "src"))
    spec_fs = importlib.util.spec_from_file_location("fs", ROOT / "scripts/frontier_search.py")
    fs = importlib.util.module_from_spec(spec_fs); spec_fs.loader.exec_module(fs)
    assert fs.statement_for_gen("S", "H", -1, 5).endswith("Hint: H")               # persistent hint: every generation
    assert fs.statement_for_gen("S", "H", 1, 0).endswith("Hint: H") and fs.statement_for_gen("S", "H", 1, 1) == "S"   # transient
    assert fs.statement_for_gen("S", None, 1, 0) == "S"
    P = {"statement": "S", "entry": "construct", "maximize": True}
    seed = {"code": "def construct(L):\n    return [1.0] * L\n", "score": 0.27, "hash": "seed"}
    better = {"code": "def construct(L):\n    return [2.0] * L\n", "score": 0.30, "hash": "abc"}
    assert fs.shown_elites(P, [seed, better], "schema", "# recap", pinned=seed) == [better, seed]   # displaced but pinned
    assert fs.shown_elites(P, [seed, better], "schema", "# recap", pinned=None) == [better]
    assert fs.shown_elites(P, [seed], "schema", "# recap", pinned=seed) == [seed]                   # never duplicated
    prompt = fs.build_prompt(P, [seed, better], "schema", "# recap", None, None, pinned=seed)
    assert "# Version 0 (score 0.300000)" in prompt and "# Version 1 (score 0.270000)" in prompt and "def construct_v1(" in prompt
    assert "# Version 1" not in fs.build_prompt(P, [seed, better], "schema", "# recap", None, None, pinned=None)


def test_factorial_main_effect_pairs_cells_that_differ_in_one_factor():
    res = {arm: {11: {"final": i / 100}} for i, arm in enumerate(slot.FACTORIAL)}
    for name, idx, hi, lo in slot.FACTORS:
        e = slot.main_effect(res, [11], idx, hi, lo, "final")
        assert e["n"] == 4                       # four cell pairs per factor
    # a pure persistence effect: transient cells +0.02 above their persistent partners, nothing else
    res = {}
    for arm, lev in slot.FACTORIAL.items():
        res[arm] = {s: {"final": 0.35 + (0.02 if lev[2] == "transient" else 0.0)} for s in (11, 12)}
    p = slot.main_effect(res, [11, 12], 2, "transient", "persistent", "final"); f = slot.main_effect(res, [11, 12], 0, "code", "words", "final")
    assert p["n"] == 8 and abs(p["median"] - 0.02) < 1e-9 and p["pos"] == 8 and f["pos"] == 0 and f["neg"] == 0
