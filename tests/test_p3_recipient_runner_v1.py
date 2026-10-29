"""Synthetic recipient sessions; known Lean proofs are not experimental data."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from creative_machine.formal_routes import production_contract_v1 as production
from creative_machine.formal_routes import recipient_contract_v1 as contract
from creative_machine.formal_routes import recipient_runner_v1 as runner
from creative_machine.formal_routes.calibration_review_v3 import closure_v3
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.transfer_design_v1 import matrix, sha

REPO = Path(__file__).resolve().parents[1]
CELLS = [cell for cell in matrix() if cell["role"] == "recipient"]
B = next(cell for cell in CELLS if cell["arm"] == "B")
O = next(cell for cell in CELLS if cell["arm"] == "O")
C = next(cell for cell in CELLS if cell["arm"] == "D0")
SOLUTION = "import World.ChallengeEvaluation\ntheorem evaluation_solution : True := by trivial\n"
BRIDGE = b"import World.Base\ntheorem candidate_bridge : True := by trivial\n"
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


def namespace(cell):
    return "P3." + cell["world_id"]


def artifact(cell=C, source=BRIDGE, declaration="candidate_bridge"):
    world = REPO / cell["world"]
    return production.BridgeArtifact(
        source, sha(source), cell["world_id"], namespace(cell), declaration,
        tuple((rel, sha((world / rel).read_bytes())) for rel in production.BASE_FILES),
    )


class FakeLean:
    """Enough of the frozen bridge checker for portable candidate staging."""
    def __call__(self, command, *, cwd, capture_output, text, timeout):
        output = ""
        if command[-1] == "Audit.lean":
            source = (cwd / "Audit.lean").read_text()
            short = re.search(r"let names : List Lean.Name := \[`([^,]+),", source)[1]
            marker = production.AUDIT_MARKER if production.AUDIT_MARKER in source else contract.AUDIT_MARKER
            output = f"{marker}|{short}|\n"
        return subprocess.CompletedProcess(command, 0, output, "")


def prepare(tmp_path, cell=B):
    candidate = artifact(cell) if cell["bridge_kind"] == "candidate" else None
    kwargs = ({"lake": "fixture-lake", "process_runner": FakeLean()}
              if candidate is not None else {})
    record = contract.materialize_recipient(
        REPO, cell["cell_id"], tmp_path / "workspace", candidate=candidate, **kwargs,
    )
    return record, candidate


def reply(source=SOLUTION, *, identity="call1", stop="tool_use", output=40):
    return {
        "model": "anthropic.claude-opus-5", "stop_reason": stop,
        "usage": {"input_tokens": 100, "output_tokens": output},
        "content": [{"type": "tool_use", "id": identity, "name": "check_solution",
                     "input": {"solution_source": source}}],
    }


def stopped(reason="end_turn", output=40):
    response = reply(stop=reason, output=output)
    response["content"] = [{"type": "text", "text": "synthetic terminal response"}]
    return response


class FakeClient:
    max_retries = 0

    def __init__(self, responses, *, count=100, count_error=None, on_count=None, on_create=None):
        self.messages = self
        self.responses = list(responses)
        self.count = count
        self.count_error = count_error
        self.on_count = on_count
        self.on_create = on_create
        self.count_calls = []
        self.create_calls = []

    def count_tokens(self, **kwargs):
        self.count_calls.append(deepcopy(kwargs))
        if self.on_count:
            self.on_count()
        if self.count_error:
            raise self.count_error
        return SimpleNamespace(input_tokens=self.count)

    def create(self, **kwargs):
        self.create_calls.append(deepcopy(kwargs))
        if self.on_create:
            self.on_create()
        if not self.responses:
            raise AssertionError("unexpected additional inference request")
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(model_dump=lambda **_: deepcopy(payload))


class FakeChecker:
    def __init__(self, outcomes=("valid",), *, on_check=None):
        self.outcomes = iter(outcomes)
        self.on_check = on_check
        self.calls = []

    def __call__(self, record, *, repository, cell_id, candidate, timeout_s):
        self.calls.append({"path": record.path, "repository": Path(repository),
                           "cell_id": cell_id, "candidate": candidate,
                           "timeout_s": timeout_s})
        if self.on_check:
            self.on_check()
        status = next(self.outcomes)
        cell = next(row for row in CELLS if row["cell_id"] == cell_id)
        source = (record.path / "Solution.lean").read_bytes()
        solution = production.ComponentReport(
            status, sha(source), namespace(cell) + ".evaluation_solution" if status == "valid" else None,
            errors=() if status == "valid" else ("synthetic rejection",),
        )
        bridge = None
        if "Bridge.lean" in record.copied_hashes:
            short = "candidate_bridge" if cell["bridge_kind"] == "candidate" else "oracle_bridge"
            declaration = candidate.declaration if candidate is not None else namespace(cell) + "." + short
            bridge = production.ComponentReport(
                "valid", record.copied_hashes["Bridge.lean"], declaration,
            )
        return contract.RecipientReport(
            solution, bridge, tuple(record.copied_hashes.items()), cell_id,
            record.world_id, namespace(cell), f"Holdout{cell['holdout']}Statement",
            record.copied_hashes.get("Bridge.lean"),
        )


def run(record, candidate, cell, tmp_path, client, checker=None, config=None):
    return runner.run_recipient_session(
        record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate,
        artifacts=tmp_path / "artifacts", config=config or runner.recipient_config(),
        client=client, checker=checker if checker is not None else FakeChecker(),
    )


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "artifacts/events.jsonl").read_text().splitlines()]


def test_default_regime_and_interface_are_explicit():
    config = runner.recipient_config()
    assert config.model == "anthropic.claude-opus-5" and config.effort == "high"
    assert config.output_per_request == 16384 and config.max_output_tokens == 20000
    assert config.timeout_seconds == 600 and config.request_timeout_seconds == 300
    assert config.max_input_tokens == 200000 and config.max_turns == 12
    assert config.reserved_cost_usd == pytest.approx(1.65)
    assert "LAST complete" in runner.SYSTEM_PROMPT
    assert runner.SOLUTION_TOOL["input_schema"]["required"] == ["solution_source"]
    assert all(len(value) == 64 for value in runner.interface_hashes().values())


def test_request_builder_is_pure():
    messages = [{"role": "user", "content": "fixture"}]
    request = runner.build_recipient_request(messages, runner.recipient_config())
    request["messages"][0]["content"] = "changed"
    request["tools"][0]["name"] = "changed"
    assert messages[0]["content"] == "fixture"
    assert runner.SOLUTION_TOOL["name"] == "check_solution"


def test_verified_proof_stops_and_preserves_exact_bytes(tmp_path):
    record, candidate = prepare(tmp_path)
    client, checker = FakeClient([reply()]), FakeChecker()
    result = run(record, candidate, B, tmp_path, client, checker)
    assert result["status"] == "proof_verified" and result["recipient_outcome"] == "verified"
    assert result["target_solved"] and result["requests"] == result["revisions"] == 1
    assert len(client.create_calls) == len(checker.calls) == 1
    assert (tmp_path / "artifacts/selected_solution/Solution.lean").read_text() == SOLUTION
    assert result["selected_solution"]["sha256"] == sha(SOLUTION.encode())
    assert result["cost_usd_at_configured_rates"] == pytest.approx(0.00165)
    assert result["accounting_complete"] and not result["external_reservation_must_remain_open"]
    assert json.loads((tmp_path / "artifacts/session.json").read_text()) == json.loads(json.dumps(result))


def test_feedback_is_limited_without_changing_raw_report(tmp_path):
    record, candidate = prepare(tmp_path)
    base = FakeChecker(("rejected",))

    def long_error(*args, **kwargs):
        report = base(*args, **kwargs)
        return replace(report, solution=replace(report.solution, errors=("x" * 15000,)))

    result = run(record, candidate, B, tmp_path, FakeClient([reply(), stopped()]), long_error)
    assert len(result["last_verification"]["solution"]["errors"][0]) == 15000
    feedback = next(event["body"] for event in events(tmp_path) if event["event"] == "feedback")
    assert feedback["feedback_truncated"] and len(feedback["errors"][0]) == 10000
    assert set(feedback) == {"status", "valid", "errors", "feedback_truncated"}


def test_last_complete_rejected_revision_is_selected_without_fallback(tmp_path):
    record, candidate = prepare(tmp_path)
    final = SOLUTION + "-- second\n"
    client = FakeClient([reply(), reply(final, identity="call2"), stopped()])
    result = run(record, candidate, B, tmp_path, client, FakeChecker(("rejected", "rejected")))
    assert result["recipient_outcome"] == "not_solved" and not result["target_solved"]
    assert result["selected_solution"]["revision"] == 2
    assert (tmp_path / "artifacts/selected_solution/Solution.lean").read_text() == final
    assert (tmp_path / "artifacts/revisions/0001/Solution.lean").read_text() == SOLUTION


@pytest.mark.parametrize("partial_tool", (True, False))
def test_truncation_never_checks_or_replaces_previous_complete_revision(tmp_path, partial_tool):
    record, candidate = prepare(tmp_path)
    partial = reply("truncated", identity="call2", stop="max_tokens") if partial_tool else stopped("max_tokens")
    checker = FakeChecker(("rejected",))
    result = run(record, candidate, B, tmp_path, FakeClient([reply(), partial]), checker)
    assert result["status"] == "output_limit" and result["revisions"] == len(checker.calls) == 1
    assert result["selected_solution"]["sha256"] == sha(SOLUTION.encode())
    assert any(event["event"] == "truncated_response_ignored" for event in events(tmp_path))


@pytest.mark.parametrize("reason", ("max_tokens", "end_turn", "refusal"))
def test_no_complete_submission_is_auditable_not_solved_without_continuation(tmp_path, reason):
    record, candidate = prepare(tmp_path)
    client, checker = FakeClient([stopped(reason)]), FakeChecker()
    result = run(record, candidate, B, tmp_path, client, checker)
    assert result["recipient_outcome"] == "not_solved" and result["selected_solution"] is None
    assert len(client.create_calls) == 1 and not checker.calls and not (record.path / "Solution.lean").exists()


@pytest.mark.parametrize("mutation", (
    "extra", "missing", "type", "tool", "multiple", "empty_id",
    "duplicate_id", "end_turn_tool", "unicode",
))
def test_invalid_tool_output_suppresses_prior_rejected_candidate(tmp_path, mutation):
    record, candidate = prepare(tmp_path)
    bad = reply(identity="call2")
    call = bad["content"][0]
    if mutation == "extra": call["input"]["holdout"] = 2
    elif mutation == "missing": call["input"].pop("solution_source")
    elif mutation == "type": call["input"]["solution_source"] = None
    elif mutation == "tool": call["name"] = "read_file"
    elif mutation == "multiple": bad["content"].append(deepcopy(call))
    elif mutation == "empty_id": call["id"] = ""
    elif mutation == "duplicate_id": call["id"] = "call1"
    elif mutation == "end_turn_tool": bad["stop_reason"] = "end_turn"
    else: call["input"]["solution_source"] = "\ud800"
    result = run(record, candidate, B, tmp_path, FakeClient([reply(), bad]),
                 FakeChecker(("rejected",)))
    assert result["status"] == "invalid_output"
    assert result["recipient_outcome"] == "invalid_protocol_output"
    assert result["selected_solution"] is None and result["revisions"] == 1
    assert result["accounting_complete"] and not result["infrastructure_failure"]


@pytest.mark.parametrize("mode", (
    "timeout", "usage_missing", "usage_bool", "overrun", "model",
    "shape", "unknown_block",
))
def test_provider_failures_stop_admissions_without_retry_or_score(tmp_path, mode):
    record, candidate = prepare(tmp_path)
    response = reply()
    if mode == "timeout": response = TimeoutError("uncertain inference")
    elif mode == "usage_missing": response["usage"].pop("input_tokens")
    elif mode == "usage_bool": response["usage"]["output_tokens"] = True
    elif mode == "overrun": response["usage"]["output_tokens"] = 16385
    elif mode == "model": response["model"] = "different-model"
    elif mode == "shape": response["content"] = "not a list"
    else: response["content"] = [{"type": "server_tool_use", "name": "unknown"}]
    client = FakeClient([response])
    result = run(record, candidate, B, tmp_path, client)
    assert result["halt_admissions"] and result["infrastructure_failure"]
    assert result["recipient_outcome"] == "not_interpretable_infrastructure"
    assert not result["target_solved"] and result["selected_solution"] is None
    assert len(client.create_calls) == 1
    if mode in {"timeout", "usage_missing", "usage_bool", "overrun", "model"}:
        assert result["external_reservation_must_remain_open"]
    if mode == "timeout":
        assert result["uncertain_request"] and result["unresolved_charge_upper_estimate_usd"] > 0


@pytest.mark.parametrize("count", (True, -1, "100"))
def test_invalid_native_count_never_reaches_inference(tmp_path, count):
    record, candidate = prepare(tmp_path)
    client = FakeClient([], count=count)
    result = run(record, candidate, B, tmp_path, client)
    assert result["halt_admissions"] and result["requests"] == 0 and not client.create_calls


def test_count_exception_has_no_inference_reservation(tmp_path):
    record, candidate = prepare(tmp_path)
    client = FakeClient([], count_error=TimeoutError("count failed"))
    result = run(record, candidate, B, tmp_path, client)
    assert result["halt_admissions"] and result["requests"] == 0
    assert result["output_reserved"] == 0 and not result["uncertain_request"]
    assert result["accounting_complete"]


def test_token_budget_stops_before_inference(tmp_path):
    record, candidate = prepare(tmp_path)
    client = FakeClient([])
    config = replace(runner.recipient_config(), max_input_tokens=1000)
    result = run(record, candidate, B, tmp_path, client, config=config)
    assert result["status"] == "token_budget" and result["requests"] == 0
    assert not result["halt_admissions"] and not client.create_calls


def test_output_budget_is_shared_across_requests(tmp_path):
    record, candidate = prepare(tmp_path)
    client = FakeClient([reply(output=16384), stopped("max_tokens", output=3616)])
    result = run(record, candidate, B, tmp_path, client, FakeChecker(("rejected",)))
    assert [call["max_tokens"] for call in client.create_calls] == [16384, 3616]
    assert result["tokens"]["output_tokens"] == result["output_reserved"] == 20000
    assert result["status"] == "output_limit"


def test_count_inference_and_checker_share_session_deadline(tmp_path, monkeypatch):
    record, candidate = prepare(tmp_path)
    now = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    client = FakeClient([reply()], on_count=lambda: now.__setitem__(0, 20.0),
                        on_create=lambda: now.__setitem__(0, 35.0))
    checker = FakeChecker()
    result = run(record, candidate, B, tmp_path, client, checker,
                 replace(runner.recipient_config(), timeout_seconds=50))
    assert client.count_calls[0]["timeout"] == 30
    assert client.create_calls[0]["timeout"] == 30
    assert checker.calls[0]["timeout_s"] == 15
    assert result["status"] == "proof_verified"


def test_counting_can_exhaust_session_before_reservation(tmp_path, monkeypatch):
    record, candidate = prepare(tmp_path)
    now = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    client = FakeClient([], on_count=lambda: now.__setitem__(0, 601.0))
    result = run(record, candidate, B, tmp_path, client)
    assert result["status"] == "session_limit" and result["requests"] == 0
    assert result["output_reserved"] == 0 and not client.create_calls


def test_checker_failure_preserves_partial_bridge_without_scoring(tmp_path):
    record, candidate = prepare(tmp_path, O)

    def broken(*args, **kwargs):
        failure = production.VerificationInfrastructureError(
            "solution_compile", "timeout", stdout="partial compiler log",
        )
        failure.partial_bridge = production.ComponentReport(
            "valid", record.copied_hashes["Bridge.lean"], namespace(O) + ".oracle_bridge",
        )
        raise failure

    result = run(record, candidate, O, tmp_path, FakeClient([reply()]), broken)
    assert result["recipient_outcome"] == "not_interpretable_infrastructure"
    assert result["halt_admissions"] and result["selected_solution"] is None
    failure = next(event for event in events(tmp_path) if event["event"] == "infrastructure_failure")
    assert failure["partial_bridge"]["status"] == "valid"
    assert failure["stdout"] == "partial compiler log"
    assert (tmp_path / "artifacts/revisions/0001/Solution.lean").exists()


@pytest.mark.parametrize("drift", (
    "identity", "world", "statement", "inputs", "duplicate_inputs", "source",
    "status", "declaration", "axioms", "valid_errors", "bridge_hash", "bridge_absent",
    "bridge_invalid", "bridge_name", "bridge_axioms", "bridge_diagnostics",
))
def test_checker_report_is_never_trusted_without_binding_validation(tmp_path, drift):
    cell = O if drift.startswith("bridge") else B
    record, candidate = prepare(tmp_path, cell)
    valid = FakeChecker()

    def broken(*args, **kwargs):
        report = valid(*args, **kwargs)
        if drift == "identity": return replace(report, cell_id="wrong")
        if drift == "world": return replace(report, world_id="wrong")
        if drift == "statement": return replace(report, statement="OtherStatement")
        if drift == "inputs": return replace(report, input_hashes=())
        if drift == "duplicate_inputs": return replace(report, input_hashes=report.input_hashes + (report.input_hashes[0],))
        if drift == "source": return replace(report, solution=replace(report.solution, source_sha256="0" * 64))
        if drift == "status": return replace(report, solution=replace(report.solution, status="missing"))
        if drift == "declaration": return replace(report, solution=replace(report.solution, declaration="wrong"))
        if drift == "axioms": return replace(report, solution=replace(report.solution, axioms=("sorryAx",)))
        if drift == "valid_errors": return replace(report, solution=replace(report.solution, errors=("contradiction",)))
        if drift == "bridge_hash": return replace(report, bridge_sha256="0" * 64)
        if drift == "bridge_absent": return replace(report, bridge=None)
        if drift == "bridge_invalid": return replace(report, bridge=replace(report.bridge, status="rejected"))
        if drift == "bridge_axioms": return replace(report, bridge=replace(report.bridge, axioms=("sorryAx",)))
        if drift == "bridge_diagnostics": return replace(report, bridge=replace(report.bridge, errors=(1,)))
        return replace(report, bridge=replace(report.bridge, declaration="wrong"))

    result = run(record, candidate, cell, tmp_path, FakeClient([reply()]), broken)
    assert result["recipient_outcome"] == "not_interpretable_infrastructure"
    assert result["halt_admissions"] and result["selected_solution"] is None


@pytest.mark.parametrize("field", ("errors", "declaration", "axioms"))
def test_rejected_checker_report_cannot_claim_success_receipts(tmp_path, field):
    record, candidate = prepare(tmp_path)
    rejected = FakeChecker(("rejected",))

    def broken(*args, **kwargs):
        report = rejected(*args, **kwargs)
        changes = ({"errors": ()} if field == "errors" else
                   {"declaration": namespace(B) + ".evaluation_solution"} if field == "declaration" else
                   {"axioms": ("propext",)})
        return replace(report, solution=replace(report.solution, **changes))

    result = run(record, candidate, B, tmp_path, FakeClient([reply()]), broken)
    assert result["recipient_outcome"] == "not_interpretable_infrastructure"
    assert result["halt_admissions"] and result["selected_solution"] is None


@pytest.mark.parametrize("which", ("base", "target", "bridge", "solution"))
def test_workspace_mutation_stops_before_later_provider_call(tmp_path, which):
    cell = O if which == "bridge" else B
    record, candidate = prepare(tmp_path, cell)
    rel = {"base": "World/Base.lean", "target": contract.TARGET_FILE,
           "bridge": "Bridge.lean", "solution": "Solution.lean"}[which]

    def mutate():
        (record.path / rel).write_text("external mutation")

    result = run(record, candidate, cell, tmp_path, FakeClient([reply()]),
                 FakeChecker(on_check=mutate))
    assert result["halt_admissions"] and result["requests"] == 1
    assert result["recipient_outcome"] == "not_interpretable_infrastructure"


@pytest.mark.parametrize("kind", (
    "existing_artifacts", "existing_output", "artifacts_inside", "sdk_retries",
    "wrong_cell", "candidate_on_control",
))
def test_admission_does_not_overwrite_or_accept_wrong_binding(tmp_path, kind):
    record, candidate = prepare(tmp_path)
    client = FakeClient([])
    artifacts = tmp_path / "artifacts"
    cell = B
    if kind == "existing_artifacts":
        artifacts.mkdir(); (artifacts / "mine.txt").write_text("keep")
    elif kind == "existing_output":
        (record.path / "Solution.lean").write_text("keep")
    elif kind == "artifacts_inside": artifacts = record.path / "artifacts"
    elif kind == "sdk_retries": client.max_retries = 2
    elif kind == "wrong_cell": cell = next(c for c in CELLS if c["arm"] == "B" and c["cell_id"] != B["cell_id"])
    else: candidate = artifact(C)
    with pytest.raises((ValueError, FileExistsError)):
        runner.run_recipient_session(
            record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate,
            artifacts=artifacts, config=runner.recipient_config(), client=client,
        )
    assert not client.count_calls and not client.create_calls
    if kind == "existing_artifacts": assert (artifacts / "mine.txt").read_text() == "keep"
    if kind == "existing_output": assert (record.path / "Solution.lean").read_text() == "keep"


@pytest.mark.parametrize("cell", (B, O, C))
def test_provider_sees_only_allowlisted_payload_and_own_feedback(tmp_path, cell):
    record, candidate = prepare(tmp_path, cell)
    first = reply()
    first["content"].insert(0, {"type": "thinking", "thinking": "synthetic", "signature": "opaque"})
    client = FakeClient([first, stopped()])
    run(record, candidate, cell, tmp_path, client, FakeChecker(("rejected",)))
    for call in (*client.count_calls, *client.create_calls):
        encoded = json.dumps(call)
        assert not any(secret in encoded for secret in (
            "SOURCE.md", "ChallengeVisible", "VisibleStatement", "Hidden/",
            "metadata.json", cell["cell_id"], str(tmp_path), "content_audit",
        ))
        assert set(call["tools"][0]["input_schema"]["properties"]) == {"solution_source"}
        assert call["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    second_messages = client.create_calls[1]["messages"]
    assert second_messages[1]["content"][0] == first["content"][0]
    feedback = json.loads(second_messages[2]["content"][0]["content"])
    assert set(feedback) == {"status", "valid", "errors", "feedback_truncated"}
    trace = events(tmp_path)
    assert [event["seq"] for event in trace] == list(range(1, len(trace) + 1))
    assert trace[-1]["event"] == "session_finished"
    host_input = json.loads((tmp_path / "artifacts/input.json").read_text())
    assert host_input["cell_id"] == cell["cell_id"] and host_input["checker_injected"]


def test_same_candidate_bytes_hide_D0_D_C2_origin_from_provider(tmp_path):
    cells = [cell for cell in CELLS if cell["world_id"] == C["world_id"]
             and cell["holdout"] == C["holdout"] and cell["bridge_kind"] == "candidate"]
    payloads = []
    for cell in cells:
        root = tmp_path / cell["arm"]
        record, candidate = prepare(root, cell)
        client = FakeClient([stopped()])
        run(record, candidate, cell, root, client)
        payloads.append(client.create_calls[0]["messages"][0]["content"])
    assert len(payloads) == 3 and len(set(payloads)) == 1


@pytest.mark.parametrize("change", (
    {"max_turns": 13}, {"max_turns": True}, {"timeout_seconds": float("nan")},
    {"aws_profile": "other"}, {"model": "different"}, {"output_per_request": 20000},
))
def test_invalid_configuration_never_touches_provider(tmp_path, change):
    record, candidate = prepare(tmp_path)
    client = FakeClient([])
    with pytest.raises(ValueError):
        run(record, candidate, B, tmp_path, client,
            config=replace(runner.recipient_config(), **change))
    assert not client.count_calls and not client.create_calls


def known_proof(cell):
    world = REPO / cell["world"]
    proof = closure_v3(world, f"holdout{cell['holdout']}", "oracle")
    if cell["bridge_kind"] == "none":
        helper = (world / "Hidden/Oracle.lean").read_text().replace(
            "import World.Base", "import World.ChallengeEvaluation",
        )
        return helper + "\n" + proof.replace("import World.ChallengeEvaluation\nimport Bridge\n", "")
    return proof


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("cell", (
    next(c for c in CELLS if c["arm"] == "B" and c["family"] == "invariant"),
    next(c for c in CELLS if c["arm"] == "O" and c["family"] == "representation"),
))
def test_synthetic_provider_uses_real_recipient_contract_in_both_families(tmp_path, cell):
    record, candidate = prepare(tmp_path, cell)
    source = known_proof(cell)
    result = runner.run_recipient_session(
        record, repository=REPO, cell_id=cell["cell_id"], candidate=candidate,
        artifacts=tmp_path / "artifacts", config=runner.recipient_config(),
        client=FakeClient([reply(source)]),
    )
    assert result["recipient_outcome"] == "verified" and result["target_solved"]
    assert result["last_verification"]["solution"]["declaration"] == namespace(cell) + ".evaluation_solution"
