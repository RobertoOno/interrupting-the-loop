"""Development fixture provenance, isolation, proof checks, and negative controls."""

import json
from pathlib import Path
import shutil

import pytest

from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.prototypes import (
    FILES, PROTOTYPES, TARGETS, _ordinary_rejection, load_prototype,
    materialize_prototype_cell, oracle_solution, review_prototype, seal_prototype,
)
from creative_machine.formal_routes.workspace import audit_workspace

ROOT = Path(__file__).resolve().parent.parent
WORLDS = ROOT / "worlds/prototypes"


@pytest.mark.parametrize("name", PROTOTYPES)
def test_prototypes_are_hand_authored_and_ineligible(name):
    metadata = load_prototype(WORLDS / name)
    assert metadata["phase"] == "prototype"
    assert metadata["sampling"] == "hand_authored_not_randomly_sampled"
    assert metadata["eligible_for_main"] is False
    assert metadata["eligible_for_calibration"] is False
    assert metadata["sources_ready"] is False


@pytest.mark.parametrize("name", PROTOTYPES)
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("bridge", [False, True])
def test_prototype_probe_only_exposes_one_target(tmp_path, name, target, bridge):
    record = materialize_prototype_cell(WORLDS / name, target, bridge, tmp_path / "cell")
    assert audit_workspace(record) == []
    files = {str(path.relative_to(record.path)) for path in record.path.rglob("*") if path.is_file()}
    expected = {"lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"}
    assert files == expected | ({"Bridge.lean"} if bridge else set())
    contents = "\n".join(path.read_text() for path in record.path.rglob("*.lean"))
    for other, (_, statement, _) in TARGETS.items():
        assert (statement in contents) == (other == target)
    assert "bit_cannot_distinguish" not in contents
    assert "no_nonzero_linear_conservation" not in contents
    (record.path / "extra.txt").write_text("forbidden input")
    assert "undeclared output: extra.txt" in audit_workspace(record)


def test_source_tampering_is_rejected(tmp_path):
    name = next(iter(PROTOTYPES))
    root = tmp_path / name
    shutil.copytree(WORLDS / name, root, ignore=shutil.ignore_patterns(".lake", "lake-manifest.json"))
    (root / "World/Base.lean").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_prototype(root)


def test_sealing_does_not_overwrite_existing_provenance(tmp_path):
    name = next(iter(PROTOTYPES))
    root = tmp_path / name
    for relative in FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORLDS / name / relative, target)
    seal_prototype(root)
    before = (root / "manifest.sha256").read_bytes()
    with pytest.raises(FileExistsError):
        seal_prototype(root)
    assert (root / "manifest.sha256").read_bytes() == before


@pytest.mark.parametrize("error", ["Lean timeout while checking Solution.lean",
    "Lean rejected Solution.lean: unknown identifier X",
    "Lean rejected Solution.lean: maximum number of heartbeats",
    "frozen target failed to build: error"])
def test_infrastructure_or_syntax_error_is_not_a_failed_baseline(error):
    assert not _ordinary_rejection({"solved": False, "errors": [error], "audit": "", "stderr": ""})


@pytest.mark.parametrize("name", PROTOTYPES)
def test_each_archived_oracle_closure_has_the_exact_output_contract(name):
    for target, (_, statement, _) in TARGETS.items():
        source = oracle_solution(WORLDS / name, target)
        assert f"theorem evaluation_solution : {statement}" in source
        assert source.count("import ") == 2
        assert "import Hidden" not in source


@pytest.mark.parametrize("name", PROTOTYPES)
@pytest.mark.skipif(shutil.which("lake") is None or not Path(CODEX_BINARY).is_file(),
                    reason="the local Lean sandbox is unavailable")
def test_prototype_kernel_closures_probes_and_semantic_mutation(name):
    result = review_prototype(WORLDS / name)
    assert result["model_calls"] == 0
    assert result["review_completed"] and result["structural_checks_passed"], json.dumps(result)
    assert len(result["oracle_closures"]) == 3
    assert len(result["automatic_probes"]) == 9
    assert all(probe["ordinary_rejection"] for probe in result["automatic_probes"])
    assert result["mutation"]["negated_target_verified"]
    assert result["mutation"]["original_oracle_rejected"]
