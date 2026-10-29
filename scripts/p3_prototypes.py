#!/usr/bin/env python3
"""Seal or review P3 development prototypes; no model calls or AWS imports."""

import argparse
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from creative_machine.formal_routes.prototypes import PROTOTYPES, digest, review_prototype, seal_prototype
from creative_machine.formal_routes.lean_sandbox import CODEX_BINARY

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "review"))
    parser.add_argument("--output", type=Path, help="Optional new JSON evidence file; never overwrite")
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise FileExistsError(args.output)
    worlds = [ROOT / "worlds/prototypes" / name for name in PROTOTYPES]
    if args.command == "seal":
        result = {"prototypes": [seal_prototype(world) for world in worlds]}
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reviews = list(pool.map(review_prototype, worlds))
        result = {"schema_version": 1, "review_id": "p3_prototypes_v3_local_review",
                  "model_calls": 0, "prototypes": reviews,
                  "structural_checks_passed": all(item["structural_checks_passed"] for item in reviews),
                  "behavioral_gate_tested": False, "main_sample_started": False,
                  "environment": {"python": platform.python_version(), "toolchain": "leanprover/lean4:v4.33.1",
                                  "sandbox_binary_sha256": digest(Path(CODEX_BINARY))},
                  "review_code_sha256": {relative: digest(ROOT / relative) for relative in (
                      "scripts/p3_prototypes.py", "src/creative_machine/formal_routes/prototypes.py",
                      "src/creative_machine/formal_routes/lean_sandbox.py",
                      "src/creative_machine/formal_routes/submission.py",
                      "src/creative_machine/formal_routes/validation.py",
                      "src/creative_machine/formal_routes/workspace.py",
                      "src/creative_machine/formal_routes/codex_runner.py")}}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    if args.command == "review":
        print(json.dumps({key: value for key, value in result.items() if key != "prototypes"}, indent=2))
        for item in result["prototypes"]:
            print(json.dumps({"world_id": item["world_id"], "review_completed": item["review_completed"],
                "structural_checks_passed": item["structural_checks_passed"],
                "oracle_closures": sum(check["solved"] for check in item["oracle_closures"]),
                "automatic_probes": [{k: probe[k] for k in ("target", "tactic", "solved", "ordinary_rejection")}
                                     for probe in item["automatic_probes"]],
                "mutation": {k: item["mutation"][k] for k in ("negated_target_verified", "original_oracle_rejected")}}, indent=2))
        return 0 if all(item["review_completed"] for item in result["prototypes"]) else 1
    print(json.dumps({"sealed": [item["world_id"] for item in result["prototypes"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
