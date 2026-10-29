"""Offline adversarial traces; optional Lean integration, never live providers."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from creative_machine.formal_routes import production_audit_v1 as audit
from creative_machine.formal_routes import production_runner_v1 as runner
from creative_machine.formal_routes.calibration_review_v3 import closure_v3
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.production_contract_v1 import (
    BASE_FILES, ComponentReport, ProductionReport, VerificationInfrastructureError,
    materialize_production_proposer,
)
from creative_machine.formal_routes.transfer_analysis_v1 import blank_dataset, analyze, transfer_eligibility
from creative_machine.formal_routes.transfer_design_v1 import matrix, load_blueprint, encoded, sha

REPO = Path(__file__).resolve().parents[1]
CELLS = [c for c in matrix() if c["role"] == "proposer"]
BRIDGE = "import World.Base\ntheorem candidate_bridge : True := by trivial\n"
SOLUTION = "import World.ChallengeVisible\nimport Bridge\ntheorem candidate_solution : True := by trivial\n"
BAD = "BAD synthetic source"
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


def submission(bridge=BRIDGE, solution=SOLUTION, identity="call1", *, output=40):
    return {"model": "anthropic.claude-opus-5", "stop_reason": "tool_use",
        "usage": {"input_tokens": 100, "output_tokens": output},
        "content": [{"type": "thinking", "thinking": "fixture reasoning", "signature": "opaque-test-signature"},
                    {"type": "tool_use", "id": identity, "name": "check_submission",
                     "input": {"bridge_source": bridge, "solution_source": solution}}]}


def terminal(reason="end_turn"):
    response = submission()
    response.update(stop_reason=reason, content=[{"type": "text", "text": "synthetic terminal"}])
    return response


class FixtureClient:
    max_retries = 0

    def __init__(self, responses, count=100, on_count=None):
        self.responses = iter(responses)
        self.count = count
        self.on_count = on_count
        self.messages = self
        self.calls = 0

    def count_tokens(self, **kwargs):
        if self.on_count:
            self.on_count()
        if isinstance(self.count, Exception):
            raise self.count
        return SimpleNamespace(input_tokens=self.count)

    def create(self, **kwargs):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(model_dump=lambda **_: deepcopy(response))


def fixture_check(record, *, namespace, timeout_s):
    """Intentionally synthetic truth function, explicit in every audit report."""
    def component(rel, blocked=False):
        path = record.path / rel
        source = path.read_bytes() if path.exists() else None
        status = ("missing" if source is None else "blocked_by_bridge" if blocked else
                  "rejected" if source.startswith(b"BAD") else "valid")
        errors = () if status == "valid" else (("long feedback " * 2000,) if source and b"LONG" in source else ("fixture " + status,))
        return ComponentReport(status, sha(source) if source is not None else None,
            "candidate_bridge" if status == "valid" and rel == "Bridge.lean" else "candidate_solution" if status == "valid" else None,
            errors=errors, stdout="synthetic compiler output")
    bridge = component("Bridge.lean")
    return ProductionReport(bridge, component("Solution.lean", not bridge.valid),
                            tuple((rel, record.copied_hashes[rel]) for rel in BASE_FILES), namespace)


def create(tmp_path, responses=None, *, cell=CELLS[0], count=100, check=fixture_check, on_count=None):
    root = REPO / cell["world"]
    record = materialize_production_proposer(root, cell["arm"], tmp_path / "workspace")
    client = FixtureClient(responses or [submission()], count, on_count)
    result = runner.run_production_session(record, namespace="P3." + cell["world_id"],
        artifacts=tmp_path / "artifacts", config=runner.production_config(), client=client, checker=check)
    return result


def inspect(tmp_path, *, cell=CELLS[0], check=fixture_check, **kwargs):
    return audit.audit_proposer_trace(REPO, tmp_path / "artifacts", cell_id=cell["cell_id"],
                                      data_kind="synthetic", checker=check, **kwargs)


def rows(tmp_path):
    return [json.loads(line) for line in (tmp_path / "artifacts/events.jsonl").read_text().splitlines()]


def save_rows(tmp_path, values):
    (tmp_path / "artifacts/events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in values))


def save_json(tmp_path, rel, value):
    (tmp_path / "artifacts" / rel).write_text(json.dumps(value) + "\n")


def mutate_summary(tmp_path, key, value):
    events = rows(tmp_path)
    events[-1]["result"][key] = value
    save_json(tmp_path, "session.json", events[-1]["result"])
    save_rows(tmp_path, events)


@pytest.mark.parametrize("cell", CELLS)
def test_all_six_proposer_payloads_are_reconstructed_from_frozen_worlds(tmp_path, cell):
    create(tmp_path, cell=cell)
    result = inspect(tmp_path, cell=cell)
    assert result["status"] == "passed" and result["data_kind"] == "synthetic"
    assert result["verification"] == "synthetic_injected_checker"
    assert result["cell_projection"]["cell_id"] == cell["cell_id"]
    assert result["cell_projection"]["observation"]["visible_solved"]
    assert result["content_audit"] == "pending" and not result["recipient_admitted"]
    assert not result["batch_audit_passed"] and not result["inference_admitted"]
    assert transfer_eligibility(result["cell_projection"]["observation"]) == (None, "content_audit_pending")


@pytest.mark.parametrize("solution", (None, BAD, "BAD LONG", ""))
def test_bridge_can_survive_absent_or_rejected_visible_and_feedback_is_exact(tmp_path, solution):
    create(tmp_path, [submission(solution=solution), terminal()])
    result = inspect(tmp_path)
    obs = result["cell_projection"]["observation"]
    assert obs["production_outcome"] == "valid_bridge"
    assert obs["visible_solved"] == (solution == "")  # Synthetic checker accepts empty bytes.
    assert obs["selected_bridge_sha256"] == sha(BRIDGE.encode())


@pytest.mark.parametrize("reason", ("end_turn", "refusal", "max_tokens"))
def test_no_submission_is_observed_without_invented_revision(tmp_path, reason):
    create(tmp_path, [terminal(reason)])
    result = inspect(tmp_path)
    obs = result["cell_projection"]["observation"]
    assert obs["revisions"] == 0 and obs["last_bridge_status"] == "not_submitted"
    assert obs["content_audit"] == "not_applicable" and not result["rechecked_revisions"]
    assert transfer_eligibility(obs) == (False, "no_complete_submission")


@pytest.mark.parametrize("final_valid", (True, False))
def test_chronological_selection_never_restores_earlier_valid_revision(tmp_path, final_valid):
    last_bridge = BRIDGE + "-- last revision\n" if final_valid else BAD
    create(tmp_path, [submission(solution=BAD), submission(last_bridge, None, "call2"), terminal()])
    result = inspect(tmp_path)
    obs = result["cell_projection"]["observation"]
    assert obs["earlier_valid_bridge"] and obs["revisions"] == 2
    assert obs["selected_bridge_sha256"] == (sha(last_bridge.encode()) if final_valid else None)
    assert result["reconstructed_session"]["production_outcome"] == ("valid_bridge" if final_valid else "invalid_bridge")
    assert len(result["rechecked_revisions"]) == 2


def test_truncated_tool_is_ignored_but_previous_complete_candidate_remains(tmp_path):
    truncated = submission(BAD, identity="call2")
    truncated["stop_reason"] = "max_tokens"
    create(tmp_path, [submission(solution=BAD), truncated])
    result = inspect(tmp_path)
    assert result["cell_projection"]["observation"]["termination"] == "output_limit"
    assert result["cell_projection"]["observation"]["revisions"] == 1
    assert result["cell_projection"]["observation"]["selected_bridge_sha256"] == sha(BRIDGE.encode())


@pytest.mark.parametrize("bad_kind", ("duplicate", "extra", "type", "missing", "name", "multiple", "empty_id", "stop", "unicode"))
def test_invalid_protocol_suppresses_a_previously_valid_bridge(tmp_path, bad_kind):
    bad = submission(identity="call2")
    call = bad["content"][-1]
    if bad_kind == "duplicate": call["id"] = "call1"
    elif bad_kind == "extra": call["input"]["hidden"] = "payload"
    elif bad_kind == "type": call["input"]["solution_source"] = 42
    elif bad_kind == "missing": del call["input"]["solution_source"]
    elif bad_kind == "name": call["name"] = "shell"
    elif bad_kind == "multiple": bad["content"].append(deepcopy(call))
    elif bad_kind == "empty_id": call["id"] = ""
    elif bad_kind == "stop": bad["stop_reason"] = "end_turn"
    else: call["input"]["bridge_source"] = "\ud800"
    create(tmp_path, [submission(solution=BAD), bad])
    obs = inspect(tmp_path)["cell_projection"]["observation"]
    assert obs["production_outcome"] == "invalid_protocol_output" and obs["last_bridge_status"] == "valid"
    assert obs["selected_bridge_sha256"] is None and obs["content_audit"] == "not_applicable"


@pytest.mark.parametrize("limit", ("requests", "input", "output", "initial_input"))
def test_native_counts_budget_caps_and_normal_limit_terminations(tmp_path, limit):
    if limit == "requests":
        create(tmp_path, [submission(solution=BAD, identity=f"call{i}") for i in range(12)])
        expected = "request_limit"
    elif limit == "input":
        create(tmp_path, [submission(solution=BAD)], count=100000)
        expected = "token_budget"
    elif limit == "initial_input":
        create(tmp_path, count=200000)
        expected = "token_budget"
    else:
        create(tmp_path, [submission(solution=BAD, identity=f"call{i}", output=9999) for i in range(2)])
        expected = "token_budget"
    assert inspect(tmp_path)["reconstructed_session"]["status"] == expected


@pytest.mark.parametrize("where", ("before_count", "after_count"))
def test_session_deadline_reconstruction(tmp_path, monkeypatch, where):
    class Clock:
        value = calls = 0
        def monotonic(self):
            self.calls += 1
            if where == "before_count" and self.calls >= 3:
                self.value = 601
            return float(self.value)
    clock = Clock()
    monkeypatch.setattr(runner.time, "monotonic", clock.monotonic)
    create(tmp_path, on_count=lambda: setattr(clock, "value", 601))
    assert inspect(tmp_path)["reconstructed_session"]["status"] == "session_limit"


def test_cache_usage_is_conservatively_reserved_but_price_is_reconstructed(tmp_path):
    response = submission()
    response["usage"].update(cache_creation_input_tokens=50, cache_read_input_tokens=40, service_tier="standard")
    create(tmp_path, [response])
    result = inspect(tmp_path)["reconstructed_session"]
    assert result["cost_usd_at_configured_rates"] == pytest.approx((5.5 * 204 + 27.5 * 40) / 1e6)
    # Preserve the frozen float/ceil arithmetic: ceil(100 * 1.10) is 111.
    assert result["input_reserved"] == 1135 and result["output_reserved"] == 40


@pytest.mark.parametrize("key,value", (
    ("requests", 0), ("revisions", True), ("tokens", {"input_tokens": 0, "output_tokens": 0}),
    ("cost_usd_at_configured_rates", 0), ("input_reserved", 100), ("output_reserved", 16384),
    ("reported_models", []), ("status", "request_limit"), ("visible_solved", False),
    ("production_outcome", "invalid_bridge"), ("accounting_complete", False),
    ("uncertain_request", True), ("elapsed_seconds", -1), ("session_cost_ceiling_usd", 2),
))
def test_self_consistent_summary_and_final_event_are_not_their_own_evidence(tmp_path, key, value):
    create(tmp_path)
    mutate_summary(tmp_path, key, value)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


@pytest.mark.parametrize("event,key,value", (
    ("request", "counted_input", 99), ("request", "reservation", [1134, 16383]),
    ("count_finished", "input_tokens", True), ("count_started", "turn", 2),
    ("response", "duration_seconds", 1e9), ("request", "timeout_seconds", 301),
    ("request", "timeout_seconds", 1), ("feedback", "revision", 2),
    ("verification", "turn", 2), ("request_settled", "input_reserved", 100),
))
def test_malformed_events_fail_without_an_external_seal(tmp_path, event, key, value):
    create(tmp_path)
    values = rows(tmp_path)
    next(r for r in values if r["event"] == event)[key] = value
    save_rows(tmp_path, values)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


@pytest.mark.parametrize("mode", ("count_history", "generation_history", "tool_contract", "thinking_signature", "feedback", "raw_source"))
def test_rebuilds_exact_messages_tools_thinking_and_feedback(tmp_path, mode):
    create(tmp_path, [submission(solution=BAD), terminal()])
    values = rows(tmp_path)
    if mode == "count_history":
        next(r for r in values if r["event"] == "count_started")["body"]["messages"][0]["content"] += "leak"
    elif mode == "generation_history":
        next(r for r in values if r["event"] == "request")["body"]["messages"].append({"role": "user", "content": "Hidden/Oracle.lean"})
    elif mode == "tool_contract":
        next(r for r in values if r["event"] == "request")["body"]["tools"][0]["name"] = "shell"
    elif mode == "thinking_signature":
        next(r for r in values if r["event"] == "count_started" and r["turn"] == 2)["body"]["messages"][1]["content"][0]["signature"] = "rewritten"
    elif mode == "feedback":
        next(r for r in values if r["event"] == "feedback")["body"]["bridge"]["errors"] = ["invented hint"]
    else:
        next(r for r in values if r["event"] == "response")["body"]["content"][-1]["input"]["bridge_source"] += "changed"
    save_rows(tmp_path, values)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


@pytest.mark.parametrize("mode", ("duplicate_key", "nan", "float_overflow", "no_newline", "blank", "seq", "order", "clock", "utc", "extra_key", "extra_event"))
def test_strict_json_event_envelopes_and_complete_order(tmp_path, mode):
    create(tmp_path)
    path = tmp_path / "artifacts/events.jsonl"
    text = path.read_text()
    if mode == "duplicate_key": path.write_text(text.replace('"seq": 1', '"seq": 99, "seq": 1', 1))
    elif mode == "nan": path.write_text(text.replace('"elapsed_seconds": ', '"elapsed_seconds": NaN, "x": ', 1))
    elif mode == "float_overflow": path.write_text(text.replace('"elapsed_seconds": ', '"elapsed_seconds": 1e999, "x": ', 1))
    elif mode == "no_newline": path.write_text(text.rstrip("\n"))
    elif mode == "blank": path.write_text(text + "\n")
    else:
        values = rows(tmp_path)
        if mode == "seq": values[2]["seq"] = True
        elif mode == "order": values[1], values[2] = values[2], values[1]
        elif mode == "clock": values[2]["elapsed_seconds"] = 0
        elif mode == "utc": values[2]["at"] = "2026-09-08T03:00:00-03:00"
        elif mode == "extra_key": values[2]["hidden_hint"] = "extra"
        else:
            values.append(deepcopy(values[-1]))
            values[-1]["seq"] += 1
        save_rows(tmp_path, values)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


@pytest.mark.parametrize("mode", ("file", "empty_dir", "symlink", "hardlink", "missing", "source", "receipt"))
def test_exact_evidence_inventory_and_bytes(tmp_path, mode):
    create(tmp_path)
    root = tmp_path / "artifacts"
    if mode == "file": (root / "Hidden.lean").write_text("unexpected")
    elif mode == "empty_dir": (root / ".lake").mkdir()
    elif mode == "symlink": (root / "alias").symlink_to(root / "session.json")
    elif mode == "hardlink": os.link(root / "session.json", root / "alias")
    elif mode == "missing": (root / "revisions/0001/verification.json").unlink()
    elif mode == "source": (root / "revisions/0001/Bridge.lean").write_text("rewritten")
    else:
        artifact = json.loads((root / "selected_bridge/artifact.json").read_text())
        artifact["revision"] = 2
        save_json(tmp_path, "selected_bridge/artifact.json", artifact)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


def test_old_selected_bytes_cannot_replace_final_revision_even_with_rehashed_receipts(tmp_path):
    create(tmp_path, [submission(solution=BAD), submission(BRIDGE + "-- second\n", None, "call2"), terminal()])
    root = tmp_path / "artifacts"
    (root / "selected_bridge/Bridge.lean").write_bytes(BRIDGE.encode())
    artifact = json.loads((root / "selected_bridge/artifact.json").read_text())
    artifact.update(sha256=sha(BRIDGE.encode()), revision=1)
    save_json(tmp_path, "selected_bridge/artifact.json", artifact)
    mutate_summary(tmp_path, "selected_bridge", artifact)
    with pytest.raises(audit.TraceAuditError, match="last complete bridge"):
        inspect(tmp_path)


@pytest.mark.parametrize("key,value", (("arm", "O"), ("world_id", "historical"), ("messages", []), ("copied_hashes", {}),
                                      ("namespace", "Wrong"), ("system", "leaked instructions"), ("checker_injected", 1)))
def test_host_identity_and_input_binding(tmp_path, key, value):
    create(tmp_path)
    path = tmp_path / "artifacts/input.json"
    source = json.loads(path.read_text())
    source[key] = value
    save_json(tmp_path, "input.json", source)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path)


def test_no_smaller_configuration_or_cross_cell_relabelling(tmp_path):
    create(tmp_path)
    with pytest.raises(audit.TraceAuditError):
        inspect(tmp_path, cell=CELLS[1])
    source = json.loads((tmp_path / "artifacts/input.json").read_text())
    source["config"]["output_per_request"] = 8192
    save_json(tmp_path, "input.json", source)
    with pytest.raises(audit.TraceAuditError, match="exact development configuration"):
        inspect(tmp_path)


def test_fresh_checker_detects_false_acceptance_in_internally_consistent_trace(tmp_path):
    def lying(record, **kwargs):
        report = fixture_check(record, **kwargs)
        return replace(report, bridge=replace(report.bridge, status="valid", declaration="candidate_bridge", errors=()),
                       visible=replace(report.visible, status="valid", declaration="candidate_solution", errors=()))
    create(tmp_path, [submission(BAD)], check=lying)
    with pytest.raises(audit.TraceAuditError, match="fresh Lean verification"):
        inspect(tmp_path)


def test_fresh_checker_diagnostics_cannot_silently_rewrite_feedback(tmp_path):
    create(tmp_path, [submission(solution=BAD), terminal()])
    def changed(record, **kwargs):
        report = fixture_check(record, **kwargs)
        return replace(report, visible=replace(report.visible, errors=("different instruction",)))
    with pytest.raises(audit.TraceAuditError, match="fresh Lean verification"):
        inspect(tmp_path, check=changed)


def test_nondeterministic_nonfeedback_stdout_is_preserved_but_not_compared(tmp_path):
    create(tmp_path)
    def other_stdout(record, **kwargs):
        report = fixture_check(record, **kwargs)
        return replace(report, bridge=replace(report.bridge, stdout="new build timing /temp/path"))
    result = inspect(tmp_path, check=other_stdout)
    assert result["rechecked_revisions"][0]["report"]["bridge"]["stdout"] == "new build timing /temp/path"
    assert result["reconstructed_session"]["last_verification"]["bridge"]["stdout"] == "synthetic compiler output"


def test_fresh_check_has_no_prior_outputs_or_cache_and_cannot_modify_raw_evidence(tmp_path):
    create(tmp_path, [submission(solution=BAD), submission(solution=None, identity="call2"), terminal()])
    seen = []
    def checker(record, **kwargs):
        assert record.path != tmp_path / "workspace" and record.path not in seen
        seen.append(record.path)
        assert not (record.path / ".lake").exists()
        assert not (record.path / "Hidden").exists()
        if len(seen) == 2:
            assert not (record.path / "Solution.lean").exists()
        return fixture_check(record, **kwargs)
    inspect(tmp_path, check=checker)
    assert len(seen) == 2
    def mutating(record, **kwargs):
        (tmp_path / "artifacts/input.json").write_text("changed during audit")
        return fixture_check(record, **kwargs)
    with pytest.raises(audit.TraceAuditError, match="changed during audit"):
        inspect(tmp_path, check=mutating)


@pytest.mark.parametrize("kind", ("count", "inference", "usage", "model", "shape", "checker", "fresh_checker"))
def test_all_technical_cases_block_scoring_and_external_reservation_release(tmp_path, kind):
    response = submission()
    check, count = fixture_check, 100
    if kind == "count": count = TimeoutError("native counter unavailable")
    elif kind == "inference": response = TimeoutError("unknown charge")
    elif kind == "usage": del response["usage"]
    elif kind == "model": response["model"] = "unknown"
    elif kind == "shape": response["stop_reason"] = "unknown"
    elif kind == "checker":
        def check(*args, **kwargs): raise VerificationInfrastructureError("compile", "resource failure")
    create(tmp_path, [response], count=count, check=check)
    if kind == "fresh_checker":
        def check(*args, **kwargs): raise VerificationInfrastructureError("compile", "fresh timeout")
    with pytest.raises(audit.TraceAuditBlocked):
        inspect(tmp_path, check=check)


def test_seal_binds_identity_bytes_data_kind_and_final_plan_separately(tmp_path):
    create(tmp_path)
    manifest = audit.build_evidence_manifest(REPO, tmp_path / "artifacts", cell_id=CELLS[0]["cell_id"], data_kind="synthetic")
    digest = sha(encoded(manifest))
    assert inspect(tmp_path, expected_evidence_sha256=digest)["evidence_manifest"] == manifest
    response_path = tmp_path / "artifacts/events.jsonl"
    response_path.write_text(response_path.read_text().replace("fixture reasoning", "other reasoning"))
    with pytest.raises(audit.TraceAuditError, match="external evidence seal"):
        inspect(tmp_path, expected_evidence_sha256=digest)


@pytest.mark.parametrize("mode", ("no_plan", "no_seal", "blueprint_as_plan", "injected", "synthetic_label"))
def test_experimental_mode_cannot_promote_test_traces_or_missing_admission_references(tmp_path, mode):
    create(tmp_path)
    kwargs = {"cell_id": CELLS[0]["cell_id"], "data_kind": "experimental"}
    if mode != "no_plan": kwargs["execution_plan_sha256"] = "a" * 64
    if mode == "blueprint_as_plan": kwargs["execution_plan_sha256"] = sha((REPO / audit.BLUEPRINT_PATH).read_bytes())
    if mode == "injected": kwargs["checker"] = fixture_check
    if mode in {"injected", "synthetic_label"}:
        manifest = audit.build_evidence_manifest(REPO, tmp_path / "artifacts", **{k: v for k, v in kwargs.items() if k != "checker"})
        kwargs["expected_evidence_sha256"] = sha(encoded(manifest))
    with pytest.raises(audit.TraceAuditError):
        audit.audit_proposer_trace(REPO, tmp_path / "artifacts", **kwargs)


def test_auditor_never_calls_runner_budget_or_request_helpers(tmp_path, monkeypatch):
    create(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError("audit reused runner logic")
    monkeypatch.setattr(runner, "run_production_session", forbidden)
    monkeypatch.setattr(runner, "build_production_request", forbidden)
    monkeypatch.setattr(runner, "_feedback", forbidden)
    monkeypatch.setattr(runner.TokenBudget, "reserve", forbidden)
    monkeypatch.setattr(runner.TokenBudget, "settle", forbidden)
    assert inspect(tmp_path)["status"] == "passed"


def test_projection_is_accepted_by_analysis_but_cannot_admit_incomplete_batch(tmp_path):
    create(tmp_path)
    report = inspect(tmp_path)
    blueprint = load_blueprint(REPO)
    dataset = blank_dataset(blueprint, data_kind="synthetic")
    dataset["cells"] = [report["cell_projection"] if c["cell_id"] == CELLS[0]["cell_id"] else c for c in dataset["cells"]]
    result = analyze(blueprint, dataset)
    assert result["status"] == "not_interpretable"
    assert result["world_results"] is None and result["experimental_decision"] is None


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
@pytest.mark.parametrize("world_index", (0, 1))
def test_real_lean_rechecks_known_fixture_in_each_family(tmp_path, world_index):
    cell = next(c for c in CELLS if c["family"] == ("invariant", "representation")[world_index] and c["arm"] == "D")
    root = REPO / cell["world"]
    bridge = (root / "Hidden/Oracle.lean").read_text().replace("oracle_bridge", "candidate_bridge")
    solution = (closure_v3(root, "visible", "oracle").replace("World.ChallengeEvaluation", "World.ChallengeVisible")
                .replace("evaluation_solution", "candidate_solution").replace("oracle_bridge", "candidate_bridge"))
    create(tmp_path, [submission(bridge, solution)], cell=cell, check=None)
    result = inspect(tmp_path, cell=cell, check=None)
    assert result["verification"] == "fresh_sandboxed_Lean_per_revision"
    assert result["cell_projection"]["observation"]["visible_solved"]
    assert result["data_kind"] == "synthetic" and result["content_audit"] == "pending"


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_rejects_consistent_but_false_synthetic_claim(tmp_path):
    # True is a valid bridge, but this candidate_solution is not the world's G0.
    create(tmp_path)
    with pytest.raises(audit.TraceAuditError, match="fresh Lean verification"):
        inspect(tmp_path, check=None)


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_real_lean_rechecks_rejections_and_a_valid_bridge_without_visible_solution(tmp_path):
    create(tmp_path, [submission(BAD), submission(BRIDGE, SOLUTION, "call2"),
                      submission(BRIDGE, None, "call3"), terminal()], check=None)
    result = inspect(tmp_path, check=None)
    assert [r["report"]["bridge"]["status"] for r in result["rechecked_revisions"]] == ["rejected", "valid", "valid"]
    obs = result["cell_projection"]["observation"]
    assert obs["earlier_valid_bridge"] and not obs["visible_solved"]
    assert obs["selected_bridge_sha256"] == sha(BRIDGE.encode()) and obs["content_audit"] == "pending"
