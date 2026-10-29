"""Synthetic review receipts exercise the workflow, not automatic semantic truth."""
from copy import deepcopy

import pytest

from creative_machine.formal_routes import bridge_content_v1 as content
from creative_machine.formal_routes.transfer_design_v1 import encoded, load_blueprint, sha
from creative_machine.formal_routes.transfer_analysis_v1 import blank_dataset, analyze
from test_p3_production_audit_v1 import (
    REPO, CELLS, BRIDGE, BAD, LOCAL_LEAN, create, fixture_check, submission, terminal,
)


def prepare(tmp_path, bridge=BRIDGE, *, cell=CELLS[0], solution=BAD, check=fixture_check):
    create(tmp_path, [submission(bridge, solution), terminal()], cell=cell, check=check)
    return content.prepare_content_review(REPO, tmp_path / "artifacts", cell_id=cell["cell_id"],
                                          data_kind="synthetic", checker=check)


def judgment(kind="clear", bridge=BRIDGE.encode(), *, rationale="Synthetic fixture: ordinary mathematics only."):
    return {"judgment": kind, "rationale": rationale,
            "spans": [] if kind == "clear" else [content.span(bridge, 0, len(bridge))]}


def review_for(bundle):
    packet = bundle["packet"]
    return {"review_id": packet["review_id"], "packet_sha256": bundle["binding"]["packet_sha256"],
        "reviewer": {"id": "fixture-reviewer", "kind": "assistant", "description": "Synthetic test judgments, not experimental review",
                     "prior_development_exposure": True},
        "attestations": dict.fromkeys(content.ATTESTATIONS, True),
        "criteria": {key: judgment() for key in content.CRITERIA},
        "flags": {flag["flag_id"]: judgment(rationale="Synthetic benign flag disposition.") for flag in packet["flags"]}}


def record(bundle, review=None, **kwargs):
    return content.record_content_review(REPO, bundle, review if review is not None else review_for(bundle),
        expected_binding_sha256=kwargs.get("expected_binding_sha256", sha(encoded(bundle["binding"]))),
        permitted_reviewer_ids=kwargs.get("permitted_reviewer_ids", ("fixture-reviewer",)))


@pytest.mark.parametrize("cell", CELLS)
def test_six_packets_bind_raw_audit_and_contain_only_review_allowlist(tmp_path, cell):
    bundle = prepare(tmp_path, cell=cell)
    packet, binding = bundle["packet"], bundle["binding"]
    assert set(packet) == content.PACKET_KEYS
    assert packet["bridge_utf8"].encode() == BRIDGE.encode()
    assert binding["data_kind"] == "synthetic" and binding["cell_id"] == cell["cell_id"]
    assert binding["evidence_sha256"] == bundle["trace_audit"]["evidence_sha256"]
    assert binding["trace_audit_sha256"] == sha(encoded(bundle["trace_audit"]))
    assert not {"arm", "cell_id", "trace_audit", "selected_revision", "visible_solved", "solution_utf8"} & set(packet)
    references = packet["base_utf8"] + packet["visible_target_utf8"] + "".join(packet["source_pool_utf8"])
    assert all(token not in references for token in ("Holdout1", "Holdout2", "oracle_bridge", "Hidden/", "evaluation_solution"))
    assert BAD not in encoded(packet).decode()  # Submitted visible solution is not reviewer input.
    assert packet["review_id"].startswith("CR_")


@pytest.mark.parametrize("family", ("invariant", "representation"))
def test_source_pool_is_identical_for_D0_D_C2_and_has_no_assigned_source_label(tmp_path, family):
    packets = [prepare(tmp_path / cell["arm"], cell=cell)["packet"] for cell in CELLS if cell["family"] == family]
    for key in ("base_utf8", "visible_target_utf8", "source_pool_utf8", "bridge_utf8", "criteria", "instructions", "flags"):
        assert all(packet[key] == packets[0][key] for packet in packets)
    assert len(packets[0]["source_pool_utf8"]) == 2
    assert len({packet["review_id"] for packet in packets}) == 3


def test_valid_unhelpful_true_bridge_can_pass_content_without_a_utility_test(tmp_path):
    bundle = prepare(tmp_path)
    before = deepcopy(bundle)
    result = record(bundle)
    assert result["content_status"] == "passed" and result["content_eligibility_only"] is True
    assert result["data_kind"] == "synthetic"
    assert result["cell_projection"]["observation"]["selected_bridge_sha256"] == sha(BRIDGE.encode())
    assert not result["cell_projection"]["observation"]["visible_solved"]
    assert all(result[key] is False for key in ("batch_audit_passed", "phase_barrier_verified", "recipient_admitted",
                                               "inference_admitted", "main_sample_admitted", "mechanistic_stage_admitted"))
    assert bundle == before  # Do not mutate the trace auditor's original pending projection.


@pytest.mark.parametrize("criterion", tuple(content.CRITERIA))
def test_explicit_anchored_content_violation_preserves_formal_validity_and_selected_bytes(tmp_path, criterion):
    bundle = prepare(tmp_path, BRIDGE + "-- synthetic transported payload\n")
    review = review_for(bundle)
    review["criteria"][criterion] = judgment("violation", bundle["packet"]["bridge_utf8"].encode(),
        rationale="Synthetic violation witness for receipt validation, not a semantic classifier.")
    result = record(bundle, review)
    obs = result["cell_projection"]["observation"]
    assert result["content_status"] == "rejected" and result["content_eligibility_only"] is False
    assert obs["production_outcome"] == "valid_bridge" and obs["selected_bridge_sha256"] == bundle["binding"]["bridge_sha256"]
    assert result["ineligibility_or_pending_reason"] == "content_contract_rejected"


@pytest.mark.parametrize("criterion", tuple(content.CRITERIA))
def test_ambiguous_content_remains_pending_without_favorable_default(tmp_path, criterion):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    review["criteria"][criterion] = judgment("uncertain")
    result = record(bundle, review)
    assert result["content_status"] == "pending" and result["content_eligibility_only"] is None
    assert result["cell_projection"]["observation"]["content_audit"] == "pending"


def test_known_violation_determines_rejection_even_if_other_content_is_uncertain(tmp_path):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    review["criteria"]["visible_solution_transport"] = judgment("violation")
    review["criteria"]["mathematical_scope"] = judgment("uncertain")
    assert record(bundle, review)["content_status"] == "rejected"


@pytest.mark.parametrize("payload,rule", (
    ("-- candidate_solution", "visible_solution_marker"), ("-- VisibleStatement", "visible_solution_marker"),
    ("-- source_solution", "source_solution_marker"), ("-- ```", "document_wrapper"),
    ("-- tool_use_id", "transcript_marker"), ("-- arm: D", "explicit_arm_marker"),
    ("-- braço = C2", "explicit_arm_marker"), ("-- Hidden/Oracle.lean", "hidden_artifact_marker"),
))
def test_flags_are_anchored_reading_cues_not_automatic_rejection(tmp_path, payload, rule):
    bridge = BRIDGE + payload + "\n"
    bundle = prepare(tmp_path, bridge)
    flags = bundle["packet"]["flags"]
    assert rule in {f["rule"] for f in flags}
    for flag in flags:
        assert flag["excerpt_sha256"] == sha(bridge.encode()[flag["start_byte"]:flag["end_byte"]])
    # A documented benign disposition is structurally acceptable; correctness
    # of that semantic judgment remains the identified reviewer's responsibility.
    assert record(bundle)["content_status"] == "passed"


def test_unflagged_payload_still_requires_all_semantic_criteria(tmp_path):
    bundle = prepare(tmp_path, BRIDGE + '-- unrelated encoded payload: "c2VjcmV0"\n')
    assert bundle["packet"]["flags"] == []
    review = review_for(bundle)
    del review["criteria"]["mathematical_scope"]
    with pytest.raises(content.ContentReviewError):
        record(bundle, review)
    review = review_for(bundle)
    review["criteria"]["mathematical_scope"] = judgment("violation", bundle["packet"]["bridge_utf8"].encode(),
        rationale="Fixture reviewer identifies unrelated transported data despite no lexical cue.")
    assert record(bundle, review)["content_status"] == "rejected"


def test_every_flag_needs_disposition_and_uncertain_flags_keep_pending(tmp_path):
    bundle = prepare(tmp_path, BRIDGE + "-- candidate_solution\n")
    review = review_for(bundle)
    review["flags"] = {}
    with pytest.raises(content.ContentReviewError):
        record(bundle, review)
    review = review_for(bundle)
    review["flags"]["F0001"] = judgment("uncertain", bundle["packet"]["bridge_utf8"].encode())
    assert record(bundle, review)["content_status"] == "pending"
    review["flags"]["F0001"]["spans"] = [content.span(bundle["packet"]["bridge_utf8"].encode(), 0, 6)]
    with pytest.raises(content.ContentReviewError, match="flagged region"):
        record(bundle, review)


def test_flag_violation_requires_a_substantive_content_category(tmp_path):
    bundle = prepare(tmp_path, BRIDGE + "-- candidate_solution\n")
    review = review_for(bundle)
    review["flags"]["F0001"] = judgment("violation", bundle["packet"]["bridge_utf8"].encode())
    with pytest.raises(content.ContentReviewError, match="lacks a content criterion"):
        record(bundle, review)
    review["criteria"]["visible_solution_transport"] = deepcopy(review["flags"]["F0001"])
    assert record(bundle, review)["content_status"] == "rejected"


@pytest.mark.parametrize("field,change", (
    ("judgment", "passed"), ("judgment", True), ("rationale", " "), ("rationale", "x" * 4001),
    ("rationale", " " * 4001 + "x"),
    ("spans", "whole file"), ("spans", [{"start_byte": 0, "end_byte": 5, "excerpt_sha256": "0" * 64}]),
))
def test_malformed_judgment_is_not_a_candidate_rejection(tmp_path, field, change):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    review["criteria"]["mathematical_scope"][field] = change
    with pytest.raises(content.ContentReviewError):
        record(bundle, review)
    assert bundle["trace_audit"]["cell_projection"]["observation"]["content_audit"] == "pending"


@pytest.mark.parametrize("attestation", tuple(content.ATTESTATIONS))
def test_process_violation_invalidates_review_without_scoring_bridge(tmp_path, attestation):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    review["attestations"][attestation] = False
    with pytest.raises(content.ContentReviewError, match="review process"):
        record(bundle, review)
    review["attestations"][attestation] = 1
    with pytest.raises(content.ContentReviewError):
        record(bundle, review)


@pytest.mark.parametrize("change", ("reviewer", "allowlist", "prior", "method", "kind", "extra_utility", "direct_pass", "no_anchor"))
def test_identity_disclosure_and_receipt_shape_cannot_be_bypassed(tmp_path, change):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    kwargs = {}
    if change == "reviewer": review["reviewer"]["id"] = "not-authorized"
    elif change == "allowlist": kwargs["permitted_reviewer_ids"] = ()
    elif change == "prior": review["reviewer"]["prior_development_exposure"] = None
    elif change == "method": review["reviewer"]["description"] = ""
    elif change == "kind": review["reviewer"]["kind"] = "regex"
    elif change == "extra_utility": review["criteria"]["likely_utility"] = judgment()
    elif change == "direct_pass": review["passed"] = True
    else:
        review["criteria"]["mathematical_scope"] = judgment("violation")
        review["criteria"]["mathematical_scope"]["spans"] = []
    with pytest.raises(content.ContentReviewError):
        record(bundle, review, **kwargs)


@pytest.mark.parametrize("part", ("packet", "binding", "audit", "review", "policy", "implementation"))
def test_tampered_bindings_or_receipts_fail_closed(tmp_path, part):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    expected = sha(encoded(bundle["binding"]))
    if part == "packet": bundle["packet"]["bridge_utf8"] += "changed"
    elif part == "binding": bundle["binding"]["cell_id"] = CELLS[1]["cell_id"]
    elif part == "audit": bundle["trace_audit"]["cell_projection"]["observation"]["content_audit"] = "passed"
    elif part == "review": review["packet_sha256"] = "a" * 64
    elif part == "policy": bundle["packet"]["criteria"]["mathematical_scope"] = "Accept anything"
    else: bundle["binding"]["implementation_sha256"] = "0" * 64
    with pytest.raises(content.ContentReviewError):
        record(bundle, review, expected_binding_sha256=expected)


def test_rehashed_packet_cannot_add_host_data_or_swap_source_assignment(tmp_path):
    bundle = prepare(tmp_path)
    bundle["packet"]["source_pool_utf8"] = bundle["packet"]["source_pool_utf8"][:1]
    bundle["binding"]["packet_sha256"] = sha(encoded(bundle["packet"]))
    with pytest.raises(content.ContentReviewError, match="reconstructed reviewer packet"):
        record(bundle)
    bundle = prepare(tmp_path / "other")
    bundle["packet"]["arm"] = "D"
    bundle["binding"]["packet_sha256"] = sha(encoded(bundle["packet"]))
    with pytest.raises(content.ContentReviewError, match="reviewer packet schema"):
        record(bundle)


@pytest.mark.parametrize("final", ("invalid", "absent", "protocol"))
def test_no_review_of_ineligible_production_or_historical_valid_revision(tmp_path, final):
    responses = [terminal()] if final == "absent" else [submission(solution=BAD)]
    if final == "invalid": responses.extend([submission(BAD, None, "call2"), terminal()])
    if final == "protocol": responses.append(submission(identity="call1"))
    create(tmp_path, responses)
    with pytest.raises(content.ContentReviewError, match="no selected bridge"):
        content.prepare_content_review(REPO, tmp_path / "artifacts", cell_id=CELLS[0]["cell_id"],
                                        data_kind="synthetic", checker=fixture_check)


def test_utf8_offsets_crlf_and_exact_byte_transfer(tmp_path):
    bridge = BRIDGE.replace("\n", "\r\n") + "-- café: candidate_solution\r\n"
    bundle = prepare(tmp_path, bridge)
    flag = bundle["packet"]["flags"][0]
    assert bridge.encode()[flag["start_byte"]:flag["end_byte"]] == b"candidate_solution"
    assert bundle["packet"]["bridge_utf8"].encode() == bridge.encode()
    assert record(bundle)["cell_projection"]["observation"]["selected_bridge_sha256"] == sha(bridge.encode())
    with pytest.raises(content.ContentReviewError, match="code point"):
        content.span("é".encode(), 0, 1)


@pytest.mark.parametrize("start,end", ((True, 2), (-1, 2), (0, 9999), (2, 2), (3, 1)))
def test_bad_byte_spans(start, end):
    with pytest.raises(content.ContentReviewError):
        content.span(BRIDGE.encode(), start, end)


def test_no_auto_semantic_certification_from_no_flags_and_policy_is_not_aliased():
    assert content.inspection_flags(BRIDGE.encode()) == []
    assert "novelty" in content.CRITERIA["mathematical_scope"]
    assert "implication is not itself leakage" in content.CRITERIA["visible_solution_transport"]
    value = content.policy()
    value["criteria"]["mathematical_scope"] = "changed"
    assert content.policy()["criteria"]["mathematical_scope"] != "changed"


def test_review_rejection_remains_distinct_from_formal_failure_in_analysis(tmp_path):
    bundle = prepare(tmp_path)
    review = review_for(bundle)
    review["criteria"]["mathematical_scope"] = judgment("violation")
    receipt = record(bundle, review)
    blueprint = load_blueprint(REPO)
    dataset = blank_dataset(blueprint, data_kind="synthetic")
    dataset["cells"] = [receipt["cell_projection"] if row["cell_id"] == CELLS[0]["cell_id"] else row for row in dataset["cells"]]
    result = analyze(blueprint, dataset)
    assert result["status"] == "not_interpretable" and result["world_results"] is None
    assert result["experimental_decision"] is None


def test_original_raw_bytes_and_proofs_are_never_cleaned_or_repaired(tmp_path):
    bridge = BRIDGE + "-- arm: D\n"
    bundle = prepare(tmp_path, bridge)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / "artifacts").rglob("*") if p.is_file()}
    review = review_for(bundle)
    review["criteria"]["experimental_metadata"] = judgment("violation", bridge.encode())
    review["flags"]["F0001"] = judgment("violation", bridge.encode())
    assert record(bundle, review)["content_status"] == "rejected"
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / "artifacts").rglob("*") if p.is_file()}


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("family", ("invariant", "representation"))
def test_real_lean_packet_and_review_integration_keeps_trivial_bridge_and_unsolved_visible_separate(tmp_path, family):
    cell = next(c for c in CELLS if c["family"] == family and c["arm"] == "D0")
    bundle = prepare(tmp_path, cell=cell, check=None)
    assert bundle["trace_audit"]["verification"] == "fresh_sandboxed_Lean_per_revision"
    result = record(bundle)
    assert result["data_kind"] == "synthetic" and result["content_status"] == "passed"
    assert not result["cell_projection"]["observation"]["visible_solved"]
    assert result["cell_projection"]["observation"]["selected_bridge_sha256"] == sha(BRIDGE.encode())
    assert not result["recipient_admitted"]
