"""Separate 16-session response-limit sensitivity; historical v3 stays immutable."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile

from creative_machine.aws_daily_budget import DailyBudget
from . import calibration_protocol_v3 as historical
from .bedrock_calibration import summarize as summarize_eight
from .bedrock_runner import BedrockAgentConfig, render_workspace, run_bedrock_session
from .calibration import write_raw_manifest
from .calibration_review_v3 import materialize_v3
from .calibration_worlds_v3 import load_v3
from .lean_sandbox import probe_sandbox

PLAN_ID = "p3a_response_limit_sensitivity_v1"
PLAN_PATH = "docs/p3/response_limit_sensitivity_plan_v1.json"
PARENT_PATH = "docs/p3/calibration_conceptual_plan_v3.json"
RUN_PATH = "runs/p3/sensitivity/" + PLAN_ID
ARCHIVE_PATH = "docs/p3/response_limit_sensitivity_evidence_v1"
LIMITS = (8192, 16384)
ORDER_SEED = 2026090801
PRICING = {**historical.PRICING, "checked_on": "2026-09-08"}
EXTRA_FILES = (
    "src/creative_machine/formal_routes/sensitivity_protocol_v1.py",
    "src/creative_machine/aws_daily_budget.py",
    "scripts/p3_sensitivity.py", "scripts/p3_run_budgeted_sensitivity_v1.py",
    "tests/test_p3_sensitivity_v1.py", "docs/p3/SENSIBILIDADE_LIMITE_RESPOSTA_V1.md",
    "docs/p3/AWS_LIMITE_DIARIO.md", PARENT_PATH,
)
HARNESS_FILES = tuple(sorted(set(historical.HARNESS_FILES) | set(EXTRA_FILES)))


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config(limit):
    if type(limit) is not int or limit not in LIMITS:
        raise ValueError("only the two prospective response limits are allowed")
    return replace(BedrockAgentConfig(), output_per_request=limit, request_timeout_seconds=300.0)


def fingerprint(repository):
    return {name: sha(repository / name) for name in HARNESS_FILES}


def cells_for(parent):
    cells = []
    for old in sorted(parent["cells"], key=lambda c: c["cell_id"]):
        for limit in LIMITS:
            cells.append({**{k: old[k] for k in ("world", "world_id", "holdout", "condition", "model_input_sha256")},
                "output_per_request": limit, "cell_id": f"S16_{old['cell_id'][3:]}_{limit}"})
    random.Random(ORDER_SEED).shuffle(cells)
    return [{**cell, "ordinal": i} for i, cell in enumerate(cells, 1)]


def build_plan(repository):
    parent = historical.load_plan_v3(repository, repository / PARENT_PATH)
    return {"schema_version": 1, "status": "FROZEN", "plan_id": PLAN_ID,
        "provider": "bedrock-mantle", "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_plan_sha256": sha(repository / PARENT_PATH), "historical_data_are_not_new_controls": True,
        "agent_by_limit": {str(n): asdict(config(n)) for n in LIMITS},
        "max_parallel": 2, "max_total_cost_usd": 30.0, "reserved_worst_case_usd": 16 * config(8192).reserved_cost_usd,
        "run_directory": RUN_PATH, "archive_directory": ARCHIVE_PATH, "order_seed": ORDER_SEED,
        "harness_sha256": fingerprint(repository), "environment": historical.environment(),
        "worlds": parent["worlds"], "cells": cells_for(parent),
        "system_prompt_sha256": parent["system_prompt_sha256"], "tool_schema_sha256": parent["tool_schema_sha256"],
        "allowed_axioms": parent["allowed_axioms"], "gate_rule_per_limit": historical.GATE,
        "robustness_requires_both_limits": True, "stop_admitting_on_infrastructure_failure": True,
        "pricing": PRICING, "main_sample_started": False, "mechanistic_stage_admitted": False}


def load_plan(repository, path):
    plan = json.loads(path.read_text())
    expected = build_plan(repository)
    created = datetime.fromisoformat(plan["created_at"])
    if created.tzinfo is None:
        raise ValueError("freeze timestamp must have a timezone")
    expected["created_at"] = plan["created_at"]
    if not same(plan, expected):
        raise ValueError("sensitivity protocol, inputs, environment or source drift")
    return plan


def prepare(repository):
    path = repository / PLAN_PATH
    if path.exists() or path.is_symlink():
        raise FileExistsError("never refreeze or overwrite the sensitivity plan")
    plan = build_plan(repository)
    historical.save_new(path, plan)
    return plan


def assert_committed(repository, plan):
    parent = historical.load_plan_v3(repository, repository / PARENT_PATH)
    commit = historical.assert_committed_v3(repository, repository / PARENT_PATH, parent)
    for name in (*HARNESS_FILES, PLAN_PATH):
        original = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=repository, timeout=15)
        if original != (repository / name).read_bytes():
            raise ValueError("uncommitted sensitivity freeze: " + name)
    return commit


def materialize(repository, cell, path):
    record = materialize_v3(repository / cell["world"], f"holdout{cell['holdout']}",
        "oracle" if cell["condition"] == "oracle_bridge" else None, path)
    if historical.sha(render_workspace(record)) != cell["model_input_sha256"]:
        raise ValueError("model-facing workspace differs from the historical input")
    return record


def preflight(repository, plan):
    reports = []
    for cell in plan["cells"]:
        with tempfile.TemporaryDirectory(prefix="p3-sensitivity-preflight-") as temporary:
            record = materialize(repository, cell, Path(temporary).resolve() / "workspace")
            report = probe_sandbox(record.path, repository / cell["world"] / "Hidden/OracleChecks.lean")
            if not report["ok"]:
                raise ValueError("sensitivity sandbox preflight failed: " + cell["cell_id"])
            reports.append({"cell_id": cell["cell_id"], **report})
    return {"ok": True, "model_calls": 0, "cells": reports}


def summarize(plan, rows):
    expected = {c["cell_id"]: c for c in plan["cells"]}
    ids = [r["cell"]["cell_id"] for r in rows]
    if len(ids) != len(set(ids)) or any(not same(expected.get(r["cell"]["cell_id"]), r["cell"]) for r in rows):
        raise ValueError("unknown, duplicate or relabelled sensitivity cell")
    by_limit = {}
    for limit in LIMITS:
        subset = [r for r in rows if r["cell"]["output_per_request"] == limit]
        subplan = {"plan_id": PLAN_ID, "agent": plan["agent_by_limit"][str(limit)], "gate_rule": historical.GATE}
        by_limit[str(limit)] = summarize_eight(subplan, subset)
    complete = len(rows) == 16 and all(not r["result"]["infrastructure_failure"] for r in rows)
    robust = complete and all(r["gate_passed"] for r in by_limit.values())
    if not complete:
        decision = "incomplete_review_infrastructure"
    elif not by_limit["8192"]["gate_passed"]:
        decision = "contrast_not_reproduced_review_before_main"
    elif robust:
        decision = "robust_under_tested_response_limits_prepare_transfer_not_main_admission"
    else:
        decision = "not_robust_to_response_limit_review_before_main"
    return {"schema_version": 1, "plan_id": PLAN_ID, "model": config(8192).model,
        "cells_started": len(rows), "cells_planned": 16, "all_cells_valid": complete,
        "not_started": sorted(set(expected) - set(ids)), "by_response_limit": by_limit,
        "robust_to_tested_limits": robust, "next_step": decision,
        "cost_usd_at_published_rates": sum(r["cost_usd_at_published_rates"] for r in by_limit.values()),
        "uncertain_requests": sum(r["uncertain_requests"] for r in by_limit.values()),
        "accounting_incomplete": any(r["result"].get("accounting_incomplete", False) for r in rows),
        "main_sample_started": False, "mechanistic_stage_admitted": False,
        "scope": "Two exposed calibration worlds, two dependent siblings each, one session per cell. No historical controls pooled, main sample, invention or mechanistic conclusion."}


def failure_result(exc):
    return {"status": "infrastructure_failure", "target_solved": False, "requests": 0,
        "infrastructure_failure": True, "uncertain_request": True, "accounting_incomplete": True,
        "error": f"unhandled cell failure: {type(exc).__name__}: {exc}",
        "tokens": {k: 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")},
        "cost_usd_at_published_rates": 0,
        "scope": "Unreported usage is unknown, not zero; full batch reservation must remain until reconciliation."}


def run(repository):
    plan = load_plan(repository, repository / PLAN_PATH)
    root = repository / RUN_PATH
    archive = repository / ARCHIVE_PATH
    if root.exists() or root.is_symlink() or archive.exists() or archive.is_symlink():
        raise FileExistsError("sensitivity already admitted; never rerun or relocate")
    checked = preflight(repository, plan)
    if not same(plan, load_plan(repository, repository / PLAN_PATH)):
        raise ValueError("sensitivity changed during preflight")
    commit = assert_committed(repository, plan)
    budget = DailyBudget(repository / "runs/aws-budget/claude_daily.jsonl")
    reservation = budget.reserve(PLAN_ID, plan["max_total_cost_usd"])
    root.mkdir(parents=True, exist_ok=False)
    historical.save_new(root / "plan.json", plan)
    historical.save_new(root / "budget-reservation.json", reservation)
    historical.save_new(root / "provenance.json", {"commit": commit, "environment": historical.environment(),
        "process_pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(), "preflight": checked})
    print(json.dumps({"event": "batch_started", "plan_id": PLAN_ID, "pid": os.getpid(), "commit": commit}), flush=True)

    def run_cell(cell):
        cell_root = root / cell["cell_id"]
        historical.save_new(cell_root / "started.json", {"cell": cell, "at": datetime.now(timezone.utc).isoformat()})
        try:
            metadata = load_v3(repository / cell["world"], phase="calibration")
            record = materialize(repository, cell, cell_root / "workspace")
            historical.save_new(cell_root / "workspace_record.json", {**asdict(record), "path": str(record.path)})
            result = run_bedrock_session(record, namespace=metadata["roles"]["namespace"],
                statement=metadata["roles"]["holdout_statements"][cell["holdout"] - 1],
                bridge_supplied=cell["condition"] == "oracle_bridge", artifacts=cell_root / "artifacts",
                config=config(cell["output_per_request"]))
        except Exception as exc:
            result = failure_result(exc)
        row = {"cell": cell, "result": result}
        historical.save_new(cell_root / "result.json", row)
        return row

    rows, cursor, stop = [], 0, False
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {}
        while pending or (cursor < len(plan["cells"]) and not stop):
            while not stop and len(pending) < 2 and cursor < len(plan["cells"]):
                cell = plan["cells"][cursor]
                pending[pool.submit(run_cell, cell)] = cell
                cursor += 1
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: pending[f]["ordinal"]):
                pending.pop(future)
                row = future.result()
                rows.append(row)
                stop = stop or row["result"]["infrastructure_failure"]
                print(json.dumps({"event": "cell_completed", "cell_id": row["cell"]["cell_id"],
                    "completed": len(rows), "total": 16, "status": row["result"]["status"]}), flush=True)
    result = summarize(plan, rows)
    result["freeze_commit"] = commit
    historical.save_new(root / "summary.json", result)
    if not result["uncertain_requests"] and not result["accounting_incomplete"] and all(
        r["result"]["status"] != "budget_accounting_error" for r in rows):
        historical.save_new(root / "budget-settlement.json", budget.settle(PLAN_ID, result["cost_usd_at_published_rates"]))
    write_raw_manifest(root, root.parent / (PLAN_ID + ".sha256"))
    return result
