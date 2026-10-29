#!/usr/bin/env python3
"""Admit S16 once after publication; USD30 within the existing USD150/day guard."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from creative_machine.formal_routes import sensitivity_protocol_v1 as protocol


def launch(root):
    """Single detached launch; a retained intent also blocks ambiguous relaunches."""
    plan = protocol.load_plan(root, root / protocol.PLAN_PATH)
    commit = protocol.assert_committed(root, plan)
    for name in (protocol.RUN_PATH, protocol.ARCHIVE_PATH):
        path = root / name
        if path.exists() or path.is_symlink():
            raise FileExistsError("sensitivity already admitted")
    parent = (root / protocol.RUN_PATH).parent
    intent = parent / (protocol.PLAN_ID + "-launch.json")
    log = parent / (protocol.PLAN_ID + ".log")
    command = [str(root / ".venv/bin/python"), "-u", str(Path(__file__).resolve()), "--worker"]
    protocol.historical.save_new(intent, {"plan_id": protocol.PLAN_ID, "commit": commit,
        "requested_at": datetime.now(timezone.utc).isoformat(), "command": command, "log": str(log)})
    with log.open("x") as stream:
        process = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=stream,
            stderr=subprocess.STDOUT, start_new_session=True)
    receipt = {"pid": process.pid, "commit": commit, "log": str(log), "intent": str(intent)}
    protocol.historical.save_new(parent / (protocol.PLAN_ID + "-process.json"), receipt)
    return receipt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(protocol.run(root) if args.worker else launch(root),
        ensure_ascii=False, indent=2, allow_nan=False), flush=True)
