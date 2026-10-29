#!/usr/bin/env python3
"""Generate/review DEVELOPMENT worlds only. No AWS, model, or pod calls."""

import argparse
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from creative_machine.formal_routes.conceptual_generator import (
    ASSETS, REPO, ConceptualSpec, generate_conceptual, sha, write_conceptual,
)
from creative_machine.formal_routes.conceptual_review import review_conceptual
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY
from creative_machine.formal_routes.prototypes import digest

DEVELOPMENT_SPECS = (
    ConceptualSpec("invariant", "43be3d3ca20476f1"),
    ConceptualSpec("representation", "cd4dc332561f4980"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--family", required=True, choices=("invariant", "representation"))
    generate.add_argument("--seed", required=True)
    generate.add_argument("--destination", required=True, type=Path)
    review = commands.add_parser("review")
    review.add_argument("--world", action="append", type=Path)
    review.add_argument("--output", type=Path, help="New evidence JSON; never overwrite")
    args = parser.parse_args()
    if args.command == "generate":
        generated = generate_conceptual(ConceptualSpec(args.family, args.seed))
        destination = write_conceptual(generated, args.destination)
        print(json.dumps({"world_id": generated.spec.world_id, "destination": str(destination),
                          "eligible_for_calibration": False, "eligible_for_main": False}))
        return 0
    if args.output and (args.output.exists() or args.output.is_symlink()):
        raise FileExistsError(args.output)
    worlds = args.world or [REPO / "worlds/development" / spec.world_id for spec in DEVELOPMENT_SPECS]
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(pool.map(review_conceptual, worlds))
    fingerprinted = [
        "scripts/p3_conceptual.py", "src/creative_machine/formal_routes/conceptual_generator.py",
        "src/creative_machine/formal_routes/conceptual_review.py", "src/creative_machine/formal_routes/prototypes.py",
        "src/creative_machine/formal_routes/lean_sandbox.py", "src/creative_machine/formal_routes/submission.py",
        "src/creative_machine/formal_routes/validation.py", "src/creative_machine/formal_routes/workspace.py",
        "src/creative_machine/formal_routes/codex_runner.py",
    ]
    result = {"schema_version": 1, "review_id": "p3_conceptual_sources_v3_local_review", "model_calls": 0,
        "behavioral_gate_tested": False, "main_sample_started": False, "worlds": reviews,
        "structural_checks_passed": all(item["structural_checks_passed"] for item in reviews),
        "environment": {"python": platform.python_version(), "toolchain": "leanprover/lean4:v4.33.1",
                        "sandbox_binary_sha256": digest(Path(CODEX_BINARY))},
        "review_code_sha256": {relative: sha((REPO / relative).read_text()) for relative in fingerprinted},
        "source_assets_sha256": {path.name: sha(path.read_text()) for path in sorted(ASSETS.glob("*.lean"))}}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, sort_keys=True, indent=2)
            handle.write("\n")
    print(json.dumps({"model_calls": 0, "structural_checks_passed": result["structural_checks_passed"],
        "worlds": [{"world_id": item["world_id"], "closure_checks": sum(c["solved"] for c in item["closure_checks"]),
                    "automatic_shortcut_found": item["automatic_shortcut_found"],
                    "sham_adapter_rejected": item["sham_adapter"]["expected_rejection"],
                    "mutation": {k: item["mutation"][k] for k in ("negated_target_verified", "original_oracle_rejected")}}
                   for item in reviews]}, indent=2))
    return 0 if result["structural_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
