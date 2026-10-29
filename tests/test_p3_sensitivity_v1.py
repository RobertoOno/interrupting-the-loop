"""Prospective S16 checks; fake models and budgets never contact AWS."""

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from creative_machine.formal_routes import sensitivity_protocol_v1 as s16
from creative_machine.formal_routes import bedrock_runner as runner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plan(monkeypatch):
    old = json.loads((ROOT / s16.PARENT_PATH).read_text())
    monkeypatch.setattr(s16.historical, "environment", lambda: deepcopy(old["environment"]))
    return s16.build_plan(ROOT)


def write_plan(tmp_path, plan):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return path


def test_only_request_size_and_common_timeout_change(plan):
    parent = json.loads((ROOT / s16.PARENT_PATH).read_text())
    for limit in s16.LIMITS:
        expected = {**parent["agent"], "output_per_request": limit, "request_timeout_seconds": 300.0}
        assert plan["agent_by_limit"][str(limit)] == expected
        assert asdict(s16.config(limit)) == expected
    assert plan["reserved_worst_case_usd"] == pytest.approx(26.4)
    assert plan["max_total_cost_usd"] == 30 and plan["max_parallel"] == 2
    assert plan["worlds"] == parent["worlds"]
    assert plan["gate_rule_per_limit"] == parent["gate_rule"]
    assert not plan["main_sample_started"] and not plan["mechanistic_stage_admitted"]


@pytest.mark.parametrize("limit", [8192.0, True, 0, 32768, "8192"])
def test_unsupported_limits_fail(limit):
    with pytest.raises(ValueError):
        s16.config(limit)


def test_all_sixteen_inputs_equal_historical_inputs_without_reusing_results(plan, tmp_path):
    parent = json.loads((ROOT / s16.PARENT_PATH).read_text())
    original_ids = {c["cell_id"] for c in parent["cells"]}
    assert len(plan["cells"]) == len({c["cell_id"] for c in plan["cells"]}) == 16
    assert not original_ids & {c["cell_id"] for c in plan["cells"]}
    assert [c["ordinal"] for c in plan["cells"]] == list(range(1, 17))
    for c in plan["cells"]:
        assert c["model_input_sha256"] in {old["model_input_sha256"] for old in parent["cells"]}
        s16.materialize(ROOT, c, tmp_path / c["cell_id"])


@pytest.mark.parametrize("change", ["model", "effort", "request_timeout", "session_timeout", "output_total", "input_total",
    "third_limit", "gate", "concurrency", "budget", "pricing", "seed", "order", "input", "duplicate", "id", "path",
    "parent_hash", "harness", "environment", "main", "timestamp", "drop_cell", "extra_field"])
def test_frozen_plan_drift_rejected_before_calls(plan, tmp_path, change):
    changed = deepcopy(plan)
    if change in ("model", "effort", "request_timeout", "session_timeout", "output_total", "input_total"):
        key, value = {"model": ("model", "different"), "effort": ("effort", "low"),
            "request_timeout": ("request_timeout_seconds", 600), "session_timeout": ("timeout_seconds", 1000),
            "output_total": ("max_output_tokens", 40000), "input_total": ("max_input_tokens", 100000)}[change]
        changed["agent_by_limit"]["16384"][key] = value
    elif change == "third_limit": changed["agent_by_limit"]["32768"] = changed["agent_by_limit"]["8192"]
    elif change == "gate": changed["gate_rule_per_limit"]["baseline_at_most"] = 4
    elif change == "concurrency": changed["max_parallel"] = 4
    elif change == "budget": changed["max_total_cost_usd"] = 150
    elif change == "pricing": changed["pricing"]["regional_multiplier"] = 1
    elif change == "seed": changed["order_seed"] += 1
    elif change == "order": changed["cells"].reverse()
    elif change == "input": changed["cells"][0]["model_input_sha256"] = "0" * 64
    elif change == "duplicate": changed["cells"][1] = changed["cells"][0]
    elif change == "id": changed["plan_id"] += "retry"
    elif change == "path": changed["run_directory"] += "-retry"
    elif change == "parent_hash": changed["parent_plan_sha256"] = "0" * 64
    elif change == "harness": changed["harness_sha256"].pop(next(iter(changed["harness_sha256"])))
    elif change == "environment": changed["environment"]["python"] = "synthetic-other-runtime"
    elif change == "main": changed["main_sample_started"] = True
    elif change == "timestamp": changed["created_at"] = "2026-09-08T12:00:00"
    elif change == "drop_cell": changed["cells"].pop()
    else: changed["posthoc_override"] = True
    with pytest.raises(ValueError):
        s16.load_plan(ROOT, write_plan(tmp_path, changed))


def result(solved=True, infrastructure=False):
    return {"status": "infrastructure_failure" if infrastructure else "solved" if solved else "output_limit",
        "target_solved": solved and not infrastructure, "infrastructure_failure": infrastructure,
        "uncertain_request": infrastructure, "requests": 0, "error": None, "cost_usd_at_published_rates": 0,
        "tokens": {k: 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}}


def robust_rows(plan):
    return [{"cell": deepcopy(c), "result": result(c["condition"] == "oracle_bridge" or
        (c["world_id"] == plan["worlds"][0]["world_id"] and c["holdout"] == 1))} for c in plan["cells"]]


def test_gate_requires_four_pairs_and_margin_separately_in_both_limits(plan):
    checked = s16.summarize(plan, robust_rows(plan))
    assert checked["robust_to_tested_limits"]
    for group in checked["by_response_limit"].values():
        assert group["complete_pairs"] == 4 and group["baseline_successes"] == 1 and group["oracle_successes"] == 4
    assert checked["next_step"] == "robust_under_tested_response_limits_prepare_transfer_not_main_admission"
    assert not checked["main_sample_started"] and not checked["mechanistic_stage_admitted"]


@pytest.mark.parametrize("limit,decision", [(8192, "contrast_not_reproduced_review_before_main"),
    (16384, "not_robust_to_response_limit_review_before_main")])
def test_no_pooled_rescue_of_one_failed_limit(plan, limit, decision):
    rows = robust_rows(plan)
    for row in rows:
        if row["cell"]["output_per_request"] == limit:
            row["result"] = result(True)
    checked = s16.summarize(plan, rows)
    assert not checked["robust_to_tested_limits"] and checked["next_step"] == decision


def test_missing_and_infrastructure_cells_never_become_negative_proofs(plan):
    rows = robust_rows(plan)
    assert s16.summarize(plan, rows[:-1])["next_step"] == "incomplete_review_infrastructure"
    rows[0]["result"] = result(False, True)
    checked = s16.summarize(plan, rows)
    assert not checked["all_cells_valid"] and checked["uncertain_requests"] == 1
    assert checked["next_step"] == "incomplete_review_infrastructure"


def test_duplicate_unknown_and_relabelled_results_rejected(plan):
    for kind in ("duplicate", "unknown", "relabel"):
        rows = robust_rows(plan)
        if kind == "duplicate": rows[1] = rows[0]
        elif kind == "unknown": rows[0]["cell"]["cell_id"] = "outside"
        else: rows[0]["cell"]["output_per_request"] = 1
        with pytest.raises(ValueError): s16.summarize(plan, rows)


@pytest.mark.parametrize("limit", s16.LIMITS)
def test_actual_harness_sends_requested_limit_and_300s_timeout(plan, tmp_path, monkeypatch, limit):
    cell = next(c for c in plan["cells"] if c["output_per_request"] == limit)
    workspace = s16.materialize(ROOT, cell, tmp_path / "workspace")
    calls = []
    class FakeMessages:
        def count_tokens(self, **kwargs): return SimpleNamespace(input_tokens=100)
        def create(self, **kwargs):
            calls.append(kwargs)
            body = {"model": "claude-opus-5", "stop_reason": "max_tokens",
                "content": [{"type": "thinking", "thinking": ""}],
                "usage": {"input_tokens": 100, "output_tokens": limit}}
            return SimpleNamespace(model_dump=lambda **_: body)
    checked = runner.run_bedrock_session(workspace, namespace="unused", statement="unused", bridge_supplied=False,
        artifacts=tmp_path / "artifacts", config=s16.config(limit), client=SimpleNamespace(messages=FakeMessages()))
    assert len(calls) == 1 and calls[0]["max_tokens"] == limit and calls[0]["timeout"] == 300
    assert checked["status"] == "output_limit" and not checked["target_solved"]
    assert checked["tokens"]["output_tokens"] == limit


@pytest.mark.parametrize("after_count", [450, 601])
def test_remaining_session_time_bounds_300s_request_and_no_call_after_deadline(plan, tmp_path, monkeypatch, after_count):
    cell = plan["cells"][0]
    workspace = s16.materialize(ROOT, cell, tmp_path / "workspace")
    now, calls = [0.0], []
    monkeypatch.setattr(runner.time, "monotonic", lambda: now[0])
    class FakeMessages:
        def count_tokens(self, **kwargs):
            now[0] = after_count
            return SimpleNamespace(input_tokens=100)
        def create(self, **kwargs):
            calls.append(kwargs)
            body = {"model": "claude-opus-5", "stop_reason": "end_turn", "content": [],
                "usage": {"input_tokens": 100, "output_tokens": 10}}
            return SimpleNamespace(model_dump=lambda **_: body)
    runner.run_bedrock_session(workspace, namespace="unused", statement="unused", bridge_supplied=False,
        artifacts=tmp_path / "artifacts", config=s16.config(16384), client=SimpleNamespace(messages=FakeMessages()))
    if after_count < 600:
        assert len(calls) == 1 and calls[0]["timeout"] == 150
    else:
        assert not calls


def test_larger_response_limit_preserves_cumulative_output_budget():
    budget = runner.TokenBudget(s16.config(16384))
    first = budget.reserve(100)
    assert first[1] == 16384
    budget.settle(first, 100, 16384)
    second = budget.reserve(100)
    assert second[1] == 3616
    budget.settle(second, 100, 3616)
    assert budget.output_reserved == 20000 and budget.reserve(100) is None


def test_client_retains_no_retries_and_common_timeout(monkeypatch):
    import sys
    calls = []
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(
        AnthropicBedrockMantle=lambda **kwargs: calls.append(kwargs)))
    runner.make_client(s16.config(16384))
    assert calls == [{"aws_profile": "main-account", "aws_region": "us-east-1", "max_retries": 0, "timeout": 300}]


@pytest.mark.parametrize("infra", [False, True])
def test_complete_simulated_loop_and_no_retry_or_settlement_on_uncertainty(plan, tmp_path, monkeypatch, infra):
    monkeypatch.setattr(s16, "RUN_PATH", str(tmp_path / "run"))
    monkeypatch.setattr(s16, "ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setattr(s16, "load_plan", lambda *args: plan)
    monkeypatch.setattr(s16, "preflight", lambda *args: {"ok": True, "model_calls": 0})
    monkeypatch.setattr(s16, "assert_committed", lambda *args: "test-not-real-inference")
    events, seen = [], []
    class FakeBudget:
        def __init__(self, path): pass
        def reserve(self, identity, ceiling):
            events.append(("reserve", identity, ceiling))
            return {"synthetic": True}
        def settle(self, identity, actual):
            events.append(("settle", identity, actual))
            return {"synthetic": True}
    monkeypatch.setattr(s16, "DailyBudget", FakeBudget)
    def fake_session(record, **kwargs):
        seen.append(kwargs["config"].output_per_request)
        return result(True, infra)
    monkeypatch.setattr(s16, "run_bedrock_session", fake_session)
    checked = s16.run(ROOT)
    assert events[0] == ("reserve", s16.PLAN_ID, 30)
    if infra:
        assert len(seen) == 2 and len(events) == 1
        assert checked["next_step"] == "incomplete_review_infrastructure"
    else:
        assert len(seen) == 16 and len(events) == 2
        assert checked["next_step"] == "contrast_not_reproduced_review_before_main"
    before = len(seen)
    with pytest.raises(FileExistsError): s16.run(ROOT)
    assert len(seen) == before


def test_archive_presence_prevents_relaunch_even_without_run_directory(tmp_path, monkeypatch, plan):
    (tmp_path / "archive").mkdir()
    monkeypatch.setattr(s16, "ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setattr(s16, "RUN_PATH", str(tmp_path / "never_created"))
    monkeypatch.setattr(s16, "load_plan", lambda *args: plan)
    monkeypatch.setattr(s16, "preflight", lambda *args: pytest.fail("must reject before preflight or provider"))
    with pytest.raises(FileExistsError): s16.run(ROOT)


def test_unknown_usage_does_not_allow_zero_cost_interpretation(plan):
    rows = robust_rows(plan)
    rows[0]["result"] = s16.failure_result(RuntimeError("synthetic interrupted accounting"))
    checked = s16.summarize(plan, rows)
    assert checked["accounting_incomplete"] and checked["uncertain_requests"] == 1
    assert not checked["all_cells_valid"]


@pytest.mark.parametrize("where", ["preflight", "assert_committed"])
def test_preflight_and_publication_fail_before_budget_or_provider(plan, tmp_path, monkeypatch, where):
    monkeypatch.setattr(s16, "RUN_PATH", str(tmp_path / "run"))
    monkeypatch.setattr(s16, "ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setattr(s16, "load_plan", lambda *args: plan)
    monkeypatch.setattr(s16, "preflight", lambda *args: {"ok": True})
    def fail(*args): raise ValueError("synthetic admission failure")
    monkeypatch.setattr(s16, where, fail)
    monkeypatch.setattr(s16, "DailyBudget", lambda *args: pytest.fail("must not reserve"))
    monkeypatch.setattr(s16, "run_bedrock_session", lambda *args, **kwargs: pytest.fail("must not infer"))
    with pytest.raises(ValueError, match="synthetic admission failure"):
        s16.run(ROOT)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("spawn_fails", [False, True])
def test_detached_launcher_retains_intent_and_never_retries(plan, tmp_path, monkeypatch, spawn_fails):
    import importlib.util
    spec = importlib.util.spec_from_file_location("s16_launcher_test", ROOT / "scripts/p3_run_budgeted_sensitivity_v1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(s16, "load_plan", lambda *args: plan)
    monkeypatch.setattr(s16, "assert_committed", lambda *args: "test-commit")
    calls = []
    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        if spawn_fails: raise OSError("synthetic spawn error")
        return SimpleNamespace(pid=12345)
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    if spawn_fails:
        with pytest.raises(OSError, match="synthetic spawn error"): module.launch(tmp_path)
    else:
        receipt = module.launch(tmp_path)
        assert receipt["pid"] == 12345
    assert len(calls) == 1 and calls[0][1]["start_new_session"]
    assert calls[0][0][-1] == "--worker" and calls[0][1]["cwd"] == tmp_path
    with pytest.raises(FileExistsError): module.launch(tmp_path)
    assert len(calls) == 1
