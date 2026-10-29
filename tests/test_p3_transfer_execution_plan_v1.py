"""Prospective contract tests; no final plan, live preflight or admission."""
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from creative_machine.formal_routes import transfer_execution_plan_v1 as plan
from creative_machine.formal_routes.transfer_design_v1 import encoded, load_blueprint, sha

REPO = Path(__file__).resolve().parents[1]
COMMIT = "a" * 40


def ci():
    return {"run": {"id": 123, "head_sha": COMMIT, "repository": {"full_name": "RobertoOno/creative-machine"},
                    "path": ".github/workflows/tests.yml", "name": "tests", "event": "push",
                    "status": "completed", "conclusion": "success"},
            "jobs": {"total_count": 3, "jobs": [{"name": name, "run_id": 123, "head_sha": COMMIT,
                                                "status": "completed", "conclusion": "success"} for name in plan.CI_JOBS]}}


def test_policy_keeps_blueprint_and_does_not_admit_inference():
    blueprint = load_blueprint(REPO)
    result = plan.policy(blueprint, source_commit=COMMIT, reviewer_ids=("fixture-reviewer",), reconciler_ids=("fixture-reconciler",))
    assert result["blueprint_sha256"] == sha(encoded(blueprint))
    assert result["max_sessions"] == 26 and result["max_parallel"] == 2
    assert result["batch_reserve_usd"] == "50" and result["aws_daily_cap_usd"] == "150"
    assert result["canonical_repository"] == "/Users/robertoonofilho/wrk/creative-machine"
    assert result["run_id"] == "p3a_transfer_development_v1"
    assert result["data_kind"] == "experimental" and result["status"] == "FROZEN_SPEC_NOT_ADMITTED"
    assert not any(result[k] for k in ("inference_admitted", "main_sample_admitted", "mechanistic_stage_admitted", "provider_authenticated"))
    assert result["control_gate"] == blueprint["contemporary_control_gate"]


@pytest.mark.parametrize("value", ((), ["x"], ("",), ("x", "x"), (None,), ({},)))
def test_reviewer_or_reconciler_identity_is_explicit(value):
    with pytest.raises(plan.ExecutionPlanError): plan.identities(value, "fixture")


def test_missing_experimental_runtime_blocks_freeze(tmp_path):
    with pytest.raises(plan.ExecutionPlanBlocked, match="experimental components missing"):
        plan.fingerprints(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.fixture
def spec(monkeypatch):
    # Only isolated policy validation uses a synthetic dependency inventory.
    # This does not populate missing runtime files or write an execution plan.
    monkeypatch.setattr(plan, "fingerprints", lambda _: {"synthetic-component.py": "b" * 64})
    return plan.build_spec(REPO, source_commit=COMMIT, reviewer_ids=("fixture-reviewer",), reconciler_ids=("fixture-reconciler",))


def test_policy_revalidation_uses_externally_retained_hash(spec):
    assert plan.validate_spec(REPO, spec, expected_sha256=sha(encoded(spec))) == spec
    with pytest.raises(plan.ExecutionPlanError): plan.validate_spec(REPO, spec, expected_sha256="c" * 64)


@pytest.mark.parametrize("field,value", (("max_sessions", 27), ("max_parallel", 3), ("batch_reserve_usd", "51"),
    ("aws_daily_cap_usd", "151"), ("run_id", "retry"), ("canonical_repository", "/tmp/other-copy"),
    ("output", "runs/retry"), ("data_kind", "synthetic"), ("inference_admitted", True),
    ("main_sample_admitted", True), ("mechanistic_stage_admitted", True), ("max_retries", 1),
    ("phase_barrier", "skip"), ("implementation_sha256", {})))
def test_rehash_does_not_authorize_policy_drift(spec, field, value):
    modified = {**spec, field: value}
    with pytest.raises(plan.ExecutionPlanError): plan.validate_spec(REPO, modified, expected_sha256=sha(encoded(modified)))


def test_successful_ci_observation_is_not_inference_admission():
    result = plan.validate_ci_observation(ci(), expected_source_commit=COMMIT)
    assert result["status"] == "source_ci_observed_success" and not result["inference_admitted"]
    assert result["observation_sha256"] == sha(encoded(ci()))


@pytest.mark.parametrize("field,value", (("head_sha", "b" * 40), ("repository", {"full_name": "other/repo"}),
    ("path", ".github/workflows/other.yml"), ("name", "other"), ("event", "workflow_dispatch"), ("id", None)))
def test_other_ci_is_not_evidence_for_this_source(field, value):
    observation = ci()
    observation["run"][field] = value
    with pytest.raises(plan.ExecutionPlanError): plan.validate_ci_observation(observation, expected_source_commit=COMMIT)


@pytest.mark.parametrize("part", ("run", "job"))
@pytest.mark.parametrize("status,conclusion", (("in_progress", None), ("completed", "failure"), ("completed", "cancelled")))
def test_pending_or_failed_ci_blocks(part, status, conclusion):
    observation = ci()
    target = observation["run"] if part == "run" else observation["jobs"]["jobs"][0]
    target.update(status=status, conclusion=conclusion)
    with pytest.raises(plan.ExecutionPlanBlocked): plan.validate_ci_observation(observation, expected_source_commit=COMMIT)


@pytest.mark.parametrize("change", ("pagination", "missing", "duplicate", "wrong_run", "wrong_sha"))
def test_job_inventory_and_binding_required(change):
    observation = ci()
    jobs = observation["jobs"]["jobs"]
    if change == "pagination": observation["jobs"]["total_count"] = 4
    elif change == "missing": jobs.pop(); observation["jobs"]["total_count"] = 2
    elif change == "duplicate": jobs[1] = deepcopy(jobs[0])
    elif change == "wrong_run": jobs[0]["run_id"] = 999
    else: jobs[0]["head_sha"] = "b" * 40
    with pytest.raises(plan.ExecutionPlanError): plan.validate_ci_observation(observation, expected_source_commit=COMMIT)


@pytest.mark.parametrize("change", ("none", "worktree", "head", "plan", "canonical"))
def test_published_source_and_later_plan_commit(tmp_path, monkeypatch, change):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, stderr=subprocess.PIPE).decode().strip()
    git("init", "-q")
    git("config", "user.name", "Synthetic test")
    git("config", "user.email", "synthetic@example.invalid")
    component = tmp_path / "component.py"
    component.write_bytes(b"# synthetic source fixture\n")
    git("add", "component.py")
    git("commit", "-qm", "synthetic source")
    source = git("rev-parse", "HEAD")
    blueprint = load_blueprint(REPO)
    monkeypatch.setattr(plan, "CANONICAL_REPOSITORY", str(tmp_path))
    monkeypatch.setattr(plan, "load_blueprint", lambda _: blueprint)
    monkeypatch.setattr(plan, "fingerprints", lambda _: {"component.py": sha(component.read_bytes())})
    spec = plan.build_spec(tmp_path, source_commit=source, reviewer_ids=("fixture-reviewer",), reconciler_ids=("fixture-reconciler",))
    target = tmp_path / plan.PLAN_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(encoded(spec))
    git("add", plan.PLAN_PATH)
    git("commit", "-qm", "synthetic plan publication")
    if change in ("worktree", "head"):
        component.write_bytes(b"# changed synthetic source\n")
        if change == "head":
            git("add", "component.py")
            git("commit", "-qm", "source drift")
    elif change == "plan": target.write_bytes(encoded({**spec, "inference_admitted": True}))
    elif change == "canonical": monkeypatch.setattr(plan, "CANONICAL_REPOSITORY", str(tmp_path / "other-copy"))
    if change == "none":
        assert plan.assert_published_sources(tmp_path, spec, expected_sha256=sha(encoded(spec))) == git("rev-parse", "HEAD")
    else:
        with pytest.raises(plan.ExecutionPlanError): plan.assert_published_sources(tmp_path, spec, expected_sha256=sha(encoded(spec)))
