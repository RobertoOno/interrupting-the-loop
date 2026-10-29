"""Audit synthetic packages; never authenticate a model or re-judge a bridge."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

import pytest

from creative_machine.formal_routes import transfer_batch_audit_v1 as audit
from creative_machine.formal_routes import transfer_rehearsal_v1 as rehearsal
from creative_machine.formal_routes.transfer_design_v1 import encoded, sha
from test_p3_transfer_rehearsal_v1 import REPO, CELLS, run, scenario, review
from test_p3_production_audit_v1 import fixture_check, terminal, LOCAL_LEAN
from test_p3_recipient_audit_v1 import check as recipient_check


@pytest.fixture(scope="module")
def complete(tmp_path_factory):
    root = tmp_path_factory.mktemp("complete-batch")
    result = run(root)
    assert result["status"] == "complete_rehearsal"
    return root / "run", result


@pytest.fixture(scope="module")
def no_bridge(tmp_path_factory):
    root = tmp_path_factory.mktemp("no-bridge-batch")
    result = run(root, scenario([terminal()]))
    assert result["status"] == "complete_rehearsal"
    return root / "run", result


def inspect(package, refs, **kwargs):
    options = {"expected_closure_sha256": refs["closure_manifest_sha256"],
        "expected_plan_sha256": refs["plan_sha256"],
        "expected_lifecycle_head_sha256": refs["lifecycle_head_sha256"],
        "permitted_reviewer_ids": ("fixture-reviewer",),
        "proposer_checker": fixture_check, "recipient_checker": recipient_check}
    options.update(kwargs)
    return audit.audit_rehearsal_batch(REPO, package, **options)


def copy_package(fixture, tmp_path):
    package, refs = fixture
    target = tmp_path / "copy"
    shutil.copytree(package, target)
    return target, deepcopy(refs)


def reseal(package, refs):
    # Tests may deliberately replace the outer trusted reference to test
    # semantic/internal binding checks independently from tamper detection.
    inventory = rehearsal._inventory(package)
    inventory.pop("closure_manifest.json")
    manifest_path = package / "closure_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["entries"] = {rel: {k: v for k, v in item.items() if k not in ("device", "inode")}
                            for rel, item in inventory.items()}
    manifest_path.write_bytes(encoded(manifest))
    refs["closure_manifest_sha256"] = sha(manifest_path.read_bytes())


def replace_journal(package, refs, rows):
    previous, updated = None, []
    for row in rows:
        entry = audit.lifecycle.entry(row["event"], row["payload"], seq=row["seq"], previous_sha256=previous, at=row["at"])
        updated.append(entry)
        previous = entry["sha256"]
        (package / f"checkpoints/{entry['seq']:04d}.json").write_bytes(encoded(
            {"head_sha256": previous, "events": entry["seq"], "data_kind": "synthetic"}))
    (package / "lifecycle.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in updated))
    refs["lifecycle_head_sha256"] = previous
    for name in ("summary.json", "closure_manifest.json"):
        path = package / name
        data = json.loads(path.read_text())
        data["lifecycle_head_sha256"] = previous
        path.write_bytes(encoded(data))
    reseal(package, refs)


def test_complete_package_reaudited_without_integrator_or_writes(complete, monkeypatch):
    package, refs = complete
    before = audit.snapshot(package)
    def forbidden(*args, **kwargs):
        pytest.fail("batch auditor called integrator/runner instead of reading evidence")
    monkeypatch.setattr(rehearsal, "run_rehearsal", forbidden)
    monkeypatch.setattr(rehearsal, "_inventory", forbidden)
    monkeypatch.setattr(rehearsal, "_candidate", forbidden)
    monkeypatch.setattr(rehearsal.proposer_runner, "run_production_session", forbidden)
    monkeypatch.setattr(rehearsal.recipient_runner, "run_recipient_session", forbidden)
    result = inspect(package, refs)
    assert result["status"] == "passed" and result["data_kind"] == "synthetic"
    assert result["reaudited_sessions"] == 26 and result["review_receipts_validated"] == 6
    assert result["skipped_candidate_positions"] == 0
    assert result["internal_phase_barrier_verified"]
    assert result["analysis"]["status"] == "not_interpretable" and result["analysis"]["contrasts"] is None
    assert all(result[key] is False for key in ("provider_origin_authenticated", "external_financial_reconciliation_verified",
        "worker_ownership_verified", "inference_admitted", "main_sample_admitted", "mechanistic_stage_admitted", "semantic_judgments_reissued"))
    assert audit.snapshot(package) == before


def test_copied_package_and_ineligible_candidates_preserve_all_controls(no_bridge, tmp_path):
    package, refs = copy_package(no_bridge, tmp_path)
    result = inspect(package, refs)
    assert result["status"] == "passed" and result["reaudited_sessions"] == 14
    assert result["skipped_candidate_positions"] == 12 and result["review_receipts_validated"] == 0
    assert result["reconstructed_dataset"]["batch_audit"]["status"] == "pending"


@pytest.mark.parametrize("field", ("expected_closure_sha256", "expected_plan_sha256", "expected_lifecycle_head_sha256"))
@pytest.mark.parametrize("value", (None, "f" * 64))
def test_external_references_cannot_be_replaced_by_self_claims(complete, field, value):
    with pytest.raises(ValueError):
        inspect(*complete, **{field: value})


@pytest.mark.parametrize("allowlist", ((), ("other",), ("fixture-reviewer", "fixture-reviewer"), ["fixture-reviewer"]))
def test_reviewer_allowlist_must_come_from_caller(complete, allowlist):
    with pytest.raises(ValueError):
        inspect(*complete, permitted_reviewer_ids=allowlist)


@pytest.mark.parametrize("kind", ("raw", "summary", "manifest", "extra", "empty_dir", "symlink", "hardlink", "missing"))
def test_tampering_fails_external_seal_before_any_fresh_checker(complete, tmp_path, kind):
    package, refs = copy_package(complete, tmp_path)
    path = package / "cells" / CELLS[0]["cell_id"] / "artifacts/session.json"
    if kind == "summary": path = package / "summary.json"
    if kind == "manifest": path = package / "closure_manifest.json"
    if kind == "extra": (package / "extra").write_bytes(b"unbound")
    elif kind == "empty_dir": (package / "empty").mkdir()
    elif kind == "symlink": (package / "link").symlink_to(path)
    elif kind == "hardlink": os.link(path, package / "link")
    elif kind == "missing": path.unlink()
    else: path.write_bytes(path.read_bytes() + b" ")
    def never(*args, **kwargs): pytest.fail("checking before verifying outer seal")
    with pytest.raises(ValueError):
        inspect(package, refs, proposer_checker=never, recipient_checker=never)


@pytest.mark.parametrize("kind", ("summary", "dataset", "analysis", "extra", "empty_dir", "workspace", "checkpoint", "raw", "receipt", "experimental"))
def test_resealed_outer_manifest_does_not_certify_inner_claims(no_bridge, tmp_path, kind):
    package, refs = copy_package(no_bridge, tmp_path)
    first = CELLS[0]["cell_id"]
    if kind in ("summary", "dataset", "analysis"):
        path = package / (kind + ".json")
        data = json.loads(path.read_text())
        if kind == "summary": data["recorded_session_count"] -= 1
        elif kind == "dataset": data["cells"][0]["observation"]["visible_solved"] = True
        else: data["inference_admitted"] = True
        path.write_bytes(encoded(data))
    elif kind == "extra": (package / "extra.json").write_bytes(b"{}")
    elif kind == "empty_dir": (package / "review_host/unbound").mkdir()
    elif kind == "workspace": (package / "cells" / first / "workspace/SOURCE.md").write_text("hidden added context")
    elif kind == "checkpoint":
        (package / "checkpoints/0001.json").write_bytes(encoded({"head_sha256": "0" * 64, "events": 1, "data_kind": "synthetic"}))
    elif kind == "raw":
        path = package / "cells" / first / "artifacts/session.json"
        data = json.loads(path.read_text())
        data["cost_usd_at_configured_rates"] = 0
        path.write_bytes(encoded(data))
    elif kind == "receipt":
        path = next((package / "receipts").iterdir())
        path.write_bytes(path.read_bytes() + b" ")
    else:
        path = package / "rehearsal_plan.json"
        data = json.loads(path.read_text())
        data["data_kind"] = "experimental"
        path.write_bytes(encoded(data))
        refs["plan_sha256"] = sha(path.read_bytes())
    reseal(package, refs)
    with pytest.raises(ValueError):
        inspect(package, refs)


@pytest.mark.parametrize("kind", ("pending", "technical"))
def test_partial_and_technical_lifecycle_block_without_scoring_or_repair(tmp_path, kind):
    fixtures = scenario()
    if kind == "technical": fixtures[CELLS[0]["cell_id"]] = []
    refs = run(tmp_path, fixtures, reviewer=lambda packet: None)
    package = tmp_path / "run"
    before = audit.snapshot(package)
    with pytest.raises(audit.BatchAuditBlocked, match="incomplete/technical"):
        inspect(package, refs)
    assert audit.snapshot(package) == before


def test_fresh_kernel_failure_keeps_package_blocked_not_zero(complete):
    def unavailable(*args, **kwargs):
        raise audit.production.VerificationInfrastructureError("fixture", "kernel unavailable")
    with pytest.raises(audit.BatchAuditBlocked, match="fresh session audit blocked"):
        inspect(*complete, proposer_checker=unavailable)


def test_changed_package_during_fresh_check_cannot_pass(no_bridge, tmp_path):
    package, refs = copy_package(no_bridge, tmp_path)
    done = False
    def corrupt(record, **kwargs):
        nonlocal done
        if not done:
            done = True
            path = package / "summary.json"
            path.write_bytes(path.read_bytes() + b" ")
        return recipient_check(record, **kwargs)
    with pytest.raises(ValueError, match="changed during independent audit"):
        inspect(package, refs, recipient_checker=corrupt)


def test_duplicate_json_keys_rejected_even_under_a_new_outer_seal(no_bridge, tmp_path):
    package, refs = copy_package(no_bridge, tmp_path)
    path = package / "summary.json"
    path.write_bytes(path.read_bytes().replace(b'{', b'{"slot_count": 26,', 1))
    reseal(package, refs)
    with pytest.raises(ValueError, match="duplicate JSON"):
        inspect(package, refs)


@pytest.mark.parametrize("kind", ("cost", "interval"))
def test_internally_valid_rehashed_journal_must_still_match_raw_sessions(no_bridge, tmp_path, kind):
    package, refs = copy_package(no_bridge, tmp_path)
    rows = [json.loads(line) for line in (package / "lifecycle.jsonl").read_text().splitlines()]
    first_close = next(row for row in rows if row["event"] == "cell_closed")
    if kind == "cost": first_close["payload"]["reported_cost_usd"] = "0"
    else: first_close["at"] = next(row["at"] for row in rows if row["event"] == "cell_started")
    replace_journal(package, refs, rows)
    with pytest.raises(ValueError, match="journal/independent cost|outside lifecycle interval"):
        inspect(package, refs)


@pytest.mark.parametrize("kind", ("decision", "timestamp"))
def test_rehashed_content_receipt_cannot_misstate_recorded_judgment(complete, tmp_path, kind):
    package, refs = copy_package(complete, tmp_path)
    identity = CELLS[0]["cell_id"]
    path = package / "review_host" / (identity + "-review.json")
    receipt = json.loads(path.read_text())
    if kind == "decision":
        from test_p3_bridge_content_v1 import judgment
        packet = json.loads((package / "review_host" / (identity + ".json")).read_text())["packet"]
        receipt["review"]["criteria"]["mathematical_scope"] = judgment("violation", packet["bridge_utf8"].encode())
        receipt["review_sha256"] = sha(encoded(receipt["review"]))
    else: receipt["recorded_at"] = "2000-01-01T00:00:00+00:00"
    path.write_bytes(encoded(receipt))
    rows = [json.loads(line) for line in (package / "lifecycle.jsonl").read_text().splitlines()]
    event = next(row for row in rows if row["event"] == "review_recorded" and row["payload"]["cell_id"] == identity)
    event["payload"]["receipt_sha256"] = sha(path.read_bytes())
    # The barrier commits to proposer review receipts too. Recompute only
    # this internal reference, deliberately leaving the semantic lie intact.
    barrier_index = next(i for i, row in enumerate(rows) if row["event"] == "phase_barrier")
    prefix, previous = [], None
    for row in rows[:barrier_index]:
        rebuilt = audit.lifecycle.entry(row["event"], row["payload"], seq=row["seq"], previous_sha256=previous, at=row["at"])
        previous = rebuilt["sha256"]
        prefix.append(rebuilt)
    state = audit.lifecycle.replay(audit.load_blueprint(REPO), prefix)
    rows[barrier_index]["payload"]["proposer_bindings_sha256"] = state["ready_proposer_bindings_sha256"]
    replace_journal(package, refs, rows)
    with pytest.raises(ValueError, match="recorded content judgment|review outside lifecycle interval"):
        inspect(package, refs)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_refutes_synthetic_false_acceptance_in_an_intact_package(no_bridge):
    # Portable fixtures accept a True theorem as though it were the target.
    # The actual kernel contract must reject this even with all outer seals.
    with pytest.raises(ValueError, match="fresh Lean verification"):
        inspect(*no_bridge, proposer_checker=None, recipient_checker=None)


@pytest.mark.parametrize("bound", ("MAX_ENTRIES", "MAX_FILE_BYTES", "MAX_TOTAL_BYTES"))
def test_reader_limits_apply_before_unbounded_allocation(tmp_path, monkeypatch, bound):
    (tmp_path / "one").write_bytes(b"12345")
    (tmp_path / "two").write_bytes(b"12345")
    monkeypatch.setattr(audit, bound, 1)
    with pytest.raises(ValueError, match="limit"):
        audit.snapshot(tmp_path)
