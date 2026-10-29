"""A separately frozen calibration for the Bedrock proof-tool protocol."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import random
import secrets
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .bedrock_runner import BedrockAgentConfig, make_client, prompt_hash, run_bedrock_session, tool_hash
from .calibration import write_raw_manifest
from .codex_runner import sha256_file
from .generator import WorldSpec, build_world, write_world
from .lean_sandbox import CODEX_BINARY, probe_sandbox
from .submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
from .validation import validate_world
from .workspace import materialize_evaluator

HARNESS_FILES = (
    "src/creative_machine/formal_routes/bedrock_runner.py",
    "src/creative_machine/formal_routes/bedrock_calibration.py",
    "src/creative_machine/formal_routes/lean_sandbox.py",
    "src/creative_machine/formal_routes/submission.py",
    "src/creative_machine/formal_routes/workspace.py",
    "src/creative_machine/formal_routes/generator.py",
    "src/creative_machine/formal_routes/validation.py",
    "src/creative_machine/formal_routes/codex_runner.py",
    "scripts/p3_bedrock.py",
)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def environment() -> dict:
    return {"python": platform.python_version(), "anthropic": importlib.metadata.version("anthropic"),
            "boto3": importlib.metadata.version("boto3"), "botocore": importlib.metadata.version("botocore"),
            "sandbox_binary_sha256": sha256_file(CODEX_BINARY)}


def prepare_plan(repository: Path, path: Path) -> dict:
    if path.exists():
        raise FileExistsError("plan already exists; never silently refreeze")
    worlds, cells = [], []
    for template in ("T1", "T2"):
        seed = secrets.randbits(64)
        spec = WorldSpec(f"CAL2_{template}_{seed:016X}", template, seed, difficulty="hard")
        rel = f"worlds/calibration/{spec.world_id}"
        world = write_world(build_world(spec), repository / rel)
        report = validate_world(world, run_lean=True)
        report.require_ok()
        relevant_words = len((world / "Sources/Relevant.md").read_text().split())
        sham_words = len((world / "Sources/Sham.md").read_text().split())
        if abs(relevant_words - sham_words) > max(relevant_words, sham_words) * 0.05:
            raise ValueError("source word counts differ by more than 5%")
        worlds.append({"path": rel, "world_id": spec.world_id, "seed": seed,
                       "template": template, "manifest_sha256": sha256_file(world / "manifest.sha256"),
                       "source_words": {"relevant": relevant_words, "sham": sham_words}})
        for holdout in (1, 2):
            for condition in ("no_bridge", "oracle_bridge"):
                cells.append({"world": rel, "world_id": spec.world_id, "holdout": holdout,
                              "condition": condition, "cell_id": "BC_" + secrets.token_hex(5).upper()})
    ordering_seed = secrets.randbits(64)
    random.Random(ordering_seed).shuffle(cells)
    for ordinal, cell in enumerate(cells, 1):
        cell["ordinal"] = ordinal
    config = BedrockAgentConfig()
    plan = {"schema_version": 1, "status": "FROZEN", "provider": "bedrock-mantle",
            "plan_id": "p3a_bedrock_headroom_v2", "created_at": datetime.now(timezone.utc).isoformat(),
            "agent": asdict(config), "max_parallel": 2, "max_total_cost_usd": 15.0,
            "reserved_worst_case_usd": len(cells) * config.reserved_cost_usd,
            "system_prompt_sha256": prompt_hash(), "tool_schema_sha256": tool_hash(),
            "allowed_axioms": list(STANDARD_LEAN_AXIOMS), "environment": environment(),
            "harness_sha256": {rel: sha256_file(repository / rel) for rel in HARNESS_FILES},
            "worlds": worlds, "order_seed": ordering_seed, "cells": cells,
            "gate_rule": {"complete_pairs": 4, "oracle_at_least": 3,
                          "baseline_at_most": 2, "net_gain_at_least": 2},
            "notes": ["Calibration only; both worlds permanently excluded from main.",
                      "New provider, proof-tool harness and standard Lean axiom policy; not a matched model comparison to v1.",
                      "No automatic model retries, fallbacks, external tools, or model-visible outcomes from other cells.",
                      "Token-count reservations include 10% plus 1024 tokens; unknown charges retain full reservation.",
                      "Application budget at published regional rates; taxes and negotiated discounts excluded."]}
    save_json(path, plan)
    return plan


def load_plan(repository: Path, path: Path) -> dict:
    plan = json.loads(path.read_text())
    if plan.get("schema_version") != 1 or plan.get("status") != "FROZEN":
        raise ValueError("a frozen schema-1 plan is required")
    if plan.get("provider") != "bedrock-mantle" or not plan["plan_id"].replace("_", "").isalnum():
        raise ValueError("invalid provider or plan identifier")
    if plan["system_prompt_sha256"] != prompt_hash() or plan["tool_schema_sha256"] != tool_hash():
        raise ValueError("prompt or tool drift")
    if set(plan["harness_sha256"]) != set(HARNESS_FILES):
        raise ValueError("incomplete harness fingerprint")
    for rel, expected in plan["harness_sha256"].items():
        if sha256_file(repository / rel) != expected:
            raise ValueError(f"harness drift: {rel}")
    if plan["environment"] != environment() or plan["allowed_axioms"] != list(STANDARD_LEAN_AXIOMS):
        raise ValueError("environment or axiom policy drift")
    config = BedrockAgentConfig(**plan["agent"])
    if config.aws_profile != "main-account" or config.model != "anthropic.claude-opus-5":
        raise ValueError("this calibration only supports the frozen Opus/main-account setup")
    if config.max_turns < 1 or config.max_input_tokens < 1 or config.max_output_tokens < 256:
        raise ValueError("invalid agent limits")
    if config.input_usd_per_million < 5.5 or config.output_usd_per_million < 27.5:
        raise ValueError("rates below the frozen regional estimate")
    if len(plan["worlds"]) != 2 or {w["template"] for w in plan["worlds"]} != {"T1", "T2"}:
        raise ValueError("exactly one calibration world per template is required")
    expected_cells = set()
    for item in plan["worlds"]:
        world = (repository / item["path"]).resolve()
        if not world.is_relative_to(repository.resolve()):
            raise ValueError("world path escapes repository")
        validate_world(world).require_ok()
        metadata = json.loads((world / "metadata.json").read_text())
        if metadata["world_id"] != item["world_id"] or metadata["phase"] != "calibration" or metadata["eligible_for_main"]:
            raise ValueError("only permanently excluded calibration worlds are allowed")
        if sha256_file(world / "manifest.sha256") != item["manifest_sha256"]:
            raise ValueError("world manifest drift")
        expected_cells.update((item["path"], item["world_id"], h, c)
                              for h in (1, 2) for c in ("no_bridge", "oracle_bridge"))
    cells = plan["cells"]
    actual_cells = {(c["world"], c["world_id"], c["holdout"], c["condition"]) for c in cells}
    if len(cells) != 8 or actual_cells != expected_cells or len({c["cell_id"] for c in cells}) != 8:
        raise ValueError("incomplete or duplicated cell matrix")
    if sorted(c["ordinal"] for c in cells) != list(range(1, 9)):
        raise ValueError("invalid cell ordering")
    if any(not c["cell_id"].replace("_", "").isalnum() for c in cells):
        raise ValueError("unsafe cell identifier")
    if not 1 <= plan["max_parallel"] <= 2 or len(cells) * config.reserved_cost_usd > min(15, plan["max_total_cost_usd"]):
        raise ValueError("plan exceeds the calibration budget or concurrency bound")
    return plan


def preflight(repository: Path, plan: dict) -> dict:
    reports = []
    for cell in plan["cells"]:
        world = repository / cell["world"]
        with tempfile.TemporaryDirectory(prefix="p3-bedrock-probe-") as temp:
            record = materialize_evaluator(world, cell["holdout"], cell["condition"], Path(temp) / "workspace")
            report = probe_sandbox(record.path, world / "Hidden/OracleChecks.lean")
            if not report["ok"]:
                raise RuntimeError(f"sandbox failed: {report}")
            reports.append(report)
    return {"ok": True, "cells": len(reports), "sandbox_checks": reports, "model_calls": 0}


def assert_committed(repository: Path, path: Path, plan: dict) -> str:
    tracked = list(plan["harness_sha256"]) + [str(path.resolve().relative_to(repository.resolve()))]
    tracked += [item["path"] for item in plan["worlds"]]
    proc = subprocess.run(["git", "diff", "HEAD", "--", *tracked], cwd=repository, capture_output=True, text=True, check=True)
    if proc.stdout:
        raise RuntimeError("freeze must be committed before any model call")
    stored = subprocess.run(["git", "show", "HEAD:" + tracked[len(plan["harness_sha256"])]], cwd=repository, capture_output=True, check=True).stdout
    if stored != path.read_bytes():
        raise RuntimeError("plan is not present verbatim in HEAD")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()


def run_plan(repository: Path, path: Path, run_root: Path) -> dict:
    plan = load_plan(repository, path)
    commit = assert_committed(repository, path, plan)
    root = run_root / plan["plan_id"]
    root.mkdir(parents=True, exist_ok=False)
    save_json(root / "plan.json", plan)
    save_json(root / "provenance.json", {"commit": commit, "environment": environment()})
    config = BedrockAgentConfig(**plan["agent"])

    def run_cell(cell):
        world = repository / cell["world"]
        meta = json.loads((world / "metadata.json").read_text())
        cell_root = root / cell["cell_id"]
        record = materialize_evaluator(world, cell["holdout"], cell["condition"], cell_root / "workspace")
        save_json(cell_root / "workspace_record.json", {**asdict(record), "path": str(record.path)})
        result = run_bedrock_session(record, namespace=meta["roles"]["namespace"],
            statement=meta["roles"]["holdout_statements"][cell["holdout"] - 1],
            bridge_supplied=cell["condition"] == "oracle_bridge", artifacts=cell_root / "artifacts", config=config)
        row = {"cell": cell, "result": result}
        save_json(cell_root / "result.json", row)
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=plan["max_parallel"]) as pool:
        futures = [pool.submit(run_cell, cell) for cell in sorted(plan["cells"], key=lambda c: c["ordinal"])]
        for future in as_completed(futures):
            rows.append(future.result())
            print(json.dumps({"event": "cell_completed", "completed": len(rows), "total": 8}), flush=True)
    result = summarize(plan, rows)
    save_json(root / "summary.json", result)
    write_raw_manifest(root, root.parent / (plan["plan_id"] + ".sha256"))
    return result


def summarize(plan: dict, rows: list[dict]) -> dict:
    matrix = {}
    valid = [r for r in rows if not r["result"]["infrastructure_failure"]]
    for row in valid:
        c = row["cell"]
        matrix.setdefault((c["world_id"], c["holdout"]), {})[c["condition"]] = row["result"]["target_solved"]
    pairs = [m for m in matrix.values() if set(m) == {"no_bridge", "oracle_bridge"}]
    baseline = sum(m["no_bridge"] for m in pairs)
    oracle = sum(m["oracle_bridge"] for m in pairs)
    g = plan["gate_rule"]
    return {"schema_version": 1, "plan_id": plan["plan_id"], "model": plan["agent"]["model"],
        "cells_total": len(rows), "cells_valid": len(valid), "complete_pairs": len(pairs),
        "baseline_successes": baseline, "oracle_successes": oracle, "net_gain": oracle - baseline,
        "gate_passed": len(pairs) == g["complete_pairs"] and oracle >= g["oracle_at_least"]
                       and baseline <= g["baseline_at_most"] and oracle - baseline >= g["net_gain_at_least"],
        "cost_usd_at_published_rates": sum(r["result"]["cost_usd_at_published_rates"] for r in rows),
        "uncertain_requests": sum(r["result"]["uncertain_request"] for r in rows),
        "tokens": {name: sum(r["result"]["tokens"][name] for r in rows) for name in
                   ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")},
        "cells": [{"cell": r["cell"], "status": r["result"]["status"],
                   "target_solved": r["result"]["target_solved"], "requests": r["result"]["requests"],
                   "tokens": r["result"]["tokens"], "cost_usd_at_published_rates": r["result"]["cost_usd_at_published_rates"],
                   "error": r["result"]["error"]} for r in sorted(rows, key=lambda r: r["cell"]["ordinal"])]}
