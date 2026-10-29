"""Prospective recipient session component for the development transfer matrix.

This is not a batch launcher, admission gate or trace auditor.  A caller must
bind the exact cell/bridge, complete the proposer/content barrier, reserve the
external budget and supply an explicit no-retry client before experimental use.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Callable

from .bedrock_runner import BedrockAgentConfig, TokenBudget
from .calibration_worlds_v3 import load_v3
from .production_contract_v1 import (
    BridgeArtifact, ComponentReport, VerificationInfrastructureError,
    WorkspaceIntegrityError,
)
from .recipient_contract_v1 import RecipientReport, render_recipient, verify_recipient
from .submission import STANDARD_LEAN_AXIOMS
from .transfer_design_v1 import load_blueprint
from .workspace import WorkspaceRecord

VERSION = "p3_recipient_runner_v1"
SELECTION_POLICY = "last_complete_solution_no_valid_fallback_v1"
CHECK_TIMEOUT_SECONDS = 120.0
COUNT_TIMEOUT_SECONDS = 30.0
FEEDBACK_CHARS = 10_000
SYSTEM_PROMPT = """You are a Lean proof-solving agent in a controlled experiment.
All available files are in the user message. Follow TASK.md exactly, using Lean
4.33.1 and Std, without Mathlib. Work only on the supplied recipient target.
Use check_solution to submit the complete contents of Solution.lean. The field
is required and each complete call replaces the previous candidate. There is no
shell, external information, filesystem-reading tool or other task available.
Submit one tool call at a time. A verified proof ends the session immediately.
The FINAL candidate is the LAST complete check_solution, not the best or last
valid earlier revision. All revisions are recorded. Text outside a complete tool
submission does not replace the candidate. A malformed tool call invalidates the
session output. No automatic continuation follows an answer without a tool call
or a truncated response. Work within the fixed budget and prioritize a verifiable
proof. Any supplied bridge is immutable. Only standard propext, Quot.sound and
Classical.choice axiom dependencies are permitted. No admitted proofs, new axioms,
custom notation, hash commands, metaprogramming, unsafe declarations or edits to
supplied inputs. Only maxRecDepth/maxHeartbeats options may be adjusted. Source is
at most 100000 UTF-8 bytes. Mathematical helper lemmas are allowed.
"""
SOLUTION_TOOL = {
    "name": "check_solution",
    "description": "Replace Solution.lean with this complete source and verify the exact recipient target.",
    "input_schema": {
        "type": "object",
        "properties": {"solution_source": {"type": "string"}},
        "required": ["solution_source"],
        "additionalProperties": False,
    },
}
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
NORMAL_TERMINATIONS = {
    "proof_verified", "model_stopped", "output_limit", "token_budget",
    "request_limit", "session_limit",
}


def recipient_config() -> BedrockAgentConfig:
    """The proposed larger S16 regime; exact admission is a later layer."""
    return replace(BedrockAgentConfig(), output_per_request=16384, request_timeout_seconds=300.0)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def interface_hashes() -> dict[str, str]:
    return {
        "system": _sha(SYSTEM_PROMPT.encode()),
        "tool": _sha(_json(SOLUTION_TOOL).encode()),
        "selection_policy": _sha(SELECTION_POLICY.encode()),
    }


def build_recipient_request(messages: list[dict], config: BedrockAgentConfig) -> dict:
    """Return the exact shared native-count/inference body without aliases."""
    return {
        "model": config.model,
        "system": SYSTEM_PROMPT,
        "messages": deepcopy(messages),
        "tools": [deepcopy(SOLUTION_TOOL)],
        "output_config": {"effort": config.effort},
        "thinking": {"type": "adaptive"},
        "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
    }


def _write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _save_new(path: Path, value) -> None:
    _write_new(path, (_json(value) + "\n").encode())


def _validate_config(config: BedrockAgentConfig) -> None:
    for name in ("max_turns", "max_input_tokens", "max_output_tokens", "output_per_request"):
        value = getattr(config, name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"invalid configuration: {name}")
    for name in ("timeout_seconds", "request_timeout_seconds", "input_usd_per_million", "output_usd_per_million"):
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid configuration: {name}")
    if not all(isinstance(getattr(config, key), str) and getattr(config, key)
               for key in ("model", "effort", "aws_profile", "aws_region")):
        raise ValueError("model/provider configuration must be explicit")
    if (config.model != "anthropic.claude-opus-5" or config.effort != "high"
            or config.aws_profile != "main-account" or config.aws_region != "us-east-1"):
        raise ValueError("this development runner has no model/profile/region fallback")
    ceilings = {"max_turns": 12, "timeout_seconds": 600, "request_timeout_seconds": 300,
                "max_input_tokens": 200_000, "max_output_tokens": 20_000,
                "output_per_request": 16384}
    if any(getattr(config, name) > ceiling for name, ceiling in ceilings.items()):
        raise ValueError("configuration exceeds proposed development ceilings")


def _trusted_identity(repository: Path, cell_id: str) -> tuple[dict, str, str]:
    blueprint = load_blueprint(repository)
    cell = next((row for row in blueprint["cells"]
                 if row["cell_id"] == cell_id and row["role"] == "recipient"), None)
    if cell is None:
        raise WorkspaceIntegrityError("unknown development recipient cell")
    metadata = load_v3(repository / cell["world"], phase="calibration")
    namespace = metadata["roles"]["namespace"]
    statement = metadata["roles"]["holdout_statements"][cell["holdout"] - 1]
    return cell, namespace, statement


def _feedback(report: RecipientReport) -> dict:
    feedback = report.feedback()
    text = "\n".join(feedback["errors"])
    feedback["errors"] = [text[:FEEDBACK_CHARS]] if text else []
    feedback["feedback_truncated"] = len(text) > FEEDBACK_CHARS
    return feedback


def _validate_component(component: ComponentReport, *, source: bytes, namespace: str) -> None:
    if not isinstance(component, ComponentReport) or component.status not in {"rejected", "valid"}:
        raise WorkspaceIntegrityError("checker returned invalid solution status")
    if component.source_sha256 != _sha(source):
        raise WorkspaceIntegrityError("checker report does not bind submitted solution bytes")
    if (not isinstance(component.axioms, tuple) or not isinstance(component.errors, tuple)
            or not all(isinstance(item, str) for item in (*component.axioms, *component.errors))
            or not isinstance(component.stdout, str) or not isinstance(component.stderr, str)):
        raise WorkspaceIntegrityError("checker returned malformed solution diagnostics")
    allowed_names = {"evaluation_solution", namespace + ".evaluation_solution"}
    if component.valid:
        if (component.declaration not in allowed_names or component.errors
                or set(component.axioms) - set(STANDARD_LEAN_AXIOMS)):
            raise WorkspaceIntegrityError("checker accepted an unexpected theorem or axiom dependency")
    elif component.declaration is not None or component.axioms or not component.errors:
        raise WorkspaceIntegrityError("rejected solution has contradictory checker fields")


def _validate_bridge(component: ComponentReport, *, digest: str, namespace: str,
                     short: str, candidate: BridgeArtifact | None) -> None:
    if (not isinstance(component, ComponentReport) or not component.valid
            or component.source_sha256 != digest
            or not isinstance(component.axioms, tuple)
            or not isinstance(component.errors, tuple)
            or not all(isinstance(item, str) for item in (*component.axioms, *component.errors))
            or not isinstance(component.stdout, str) or not isinstance(component.stderr, str)
            or component.errors
            or set(component.axioms) - set(STANDARD_LEAN_AXIOMS)):
        raise WorkspaceIntegrityError("checker did not validate the immutable supplied bridge")
    if component.declaration not in {short, namespace + "." + short}:
        raise WorkspaceIntegrityError("checker returned unexpected immutable bridge declaration")
    if candidate is not None and component.declaration != candidate.declaration:
        raise WorkspaceIntegrityError("checker bridge declaration differs from bound artifact")


def _validate_report(report, *, record: WorkspaceRecord, repository: Path, cell_id: str,
                     candidate: BridgeArtifact | None, source: bytes) -> None:
    cell, namespace, statement = _trusted_identity(repository, cell_id)
    if (not isinstance(report, RecipientReport) or report.cell_id != cell_id
            or report.world_id != record.world_id or report.world_id != cell["world_id"]
            or report.namespace != namespace or report.statement != statement):
        raise WorkspaceIntegrityError("checker returned incompatible recipient identity or target")
    if (len(report.input_hashes) != len(record.copied_hashes)
            or dict(report.input_hashes) != record.copied_hashes):
        raise WorkspaceIntegrityError("checker report has different frozen recipient inputs")
    expected_bridge_hash = record.copied_hashes.get("Bridge.lean")
    if report.bridge_sha256 != expected_bridge_hash:
        raise WorkspaceIntegrityError("checker report has different bridge bytes")
    _validate_component(report.solution, source=source, namespace=namespace)
    if report.target_solved != report.solution.valid:
        raise WorkspaceIntegrityError("checker target outcome contradicts its solution report")
    if expected_bridge_hash is None:
        if report.bridge is not None:
            raise WorkspaceIntegrityError("baseline checker invented a bridge report")
    else:
        bridge = report.bridge
        expected_short = "candidate_bridge" if cell["bridge_kind"] == "candidate" else "oracle_bridge"
        _validate_bridge(bridge, digest=expected_bridge_hash, namespace=namespace,
                         short=expected_short, candidate=candidate)


def run_recipient_session(
    record: WorkspaceRecord, *, repository: Path, cell_id: str,
    candidate: BridgeArtifact | None, artifacts: Path,
    config: BedrockAgentConfig, client, checker: Callable | None = None,
) -> dict:
    """Run one fresh session with an explicit client and no implicit retries.

    Successful return is only raw session evidence. It does not prove the phase
    barrier, bridge-content approval, provider provenance or batch accounting.
    An uncaught storage error must leave the full external reservation open.
    """
    started = time.monotonic()
    _validate_config(config)
    if type(getattr(client, "max_retries", None)) is not int or client.max_retries != 0:
        raise ValueError("client must explicitly disable SDK retries")
    repository = Path(repository)
    cell, namespace, statement = _trusted_identity(repository, cell_id)
    initial = render_recipient(record, repository=repository, cell_id=cell_id, candidate=candidate)
    output_path = record.path / "Solution.lean"
    if output_path.exists() or output_path.is_symlink():
        raise WorkspaceIntegrityError("recipient session requires absent initial output")
    artifacts = Path(artifacts)
    visible_root, artifact_root = record.path.resolve(), artifacts.resolve()
    if visible_root == artifact_root or visible_root in artifact_root.parents or artifact_root in visible_root.parents:
        raise WorkspaceIntegrityError("artifacts and model workspace must be disjoint")
    if artifacts.is_symlink():
        raise WorkspaceIntegrityError("artifacts directory is a symlink")
    artifacts.mkdir(parents=True, exist_ok=False)
    _write_new(artifacts / "events.jsonl", b"")
    messages = [{"role": "user", "content": initial}]
    expected_output: bytes | None = None
    bridge_hash = record.copied_hashes.get("Bridge.lean")
    _save_new(artifacts / "input.json", {
        "version": VERSION, "config": asdict(config), "system": SYSTEM_PROMPT,
        "tools": [SOLUTION_TOOL], "messages": messages,
        "selection_policy": SELECTION_POLICY, "interface_hashes": interface_hashes(),
        "cell_id": cell_id, "world_id": record.world_id, "condition": record.condition,
        "holdout": cell["holdout"], "namespace": namespace, "statement": statement,
        "bridge_sha256": bridge_hash, "copied_hashes": record.copied_hashes,
        "checker_injected": checker is not None,
        "client_class": f"{type(client).__module__}.{type(client).__qualname__}",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    deadline = started + config.timeout_seconds
    budget = TokenBudget(config)
    usage = dict.fromkeys(USAGE_FIELDS, 0)
    sequence = requests = revisions = 0
    last_report: RecipientReport | None = None
    selected = None
    reported_models: list[str] = []
    status, error = "request_limit", None
    uncertainty = False
    accounting_complete = True
    unresolved_bound = 0.0
    active_reservation = None
    used_tool_ids: set[str] = set()

    def event(kind: str, **payload) -> None:
        nonlocal sequence
        sequence += 1
        body = {"seq": sequence, "event": kind,
                "at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": time.monotonic() - started, **payload}
        with (artifacts / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(_json(body) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def fail(phase: str, exc: Exception) -> None:
        nonlocal status, error
        status, error = "infrastructure_failure", f"{phase}: {type(exc).__name__}: {exc}"
        detail = {"phase": phase, "error": error}
        if isinstance(exc, VerificationInfrastructureError):
            detail.update(compiler_phase=exc.phase, stdout=exc.stdout, stderr=exc.stderr,
                          partial_bridge=asdict(exc.partial_bridge) if exc.partial_bridge else None)
        event("infrastructure_failure", **detail)

    def check_workspace() -> None:
        if render_recipient(record, repository=repository, cell_id=cell_id, candidate=candidate) != initial:
            raise WorkspaceIntegrityError("immutable recipient payload drift")
        if output_path.is_symlink():
            raise WorkspaceIntegrityError("recipient output became a symlink")
        actual = output_path.read_bytes() if output_path.exists() else None
        if actual != expected_output:
            raise WorkspaceIntegrityError("recipient working output changed outside the runner")

    event("session_started", selection_policy=SELECTION_POLICY)
    for turn in range(1, config.max_turns + 1):
        try:
            check_workspace()
        except Exception as exc:
            fail("workspace", exc)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "session_limit"
            break
        request = build_recipient_request(messages, config)
        count_timeout = min(COUNT_TIMEOUT_SECONDS, remaining)
        event("count_started", turn=turn, body=request, timeout_seconds=count_timeout)
        counted_at = time.monotonic()
        try:
            counted = client.messages.count_tokens(**deepcopy(request), timeout=count_timeout).input_tokens
            if type(counted) is not int or counted < 0:
                raise ValueError("invalid native input token count")
        except Exception as exc:
            fail("token_count", exc)
            break
        event("count_finished", turn=turn, input_tokens=counted,
              duration_seconds=time.monotonic() - counted_at)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "session_limit"
            break
        active_reservation = budget.reserve(counted)
        if active_reservation is None:
            status = "token_budget"
            break
        request["max_tokens"] = active_reservation[1]
        timeout = min(config.request_timeout_seconds, remaining)
        event("request", turn=turn, body=request, timeout_seconds=timeout,
              counted_input=counted, reservation=active_reservation)
        requests += 1
        requested_at = time.monotonic()
        uncertainty = True
        unresolved_bound = (active_reservation[0] * config.input_usd_per_million
                            + active_reservation[1] * config.output_usd_per_million) / 1_000_000
        try:
            response = client.messages.create(**deepcopy(request), timeout=timeout)
            payload = response.model_dump(mode="json", exclude_none=True)
            _json(payload)
        except Exception as exc:
            accounting_complete = False
            fail("inference_or_decode", exc)
            break
        event("response", turn=turn, body=payload,
              duration_seconds=time.monotonic() - requested_at)
        try:
            raw_usage = payload["usage"]
            if not isinstance(raw_usage, dict) or not {"input_tokens", "output_tokens"} <= set(raw_usage):
                raise ValueError("required usage is missing")
            for name in USAGE_FIELDS:
                value = raw_usage.get(name, 0)
                if type(value) is not int or value < 0:
                    raise ValueError(f"invalid usage field: {name}")
            billable_input_bound = (raw_usage["input_tokens"]
                                    + 2 * raw_usage.get("cache_creation_input_tokens", 0)
                                    + raw_usage.get("cache_read_input_tokens", 0))
            for name in USAGE_FIELDS:
                usage[name] += raw_usage.get(name, 0)
            budget.settle(active_reservation, billable_input_bound, raw_usage["output_tokens"])
        except Exception as exc:
            accounting_complete = False
            fail("usage_accounting", exc)
            break
        uncertainty, unresolved_bound = False, 0.0
        event("request_settled", turn=turn, tokens=raw_usage,
              input_reserved=budget.input_reserved, output_reserved=budget.output_reserved)
        response_model = payload.get("model")
        reported_models.append(response_model)
        if (not isinstance(response_model, str)
                or response_model.removeprefix("anthropic.") != config.model.removeprefix("anthropic.")):
            accounting_complete = False
            fail("response_model", ValueError("response model differs from requested model"))
            break
        content, reason = payload.get("content"), payload.get("stop_reason")
        if (not isinstance(content, list) or any(not isinstance(block, dict) for block in content)
                or reason not in ("tool_use", "end_turn", "max_tokens", "refusal")):
            fail("response_shape", ValueError("unknown or malformed response structure"))
            break
        if any(block.get("type") not in ("text", "thinking", "redacted_thinking", "tool_use")
               for block in content):
            fail("response_shape", ValueError("unsupported response block type"))
            break
        messages.append({"role": "assistant", "content": deepcopy(content)})
        if reason == "max_tokens":
            status = "output_limit"
            event("truncated_response_ignored", turn=turn)
            break
        calls = [block for block in content if block.get("type") == "tool_use"]
        if reason in ("end_turn", "refusal") and not calls:
            status = "model_stopped"
            break
        if reason != "tool_use" or len(calls) != 1:
            status, error = "invalid_output", "expected exactly one complete solution submission"
            break
        call = calls[0]
        arguments = call.get("input")
        if (call.get("name") != SOLUTION_TOOL["name"] or not isinstance(call.get("id"), str)
                or not call["id"] or call["id"] in used_tool_ids or not isinstance(arguments, dict)
                or set(arguments) != {"solution_source"}
                or not isinstance(arguments["solution_source"], str)):
            status, error = "invalid_output", "check_solution arguments or identity violate the contract"
            break
        used_tool_ids.add(call["id"])
        try:
            source = arguments["solution_source"].encode("utf-8")
        except UnicodeEncodeError:
            status, error = "invalid_output", "submitted source is not valid UTF-8"
            break
        revisions += 1
        last_report = None
        revision_dir = artifacts / "revisions" / f"{revisions:04d}"
        revision_dir.mkdir(parents=True, exist_ok=False)
        _write_new(revision_dir / "Solution.lean", source)
        _save_new(revision_dir / "submission.json", {
            "turn": turn, "tool_use_id": call["id"], "revision": revisions,
            "source_sha256": _sha(source),
        })
        event("submission", turn=turn, revision=revisions, source_sha256=_sha(source))
        try:
            check_workspace()
            output_path.write_bytes(source)
            expected_output = source
            check_workspace()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VerificationInfrastructureError("checker", "session deadline before verification")
            check_timeout = min(CHECK_TIMEOUT_SECONDS, remaining)
            event("verification_started", turn=turn, revision=revisions,
                  timeout_seconds=check_timeout)
            checked_at = time.monotonic()
            report = (checker or verify_recipient)(
                record, repository=repository, cell_id=cell_id, candidate=candidate,
                timeout_s=check_timeout,
            )
            _validate_report(report, record=record, repository=repository,
                             cell_id=cell_id, candidate=candidate, source=source)
            check_workspace()
        except Exception as exc:
            fail("checker", exc)
            break
        last_report = report
        _save_new(revision_dir / "verification.json", asdict(report))
        event("verification", turn=turn, revision=revisions, report=asdict(report),
              duration_seconds=time.monotonic() - checked_at)
        feedback = _feedback(report)
        event("feedback", turn=turn, revision=revisions, body=feedback)
        if report.target_solved:
            status = "proof_verified"
            break
        messages.append({"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": call["id"],
            "content": _json(feedback),
        }]})

    try:
        check_workspace()
        if status in NORMAL_TERMINATIONS and last_report is not None:
            if expected_output is None:
                raise WorkspaceIntegrityError("verified revision has no bound output bytes")
            selected_dir = artifacts / "selected_solution"
            selected_dir.mkdir(exist_ok=False)
            _write_new(selected_dir / "Solution.lean", expected_output)
            selected = {
                "revision": revisions,
                "relative_path": "selected_solution/Solution.lean",
                "sha256": _sha(expected_output),
                "status": last_report.solution.status,
                "declaration": last_report.solution.declaration,
            }
            _save_new(selected_dir / "artifact.json", selected)
    except Exception as exc:
        selected = None
        fail("final_integrity", exc)

    if status == "infrastructure_failure":
        recipient_outcome = "not_interpretable_infrastructure"
    elif status == "invalid_output":
        recipient_outcome = "invalid_protocol_output"
    elif last_report is not None and last_report.target_solved and status in NORMAL_TERMINATIONS:
        recipient_outcome = "verified"
    else:
        recipient_outcome = "not_solved"
    cost = (config.input_usd_per_million * (
                usage["input_tokens"] + 2 * usage["cache_creation_input_tokens"]
                + 0.1 * usage["cache_read_input_tokens"])
            + config.output_usd_per_million * usage["output_tokens"]) / 1_000_000
    result = {
        "version": VERSION, "status": status, "recipient_outcome": recipient_outcome,
        "selection_policy": SELECTION_POLICY, "requests": requests, "revisions": revisions,
        "last_verification": asdict(last_report) if last_report is not None else None,
        "selected_solution": selected, "target_solved": recipient_outcome == "verified",
        "bridge_sha256": bridge_hash, "infrastructure_failure": status == "infrastructure_failure",
        "halt_admissions": status == "infrastructure_failure", "error": error,
        "tokens": usage, "accounting_complete": accounting_complete,
        "external_reservation_must_remain_open": not accounting_complete,
        "uncertain_request": uncertainty,
        "unresolved_charge_upper_estimate_usd": unresolved_bound,
        "cost_usd_at_configured_rates": cost,
        "session_cost_ceiling_usd": config.reserved_cost_usd,
        "input_reserved": budget.input_reserved, "output_reserved": budget.output_reserved,
        "reported_models": reported_models, "elapsed_seconds": time.monotonic() - started,
        "cost_basis": "configured regional rates; cache writes conservatively at 1h rate; not an AWS invoice",
    }
    event("session_finished", result=result)
    _save_new(artifacts / "session.json", result)
    return result
