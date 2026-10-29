"""Offline synthetic trace/manifest mutations; never instantiate a provider."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("p3_s16_audit_test", ROOT / "scripts/p3_audit_sensitivity_v1.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def synthetic_trace(limit=8192, solved=True):
    initial = "Synthetic text, not a real Lean proof or experimental datum."
    cell = {"output_per_request": limit, "model_input_sha256": hashlib.sha256(initial.encode()).hexdigest()}
    agent = asdict(audit.protocol.config(limit))
    messages = [{"role": "user", "content": initial}]
    inputs = {"system": audit.SYSTEM_PROMPT, "tools": [audit.SOLUTION_TOOL], "messages": messages, "config": agent}
    request = {"model": agent["model"], "system": audit.SYSTEM_PROMPT, "tools": [audit.SOLUTION_TOOL],
        "messages": deepcopy(messages), "output_config": {"effort": "high"}, "thinking": {"type": "adaptive"},
        "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}, "max_tokens": limit}
    content = ([{"type": "tool_use", "id": "synthetic-call", "name": "check_solution",
        "input": {"source": "synthetic source"}}] if solved else [{"type": "thinking", "thinking": "synthetic"}])
    usage = {name: 0 for name in audit.USAGE}
    usage.update(input_tokens=100, output_tokens=100 if solved else limit)
    response = {"model": "claude-opus-5", "content": content, "usage": usage,
        "stop_reason": "tool_use" if solved else "max_tokens"}
    report = asdict(audit.EvaluationReport(ok=True, solution_valid=True))
    # math.ceil(100 * 1.1) is 111 on this binary-float path, matching the frozen guard.
    bound = audit.math.ceil(100 * 1.10) + 1024
    events = [{"event": "request", "turn": 1, "counted_input": 100,
        "reservation": [bound, limit], "body": request}, {"event": "response", "turn": 1, "body": response}]
    if solved:
        events.append({"event": "verification", "turn": 1, "report": report})
    session = {"status": "solved" if solved else "output_limit", "target_solved": solved,
        "requests": 1, "infrastructure_failure": False, "uncertain_request": False, "error": None,
        "workspace_audit_errors": [], "tokens": usage, "verification": [report] if solved else [],
        "reported_models": ["claude-opus-5"], "input_reserved": bound,
        "output_reserved": usage["output_tokens"], "elapsed_seconds": 20,
        "session_cost_ceiling_usd": 1.65, "cost_usd_at_published_rates": float(audit.money(usage, agent))}
    return cell, initial, inputs, session, events


@pytest.mark.parametrize("limit", [8192, 16384])
@pytest.mark.parametrize("solved", [False, True])
def test_reconstructs_synthetic_trace_both_limits(limit, solved):
    checked = audit.audit_trace(*synthetic_trace(limit, solved))
    assert checked["status"] == ("solved" if solved else "output_limit")
    assert checked["requests"] == 1 and len(checked["sources"]) == int(solved)


@pytest.mark.parametrize("change", ["input", "config", "model", "cap", "history", "tool", "effort", "count",
    "reservation", "response_model", "usage", "bool_usage", "missing_usage", "output_overrun", "cost", "status",
    "score", "reported_models", "requests", "bool_requests", "unresolved", "infrastructure", "extra_request",
    "no_response", "no_verification", "fake_verified", "order", "extra_config", "elapsed", "workspace"])
def test_adversarial_trace_changes_fail(change):
    cell, initial, inputs, session, events = deepcopy(synthetic_trace())
    if change == "input": initial += " altered"
    elif change == "config": inputs["config"]["request_timeout_seconds"] = 120
    elif change == "model": events[0]["body"]["model"] = "other"
    elif change == "cap": events[0]["body"]["max_tokens"] = 16384
    elif change == "history": events[0]["body"]["messages"].append({"role": "user", "content": "leaked previous cell"})
    elif change == "tool": events[0]["body"]["tools"] = []
    elif change == "effort": events[0]["body"]["output_config"]["effort"] = "low"
    elif change == "count": events[0]["counted_input"] = -1
    elif change == "reservation": events[0]["reservation"][1] = 20000
    elif change == "response_model": events[1]["body"]["model"] = "other"
    elif change == "usage": session["tokens"] = {**session["tokens"], "output_tokens": 101}
    elif change == "bool_usage": events[1]["body"]["usage"]["cache_read_input_tokens"] = False
    elif change == "missing_usage": events[1]["body"]["usage"].pop("input_tokens")
    elif change == "output_overrun": events[1]["body"]["usage"]["output_tokens"] = 8193
    elif change == "cost": session["cost_usd_at_published_rates"] += .01
    elif change == "status": session["status"] = "output_limit"
    elif change == "score": session["target_solved"] = False
    elif change == "reported_models": session["reported_models"] = ["other"]
    elif change == "requests": session["requests"] = 2
    elif change == "bool_requests": session["requests"] = True
    elif change == "unresolved": session["uncertain_request"] = True
    elif change == "infrastructure": session["infrastructure_failure"] = True
    elif change == "extra_request": events.append(deepcopy(events[0]))
    elif change == "no_response": events = events[:1]
    elif change == "no_verification": events.pop()
    elif change == "fake_verified": events[2]["report"]["solution_valid"] = False
    elif change == "order": events[1]["turn"] = 2
    elif change == "extra_config": events[0]["body"]["temperature"] = 1
    elif change == "elapsed": session["elapsed_seconds"] = float("nan")
    else: session["workspace_audit_errors"] = ["immutable file changed"]
    with pytest.raises(ValueError):
        audit.audit_trace(cell, initial, inputs, session, events)


def make_manifest(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "a.json").write_text("{}")
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text(audit.digest(root / "a.json") + "  a.json\n")
    return root, manifest


def test_manifest_complete_and_hashes_stable(tmp_path):
    root, manifest = make_manifest(tmp_path)
    assert list(audit.verify_manifest(root, manifest)) == ["a.json"]


@pytest.mark.parametrize("mutation", ["missing", "extra", "changed", "duplicate", "absolute", "traversal", "symlink", "invalid_digest", "empty"])
def test_manifest_inventory_mutations_rejected(tmp_path, mutation):
    root, manifest = make_manifest(tmp_path)
    if mutation == "missing": (root / "a.json").unlink()
    elif mutation == "extra": (root / "b.json").write_text("{}")
    elif mutation == "changed": (root / "a.json").write_text('{"changed":true}')
    elif mutation == "duplicate": manifest.write_text(manifest.read_text() * 2)
    elif mutation == "absolute": manifest.write_text("0" * 64 + "  /outside\n")
    elif mutation == "traversal": manifest.write_text("0" * 64 + "  ../outside\n")
    elif mutation == "symlink": (root / "link").symlink_to(root / "a.json")
    elif mutation == "invalid_digest": manifest.write_text("x" * 64 + "  a.json\n")
    else: manifest.write_text("")
    with pytest.raises(ValueError): audit.verify_manifest(root, manifest)


def test_numeric_comparison_only_allows_summation_roundoff():
    assert audit.compare_numeric({"cost": .1 + .2}, {"cost": .3})
    assert not audit.compare_numeric({"cost": True}, {"cost": 1})
    assert not audit.compare_numeric({"cost": float("nan")}, {"cost": 0})
    assert not audit.compare_numeric({"extra": 1}, {})
