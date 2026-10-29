"""Allowlist-only materialization of proposer and evaluator workspaces."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .validation import validate_world


class ProposerArm(str, Enum):
    D0 = "D0"
    D = "D"
    C2 = "C2"


class EvaluatorCondition(str, Enum):
    NO_BRIDGE = "no_bridge"
    CANDIDATE_BRIDGE = "candidate_bridge"
    ORACLE_BRIDGE = "oracle_bridge"


@dataclass(frozen=True)
class WorkspaceRecord:
    path: Path
    world_id: str
    role: str
    condition: str
    copied_hashes: dict[str, str]
    allowed_outputs: tuple[str, ...]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_destination(destination: Path | str) -> Path:
    root = Path(destination)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"workspace is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _copy(world: Path, destination: Path, rel: str, target_rel: str | None = None) -> str:
    source = world / rel
    target = destination / (target_rel or rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return _hash(target)


def _metadata(world: Path) -> dict:
    report = validate_world(world)
    report.require_ok()
    return json.loads((world / "metadata.json").read_text(encoding="utf-8"))


def audit_workspace(record: WorkspaceRecord) -> list[str]:
    """Check immutable inputs and reject undeclared files after an agent session."""
    errors: list[str] = []
    root = record.path.resolve()
    expected = set(record.copied_hashes)
    allowed = set(record.allowed_outputs)
    actual: set[str] = set()
    for path in root.rglob("*"):
        if ".lake" in path.parts or path.name == "lake-manifest.json":
            continue
        rel = str(path.relative_to(root))
        if path.is_symlink():
            errors.append(f"symlink forbidden: {rel}")
        elif path.is_file():
            actual.add(rel)
    for rel in sorted(expected - actual):
        errors.append(f"immutable input missing: {rel}")
    for rel in sorted(actual - expected - allowed):
        errors.append(f"undeclared output: {rel}")
    for rel, expected_hash in record.copied_hashes.items():
        target = root / rel
        if target.is_file() and not target.is_symlink() and _hash(target) != expected_hash:
            errors.append(f"immutable input changed: {rel}")
    return errors


def materialize_proposer(
    world: Path | str,
    arm: ProposerArm | str,
    destination: Path | str,
) -> WorkspaceRecord:
    """Expose only Base, visible target, and the arm-specific source."""
    source_root = Path(world).resolve()
    selected = ProposerArm(arm)
    metadata = _metadata(source_root)
    dest = _empty_destination(destination)
    copied: dict[str, str] = {}
    for rel in ("lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeVisible.lean"):
        copied[rel] = _copy(source_root, dest, rel)
    if selected is ProposerArm.D:
        copied["SOURCE.md"] = _copy(source_root, dest, "Sources/Relevant.md", "SOURCE.md")
    elif selected is ProposerArm.C2:
        copied["SOURCE.md"] = _copy(source_root, dest, "Sources/Sham.md", "SOURCE.md")

    namespace = metadata["roles"]["namespace"]
    task = (
        "Prove the frozen visible statement. Produce exactly two files:\n"
        "- Bridge.lean imports only World.Base and declares theorem candidate_bridge.\n"
        "- Solution.lean imports World.ChallengeVisible and Bridge and declares\n"
        f"  theorem candidate_solution : {namespace}.VisibleStatement.\n"
        f"Both declarations may be global or inside exactly namespace {namespace}.\n"
        "Do not change the supplied files.\n"
    )
    (dest / "TASK.md").write_text(task, encoding="utf-8")
    copied["TASK.md"] = _hash(dest / "TASK.md")
    exposed = {str(path.relative_to(dest)) for path in dest.rglob("*") if path.is_file()}
    if any(path.startswith("Hidden/") or "Holdout" in path or path == "metadata.json" for path in exposed):
        raise AssertionError("hidden artifact leaked into proposer workspace")
    return WorkspaceRecord(
        dest,
        metadata["world_id"],
        "proposer",
        selected.value,
        copied,
        ("Bridge.lean", "Solution.lean"),
    )


def materialize_evaluator(
    world: Path | str,
    holdout: int,
    condition: EvaluatorCondition | str,
    destination: Path | str,
    *,
    candidate_bridge: Path | str | None = None,
) -> WorkspaceRecord:
    """Expose one sibling target and optionally one immutable bridge."""
    if holdout not in {1, 2}:
        raise ValueError("holdout must be 1 or 2")
    source_root = Path(world).resolve()
    selected = EvaluatorCondition(condition)
    if selected is EvaluatorCondition.CANDIDATE_BRIDGE and candidate_bridge is None:
        raise ValueError("candidate_bridge path is required")
    if selected is not EvaluatorCondition.CANDIDATE_BRIDGE and candidate_bridge is not None:
        raise ValueError("candidate_bridge is only valid in candidate_bridge condition")
    metadata = _metadata(source_root)
    dest = _empty_destination(destination)
    copied: dict[str, str] = {}
    for rel in ("lakefile.toml", "lean-toolchain", "World/Base.lean"):
        copied[rel] = _copy(source_root, dest, rel)
    target_rel = f"World/Holdout{holdout}.lean"
    copied["World/ChallengeEvaluation.lean"] = _copy(
        source_root, dest, target_rel, "World/ChallengeEvaluation.lean"
    )
    bridge_name = None
    if selected is EvaluatorCondition.ORACLE_BRIDGE:
        copied["Bridge.lean"] = _copy(source_root, dest, "Hidden/Oracle.lean", "Bridge.lean")
        bridge_name = metadata["roles"]["oracle_bridge"]
    elif selected is EvaluatorCondition.CANDIDATE_BRIDGE:
        bridge_source = Path(candidate_bridge).resolve()
        if not bridge_source.is_file():
            raise FileNotFoundError(bridge_source)
        shutil.copy2(bridge_source, dest / "Bridge.lean")
        copied["Bridge.lean"] = _hash(dest / "Bridge.lean")
        bridge_name = "candidate_bridge"

    statement = metadata["roles"]["holdout_statements"][holdout - 1]
    namespace = metadata["roles"]["namespace"]
    bridge_line = (
        f"An immutable bridge named {bridge_name} is available in Bridge.lean.\n"
        if bridge_name
        else "No bridge is supplied.\n"
    )
    import_line = (
        "Solution.lean must import exactly World.ChallengeEvaluation and Bridge.\n"
        if bridge_name
        else "Solution.lean must import only World.ChallengeEvaluation.\n"
    )
    task = (
        f"Prove {namespace}.{statement} from World/ChallengeEvaluation.lean.\n"
        + bridge_line
        + import_line
        + "Declare theorem evaluation_solution with exactly that frozen statement type, either\n"
        + f"globally or inside exactly namespace {namespace}.\n"
        + "Write only Solution.lean; do not edit supplied files or any bridge.\n"
    )
    (dest / "TASK.md").write_text(task, encoding="utf-8")
    copied["TASK.md"] = _hash(dest / "TASK.md")
    exposed = {str(path.relative_to(dest)) for path in dest.rglob("*") if path.is_file()}
    if any(path.startswith("Hidden/") or path == "metadata.json" for path in exposed):
        raise AssertionError("hidden artifact leaked into evaluator workspace")
    if any(f"Holdout{other}" in path for other in {1, 2} - {holdout} for path in exposed):
        raise AssertionError("the other sibling leaked into evaluator workspace")
    return WorkspaceRecord(
        dest,
        metadata["world_id"],
        "evaluator",
        selected.value,
        copied,
        ("Solution.lean",),
    )
