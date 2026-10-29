#!/usr/bin/env python3
"""Recheck the archived v2 proofs locally; never import a model client or call AWS."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY, sandbox_process
from creative_machine.formal_routes.submission import verify_evaluator_solution
from creative_machine.formal_routes.validation import validate_world
from creative_machine.formal_routes.workspace import materialize_evaluator

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs/p3"


def check_hash(path: Path, expected: str) -> None:
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"archive or implementation drift: {path}")


def main() -> int:
    plan = json.loads((DOCS / "calibration_bedrock_plan_v2.json").read_text())
    if plan["plan_id"] != "p3a_bedrock_headroom_v2" or plan["status"] != "FROZEN":
        raise ValueError("the frozen Bedrock v2 plan is required")
    for relative, expected in plan["harness_sha256"].items():
        check_hash(ROOT / relative, expected)
    check_hash(Path(CODEX_BINARY), plan["environment"]["sandbox_binary_sha256"])
    manifest = {}
    for line in (DOCS / "calibration_bedrock_raw_manifest_v2.sha256").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        if relative in manifest:
            raise ValueError(f"duplicate raw manifest entry: {relative}")
        manifest[relative] = digest
    check_hash(DOCS / "calibration_bedrock_results_v2.json", manifest["summary.json"])

    for item in plan["worlds"]:
        world = ROOT / item["path"]
        check_hash(world / "manifest.sha256", item["manifest_sha256"])
        validate_world(world).require_ok()

    checks = []
    with tempfile.TemporaryDirectory(prefix="p3-archived-v2-") as temporary:
        for cell in plan["cells"]:
            cell_id = cell["cell_id"]
            archive = DOCS / "calibration_bedrock_evidence_v2" / cell_id
            check_hash(archive / "Solution.lean", manifest[f"{cell_id}/workspace/Solution.lean"])
            check_hash(archive / "result.json", manifest[f"{cell_id}/result.json"])
            original = json.loads((archive / "result.json").read_text())
            if original["cell"] != cell:
                raise ValueError(f"archived cell identity mismatch: {cell_id}")
            world = ROOT / cell["world"]
            metadata = json.loads((world / "metadata.json").read_text())
            if metadata["allowed_axioms"] != plan["allowed_axioms"]:
                raise ValueError(f"axiom policy drift: {cell_id}")
            destination = Path(temporary) / cell_id
            materialize_evaluator(world, cell["holdout"], cell["condition"], destination)
            shutil.copy2(archive / "Solution.lean", destination / "Solution.lean")
            report = verify_evaluator_solution(
                destination,
                namespace=metadata["roles"]["namespace"],
                statement=metadata["roles"]["holdout_statements"][cell["holdout"] - 1],
                bridge_supplied=cell["condition"] == "oracle_bridge",
                lake="/opt/homebrew/bin/lake",
                process_runner=sandbox_process,
                allowed_axioms=tuple(plan["allowed_axioms"]),
            )
            checks.append({"cell_id": cell_id, "ok": report.ok,
                           "matches_original": report.ok == original["result"]["target_solved"],
                           "errors": report.errors})
    ok = len(checks) == 8 and all(item["ok"] and item["matches_original"] for item in checks)
    print(json.dumps({"ok": ok, "model_calls": 0, "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
