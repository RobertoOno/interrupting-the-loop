"""Behavioral calibration orchestration for Program 3A."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .codex_runner import (
    CodexAgentConfig,
    codex_cli_version,
    input_digest,
    output_hashes,
    resolve_codex,
    run_codex_session,
    sha256_file,
)
from .submission import verify_evaluator_solution
from .telemetry import AttemptRecord
from .workspace import EvaluatorCondition, audit_workspace, materialize_evaluator

HEADROOM_PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HeadroomCell:
    ordinal: int
    cell_id: str
    world: str
    world_id: str
    holdout: int
    condition: str


@dataclass(frozen=True)
class LoadedHeadroomPlan:
    path: Path
    repository: Path
    plan_id: str
    model: str
    reasoning_effort: str
    timeout_seconds: float
    max_parallel: int
    expected_cli_version: str
    expected_codex_sha256: str
    prompt: str
    prompt_sha256: str
    cells: tuple[HeadroomCell, ...]
    raw: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def load_headroom_plan(path: Path | str, *, repository: Path | str) -> LoadedHeadroomPlan:
    plan_path = Path(path).resolve()
    repo = Path(repository).resolve()
    data = _read_json(plan_path)
    if data.get("schema_version") != HEADROOM_PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported headroom plan schema")
    agent = data.get("agent")
    if not isinstance(agent, dict):
        raise ValueError("agent configuration missing from plan")
    prompt = agent.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("agent prompt missing from plan")
    expected_prompt_hash = agent.get("prompt_sha256")
    observed_prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if expected_prompt_hash != observed_prompt_hash:
        raise ValueError("plan prompt hash mismatch")

    world_entries = data.get("worlds")
    if not isinstance(world_entries, list) or len(world_entries) != 2:
        raise ValueError("headroom plan must contain exactly two calibration worlds")
    worlds: dict[str, str] = {}
    for item in world_entries:
        if not isinstance(item, dict):
            raise ValueError("invalid world entry")
        rel = item.get("path")
        world_id = item.get("world_id")
        if not isinstance(rel, str) or not isinstance(world_id, str):
            raise ValueError("world entry requires path and world_id")
        root = (repo / rel).resolve()
        if not root.is_relative_to(repo):
            raise ValueError(f"world escapes repository: {rel}")
        metadata = _read_json(root / "metadata.json")
        if metadata.get("world_id") != world_id:
            raise ValueError(f"world id mismatch: {rel}")
        if metadata.get("phase") != "calibration" or metadata.get("eligible_for_main") is not False:
            raise ValueError(f"world is not permanently excluded calibration material: {rel}")
        expected_manifest = item.get("manifest_sha256")
        if sha256_file(root / "manifest.sha256") != expected_manifest:
            raise ValueError(f"world manifest drift: {rel}")
        worlds[world_id] = rel

    cells_data = data.get("cells")
    if not isinstance(cells_data, list) or len(cells_data) != 8:
        raise ValueError("headroom plan must contain exactly eight cells")
    cells: list[HeadroomCell] = []
    seen_ids: set[str] = set()
    combinations: set[tuple[str, int, str]] = set()
    for item in cells_data:
        if not isinstance(item, dict):
            raise ValueError("invalid cell entry")
        cell = HeadroomCell(
            ordinal=int(item["ordinal"]),
            cell_id=str(item["cell_id"]),
            world=str(item["world"]),
            world_id=str(item["world_id"]),
            holdout=int(item["holdout"]),
            condition=str(item["condition"]),
        )
        if cell.cell_id in seen_ids:
            raise ValueError(f"duplicate cell id: {cell.cell_id}")
        if cell.world_id not in worlds or worlds[cell.world_id] != cell.world:
            raise ValueError(f"unknown world in cell: {cell.cell_id}")
        if cell.holdout not in {1, 2}:
            raise ValueError(f"invalid holdout in cell: {cell.cell_id}")
        if cell.condition not in {
            EvaluatorCondition.NO_BRIDGE.value,
            EvaluatorCondition.ORACLE_BRIDGE.value,
        }:
            raise ValueError(f"invalid condition in cell: {cell.cell_id}")
        seen_ids.add(cell.cell_id)
        combinations.add((cell.world_id, cell.holdout, cell.condition))
        cells.append(cell)
    expected_combinations = {
        (world_id, holdout, condition.value)
        for world_id in worlds
        for holdout in (1, 2)
        for condition in (EvaluatorCondition.NO_BRIDGE, EvaluatorCondition.ORACLE_BRIDGE)
    }
    if combinations != expected_combinations:
        raise ValueError("headroom cell matrix is incomplete or duplicated")
    if sorted(cell.ordinal for cell in cells) != list(range(1, 9)):
        raise ValueError("headroom cell ordinals must be exactly 1..8")
    cells.sort(key=lambda cell: cell.ordinal)

    return LoadedHeadroomPlan(
        path=plan_path,
        repository=repo,
        plan_id=str(data["plan_id"]),
        model=str(agent["model"]),
        reasoning_effort=str(agent["reasoning_effort"]),
        timeout_seconds=float(agent["timeout_seconds"]),
        max_parallel=int(agent["max_parallel"]),
        expected_cli_version=str(agent["codex_cli_version"]),
        expected_codex_sha256=str(agent["codex_executable_sha256"]),
        prompt=prompt,
        prompt_sha256=expected_prompt_hash,
        cells=tuple(cells),
        raw=data,
    )


def assert_agent_environment(plan: LoadedHeadroomPlan, config: CodexAgentConfig) -> None:
    observed_version = codex_cli_version(config.codex_executable)
    if observed_version != plan.expected_cli_version:
        raise RuntimeError(
            f"Codex CLI drift: expected {plan.expected_cli_version!r}, observed {observed_version!r}"
        )
    observed_binary_hash = sha256_file(resolve_codex(config.codex_executable))
    if observed_binary_hash != plan.expected_codex_sha256:
        raise RuntimeError("Codex executable hash drift")


def _sandbox_command(
    workspace: Path,
    config: CodexAgentConfig,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    # Reuse the exact filesystem/network profile emitted by the agent adapter.
    from .codex_runner import (
        PERMISSION_PROFILE,
        filesystem_profile_override,
        sanitized_environment,
    )

    binary = resolve_codex(config.codex_executable)
    args = [
        str(binary),
        "sandbox",
        "-P",
        PERMISSION_PROFILE,
        "-C",
        str(workspace),
        "-c",
        filesystem_profile_override(workspace),
        "-c",
        f"permissions.{PERMISSION_PROFILE}.network.enabled=false",
        "--",
        *command,
    ]
    return subprocess.run(
        args,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
        env=sanitized_environment(),
        check=False,
    )


def preflight_cell_sandbox(
    workspace: Path | str,
    *,
    forbidden_probe: Path | str,
    config: CodexAgentConfig,
) -> dict[str, Any]:
    """Prove read isolation, write capability, Lean availability, and no network."""
    root = Path(workspace).resolve()
    forbidden = Path(forbidden_probe).resolve()
    if not forbidden.is_file():
        raise FileNotFoundError(forbidden)
    hidden = _sandbox_command(root, config, ["/bin/cat", str(forbidden)])
    write = _sandbox_command(
        root,
        config,
        ["/bin/sh", "-c", "touch .p3_sandbox_probe && rm .p3_sandbox_probe"],
    )
    lean = _sandbox_command(
        root,
        config,
        ["/bin/sh", "-c", "lake build World.ChallengeEvaluation"],
    )
    network = _sandbox_command(
        root,
        config,
        ["/usr/bin/curl", "-Is", "--max-time", "3", "https://example.com"],
    )
    report = {
        "hidden_read_denied": hidden.returncode != 0,
        "hidden_read_returncode": hidden.returncode,
        "workspace_write_ok": write.returncode == 0,
        "workspace_write_returncode": write.returncode,
        "lean_ok": lean.returncode == 0,
        "lean_returncode": lean.returncode,
        "network_denied": network.returncode != 0,
        "network_returncode": network.returncode,
    }
    report["ok"] = all(
        report[key]
        for key in ("hidden_read_denied", "workspace_write_ok", "lean_ok", "network_denied")
    )
    if not report["ok"]:
        raise RuntimeError(f"sandbox preflight failed: {json.dumps(report, sort_keys=True)}")
    return report


def _run_cell(
    cell: HeadroomCell,
    *,
    repository: Path,
    live_root: Path,
    config: CodexAgentConfig,
) -> tuple[int, dict[str, Any]]:
    cell_root = live_root / cell.cell_id
    if cell_root.exists():
        raise FileExistsError(f"cell directory already exists; no implicit reruns: {cell_root}")
    workspace = cell_root / "workspace"
    artifacts = cell_root / "artifacts"
    world = repository / cell.world
    record = materialize_evaluator(
        world,
        cell.holdout,
        cell.condition,
        workspace,
    )
    metadata = _read_json(world / "metadata.json")
    statement = metadata["roles"]["holdout_statements"][cell.holdout - 1]
    preflight = preflight_cell_sandbox(
        workspace,
        forbidden_probe=world / "Hidden" / "OracleChecks.lean",
        config=config,
    )
    session = run_codex_session(workspace, artifacts, config)
    audit_errors = audit_workspace(record)
    verification = verify_evaluator_solution(
        workspace,
        namespace=metadata["roles"]["namespace"],
        statement=statement,
        bridge_supplied=cell.condition == EvaluatorCondition.ORACLE_BRIDGE.value,
        timeout_s=300,
    )

    infrastructure_failure = False
    if session.timed_out and not session.turn_started:
        infrastructure_failure = True
    elif session.returncode not in {0, None} and not session.turn_started:
        infrastructure_failure = True
    elif session.event_errors and not session.events:
        infrastructure_failure = True

    solved = bool(verification.ok and not audit_errors and not infrastructure_failure)
    if infrastructure_failure:
        status = "infrastructure_failure"
    elif session.timed_out:
        status = "timeout"
    elif session.returncode != 0:
        status = "agent_process_error"
    elif audit_errors:
        status = "protocol_violation"
    elif solved:
        status = "solved"
    else:
        status = "unsolved"

    attempt = AttemptRecord(
        run_id=cell.cell_id,
        world_id=cell.world_id,
        phase="calibration",
        role="evaluator",
        condition=cell.condition,
        input_sha256=input_digest(record.copied_hashes),
        status=status,
        model=config.model,
        holdout=cell.holdout,
        infrastructure_failure=infrastructure_failure,
        target_solved=solved,
        tokens=session.tokens,
        elapsed_seconds=session.elapsed_seconds,
        lean_calls=session.lean_calls,
        output_hashes=output_hashes(workspace, record.allowed_outputs),
    )
    details = {
        "schema_version": 1,
        "ordinal": cell.ordinal,
        "cell": asdict(cell),
        "preflight": preflight,
        "session": {
            "returncode": session.returncode,
            "timed_out": session.timed_out,
            "turn_started": session.turn_started,
            "event_count": len(session.events),
            "event_errors": session.event_errors,
        },
        "workspace_audit_errors": audit_errors,
        "verification": asdict(verification),
        "attempt": json.loads(attempt.to_json()),
    }
    (cell_root / "record.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return cell.ordinal, details


def run_headroom_plan(
    plan: LoadedHeadroomPlan,
    *,
    repository: Path | str,
    live_root: Path | str,
    archive_root: Path | str | None = None,
    parallel: int | None = None,
) -> list[dict[str, Any]]:
    """Run all eight frozen headroom cells once, with no automatic retries."""
    repo = Path(repository).resolve()
    live = Path(live_root).resolve() / plan.plan_id
    if live.exists():
        raise FileExistsError(f"run set already exists; no implicit reruns: {live}")
    live.mkdir(parents=True)
    config = CodexAgentConfig(
        model=plan.model,
        reasoning_effort=plan.reasoning_effort,
        timeout_seconds=plan.timeout_seconds,
        expected_cli_version=plan.expected_cli_version,
        prompt=plan.prompt,
    )
    assert_agent_environment(plan, config)
    workers = parallel if parallel is not None else plan.max_parallel
    if workers < 1 or workers > plan.max_parallel:
        raise ValueError(f"parallel must be between 1 and frozen maximum {plan.max_parallel}")
    results: list[tuple[int, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="p3-headroom") as executor:
        futures = {
            executor.submit(
                _run_cell,
                cell,
                repository=repo,
                live_root=live,
                config=config,
            ): cell
            for cell in plan.cells
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item[0])
    attempts_path = live / "attempts.jsonl"
    attempts_path.write_text(
        "".join(
            json.dumps(item[1]["attempt"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in results
        ),
        encoding="utf-8",
    )
    (live / "plan.snapshot.json").write_text(
        json.dumps(plan.raw, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if archive_root is not None:
        archive = Path(archive_root).resolve() / plan.plan_id
        if archive.exists():
            raise FileExistsError(f"archive already exists: {archive}")
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(live, archive)
    return [item[1] for item in results]


def summarize_headroom(
    plan: LoadedHeadroomPlan,
    *,
    run_root: Path | str,
) -> dict[str, Any]:
    root = Path(run_root).resolve() / plan.plan_id
    records: list[dict[str, Any]] = []
    for cell in plan.cells:
        details = _read_json(root / cell.cell_id / "record.json")
        if details.get("cell", {}).get("cell_id") != cell.cell_id:
            raise ValueError(f"record/plan mismatch: {cell.cell_id}")
        world = plan.repository / cell.world
        metadata = _read_json(world / "metadata.json")
        statement = metadata["roles"]["holdout_statements"][cell.holdout - 1]
        verification = verify_evaluator_solution(
            root / cell.cell_id / "workspace",
            namespace=metadata["roles"]["namespace"],
            statement=statement,
            bridge_supplied=cell.condition == EvaluatorCondition.ORACLE_BRIDGE.value,
            timeout_s=300,
        )
        initial = details["attempt"]
        infrastructure_failure = bool(initial["infrastructure_failure"])
        terminal_failure = initial["status"] in {"timeout", "agent_process_error"}
        rescored_solved = bool(
            verification.ok
            and not details["workspace_audit_errors"]
            and not infrastructure_failure
            and not terminal_failure
        )
        if infrastructure_failure:
            rescored_status = "infrastructure_failure"
        elif terminal_failure:
            rescored_status = initial["status"]
        elif details["workspace_audit_errors"]:
            rescored_status = "protocol_violation"
        elif rescored_solved:
            rescored_status = "solved"
        else:
            rescored_status = "unsolved"
        records.append(
            {
                **details,
                "rescored_status": rescored_status,
                "rescored_target_solved": rescored_solved,
                "rescoring": {
                    "declaration": verification.declaration,
                    "errors": verification.errors,
                },
            }
        )
    valid = [item for item in records if not item["attempt"]["infrastructure_failure"]]
    matrix: dict[tuple[str, int], dict[str, bool]] = {}
    for item in valid:
        cell = item["cell"]
        key = (cell["world_id"], cell["holdout"])
        matrix.setdefault(key, {})[cell["condition"]] = bool(item["rescored_target_solved"])
    complete_pairs = [
        values
        for values in matrix.values()
        if {EvaluatorCondition.NO_BRIDGE.value, EvaluatorCondition.ORACLE_BRIDGE.value}
        <= set(values)
    ]
    baseline_successes = sum(
        values[EvaluatorCondition.NO_BRIDGE.value] for values in complete_pairs
    )
    oracle_successes = sum(
        values[EvaluatorCondition.ORACLE_BRIDGE.value] for values in complete_pairs
    )
    paired_gain = oracle_successes - baseline_successes
    denominator = len(complete_pairs)
    gate_passed = (
        denominator == 4
        and oracle_successes >= 3
        and baseline_successes <= 2
        and paired_gain >= 2
    )
    return {
        "schema_version": 2,
        "scoring": {
            "revision": "namespace-aware-v2",
            "reason": (
                "The original verifier only resolved a root-level evaluation_solution. "
                "The same frozen outputs were rescored accepting either the root or exact "
                "world namespace; no agent session was repeated."
            ),
            "model_sessions_repeated": 0,
        },
        "plan_id": plan.plan_id,
        "model": plan.model,
        "reasoning_effort": plan.reasoning_effort,
        "timeout_seconds": plan.timeout_seconds,
        "cells_total": len(records),
        "cells_valid": len(valid),
        "infrastructure_failures": len(records) - len(valid),
        "complete_pairs": denominator,
        "no_bridge_successes": baseline_successes,
        "oracle_bridge_successes": oracle_successes,
        "paired_gain_count": paired_gain,
        "mean_paired_gain": paired_gain / denominator if denominator else None,
        "calibration_gate_passed": gate_passed,
        "gate_rule": {
            "complete_pairs": 4,
            "oracle_bridge_successes_at_least": 3,
            "no_bridge_successes_at_most": 2,
            "paired_gain_count_at_least": 2,
        },
        "cells": [
            {
                "ordinal": item["ordinal"],
                "cell_id": item["cell"]["cell_id"],
                "world_id": item["cell"]["world_id"],
                "holdout": item["cell"]["holdout"],
                "condition": item["cell"]["condition"],
                "initial_status": item["attempt"]["status"],
                "initial_target_solved": item["attempt"]["target_solved"],
                "status": item["rescored_status"],
                "target_solved": item["rescored_target_solved"],
                "rescored": item["attempt"]["target_solved"] != item["rescored_target_solved"],
                "resolved_declaration": item["rescoring"]["declaration"],
                "verification_errors": item["rescoring"]["errors"],
                "infrastructure_failure": item["attempt"]["infrastructure_failure"],
                "tokens": item["attempt"]["tokens"],
                "elapsed_seconds": item["attempt"]["elapsed_seconds"],
            }
            for item in records
        ],
    }


def write_raw_manifest(run_root: Path | str, destination: Path | str) -> None:
    root = Path(run_root).resolve()
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        lines.append(f"{sha256_file(path)}  {path.relative_to(root)}")
    Path(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")
