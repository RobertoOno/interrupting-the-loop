"""Local checks for the corrected v3 worlds; no experimental model calls."""

import re
import shutil
import tempfile
from pathlib import Path

from .calibration_worlds_v3 import load_v3
from .conceptual_generator import sha
from .conceptual_review import LAKE, _stage, _semantic_mutation, expected_proof_rejection
from .lean_sandbox import sandbox_process
from .prototypes import TARGETS, _check_solution, _ordinary_rejection
from .submission import STANDARD_LEAN_AXIOMS, axiom_audit_ok
from .workspace import WorkspaceRecord, materialize_evaluator


def materialize_v3(root: Path, target: str, bridge: str | None, destination: Path) -> WorkspaceRecord:
    if target not in TARGETS or bridge not in (None, "oracle", "adapted"):
        raise ValueError("unknown target or bridge")
    metadata = load_v3(root)
    if target != "visible" and bridge != "adapted":
        return materialize_evaluator(root, int(target[-1]), "oracle_bridge" if bridge else "no_bridge", destination)
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
    return WorkspaceRecord(destination, metadata["world_id"], "offline_probe",
                           "oracle_bridge" if bridge else "no_bridge", hashes, ("Solution.lean",))


def closure_v3(root: Path, target: str, bridge: str) -> str:
    if target not in TARGETS or bridge not in ("oracle", "adapted"):
        raise ValueError("unknown target or bridge")
    metadata = load_v3(root)
    relative = "Hidden/OracleChecks.lean" if bridge == "oracle" else "Hidden/SourceChecks.lean"
    theorem = TARGETS[target][2].replace("oracle_", f"{bridge}_")
    text = (root / relative).read_text()
    match = re.search(rf"theorem {theorem} :.*?(?=\n\n(?:theorem|def|#print|end))", text, re.S)
    if not match:
        raise ValueError(f"missing closure: {theorem}")
    body = match.group().replace(f"theorem {theorem}", "theorem evaluation_solution", 1)
    ns = metadata["roles"]["namespace"]
    opens = "open Mark\n" if metadata["family"] == "representation" else ""
    return f"import World.ChallengeEvaluation\nimport Bridge\nnamespace {ns}\n{opens}{body}\nend {ns}\n"


def review_v3(root: Path) -> dict:
    metadata = load_v3(root)
    result = {"world_id": metadata["world_id"], "phase": metadata["phase"], "model_calls": 0,
              "manifest_sha256": sha((root / "manifest.sha256").read_text()),
              "kernel_checks": [], "closure_checks": [], "automatic_probes": []}
    with tempfile.TemporaryDirectory(prefix="p3-v3-review-") as tmp:
        tmp = Path(tmp).resolve()
        staged = tmp / "kernel"
        _stage(root, staged, metadata)
        modules = [p.removesuffix(".lean").replace("/", ".") for p in metadata["lean_checks"]["must_compile"]]
        built = sandbox_process([LAKE, "build", *modules], cwd=staged, timeout=60)
        if built.returncode:
            raise RuntimeError(built.stdout + built.stderr)
        for relative, count in metadata["lean_checks"]["axiom_audits"].items():
            audit = sandbox_process([LAKE, "env", "lean", relative], cwd=staged, timeout=30)
            result["kernel_checks"].append({"file": relative, "declarations": count,
                "ok": audit.returncode == 0 and axiom_audit_ok(audit.stdout + audit.stderr, STANDARD_LEAN_AXIOMS, count),
                "stdout": audit.stdout, "stderr": audit.stderr})
        negative = sandbox_process([LAKE, "env", "lean", "Hidden/AdaptedSham.lean"], cwd=staged, timeout=30)
        result["sham_adapter"] = {"expected_rejection": expected_proof_rejection(negative.returncode, negative.stdout, negative.stderr),
                                  "stdout": negative.stdout, "stderr": negative.stderr}
        for target, (_, statement, _) in TARGETS.items():
            for bridge in ("oracle", "adapted"):
                record = materialize_v3(root, target, bridge, tmp / f"{target}-{bridge}")
                result["closure_checks"].append({"target": target, "bridge": bridge,
                    **_check_solution(record, target, closure_v3(root, target, bridge))})
            definitions = statement + (", start, move1, move2, move3, move4" if metadata["family"] == "invariant" else "")
            inductive = "Reaches, Step" if metadata["family"] == "invariant" else "Related"
            tactics = {"simp": f"simp [{definitions}]", "grind": f"grind (splits := 4) [{definitions}, {inductive}]",
                       "omega": f"unfold {statement}\n  intros\n  omega"}
            for tactic_name, tactic in tactics.items():
                record = materialize_v3(root, target, None, tmp / f"{target}-{tactic_name}")
                ns = metadata["roles"]["namespace"]
                source = (f"import World.ChallengeEvaluation\nnamespace {ns}\nset_option maxHeartbeats 200000\n"
                          + f"theorem evaluation_solution : {statement} := by\n  {tactic}\nend {ns}\n")
                checked = _check_solution(record, target, source)
                result["automatic_probes"].append({"target": target, "tactic": tactic_name, "source": source,
                                                   "ordinary_rejection": _ordinary_rejection(checked), **checked})
        result["mutation"] = _semantic_mutation(root, tmp / "mutant", metadata)
    result["review_completed"] = (all(c["ok"] for c in result["kernel_checks"])
        and result["sham_adapter"]["expected_rejection"] and all(c["solved"] for c in result["closure_checks"])
        and all(c["solved"] or c["ordinary_rejection"] for c in result["automatic_probes"])
        and result["mutation"]["negated_target_verified"] and result["mutation"]["original_oracle_rejected"])
    result["automatic_shortcut_found"] = any(c["solved"] for c in result["automatic_probes"])
    result["structural_checks_passed"] = result["review_completed"] and not result["automatic_shortcut_found"]
    return result
