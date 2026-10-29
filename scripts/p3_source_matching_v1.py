#!/usr/bin/env python3
"""Prepare, validate, count once, or audit the prospective D/C2 token preflight."""
import argparse
import json
from pathlib import Path

from creative_machine.formal_routes import source_matching_v1 as matching

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "run", "audit"))
    command = parser.parse_args().command
    if command == "prepare":
        plan = matching.prepare(ROOT)
        result = {"plan_id": plan["plan_id"], "requests": len(plan["requests"]), "status": plan["status"]}
    elif command == "validate":
        plan = matching.load_plan(ROOT)
        result = {"ok": True, "plan_id": plan["plan_id"], "requests": len(plan["requests"])}
    else:
        result = getattr(matching, command)(ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
