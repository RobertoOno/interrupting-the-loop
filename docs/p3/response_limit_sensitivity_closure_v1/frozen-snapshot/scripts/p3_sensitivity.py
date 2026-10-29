#!/usr/bin/env python3
"""Prepare or check S16 without constructing any provider client."""

import argparse
import json
from pathlib import Path
from creative_machine.formal_routes import sensitivity_protocol_v1 as protocol

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "preflight", "check-commit"))
    args = parser.parse_args()
    if args.command == "prepare":
        result = protocol.prepare(ROOT)
    else:
        plan = protocol.load_plan(ROOT, ROOT / protocol.PLAN_PATH)
        if args.command == "validate":
            result = {"ok": True, "plan_id": plan["plan_id"], "cells": len(plan["cells"]), "model_calls": 0}
        elif args.command == "preflight":
            result = protocol.preflight(ROOT, plan)
        else:
            result = {"commit": protocol.assert_committed(ROOT, plan), "model_calls": 0}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
