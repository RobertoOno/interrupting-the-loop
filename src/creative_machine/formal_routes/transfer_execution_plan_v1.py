"""Prospective execution-spec contract; no generation, claims or reservations.

The frozen development blueprint is an input, never overwritten. A spec cannot
be built until the experimental launcher and independent auditor exist. A spec
hash alone never authorizes inference: live preflight and finance remain gates.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
import subprocess

from . import bridge_content_v1 as content
from .production_audit_v1 import _decode
from .production_runner_v1 import production_config
from .transfer_design_v1 import BLUEPRINT_PATH, SOURCE_PLAN_PATH, SOURCE_EVIDENCE_PATH, OWN_FILES, encoded, load_blueprint, sha, _safe_bytes
from .transfer_lifecycle_v1 import is_hash
from .transfer_transport_v1 import ENDPOINT, SDK_VERSION

VERSION = "p3_transfer_execution_plan_v1"
PLAN_PATH = "docs/p3/transfer_execution_plan_v1.json"
CANONICAL_REPOSITORY = "/Users/robertoonofilho/wrk/creative-machine"
RUN_ID = "p3a_transfer_development_v1"
REGISTRY_REL = "runs/worker-claims"
BUDGET_REL = "runs/aws-budget/claude_daily.jsonl"
OUTPUT_REL = "runs/" + RUN_ID
REQUIRED_EXPERIMENTAL_FILES = (
    "src/creative_machine/formal_routes/transfer_experiment_v1.py",
    "src/creative_machine/formal_routes/transfer_experiment_audit_v1.py",
    "scripts/p3_transfer_experiment_v1.py",
    "tests/test_p3_transfer_experiment_v1.py",
    "tests/test_p3_transfer_experiment_audit_v1.py",
)
CI_JOBS = ("pytest", "transfer-rehearsal", "transfer-batch-audit")


class ExecutionPlanError(ValueError):
    pass


class ExecutionPlanBlocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ExecutionPlanError(message)


def identities(values, label):
    require(isinstance(values, tuple) and bool(values)
            and all(isinstance(v, str) and bool(v.strip()) and len(v) <= 120 for v in values)
            and len(set(values)) == len(values), label + " allowlist")
    return list(values)


def policy(blueprint, *, source_commit, reviewer_ids, reconciler_ids):
    require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit), "full source commit required")
    return {"version": VERSION, "status": "FROZEN_SPEC_NOT_ADMITTED", "data_kind": "experimental",
        "blueprint_sha256": sha(encoded(blueprint)), "source_commit": source_commit,
        "canonical_repository": CANONICAL_REPOSITORY, "run_id": RUN_ID,
        "worker_registry": REGISTRY_REL, "budget_journal": BUDGET_REL, "output": OUTPUT_REL,
        "agent": asdict(production_config()), "sdk_version": SDK_VERSION, "endpoint": ENDPOINT,
        "max_retries": 0, "max_parallel": 2, "max_sessions": 26, "batch_reserve_usd": "50",
        "aws_daily_cap_usd": "150", "budget_timezone": "America/Sao_Paulo",
        "reviewer_ids": identities(reviewer_ids, "reviewer"), "reconciler_ids": identities(reconciler_ids, "reconciler"),
        "content_policy_sha256": sha(encoded(content.policy())), "ci_jobs": list(CI_JOBS),
        "phase_barrier": blueprint["phase_barrier"], "selection_policy": blueprint["selection_policy"],
        "control_gate": blueprint["contemporary_control_gate"],
        "on_technical_failure": "preserve_evidence_and_reservation_halt_no_retry_or_replacement",
        "review_process": "all_six_proposers_audited_then_masked_first_review_before_recipients",
        "unresolved_review": "wait_without_new_admissions_no_automatic_adjudication",
        "evidence_profile": "native_host_observation_with_independent_raw_transport_and_batch_audits",
        "scientific_scope": blueprint["scientific_scope"], "provider_authenticated": False,
        "inference_admitted": False, "main_sample_admitted": False, "mechanistic_stage_admitted": False}


def fingerprints(repository):
    repository = Path(repository)
    missing = [rel for rel in REQUIRED_EXPERIMENTAL_FILES if not (repository / rel).is_file()]
    if missing:
        raise ExecutionPlanBlocked("experimental components missing before freeze: " + ", ".join(missing))
    source_plan = _decode(_safe_bytes(repository, SOURCE_PLAN_PATH))
    paths = set(source_plan["harness_and_world_sha256"]) | set(REQUIRED_EXPERIMENTAL_FILES) | set(OWN_FILES)
    paths.update((BLUEPRINT_PATH, SOURCE_PLAN_PATH, ".github/workflows/tests.yml", "pyproject.toml",
                  "src/creative_machine/__init__.py", "src/creative_machine/aws_daily_budget.py",
                  "tests/test_aws_daily_budget.py"))
    for pattern in ("src/creative_machine/formal_routes/*.py", "tests/test_p3_*.py", SOURCE_EVIDENCE_PATH + "/*.json"):
        paths.update(p.relative_to(repository).as_posix() for p in repository.glob(pattern))
    # Do not include the plan itself: the source commit precedes the plan's
    # publication. CLAUDE/PLANO and unrelated user artifacts remain outside it.
    return {rel: sha(_safe_bytes(repository, rel)) for rel in sorted(paths)}


def build_spec(repository: Path, *, source_commit: str, reviewer_ids: tuple, reconciler_ids: tuple):
    blueprint = load_blueprint(repository)
    return {**policy(blueprint, source_commit=source_commit, reviewer_ids=reviewer_ids, reconciler_ids=reconciler_ids),
            "implementation_sha256": fingerprints(repository)}


def validate_spec(repository: Path, spec: dict, *, expected_sha256: str):
    require(is_hash(expected_sha256) and isinstance(spec, dict) and sha(encoded(spec)) == expected_sha256, "external execution spec reference")
    require(isinstance(spec.get("reviewer_ids"), list) and isinstance(spec.get("reconciler_ids"), list), "execution identities schema")
    expected = build_spec(repository, source_commit=spec.get("source_commit"),
                          reviewer_ids=tuple(spec["reviewer_ids"]), reconciler_ids=tuple(spec["reconciler_ids"]))
    require(encoded(spec) == encoded(expected), "execution policy/dependency drift")
    return expected


def assert_published_sources(repository: Path, spec: dict, *, expected_sha256: str):
    """Read-only local Git checks. The CI receipt is separately fetched/checked.

    A source commit and the later plan-publication commit avoid a self-hash
    cycle. Neither local Git nor a JSON CI receipt proves the remote by itself.
    """
    spec = validate_spec(repository, spec, expected_sha256=expected_sha256)
    require(Path(repository).resolve() == Path(CANONICAL_REPOSITORY), "use canonical working repository, never the other copy")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repository, timeout=15)
    source = spec["source_commit"]
    require(git("rev-parse", source + "^{commit}").decode().strip() == source, "source commit unavailable")
    git("merge-base", "--is-ancestor", source, "HEAD")
    for rel, digest in spec["implementation_sha256"].items():
        require(sha(git("show", source + ":" + rel)) == digest == sha(git("show", "HEAD:" + rel)), "source not published/changed: " + rel)
    require(git("show", "HEAD:" + PLAN_PATH) == _safe_bytes(repository, PLAN_PATH) == encoded(spec), "execution plan not committed")
    return git("rev-parse", "HEAD").decode().strip()


def validate_ci_observation(observation: dict, *, expected_source_commit: str):
    """Validate retained output of separate GitHub run/jobs reads, not hashes.

    The host must fetch both objects through authenticated GitHub reads and
    retain their bytes outside the model workspace. This is structural evidence,
    not cryptographic authentication of an arbitrary caller-supplied JSON blob.
    """
    require(isinstance(observation, dict) and set(observation) == {"run", "jobs"}, "CI observation schema")
    run, jobs = observation["run"], observation["jobs"]
    require(isinstance(run, dict) and isinstance(jobs, dict), "CI run/jobs schema")
    require(type(run.get("id")) is int and run["id"] > 0, "CI run ID required")
    require(run.get("head_sha") == expected_source_commit and re.fullmatch(r"[0-9a-f]{40}", expected_source_commit), "CI source commit mismatch")
    require(run.get("repository", {}).get("full_name") == "RobertoOno/creative-machine"
            and run.get("path") == ".github/workflows/tests.yml" and run.get("name") == "tests"
            and run.get("event") == "push", "CI repository/workflow/event mismatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ExecutionPlanBlocked("source CI not yet approved")
    rows = jobs.get("jobs")
    require(isinstance(rows, list) and jobs.get("total_count") == len(rows), "incomplete/paginated CI jobs")
    require(len(rows) == len(CI_JOBS) and {r.get("name") for r in rows} == set(CI_JOBS), "missing/duplicate/unexpected CI job")
    for row in rows:
        require(row.get("run_id") == run.get("id") and row.get("head_sha") == expected_source_commit, "CI job run/commit mismatch")
        if row.get("status") != "completed" or row.get("conclusion") != "success":
            raise ExecutionPlanBlocked("required CI job not approved: " + row["name"])
    return {"status": "source_ci_observed_success", "run_id": run["id"], "source_commit": expected_source_commit,
            "observation_sha256": sha(encoded(observation)), "jobs": list(CI_JOBS), "inference_admitted": False}
