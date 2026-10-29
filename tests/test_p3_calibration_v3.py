"""Prospective v3 exclusions, isolation, proof gates and pre-inference freeze checks."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from creative_machine.formal_routes import calibration_protocol_v3 as protocol
from creative_machine.formal_routes.bedrock_runner import BedrockAgentConfig, render_workspace
from creative_machine.formal_routes.calibration_review_v3 import materialize_v3, review_v3
from creative_machine.formal_routes.calibration_worlds_v3 import (
    CALIBRATION_LEVELS, DEV_SEEDS, REPO, WorldV3Spec, build_v3, calibration_orbits, candidates,
    development_orbits, exclusion_audit, load_v3, sample_pairs,
)
from creative_machine.formal_routes.conceptual_generator import action_at, pair_orbit, write_conceptual
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY, sandbox_process
from creative_machine.formal_routes.workspace import audit_workspace

PLAN = REPO / "docs/p3/calibration_conceptual_plan_v3.json"
LOCAL_LEAN = shutil.which("lake") is not None and Path(CODEX_BINARY).is_file()


@pytest.mark.parametrize("family,seed,phase", [
    ("invariant", DEV_SEEDS[0], "main"), ("invariant", "a" * 16, "development"),
    ("representation", DEV_SEEDS[0], "calibration"), ("unknown", DEV_SEEDS[0], "development"),
])
def test_undeclared_development_and_main_generation_are_forbidden(family, seed, phase):
    with pytest.raises(ValueError):
        WorldV3Spec(family, seed, phase)


@pytest.mark.parametrize("family", ("invariant", "representation"))
def test_development_instances_are_deterministic_and_declared(family, tmp_path):
    for seed in DEV_SEEDS:
        spec = WorldV3Spec(family, seed, "development")
        one, two = build_v3(spec), build_v3(spec)
        assert one.files == two.files
        assert seed.upper() not in spec.world_id
        assert not one.metadata["eligible_for_main"] and not one.metadata["eligible_for_calibration"]
        path = write_conceptual(one, tmp_path.resolve() / spec.world_id)
        assert load_v3(path, phase="development") == one.metadata
        with pytest.raises(ValueError, match="phase"):
            load_v3(path, phase="calibration")
        if family == "invariant":
            assert one.metadata["parameters"]["conserved_value"] in (2, 3)
            assert "different_components" in one.files["Hidden/Diagnostics.lean"]
    assert not set(CALIBRATION_LEVELS) & {0, 1, 2, 3}


def test_short_stratum_really_is_exhausted_and_replacement_remains_available():
    report = exclusion_audit()
    assert report["old_short_holdout_remaining"] == 0
    assert report["replacement_holdout_remaining_after_old_development"] == 59
    assert all(item["literal_orbits"] > 0 for item in report["remaining_after_all_declared_development"])
    old, expanded = development_orbits(), calibration_orbits()
    assert old < expanded
    for seed in DEV_SEEDS:
        pairs, _ = sample_pairs(seed, old)
        assert {pair_orbit(pair) for pair in pairs}.issubset(expanded)
        for index, (u, v) in enumerate(pairs):
            assert len(u) == len(v) == (6 if index == 0 else 8)
            assert u.count("a") == v.count("a") and action_at(u) != action_at(v)
        for point in ((0, 0), (0, 1), (1, 0), (1, 1)):
            assert action_at(pairs[1][0], point, bits=True) == action_at(pairs[1][1], point, bits=True)
    assert candidates(6, "same_action", old) == []


@pytest.fixture(params=("invariant", "representation"))
def development_world(request, tmp_path):
    spec = WorldV3Spec(request.param, DEV_SEEDS[0], "development")
    return write_conceptual(build_v3(spec), tmp_path.resolve() / spec.world_id)


def test_evaluator_payloads_expose_no_sibling_source_or_metadata(development_world, tmp_path):
    for holdout in (1, 2):
        for bridge in (None, "oracle"):
            record = materialize_v3(development_world, f"holdout{holdout}", bridge, tmp_path / f"cell-{holdout}-{bridge}")
            assert audit_workspace(record) == []
            text = render_workspace(record)
            assert f"Holdout{3-holdout}Statement" not in text
            assert all(marker not in text for marker in ("source_solution", "comparisonSeed", "metadata.json", "Sources/"))
            assert ("FILE Bridge.lean" in text) == bool(bridge)
            assert "FILE TASK.md" in text


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_corrected_development_proofs_and_negative_controls(development_world):
    report = review_v3(development_world)
    assert report["structural_checks_passed"], json.dumps(report)
    assert report["model_calls"] == 0
    assert len(report["closure_checks"]) == 6 and len(report["automatic_probes"]) == 9


@pytest.mark.parametrize("family", ("invariant", "representation"))
@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_second_declared_seed_compiles(tmp_path, family):
    spec = WorldV3Spec(family, DEV_SEEDS[1], "development")
    world = build_v3(spec)
    root = write_conceptual(world, tmp_path.resolve() / spec.world_id)
    modules = [p.removesuffix(".lean").replace("/", ".") for p in world.metadata["lean_checks"]["must_compile"]]
    built = sandbox_process(["/opt/homebrew/bin/lake", "build", *modules], cwd=root, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr


@pytest.mark.skipif(not LOCAL_LEAN, reason="local sandbox/Lean unavailable")
def test_old_n_variation_has_equal_reachability():
    spec = importlib.util.spec_from_file_location("p3_generation_audit_v3", REPO / "scripts/p3_generation_audit_v3.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.audit()
    assert report["equal_reachability_verified"] and report["model_calls"] == 0


@pytest.fixture
def frozen_plan(monkeypatch):
    if not PLAN.exists():
        pytest.skip("no v3 calibration sampled/frozen yet; do not sample within a test")
    # These are offline protocol tests, not admission of this machine to run
    # the historical experiment. Supply its recorded environment explicitly;
    # production environment() and all fingerprint/drift checks stay intact.
    recorded_environment = json.loads(PLAN.read_text())["environment"]
    monkeypatch.setattr(protocol, "environment", lambda: copy.deepcopy(recorded_environment))
    return protocol.load_plan_v3(REPO, PLAN)


def test_frozen_v3_preserves_model_interface_and_budget(frozen_plan):
    assert frozen_plan["agent"] == as_original_v2_config()
    assert frozen_plan["gate_rule"] == protocol.GATE
    assert frozen_plan["reserved_worst_case_usd"] == pytest.approx(13.2)
    assert frozen_plan["max_total_cost_usd"] == 15.0
    for world in frozen_plan["worlds"]:
        metadata = load_v3(REPO / world["path"], phase="calibration")
        if world["family"] == "invariant":
            assert metadata["parameters"]["conserved_value"] in CALIBRATION_LEVELS
        else:
            assert all(pair_orbit(pair) not in calibration_orbits() for pair in metadata["parameters"]["pairs"])


def as_original_v2_config():
    return json.loads((REPO / "docs/p3/calibration_bedrock_plan_v2.json").read_text())["agent"]


@pytest.mark.parametrize("change", ("gate", "budget", "effort", "duplicates", "world_escape", "harness", "pricing", "environment"))
def test_plan_mutations_rejected_before_model_access(frozen_plan, tmp_path, change):
    plan = copy.deepcopy(frozen_plan)
    if change == "gate":
        plan["gate_rule"]["baseline_at_most"] = 4
    elif change == "budget":
        plan["max_total_cost_usd"] = 100
    elif change == "effort":
        plan["agent"]["effort"] = "low"
    elif change == "duplicates":
        plan["cells"][1] = plan["cells"][0]
    elif change == "world_escape":
        plan["worlds"][0]["path"] = "../outside"
    elif change == "harness":
        plan["harness_sha256"].pop(next(iter(plan["harness_sha256"])))
    elif change == "environment":
        plan["environment"]["python"] = "0.0.0-synthetic-drift"
    else:
        plan["pricing"]["regional_multiplier"] = 1.0
    path = tmp_path / "plan.json"
    protocol.save_new(path, plan)
    with pytest.raises(ValueError):
        protocol.load_plan_v3(REPO, path)


def test_runtime_environment_drift_is_still_rejected(frozen_plan, monkeypatch):
    actual = copy.deepcopy(frozen_plan["environment"])
    actual["python"] = "0.0.0-synthetic-host"
    monkeypatch.setattr(protocol, "environment", lambda: actual)
    with pytest.raises(ValueError, match="environment"):
        protocol.load_plan_v3(REPO, PLAN)


def test_every_frozen_blob_must_be_in_head(frozen_plan, monkeypatch):
    missing = frozen_plan["worlds"][0]["path"] + "/Hidden/Oracle.lean"
    visited = []

    def fake_git(args, **kwargs):
        relative = args[2].removeprefix("HEAD:")
        visited.append(relative)
        return subprocess.CompletedProcess(args, 1 if relative == missing else 0,
            b"" if relative == missing else (REPO / relative).read_bytes(), b"")

    monkeypatch.setattr(protocol.subprocess, "run", fake_git)
    with pytest.raises(RuntimeError, match="committed verbatim"):
        protocol.assert_committed_v3(REPO, PLAN, frozen_plan)
    assert missing in visited


def test_simulated_run_never_uses_provider_and_never_overwrites(frozen_plan, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(protocol, "require_run_root", lambda *args: None)  # Only this simulated loop uses a test directory.
    monkeypatch.setattr(protocol, "assert_committed_v3", lambda *args: "simulated-test-commit")
    monkeypatch.setattr(protocol, "preflight_v3", lambda *args: {"ok": True, "model_calls": 0})

    def fake_session(record, **kwargs):
        assert kwargs["config"] == BedrockAgentConfig()
        seen.append(record.condition)
        return {"status": "solved", "target_solved": True, "infrastructure_failure": False, "uncertain_request": False,
                "requests": 0, "error": None, "cost_usd_at_published_rates": 0,
                "tokens": {k: 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}}

    monkeypatch.setattr(protocol, "run_bedrock_session", fake_session)
    result = protocol.run_v3(REPO, PLAN, tmp_path)
    assert len(seen) == 8
    assert result["baseline_successes"] == 4 and result["oracle_successes"] == 4
    assert not result["gate_passed"] and result["cost_usd_at_published_rates"] == 0
    with pytest.raises(FileExistsError):
        protocol.run_v3(REPO, PLAN, tmp_path)
    assert len(seen) == 8


def test_alternate_output_location_cannot_enable_another_experiment(tmp_path):
    with pytest.raises(ValueError, match="run root is frozen"):
        protocol.run_v3(REPO, PLAN, tmp_path)
