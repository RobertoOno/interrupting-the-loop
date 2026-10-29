"""Adversarial audit tests. Shared runner fixtures are synthetic, never data."""
from copy import deepcopy
from dataclasses import replace
import json
import os

import pytest

from creative_machine.formal_routes import recipient_audit_v1 as audit
from creative_machine.formal_routes import recipient_contract_v1 as contract
from creative_machine.formal_routes import recipient_runner_v1 as runner
from creative_machine.formal_routes import production_contract_v1 as production
from creative_machine.formal_routes.transfer_design_v1 import encoded, sha
from creative_machine.formal_routes.transfer_analysis_v1 import blank_dataset, analyze
from test_p3_recipient_runner_v1 import (
    REPO, CELLS, B, O, C, SOLUTION, LOCAL_LEAN, FakeClient, FakeChecker,
    artifact, namespace, prepare, reply, stopped, known_proof,
)


def check(record, **kwargs):
    path = record.path / "Solution.lean"
    if path.exists():
        status = "rejected" if path.read_text().startswith("BAD") else "valid"
        result = FakeChecker((status,))(record, **kwargs)
        if path.read_text().startswith("BADLONG"):
            result = replace(result, solution=replace(result.solution, errors=("x" * 15000,)))
        return result
    cell = next(c for c in CELLS if c["cell_id"] == kwargs["cell_id"])
    bridge = None
    if "Bridge.lean" in record.copied_hashes:
        candidate = kwargs["candidate"]
        declaration = candidate.declaration if candidate else namespace(cell) + ".oracle_bridge"
        bridge = production.ComponentReport("valid", record.copied_hashes["Bridge.lean"], declaration)
    return contract.RecipientReport(
        production.ComponentReport("missing", None, None, errors=("no submission",)),
        bridge, tuple(record.copied_hashes.items()), cell["cell_id"], record.world_id,
        namespace(cell), f"Holdout{cell['holdout']}Statement", record.copied_hashes.get("Bridge.lean"),
    )


def create(tmp_path, responses=None, cell=B, client=None, checker=check):
    record, candidate = prepare(tmp_path, cell)
    runner.run_recipient_session(record, repository=REPO, cell_id=cell["cell_id"],
        candidate=candidate, artifacts=tmp_path / "artifacts", config=runner.recipient_config(),
        client=client or FakeClient(responses if responses is not None else [reply()]), checker=checker)
    return candidate


def inspect(tmp_path, cell=B, candidate=None, **kwargs):
    return audit.audit_recipient_trace(REPO, tmp_path / "artifacts", cell_id=cell["cell_id"],
        candidate=candidate, data_kind=kwargs.pop("data_kind", "synthetic"),
        checker=kwargs.pop("checker", check), **kwargs)


def read(tmp_path, name):
    return json.loads((tmp_path / "artifacts" / name).read_text())


def write(tmp_path, name, value):
    (tmp_path / "artifacts" / name).write_text(json.dumps(value))


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "artifacts/events.jsonl").read_text().splitlines()]


def save_events(tmp_path, rows):
    (tmp_path / "artifacts/events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))


@pytest.mark.parametrize("cell", CELLS, ids=lambda c: c["cell_id"])
def test_all_twenty_positions_reconstruct_without_admitting_batch(tmp_path, cell):
    candidate = create(tmp_path, cell=cell)
    result = inspect(tmp_path, cell, candidate)
    assert result["status"] == "passed" and result["reconstructed_session"]["target_solved"]
    assert len(result["rechecked_revisions"]) == 1
    assert result["cell_projection"]["cell_id"] == cell["cell_id"]
    assert not any(result[key] for key in (
        "parent_and_content_validated", "phase_barrier_verified", "batch_audit_passed",
        "inference_admitted", "recipient_admitted", "main_sample_admitted", "mechanistic_stage_admitted"))


@pytest.mark.parametrize("reason", ["end_turn", "refusal", "max_tokens"])
@pytest.mark.parametrize("cell", [B, O, C], ids=lambda c: c["arm"])
def test_no_submission_rechecks_inputs_and_bridge(tmp_path, cell, reason):
    candidate = create(tmp_path, [stopped(reason)], cell)
    result = inspect(tmp_path, cell, candidate)
    assert result["no_submission_input_check"]["solution"]["status"] == "missing"
    assert not result["reconstructed_session"]["target_solved"]
    assert not result["rechecked_revisions"]


@pytest.mark.parametrize("final", [reply(identity="two"), stopped(), reply("partial", identity="two", stop="max_tokens")])
def test_rejected_revision_followed_by_success_stop_or_truncation(tmp_path, final):
    create(tmp_path, [reply("BADLONG"), final])
    result = inspect(tmp_path)
    expected = 2 if final["stop_reason"] == "tool_use" else 1
    assert len(result["rechecked_revisions"]) == expected
    assert result["reconstructed_session"]["selected_solution"]["revision"] == expected


def test_last_rejected_revision_and_empty_source_remain_real_submissions(tmp_path):
    create(tmp_path, [reply("BAD"), reply("BAD second", identity="two"), stopped()])
    result = inspect(tmp_path)
    assert result["reconstructed_session"]["selected_solution"]["revision"] == 2
    other = tmp_path / "empty"
    create(other, [reply("")])
    assert inspect(other)["rechecked_revisions"][0]["report"]["solution"]["source_sha256"] == sha(b"")


@pytest.mark.parametrize("mutation", ["extra", "missing", "type", "tool", "multiple", "empty_id", "duplicate_id", "end_turn", "unicode"])
def test_protocol_failures_suppress_previous_selection(tmp_path, mutation):
    response = reply(identity="two")
    call = response["content"][0]
    if mutation == "extra": call["input"]["extra"] = True
    elif mutation == "missing": call["input"].clear()
    elif mutation == "type": call["input"]["solution_source"] = None
    elif mutation == "tool": call["name"] = "other"
    elif mutation == "multiple": response["content"].append(deepcopy(call))
    elif mutation == "empty_id": call["id"] = ""
    elif mutation == "duplicate_id": call["id"] = "call1"
    elif mutation == "end_turn": response["stop_reason"] = "end_turn"
    else: call["input"]["solution_source"] = "\ud800"
    create(tmp_path, [reply("BAD"), response])
    summary = inspect(tmp_path)["reconstructed_session"]
    assert summary["recipient_outcome"] == "invalid_protocol_output"
    assert summary["selected_solution"] is None


@pytest.mark.parametrize("kind", ["input", "output", "requests"])
def test_budget_and_request_exhaustion(tmp_path, kind):
    if kind == "input": client = FakeClient([], count=200000)
    elif kind == "output": client = FakeClient([reply("BAD", output=16384), reply("BAD2", identity="two", output=3600)])
    else: client = FakeClient([reply("BAD", identity=str(i)) for i in range(12)])
    create(tmp_path, client=client)
    result = inspect(tmp_path)["reconstructed_session"]
    assert result["status"] == ("request_limit" if kind == "requests" else "token_budget")


def test_cache_accounting(tmp_path):
    response = reply()
    response["usage"].update(cache_creation_input_tokens=12, cache_read_input_tokens=30)
    create(tmp_path, [response])
    summary = inspect(tmp_path)["reconstructed_session"]
    assert summary["cost_usd_at_configured_rates"] == pytest.approx((5.5 * 127 + 27.5 * 40) / 1e6)
    assert summary["input_reserved"] == 1135


@pytest.mark.parametrize("where", ["before_count", "after_count"])
def test_session_deadline(tmp_path, monkeypatch, where):
    class Clock:
        value = calls = 0
        def monotonic(self):
            self.calls += 1
            if where == "before_count" and self.calls >= 3:
                self.value = 601
            return float(self.value)
    clock = Clock()
    monkeypatch.setattr(runner.time, "monotonic", clock.monotonic)
    create(tmp_path, client=FakeClient([], on_count=lambda: setattr(clock, "value", 601)))
    assert inspect(tmp_path)["reconstructed_session"]["status"] == "session_limit"


@pytest.mark.parametrize("field,value", [
    ("target_solved", False), ("requests", 2), ("revisions", True), ("selected_solution", None),
    ("status", "model_stopped"), ("cost_usd_at_configured_rates", 0), ("input_reserved", 1),
    ("output_reserved", 0), ("accounting_complete", False), ("recipient_outcome", "not_solved"),
])
def test_synchronized_summary_forgery_is_reconstructed(tmp_path, field, value):
    create(tmp_path)
    summary = read(tmp_path, "session.json")
    summary[field] = value
    write(tmp_path, "session.json", summary)
    rows = events(tmp_path)
    rows[-1]["result"] = summary
    save_events(tmp_path, rows)
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path)


@pytest.mark.parametrize("kind", ["history", "tool", "thinking", "feedback", "source", "receipt", "sequence", "timestamp", "usage"])
def test_trace_tampering(tmp_path, kind):
    create(tmp_path, [reply("BAD"), reply(identity="two")])
    rows = events(tmp_path)
    if kind in {"history", "tool", "thinking"}:
        body = next(r for r in rows if r["event"] == "request")["body"]
        if kind == "history": body["messages"][0]["content"] += "leak"
        elif kind == "tool": body["tools"][0]["name"] = "other"
        else: body["thinking"] = {"type": "disabled"}
    elif kind == "feedback": next(r for r in rows if r["event"] == "feedback")["body"]["errors"] = []
    elif kind == "source": (tmp_path / "artifacts/revisions/0001/Solution.lean").write_text("different")
    elif kind == "receipt":
        receipt = read(tmp_path, "revisions/0001/submission.json")
        receipt["tool_use_id"] = "wrong"
        write(tmp_path, "revisions/0001/submission.json", receipt)
    elif kind == "sequence": rows[1]["seq"] = True
    elif kind == "timestamp": rows[1]["at"] = "2020-01-01T00:00:00Z"
    else: next(r for r in rows if r["event"] == "response")["body"]["usage"]["input_tokens"] = True
    save_events(tmp_path, rows)
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path)


@pytest.mark.parametrize("kind", ["extra", "directory", "symlink", "hardlink", "missing", "selected", "duplicate_json"])
def test_inventory_and_json_fail_closed(tmp_path, kind):
    create(tmp_path)
    root = tmp_path / "artifacts"
    if kind == "extra": (root / "extra").write_text("x")
    elif kind == "directory": (root / "empty").mkdir()
    elif kind == "symlink": (root / "link").symlink_to(root / "input.json")
    elif kind == "hardlink": os.link(root / "input.json", root / "link")
    elif kind == "missing": (root / "revisions/0001/submission.json").unlink()
    elif kind == "selected": (root / "selected_solution/Solution.lean").write_text("different")
    else: (root / "session.json").write_text('{"status": 1, "status": 2}')
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path)


@pytest.mark.parametrize("field", ["cell_id", "world_id", "namespace", "statement", "bridge_sha256", "holdout", "copied_hashes", "messages"])
def test_host_binding_is_not_trusted(tmp_path, field):
    create(tmp_path)
    initial = read(tmp_path, "input.json")
    initial[field] = "wrong"
    write(tmp_path, "input.json", initial)
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path)


def test_candidate_binding_and_external_seal(tmp_path):
    candidate = create(tmp_path, cell=C)
    manifest = audit.build_evidence_manifest(REPO, tmp_path / "artifacts", cell_id=C["cell_id"], data_kind="synthetic", candidate=candidate)
    seal = sha(encoded(manifest))
    assert inspect(tmp_path, C, candidate, expected_evidence_sha256=seal)["evidence_sha256"] == seal
    different = artifact(C, source=candidate.source + b"\n")
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path, C, different, expected_evidence_sha256=seal)
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path, C, candidate, expected_evidence_sha256="0" * 64)
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path, B, candidate)


@pytest.mark.parametrize("kind", ["plan", "seal", "blueprint", "injected", "label"])
def test_experimental_provenance_gates(tmp_path, kind):
    create(tmp_path)
    kwargs = dict(data_kind="experimental", checker=None, execution_plan_sha256="a" * 64)
    if kind == "plan": kwargs.pop("execution_plan_sha256")
    elif kind == "blueprint": kwargs["execution_plan_sha256"] = "74e0ee9e49aa92797d6951023345c5d38dc46dd1d28eea1fae3db0db1035fa81"
    elif kind in {"injected", "label"}:
        manifest = audit.build_evidence_manifest(REPO, tmp_path / "artifacts", cell_id=B["cell_id"], data_kind="experimental", execution_plan_sha256="a" * 64)
        kwargs["expected_evidence_sha256"] = sha(encoded(manifest))
        if kind == "injected": kwargs["checker"] = check
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path, **kwargs)


@pytest.mark.parametrize("kind", ["count", "inference", "usage", "model", "checker"])
def test_technical_traces_never_become_scores(tmp_path, kind):
    response = reply()
    if kind == "usage": response["usage"] = None
    if kind == "model": response["model"] = "wrong"
    client = FakeClient([RuntimeError("offline") if kind == "inference" else response],
                        count_error=RuntimeError("offline") if kind == "count" else None)
    def unavailable(*args, **kwargs): raise RuntimeError("checker unavailable")
    create(tmp_path, client=client, checker=unavailable if kind == "checker" else check)
    with pytest.raises(audit.TraceAuditBlocked): inspect(tmp_path)


def test_fresh_rejection_invalidates_recorded_success(tmp_path):
    create(tmp_path)
    with pytest.raises(audit.TraceAuditError, match="fresh Lean"):
        inspect(tmp_path, checker=FakeChecker(("rejected",)))


@pytest.mark.parametrize("submit", [True, False])
def test_fresh_checker_unavailable_blocks_even_without_submission(tmp_path, submit):
    candidate = create(tmp_path, [reply()] if submit else [stopped()], O)
    def unavailable(*args, **kwargs): raise RuntimeError("bridge infrastructure")
    with pytest.raises(audit.TraceAuditBlocked) as error:
        inspect(tmp_path, O, candidate, checker=unavailable)
    assert isinstance(error.value.__cause__, RuntimeError)


@pytest.mark.parametrize("kind", ["output", "input", "raw"])
def test_changes_during_fresh_check_fail_closed(tmp_path, kind):
    create(tmp_path)
    def changing(record, **kwargs):
        report = check(record, **kwargs)
        path = record.path / ("Solution.lean" if kind == "output" else "World/Base.lean")
        if kind == "raw": path = tmp_path / "artifacts/session.json"
        path.write_bytes(path.read_bytes() + b"\n")
        return report
    with pytest.raises(audit.TraceAuditError): inspect(tmp_path, checker=changing)


def test_fresh_workspaces_diagnostics_and_independence(tmp_path, monkeypatch):
    create(tmp_path, [reply("BAD"), reply(identity="two")])
    def forbidden(*args, **kwargs): raise AssertionError("runner execution reused")
    for name in ("run_recipient_session", "build_recipient_request", "_feedback"):
        monkeypatch.setattr(runner, name, forbidden)
    monkeypatch.setattr(runner.TokenBudget, "reserve", forbidden)
    monkeypatch.setattr(runner.TokenBudget, "settle", forbidden)
    monkeypatch.setattr(audit.evidence, "audit_proposer_trace", forbidden)
    paths = []
    def checking(record, **kwargs):
        assert not (record.path / ".lake").exists()
        assert record.path not in paths
        paths.append(record.path)
        report = check(record, **kwargs)
        return replace(report, solution=replace(report.solution, stdout="fresh diagnostic"))
    result = inspect(tmp_path, checker=checking)
    assert len(paths) == 2 and all(not p.exists() for p in paths)
    assert result["rechecked_revisions"][0]["report"]["solution"]["stdout"] == "fresh diagnostic"


def test_projection_does_not_admit_unfinished_batch(tmp_path):
    create(tmp_path)
    report = inspect(tmp_path)
    blueprint = audit.load_blueprint(REPO)
    dataset = blank_dataset(blueprint, data_kind="synthetic")
    dataset["cells"] = [report["cell_projection"] if c["cell_id"] == B["cell_id"] else c for c in dataset["cells"]]
    result = analyze(blueprint, dataset)
    assert result["status"] == "not_interpretable"
    assert result["world_results"] is None and result["experimental_decision"] is None


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("cell", [
    next(c for c in CELLS if c["arm"] == "B" and c["family"] == "invariant"),
    next(c for c in CELLS if c["arm"] == "O" and c["family"] == "representation"),
])
def test_real_lean_reconstruction_in_both_families(tmp_path, cell):
    create(tmp_path, [reply(known_proof(cell))], cell, checker=None)
    result = inspect(tmp_path, cell, checker=None)
    assert result["reconstructed_session"]["target_solved"]
    assert result["verification"] == "fresh_sandboxed_Lean_per_revision"


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_rejects_fabricated_acceptance(tmp_path):
    create(tmp_path)
    with pytest.raises(audit.TraceAuditError, match="fresh Lean"):
        inspect(tmp_path, checker=None)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_rechecks_rejected_then_verified_revision(tmp_path):
    create(tmp_path, [reply(SOLUTION), reply(known_proof(B), identity="two")], checker=None)
    result = inspect(tmp_path, checker=None)
    assert [r["report"]["solution"]["status"] for r in result["rechecked_revisions"]] == ["rejected", "valid"]
