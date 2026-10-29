"""Budgeted Bedrock proof agent with one tool and no filesystem-reading tool.

Only frozen workspace inputs are sent to the provider. Candidates are compiled
from clean sources in a local sandbox. This is an experimental model invocation,
not a general-purpose assistant or a delegated development agent.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .lean_sandbox import sandbox_process
from .submission import EvaluationReport, STANDARD_LEAN_AXIOMS, verify_evaluator_solution
from .workspace import WorkspaceRecord, audit_workspace

SYSTEM_PROMPT = """You are a Lean proof-solving agent in a controlled experiment.
All available files are supplied in the user message. Follow TASK.md exactly.
Use check_solution to submit the complete contents of Solution.lean and receive
compiler feedback. You may revise it after a rejection. A verified solution ends
the session automatically. No shell, external information, or other files exist
for this task. Do not ask questions. Use Lean 4.33.1, without Mathlib.
Prove the exact frozen statement. Only the standard Lean axioms propext,
Classical.choice, and Quot.sound are allowed as transitive dependencies. sorryAx
is forbidden. Compiler success alone is insufficient; the checker also checks
the exact statement and full axiom audit. Do not use
metaprogramming, new axioms, unsafe declarations, or change supplied inputs.
Only submit one check_solution call at a time. Local helper lemmas in Solution.lean
are permitted. Work within the fixed session budget; prioritize a valid proof.
"""

SOLUTION_TOOL = {
    "name": "check_solution",
    "description": "Replace Solution.lean with this complete source and check its exact type and axiom dependencies. A valid proof finishes the session.",
    "input_schema": {
        "type": "object", "properties": {"source": {"type": "string"}},
        "required": ["source"], "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class BedrockAgentConfig:
    model: str = "anthropic.claude-opus-5"
    aws_profile: str = "main-account"
    aws_region: str = "us-east-1"
    effort: str = "high"
    max_turns: int = 12
    timeout_seconds: float = 600.0
    request_timeout_seconds: float = 120.0
    max_input_tokens: int = 200_000
    max_output_tokens: int = 20_000
    output_per_request: int = 8192
    check_timeout_seconds: float = 60.0   # Lean checker per submission (Mathlib worlds take ~3x the Std time)
    input_usd_per_million: float = 5.5
    output_usd_per_million: float = 27.5

    @property
    def reserved_cost_usd(self) -> float:
        return (self.max_input_tokens * self.input_usd_per_million
                + self.max_output_tokens * self.output_usd_per_million) / 1_000_000


@dataclass
class TokenBudget:
    """Reserve conservative input estimates and output maxima before every call.

An uncertain request keeps its full reservation and is never automatically retried.
Input counting is approximate; an unexpected overrun aborts the session explicitly.
This is an application guard, not a provider-enforced AWS billing cap.
"""
    config: BedrockAgentConfig
    input_reserved: int = 0
    output_reserved: int = 0

    def reserve(self, counted_input: int) -> tuple[int, int] | None:
        if counted_input < 0:
            raise ValueError("negative token count")
        input_bound = math.ceil(counted_input * 1.10) + 1024
        output_bound = min(self.config.output_per_request,
                           self.config.max_output_tokens - self.output_reserved)
        if self.input_reserved + input_bound > self.config.max_input_tokens or output_bound < 256:
            return None
        self.input_reserved += input_bound
        self.output_reserved += output_bound
        return input_bound, output_bound

    def settle(self, reservation: tuple[int, int], actual_input: int, actual_output: int) -> None:
        in_bound, out_bound = reservation
        if not 0 <= actual_input <= in_bound or not 0 <= actual_output <= out_bound:
            raise RuntimeError("provider usage exceeded the reserved token bound")
        self.output_reserved -= out_bound - actual_output


def prompt_hash() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()


def tool_hash() -> str:
    return hashlib.sha256(json.dumps(SOLUTION_TOOL, sort_keys=True).encode()).hexdigest()


def make_client(config: BedrockAgentConfig):
    from anthropic import AnthropicBedrockMantle
    return AnthropicBedrockMantle(aws_profile=config.aws_profile, aws_region=config.aws_region,
                                 max_retries=0, timeout=config.request_timeout_seconds)


def render_workspace(record: WorkspaceRecord) -> str:
    errors = audit_workspace(record)
    if errors:
        raise ValueError("invalid workspace: " + "; ".join(errors))
    return "\n\n".join(
        f"FILE {name}\n```\n{(record.path / name).read_text(encoding='utf-8')}\n```"
        for name in sorted(record.copied_hashes)
    )


def _append(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def run_bedrock_session(record: WorkspaceRecord, *, namespace: str, statement: str,
                        bridge_supplied: bool, artifacts: Path, config: BedrockAgentConfig,
                        client=None, checker: Callable | None = None) -> dict:
    artifacts.mkdir(parents=True, exist_ok=False)
    initial = render_workspace(record)
    messages = [{"role": "user", "content": initial}]
    (artifacts / "input.json").write_text(json.dumps({"system": SYSTEM_PROMPT,
        "tools": [SOLUTION_TOOL], "messages": messages, "config": asdict(config)},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    events = artifacts / "events.jsonl"
    client = client if client is not None else make_client(config)
    budget = TokenBudget(config)
    started = time.monotonic()
    deadline = started + config.timeout_seconds
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0}
    checks = []
    status = "turn_limit"
    error = None
    requests = 0
    uncertain_request = False
    reported_models = []

    def limited_process(command, **kwargs):
        kwargs["timeout"] = max(0.01, min(kwargs.get("timeout", 60), deadline - time.monotonic()))
        return sandbox_process(command, **kwargs)

    def check(source: str):
        (record.path / "Solution.lean").write_text(source, encoding="utf-8")
        if checker is not None:
            return checker(source)
        return verify_evaluator_solution(record.path, namespace=namespace, statement=statement,
            bridge_supplied=bridge_supplied, timeout_s=config.check_timeout_seconds, process_runner=limited_process,
            allowed_axioms=STANDARD_LEAN_AXIOMS)

    for turn in range(1, config.max_turns + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "timeout"
            break
        request = {"model": config.model, "system": SYSTEM_PROMPT, "messages": messages,
                   "tools": [SOLUTION_TOOL], "output_config": {"effort": config.effort},
                   "thinking": {"type": "adaptive"},
                   "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}}
        try:
            counted = client.messages.count_tokens(**request,
                timeout=min(30, remaining)).input_tokens
        except Exception as exc:
            status, error = "infrastructure_failure", f"token_count: {type(exc).__name__}: {exc}"
            break
        reservation = budget.reserve(counted)
        if reservation is None:
            status = "budget_exhausted"
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "timeout"
            break
        request["max_tokens"] = reservation[1]
        _append(events, {"event": "request", "turn": turn, "counted_input": counted,
                         "reservation": reservation, "body": request})
        requests += 1
        try:
            response = client.messages.create(**request,
                timeout=min(config.request_timeout_seconds, remaining))
        except Exception as exc:
            status, error = "infrastructure_failure", f"inference: {type(exc).__name__}: {exc}"
            uncertain_request = True
            break
        payload = response.model_dump(mode="json", exclude_none=True)
        _append(events, {"event": "response", "turn": turn, "body": payload})
        raw_usage = payload["usage"]
        for name in usage:
            value = raw_usage.get(name, 0) or 0
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid usage field: {name}")
            usage[name] += value
        actual_input = (raw_usage["input_tokens"] + 2 * (raw_usage.get("cache_creation_input_tokens", 0) or 0)
                        + (raw_usage.get("cache_read_input_tokens", 0) or 0))
        try:
            budget.settle(reservation, actual_input, raw_usage["output_tokens"])
        except RuntimeError as exc:
            status, error = "budget_accounting_error", str(exc)
            break
        response_model = payload.get("model", "")
        reported_models.append(response_model)
        if response_model.removeprefix("anthropic.") != config.model.removeprefix("anthropic."):
            status, error = "infrastructure_failure", f"unexpected response model: {response_model}"
            break
        content = payload.get("content", [])
        messages.append({"role": "assistant", "content": content})
        tool_calls = [block for block in content if block.get("type") == "tool_use"]
        if not tool_calls:
            status = "output_limit" if payload.get("stop_reason") == "max_tokens" else "unsolved"
            break
        if len(tool_calls) != 1 or tool_calls[0].get("name") != "check_solution":
            status = "protocol_violation"
            break
        call = tool_calls[0]
        arguments = call.get("input", {})
        if set(arguments) != {"source"} or not isinstance(arguments.get("source"), str):
            report = EvaluationReport(errors=["check_solution requires exactly a string source"])
        elif len(arguments["source"].encode()) > 100_000:
            report = EvaluationReport(errors=["solution exceeds the 100000-byte source limit"])
        else:
            try:
                report = check(arguments["source"])
            except subprocess.TimeoutExpired:
                report = EvaluationReport(errors=["Lean verification timeout"])
            except Exception as exc:
                status, error = "infrastructure_failure", f"checker: {type(exc).__name__}: {exc}"
                break
        check_record = asdict(report)
        checks.append(check_record)
        _append(events, {"event": "verification", "turn": turn, "report": check_record})
        feedback = {"ok": report.ok, "errors": report.errors,
                    "compiler_output": (report.stdout + "\n" + report.stderr)[-20000:]}
        if report.ok:
            status = "solved"
            break
        messages.append({"role": "user", "content": [{"type": "tool_result",
            "tool_use_id": call["id"], "content": json.dumps(feedback)}]})
    audit_errors = audit_workspace(record)
    if audit_errors:
        status = "protocol_violation"
    # A 1h write is the most expensive possible cache write; no explicit cache is requested.
    cost = (config.input_usd_per_million * (usage["input_tokens"]
            + 2 * usage["cache_creation_input_tokens"] + 0.1 * usage["cache_read_input_tokens"])
            + config.output_usd_per_million * usage["output_tokens"]) / 1_000_000
    result = {"status": status, "target_solved": status == "solved", "requests": requests,
              "infrastructure_failure": status in {"infrastructure_failure", "budget_accounting_error"},
              "error": error, "uncertain_request": uncertain_request,
              "tokens": usage, "cost_usd_at_published_rates": cost,
              "cost_basis": "regional standard list rates; excludes tax/private discounts; cache writes conservatively at 1h rate",
              "input_reserved": budget.input_reserved, "output_reserved": budget.output_reserved,
              "session_cost_ceiling_usd": config.reserved_cost_usd,
              "elapsed_seconds": time.monotonic() - started,
              "verification": checks, "workspace_audit_errors": audit_errors,
              "reported_models": reported_models}
    if uncertain_request:
        result["unresolved_charge_upper_estimate_usd"] = (
            reservation[0] * config.input_usd_per_million
            + reservation[1] * config.output_usd_per_million) / 1_000_000
    (artifacts / "session.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)
                                             + "\n", encoding="utf-8")
    return result
