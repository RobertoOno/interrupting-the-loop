"""A2 prover mode: the native whole-proof template, transplant of the answer's last Lean block into Solution.lean,
plain-text feedback turns, plan hashing by mode, the context-window status, the cross-model rule, and (when the
Mathlib environment is available) a real check of a transplanted proof."""
from __future__ import annotations
import json, os, shutil, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
from creative_machine.formal_routes import ladder_runner_v1 as R  # noqa: E402
from creative_machine.formal_routes import openai_session_v1 as O  # noqa: E402
from creative_machine.formal_routes.submission import EvaluationReport  # noqa: E402

CFG = dict(base_url="http://fake/v1", model="prover", mode="prover", max_turns=3, timeout_seconds=60.0, request_timeout_seconds=10.0,
           max_output_tokens=4096, output_per_request=2048)


def fake_post(script):
    calls = []
    def post(url, body, *, timeout, api_key):
        calls.append(body); kind, payload = script[min(len(calls) - 1, len(script) - 1)]
        if kind == "overflow":
            raise O.ContextOverflow("This model's maximum context length is 32768 tokens. However, you requested 33000 tokens")
        if kind == "tool":
            msg = {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "check_solution", "arguments": json.dumps(payload)}}]}
            return {"model": "m", "choices": [{"message": msg, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 1500, "completion_tokens": 700}}
        return {"model": "prover", "choices": [{"message": {"role": "assistant", "content": payload}, "finish_reason": "length" if kind == "length" else "stop"}],
                "usage": {"prompt_tokens": 1500, "completion_tokens": 700}}
    post.calls = calls
    return post


@pytest.fixture
def world(tmp_path):
    return L.build_instance("pm-1", tmp_path / "w", phase="pilot", extra=("E",), env="mathlib")[0].parent


def answer(ctx, proof, *, helper="", reemit=True, trailing_end=False):
    code = ((O.PROVER_HEADER + "\n" + ctx["definitions"] + "\n") if reemit else "") + helper + f"theorem evaluation_solution : {ctx['statement']} := by\n{proof}"
    code += f"\n\nend {ctx['namespace']}\n" if trailing_end else "\n"
    return "### Proof plan\nThe quantity y - x is conserved by every move.\n\n```lean4\n" + code + "```\n"


def session(rec, script, checker, name):
    return O.run_openai_session(rec, namespace="A1.X.L1", statement="LadderStatement", bridge_supplied=False, artifacts=rec.path.parent / name,
                                config=O.OpenAIAgentConfig(**CFG), post=fake_post(script), checker=checker)


def test_world_context_and_prompt(world, tmp_path):
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws_none")
    ctx = O.world_context(rec.path); meta = L.load_step(world / "L1")
    assert ctx["namespace"] == meta["roles"]["namespace"] and ctx["statement"] == meta["statement_text"]
    assert "structure State where" in ctx["definitions"] and "def start : State" in ctx["definitions"]
    assert not any(l.startswith(("import", "namespace", "end")) for l in ctx["definitions"].splitlines())
    prompt = O.render_prover_prompt(rec)
    assert prompt.startswith("Complete the following Lean 4 code:") and prompt.count("```lean4") == 1 and "namespace" not in prompt
    assert f"theorem evaluation_solution : {ctx['statement']} := by\n```" in prompt and prompt.index("import Mathlib") < prompt.index("structure State")
    ref = tmp_path / "ref.md"; ref.write_text(R.render_example_md(world / "E", (world / "E/Hidden/Reference.lean").read_text()))
    p2 = O.render_prover_prompt(R.materialize_ladder(world / "L4", "reference", tmp_path / "ws_ref", source_file=ref))
    assert p2.startswith(O.PROVER_EXAMPLE_NOTE) and "# Worked example" in p2 and p2.endswith(O.PROVER_TEMPLATE.split("{formal}")[1])
    assert O.render_prover_prompt(R.materialize_ladder(world / "L4", "content", tmp_path / "ws_content")).startswith(O.PROVER_CONTENT_NOTE)
    with pytest.raises(ValueError):
        O.world_context(L.build_instance("pm-std", tmp_path / "s", phase="pilot")[0])   # Std world: refused


def test_extract_transplant(world, tmp_path):
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws"); ctx = O.world_context(rec.path)
    helper = "lemma helper (n : Int) : n = n := rfl\n\n"
    src, found, why = O.extract_prover_solution(answer(ctx, "  intro t h\n  sorry", helper=helper, trailing_end=True), ctx)
    assert found and why == "ok"
    lines = src.splitlines()
    assert lines[0] == "import World.ChallengeEvaluation" and f"namespace {ctx['namespace']}" in lines and lines[-1] == f"end {ctx['namespace']}"
    assert "structure State where" not in src and "import Mathlib" not in src and src.count("\nend ") == 1 and "deriving" not in src
    assert "lemma helper" in src and "open BigOperators Real Nat Topology Rat" in src and "set_option maxHeartbeats 400000" in src
    assert src.index("lemma helper") < src.index("theorem evaluation_solution") and src.rstrip().endswith(f"sorry\n\nend {ctx['namespace']}")
    src2, found2, _ = O.extract_prover_solution("```\ntheorem evaluation_solution : True := by\n  trivial\n```", ctx)   # theorem only, bare fence
    assert found2 and "theorem evaluation_solution : True := by\n  trivial" in src2
    src3, _, _ = O.extract_prover_solution("```lean\ntheorem evaluation_solution : True := by\n  omega\n```\ntext\n```lean4\ntheorem evaluation_solution : True := by\n  trivial\n```", ctx)
    assert "trivial" in src3 and "omega" not in src3   # the last block wins
    assert O.extract_prover_solution("no code here", ctx) == (None, False, "no fenced Lean code block in the answer")
    raw = O.PROVER_HEADER + "\n" + ctx["definitions"] + f"\ntheorem evaluation_solution : {ctx['statement']} := by\n  intro t h\n  omega\n"   # E1: unfenced completed file
    src5, found5, why5 = O.extract_prover_solution(raw, ctx)
    assert found5 and why5 == "ok" and "structure State" not in src5 and src5.count("theorem evaluation_solution") == 1 and "  omega" in src5
    src4, found4, why4 = O.extract_prover_solution("```lean4\ntheorem other : True := trivial\n```", ctx)
    assert src4 is None and found4 and "evaluation_solution" in why4


def test_prover_session_feedback_then_solved(world, tmp_path):
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws"); ctx = O.world_context(rec.path)
    checker = lambda src: EvaluationReport(ok=True, solution_valid=True) if "good_proof" in src else EvaluationReport(errors=["Lean rejected the proof"], stderr="error: unsolved goals\n⊢ False")
    post = fake_post([("text", answer(ctx, "  bad_proof")), ("text", answer(ctx, "  good_proof", reemit=False))])
    art = rec.path.parent / "art_fb"
    r = O.run_openai_session(rec, namespace="A1.X.L1", statement="LadderStatement", bridge_supplied=False, artifacts=art, config=O.OpenAIAgentConfig(**CFG), post=post, checker=checker)
    assert r["status"] == "solved" and r["requests"] == 2 and r["submissions"] == 2 and r["mode"] == "prover" and r["tokens"]["output_tokens"] == 1400
    first, second = post.calls
    assert "tools" not in first and first["messages"][0]["role"] == "user" and "Complete the following Lean 4 code" in first["messages"][0]["content"]
    assert second["messages"][1]["role"] == "assistant" and second["messages"][2]["role"] == "user"
    fb = second["messages"][2]["content"]
    assert fb.startswith("The proof was rejected by Lean 4") and "Lean rejected the proof" in fb and "unsolved goals" in fb and "keeping the theorem statement unchanged" in fb
    assert (rec.path / "Solution.lean").read_text().count("good_proof") == 1
    inp = json.loads((art / "input.json").read_text()); assert inp["mode"] == "prover" and "tools" not in inp and inp["world_context"]["namespace"] == ctx["namespace"]
    ev = [json.loads(l) for l in (art / "events.jsonl").read_text().splitlines()]
    assert [e["event"] for e in ev] == ["request", "response", "verification", "request", "response", "verification"] and "import World.ChallengeEvaluation" in ev[2]["source"]


def test_prover_no_block_missing_theorem_overflow_and_extra_body(world, tmp_path):
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws")
    reject = lambda src: EvaluationReport(errors=["x"])
    assert session(rec, [("text", "I give up.")], reject, "a1")["status"] == "unsolved"
    assert session(rec, [("length", "### Proof plan\n```lean4\ntheorem evaluation_solution")], reject, "a2")["status"] == "output_limit"
    wrong = "```lean4\ntheorem other : True := trivial\n```"
    r = session(rec, [("text", wrong)] * 3, reject, "a3")
    assert r["status"] == "turn_limit" and r["requests"] == 3 and all("evaluation_solution" in v["errors"][0] for v in r["verification"])
    r = session(rec, [("overflow", None)], reject, "a4")
    assert r["status"] == "budget_exhausted" and not r["infrastructure_failure"] and not r["uncertain_request"] and "context window" in r["error"]
    cfg = O.OpenAIAgentConfig(**{**CFG, "mode": "tool", "extra_body": {"reasoning_effort": "low"}})
    post = fake_post([("overflow", None)])
    r = O.run_openai_session(rec, namespace="A1.X.L1", statement="LadderStatement", bridge_supplied=False, artifacts=rec.path.parent / "a5", config=cfg, post=post, checker=reject)
    assert r["status"] == "budget_exhausted" and post.calls[0]["reasoning_effort"] == "low" and "tools" in post.calls[0]
    with pytest.raises(ValueError):
        O.run_openai_session(rec, namespace="A1.X.L1", statement="LadderStatement", bridge_supplied=False, artifacts=rec.path.parent / "a6",
                             config=O.OpenAIAgentConfig(**{**CFG, "mode": "other"}), post=post, checker=reject)


def test_plan_hash_preflight_and_run_by_mode(world, tmp_path, monkeypatch):
    agent = {"provider": "openai_compatible", "model": "prover", "mode": "prover", "max_turns": 2, "timeout_seconds": 60.0, "request_timeout_seconds": 10.0,
             "max_output_tokens": 4096, "output_per_request": 2048, "temperature": 1.0, "top_p": 0.95, "check_timeout_seconds": 180.0, "extra_body": {"reasoning_effort": "low"}}
    plan = R.make_plan(ROOT, plan_id="t_prover", phase="pilot", instances=[world], steps=["L1"], arms=["none"], attempts=1, budgets={"b16k": 16384}, agent=agent,
                       order_seed=1, daily_reserve_usd=0.0)
    cell = plan["cells"][0]; rec = R.materialize_ladder(world / "L1", "none", tmp_path / "h")
    assert cell["model_input_sha256"] == R.sha(O.render_prover_prompt(rec)) != R.sha(R.render_workspace(rec))
    tool_plan = R.make_plan(ROOT, plan_id="t_tool", phase="pilot", instances=[world], steps=["L1"], arms=["none"], attempts=1, budgets={"b16k": 16384},
                            agent={**agent, "mode": "tool"}, order_seed=1, daily_reserve_usd=0.0)
    assert tool_plan["cells"][0]["model_input_sha256"] == R.sha(R.render_workspace(rec))
    monkeypatch.setattr(R, "probe_sandbox", lambda ws, ref: {"ok": True})   # the Lean probe of a Mathlib world needs the shared cache; covered by the integration test
    pre = R.preflight(ROOT, plan, lean=False); assert pre["ok"] and pre["drift"] == []
    assert R.preflight(ROOT, {**plan, "agent": {**agent, "mode": "tool"}}, lean=False)["drift"] == [cell["cell_id"]]   # the hash is by mode
    plan_path = tmp_path / "plan.json"; plan_path.write_text(json.dumps(plan))
    monkeypatch.setenv("CM_OPENAI_BASE_URL", "http://fake/v1")
    ctx = O.world_context(rec.path)
    s = R.run_plan(ROOT, plan_path, tmp_path / "runs", journal=tmp_path / "j.jsonl", client_factory=lambda cfg: fake_post([("text", answer(ctx, "  good"))]),
                   allow_dirty=True, run_tag="r1", checker=lambda src: EvaluationReport(ok=True, solution_valid=True))
    assert s["statuses"] == {"solved": 1}
    res = json.loads((tmp_path / "runs/t_prover" / cell["cell_id"] / "result.json").read_text())
    assert res["result"]["mode"] == "prover" and res["result"]["tokens"]["output_tokens"] == 700
    inp = json.loads((tmp_path / "runs/t_prover" / cell["cell_id"] / "artifacts/input.json").read_text())
    assert inp["config"]["extra_body"] == {"reasoning_effort": "low"} and inp["config"]["check_timeout_seconds"] == 180.0


def test_analysis_budget_label_and_cross_model_rule(tmp_path):
    import analysis_a2_mathlib as M
    import analysis_a2_pilot as P
    inst = ["S1", "S2", "S3", "S4", "S5", "S6"]
    def rows(label, arm_rates):
        out = []
        for i, s in enumerate(inst):
            for step, arms in arm_rates.items():
                for arm, k in arms.items():
                    for a in range(4):
                        out.append({"instance": s, "step": step, "arm": arm, "budget_label": label, "attempt": a, "status": "solved" if a < k else "unsolved", "solved": a < k})
        return out
    planA = {"main_budget_label": "b16k", "agent": {"model": "p4b", "mode": "prover"}}
    good = P.analyze(planA, rows("b16k", {"L1": {"none": 4}, "L2": {"none": 3}, "L3": {"none": 2}, "L4": {"none": 1}, "L5": {"none": 1}, "E": {"none": 1}}),
                     {}, rows("b16k", {"L4": {"reference": 4, "skeleton": 1}, "L5": {"reference": 4, "skeleton": 1}}))
    assert good["decision"] == "admit_A2" and good["session_mode"] == "prover" and good["none_rates"]["L1"]["n"] == 24
    bad = P.analyze(planA, rows("b16k", {"L1": {"none": 1}, "L2": {"none": 0}, "L3": {"none": 0}, "L4": {"none": 0}, "L5": {"none": 0}, "E": {"none": 0}}), {}, [])
    assert bad["decision"] == "no_competence_try_second_model"
    # a b16k plan read with the old fixed label would see nothing: the label now comes from the plan
    assert P.analyze({"agent": {}}, rows("b16k", {"L1": {"none": 4}}), {}, [])["none_rates"]["L1"]["n"] == 0
    out = M.analyze(["p4b", "g8b", "q27b", "p32b"], {"p4b": bad, "g8b": good, "q27b": good, "p32b": None})
    assert out["substrate"] == "g8b" and out["not_run"] == ["q27b", "p32b"] and out["verdict"] == "substrate_g8b" and out["models"]["q27b"] == {"ran": False}
    assert M.analyze(["p4b"], {"p4b": bad})["verdict"] == "no_open_model_admitted_A2_closes_in_this_domain"
    md = M.render(out); assert "| g8b | prover | " in md and "não rodou" in md and "`substrate_g8b`" in md


MATHLIB = os.environ.get("CM_LAKE_SHARED", "")


@pytest.mark.skipif(not (MATHLIB and Path(MATHLIB).is_dir() and shutil.which("lake")), reason="Mathlib environment (CM_LAKE_SHARED) not available")
def test_transplanted_reference_passes_the_real_checker(world, tmp_path):
    """The unfolded statement is accepted by the audit's #check (definitional equality with LadderStatement) and the
    prover header's open/set_option lines do not break the reference tactics inside the namespace."""
    from creative_machine.formal_routes.submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws_lean"); ctx = O.world_context(rec.path)
    w = L.make_step("pm-1", "L1")
    src, found, _ = O.extract_prover_solution(answer(ctx, L._solution_body(w, "bridge").rstrip("\n"), helper=L._measure_block(w, w.fields, "bridge") + "\n", trailing_end=True), ctx)
    (rec.path / "Solution.lean").write_text(src)
    rep = verify_evaluator_solution(rec.path, namespace=ctx["namespace"], statement=L.STATEMENT, bridge_supplied=False, timeout_s=600, allowed_axioms=STANDARD_LEAN_AXIOMS)
    assert rep.ok, rep.errors


def test_sandbox_profile_reads_the_shared_lake_cache(tmp_path, monkeypatch):
    """E2: the shared Mathlib packages are readable (never writable) inside the Lean sandbox; unset -> profile unchanged."""
    from creative_machine.formal_routes.codex_runner import filesystem_profile_override
    monkeypatch.delenv("CM_LAKE_SHARED", raising=False)
    base = filesystem_profile_override(tmp_path / "ws")
    shared = tmp_path / "shared"; shared.mkdir()
    monkeypatch.setenv("CM_LAKE_SHARED", str(shared))
    withit = filesystem_profile_override(tmp_path / "ws")
    assert str(shared.resolve()) in withit and f'"{shared.resolve()}"="read"' in withit and "write" in withit and withit.count("write") == 1
    if Path("/Library/Developer/CommandLineTools").is_dir():
        assert '"/Library/Developer/CommandLineTools"="read"' in withit and "CommandLineTools" not in base
    monkeypatch.setenv("CM_LAKE_SHARED", str(tmp_path / "absent"))
    assert filesystem_profile_override(tmp_path / "ws") == base


def test_e5_submission_from_reasoning(world, tmp_path):
    """E5: content without a submission, file inside the reasoning (fenced or from the last `import Mathlib`)."""
    rec = R.materialize_ladder(world / "L1", "none", tmp_path / "ws"); ctx = O.world_context(rec.path)
    body = O.PROVER_HEADER + "\n" + ctx["definitions"] + f"\ntheorem evaluation_solution : {ctx['statement']} := by\n  intro t h\n  good_proof\n"
    reasoning = "Let me think. First draft:\nimport Mathlib\ntheorem evaluation_solution : True := by trivial\nHmm, no. Final answer:\n" + body
    src, found, why = O.extract_from_reasoning(reasoning, ctx)
    assert found and "good_proof" in src and "trivial" not in src and "Let me think" not in src
    src2, found2, _ = O.extract_from_reasoning("thinking...\n```lean4\n" + body + "```\nmore thoughts", ctx)
    assert found2 and "good_proof" in src2
    assert O.extract_from_reasoning("just prose", ctx) == (None, False, "no Lean file in the reasoning")
    checker = lambda s: EvaluationReport(ok=True, solution_valid=True) if "good_proof" in s else EvaluationReport(errors=["x"])
    calls = []
    def post(url, b, *, timeout, api_key):
        calls.append(b); return {"model": "m", "choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": reasoning}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 400}}
    r = O.run_openai_session(rec, namespace="A1.X.L1", statement="LadderStatement", bridge_supplied=False, artifacts=rec.path.parent / "art_e5", config=O.OpenAIAgentConfig(**CFG), post=post, checker=checker)
    assert r["status"] == "solved" and r["submissions"] == 1
    ev = [json.loads(l) for l in (rec.path.parent / "art_e5" / "events.jsonl").read_text().splitlines()]
    assert "submission_from_reasoning" in [e["event"] for e in ev]
