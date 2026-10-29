"""Development-only 26-slot matrix; never an inference launcher or admission.

All labels and dependencies here are HOST metadata, not a recipient prompt.
The separate execution plan must bind the remaining recipient/audit/budget
components before providing any client. Historical sources remain immutable.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from .calibration_worlds_v3 import load_v3
from .production_runner_v1 import interface_hashes, production_config, SELECTION_POLICY

DESIGN_ID = "p3_production_transfer_development_v1"
BLUEPRINT_PATH = "docs/p3/transfer_design_draft_v1.json"
ORDER_SEED = 2026090802
ARMS = ("D0", "D", "C2")
WORLDS = ("worlds/calibration/CAL3_I_E87C49876088749B",
          "worlds/calibration/CAL3_R_F76437525B190ECB")
SOURCE_PLAN_PATH = "docs/p3/source_matching_plan_v1.json"
SOURCE_PLAN_SHA256 = "bdaa42d196d15e58b6bbb045468b9056b1b4c14332c0859eff6a15ddf5ee2aea"
SOURCE_EVIDENCE_PATH = "docs/p3/source_matching_evidence_v1"
SOURCE_MANIFEST_SHA256 = "967f75c5fc6f94aca195d8bf623284d955b36f09cc0e41a5a3249e2aa6cdc0df"
GATE = {"complete_pairs": 4, "oracle_at_least": 3, "baseline_at_most": 2, "net_gain_at_least": 2}
OWN_FILES = (
    "src/creative_machine/formal_routes/transfer_design_v1.py",
    "src/creative_machine/formal_routes/transfer_analysis_v1.py",
    "scripts/p3_transfer_development_v1.py",
    "tests/test_p3_transfer_design_v1.py", "tests/test_p3_transfer_analysis_v1.py",
    "docs/p3/MATRIZ_E_ANALISE_TRANSFERENCIA_V1.md",
)


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell_id(world_id: str, arm: str, holdout: int | None) -> str:
    return "T26_" + sha(f"{DESIGN_ID}:identity:{world_id}:{arm}:{holdout}".encode())[:12].upper()


def matrix() -> list[dict]:
    """Two deterministic hash-ranked permutations, fixed independently of data."""
    proposers, recipients = [], []
    for world, family in zip(WORLDS, ("invariant", "representation")):
        world_id = Path(world).name
        common = {"world": world, "world_id": world_id, "family": family}
        for arm in ARMS:
            proposers.append({**common, "cell_id": _cell_id(world_id, arm, None),
                "phase": "production", "role": "proposer", "arm": arm, "holdout": None,
                "parent_proposer_id": None, "baseline_cell_id": None, "bridge_kind": None})
        for holdout in (1, 2):
            baseline = _cell_id(world_id, "B", holdout)
            for arm in (*ARMS, "B", "O"):
                recipients.append({**common, "cell_id": _cell_id(world_id, arm, holdout),
                    "phase": "evaluation", "role": "recipient", "arm": arm, "holdout": holdout,
                    "parent_proposer_id": _cell_id(world_id, arm, None) if arm in ARMS else None,
                    "baseline_cell_id": baseline,
                    "bridge_kind": "candidate" if arm in ARMS else "none" if arm == "B" else "oracle"})
    ordered = []
    for group in (proposers, recipients):
        group.sort(key=lambda c: (sha(f"{ORDER_SEED}:{c['phase']}:{c['cell_id']}".encode()), c["cell_id"]))
        for ordinal, row in enumerate(group, 1):
            ordered.append({**row, "ordinal": len(ordered) + 1, "phase_ordinal": ordinal})
    return ordered


def validate_matrix(cells: list[dict]) -> None:
    if encoded(cells) != encoded(matrix()):
        raise ValueError("matrix labels, worlds, dependencies, cells or ordering drift")


def design_rules() -> dict:
    """Pure policy, also validated when the analyzer is called without the CLI."""
    return {"schema_version": 1, "design_id": DESIGN_ID, "status": "DRAFT_NOT_ADMITTED",
        "order_seed": ORDER_SEED, "ordering_method": "sha256(seed:phase:cell_id), ascending, separate phases",
        "phase_barrier": "all_six_proposers_sealed_and_audited_before_any_recipient",
        "cells": matrix(), "agent": asdict(production_config()),
        "max_parallel": 2, "max_sessions": 26, "nominal_reservation_usd": 42.9,
        "proposed_batch_cap_usd": 50.0, "aws_daily_cap_usd": 150.0,
        "selection_policy": SELECTION_POLICY, "contemporary_control_gate": dict(GATE),
        "pending_admission_components": ["independent_trace_auditor", "bridge_content_and_blinding_policy",
            "recipient_harness", "batch_budget_and_admission", "frozen_execution_plan_preflight_and_ci"],
        "scientific_scope": "Two exposed worlds; descriptive production/transfer diagnostic, not H2 confirmation.",
        "inference_admitted": False, "main_sample_admitted": False, "mechanistic_stage_admitted": False}


def validate_design_rules(blueprint: dict) -> None:
    """Validate structural policy; filesystem provenance belongs to load_blueprint."""
    rules = design_rules()
    extra = {"worlds", "source_matching", "proposer_initial_inputs", "implementation_sha256"}
    if not isinstance(blueprint, dict) or set(blueprint) != set(rules) | extra:
        raise ValueError("invalid blueprint schema")
    if encoded({key: blueprint[key] for key in rules}) != encoded(rules):
        raise ValueError("development design policy drift")
    worlds = blueprint["worlds"]
    if not isinstance(worlds, list) or len(worlds) != 2:
        raise ValueError("exactly two exposed worlds are required")
    for world, path, family in zip(worlds, WORLDS, ("invariant", "representation")):
        if (not isinstance(world, dict) or set(world) != {"path", "world_id", "family", "namespace",
                "eligible_for_main", "manifest_sha256", "oracle_bridge_sha256", "artifact_sha256"}
                or world["path"] != path or world["world_id"] != Path(path).name or world["family"] != family
                or world["namespace"] != "P3." + Path(path).name or world["eligible_for_main"] is not False):
            raise ValueError("world identity or eligibility drift")
        hashes = world["artifact_sha256"]
        if (not isinstance(hashes, dict) or any(not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
                                               for v in (*hashes.values(), world["manifest_sha256"], world["oracle_bridge_sha256"]))
                or hashes.get("Hidden/Oracle.lean") != world["oracle_bridge_sha256"]):
            raise ValueError("invalid world or oracle hashes")
    source = blueprint["source_matching"]
    if (not isinstance(source, dict) or set(source) != {"plan_sha256", "manifest_sha256", "result_sha256"}
            or source["plan_sha256"] != SOURCE_PLAN_SHA256 or source["manifest_sha256"] != SOURCE_MANIFEST_SHA256):
        raise ValueError("closed source matching reference drift")


def _safe_bytes(repository: Path, rel: str) -> bytes:
    path = repository / rel
    if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
        raise ValueError("unsafe design input: " + rel)
    return path.read_bytes()


def build_blueprint(repository: Path) -> dict:
    """Read frozen upstream hashes; no token recount, Lean execution or API call."""
    source_bytes = _safe_bytes(repository, SOURCE_PLAN_PATH)
    manifest_bytes = _safe_bytes(repository, SOURCE_EVIDENCE_PATH + "/manifest.json")
    if sha(source_bytes) != SOURCE_PLAN_SHA256 or sha(manifest_bytes) != SOURCE_MANIFEST_SHA256:
        raise ValueError("closed source-matching provenance drift")
    source_plan, manifest = json.loads(source_bytes), json.loads(manifest_bytes)
    result_bytes = _safe_bytes(repository, SOURCE_EVIDENCE_PATH + "/result.json")
    if sha(result_bytes) != manifest["result.json"]:
        raise ValueError("closed native matching result drift")
    result = json.loads(result_bytes)
    if result["status"] != "complete" or result["matching_passed"] is not True:
        raise ValueError("native source matching must already be closed and passed")
    for rel, expected in source_plan["harness_and_world_sha256"].items():
        if sha(_safe_bytes(repository, rel)) != expected:
            raise ValueError("frozen upstream dependency drift: " + rel)
    if source_plan["agent"] != asdict(production_config()) or source_plan["interface_sha256"] != interface_hashes():
        raise ValueError("production interface differs from the counted interface")
    worlds = []
    for rel in WORLDS:
        metadata = load_v3(repository / rel, phase="calibration")
        worlds.append({"path": rel, "world_id": metadata["world_id"], "family": metadata["family"],
            "namespace": metadata["roles"]["namespace"], "eligible_for_main": False,
            "manifest_sha256": sha(_safe_bytes(repository, rel + "/manifest.sha256")),
            "oracle_bridge_sha256": metadata["artifact_hashes"]["Hidden/Oracle.lean"],
            "artifact_sha256": metadata["artifact_hashes"]})
    return {**design_rules(), "worlds": worlds,
        "source_matching": {"plan_sha256": SOURCE_PLAN_SHA256, "manifest_sha256": SOURCE_MANIFEST_SHA256,
                            "result_sha256": sha(result_bytes)},
        "proposer_initial_inputs": [row for row in source_plan["requests"] if row["kind"] == "initial_proposer"],
        "implementation_sha256": {rel: sha(_safe_bytes(repository, rel)) for rel in OWN_FILES}}


def prepare(repository: Path) -> dict:
    blueprint = build_blueprint(repository)
    with (repository / BLUEPRINT_PATH).open("xb") as handle:
        handle.write(encoded(blueprint))
    return blueprint


def load_blueprint(repository: Path) -> dict:
    data = json.loads(_safe_bytes(repository, BLUEPRINT_PATH))
    if encoded(data) != encoded(build_blueprint(repository)):
        raise ValueError("development blueprint drift; never silently change the matrix")
    return data
