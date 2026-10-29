"""Synthetic provider sessions and optional real Lean checks; never live inference."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from creative_machine.formal_routes import production_runner_v1 as runner
from creative_machine.formal_routes.production_contract_v1 import (
    BASE_FILES, ComponentReport, ProductionReport, VerificationInfrastructureError,
    WorkspaceIntegrityError, materialize_production_proposer,
)
from creative_machine.formal_routes.calibration_review_v3 import closure_v3
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY

REPO = Path(__file__).resolve().parents[1]
WORLDS = (REPO / "worlds/calibration/CAL3_I_E87C49876088749B",
          REPO / "worlds/calibration/CAL3_R_F76437525B190ECB")
WORLD = WORLDS[0]
NS = json.loads((WORLD / "metadata.json").read_text())["roles"]["namespace"]
BRIDGE = "import World.Base\ntheorem candidate_bridge : True := by trivial\n"
SOLUTION = "import World.ChallengeVisible\nimport Bridge\ntheorem candidate_solution : True := by trivial\n"
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reply(bridge=BRIDGE, solution=SOLUTION, *, identity="call1", stop="tool_use", output=40):
    return {"model": "anthropic.claude-opus-5", "stop_reason": stop,
            "usage": {"input_tokens": 100, "output_tokens": output},
            "content": [{"type": "tool_use", "id": identity, "name": "check_submission",
                         "input": {"bridge_source": bridge, "solution_source": solution}}]}


def stopped(reason="end_turn", output=40):
    result = reply(stop=reason, output=output)
    result["content"] = [{"type": "text", "text": "synthetic terminal response"}]
    return result


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
    def __init__(self, outcomes=(("valid", "valid"),), *, on_check=None):
        self.outcomes = iter(outcomes)
        self.calls = []
        self.on_check = on_check

    def __call__(self, record, *, namespace, timeout_s):
        self.calls.append({"path": record.path, "namespace": namespace, "timeout_s": timeout_s})
        if self.on_check:
            self.on_check()
        bridge_status, visible_status = next(self.outcomes)

        def component(rel, status, name):
            path = record.path / rel
            return ComponentReport(status, sha(path.read_bytes()) if path.exists() else None,
                                   name if status == "valid" else None,
                                   errors=() if status == "valid" else ("synthetic rejection or absence",))

        return ProductionReport(component("Bridge.lean", bridge_status, "candidate_bridge"),
                                component("Solution.lean", visible_status, "candidate_solution"),
                                tuple((rel, record.copied_hashes[rel]) for rel in BASE_FILES), namespace)


@pytest.fixture
def record(tmp_path):
    return materialize_production_proposer(WORLD, "D", tmp_path / "workspace")


def run(record, tmp_path, client, checker=None, config=None):
    return runner.run_production_session(record, namespace=NS, artifacts=tmp_path / "artifacts",
                                          config=config or runner.production_config(), client=client,
                                          checker=checker if checker is not None else FakeChecker())


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "artifacts/events.jsonl").read_text().splitlines()]


def test_default_regime_is_the_larger_s16_and_interface_is_explicit():
    config = runner.production_config()
    assert config.model == "anthropic.claude-opus-5" and config.effort == "high"
    assert config.output_per_request == 16384 and config.max_output_tokens == 20000
    assert config.timeout_seconds == 600 and config.request_timeout_seconds == 300
    assert config.max_input_tokens == 200000 and config.max_turns == 12
    assert config.reserved_cost_usd == pytest.approx(1.65)
    assert "LAST complete" in runner.SYSTEM_PROMPT
    assert runner.SUBMISSION_TOOL["input_schema"]["required"] == ["bridge_source", "solution_source"]
    assert all(len(value) == 64 for value in runner.interface_hashes().values())


def test_request_builder_is_pure_and_does_not_alias_messages_or_tool_contract():
    messages = [{"role": "user", "content": "test fixture"}]
    request = runner.build_production_request(messages, runner.production_config())
    request["messages"][0]["content"] = "changed copy"
    request["tools"][0]["name"] = "changed copy"
    assert messages[0]["content"] == "test fixture"
    assert runner.SUBMISSION_TOOL["name"] == "check_submission"


def test_feedback_limit_is_logged_without_changing_raw_verification(record, tmp_path):
    valid = FakeChecker([("valid", "rejected")])

    def long_error(record, **kwargs):
        report = valid(record, **kwargs)
        return replace(report, visible=replace(report.visible, errors=("x" * 15000,)))

    result = run(record, tmp_path, FakeClient([reply(), stopped()]), long_error)
    assert result["production_outcome"] == "valid_bridge"
    assert len(result["last_verification"]["visible"]["errors"][0]) == 15000
    feedback = next(event["body"] for event in events(tmp_path) if event["event"] == "feedback")
    assert feedback["visible"]["feedback_truncated"]
    assert len(feedback["visible"]["errors"][0]) == 10000


def test_both_verified_stops_without_extra_requests_and_preserves_bytes(record, tmp_path):
    client, checker = FakeClient([reply()]), FakeChecker()
    result = run(record, tmp_path, client, checker)
    assert result["status"] == "both_verified"
    assert result["bridge_eligible_pending_audit"] and result["visible_solved"]
    assert result["requests"] == result["revisions"] == len(client.create_calls) == 1
    assert (tmp_path / "artifacts/selected_bridge/Bridge.lean").read_bytes() == BRIDGE.encode()
    assert result["selected_bridge"]["sha256"] == sha(BRIDGE.encode())
    assert result["cost_usd_at_configured_rates"] == pytest.approx(0.00165)
    assert result["accounting_complete"] and not result["external_reservation_must_remain_open"]
    stored = json.loads((tmp_path / "artifacts/session.json").read_text())
    assert json.loads(json.dumps(result)) == stored
    assert checker.calls[0]["timeout_s"] <= 120


@pytest.mark.parametrize("visible", ("missing", "rejected"))
def test_valid_bridge_survives_absent_or_failed_visible_on_model_stop(record, tmp_path, visible):
    first = reply(solution=None if visible == "missing" else SOLUTION)
    client = FakeClient([first, stopped()])
    result = run(record, tmp_path, client, FakeChecker([("valid", visible)]))
    assert result["status"] == "model_stopped" and result["production_outcome"] == "valid_bridge"
    assert result["bridge_eligible_pending_audit"] and not result["visible_solved"]
    assert result["selected_bridge"]["revision"] == 1
    assert result["last_verification"]["visible"]["status"] == visible


def test_last_invalid_revision_replaces_earlier_valid_bridge_without_fallback(record, tmp_path):
    client = FakeClient([reply(), reply("invalid last bridge", identity="call2")])
    result = run(record, tmp_path, client, FakeChecker([("valid", "rejected"), ("rejected", "blocked_by_bridge")]),
                 replace(runner.production_config(), max_turns=2))
    assert result["status"] == "request_limit" and result["production_outcome"] == "invalid_bridge"
    assert result["revisions"] == 2 and result["selected_bridge"] is None
    assert not (tmp_path / "artifacts/selected_bridge").exists()
    assert (tmp_path / "artifacts/revisions/0001/Bridge.lean").read_text() == BRIDGE
    assert (tmp_path / "artifacts/revisions/0002/Bridge.lean").read_text() == "invalid last bridge"


def test_later_complete_valid_revision_is_selected_and_omission_removes_stale_solution(record, tmp_path):
    last_bridge = BRIDGE + "-- final version\n"
    client = FakeClient([reply(), reply(last_bridge, None, identity="call2"), stopped()])
    checker = FakeChecker([("rejected", "blocked_by_bridge"), ("valid", "missing")])
    result = run(record, tmp_path, client, checker)
    assert result["selected_bridge"]["revision"] == 2
    assert (tmp_path / "artifacts/selected_bridge/Bridge.lean").read_bytes() == last_bridge.encode()
    assert not (record.path / "Solution.lean").exists()
    assert (tmp_path / "artifacts/revisions/0001/Solution.lean").read_text() == SOLUTION
    assert not (tmp_path / "artifacts/revisions/0002/Solution.lean").exists()


@pytest.mark.parametrize("partial_tool", (True, False))
def test_truncated_response_is_not_checked_and_does_not_replace_complete_candidate(record, tmp_path, partial_tool):
    partial = reply("truncated source", stop="max_tokens", identity="call2") if partial_tool else stopped("max_tokens")
    client, checker = FakeClient([reply(), partial]), FakeChecker([("valid", "rejected")])
    result = run(record, tmp_path, client, checker)
    assert result["status"] == "output_limit" and result["revisions"] == len(checker.calls) == 1
    assert (tmp_path / "artifacts/selected_bridge/Bridge.lean").read_text() == BRIDGE
    assert any(event["event"] == "truncated_response_ignored" for event in events(tmp_path))


@pytest.mark.parametrize("reason", ("max_tokens", "end_turn", "refusal"))
def test_no_complete_submission_stays_absent_with_no_automatic_continuation(record, tmp_path, reason):
    client, checker = FakeClient([stopped(reason)]), FakeChecker()
    result = run(record, tmp_path, client, checker)
    assert result["production_outcome"] == "no_complete_submission"
    assert not result["bridge_eligible_pending_audit"]
    assert len(client.create_calls) == 1 and not checker.calls
    assert not (record.path / "Bridge.lean").exists()


@pytest.mark.parametrize("mutation", ("extra", "missing", "type", "tool", "multiple", "empty_id", "duplicate_id", "end_turn_tool", "unicode"))
def test_invalid_tool_output_cannot_rescue_prior_bridge(record, tmp_path, mutation):
    bad = reply(identity="call2")
    call = bad["content"][0]
    if mutation == "extra":
        call["input"]["holdout"] = "not allowed"
    elif mutation == "missing":
        call["input"].pop("solution_source")
    elif mutation == "type":
        call["input"]["bridge_source"] = None
    elif mutation == "tool":
        call["name"] = "read_file"
    elif mutation == "multiple":
        bad["content"].append(deepcopy(call))
    elif mutation == "empty_id":
        call["id"] = ""
    elif mutation == "duplicate_id":
        call["id"] = "call1"
    elif mutation == "end_turn_tool":
        bad["stop_reason"] = "end_turn"
    else:
        call["input"]["bridge_source"] = "\ud800"
    client = FakeClient([reply(), bad])
    result = run(record, tmp_path, client, FakeChecker([("valid", "rejected")]))
    assert result["status"] == "invalid_output"
    assert result["production_outcome"] == "invalid_protocol_output"
    assert not result["bridge_eligible_pending_audit"]
    assert result["accounting_complete"] and not result["infrastructure_failure"]
    assert result["revisions"] == 1 and len(client.create_calls) == 2


@pytest.mark.parametrize("mode", ("timeout", "usage_missing", "usage_bool", "overrun", "model", "shape", "unknown_block"))
def test_provider_failures_stop_admission_and_never_retry_or_transfer(record, tmp_path, mode):
    response = reply()
    if mode == "timeout":
        response = TimeoutError("uncertain inference")
    elif mode == "usage_missing":
        response["usage"].pop("input_tokens")
    elif mode == "usage_bool":
        response["usage"]["output_tokens"] = True
    elif mode == "overrun":
        response["usage"]["output_tokens"] = 16385
    elif mode == "model":
        response["model"] = "different-model"
    elif mode == "shape":
        response["content"] = "not a content list"
    else:
        response["content"] = [{"type": "server_tool_use", "name": "unknown"}]
    client = FakeClient([response])
    result = run(record, tmp_path, client)
    assert result["halt_admissions"] and result["infrastructure_failure"]
    assert result["production_outcome"] == "not_interpretable_infrastructure"
    assert not result["bridge_eligible_pending_audit"] and len(client.create_calls) == 1
    assert [event["event"] for event in events(tmp_path)].index("request") < [event["event"] for event in events(tmp_path)].index("infrastructure_failure")
    if mode in ("timeout", "usage_missing", "usage_bool", "overrun", "model"):
        assert result["external_reservation_must_remain_open"]
    if mode == "timeout":
        assert result["uncertain_request"] and result["output_reserved"] == 16384
        assert result["unresolved_charge_upper_estimate_usd"] > 0


@pytest.mark.parametrize("count", (True, -1, "100"))
def test_bad_native_counts_make_no_inference_request(record, tmp_path, count):
    client = FakeClient([], count=count)
    result = run(record, tmp_path, client)
    assert result["halt_admissions"] and result["requests"] == 0
    assert not client.create_calls


def test_count_exception_does_not_consume_or_leave_an_inference_reservation(record, tmp_path):
    client = FakeClient([], count_error=TimeoutError("count failed"))
    result = run(record, tmp_path, client)
    assert result["halt_admissions"] and result["requests"] == 0
    assert result["output_reserved"] == 0 and not result["uncertain_request"]
    assert result["accounting_complete"]


def test_budget_prevents_call_before_reserved_input_bound_is_exceeded(record, tmp_path):
    client = FakeClient([])
    result = run(record, tmp_path, client, config=replace(runner.production_config(), max_input_tokens=1000))
    assert result["status"] == "token_budget" and result["requests"] == 0
    assert not result["halt_admissions"] and not client.create_calls


def test_second_output_limit_uses_remaining_total_not_a_fresh_budget(record, tmp_path):
    client = FakeClient([reply(output=16384), stopped("max_tokens", output=3616)])
    result = run(record, tmp_path, client, FakeChecker([("valid", "rejected")]))
    assert [call["max_tokens"] for call in client.create_calls] == [16384, 3616]
    assert result["tokens"]["output_tokens"] == result["output_reserved"] == 20000
    assert result["status"] == "output_limit" and result["bridge_eligible_pending_audit"]


def test_request_and_checker_share_the_session_deadline(record, tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    client = FakeClient([reply()], on_count=lambda: now.__setitem__(0, 20.0),
                        on_create=lambda: now.__setitem__(0, 35.0))
    checker = FakeChecker()
    result = run(record, tmp_path, client, checker, replace(runner.production_config(), timeout_seconds=50))
    assert client.count_calls[0]["timeout"] == 30
    assert client.create_calls[0]["timeout"] == 30
    assert checker.calls[0]["timeout_s"] == 15
    assert result["status"] == "both_verified"


def test_counting_can_exhaust_session_without_admitting_an_inference_call(record, tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    client = FakeClient([], on_count=lambda: now.__setitem__(0, 601.0))
    result = run(record, tmp_path, client)
    assert result["status"] == "session_limit" and result["requests"] == 0
    assert result["output_reserved"] == 0 and not client.create_calls


def test_checker_failure_preserves_partial_bridge_but_does_not_admit_transfer(record, tmp_path):
    def broken(record, **kwargs):
        failure = VerificationInfrastructureError("visible_compile", "timeout", stdout="partial compiler log")
        failure.partial_bridge = ComponentReport("valid", sha(BRIDGE.encode()), "candidate_bridge")
        raise failure

    result = run(record, tmp_path, FakeClient([reply()]), broken)
    assert result["halt_admissions"] and not result["bridge_eligible_pending_audit"]
    event = next(event for event in events(tmp_path) if event["event"] == "infrastructure_failure")
    assert event["partial_bridge"]["status"] == "valid" and event["stdout"] == "partial compiler log"
    assert (tmp_path / "artifacts/revisions/0001/Bridge.lean").exists()
    assert result["accounting_complete"] and not result["uncertain_request"]


@pytest.mark.parametrize("drift", ("bytes", "base", "namespace", "axioms", "presence", "declaration", "blocked_bridge"))
def test_checker_report_integrity_is_not_assumed(record, tmp_path, drift):
    valid = FakeChecker()

    def broken(record, **kwargs):
        report = valid(record, **kwargs)
        if drift == "bytes":
            return replace(report, bridge=replace(report.bridge, source_sha256="0" * 64))
        if drift == "base":
            return replace(report, base_hashes=())
        if drift == "namespace":
            return replace(report, namespace="Wrong.Namespace")
        if drift == "axioms":
            return replace(report, bridge=replace(report.bridge, axioms=("sorryAx",)))
        if drift == "declaration":
            return replace(report, bridge=replace(report.bridge, declaration="wrong_theorem"))
        if drift == "blocked_bridge":
            return replace(report, bridge=replace(report.bridge, status="blocked_by_bridge"))
        return replace(report, visible=replace(report.visible, status="missing"))

    result = run(record, tmp_path, FakeClient([reply()]), broken)
    assert result["halt_admissions"] and result["selected_bridge"] is None


def test_workspace_tampering_stops_before_any_later_provider_call(record, tmp_path):
    def mutate():
        (record.path / "World/Base.lean").write_text("mutated base")

    client = FakeClient([reply()])
    result = run(record, tmp_path, client, FakeChecker(on_check=mutate))
    assert result["halt_admissions"] and len(client.create_calls) == 1
    assert not result["bridge_eligible_pending_audit"]


@pytest.mark.parametrize("kind", ("existing_artifacts", "existing_output", "artifacts_inside", "sdk_retries"))
def test_session_admission_never_overwrites_existing_work_or_uses_implicit_retries(record, tmp_path, kind):
    client = FakeClient([])
    artifacts = tmp_path / "artifacts"
    if kind == "existing_artifacts":
        artifacts.mkdir()
        (artifacts / "mine.txt").write_text("keep")
    elif kind == "existing_output":
        (record.path / "Bridge.lean").write_text("keep")
    elif kind == "artifacts_inside":
        artifacts = record.path / "artifacts"
    else:
        client.max_retries = 2
    with pytest.raises((ValueError, FileExistsError)):
        runner.run_production_session(record, namespace=NS, artifacts=artifacts,
                                      config=runner.production_config(), client=client)
    assert not client.count_calls and not client.create_calls
    if kind == "existing_artifacts":
        assert (artifacts / "mine.txt").read_text() == "keep"
    elif kind == "existing_output":
        assert (record.path / "Bridge.lean").read_text() == "keep"


def test_provider_trace_contains_only_visible_inputs_and_its_own_feedback(record, tmp_path):
    first = reply()
    first["content"].insert(0, {"type": "thinking", "thinking": "synthetic thinking", "signature": "opaque-signature"})
    client = FakeClient([first, stopped()])
    run(record, tmp_path, client, FakeChecker([("valid", "rejected")]))
    for call in (*client.count_calls, *client.create_calls):
        encoded = json.dumps(call)
        assert not any(secret in encoded for secret in ("Holdout", "Hidden/", "Oracle.lean", "metadata.json", str(tmp_path)))
        assert set(call["tools"][0]["input_schema"]["properties"]) == {"bridge_source", "solution_source"}
        assert call["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    second_messages = client.create_calls[1]["messages"]
    assert second_messages[1]["content"][0] == first["content"][0]
    feedback = json.loads(second_messages[2]["content"][0]["content"])
    assert set(feedback) == {"bridge", "visible"} and feedback["bridge"]["valid"]
    trace = events(tmp_path)
    assert [event["seq"] for event in trace] == list(range(1, len(trace) + 1))
    assert all("at" in event and event["elapsed_seconds"] >= 0 for event in trace)
    assert [event["event"] for event in trace][-1] == "session_finished"
    request_events = [event for event in trace if event["event"] == "request"]
    for event, call in zip(request_events, client.create_calls):
        assert {**event["body"], "timeout": event["timeout_seconds"]} == call
    assert len(request_events[0]["body"]["messages"]) == 1  # No aliasing of later history.
    host_input = json.loads((tmp_path / "artifacts/input.json").read_text())
    assert host_input["checker_injected"] and host_input["client_class"].endswith("FakeClient")


@pytest.mark.parametrize("change", ({"max_turns": 13}, {"max_turns": True}, {"timeout_seconds": float("nan")},
                                     {"aws_profile": "other"}, {"model": "different"}, {"output_per_request": 20000}))
def test_invalid_or_out_of_scope_config_does_not_touch_provider(record, tmp_path, change):
    client = FakeClient([])
    with pytest.raises(ValueError):
        run(record, tmp_path, client, config=replace(runner.production_config(), **change))
    assert not client.count_calls and not client.create_calls


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("world", WORLDS)
def test_synthetic_provider_submission_uses_real_new_lean_contract(tmp_path, world):
    """Known oracle fixture is instrumentation, never a model-generated bridge."""
    record = materialize_production_proposer(world, "D", tmp_path / "workspace")
    ns = json.loads((world / "metadata.json").read_text())["roles"]["namespace"]
    bridge = (world / "Hidden/Oracle.lean").read_text().replace("oracle_bridge", "candidate_bridge")
    solution = (closure_v3(world, "visible", "oracle").replace("World.ChallengeEvaluation", "World.ChallengeVisible")
                .replace("evaluation_solution", "candidate_solution").replace("oracle_bridge", "candidate_bridge"))
    client = FakeClient([reply(bridge, solution)])
    result = runner.run_production_session(record, namespace=ns, artifacts=tmp_path / "artifacts",
                                           config=runner.production_config(), client=client)
    assert result["status"] == "both_verified", result
    assert result["selected_bridge"]["declaration"] == f"{ns}.candidate_bridge"
    assert (tmp_path / "artifacts/selected_bridge/Bridge.lean").read_bytes() == bridge.encode()
