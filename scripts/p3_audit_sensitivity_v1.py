#!/usr/bin/env python3
"""Read-only S16 trace/accounting audit plus fresh Lean checks; no provider client.

This is an offline verifier, not a rerun or a new scorer. Unknown/incomplete
terminal paths fail closed and require review, never become negative proofs.
"""

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

from creative_machine.formal_routes import sensitivity_protocol_v1 as protocol
from creative_machine.formal_routes.bedrock_runner import SYSTEM_PROMPT, SOLUTION_TOOL, render_workspace
from creative_machine.formal_routes.calibration_worlds_v3 import load_v3
from creative_machine.formal_routes.lean_sandbox import sandbox_process
from creative_machine.formal_routes.submission import EvaluationReport, verify_evaluator_solution
from creative_machine.formal_routes.workspace import audit_workspace

ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMMIT = "032cc01b1c8bdc8151d9be3817a1368a6fd6445b"
USAGE = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(root, manifest):
    require(not root.is_symlink() and not manifest.is_symlink(), "symlink root or manifest")
    entries = {}
    for line in manifest.read_text().splitlines():
        value, relative = line.split("  ", 1)
        path = Path(relative)
        require(re.fullmatch("[0-9a-f]{64}", value) and relative not in entries and
                relative == path.as_posix() and path.parts and not path.is_absolute() and
                ".." not in path.parts, "invalid manifest entry")
        entries[relative] = value
    paths = list(root.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "symlink in raw tree")
    require({p.relative_to(root).as_posix() for p in paths if p.is_file()} == set(entries),
            "raw inventory differs from manifest")
    for relative, value in entries.items():
        require(digest(root / relative) == value, "raw hash mismatch: " + relative)
    require(bool(entries), "empty raw manifest")
    return entries


def money(tokens, agent):
    return (Decimal(str(agent["input_usd_per_million"])) *
        (tokens["input_tokens"] + 2 * tokens["cache_creation_input_tokens"] +
         Decimal("0.1") * tokens["cache_read_input_tokens"]) +
        Decimal(str(agent["output_usd_per_million"])) * tokens["output_tokens"]) / Decimal(1000000)


def compare_numeric(left, right):
    """Strict structure/types, allowing only floating-point summation roundoff."""
    if isinstance(left, float) or isinstance(right, float):
        return (type(left) in (int, float) and type(right) in (int, float) and
                math.isclose(left, right, rel_tol=0, abs_tol=1e-12))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(compare_numeric(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(compare_numeric(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def audit_trace(cell, initial, input_doc, session, events):
    agent = asdict(protocol.config(cell["output_per_request"]))
    messages = [{"role": "user", "content": initial}]
    require(hashlib.sha256(initial.encode()).hexdigest() == cell["model_input_sha256"], "input hash drift")
    require(protocol.same(input_doc, {"system": SYSTEM_PROMPT, "tools": [SOLUTION_TOOL],
        "messages": messages, "config": agent}), "input/config drift")
    require(session["infrastructure_failure"] is False and session["uncertain_request"] is False and
        session.get("accounting_incomplete", False) is False and session["error"] is None and
        session["workspace_audit_errors"] == [], "incomplete infrastructure or workspace audit")
    tokens = {name: 0 for name in USAGE}
    sources, reports, models = [], [], []
    cursor = requests = input_reserved = output_reserved = 0
    terminal = None
    while cursor < len(events):
        require(terminal is None and requests < agent["max_turns"], "request after terminal or turn limit")
        request = events[cursor]
        requests += 1
        require(request["event"] == "request" and type(request["turn"]) is int and
                request["turn"] == requests, "request order")
        count = request["counted_input"]
        require(type(count) is int and count >= 0, "invalid input count")
        bound_in = math.ceil(count * 1.10) + 1024
        bound_out = min(agent["output_per_request"], agent["max_output_tokens"] - output_reserved)
        require(bound_out >= 256 and input_reserved + bound_in <= agent["max_input_tokens"], "budget overrun")
        require(protocol.same(request["reservation"], [bound_in, bound_out]), "reservation mismatch")
        expected_request = {"model": agent["model"], "system": SYSTEM_PROMPT, "messages": deepcopy(messages),
            "tools": [SOLUTION_TOOL], "output_config": {"effort": agent["effort"]},
            "thinking": {"type": "adaptive"}, "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
            "max_tokens": bound_out}
        require(protocol.same(request["body"], expected_request), "request body or cross-session history drift")
        input_reserved += bound_in
        cursor += 1
        require(cursor < len(events), "request has no response; charge is uncertain")
        response_event = events[cursor]
        require(response_event["event"] == "response" and response_event["turn"] == requests, "response order")
        response = response_event["body"]
        require(response["model"].removeprefix("anthropic.") == agent["model"].removeprefix("anthropic."), "model drift")
        models.append(response["model"])
        require({"input_tokens", "output_tokens"} <= response["usage"].keys(), "missing response usage")
        usage = {name: (0 if response["usage"].get(name) is None else response["usage"][name]) for name in USAGE}
        require(all(type(v) is int and v >= 0 for v in usage.values()), "invalid response usage")
        require(usage["input_tokens"] + 2 * usage["cache_creation_input_tokens"] +
            usage["cache_read_input_tokens"] <= bound_in and usage["output_tokens"] <= bound_out, "response exceeds reservation")
        for name in USAGE:
            tokens[name] += usage[name]
        output_reserved += usage["output_tokens"]
        content = response.get("content", [])
        messages.append({"role": "assistant", "content": content})
        calls = [block for block in content if block.get("type") == "tool_use"]
        cursor += 1
        if not calls:
            terminal = "output_limit" if response.get("stop_reason") == "max_tokens" else "unsolved"
            continue
        if len(calls) != 1 or calls[0].get("name") != "check_solution":
            terminal = "protocol_violation"
            continue
        call = calls[0]
        args = call.get("input", {})
        require(cursor < len(events), "missing proof verification")
        verified = events[cursor]
        require(verified["event"] == "verification" and verified["turn"] == requests, "verification order")
        report = verified["report"]
        require(report.keys() == asdict(EvaluationReport()).keys() and
                type(report["ok"]) is bool and type(report["solution_valid"]) is bool, "invalid verification record")
        reports.append(report)
        valid_argument = (isinstance(args, dict) and set(args) == {"source"} and
            isinstance(args["source"], str) and len(args["source"].encode()) <= 100000)
        require(valid_argument or report["ok"] is False, "malformed source accepted")
        if valid_argument:
            sources.append({"turn": requests, "source": args["source"], "online_report": report})
        cursor += 1
        if report["ok"]:
            require(report["solution_valid"] and not report["errors"], "inconsistent successful proof record")
            terminal = "solved"
        else:
            feedback = {"ok": report["ok"], "errors": report["errors"],
                "compiler_output": (report["stdout"] + "\n" + report["stderr"])[-20000:]}
            messages.append({"role": "user", "content": [{"type": "tool_result",
                "tool_use_id": call["id"], "content": json.dumps(feedback)}]})
    if terminal is None:
        if requests == agent["max_turns"]:
            terminal = "turn_limit"
        elif agent["max_output_tokens"] - output_reserved < 256:
            terminal = "budget_exhausted"
        else:
            raise ValueError("terminal path requires additional timing/input-count evidence; do not score as failure")
    require(session["status"] == terminal and session["target_solved"] is (terminal == "solved"), "terminal score mismatch")
    require(protocol.same(session["tokens"], tokens) and type(session["requests"]) is int and session["requests"] == requests and
        protocol.same(session["verification"], reports) and session["reported_models"] == models and
        session["input_reserved"] == input_reserved and session["output_reserved"] == output_reserved,
        "session totals differ from trace")
    require(math.isfinite(session["elapsed_seconds"]) and 0 <= session["elapsed_seconds"] <= agent["timeout_seconds"] + 1,
            "session elapsed time outside audited bound")
    cost = money(tokens, agent)
    require(compare_numeric(float(cost), session["cost_usd_at_published_rates"]) and
        compare_numeric(session["session_cost_ceiling_usd"], protocol.config(cell["output_per_request"]).reserved_cost_usd),
        "cost or session ceiling mismatch")
    return {"status": terminal, "requests": requests, "tokens": tokens, "cost_usd": str(cost), "sources": sources}


def recheck(repository, cell, source, allowed_axioms):
    metadata = load_v3(repository / cell["world"], phase="calibration")
    with tempfile.TemporaryDirectory(prefix="p3-s16-proof-audit-") as temporary:
        record = protocol.materialize(repository, cell, Path(temporary).resolve() / "workspace")
        (record.path / "Solution.lean").write_text(source)
        return asdict(verify_evaluator_solution(record.path,
            namespace=metadata["roles"]["namespace"],
            statement=metadata["roles"]["holdout_statements"][cell["holdout"] - 1],
            bridge_supplied=cell["condition"] == "oracle_bridge", process_runner=sandbox_process,
            allowed_axioms=tuple(allowed_axioms)))


def audit(repository, root, manifest):
    plan = protocol.load_plan(repository, repository / protocol.PLAN_PATH)
    entries = verify_manifest(root, manifest)
    require(protocol.same(read(root / "plan.json"), plan), "raw plan differs")
    for name in (*plan["harness_sha256"], protocol.PLAN_PATH):
        frozen = subprocess.check_output(["git", "show", FROZEN_COMMIT + ":" + name], cwd=repository, timeout=15)
        require(frozen == (repository / name).read_bytes(), "published source differs: " + name)
    provenance = read(root / "provenance.json")
    require(provenance["commit"] == FROZEN_COMMIT and provenance["environment"] == plan["environment"], "provenance drift")
    expected_preflight = {"ok": True, "model_calls": 0, "cells": [{"cell_id": c["cell_id"],
        "outside_read_denied": True, "network_denied": True, "lean_ok": True, "ok": True} for c in plan["cells"]]}
    require(protocol.same(provenance["preflight"], expected_preflight), "preflight incomplete")
    reservation, settlement = read(root / "budget-reservation.json"), read(root / "budget-settlement.json")
    require(reservation["run_id"] == settlement["run_id"] == plan["plan_id"] and
        reservation["event"] == "reserve" and settlement["event"] == "settle" and
        Decimal(reservation["usd"]) == Decimal("30") and reservation["daily_limit_usd"] == "150", "budget receipt drift")
    start, end = datetime.fromisoformat(reservation["at"]), datetime.fromisoformat(settlement["at"])
    require(start.tzinfo and end.tzinfo and start <= end, "reversed or naive budget times")
    committed_at = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", FROZEN_COMMIT], cwd=repository))
    require(datetime.fromisoformat(plan["created_at"]) <= start and committed_at <= start.timestamp(),
            "plan or source commit postdates admission")
    rows, checks, exact_cost = [], [], Decimal("0")
    for cell in plan["cells"]:
        cell_root = root / cell["cell_id"]
        row, session = read(cell_root / "result.json"), read(cell_root / "artifacts/session.json")
        require(protocol.same(row, {"cell": cell, "result": session}), "cell/result identity drift")
        started = read(cell_root / "started.json")
        require(protocol.same(started["cell"], cell) and start <= datetime.fromisoformat(started["at"]) <= end,
                "cell admission identity or time drift")
        events = [json.loads(line) for line in (cell_root / "artifacts/events.jsonl").read_text().splitlines()]
        with tempfile.TemporaryDirectory(prefix="p3-s16-input-audit-") as temporary:
            fresh = protocol.materialize(repository, cell, Path(temporary).resolve() / "workspace")
            recorded = read(cell_root / "workspace_record.json")
            expected_record = {**asdict(fresh), "path": recorded["path"]}
            require(protocol.same(recorded, expected_record), "workspace allowlist/identity drift")
            require(not audit_workspace(replace(fresh, path=cell_root / "workspace")), "raw workspace drift")
            trace = audit_trace(cell, render_workspace(fresh), read(cell_root / "artifacts/input.json"), session, events)
        source_path = cell_root / "workspace/Solution.lean"
        if trace["sources"]:
            require(source_path.read_text() == trace["sources"][-1]["source"], "saved proof differs from submitted source")
        else:
            require(not source_path.exists(), "unsubmitted saved proof")
        proofs = []
        for submitted in trace.pop("sources"):
            checked = recheck(repository, cell, submitted["source"], plan["allowed_axioms"])
            require(checked["ok"] is submitted["online_report"]["ok"] and
                checked["solution_valid"] is submitted["online_report"]["solution_valid"], "fresh Lean score differs")
            proofs.append({"turn": submitted["turn"], "source_sha256": hashlib.sha256(submitted["source"].encode()).hexdigest(),
                "matches_online": True, "recheck": checked})
        exact_cost += Decimal(trace["cost_usd"])
        rows.append(row)
        checks.append({"cell": cell, **trace, "proofs": proofs, "elapsed_seconds": session["elapsed_seconds"]})
    recomputed = {**protocol.summarize(plan, rows), "freeze_commit": FROZEN_COMMIT}
    require(compare_numeric(read(root / "summary.json"), recomputed), "aggregate drift")
    # Separate count implementation, using independently rechecked terminal scores.
    gates = {}
    for limit in protocol.LIMITS:
        group = [c for c in checks if c["cell"]["output_per_request"] == limit]
        baseline = sum(c["status"] == "solved" for c in group if c["cell"]["condition"] == "no_bridge")
        oracle = sum(c["status"] == "solved" for c in group if c["cell"]["condition"] == "oracle_bridge")
        gates[str(limit)] = {"baseline": baseline, "oracle": oracle, "pairs": len(group) // 2,
            "passed": len(group) == 8 and oracle >= 3 and baseline <= 2 and oracle - baseline >= 2}
        require(gates[str(limit)]["passed"] == recomputed["by_response_limit"][str(limit)]["gate_passed"], "independent gate drift")
    require(Decimal(settlement["usd"]) == exact_cost and exact_cost <= Decimal(reservation["usd"]), "settlement differs from raw usage")
    require(verify_manifest(root, manifest) == entries, "raw changed during audit")
    return {"ok": True, "model_calls": 0, "plan_id": plan["plan_id"], "freeze_commit": FROZEN_COMMIT,
        "raw_files_verified": len(entries), "raw_manifest_sha256": digest(manifest),
        "harness_files_verified": len(plan["harness_sha256"]), "fresh_proofs_checked": sum(len(c["proofs"]) for c in checks),
        "exact_cost_usd_at_frozen_rates": str(exact_cost), "independent_gates": gates,
        "decision": recomputed["next_step"], "all_checks": checks,
        "limits": ["Fresh execution of the same frozen Lean checker, not an independent theorem prover or model replication.",
            "Per-request wall-clock timestamps were not logged; timeout configuration is checked in frozen sources and session elapsed totals.",
            "Two exposed worlds, dependent siblings, one session per cell. No principal sample, invention or mechanism claim."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / protocol.RUN_PATH)
    parser.add_argument("--manifest", type=Path, default=ROOT / (protocol.RUN_PATH + ".sha256"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        require(not args.output.resolve().is_relative_to(args.raw.resolve()), "never write into raw evidence")
        require(not args.output.exists() and not args.output.is_symlink(), "never overwrite audit output")
    result = audit(ROOT, args.raw, args.manifest)
    if args.output:
        protocol.historical.save_new(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
