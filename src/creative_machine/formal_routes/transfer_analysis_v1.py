"""Pure, descriptive scoring of audited projections for the development matrix.

This is NOT the independent trace auditor, an evidence authenticity check or an
admission capability. The future batch auditor must construct these projections
from frozen raw traces. Synthetic datasets can exercise every decision without
being labelled as experimental evidence or advancing research automatically.
"""
from __future__ import annotations

from collections import Counter
import re

from .production_runner_v1 import NORMAL_TERMINATIONS, SELECTION_POLICY
from .transfer_design_v1 import ARMS, DESIGN_ID, GATE, WORLDS, encoded, sha, validate_design_rules

VERSION = "p3_transfer_analysis_v1"
CELL_KEYS = {"cell_id", "state", "trace_audit", "accounting", "evidence_sha256", "observation"}
PRODUCTION_KEYS = {"production_outcome", "termination", "revisions", "last_bridge_status",
                   "earlier_valid_bridge", "visible_solved", "selected_bridge_sha256", "content_audit",
                   "selection_policy"}
RECIPIENT_KEYS = {"outcome", "target_solved", "bridge_sha256"}
NO_BRIDGE = {"invalid_bridge", "no_complete_submission", "invalid_protocol_output"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _keys(value, keys, label):
    _require(isinstance(value, dict) and set(value) == set(keys), "invalid " + label + " schema")


def _proposer(obs: dict) -> None:
    _keys(obs, PRODUCTION_KEYS, "production observation")
    _require(obs["selection_policy"] == SELECTION_POLICY, "wrong chronological selection policy")
    outcome, last, revisions = obs["production_outcome"], obs["last_bridge_status"], obs["revisions"]
    _require(outcome in NO_BRIDGE | {"valid_bridge"}, "unknown production outcome")
    _require(last in {"valid", "rejected", "missing", "not_submitted"}, "invalid last bridge status")
    _require(type(revisions) is int and 0 <= revisions <= 12, "invalid revision count")
    _require(type(obs["visible_solved"]) is bool and type(obs["earlier_valid_bridge"]) is bool,
             "production booleans must be explicit")
    _require(not obs["earlier_valid_bridge"] or revisions >= 2, "earlier bridge without an earlier revision")
    _require((last == "not_submitted") == (revisions == 0), "last bridge and revision count disagree")
    if outcome == "invalid_protocol_output":
        _require(obs["termination"] == "invalid_output" and not obs["visible_solved"], "invalid protocol termination")
    else:
        _require(obs["termination"] in NORMAL_TERMINATIONS, "unknown or technical production termination")
        _require((outcome == "no_complete_submission") == (revisions == 0), "submission and production outcome disagree")
        _require((outcome == "valid_bridge") == (last == "valid"), "formal bridge and outcome disagree")
    if outcome == "valid_bridge":
        _require(_hash(obs["selected_bridge_sha256"]), "valid final bridge needs its selected bytes hash")
        _require(obs["content_audit"] in {"passed", "rejected", "pending"}, "content audit is required")
    else:
        _require(obs["selected_bridge_sha256"] is None and obs["content_audit"] == "not_applicable",
                 "ineligible production cannot select a historical bridge")
    _require(not obs["visible_solved"] or outcome == "valid_bridge", "visible solution requires a valid final bridge")
    _require((obs["termination"] == "both_verified") == obs["visible_solved"], "visible success must end the session")


def transfer_eligibility(obs: dict) -> tuple[bool | None, str | None]:
    """No sibling input, utility, earlier revision or similarity-based selection."""
    _proposer(obs)
    if obs["production_outcome"] in NO_BRIDGE:
        return False, obs["production_outcome"]
    if obs["content_audit"] == "pending":
        return None, "content_audit_pending"
    if obs["content_audit"] == "rejected":
        return False, "content_contract_rejected"
    return True, None


def blank_dataset(blueprint: dict, *, data_kind: str) -> dict:
    _require(data_kind in {"synthetic", "experimental"}, "data kind is required")
    validate_design_rules(blueprint)
    return {"schema_version": 1, "analysis_version": VERSION, "design_id": DESIGN_ID,
        "blueprint_sha256": sha(encoded(blueprint)), "data_kind": data_kind,
        "batch_audit": {"status": "pending", "report_sha256": None, "execution_plan_sha256": None,
                        "phase_barrier_verified": False, "accounting": "pending"},
        "cells": [{"cell_id": c["cell_id"], "state": "not_started", "trace_audit": "pending",
                   "accounting": "pending", "evidence_sha256": None, "observation": None}
                  for c in blueprint["cells"]]}


def _validate(blueprint: dict, dataset: dict) -> tuple[dict, list[str]]:
    validate_design_rules(blueprint)
    _keys(dataset, {"schema_version", "analysis_version", "design_id", "blueprint_sha256",
                    "data_kind", "batch_audit", "cells"}, "dataset")
    _require(type(dataset["schema_version"]) is int and dataset["schema_version"] == 1
             and dataset["analysis_version"] == VERSION and dataset["design_id"] == DESIGN_ID,
             "incompatible analysis dataset")
    _require(dataset["blueprint_sha256"] == sha(encoded(blueprint)), "observation/design hash mismatch")
    _require(dataset["data_kind"] in {"synthetic", "experimental"}, "unknown evidence kind")
    batch = dataset["batch_audit"]
    _keys(batch, {"status", "report_sha256", "execution_plan_sha256", "phase_barrier_verified", "accounting"}, "batch audit")
    _require(batch["status"] in {"passed", "pending", "failed"} and batch["accounting"] in {"complete", "pending"},
             "invalid batch audit or accounting status")
    _require(type(batch["phase_barrier_verified"]) is bool, "phase barrier must be explicit")
    _require(batch["report_sha256"] is None or _hash(batch["report_sha256"]), "invalid batch audit hash")
    _require(batch["execution_plan_sha256"] is None or _hash(batch["execution_plan_sha256"]), "invalid execution plan hash")
    _require(batch["status"] != "passed" or _hash(batch["report_sha256"]), "passed audit needs a report hash")
    _require(batch["status"] != "passed" or _hash(batch["execution_plan_sha256"]), "passed audit needs the separate frozen execution plan")
    reasons = []
    if batch["status"] != "passed": reasons.append("batch_audit_" + batch["status"])
    if not batch["phase_barrier_verified"]: reasons.append("proposer_recipient_phase_barrier_unverified")
    if batch["accounting"] != "complete": reasons.append("batch_accounting_pending")
    _require(isinstance(dataset["cells"], list), "cells must be a list")
    indexed = {}
    expected = {c["cell_id"]: c for c in blueprint["cells"]}
    for row in dataset["cells"]:
        _keys(row, CELL_KEYS, "cell")
        identity = row["cell_id"]
        _require(isinstance(identity, str) and identity in expected and identity not in indexed,
                 "unknown or duplicate cell; historical or relabelled results are not controls")
        indexed[identity] = row
        cell = expected[identity]
        _require(row["state"] in {"not_started", "completed", "skipped_no_bridge", "technical_failure"}, "invalid cell state")
        _require(row["trace_audit"] in {"passed", "pending", "failed", "not_applicable"}, "invalid trace audit state")
        _require(row["accounting"] in {"complete", "pending", "not_applicable"}, "invalid cell accounting state")
        _require(row["evidence_sha256"] is None or _hash(row["evidence_sha256"]), "invalid cell evidence hash")
        if row["state"] == "skipped_no_bridge":
            _require(cell["bridge_kind"] == "candidate", "only a candidate recipient can be skipped")
            _require(row["trace_audit"] == row["accounting"] == "not_applicable"
                     and row["observation"] is None and row["evidence_sha256"] is None,
                     "a skipped recipient cannot have a session or invented response")
            continue
        _require(row["trace_audit"] != "not_applicable" and row["accounting"] != "not_applicable",
                 "applicable cell cannot omit audit/accounting")
        if row["state"] != "completed":
            _require(row["observation"] is None, "uncompleted/technical session cannot provide a scientific score")
            if row["state"] == "not_started":
                _require(row["evidence_sha256"] is None and row["trace_audit"] == row["accounting"] == "pending",
                         "unstarted slot cannot claim session evidence or completed audit")
            reasons.append(f"{identity}:{row['state']}")
            continue
        _require(_hash(row["evidence_sha256"]), "completed session needs an evidence hash")
        if row["trace_audit"] != "passed": reasons.append(f"{identity}:trace_{row['trace_audit']}")
        if row["accounting"] != "complete": reasons.append(f"{identity}:accounting_pending")
        obs = row["observation"]
        if cell["role"] == "proposer":
            _proposer(obs)
            if transfer_eligibility(obs)[0] is None: reasons.append(f"{identity}:content_audit_pending")
        else:
            _keys(obs, RECIPIENT_KEYS, "recipient observation")
            _require(type(obs["target_solved"]) is bool, "recipient success must be boolean")
            _require(obs["outcome"] in {"verified", "not_solved", "invalid_protocol_output"}, "invalid recipient outcome")
            _require(obs["target_solved"] == (obs["outcome"] == "verified"), "recipient outcome disagrees with proof verification")
            if cell["bridge_kind"] == "none":
                _require(obs["bridge_sha256"] is None, "baseline cannot receive a bridge")
            else:
                _require(_hash(obs["bridge_sha256"]), "treated recipient needs exact bridge hash")
                if cell["bridge_kind"] == "oracle":
                    world = next(w for w in blueprint["worlds"] if w["world_id"] == cell["world_id"])
                    _require(obs["bridge_sha256"] == world["oracle_bridge_sha256"], "contemporary oracle bridge mismatch")
    _require(set(indexed) == set(expected), "all 26 slots must remain in the inventory, including unstarted/skipped")
    evidence = [r["evidence_sha256"] for r in indexed.values() if r["evidence_sha256"] is not None]
    _require(len(evidence) == len(set(evidence)), "different sessions cannot reuse one full evidence manifest")
    for cell in blueprint["cells"]:
        if cell["bridge_kind"] != "candidate": continue
        row, parent = indexed[cell["cell_id"]], indexed[cell["parent_proposer_id"]]
        eligible, reason = transfer_eligibility(parent["observation"]) if parent["state"] == "completed" else (None, "parent_incomplete")
        if eligible is True:
            _require(row["state"] != "skipped_no_bridge", "eligible bridge cannot be selectively omitted")
            if row["state"] == "completed":
                _require(row["observation"]["bridge_sha256"] == parent["observation"]["selected_bridge_sha256"],
                         "recipient used different bytes or an earlier bridge")
        elif eligible is False:
            _require(row["state"] in {"skipped_no_bridge", "not_started"}, "ineligible bridge cannot be tested")
            if row["state"] != "skipped_no_bridge": reasons.append(f"{cell['cell_id']}:skip_not_recorded:{reason}")
        else:
            _require(row["state"] == "not_started", "recipient cannot start or be excluded before the parent audit")
    return indexed, sorted(set(reasons))


def analyze(blueprint: dict, dataset: dict) -> dict:
    """Only full, audited inventories expose scientific aggregates; never impute failure."""
    indexed, reasons = _validate(blueprint, dataset)
    base = {"analysis_version": VERSION, "design_id": DESIGN_ID, "data_kind": dataset["data_kind"],
            "blueprint_sha256": dataset["blueprint_sha256"], "dataset_sha256": sha(encoded(dataset)),
            "slot_states": dict(sorted(Counter(r["state"] for r in indexed.values()).items())),
            "evidence_verification": "auditor_projection_contract_only_not_raw_trace_reaudit",
            "inference_admitted": False, "main_sample_admitted": False, "mechanistic_stage_admitted": False,
            "H2_confirmed": False, "world_units": 2,
            "interpretation": "descriptive development diagnostic; shared baselines and dependent siblings"}
    if reasons:
        return {**base, "status": "not_interpretable", "blocking_reasons": reasons,
                "decision_rule": "incomplete_review_infrastructure_or_audit", "experimental_decision": None,
                "world_results": None, "control_gate": None, "contrasts": None}
    cells = blueprint["cells"]
    lookup = {(c["world_id"], c["arm"], c["holdout"]): c for c in cells}

    def result(world, arm, holdout):
        return indexed[lookup[world, arm, holdout]["cell_id"]]["observation"]

    def outcomes(world, arm):
        return [int(result(world, arm, holdout)["target_solved"]) for holdout in (1, 2)]

    world_results, contrasts, positive = [], [], []
    for world_path in WORLDS:
        world = world_path.rsplit("/", 1)[-1]
        family = lookup[world, "D0", None]["family"]
        baseline, oracle = outcomes(world, "B"), outcomes(world, "O")
        oracle_u = (sum(oracle) - sum(baseline)) / 2
        arms = {}
        for arm in ARMS:
            obs = result(world, arm, None)
            eligible, reason = transfer_eligibility(obs)
            treated = outcomes(world, arm) if eligible else None
            per_sibling = [t - b for t, b in zip(treated, baseline)] if eligible else None
            utility = sum(per_sibling) / 2 if eligible else 0.0
            bridge_valid = obs["last_bridge_status"] == "valid" if obs["last_bridge_status"] != "not_submitted" else None
            arms[arm] = {"proposer_cell_id": lookup[world, arm, None]["cell_id"],
                "production_outcome": obs["production_outcome"], "termination": obs["termination"],
                "revisions": obs["revisions"], "earlier_valid_bridge": obs["earlier_valid_bridge"],
                "formal_bridge_valid": bridge_valid, "transfer_eligible": eligible, "ineligibility_reason": reason,
                "visible_solved": obs["visible_solved"], "selected_bridge_sha256": obs["selected_bridge_sha256"],
                "baseline": list(baseline), "with_bridge": treated, "per_sibling_gain": per_sibling,
                "U": utility, "utility_measured": eligible,
                "utility_kind": "measured" if eligible else "conventional_zero_production_failure",
                "helped_without_visible_solution": eligible and utility > 0 and not obs["visible_solved"],
                "prior_valid_revision_lost": obs["earlier_valid_bridge"] and obs["last_bridge_status"] != "valid",
                "valid_bridge_suppressed_by_protocol": bridge_valid is True and obs["production_outcome"] == "invalid_protocol_output"}
            if eligible and utility > 0: positive.append({"world_id": world, "arm": arm, "U": utility})
        world_results.append({"world_id": world, "family": family, "baseline": baseline, "oracle": oracle,
            "oracle_U": oracle_u, "baseline_at_ceiling": all(baseline),
            "baseline_cell_ids": [lookup[world, "B", h]["cell_id"] for h in (1, 2)], "arms": arms})
        contrasts.append({"world_id": world, "D_minus_C2": arms["D"]["U"] - arms["C2"]["U"],
                          "D_minus_D0": arms["D"]["U"] - arms["D0"]["U"],
                          "contains_conventional_zero": any(not a["utility_measured"] for a in arms.values())})
    b = sum(sum(w["baseline"]) for w in world_results)
    o = sum(sum(w["oracle"]) for w in world_results)
    failures = []
    if o < GATE["oracle_at_least"]: failures.append("oracle_below_threshold")
    if b > GATE["baseline_at_most"]: failures.append("baseline_ceiling_insufficient_headroom")
    if o - b < GATE["net_gain_at_least"]: failures.append("oracle_net_gain_below_threshold")
    gate = {"complete_pairs": 4, "baseline_successes": b, "oracle_successes": o,
            "net_gain": o - b, "passed": not failures, "failed_requirements": failures,
            "not_the_eight_world_H1": True}
    decision = ("controls_inadequate_review_instrument" if failures else
                "positive_transfer_prepare_independent_study_not_admission" if positive else
                "no_positive_transfer_close_diagnostic_review_all_failures")
    return {**base, "status": "complete", "blocking_reasons": [], "world_results": world_results,
        "control_gate": gate, "contrasts": contrasts, "positive_transfer_cells": positive,
        "decision_rule": decision, "experimental_decision": decision if dataset["data_kind"] == "experimental" else None,
        "synthetic_decision_only": dataset["data_kind"] == "synthetic",
        "hypothesis_interpretation_allowed": not failures and dataset["data_kind"] == "experimental",
        "raw_trace_audit_report_sha256": dataset["batch_audit"]["report_sha256"],
        "execution_plan_sha256": dataset["batch_audit"]["execution_plan_sha256"]}
