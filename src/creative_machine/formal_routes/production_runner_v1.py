"""Prospective proposer session component, not a batch launcher or admission gate.

The caller must freeze/review the experiment and reserve its daily/batch budget
before supplying a real client. This module never constructs one, queries a
sibling, selects a historical best bridge, or retries a request. Offline tests
inject both the client and (where appropriate) the proof checker.
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
import re
import time
from typing import Callable

from .bedrock_runner import BedrockAgentConfig, TokenBudget
from .production_contract_v1 import (
    BASE_FILES, OUTPUTS, ProductionReport, VerificationInfrastructureError,
    WorkspaceIntegrityError, bridge_artifact, render_production_proposer,
    verify_production,
)
from .workspace import WorkspaceRecord
from .submission import STANDARD_LEAN_AXIOMS

VERSION = "p3_production_runner_v1"
SELECTION_POLICY = "last_complete_submission_no_valid_fallback_v1"
CHECK_TIMEOUT_SECONDS = 120.0
COUNT_TIMEOUT_SECONDS = 30.0
FEEDBACK_CHARS_PER_COMPONENT = 10_000
SYSTEM_PROMPT = """You are a Lean proof-solving agent in a controlled experiment.
All available files are in the user message. Follow TASK.md exactly, using Lean
4.33.1 and Std, without Mathlib. Work only on the supplied visible task.
Use check_submission to submit complete Bridge.lean and Solution.lean contents.
Both fields are required; use null for solution_source to explicitly omit it.
Each call replaces both previous files. There is no shell, external information,
filesystem-reading tool, or other task available. Submit one tool call at a time.
The checker verifies the bridge and visible solution separately. You may revise
after a rejection. Verification of both ends the session immediately. A valid
bridge can remain eligible if the visible solution fails or is absent.
The FINAL candidate is the LAST complete check_submission, not the best or last
valid earlier revision. All revisions are recorded. Later invalid complete
submissions replace earlier valid ones. Text outside a complete tool submission
does not replace files. A malformed tool call invalidates the session output.
No automatic continuation follows an answer without a tool call or a truncated
response. Work within the fixed budget and prioritize verifiable outputs.
Only standard propext, Quot.sound, and Classical.choice axiom dependencies are
permitted. No admitted proofs, new axioms, custom notation, hash commands,
metaprogramming, unsafe declarations, or changes to supplied inputs. Only
maxRecDepth/maxHeartbeats options may be adjusted. Each source is at most
100000 UTF-8 bytes. Put only the reusable intermediary and its required helpers
in Bridge.lean, not the visible solution, source text, or conversation.
"""
SUBMISSION_TOOL = {
    "name": "check_submission",
    "description": "Replace both output files and check bridge and visible proof separately. Both valid ends the session.",
    "input_schema": {
        "type": "object",
        "properties": {"bridge_source": {"type": "string"},
                       "solution_source": {"type": ["string", "null"]}},
        "required": ["bridge_source", "solution_source"],
        "additionalProperties": False,
    },
}
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
NORMAL_TERMINATIONS = {"both_verified", "model_stopped", "output_limit", "token_budget", "request_limit", "session_limit"}


def production_config() -> BedrockAgentConfig:
    """Proposed S16 larger regime; actual batch admission must bind all fields."""
    return replace(BedrockAgentConfig(), output_per_request=16384, request_timeout_seconds=300.0)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def interface_hashes() -> dict[str, str]:
    return {"system": _sha(SYSTEM_PROMPT.encode()), "tool": _sha(_json(SUBMISSION_TOOL).encode()),
            "selection_policy": _sha(SELECTION_POLICY.encode())}


def build_production_request(messages: list[dict], config: BedrockAgentConfig) -> dict:
    """Shared native-count/inference body, reusable by the source-matching preflight."""
    return {"model": config.model, "system": SYSTEM_PROMPT, "messages": deepcopy(messages),
            "tools": [deepcopy(SUBMISSION_TOOL)], "output_config": {"effort": config.effort},
            "thinking": {"type": "adaptive"},
            "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}}


def _write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _save_new(path: Path, value) -> None:
    _write_new(path, (_json(value) + "\n").encode("utf-8"))


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
                "max_input_tokens": 200_000, "max_output_tokens": 20_000, "output_per_request": 16384}
    if any(getattr(config, name) > ceiling for name, ceiling in ceilings.items()):
        raise ValueError("configuration exceeds proposed development ceilings")


def _feedback(report: ProductionReport) -> dict:
    feedback = report.feedback()
    for component in feedback.values():
        text = "\n".join(component["errors"])
        component["errors"] = [text[:FEEDBACK_CHARS_PER_COMPONENT]] if text else []
        component["feedback_truncated"] = len(text) > FEEDBACK_CHARS_PER_COMPONENT
    return feedback


def _validate_report(report, record: WorkspaceRecord, namespace: str, sources: dict[str, bytes | None]) -> None:
    if not isinstance(report, ProductionReport) or report.namespace != namespace:
        raise WorkspaceIntegrityError("checker returned incompatible production report")
    expected_base = tuple((rel, record.copied_hashes[rel]) for rel in BASE_FILES)
    if report.base_hashes != expected_base:
        raise WorkspaceIntegrityError("checker report has different frozen base")
    for component, rel in ((report.bridge, "Bridge.lean"), (report.visible, "Solution.lean")):
        data = sources[rel]
        expected_name = "candidate_bridge" if rel == "Bridge.lean" else "candidate_solution"
        if component.source_sha256 != (None if data is None else _sha(data)):
            raise WorkspaceIntegrityError("checker report does not bind submitted bytes")
        if component.status not in ("missing", "rejected", "valid", "blocked_by_bridge"):
            raise WorkspaceIntegrityError("unknown checker component status")
        if (component.status == "missing") != (data is None):
            raise WorkspaceIntegrityError("checker presence status contradicts submitted bytes")
        if component.valid and not component.declaration:
            raise WorkspaceIntegrityError("valid report lacks theorem declaration")
        if component.valid and component.declaration not in (expected_name, f"{namespace}.{expected_name}"):
            raise WorkspaceIntegrityError("valid report names an unexpected theorem")
        if component.valid and set(component.axioms) - set(STANDARD_LEAN_AXIOMS):
            raise WorkspaceIntegrityError("valid report contains forbidden axiom dependencies")
    if report.visible.valid and not report.bridge.valid:
        raise WorkspaceIntegrityError("visible accepted without valid bridge dependency")
    if report.bridge.status == "blocked_by_bridge" or (report.bridge.valid and report.visible.status == "blocked_by_bridge"):
        raise WorkspaceIntegrityError("checker dependency status contradicts bridge validity")


def run_production_session(
    record: WorkspaceRecord, *, namespace: str, artifacts: Path,
    config: BedrockAgentConfig, client, checker: Callable | None = None,
) -> dict:
    """One fresh session; explicit client, no implicit credentials or live launch.

    A successful return does not admit sibling evaluations: the caller still
    audits the session/batch, then rechecks selected bytes via the contract.
    Any uncaught evidence/filesystem exception must halt admissions and retain
    the full external session reservation; never rerun this artifacts directory.
    """
    started = time.monotonic()
    _validate_config(config)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", namespace):
        raise ValueError("invalid trusted namespace")
    if type(getattr(client, "max_retries", None)) is not int or client.max_retries != 0:
        raise ValueError("client must explicitly disable SDK retries")
    initial = render_production_proposer(record)
    if any((record.path / rel).exists() or (record.path / rel).is_symlink() for rel in OUTPUTS):
        raise WorkspaceIntegrityError("proposer session requires absent initial outputs")
    artifacts = Path(artifacts)
    visible_root, artifact_root = record.path.resolve(), artifacts.resolve()
    if visible_root == artifact_root or visible_root in artifact_root.parents or artifact_root in visible_root.parents:
        raise WorkspaceIntegrityError("artifacts and model workspace must be disjoint")
    if artifacts.is_symlink():
        raise WorkspaceIntegrityError("artifacts directory is a symlink")
    artifacts.mkdir(parents=True, exist_ok=False)
    _write_new(artifacts / "events.jsonl", b"")
    messages = [{"role": "user", "content": initial}]
    _save_new(artifacts / "input.json", {"version": VERSION, "config": asdict(config),
        "system": SYSTEM_PROMPT, "tools": [SUBMISSION_TOOL], "messages": messages,
        "selection_policy": SELECTION_POLICY, "interface_hashes": interface_hashes(),
        "world_id": record.world_id, "arm": record.condition, "namespace": namespace,
        "copied_hashes": record.copied_hashes, "checker_injected": checker is not None,
        "client_class": f"{type(client).__module__}.{type(client).__qualname__}",
        "started_at": datetime.now(timezone.utc).isoformat()})
    deadline = started + config.timeout_seconds
    budget = TokenBudget(config)
    usage = dict.fromkeys(USAGE_FIELDS, 0)
    sequence = requests = revisions = 0
    last_report = None
    selected = None
    reported_models: list[str] = []
    status, error = "request_limit", None
    uncertainty = False
    accounting_complete = True
    unresolved_bound = 0.0
    active_reservation = None
    used_tool_ids: set[str] = set()

    def event(kind: str, **payload):
        nonlocal sequence
        sequence += 1
        body = {"seq": sequence, "event": kind, "at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": time.monotonic() - started, **payload}
        with (artifacts / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(_json(body) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def fail(phase: str, exc: Exception):
        nonlocal status, error
        status, error = "infrastructure_failure", f"{phase}: {type(exc).__name__}: {exc}"
        detail = {"phase": phase, "error": error}
        if isinstance(exc, VerificationInfrastructureError):
            detail.update(compiler_phase=exc.phase, stdout=exc.stdout, stderr=exc.stderr,
                          partial_bridge=asdict(exc.partial_bridge) if exc.partial_bridge else None)
        event("infrastructure_failure", **detail)

    def check_inputs():
        if render_production_proposer(record) != initial:
            raise WorkspaceIntegrityError("immutable proposer payload drift")

    event("session_started", selection_policy=SELECTION_POLICY)
    for turn in range(1, config.max_turns + 1):
        try:
            check_inputs()
        except Exception as exc:
            fail("workspace", exc)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "session_limit"
            break
        request = build_production_request(messages, config)
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
        event("count_finished", turn=turn, input_tokens=counted, duration_seconds=time.monotonic() - counted_at)
        # Do not reserve an inference call after counting used up the session.
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
            # Ensure the raw response can be archived without silently dropping data.
            _json(payload)
        except Exception as exc:
            accounting_complete = False
            fail("inference_or_decode", exc)
            break
        event("response", turn=turn, body=payload, duration_seconds=time.monotonic() - requested_at)
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
        event("request_settled", turn=turn, tokens=raw_usage, input_reserved=budget.input_reserved,
              output_reserved=budget.output_reserved)
        response_model = payload.get("model")
        reported_models.append(response_model)
        if not isinstance(response_model, str) or response_model.removeprefix("anthropic.") != config.model.removeprefix("anthropic."):
            accounting_complete = False  # Unknown-model pricing is not assumed equivalent.
            fail("response_model", ValueError("response model differs from requested model"))
            break
        content, reason = payload.get("content"), payload.get("stop_reason")
        if (not isinstance(content, list) or any(not isinstance(block, dict) for block in content)
                or reason not in ("tool_use", "end_turn", "max_tokens", "refusal")):
            fail("response_shape", ValueError("unknown or malformed response structure"))
            break
        if any(block.get("type") not in ("text", "thinking", "redacted_thinking", "tool_use") for block in content):
            fail("response_shape", ValueError("unsupported response block type"))
            break
        # Preserve the exact assistant blocks (including thinking signatures).
        messages.append({"role": "assistant", "content": deepcopy(content)})
        if reason == "max_tokens":
            status = "output_limit"  # Do not execute a tool in a truncated response.
            event("truncated_response_ignored", turn=turn)
            break
        calls = [block for block in content if block.get("type") == "tool_use"]
        if reason in ("end_turn", "refusal") and not calls:
            status = "model_stopped"
            break
        if reason != "tool_use" or len(calls) != 1:
            status, error = "invalid_output", "expected exactly one complete tool submission"
            break
        call = calls[0]
        arguments = call.get("input")
        if (call.get("name") != SUBMISSION_TOOL["name"] or not isinstance(call.get("id"), str)
                or not call["id"] or call["id"] in used_tool_ids or not isinstance(arguments, dict)
                or set(arguments) != {"bridge_source", "solution_source"}
                or not isinstance(arguments["bridge_source"], str)
                or not (arguments["solution_source"] is None or isinstance(arguments["solution_source"], str))):
            status, error = "invalid_output", "check_submission arguments or identity violate the contract"
            break
        used_tool_ids.add(call["id"])
        try:
            sources = {"Bridge.lean": arguments["bridge_source"].encode("utf-8"),
                       "Solution.lean": None if arguments["solution_source"] is None
                       else arguments["solution_source"].encode("utf-8")}
        except UnicodeEncodeError:
            status, error = "invalid_output", "submitted source is not valid UTF-8"
            break
        revisions += 1
        last_report = None  # Never fall back if this complete revision later fails.
        revision_dir = artifacts / "revisions" / f"{revisions:04d}"
        revision_dir.mkdir(parents=True, exist_ok=False)
        for rel, source in sources.items():
            if source is not None:
                _write_new(revision_dir / rel, source)
        hashes = {rel: None if data is None else _sha(data) for rel, data in sources.items()}
        _save_new(revision_dir / "submission.json", {"turn": turn, "tool_use_id": call["id"],
                                                    "revision": revisions, "source_hashes": hashes})
        event("submission", turn=turn, revision=revisions, source_hashes=hashes)
        try:
            check_inputs()
            for rel, source in sources.items():
                path = record.path / rel
                if source is None:
                    # Only our own prior working output, preserved in revisions/.
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(source)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VerificationInfrastructureError("checker", "session deadline before verification")
            check_timeout = min(CHECK_TIMEOUT_SECONDS, remaining)
            event("verification_started", turn=turn, revision=revisions, timeout_seconds=check_timeout)
            checked_at = time.monotonic()
            report = (checker or verify_production)(record, namespace=namespace, timeout_s=check_timeout)
            _validate_report(report, record, namespace, sources)
            check_inputs()
        except Exception as exc:
            fail("checker", exc)
            break
        last_report = report
        _save_new(revision_dir / "verification.json", asdict(report))
        event("verification", turn=turn, revision=revisions, report=asdict(report),
              duration_seconds=time.monotonic() - checked_at)
        feedback = _feedback(report)
        event("feedback", turn=turn, revision=revisions, body=feedback)
        if report.bridge.valid and report.visible.valid:
            status = "both_verified"
            break
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call["id"],
                                                         "content": _json(feedback)}]})

    try:
        check_inputs()
        if status in NORMAL_TERMINATIONS and last_report is not None and last_report.bridge.valid:
            artifact = bridge_artifact(record, last_report)
            selected_dir = artifacts / "selected_bridge"
            selected_dir.mkdir(exist_ok=False)
            _write_new(selected_dir / "Bridge.lean", artifact.source)
            selected = {key: value for key, value in asdict(artifact).items() if key != "source"}
            selected.update(revision=revisions, relative_path="selected_bridge/Bridge.lean")
            _save_new(selected_dir / "artifact.json", selected)
    except Exception as exc:
        selected = None
        fail("final_integrity", exc)
    # The next batch stage must audit this trace, not simply trust selected != None.
    if status == "infrastructure_failure":
        production_outcome = "not_interpretable_infrastructure"
    elif status == "invalid_output":
        production_outcome = "invalid_protocol_output"
    elif last_report is None:
        production_outcome = "no_complete_submission"
    elif last_report.bridge.valid:
        production_outcome = "valid_bridge"
    else:
        production_outcome = "invalid_bridge"
    cost = (config.input_usd_per_million * (usage["input_tokens"]
            + 2 * usage["cache_creation_input_tokens"] + 0.1 * usage["cache_read_input_tokens"])
            + config.output_usd_per_million * usage["output_tokens"]) / 1_000_000
    result = {"version": VERSION, "status": status, "production_outcome": production_outcome,
        "selection_policy": SELECTION_POLICY, "requests": requests, "revisions": revisions,
        "last_verification": asdict(last_report) if last_report is not None else None,
        "selected_bridge": selected, "bridge_eligible_pending_audit": selected is not None,
        "visible_solved": bool(last_report and last_report.visible.valid and status in NORMAL_TERMINATIONS),
        "infrastructure_failure": status == "infrastructure_failure", "halt_admissions": status == "infrastructure_failure",
        "error": error, "tokens": usage, "accounting_complete": accounting_complete,
        "external_reservation_must_remain_open": not accounting_complete,
        "uncertain_request": uncertainty, "unresolved_charge_upper_estimate_usd": unresolved_bound,
        "cost_usd_at_configured_rates": cost, "session_cost_ceiling_usd": config.reserved_cost_usd,
        "input_reserved": budget.input_reserved, "output_reserved": budget.output_reserved,
        "reported_models": reported_models, "elapsed_seconds": time.monotonic() - started,
        "cost_basis": "configured regional rates; cache writes conservatively at 1h rate; not an AWS invoice"}
    event("session_finished", result=result)
    _save_new(artifacts / "session.json", result)
    return result
