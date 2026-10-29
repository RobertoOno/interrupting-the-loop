"""Separate prospective freeze for the final small conceptual headroom calibration.

Reuses the v2 model-facing harness verbatim; never edits earlier freezes. Preparing,
validating, and preflighting do not instantiate a provider client. Only run does.
"""

import json
import random
import secrets
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .bedrock_calibration import HARNESS_FILES as V2_HARNESS, environment, summarize
from .bedrock_runner import BedrockAgentConfig, prompt_hash, render_workspace, run_bedrock_session, tool_hash
from .calibration import write_raw_manifest
from .calibration_review_v3 import materialize_v3, review_v3
from .calibration_worlds_v3 import REPO, REGISTRY, WorldV3Spec, build_v3, exclusion_audit, load_v3
from .conceptual_generator import ASSETS, sha, write_conceptual
from .lean_sandbox import probe_sandbox
from .submission import STANDARD_LEAN_AXIOMS

PLAN_ID = "p3a_conceptual_headroom_v3"
RUN_ROOT = "runs/p3/calibration"
GATE = {"complete_pairs": 4, "oracle_at_least": 3, "baseline_at_most": 2, "net_gain_at_least": 2}
PRICING = {"checked_on": "2026-09-04", "base_input_usd_per_million": 5.0,
           "base_output_usd_per_million": 25.0, "regional_multiplier": 1.1,
           "sources": ["https://platform.claude.com/docs/en/about-claude/pricing",
                       "https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock"],
           "basis": "standard regional list rates; excludes taxes/private discounts; not an AWS-enforced billing cap"}
HARNESS_FILES = tuple(sorted(set(V2_HARNESS) | {
    "src/creative_machine/formal_routes/calibration_worlds_v3.py",
    "src/creative_machine/formal_routes/calibration_review_v3.py",
    "src/creative_machine/formal_routes/calibration_protocol_v3.py",
    "src/creative_machine/formal_routes/conceptual_generator.py",
    "src/creative_machine/formal_routes/conceptual_review.py",
    "src/creative_machine/formal_routes/prototypes.py",
    "src/creative_machine/formal_routes/calibration.py",
    "scripts/p3_calibration_v3.py", REGISTRY,
    *[str(path.relative_to(REPO)) for path in ASSETS.glob("*.lean")],
}))


def save_new(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")


def fingerprint(repository: Path) -> dict:
    return {rel: sha((repository / rel).read_text()) for rel in HARNESS_FILES}


def prepare_v3(repository: Path, path: Path) -> dict:
    path = path.absolute()
    if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
        raise ValueError("prepare the plan inside the repository, without symlinks")
    evidence = path.with_name("calibration_local_review_v3.json")
    if path.exists() or evidence.exists():
        raise FileExistsError("never overwrite a prepared plan or its local evidence")
    provenance = fingerprint(repository)
    worlds = []
    for family in ("invariant", "representation"):
        seed = secrets.token_hex(8)
        spec = WorldV3Spec(family, seed, "calibration")
        relative = f"worlds/calibration/{spec.world_id}"
        root = write_conceptual(build_v3(spec), repository / relative)
        worlds.append({"family": family, "path": relative, "world_id": spec.world_id, "seed": seed,
                       "manifest_sha256": sha((root / "manifest.sha256").read_text())})
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(pool.map(review_v3, [repository / w["path"] for w in worlds]))
    review = {"model_calls": 0, "behavioral_gate_tested": False, "worlds": reviews,
              "exclusions": exclusion_audit(), "environment": environment(), "harness_sha256": provenance,
              "structural_checks_passed": all(r["structural_checks_passed"] for r in reviews)}
    save_new(evidence, review)
    if not review["structural_checks_passed"]:
        raise ValueError("local checks failed; no plan frozen, no model called, no automatic resampling")
    config = BedrockAgentConfig()
    cells = []
    for world in worlds:
        for holdout in (1, 2):
            for condition in ("no_bridge", "oracle_bridge"):
                cells.append({"world": world["path"], "world_id": world["world_id"], "holdout": holdout,
                              "condition": condition, "cell_id": "C3_" + secrets.token_hex(6).upper()})
    order_seed = secrets.randbits(64)
    random.Random(order_seed).shuffle(cells)
    for ordinal, cell in enumerate(cells, 1):
        cell["ordinal"] = ordinal
        with tempfile.TemporaryDirectory(prefix="p3-v3-input-freeze-") as temp:
            record = materialize_v3(repository / cell["world"], f"holdout{cell['holdout']}",
                "oracle" if cell["condition"] == "oracle_bridge" else None, Path(temp).resolve() / "workspace")
            cell["model_input_sha256"] = sha(render_workspace(record))
    plan = {"schema_version": 1, "status": "FROZEN", "plan_id": PLAN_ID, "provider": "bedrock-mantle",
        "created_at": datetime.now(timezone.utc).isoformat(), "agent": asdict(config),
        "max_parallel": 2, "max_total_cost_usd": 15.0, "reserved_worst_case_usd": 8 * config.reserved_cost_usd,
        "run_directory": RUN_ROOT + "/" + PLAN_ID,
        "system_prompt_sha256": prompt_hash(), "tool_schema_sha256": tool_hash(),
        "allowed_axioms": list(STANDARD_LEAN_AXIOMS), "environment": environment(),
        "harness_sha256": provenance, "worlds": worlds, "cells": cells, "order_seed": order_seed,
        "gate_rule": GATE, "last_small_calibration_before_domain_reassessment": True,
        "local_evidence": {"path": str(evidence.relative_to(repository)), "sha256": sha(evidence.read_text())},
        "pricing": PRICING,
        "notes": ["Known mathematical families; neither structural novelty nor invention is tested.",
                  "No proposers, main sample, P3B, internal-model probes, or pods in this freeze.",
                  "Same v2 model-facing prompt, tool, model, effort, limits, and standard Lean axiom policy.",
                  "Invariant levels exclude development components; literal word orbits exclude all declared development inputs.",
                  "Longer first sibling fixes an exhausted stratum; no selection uses model outcomes.",
                  "No retries/fallbacks or automatic refreezes; run directory must be new."]}
    if fingerprint(repository) != provenance:
        raise ValueError("harness changed during preparation; no plan frozen")
    save_new(path, plan)
    return plan


def _safe_path(repository: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("unsafe repository-relative path")
    path = repository / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repository.resolve()):
        raise ValueError("repository path escapes or is a symlink")
    return path


def load_plan_v3(repository: Path, path: Path) -> dict:
    plan = json.loads(path.read_text())
    if (plan.get("status") != "FROZEN" or plan.get("schema_version") != 1
            or plan.get("plan_id") != PLAN_ID or plan.get("provider") != "bedrock-mantle"):
        raise ValueError("the separate frozen v3 plan is required")
    if (plan.get("gate_rule") != GATE or plan.get("last_small_calibration_before_domain_reassessment") is not True
            or plan.get("pricing") != PRICING or plan.get("run_directory") != RUN_ROOT + "/" + PLAN_ID):
        raise ValueError("gate or stopping-rule drift")
    if (plan.get("agent") != asdict(BedrockAgentConfig()) or plan.get("max_parallel") != 2
            or plan.get("max_total_cost_usd") != 15.0
            or plan.get("reserved_worst_case_usd") != 8 * BedrockAgentConfig().reserved_cost_usd):
        raise ValueError("model, effort, budget or limits drift")
    if (plan.get("environment") != environment() or plan.get("allowed_axioms") != list(STANDARD_LEAN_AXIOMS)
            or plan.get("harness_sha256") != fingerprint(repository)
            or plan.get("system_prompt_sha256") != prompt_hash() or plan.get("tool_schema_sha256") != tool_hash()):
        raise ValueError("harness, environment, prompt or axiom drift")
    evidence = _safe_path(repository, plan["local_evidence"]["path"])
    review = json.loads(evidence.read_text())
    if (sha(evidence.read_text()) != plan["local_evidence"]["sha256"]
            or review.get("structural_checks_passed") is not True or review.get("model_calls") != 0
            or review.get("harness_sha256") != plan["harness_sha256"]):
        raise ValueError("local evidence drift")
    worlds = plan["worlds"]
    if len(worlds) != 2 or {w["family"] for w in worlds} != {"invariant", "representation"}:
        raise ValueError("exactly two distinct calibration families are required")
    if (review.get("exclusions") != exclusion_audit() or len(review.get("worlds", [])) != 2
            or {(r["world_id"], r["manifest_sha256"]) for r in review["worlds"]}
            != {(w["world_id"], w["manifest_sha256"]) for w in worlds}
            or any(r.get("phase") != "calibration" or not r.get("structural_checks_passed") for r in review["worlds"])):
        raise ValueError("local review does not cover the frozen worlds and exclusions")
    expected = set()
    for item in worlds:
        root = _safe_path(repository, item["path"])
        metadata = load_v3(root, phase="calibration")
        if (metadata["world_id"] != item["world_id"] or metadata["seed"] != item["seed"]
                or metadata["family"] != item["family"] or sha((root / "manifest.sha256").read_text()) != item["manifest_sha256"]):
            raise ValueError("world identity or manifest drift")
        expected.update((item["path"], item["world_id"], h, c) for h in (1, 2) for c in ("no_bridge", "oracle_bridge"))
    cells = plan["cells"]
    if (len(cells) != 8 or {(c["world"], c["world_id"], c["holdout"], c["condition"]) for c in cells} != expected
            or len({c["cell_id"] for c in cells}) != 8
            or sorted(c["ordinal"] for c in cells) != list(range(1, 9))
            or any(not c["cell_id"].replace("_", "").isalnum() for c in cells)):
        raise ValueError("invalid or duplicated cell matrix")
    return plan


def assert_committed_v3(repository: Path, path: Path, plan: dict) -> str:
    relatives = [*HARNESS_FILES, str(path.resolve().relative_to(repository.resolve())), plan["local_evidence"]["path"]]
    for item in plan["worlds"]:
        root = repository / item["path"]
        metadata = load_v3(root, phase="calibration")
        relatives.extend(f"{item['path']}/{rel}" for rel in (*metadata["artifact_hashes"], "metadata.json", "manifest.sha256"))
    for relative in sorted(set(relatives)):
        recorded = subprocess.run(["git", "show", "HEAD:" + relative], cwd=repository, capture_output=True, check=False)
        if recorded.returncode or recorded.stdout != (repository / relative).read_bytes():
            raise RuntimeError(f"freeze must be committed verbatim before inference: {relative}")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()


def preflight_v3(repository: Path, plan: dict) -> dict:
    reports = []
    for cell in plan["cells"]:
        with tempfile.TemporaryDirectory(prefix="p3-v3-sandbox-") as temp:
            root = repository / cell["world"]
            record = materialize_v3(root, f"holdout{cell['holdout']}",
                "oracle" if cell["condition"] == "oracle_bridge" else None, Path(temp).resolve() / "workspace")
            if sha(render_workspace(record)) != cell["model_input_sha256"]:
                raise ValueError("model input drift")
            report = probe_sandbox(record.path, root / "Hidden/OracleChecks.lean")
            if not report["ok"]:
                raise RuntimeError(f"sandbox check failed: {report}")
            reports.append({"cell_id": cell["cell_id"], **report})
    return {"ok": True, "model_calls": 0, "cells": reports}


def require_run_root(repository: Path, run_root: Path):
    if run_root.resolve() != (repository / RUN_ROOT).resolve():
        raise ValueError("run root is frozen; relocation must not enable a second experiment")


def run_v3(repository: Path, path: Path, run_root: Path) -> dict:
    require_run_root(repository, run_root)
    plan = load_plan_v3(repository, path)
    commit = assert_committed_v3(repository, path, plan)
    # All input/sandbox checks precede client construction; never spend on a bad preflight.
    preflight = preflight_v3(repository, plan)
    root = run_root / PLAN_ID
    root.mkdir(parents=True, exist_ok=False)
    save_new(root / "plan.json", plan)
    save_new(root / "provenance.json", {"commit": commit, "environment": environment(), "preflight": preflight})
    config = BedrockAgentConfig(**plan["agent"])

    def run_cell(cell):
        world = repository / cell["world"]
        metadata = load_v3(world, phase="calibration")
        cell_root = root / cell["cell_id"]
        record = materialize_v3(world, f"holdout{cell['holdout']}",
            "oracle" if cell["condition"] == "oracle_bridge" else None, cell_root / "workspace")
        if sha(render_workspace(record)) != cell["model_input_sha256"]:
            raise ValueError("model input drift")
        save_new(cell_root / "workspace_record.json", {**asdict(record), "path": str(record.path)})
        result = run_bedrock_session(record, namespace=metadata["roles"]["namespace"],
            statement=metadata["roles"]["holdout_statements"][cell["holdout"] - 1],
            bridge_supplied=cell["condition"] == "oracle_bridge", artifacts=cell_root / "artifacts", config=config)
        row = {"cell": cell, "result": result}
        save_new(cell_root / "result.json", row)
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_cell, cell) for cell in sorted(plan["cells"], key=lambda c: c["ordinal"])]
        for future in as_completed(futures):
            rows.append(future.result())
            print(json.dumps({"event": "cell_completed", "completed": len(rows), "total": 8}), flush=True)
    result = summarize(plan, rows)
    result.update({"behavioral_gate_tested": True, "main_sample_started": False,
                   "structural_novelty_claimed": False, "freeze_commit": commit})
    save_new(root / "summary.json", result)
    write_raw_manifest(root, root.parent / (PLAN_ID + ".sha256"))
    return result
