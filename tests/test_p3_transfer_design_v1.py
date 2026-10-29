"""Offline matrix integrity and closure references; no provider or Lean execution."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import pytest

from creative_machine.formal_routes import transfer_design_v1 as design

REPO = Path(__file__).resolve().parents[1]


def test_full_matrix_has_two_worlds_and_only_the_twenty_six_fixed_positions():
    cells = design.matrix()
    assert cells == design.matrix()
    assert len(cells) == len({c["cell_id"] for c in cells}) == 26
    assert [c["ordinal"] for c in cells] == list(range(1, 27))
    assert Counter(c["role"] for c in cells) == {"proposer": 6, "recipient": 20}
    assert Counter(c["bridge_kind"] for c in cells) == {None: 6, "none": 4, "oracle": 4, "candidate": 12}
    assert {c["world"] for c in cells} == set(design.WORLDS)
    assert all(c["phase"] == "production" for c in cells[:6])
    assert all(c["phase"] == "evaluation" for c in cells[6:])
    assert all(c["arm"] in design.ARMS and c["holdout"] is None for c in cells[:6])
    assert [c["phase_ordinal"] for c in cells[6:]] == list(range(1, 21))


def test_each_candidate_depends_on_its_parent_and_a_single_shared_baseline():
    cells = design.matrix()
    lookup = {c["cell_id"]: c for c in cells}
    for c in cells[6:]:
        b = lookup[c["baseline_cell_id"]]
        assert b["arm"] == "B" and b["world_id"] == c["world_id"] and b["holdout"] == c["holdout"]
        if c["bridge_kind"] == "candidate":
            p = lookup[c["parent_proposer_id"]]
            assert p["role"] == "proposer" and p["arm"] == c["arm"] and p["world_id"] == c["world_id"]
        else:
            assert c["parent_proposer_id"] is None
    assert set(Counter(c["baseline_cell_id"] for c in cells[6:]).values()) == {5}


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "id", "arm", "holdout", "world", "phase", "order", "parent", "baseline", "extra"])
def test_matrix_drift_is_never_silently_accepted(mutation):
    cells = design.matrix()
    if mutation == "drop": cells.pop()
    elif mutation == "duplicate": cells[1] = deepcopy(cells[0])
    elif mutation == "order": cells.reverse()
    elif mutation == "id": cells[0]["cell_id"] = "S16_OLD_CONTROL"
    elif mutation == "extra": cells[0]["posthoc"] = True
    else:
        key = {"world": "world_id", "parent": "parent_proposer_id", "baseline": "baseline_cell_id"}.get(mutation, mutation)
        cells[-1][key] = "changed"
    with pytest.raises(ValueError, match="drift"):
        design.validate_matrix(cells)


def test_blueprint_is_bound_to_closed_sources_but_is_not_admission():
    blueprint = design.build_blueprint(REPO)
    assert blueprint == design.build_blueprint(REPO)
    assert blueprint["status"] == "DRAFT_NOT_ADMITTED"
    assert not any(blueprint[k] for k in ("inference_admitted", "main_sample_admitted", "mechanistic_stage_admitted"))
    assert blueprint["max_sessions"] == 26 and blueprint["max_parallel"] == 2
    assert blueprint["agent"]["output_per_request"] == 16384 and blueprint["agent"]["effort"] == "high"
    assert blueprint["nominal_reservation_usd"] == 42.9 and blueprint["proposed_batch_cap_usd"] == 50
    assert len(blueprint["proposer_initial_inputs"]) == 6
    assert all(not w["eligible_for_main"] for w in blueprint["worlds"])
    old = json.loads((REPO / "docs/p3/response_limit_sensitivity_plan_v1.json").read_text())
    assert not {c["cell_id"] for c in old["cells"]} & {c["cell_id"] for c in blueprint["cells"]}


def test_upstream_evidence_is_bound_to_fixed_closed_manifest(monkeypatch):
    original = design._safe_bytes

    def changed(repository, rel):
        raw = original(repository, rel)
        return raw + b" " if rel == design.SOURCE_EVIDENCE_PATH + "/manifest.json" else raw

    monkeypatch.setattr(design, "_safe_bytes", changed)
    with pytest.raises(ValueError, match="provenance drift"):
        design.build_blueprint(REPO)


def test_blueprint_prepare_is_exclusive_and_validate_detects_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(design, "BLUEPRINT_PATH", "blueprint.json")
    monkeypatch.setattr(design, "build_blueprint", lambda _: {"draft": True})
    assert design.prepare(tmp_path) == design.load_blueprint(tmp_path) == {"draft": True}
    with pytest.raises(FileExistsError): design.prepare(tmp_path)
    monkeypatch.setattr(design, "build_blueprint", lambda _: {"draft": False})
    with pytest.raises(ValueError, match="drift"): design.load_blueprint(tmp_path)


def test_checked_in_blueprint_matches_the_current_recipe_and_dependencies():
    blueprint = design.load_blueprint(REPO)
    design.validate_design_rules(blueprint)
    assert blueprint["cells"] == design.matrix()
