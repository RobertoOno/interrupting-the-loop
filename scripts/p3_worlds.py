#!/usr/bin/env python3
"""Generate and validate Program 3 calibration worlds (never model calls)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from creative_machine.formal_routes import WorldSpec, build_world, validate_world, write_world

ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_ROOT = ROOT / "worlds" / "calibration"
CALIBRATION_SPECS = (
    WorldSpec("CAL_T1_E2CCC255", "T1", int("e2ccc2555a3cccc7", 16)),
    WorldSpec("CAL_T2_15CCB41E", "T2", int("15ccb41e67d0ca58", 16)),
)


def generate_calibration(root: Path = CALIBRATION_ROOT) -> list[Path]:
    paths: list[Path] = []
    for spec in CALIBRATION_SPECS:
        destination = root / spec.world_id
        paths.append(write_world(build_world(spec), destination))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate-calibration")
    generate.add_argument("--root", type=Path, default=CALIBRATION_ROOT)
    validate = sub.add_parser("validate")
    validate.add_argument("worlds", type=Path, nargs="+")
    validate.add_argument("--lean", action="store_true")
    args = parser.parse_args()

    if args.command == "generate-calibration":
        paths = generate_calibration(args.root)
        print(json.dumps([str(path) for path in paths], indent=2))
        return

    failed = False
    reports = []
    for path in args.worlds:
        report = validate_world(path, run_lean=args.lean)
        reports.append(
            {
                "world": str(report.world),
                "ok": report.ok,
                "static_ok": report.static_ok,
                "lean_ok": report.lean_ok,
                "errors": report.errors,
                "checks": [
                    {"path": check.path, "expected": check.expected, "returncode": check.returncode}
                    for check in report.checks
                ],
            }
        )
        failed = failed or not report.ok
    print(json.dumps(reports, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
