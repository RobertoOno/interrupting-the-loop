#!/usr/bin/env python3
"""Validate, run, and summarize the frozen Program 3A behavioral calibration."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from creative_machine.formal_routes.calibration import (
    load_headroom_plan,
    preflight_cell_sandbox,
    run_headroom_plan,
    summarize_headroom,
    write_raw_manifest,
)
from creative_machine.formal_routes.codex_runner import CodexAgentConfig
from creative_machine.formal_routes.workspace import (
    EvaluatorCondition,
    materialize_evaluator,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = ROOT / "docs" / "p3" / "calibration_headroom_plan_v1.json"


def _load(path: Path):
    return load_headroom_plan(path, repository=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-plan")
    validate.add_argument("--plan", type=Path, default=DEFAULT_PLAN)

    probe = sub.add_parser("sandbox-probe")
    probe.add_argument("--plan", type=Path, default=DEFAULT_PLAN)

    run = sub.add_parser("run-headroom")
    run.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run.add_argument("--live-root", type=Path, required=True)
    run.add_argument("--archive-root", type=Path)
    run.add_argument("--parallel", type=int)

    summarize = sub.add_parser("summarize-headroom")
    summarize.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    summarize.add_argument("--run-root", type=Path, required=True)
    summarize.add_argument("--output", type=Path)
    summarize.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    plan = _load(args.plan)
    if args.command == "validate-plan":
        print(
            json.dumps(
                {
                    "ok": True,
                    "plan_id": plan.plan_id,
                    "cells": len(plan.cells),
                    "model": plan.model,
                    "reasoning_effort": plan.reasoning_effort,
                    "timeout_seconds": plan.timeout_seconds,
                    "max_parallel": plan.max_parallel,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    config = CodexAgentConfig(
        model=plan.model,
        reasoning_effort=plan.reasoning_effort,
        timeout_seconds=plan.timeout_seconds,
        expected_cli_version=plan.expected_cli_version,
        prompt=plan.prompt,
    )
    if args.command == "sandbox-probe":
        cell = plan.cells[0]
        world = ROOT / cell.world
        with tempfile.TemporaryDirectory(prefix="p3-calibration-probe-") as temp:
            workspace = Path(temp) / "workspace"
            materialize_evaluator(
                world,
                cell.holdout,
                EvaluatorCondition(cell.condition),
                workspace,
            )
            report = preflight_cell_sandbox(
                workspace,
                forbidden_probe=world / "Hidden" / "OracleChecks.lean",
                config=config,
            )
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    if args.command == "run-headroom":
        print(
            json.dumps(
                {
                    "event": "run_started",
                    "plan_id": plan.plan_id,
                    "cells": len(plan.cells),
                    "parallel": args.parallel or plan.max_parallel,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        results = run_headroom_plan(
            plan,
            repository=ROOT,
            live_root=args.live_root,
            archive_root=args.archive_root,
            parallel=args.parallel,
        )
        for result in results:
            print(
                json.dumps(
                    {
                        "event": "cell_completed",
                        "ordinal": result["ordinal"],
                        "cell_id": result["cell"]["cell_id"],
                        "status": result["attempt"]["status"],
                        "target_solved": result["attempt"]["target_solved"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        print(json.dumps({"event": "run_completed", "plan_id": plan.plan_id}, sort_keys=True))
        return

    summary = summarize_headroom(plan, run_root=args.run_root)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        write_raw_manifest(Path(args.run_root) / plan.plan_id, args.manifest)
    print(rendered, end="")


if __name__ == "__main__":
    main()
