"""Budget, isolation, and proof-tool protocol regressions; never live inference."""
from pathlib import Path
from types import SimpleNamespace
import json
import re
import shutil

import pytest

from creative_machine.formal_routes import WorldSpec, build_world, write_world, materialize_evaluator, validate_world
from creative_machine.formal_routes.bedrock_runner import (
    BedrockAgentConfig, TokenBudget, render_workspace, run_bedrock_session,
)
from creative_machine.formal_routes.submission import (
    EvaluationReport, STANDARD_LEAN_AXIOMS, _stage_sources, axiom_audit_ok, verify_evaluator_solution,
)
from creative_machine.formal_routes.lean_sandbox import sandbox_process


def test_budget_reserves_before_call_and_keeps_uncertain_reservations():
    config = BedrockAgentConfig(max_input_tokens=3000, max_output_tokens=4096)
    budget = TokenBudget(config)
    first = budget.reserve(1000)
    assert first == (2124, 4096)
    assert budget.reserve(1000) is None
    budget.settle(first, 1000, 100)
    assert budget.output_reserved == 100
    assert budget.input_reserved == 2124
    with pytest.raises(RuntimeError, match="exceeded"):
        TokenBudget(config).settle((10, 100), 11, 20)


def test_axiom_policy_is_explicit_and_never_accepts_sorry_or_new_axioms():
    standard = "'proof' depends on axioms: [propext, Quot.sound, Classical.choice]"
    assert not axiom_audit_ok(standard)
    assert axiom_audit_ok(standard, STANDARD_LEAN_AXIOMS)
    assert not axiom_audit_ok("'proof' depends on axioms: [sorryAx]", STANDARD_LEAN_AXIOMS)
    assert not axiom_audit_ok("'proof' depends on axioms: [bad]", STANDARD_LEAN_AXIOMS)
    assert not axiom_audit_ok("", STANDARD_LEAN_AXIOMS)


def workspace(tmp_path):
    world = write_world(build_world(WorldSpec("CAL_T1_ABCD9876", "T1", 88)), tmp_path / "world")
    record = materialize_evaluator(world, 1, "no_bridge", tmp_path / "workspace")
    return world, record


def test_model_input_cannot_include_neighbor_oracle_or_unlisted_files(tmp_path):
    world, record = workspace(tmp_path)
    text = render_workspace(record)
    assert "Oracle.lean" not in text and "metadata.json" not in text
    assert "Holdout2Statement" not in text
    (record.path / "extra.txt").write_text("unapproved")
    with pytest.raises(ValueError, match="invalid workspace"):
        render_workspace(record)


def test_clean_staging_never_copies_cached_binaries(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    (root / "source.lean").write_text("theorem t : True := True.intro")
    (root / ".lake").mkdir()
    (root / ".lake/poisoned.olean").write_bytes(b"untrusted")
    staged = tmp_path / "staged"
    _stage_sources(root, staged, ("source.lean",))
    assert not (staged / ".lake").exists()
    assert (staged / "source.lean").exists()


class FakeMessages:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def count_tokens(self, **kwargs):
        return SimpleNamespace(input_tokens=100)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise TimeoutError("uncertain provider response")
        payload = {"model": "anthropic.claude-opus-5", "stop_reason": "tool_use",
                   "usage": {"input_tokens": 100, "output_tokens": 40},
                   "content": [{"type": "tool_use", "id": "tool1", "name": "check_solution",
                                "input": {"source": "candidate"}}]}
        return SimpleNamespace(model_dump=lambda **_: payload)


def test_verified_tool_submission_stops_without_extra_inference(tmp_path):
    _, record = workspace(tmp_path)
    fake = FakeMessages()
    result = run_bedrock_session(record, namespace="unused", statement="unused", bridge_supplied=False,
        artifacts=tmp_path / "artifacts", config=BedrockAgentConfig(), client=SimpleNamespace(messages=fake),
        checker=lambda source: EvaluationReport(ok=True, solution_valid=True))
    assert result["status"] == "solved" and len(fake.calls) == 1
    assert result["tokens"]["output_tokens"] == 40
    assert result["cost_usd_at_published_rates"] == pytest.approx(0.00165)


def test_uncertain_request_is_recorded_and_never_retried(tmp_path):
    _, record = workspace(tmp_path)
    fake = FakeMessages(fail=True)
    result = run_bedrock_session(record, namespace="unused", statement="unused", bridge_supplied=False,
        artifacts=tmp_path / "artifacts", config=BedrockAgentConfig(), client=SimpleNamespace(messages=fake))
    assert result["infrastructure_failure"] and result["uncertain_request"]
    assert len(fake.calls) == 1 and result["unresolved_charge_upper_estimate_usd"] > 0


@pytest.mark.parametrize("template", ["T1", "T2"])
@pytest.mark.skipif(shutil.which("lake") is None, reason="Lean unavailable")
def test_hard_world_and_oracle_work_through_sandbox(tmp_path: Path, template: str):
    world = write_world(build_world(WorldSpec(f"CAL2_{template}_CAFE1234", template, 14, difficulty="hard")), tmp_path / "world")
    report = validate_world(world, run_lean=True)
    assert report.ok, report.errors
    record = materialize_evaluator(world, 1, "oracle_bridge", tmp_path / "workspace")
    meta = json.loads((world / "metadata.json").read_text())
    ns = meta["roles"]["namespace"]
    body = re.search(r"theorem oracle_holdout1 :.*?(?=\n\n(?:theorem|#print))",
                     (world / "Hidden/OracleChecks.lean").read_text(), re.S).group()
    body = body.replace("theorem oracle_holdout1", "theorem evaluation_solution")
    (record.path / "Solution.lean").write_text("import World.ChallengeEvaluation\nimport Bridge\n"
                                              + f"namespace {ns}\n{body}\nend {ns}\n")
    verified = verify_evaluator_solution(record.path, namespace=ns, statement="Holdout1Statement",
        bridge_supplied=True, allowed_axioms=STANDARD_LEAN_AXIOMS, process_runner=sandbox_process)
    assert verified.ok, verified.errors
