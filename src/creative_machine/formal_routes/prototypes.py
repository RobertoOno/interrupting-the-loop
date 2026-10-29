"""Offline-only review of hand-authored P3 prototypes, not a model experiment.

Keep this separate from the fingerprinted v1/v2 generators and runners. Prototype
fixtures are already exposed during development and are never main-sample inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from .lean_sandbox import sandbox_process
from .submission import STANDARD_LEAN_AXIOMS, axiom_audit_ok, verify_evaluator_solution
from .validation import validate_world
from .workspace import WorkspaceRecord, audit_workspace

PROTOTYPES = {
    "DEV_INVARIANT_V3": {
        "route": "quadratic_conservation",
        "diagnostic_audits": 8,
        "unfold": "start, move1, move2, move3, move4",
        "inductive": "Reaches, Step",
    },
    "DEV_REPRESENTATION_V3": {
        "route": "noncommutative_representation",
        "diagnostic_audits": 11,
        "unfold": "",
        "inductive": "Related",
    },
}
FILES = (
    "lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeVisible.lean",
    "World/Holdout1.lean", "World/Holdout2.lean", "Hidden/Oracle.lean",
    "Hidden/OracleChecks.lean", "Hidden/Diagnostics.lean",
)
TARGETS = {
    "visible": ("World/ChallengeVisible.lean", "VisibleStatement", "oracle_visible"),
    "holdout1": ("World/Holdout1.lean", "Holdout1Statement", "oracle_holdout1"),
    "holdout2": ("World/Holdout2.lean", "Holdout2Statement", "oracle_holdout2"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal_prototype(root: Path) -> dict:
    """Record source provenance once; this does NOT freeze a behavioral protocol."""
    settings = PROTOTYPES[root.name]
    if (root / "metadata.json").exists() or (root / "manifest.sha256").exists():
        raise FileExistsError("prototype provenance exists; do not silently replace hashes")
    for relative in FILES:
        if not (root / relative).is_file() or (root / relative).is_symlink():
            raise ValueError(f"missing source or symlink: {relative}")
    public = list(FILES[:4])
    metadata = {
        "schema_version": 1, "world_id": root.name, "phase": "prototype",
        "status": "DEVELOPMENT_ONLY", "eligible_for_main": False,
        "eligible_for_calibration": False, "prototype_version": "0.1.0",
        "route": settings["route"], "toolchain": "leanprover/lean4:v4.33.1",
        "sampling": "hand_authored_not_randomly_sampled", "sources_ready": False,
        "allowed_axioms": list(STANDARD_LEAN_AXIOMS),
        "public_files": public, "hidden_files": sorted(set(FILES) - set(public)),
        "artifact_hashes": {relative: digest(root / relative) for relative in FILES},
        "roles": {"namespace": f"P3.{root.name}", "oracle_bridge": "oracle_bridge",
                  "visible_statement": "VisibleStatement",
                  "holdout_statements": ["Holdout1Statement", "Holdout2Statement"]},
        "lean_checks": {"must_compile": list(FILES[2:]), "must_fail": [],
                        "axiom_audits": {"Hidden/OracleChecks.lean": 4,
                                         "Hidden/Diagnostics.lean": settings["diagnostic_audits"]}},
    }
    (root / "metadata.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    manifest = "".join(f"{digest(root / rel)}  {rel}\n" for rel in sorted((*FILES, "metadata.json")))
    (root / "manifest.sha256").write_text(manifest)
    load_prototype(root)
    return metadata


def load_prototype(root: Path) -> dict:
    validate_world(root).require_ok()
    metadata = json.loads((root / "metadata.json").read_text())
    if (root.name not in PROTOTYPES or metadata.get("world_id") != root.name
            or metadata.get("phase") != "prototype" or metadata.get("status") != "DEVELOPMENT_ONLY"
            or metadata.get("eligible_for_main") is not False
            or metadata.get("eligible_for_calibration") is not False
            or metadata.get("sources_ready") is not False
            or set(metadata["artifact_hashes"]) != set(FILES)
            or metadata.get("allowed_axioms") != list(STANDARD_LEAN_AXIOMS)):
        raise ValueError("an explicitly development-only prototype is required")
    return metadata


def _copy_sources(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for relative in FILES:
        source = root / relative
        if source.is_symlink():
            raise ValueError(f"symlink forbidden: {source}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def materialize_prototype_cell(root: Path, target: str, bridge: bool, destination: Path) -> WorkspaceRecord:
    """Copy only one target, base and optional oracle; never expose review diagnostics."""
    metadata = load_prototype(root)
    destination.mkdir(parents=True, exist_ok=False)
    mapping = {"lakefile.toml": "lakefile.toml", "lean-toolchain": "lean-toolchain",
               "World/Base.lean": "World/Base.lean", TARGETS[target][0]: "World/ChallengeEvaluation.lean"}
    if bridge:
        mapping["Hidden/Oracle.lean"] = "Bridge.lean"
    hashes = {}
    for source, relative in mapping.items():
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / source, output)
        hashes[relative] = digest(output)
    return WorkspaceRecord(destination, metadata["world_id"], "offline_evaluator_probe",
                           "oracle_bridge" if bridge else "no_bridge", hashes, ("Solution.lean",))


def oracle_solution(root: Path, target: str) -> str:
    text = (root / "Hidden/OracleChecks.lean").read_text()
    theorem = TARGETS[target][2]
    match = re.search(rf"theorem {theorem} :.*?(?=\n\n(?:theorem|#print))", text, re.S)
    if not match:
        raise ValueError(f"oracle closure not found: {target}")
    body = match.group().replace(f"theorem {theorem}", "theorem evaluation_solution", 1)
    opens = "open Mark\n" if root.name == "DEV_REPRESENTATION_V3" else ""
    return ("import World.ChallengeEvaluation\nimport Bridge\n"
            + f"namespace P3.{root.name}\n{opens}{body}\nend P3.{root.name}\n")


def _check_solution(record: WorkspaceRecord, target: str, source: str) -> dict:
    (record.path / "Solution.lean").write_text(source)
    report = verify_evaluator_solution(
        record.path, namespace=f"P3.{record.world_id}", statement=TARGETS[target][1],
        bridge_supplied=record.condition == "oracle_bridge", lake="/opt/homebrew/bin/lake",
        timeout_s=30, allowed_axioms=STANDARD_LEAN_AXIOMS, process_runner=sandbox_process,
    )
    errors = audit_workspace(record)
    return {"solved": report.ok and not errors, "errors": report.errors + errors,
            "audit": report.stdout, "stderr": report.stderr}


def _ordinary_rejection(check: dict) -> bool:
    text = "\n".join(check["errors"]) + check["audit"] + check["stderr"]
    return (not check["solved"] and "Lean rejected Solution.lean:" in text
            and any(marker in text for marker in ("unsolved goals", "`grind` failed", "omega could not prove"))
            and not any(marker in text for marker in ("timeout", "unknown identifier", "unexpected token",
                                                     "maximum recursion depth", "maximum number of heartbeats")))


def review_prototype(root: Path) -> dict:
    """Kernel audits, all target closures, fixed no-bridge probes and a semantic mutation."""
    metadata = load_prototype(root)
    settings = PROTOTYPES[root.name]
    result = {"world_id": root.name, "model_calls": 0, "eligible_for_calibration": False,
              "manifest_sha256": digest(root / "manifest.sha256"), "kernel_checks": [],
              "oracle_closures": [], "automatic_probes": [], "mutation": {}}
    with tempfile.TemporaryDirectory(prefix="p3-prototype-review-") as temporary:
        temporary = Path(temporary)
        staged = temporary / "kernel"
        _copy_sources(root, staged)
        build = sandbox_process(["/opt/homebrew/bin/lake", "build", "Hidden.OracleChecks", "Hidden.Diagnostics"],
                                cwd=staged, timeout=60)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        for relative, count in metadata["lean_checks"]["axiom_audits"].items():
            audit = sandbox_process(["/opt/homebrew/bin/lake", "env", "lean", relative], cwd=staged, timeout=30)
            result["kernel_checks"].append({"file": relative, "expected_declarations": count,
                "ok": audit.returncode == 0 and axiom_audit_ok(audit.stdout + audit.stderr, STANDARD_LEAN_AXIOMS, count),
                "stdout": audit.stdout, "stderr": audit.stderr})
        for target, (_, statement, _) in TARGETS.items():
            record = materialize_prototype_cell(root, target, True, temporary / f"{target}-oracle")
            result["oracle_closures"].append({"target": target, **_check_solution(record, target, oracle_solution(root, target))})
            definitions = ", ".join(filter(None, (statement, settings["unfold"])))
            tactics = {"simp": f"simp [{definitions}]",
                       "grind": f"grind (splits := 4) [{definitions}, {settings['inductive']}]",
                       "omega": f"unfold {statement}\n  intros\n  omega"}
            for name, tactic in tactics.items():
                record = materialize_prototype_cell(root, target, False, temporary / f"{target}-{name}")
                source = ("import World.ChallengeEvaluation\n"
                          + f"namespace P3.{root.name}\n"
                          + "set_option maxHeartbeats 200000\n"
                          + f"theorem evaluation_solution : {statement} := by\n  {tactic}\n"
                          + f"end P3.{root.name}\n")
                check = _check_solution(record, target, source)
                result["automatic_probes"].append({"target": target, "tactic": name, "source": source,
                                                   "ordinary_rejection": _ordinary_rejection(check), **check})

        mutant = temporary / "mutant"
        _copy_sources(root, mutant)
        base = (mutant / "World/Base.lean").read_text()
        if root.name == "DEV_INVARIANT_V3":
            old, new = "def start : State := ⟨2, 1, 1⟩", "def start : State := ⟨1, 1, 1⟩"
            proof = "exact h 0 1 (Reaches.tail (Reaches.refl start) (Step.second start))"
            mutation_name = "singular_initial_state"
        else:
            old = "  | trans {u v w} : Related u v → Related v w → Related u w"
            new = old + "\n  | collapse : Related [a, a, b, b] [a, b, a, b]"
            proof = "exact h [] [] Related.collapse"
            mutation_name = "additional_rewrite_collapses_visible_pair"
        if base.count(old) != 1:
            raise ValueError("mutation anchor is not unique")
        (mutant / "World/Base.lean").write_text(base.replace(old, new))
        changed = sandbox_process(["/opt/homebrew/bin/lake", "build", "World.ChallengeVisible"], cwd=mutant, timeout=30)
        witness = (f"import World.ChallengeVisible\nnamespace P3.{root.name}\n"
                   + "theorem mutation_falsifies_target : ¬ VisibleStatement := by\n  intro h\n  "
                   + proof + f"\n#print axioms mutation_falsifies_target\nend P3.{root.name}\n")
        (mutant / "Mutation.lean").write_text(witness)
        checked = sandbox_process(["/opt/homebrew/bin/lake", "env", "lean", "Mutation.lean"], cwd=mutant, timeout=30)
        oracle = sandbox_process(["/opt/homebrew/bin/lake", "build", "Hidden.OracleChecks"], cwd=mutant, timeout=30)
        result["mutation"] = {"name": mutation_name,
            "negated_target_verified": changed.returncode == 0 and checked.returncode == 0
                and axiom_audit_ok(checked.stdout + checked.stderr, STANDARD_LEAN_AXIOMS),
            "original_oracle_rejected": oracle.returncode != 0
                and ("unsolved goals" in oracle.stdout or "`grind` failed" in oracle.stdout
                     or "Alternative `collapse` has not been provided" in oracle.stdout),
            "witness_source": witness, "witness_audit": checked.stdout,
            "oracle_diagnostic": (oracle.stdout + oracle.stderr).replace(str(mutant.resolve()), "<mutant>")
                .replace(str(mutant), "<mutant>")}
    result["automatic_shortcut_found"] = any(item["solved"] for item in result["automatic_probes"])
    result["review_completed"] = (all(item["ok"] for item in result["kernel_checks"])
        and all(item["solved"] for item in result["oracle_closures"])
        and all(item["solved"] or item["ordinary_rejection"] for item in result["automatic_probes"])
        and result["mutation"]["negated_target_verified"] and result["mutation"]["original_oracle_rejected"])
    result["structural_checks_passed"] = result["review_completed"] and not result["automatic_shortcut_found"]
    return result
