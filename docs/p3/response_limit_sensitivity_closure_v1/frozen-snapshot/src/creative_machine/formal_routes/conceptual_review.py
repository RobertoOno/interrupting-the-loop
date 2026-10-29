"""Offline kernel/source/isolated-workspace checks for conceptual development worlds."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from .conceptual_generator import load_conceptual, sha, word
from .lean_sandbox import sandbox_process
from .prototypes import TARGETS, _check_solution, _ordinary_rejection
from .submission import STANDARD_LEAN_AXIOMS, axiom_audit_ok
from .workspace import WorkspaceRecord

LAKE = "/opt/homebrew/bin/lake"


def materialize_conceptual_cell(root: Path, target: str, bridge: str | None, destination: Path) -> WorkspaceRecord:
    if target not in TARGETS or bridge not in (None, "oracle", "adapted"):
        raise ValueError("known target and bridge (oracle/adapted/None) required")
    metadata = load_conceptual(root)
    destination.mkdir(parents=True, exist_ok=False)
    mapping = {"lakefile.toml": "lakefile.toml", "lean-toolchain": "lean-toolchain",
               "World/Base.lean": "World/Base.lean", TARGETS[target][0]: "World/ChallengeEvaluation.lean"}
    if bridge:
        mapping[f"Hidden/{'Oracle' if bridge == 'oracle' else 'AdaptedRelevant'}.lean"] = "Bridge.lean"
    hashes = {}
    for source, relative in mapping.items():
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / source, output)
        hashes[relative] = sha(output.read_text())
    # The historical checker only needs to distinguish supplied vs absent bridge.
    return WorkspaceRecord(destination, metadata["world_id"], "offline_development_probe",
                           "oracle_bridge" if bridge else "no_bridge", hashes, ("Solution.lean",))


def closure_source(root: Path, target: str, bridge: str) -> str:
    if target not in TARGETS or bridge not in ("oracle", "adapted"):
        raise ValueError("unknown target/bridge")
    metadata = load_conceptual(root)
    relative = "Hidden/OracleChecks.lean" if bridge == "oracle" else "Hidden/SourceChecks.lean"
    theorem = TARGETS[target][2].replace("oracle_", f"{bridge}_")
    text = (root / relative).read_text()
    match = re.search(rf"theorem {theorem} :.*?(?=\n\n(?:theorem|def|#print|end))", text, re.S)
    if not match:
        raise ValueError(f"closure not found: {theorem}")
    body = match.group().replace(f"theorem {theorem}", "theorem evaluation_solution", 1)
    opens = "open Mark\n" if metadata["family"] == "representation" else ""
    namespace = metadata["roles"]["namespace"]
    return (f"import World.ChallengeEvaluation\nimport Bridge\nnamespace {namespace}\n"
            + opens + body + f"\nend {namespace}\n")


def expected_proof_rejection(returncode: int, stdout: str, stderr: str) -> bool:
    text = (stdout + "\n" + stderr).lower()
    return (returncode != 0 and any(marker in text for marker in (
        "unsolved goals", "type mismatch", "`grind` failed", "alternative `collapse` has not been provided"))
        and not any(marker in text for marker in ("unknown identifier", "unexpected token", "timeout",
            "maximum recursion depth", "maximum number of heartbeats", "no goals to be solved", "unknown module")))


def _stage(root: Path, destination: Path, metadata: dict) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for relative in metadata["artifact_hashes"]:
        source = root / relative
        if source.is_symlink():
            raise ValueError(f"symlink forbidden: {source}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _semantic_mutation(root: Path, destination: Path, metadata: dict) -> dict:
    _stage(root, destination, metadata)
    base = (destination / "World/Base.lean").read_text()
    if metadata["family"] == "invariant":
        x, y, z = metadata["parameters"]["offsets"]
        base, count = re.subn(r"def start : State := .*", f"def start : State := ⟨{x+1}, {y+1}, {z+1}⟩", base)
        if count != 1:
            raise ValueError("mutation anchor not unique")
        proof = "exact h 0 1 (Reaches.tail (Reaches.refl start) (Step.second start))"
        name = "singular_decoded_initial_state"
    else:
        u, v = metadata["parameters"]["pairs"][0]
        anchor = "  | trans {u v w} : Related u v → Related v w → Related u w"
        if base.count(anchor) != 1:
            raise ValueError("mutation anchor not unique")
        base = base.replace(anchor, anchor + f"\n  | collapse : Related {word(u)} {word(v)}")
        proof = "exact h [] [] Related.collapse"
        name = "additional_rewrite_collapses_visible_pair"
    (destination / "World/Base.lean").write_text(base)
    namespace = metadata["roles"]["namespace"]
    witness = (f"import World.ChallengeVisible\nnamespace {namespace}\n"
        + "theorem mutation_falsifies_target : ¬ VisibleStatement := by\n  intro h\n  " + proof
        + f"\n#print axioms mutation_falsifies_target\nend {namespace}\n")
    (destination / "Mutation.lean").write_text(witness)
    built = sandbox_process([LAKE, "build", "World.ChallengeVisible"], cwd=destination, timeout=30)
    checked = sandbox_process([LAKE, "env", "lean", "Mutation.lean"], cwd=destination, timeout=30)
    oracle = sandbox_process([LAKE, "build", "Hidden.OracleChecks"], cwd=destination, timeout=30)
    return {"name": name, "negated_target_verified": built.returncode == 0 and checked.returncode == 0
                and axiom_audit_ok(checked.stdout + checked.stderr, STANDARD_LEAN_AXIOMS),
            "original_oracle_rejected": expected_proof_rejection(oracle.returncode, oracle.stdout, oracle.stderr),
            "witness_source": witness, "witness_audit": checked.stdout + checked.stderr,
            "oracle_diagnostic": (oracle.stdout + oracle.stderr).replace(str(destination), "<mutant>")}


def review_conceptual(root: Path) -> dict:
    """Failures/timeouts are errors, never counted as behavioral difficulty."""
    metadata = load_conceptual(root)
    result = {"world_id": metadata["world_id"], "model_calls": 0, "behavioral_gate_tested": False,
              "manifest_sha256": sha((root / "manifest.sha256").read_text()),
              "kernel_checks": [], "closure_checks": [], "automatic_probes": [],
              "source_matching": metadata["source_matching"]}
    with tempfile.TemporaryDirectory(prefix="p3-conceptual-review-") as temporary:
        temporary = Path(temporary).resolve()
        staged = temporary / "kernel"
        _stage(root, staged, metadata)
        modules = [rel.removesuffix(".lean").replace("/", ".") for rel in metadata["lean_checks"]["must_compile"]]
        built = sandbox_process([LAKE, "build", *modules], cwd=staged, timeout=60)
        if built.returncode:
            raise RuntimeError(built.stdout + built.stderr)
        for relative, count in metadata["lean_checks"]["axiom_audits"].items():
            audit = sandbox_process([LAKE, "env", "lean", relative], cwd=staged, timeout=30)
            result["kernel_checks"].append({"file": relative, "expected_declarations": count,
                "ok": audit.returncode == 0 and axiom_audit_ok(audit.stdout + audit.stderr, STANDARD_LEAN_AXIOMS, count),
                "stdout": audit.stdout, "stderr": audit.stderr})
        negative = sandbox_process([LAKE, "env", "lean", "Hidden/AdaptedSham.lean"], cwd=staged, timeout=30)
        result["sham_adapter"] = {"expected_rejection": expected_proof_rejection(negative.returncode, negative.stdout, negative.stderr),
                                  "stdout": negative.stdout, "stderr": negative.stderr}
        for target, (_, statement, _) in TARGETS.items():
            for bridge in ("oracle", "adapted"):
                record = materialize_conceptual_cell(root, target, bridge, temporary / f"{target}-{bridge}")
                result["closure_checks"].append({"target": target, "bridge": bridge,
                    **_check_solution(record, target, closure_source(root, target, bridge))})
            definitions = statement + (", start, move1, move2, move3, move4" if metadata["family"] == "invariant" else "")
            inductive = "Reaches, Step" if metadata["family"] == "invariant" else "Related"
            tactics = {"simp": f"simp [{definitions}]", "grind": f"grind (splits := 4) [{definitions}, {inductive}]",
                       "omega": f"unfold {statement}\n  intros\n  omega"}
            for name, tactic in tactics.items():
                record = materialize_conceptual_cell(root, target, None, temporary / f"{target}-{name}")
                namespace = metadata["roles"]["namespace"]
                source = (f"import World.ChallengeEvaluation\nnamespace {namespace}\n"
                    + "set_option maxHeartbeats 200000\n"
                    + f"theorem evaluation_solution : {statement} := by\n  {tactic}\nend {namespace}\n")
                checked = _check_solution(record, target, source)
                result["automatic_probes"].append({"target": target, "tactic": name, "source": source,
                                                   "ordinary_rejection": _ordinary_rejection(checked), **checked})
        result["mutation"] = _semantic_mutation(root, temporary / "mutant", metadata)
    result["review_completed"] = (all(check["ok"] for check in result["kernel_checks"])
        and result["sham_adapter"]["expected_rejection"]
        and all(check["solved"] for check in result["closure_checks"])
        and all(check["solved"] or check["ordinary_rejection"] for check in result["automatic_probes"])
        and result["mutation"]["negated_target_verified"] and result["mutation"]["original_oracle_rejected"])
    result["automatic_shortcut_found"] = any(check["solved"] for check in result["automatic_probes"])
    result["structural_checks_passed"] = result["review_completed"] and not result["automatic_shortcut_found"]
    return result
