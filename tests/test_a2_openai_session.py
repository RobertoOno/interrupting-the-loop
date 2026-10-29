"""A2: the OpenAI-compatible session loop with a fake endpoint (no GPU), and run_plan dispatch for an open-model plan."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
from creative_machine.formal_routes import ladder_runner_v1 as R  # noqa: E402
from creative_machine.formal_routes.openai_session_v1 import OpenAIAgentConfig, run_openai_session  # noqa: E402
from creative_machine.formal_routes.submission import EvaluationReport  # noqa: E402

CFG = dict(base_url="http://fake/v1", model="m", max_turns=3, timeout_seconds=60.0, request_timeout_seconds=10.0, max_output_tokens=4096, output_per_request=2048)


def fake_post(script):
    """script: list of responses per request; each is (kind, payload) with kind in {'tool', 'text', 'length', 'raise'}."""
    calls = []
    def post(url, body, *, timeout, api_key):
        calls.append(body); kind, payload = script[min(len(calls) - 1, len(script) - 1)]
        if kind == "raise":
            raise ConnectionError("down")
        usage = {"prompt_tokens": 1000, "completion_tokens": 600}
        if kind == "tool":
            msg = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "check_solution", "arguments": json.dumps(payload)}}]}
            return {"model": "m", "choices": [{"message": msg, "finish_reason": "tool_calls"}], "usage": usage}
        return {"model": "m", "choices": [{"message": {"role": "assistant", "content": payload}, "finish_reason": "length" if kind == "length" else "stop"}], "usage": usage}
    post.calls = calls
    return post


@pytest.fixture
def rec(tmp_path):
    inst = L.build_instance("o-1", tmp_path / "w", phase="pilot")[0].parent
    return R.materialize_ladder(inst / "L3", "none", tmp_path / "ws"), inst


def run(rec, script, checker=None, art_name=None):
    ws, inst = rec
    art = ws.path.parent / (art_name or f"art_{len(os.listdir(ws.path.parent))}")
    return run_openai_session(ws, namespace="A1.X.L3", statement="LadderStatement", bridge_supplied=False, artifacts=art, config=OpenAIAgentConfig(**CFG),
                              post=fake_post(script), checker=checker)


def test_solved_on_first_valid_submission(rec):
    checker = lambda src: EvaluationReport(ok=True, solution_valid=True) if "good" in src else EvaluationReport(errors=["bad"])
    r = run(rec, [("tool", {"source": "theorem good := by omega"})], checker, art_name="art_solved")
    assert r["status"] == "solved" and r["target_solved"] and r["requests"] == 1 and r["tokens"]["output_tokens"] == 600 and r["cost_usd_at_published_rates"] == 0.0
    assert json.loads((Path(rec[0].path).parent / "art_solved" / "session.json").read_text())["provider"] == "openai_compatible"


def test_rejected_then_solved_and_tool_feedback(rec):
    checker = lambda src: EvaluationReport(ok=True, solution_valid=True) if "good" in src else EvaluationReport(errors=["Lean rejected"])
    r = run(rec, [("tool", {"source": "bad"}), ("tool", {"source": "good"})], checker)
    assert r["status"] == "solved" and r["requests"] == 2 and len(r["verification"]) == 2 and not r["verification"][0]["ok"]


def test_text_answer_and_length(rec):
    assert run(rec, [("text", "I cannot.")])["status"] == "unsolved"
    assert run(rec, [("length", "thinking...")])["status"] == "output_limit"


def test_malformed_arguments_and_budget_and_failure(rec):
    r = run(rec, [("tool", {"src": 1}), ("tool", {"src": 1}), ("tool", {"src": 1})], checker=lambda s: EvaluationReport(errors=["x"]))
    assert r["status"] == "turn_limit" and all("exactly a string source" in v["errors"][0] for v in r["verification"])
    r = run(rec, [("raise", None)]); assert r["status"] == "infrastructure_failure" and r["uncertain_request"]
    cfg = dict(CFG, max_output_tokens=1000, output_per_request=800)
    ws, inst = rec
    r = run_openai_session(ws, namespace="A1.X.L3", statement="LadderStatement", bridge_supplied=False, artifacts=ws.path.parent / "art_b",
                           config=OpenAIAgentConfig(**cfg), post=fake_post([("tool", {"source": "bad"})]), checker=lambda s: EvaluationReport(errors=["x"]))
    # 600 used after request 1 (400 left, allowed), 1200 after request 2 (< 256 left): exhausted before request 3
    assert r["status"] == "budget_exhausted" and r["requests"] == 2


def test_run_plan_dispatches_open_model_without_daily_budget(tmp_path, monkeypatch):
    inst = L.build_instance("o-2", tmp_path / "worlds", phase="pilot")[0].parent
    agent = {"provider": "openai_compatible", "model": "m", "max_turns": 2, "timeout_seconds": 60.0, "request_timeout_seconds": 10.0, "max_output_tokens": 4096,
             "output_per_request": 2048, "temperature": 0.7, "top_p": 0.8}
    plan = R.make_plan(ROOT, plan_id="t_open", phase="pilot", instances=[inst], steps=["L1"], arms=["none"], attempts=2, budgets={"b8k": 8192}, agent=agent,
                       order_seed=1, daily_reserve_usd=0.0)
    assert plan["session_ceiling_usd"]["b8k"] == 0.0 and plan["worst_case_usd"] == 0.0
    plan_path = tmp_path / "plan.json"; plan_path.write_text(json.dumps(plan))
    journal = tmp_path / "journal.jsonl"
    monkeypatch.delenv("CM_OPENAI_BASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        R.run_plan(ROOT, plan_path, tmp_path / "runs", journal=journal, allow_dirty=True, run_tag="r0")
    monkeypatch.setenv("CM_OPENAI_BASE_URL", "http://fake/v1")
    factory = lambda cfg: fake_post([("tool", {"source": "good"})])
    s = R.run_plan(ROOT, plan_path, tmp_path / "runs", journal=journal, client_factory=factory, allow_dirty=True, run_tag="r1",
                   checker=lambda src: EvaluationReport(ok=True, solution_valid=True))
    assert s["completed"] == 2 and s["statuses"] == {"solved": 2} and not journal.exists()
    prov = json.loads((tmp_path / "runs/t_open/provenance.json").read_text()); assert prov["provider"] == "openai_compatible" and prov["base_url"] == "http://fake/v1"


def test_assemble_stream_rebuilds_tool_calls_and_usage():
    from creative_machine.formal_routes.openai_session_v1 import assemble_stream
    def ev(obj):
        return "data: " + json.dumps(obj)
    lines = [
        ev({"model": "m", "choices": [{"delta": {"reasoning_content": "think "}, "finish_reason": None}]}),
        ev({"model": "m", "choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c9", "type": "function", "function": {"name": "check_", "arguments": ""}}]}, "finish_reason": None}]}),
        ev({"model": "m", "choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "solution", "arguments": "{\"source\": \"th"}}]}, "finish_reason": None}]}),
        ev({"model": "m", "choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "eorem x\"}"}}]}, "finish_reason": "tool_calls"}]}),
        ev({"model": "m", "choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 20}}),
        "data: [DONE]"]
    out = assemble_stream(lines)
    msg = out["choices"][0]["message"]; call = msg["tool_calls"][0]
    assert call["id"] == "c9" and call["function"]["name"] == "check_solution" and json.loads(call["function"]["arguments"]) == {"source": "theorem x"}
    assert out["choices"][0]["finish_reason"] == "tool_calls" and out["usage"]["completion_tokens"] == 20 and msg["reasoning_content"] == "think "
    text = assemble_stream([ev({"choices": [{"delta": {"content": "I "}, "finish_reason": None}]}), ev({"choices": [{"delta": {"content": "cannot"}, "finish_reason": "length"}]}), "data: [DONE]"])
    new = assemble_stream([ev({"choices": [{"delta": {"reasoning": "hmm "}, "finish_reason": None}]}), ev({"choices": [{"delta": {"reasoning": "ok"}, "finish_reason": "length"}]}), "data: [DONE]"])   # E5: `reasoning` field
    assert new["choices"][0]["message"]["reasoning_content"] == "hmm ok" and new["choices"][0]["message"]["content"] == ""
    assert text["choices"][0]["message"]["content"] == "I cannot" and text["choices"][0]["finish_reason"] == "length" and "tool_calls" not in text["choices"][0]["message"]
