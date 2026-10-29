"""Synthetic audit projections, never experimental agents, evidence or conclusions."""
from copy import deepcopy
import itertools
from pathlib import Path

import pytest

from creative_machine.formal_routes import transfer_analysis_v1 as analysis
from creative_machine.formal_routes import transfer_design_v1 as design

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def blueprint():
    return design.build_blueprint(REPO)


def hashed(label):
    return design.sha(("synthetic fixture: " + label).encode())


def dataset(blueprint):
    """All bridges valid but unhelpful, B=0/4, O=4/4, all rows audited synthetically."""
    data = analysis.blank_dataset(blueprint, data_kind="synthetic")
    data["batch_audit"] = {"status": "passed", "report_sha256": hashed("batch audit"),
                           "execution_plan_sha256": hashed("separate frozen execution plan"),
                           "phase_barrier_verified": True, "accounting": "complete"}
    selected = {c["cell_id"]: hashed("final bridge " + c["cell_id"]) for c in blueprint["cells"][:6]}
    for c, row in zip(blueprint["cells"], data["cells"]):
        row.update(state="completed", trace_audit="passed", accounting="complete", evidence_sha256=hashed(c["cell_id"]))
        if c["role"] == "proposer":
            row["observation"] = {"production_outcome": "valid_bridge", "termination": "model_stopped",
                "revisions": 1, "last_bridge_status": "valid", "earlier_valid_bridge": False,
                "visible_solved": False, "selected_bridge_sha256": selected[c["cell_id"]],
                "content_audit": "passed", "selection_policy": analysis.SELECTION_POLICY}
        else:
            bridge = None
            if c["bridge_kind"] == "candidate": bridge = selected[c["parent_proposer_id"]]
            if c["bridge_kind"] == "oracle":
                bridge = next(w["oracle_bridge_sha256"] for w in blueprint["worlds"] if w["world_id"] == c["world_id"])
            row["observation"] = {"outcome": "verified" if c["arm"] == "O" else "not_solved",
                                  "target_solved": c["arm"] == "O", "bridge_sha256": bridge}
    return data


def row_for(blueprint, data, *, family="representation", arm="D", holdout=None):
    cell = next(c for c in blueprint["cells"] if c["family"] == family and c["arm"] == arm and c["holdout"] == holdout)
    return next(r for r in data["cells"] if r["cell_id"] == cell["cell_id"])


def solve(blueprint, data, *, family="representation", arm="D", holdout=1, value=True):
    obs = row_for(blueprint, data, family=family, arm=arm, holdout=holdout)["observation"]
    obs.update(target_solved=value, outcome="verified" if value else "not_solved")


def reject_production(blueprint, data, *, family="representation", arm="D", outcome="invalid_bridge"):
    parent = row_for(blueprint, data, family=family, arm=arm)
    obs = parent["observation"]
    obs.update(production_outcome=outcome, selected_bridge_sha256=None, content_audit="not_applicable",
               last_bridge_status="rejected", visible_solved=False)
    if outcome == "no_complete_submission": obs.update(revisions=0, last_bridge_status="not_submitted")
    if outcome == "invalid_protocol_output": obs["termination"] = "invalid_output"
    for h in (1, 2):
        row = row_for(blueprint, data, family=family, arm=arm, holdout=h)
        row.update(state="skipped_no_bridge", trace_audit="not_applicable", accounting="not_applicable",
                   evidence_sha256=None, observation=None)


def scored(result, family="representation", arm="D"):
    return next(w for w in result["world_results"] if w["family"] == family)["arms"][arm]


def test_blank_inventory_exposes_no_partial_scientific_results(blueprint):
    result = analysis.analyze(blueprint, analysis.blank_dataset(blueprint, data_kind="synthetic"))
    assert result["status"] == "not_interpretable" and result["slot_states"] == {"not_started": 26}
    assert result["world_results"] is result["control_gate"] is result["contrasts"] is None
    assert result["experimental_decision"] is None and not result["inference_admitted"]


def test_valid_unhelpful_bridge_is_measured_zero_not_production_failure(blueprint):
    result = analysis.analyze(blueprint, dataset(blueprint))
    cell = scored(result)
    assert cell["U"] == 0 and cell["utility_measured"] is True
    assert cell["with_bridge"] == [0, 0] and cell["per_sibling_gain"] == [0, 0]
    assert cell["utility_kind"] == "measured"
    assert result["decision_rule"] == "no_positive_transfer_close_diagnostic_review_all_failures"


@pytest.mark.parametrize("outcome", ["invalid_bridge", "no_complete_submission", "invalid_protocol_output"])
def test_production_failure_preserves_empty_recipient_slots_and_conventional_zero(blueprint, outcome):
    data = dataset(blueprint)
    reject_production(blueprint, data, outcome=outcome)
    result = analysis.analyze(blueprint, data)
    cell = scored(result)
    assert result["status"] == "complete" and result["slot_states"] == {"completed": 24, "skipped_no_bridge": 2}
    assert cell["U"] == 0 and cell["utility_measured"] is False
    assert cell["with_bridge"] is cell["per_sibling_gain"] is None
    assert cell["ineligibility_reason"] == outcome and cell["utility_kind"] == "conventional_zero_production_failure"


def test_all_six_proposers_can_fail_without_dropping_any_world_arm_or_control(blueprint):
    data = dataset(blueprint)
    for family, arm in itertools.product(("invariant", "representation"), design.ARMS):
        reject_production(blueprint, data, family=family, arm=arm, outcome="no_complete_submission")
    result = analysis.analyze(blueprint, data)
    assert result["slot_states"] == {"completed": 14, "skipped_no_bridge": 12}
    assert result["control_gate"]["passed"] and len(result["world_results"]) == 2
    assert all(len(w["arms"]) == 3 for w in result["world_results"])
    assert result["positive_transfer_cells"] == []


@pytest.mark.parametrize("arm", ["D0", "D", "C2"])
def test_any_arm_can_supply_positive_transfer_without_visible_solution(blueprint, arm):
    data = dataset(blueprint)
    solve(blueprint, data, arm=arm)
    result = analysis.analyze(blueprint, data)
    assert result["control_gate"]["passed"]
    assert result["decision_rule"] == "positive_transfer_prepare_independent_study_not_admission"
    cell = scored(result, arm=arm)
    assert cell["U"] == 0.5 and cell["helped_without_visible_solution"]
    assert not cell["visible_solved"] and cell["utility_measured"]
    assert result["experimental_decision"] is None and result["synthetic_decision_only"]
    assert not result["H2_confirmed"] and not result["mechanistic_stage_admitted"]


def test_negative_utilities_and_family_ceiling_are_preserved(blueprint):
    data = dataset(blueprint)
    for h in (1, 2): solve(blueprint, data, family="invariant", arm="B", holdout=h)
    result = analysis.analyze(blueprint, data)
    assert result["control_gate"]["passed"]
    for arm in design.ARMS:
        cell = scored(result, family="invariant", arm=arm)
        assert cell["U"] == -1 and cell["per_sibling_gain"] == [-1, -1] and cell["utility_measured"]
    assert next(w for w in result["world_results"] if w["family"] == "invariant")["baseline_at_ceiling"]


def test_per_sibling_gains_reveal_a_gain_and_a_loss_that_cancel(blueprint):
    data = dataset(blueprint)
    solve(blueprint, data, arm="B", holdout=1)
    solve(blueprint, data, holdout=2)
    cell = scored(analysis.analyze(blueprint, data))
    assert cell["U"] == 0 and cell["per_sibling_gain"] == [-1, 1]


def test_contrasts_can_favor_c2_and_d0_and_reuse_exact_baseline_ids(blueprint):
    data = dataset(blueprint)
    solve(blueprint, data, arm="C2")
    for h in (1, 2): solve(blueprint, data, arm="D0", holdout=h)
    result = analysis.analyze(blueprint, data)
    contrast = next(c for c in result["contrasts"] if c["world_id"].startswith("CAL3_R"))
    assert contrast["D_minus_C2"] == -0.5 and contrast["D_minus_D0"] == -1
    assert len({i for w in result["world_results"] for i in w["baseline_cell_ids"]}) == 4
    assert result["world_units"] == 2 and "p_value" not in result


def test_complete_control_truth_table_uses_all_three_requirements(blueprint):
    for bits in itertools.product((False, True), repeat=8):
        data = dataset(blueprint)
        coords = list(itertools.product(("invariant", "representation"), (1, 2)))
        for arm, values in (("B", bits[:4]), ("O", bits[4:])):
            for (family, h), value in zip(coords, values):
                solve(blueprint, data, family=family, arm=arm, holdout=h, value=value)
        result = analysis.analyze(blueprint, data)
        b, o = sum(bits[:4]), sum(bits[4:])
        expected = o >= 3 and b <= 2 and o - b >= 2
        gate = result["control_gate"]
        assert gate["passed"] is expected and gate["complete_pairs"] == 4
        assert (gate["baseline_successes"], gate["oracle_successes"], gate["net_gain"]) == (b, o, o - b)
        assert ("oracle_below_threshold" in gate["failed_requirements"]) == (o < 3)
        assert ("baseline_ceiling_insufficient_headroom" in gate["failed_requirements"]) == (b > 2)
        assert ("oracle_net_gain_below_threshold" in gate["failed_requirements"]) == (o - b < 2)


def test_positive_candidate_cannot_rescue_inadequate_controls(blueprint):
    data = dataset(blueprint)
    for family, h in (("invariant", 1), ("invariant", 2), ("representation", 1)):
        solve(blueprint, data, family=family, arm="B", holdout=h)
    for h in (1, 2): solve(blueprint, data, holdout=h)
    result = analysis.analyze(blueprint, data)
    assert result["positive_transfer_cells"] and not result["control_gate"]["passed"]
    assert result["decision_rule"] == "controls_inadequate_review_instrument"
    assert not result["hypothesis_interpretation_allowed"]


@pytest.mark.parametrize("failure", ["technical", "not_started", "cell_audit_pending", "cell_audit_failed", "cell_accounting",
                                      "batch_audit_pending", "batch_audit_failed", "batch_accounting", "phase_barrier"])
def test_technical_incomplete_and_unaudited_data_never_receive_scientific_scores(blueprint, failure):
    data = dataset(blueprint)
    row = row_for(blueprint, data, holdout=1)
    if failure in {"technical", "not_started"}:
        row.update(state="technical_failure" if failure == "technical" else "not_started",
                   observation=None, evidence_sha256=None, trace_audit="pending", accounting="pending")
    elif failure.startswith("cell_audit"): row["trace_audit"] = failure.rsplit("_", 1)[-1]
    elif failure == "cell_accounting": row["accounting"] = "pending"
    elif failure.startswith("batch_audit"): data["batch_audit"]["status"] = failure.rsplit("_", 1)[-1]
    elif failure == "batch_accounting": data["batch_audit"]["accounting"] = "pending"
    else: data["batch_audit"]["phase_barrier_verified"] = False
    result = analysis.analyze(blueprint, data)
    assert result["status"] == "not_interpretable" and result["blocking_reasons"]
    assert result["world_results"] is result["contrasts"] is result["control_gate"] is None
    assert result["experimental_decision"] is None


def test_content_audit_pending_is_not_an_exclusion_or_zero(blueprint):
    data = dataset(blueprint)
    row_for(blueprint, data)["observation"]["content_audit"] = "pending"
    for h in (1, 2):
        row_for(blueprint, data, holdout=h).update(state="not_started", observation=None, evidence_sha256=None,
                                                  trace_audit="pending", accounting="pending")
    result = analysis.analyze(blueprint, data)
    assert result["status"] == "not_interpretable" and result["world_results"] is None
    assert any("content_audit_pending" in reason for reason in result["blocking_reasons"])


def test_content_rejection_preserves_formal_validity_but_never_repairs_the_bridge(blueprint):
    data = dataset(blueprint)
    selected = row_for(blueprint, data)["observation"]["selected_bridge_sha256"]
    row_for(blueprint, data)["observation"]["content_audit"] = "rejected"
    for h in (1, 2):
        row_for(blueprint, data, holdout=h).update(state="skipped_no_bridge", observation=None, evidence_sha256=None,
                                                  trace_audit="not_applicable", accounting="not_applicable")
    cell = scored(analysis.analyze(blueprint, data))
    assert cell["formal_bridge_valid"] and not cell["transfer_eligible"] and not cell["utility_measured"]
    assert cell["selected_bridge_sha256"] == selected and cell["ineligibility_reason"] == "content_contract_rejected"


def test_lost_valid_revision_is_distinguished_from_protocol_suppression(blueprint):
    data = dataset(blueprint)
    reject_production(blueprint, data)
    row_for(blueprint, data)["observation"].update(revisions=2, earlier_valid_bridge=True)
    cell = scored(analysis.analyze(blueprint, data))
    assert cell["prior_valid_revision_lost"] and not cell["valid_bridge_suppressed_by_protocol"]
    data = dataset(blueprint)
    reject_production(blueprint, data, outcome="invalid_protocol_output")
    row_for(blueprint, data)["observation"]["last_bridge_status"] = "valid"
    cell = scored(analysis.analyze(blueprint, data))
    assert cell["valid_bridge_suppressed_by_protocol"] and not cell["prior_valid_revision_lost"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "historical", "arm_label", "extra_field", "blueprint_hash", "schema_version",
    "model", "gate", "wrong_bridge", "oracle_bridge", "baseline_bridge", "solved_type", "solved_outcome",
    "technical_score", "invalid_protocol_selected", "best_revision", "earlier_without_revision", "missing_audit_hash",
    "unstarted_audited", "content_not_applicable", "too_many_revisions"])
def test_invalid_or_relabelled_observations_are_rejected_not_rescored(blueprint, mutation):
    data, bp = dataset(blueprint), deepcopy(blueprint)
    parent = row_for(blueprint, data)["observation"]
    target = row_for(blueprint, data, holdout=1)
    if mutation == "missing": data["cells"].pop()
    elif mutation == "duplicate": data["cells"][1] = deepcopy(data["cells"][0])
    elif mutation == "historical": target["cell_id"] = "S16_OLD_CONTROL"
    elif mutation == "arm_label": target["arm"] = "D"
    elif mutation == "extra_field": data["posthoc"] = True
    elif mutation == "blueprint_hash": data["blueprint_sha256"] = hashed("wrong blueprint")
    elif mutation == "schema_version": data["schema_version"] = True
    elif mutation == "model": bp["agent"]["model"] = "smaller-model"
    elif mutation == "gate": bp["contemporary_control_gate"]["baseline_at_most"] = 4
    elif mutation == "wrong_bridge": target["observation"]["bridge_sha256"] = hashed("earlier revision")
    elif mutation == "oracle_bridge": row_for(blueprint, data, arm="O", holdout=1)["observation"]["bridge_sha256"] = hashed("replacement oracle")
    elif mutation == "baseline_bridge": row_for(blueprint, data, arm="B", holdout=1)["observation"]["bridge_sha256"] = hashed("leak")
    elif mutation == "solved_type": target["observation"]["target_solved"] = 0
    elif mutation == "solved_outcome": target["observation"]["outcome"] = "verified"
    elif mutation == "technical_score": target["state"] = "technical_failure"
    elif mutation == "invalid_protocol_selected": parent.update(production_outcome="invalid_protocol_output", termination="invalid_output")
    elif mutation == "best_revision": parent["selection_policy"] = "best_historical_bridge"
    elif mutation == "earlier_without_revision": parent["earlier_valid_bridge"] = True
    elif mutation == "missing_audit_hash": data["batch_audit"]["report_sha256"] = None
    elif mutation == "unstarted_audited": target.update(state="not_started", observation=None)
    elif mutation == "content_not_applicable": parent["content_audit"] = "not_applicable"
    elif mutation == "too_many_revisions": parent["revisions"] = 13
    with pytest.raises(ValueError): analysis.analyze(bp, data)


def test_eligible_recipient_cannot_be_selectively_skipped(blueprint):
    data = dataset(blueprint)
    row_for(blueprint, data, holdout=1).update(state="skipped_no_bridge", observation=None, evidence_sha256=None,
                                             trace_audit="not_applicable", accounting="not_applicable")
    with pytest.raises(ValueError, match="selectively omitted"): analysis.analyze(blueprint, data)


def test_ineligible_or_pending_bridge_cannot_have_a_recipient(blueprint):
    for status in ("rejected", "pending"):
        data = dataset(blueprint)
        row_for(blueprint, data)["observation"]["content_audit"] = status
        with pytest.raises(ValueError): analysis.analyze(blueprint, data)


def test_controls_cannot_be_skipped_and_skips_cannot_invent_evidence(blueprint):
    data = dataset(blueprint)
    row_for(blueprint, data, arm="B", holdout=1).update(state="skipped_no_bridge", observation=None, evidence_sha256=None,
                                                       trace_audit="not_applicable", accounting="not_applicable")
    with pytest.raises(ValueError, match="only a candidate"): analysis.analyze(blueprint, data)
    data = dataset(blueprint)
    reject_production(blueprint, data)
    row_for(blueprint, data, holdout=1)["evidence_sha256"] = hashed("invented skipped session")
    with pytest.raises(ValueError, match="invented"): analysis.analyze(blueprint, data)


def test_input_permutation_does_not_change_scoring_or_mutate_data(blueprint):
    data = dataset(blueprint)
    original = deepcopy(data)
    result = analysis.analyze(blueprint, data)
    assert data == original
    data["cells"].reverse()
    reordered = analysis.analyze(blueprint, data)
    for key in ("world_results", "control_gate", "contrasts", "decision_rule"):
        assert result[key] == reordered[key]


def test_experimental_label_does_not_make_analysis_an_admission_capability(blueprint):
    # Exercise the projection-label branch using a synthetic fixture, no real run.
    data = dataset(blueprint)
    solve(blueprint, data)
    data["data_kind"] = "experimental"
    result = analysis.analyze(blueprint, data)
    assert result["experimental_decision"] == result["decision_rule"]
    assert result["evidence_verification"] == "auditor_projection_contract_only_not_raw_trace_reaudit"
    assert not result["inference_admitted"] and not result["main_sample_admitted"] and not result["mechanistic_stage_admitted"]


@pytest.mark.parametrize("mutation", ["model", "budget", "concurrency", "gate", "world", "eligibility", "source_reference"])
def test_direct_analysis_rejects_policy_drift_even_after_rehashing_dataset(blueprint, mutation):
    data, bp = dataset(blueprint), deepcopy(blueprint)
    if mutation == "model": bp["agent"]["model"] = "smaller-model"
    elif mutation == "budget": bp["proposed_batch_cap_usd"] = 500
    elif mutation == "concurrency": bp["max_parallel"] = 4
    elif mutation == "gate": bp["contemporary_control_gate"]["oracle_at_least"] = 1
    elif mutation == "world": bp["worlds"].reverse()
    elif mutation == "eligibility": bp["worlds"][0]["eligible_for_main"] = True
    else: bp["source_matching"]["plan_sha256"] = hashed("posthoc count")
    data["blueprint_sha256"] = design.sha(design.encoded(bp))
    with pytest.raises(ValueError): analysis.analyze(bp, data)


def test_audit_claim_needs_execution_plan_and_cannot_reuse_evidence(blueprint):
    data = dataset(blueprint)
    data["batch_audit"]["execution_plan_sha256"] = None
    with pytest.raises(ValueError, match="separate frozen execution plan"): analysis.analyze(blueprint, data)
    data = dataset(blueprint)
    data["cells"][1]["evidence_sha256"] = data["cells"][0]["evidence_sha256"]
    with pytest.raises(ValueError, match="reuse"): analysis.analyze(blueprint, data)
