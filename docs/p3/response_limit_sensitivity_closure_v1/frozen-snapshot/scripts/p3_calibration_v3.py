#!/usr/bin/env python3
"""Prepare/validate/preflight the final small v3 calibration; only run calls models."""

import argparse
import json
from pathlib import Path

from creative_machine.formal_routes.calibration_protocol_v3 import (
    assert_committed_v3, load_plan_v3, preflight_v3, prepare_v3, run_v3,
)
from creative_machine.formal_routes.calibration_worlds_v3 import exclusion_audit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "docs/p3/calibration_conceptual_plan_v3.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit-exclusions", "prepare", "validate", "preflight", "check-commit", "run"))
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs/p3/calibration")
    args = parser.parse_args()
    if args.command == "audit-exclusions":
        result = exclusion_audit()
    elif args.command == "prepare":
        plan = prepare_v3(ROOT, args.plan)
        result = {"plan_id": plan["plan_id"], "status": plan["status"], "cells": len(plan["cells"]),
                  "model_calls": 0, "reserved_worst_case_usd": plan["reserved_worst_case_usd"]}
    else:
        plan = load_plan_v3(ROOT, args.plan)
        if args.command == "validate":
            result = {"ok": True, "plan_id": plan["plan_id"], "cells": len(plan["cells"]), "model_calls": 0}
        elif args.command == "preflight":
            result = preflight_v3(ROOT, plan)
        elif args.command == "check-commit":
            result = {"commit": assert_committed_v3(ROOT, args.plan, plan), "model_calls": 0}
        else:
            result = run_v3(ROOT, args.plan, args.run_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
