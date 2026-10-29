#!/usr/bin/env python3
"""Recheck development exclusions and the equal-reachability proof, without models."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from creative_machine.formal_routes.calibration_protocol_v3 import save_new
from creative_machine.formal_routes.calibration_worlds_v3 import exclusion_audit
from creative_machine.formal_routes.conceptual_generator import sha
from creative_machine.formal_routes.lean_sandbox import sandbox_process
from creative_machine.formal_routes.prototypes import load_prototype
from creative_machine.formal_routes.submission import STANDARD_LEAN_AXIOMS, axiom_audit_ok

ROOT = Path(__file__).resolve().parent.parent
PROOF = "docs/p3/generation_audit_v3/StartEquivalence.lean"


def audit():
    prototype = ROOT / "worlds/prototypes/DEV_INVARIANT_V3"
    load_prototype(prototype)
    with tempfile.TemporaryDirectory(prefix="p3-generation-audit-") as temp:
        temp = Path(temp).resolve()
        for relative in ("lakefile.toml", "lean-toolchain", "World/Base.lean"):
            target = temp / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prototype / relative, target)
        shutil.copy2(ROOT / PROOF, temp / "StartEquivalence.lean")
        built = sandbox_process(["/opt/homebrew/bin/lake", "build", "World.Base"], cwd=temp, timeout=30)
        proof = sandbox_process(["/opt/homebrew/bin/lake", "env", "lean", "StartEquivalence.lean"], cwd=temp, timeout=30)
    result = {"model_calls": 0, "exclusions": exclusion_audit(),
              "equal_reachability_verified": built.returncode == 0 and proof.returncode == 0
                  and axiom_audit_ok(proof.stdout + proof.stderr, STANDARD_LEAN_AXIOMS, 6),
              "proof_audit": proof.stdout, "stderr": proof.stderr,
              "proof_sha256": sha((ROOT / PROOF).read_text()),
              "base_sha256": sha((prototype / "World/Base.lean").read_text()),
              "audit_code_sha256": sha(Path(__file__).read_text()),
              "generator_sha256": sha((ROOT / "src/creative_machine/formal_routes/calibration_worlds_v3.py").read_text())}
    if not result["equal_reachability_verified"]:
        raise ValueError(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise FileExistsError(args.output)
    result = audit()
    if args.output:
        save_new(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
