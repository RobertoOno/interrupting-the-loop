"""Program 3 world generation, isolation, and telemetry tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from creative_machine.formal_routes import (
    EvaluatorCondition,
    ProposerArm,
    WorldSpec,
    audit_workspace,
    build_world,
    materialize_evaluator,
    materialize_proposer,
    scan_forbidden_lean,
    validate_world,
    verify_evaluator_solution,
    verify_submission,
    write_world,
)
from creative_machine.formal_routes.calibration import load_headroom_plan
from creative_machine.formal_routes.codex_runner import (
    CodexAgentConfig,
    build_codex_command,
    extract_lean_calls,
    extract_tokens,
    input_digest,
    parse_event_stream,
    sanitized_environment,
)
from creative_machine.formal_routes.telemetry import AttemptRecord, append_record


@pytest.mark.parametrize("template", ["T1", "T2"])
def test_generation_is_byte_deterministic(template: str):
    spec = WorldSpec(f"CAL_{template}_DEADBEEF", template, 0xDEADBEEF)
    first = build_world(spec)
    second = build_world(spec)
    assert first.files == second.files
    assert first.metadata == second.metadata
    assert first.metadata["eligible_for_main"] is False
    assert first.metadata["phase"] == "calibration"


def test_different_seed_changes_world():
    a = build_world(WorldSpec("CAL_T1_AAAAAAAA", "T1", 1))
    b = build_world(WorldSpec("CAL_T1_BBBBBBBB", "T1", 2))
    assert a.files["World/Base.lean"] != b.files["World/Base.lean"]


@pytest.mark.parametrize("template", ["T1", "T2"])
def test_manifest_and_static_validation_detect_tampering(tmp_path: Path, template: str):
    root = write_world(build_world(WorldSpec(f"CAL_{template}_12345678", template, 123)), tmp_path / template)
    report = validate_world(root)
    assert report.ok and report.static_ok and report.lean_ok is None
    base = root / "World/Base.lean"
    base.write_text(base.read_text() + "\n-- tampered\n")
    report = validate_world(root)
    assert not report.ok
    assert any("hash mismatch" in error for error in report.errors)


def test_world_write_is_idempotent_but_never_overwrites(tmp_path: Path):
    world = build_world(WorldSpec("CAL_T1_FEEDFACE", "T1", 9))
    root = write_world(world, tmp_path / "world")
    assert write_world(world, root) == root
    (root / "extra.txt").write_text("mine")
    with pytest.raises(FileExistsError):
        write_world(world, root)


def test_static_validation_rejects_unmanifested_files_and_symlinks(tmp_path: Path):
    root = write_world(build_world(WorldSpec("CAL_T1_BAD0C0DE", "T1", 10)), tmp_path / "world")
    (root / "unexpected.txt").write_text("not frozen")
    report = validate_world(root)
    assert any("unmanifested file" in error for error in report.errors)
    (root / "unexpected.txt").unlink()
    (root / "outside.txt").write_text("outside")
    (root / "linked.txt").symlink_to(root / "outside.txt")
    report = validate_world(root)
    assert any("symlink forbidden" in error for error in report.errors)


def test_proposer_allowlist_and_arm_sources(tmp_path: Path):
    world = write_world(build_world(WorldSpec("CAL_T1_ABCD1234", "T1", 7)), tmp_path / "world")
    for arm in ProposerArm:
        workspace = tmp_path / f"ws-{arm.value}"
        record = materialize_proposer(world, arm, workspace)
        files = {str(path.relative_to(workspace)) for path in workspace.rglob("*") if path.is_file()}
        assert "World/Base.lean" in files and "World/ChallengeVisible.lean" in files
        assert not any("Holdout" in name or name.startswith("Hidden/") for name in files)
        assert ("SOURCE.md" in files) is (arm is not ProposerArm.D0)
        assert audit_workspace(record) == []
    assert (tmp_path / "ws-D" / "SOURCE.md").read_text() == (world / "Sources/Relevant.md").read_text()
    assert (tmp_path / "ws-C2" / "SOURCE.md").read_text() == (world / "Sources/Sham.md").read_text()


def test_evaluator_gets_exactly_one_holdout_and_requested_bridge(tmp_path: Path):
    world = write_world(build_world(WorldSpec("CAL_T2_ABCD1234", "T2", 11)), tmp_path / "world")
    baseline = tmp_path / "baseline"
    materialize_evaluator(world, 1, EvaluatorCondition.NO_BRIDGE, baseline)
    assert (baseline / "World/ChallengeEvaluation.lean").is_file()
    assert not (baseline / "Bridge.lean").exists()
    assert "Holdout1Statement" in (baseline / "World/ChallengeEvaluation.lean").read_text()
    assert "Holdout2Statement" not in "\n".join(
        path.read_text() for path in baseline.rglob("*") if path.is_file()
    )
    assert "evaluation_solution" in (baseline / "TASK.md").read_text()
    oracle = tmp_path / "oracle"
    materialize_evaluator(world, 2, EvaluatorCondition.ORACLE_BRIDGE, oracle)
    assert (oracle / "Bridge.lean").is_file()
    assert "oracle_bridge" in (oracle / "Bridge.lean").read_text()


def test_codex_command_is_ephemeral_and_uses_restricted_profile(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\n")
    fake_codex.chmod(0o755)
    command = build_codex_command(
        workspace,
        tmp_path / "last.txt",
        CodexAgentConfig(codex_executable=str(fake_codex)),
    )
    rendered = " ".join(command)
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--sandbox" not in command
    assert 'default_permissions="p3_cell"' in command
    assert f'"{workspace.resolve()}"="write"' in rendered
    assert '":root"="deny"' in rendered
    assert "permissions.p3_cell.network.enabled=false" in command
    assert 'web_search="disabled"' in command


def test_codex_environment_does_not_forward_cloud_secrets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-for-agent")
    monkeypatch.setenv("OPENAI_API_KEY", "not-for-agent")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = sanitized_environment()
    assert env["PATH"] == "/usr/bin:/bin"
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "OPENAI_API_KEY" not in env


def test_codex_event_parsing_extracts_usage_and_lean_calls():
    stream = "\n".join(
        (
            '{"type":"thread.started","thread_id":"t"}',
            '{"type":"item.completed","item":{"id":"i","type":"command_execution",'
            '"command":"lake env lean Solution.lean","exit_code":0,"status":"completed"}}',
            '{"type":"turn.completed","usage":{"input_tokens":10,'
            '"cached_input_tokens":3,"output_tokens":7}}',
        )
    )
    events, errors = parse_event_stream(stream)
    assert not errors
    assert extract_tokens(events) == {
        "input_tokens": 10,
        "cached_input_tokens": 3,
        "output_tokens": 7,
    }
    calls = extract_lean_calls(events)
    assert len(calls) == 1 and calls[0]["exit_code"] == 0
    assert len(input_digest({"TASK.md": "a" * 64})) == 64


def test_frozen_headroom_plan_is_complete():
    root = Path(__file__).resolve().parent.parent
    plan = load_headroom_plan(
        root / "docs" / "p3" / "calibration_headroom_plan_v1.json",
        repository=root,
    )
    assert len(plan.cells) == 8
    assert plan.model == "gpt-5.6-sol"
    assert plan.reasoning_effort == "high"


def test_post_session_audit_detects_mutation_extra_file_and_symlink(tmp_path: Path):
    world = write_world(build_world(WorldSpec("CAL_T1_A0D17ED0", "T1", 12)), tmp_path / "world")
    workspace = tmp_path / "workspace"
    record = materialize_proposer(world, ProposerArm.D0, workspace)
    (workspace / "Bridge.lean").write_text("candidate output")
    (workspace / "Solution.lean").write_text("candidate output")
    assert audit_workspace(record) == []
    base = workspace / "World/Base.lean"
    base.write_text(base.read_text() + "\n-- changed\n")
    (workspace / "extra.lean").write_text("unexpected")
    (workspace / "linked.lean").symlink_to(base)
    errors = audit_workspace(record)
    assert any("immutable input changed" in error for error in errors)
    assert any("undeclared output" in error for error in errors)
    assert any("symlink forbidden" in error for error in errors)


def test_forbidden_scanner_covers_unsound_and_meta_escape_hatches():
    source = "axiom bad : False\nrun_tac do pure ()\n#eval IO.println \"x\"\nexample : True := by sorry"
    findings = scan_forbidden_lean(source)
    assert {"axiom", "run_tac", "#eval", "sorry"}.issubset(findings)
    assert scan_forbidden_lean("theorem safe : True := by exact True.intro") == []


def test_telemetry_is_stable_and_validated(tmp_path: Path):
    record = AttemptRecord(
        run_id="cal-001",
        world_id="CAL_T1_ABCD1234",
        phase="calibration",
        role="proposer",
        condition="D0",
        input_sha256="a" * 64,
        status="completed",
    )
    path = tmp_path / "attempts.jsonl"
    append_record(path, record)
    decoded = json.loads(path.read_text().strip())
    assert decoded["schema_version"] == 1 and decoded["world_id"] == record.world_id
    with pytest.raises(ValueError):
        AttemptRecord(
            run_id="bad",
            world_id="x",
            phase="main",
            role="evaluator",
            condition="no_bridge",
            input_sha256="b" * 64,
            status="completed",
        ).to_json()


@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean toolchain is not installed")
def test_valid_submission_compiles_and_is_axiom_free(tmp_path: Path):
    world = write_world(build_world(WorldSpec("CAL_T1_C001D00D", "T1", 21)), tmp_path / "world")
    workspace = tmp_path / "workspace"
    materialize_proposer(world, ProposerArm.D0, workspace)
    metadata = json.loads((world / "metadata.json").read_text())
    namespace = metadata["roles"]["namespace"]
    carries = metadata["roles"]["preservation_predicate"]
    chain = metadata["roles"]["chain_type"]
    halt = metadata["roles"]["halt_constructor"]
    step = metadata["roles"]["step_constructor"]
    (workspace / "Bridge.lean").write_text(
        f"""import World.Base

namespace {namespace}

universe u
theorem candidate_bridge {{α : Type u}} {{R : α → α → Prop}} {{P : α → Prop}}
    (h : {carries} R P) {{x z : α}}
    (route : {chain} R x z) (hx : P x) : P z := by
  induction route with
  | {halt} point => exact hx
  | {step} hxy tail ih => exact ih (h _ _ hxy hx)

end {namespace}
"""
    )
    (workspace / "Solution.lean").write_text(
        f"""import World.ChallengeVisible
import Bridge

namespace {namespace}

theorem candidate_solution : VisibleStatement := by
  intro α R P x y z h hxy route hx
  exact candidate_bridge h route (h x y hxy hx)

end {namespace}
"""
    )
    report = verify_submission(workspace, namespace=namespace, timeout_s=300)
    assert report.ok, report.errors
    assert report.bridge_declaration == f"{namespace}.candidate_bridge"
    assert report.solution_declaration == f"{namespace}.candidate_solution"


@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean toolchain is not installed")
def test_valid_evaluator_solution_compiles_and_is_axiom_free(tmp_path: Path):
    world = write_world(build_world(WorldSpec("CAL_T1_EA1A7001", "T1", 22)), tmp_path / "world")
    workspace = tmp_path / "workspace"
    materialize_evaluator(world, 1, EvaluatorCondition.ORACLE_BRIDGE, workspace)
    metadata = json.loads((world / "metadata.json").read_text())
    namespace = metadata["roles"]["namespace"]
    statement = metadata["roles"]["holdout_statements"][0]
    (workspace / "Solution.lean").write_text(
        f"""import World.ChallengeEvaluation
import Bridge

namespace {namespace}

theorem evaluation_solution : {statement} := by
  intro α R P x y z h first second hx
  exact oracle_bridge h second (oracle_bridge h first hx)

end {namespace}
"""
    )
    report = verify_evaluator_solution(
        workspace,
        namespace=namespace,
        statement=statement,
        bridge_supplied=True,
        timeout_s=300,
    )
    assert report.ok, report.errors
    assert report.declaration == f"{namespace}.evaluation_solution"


@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean toolchain is not installed")
@pytest.mark.parametrize("template", ["T1", "T2"])
def test_generated_world_passes_lean_quality_gates(tmp_path: Path, template: str):
    root = write_world(build_world(WorldSpec(f"CAL_{template}_CAFEBABE", template, 13)), tmp_path / template)
    report = validate_world(root, run_lean=True, timeout_s=300)
    assert report.ok, report.errors
