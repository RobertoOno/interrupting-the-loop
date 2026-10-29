#!/usr/bin/env python3
"""Prepare/validate the development matrix or analyze supplied audit projections.

No run command, provider construction, budget reservation or GPU management.
"""
import argparse
import json
from pathlib import Path

from creative_machine.formal_routes import transfer_design_v1 as design
from creative_machine.formal_routes.transfer_analysis_v1 import analyze

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "analyze"))
    parser.add_argument("--observations", type=Path, help="Auditor projection JSON; explicitly synthetic or experimental")
    parser.add_argument("--output", type=Path, help="Optional new analysis output; never overwrite")
    args = parser.parse_args()
    if args.command != "analyze" and (args.observations or args.output):
        parser.error("observation/output arguments belong only to analyze")
    blueprint = design.prepare(ROOT) if args.command == "prepare" else design.load_blueprint(ROOT)
    if args.command == "analyze":
        if args.observations is None:
            parser.error("analyze requires --observations; no inferred or historical results")
        result = analyze(blueprint, json.loads(args.observations.read_bytes()))
        if args.output:
            with args.output.open("xb") as handle:
                handle.write(design.encoded(result))
    else:
        result = {"design_id": blueprint["design_id"], "status": blueprint["status"],
                  "slots": len(blueprint["cells"]), "blueprint_sha256": design.sha(design.encoded(blueprint)),
                  "inference_admitted": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
