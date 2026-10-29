#!/usr/bin/env python3
"""Prepare, verify and execute a separately frozen Bedrock calibration."""
import argparse
import json
from pathlib import Path

from creative_machine.formal_routes.bedrock_calibration import load_plan, preflight, prepare_plan, run_plan

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "docs/p3/calibration_bedrock_plan_v2.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "preflight", "run"))
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs/p3/calibration")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_plan(ROOT, args.plan)
    else:
        plan = load_plan(ROOT, args.plan)
        if args.command == "validate":
            result = {"ok": True, "plan_id": plan["plan_id"], "model": plan["agent"]["model"],
                      "max_total_cost_usd": plan["max_total_cost_usd"], "cells": len(plan["cells"])}
        elif args.command == "preflight":
            result = preflight(ROOT, plan)
        else:
            result = run_plan(ROOT, args.plan, args.run_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
