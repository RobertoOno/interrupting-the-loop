"""A1 — sibling ladder sessions (v1): workspace per cell, plan with input hashes, preflight, budgeted run.

Reuses the P3 session loop verbatim (`run_bedrock_session`: system prompt, check_solution tool, Lean sandbox,
exact statement + axiom audit) and the P3 layout conventions. Arms: none (Base + target), ladder (+ SOURCE.md =
the previous step's complete worked example), sham (+ SOURCE.md = the fixed generic worked example).
No retry of a cell, no re-selection after data; a run is resumable only by skipping cells that already have a
result.json. Daily budget: one reservation per run through DailyBudget; a new cell is admitted only while the
actual spend plus the per-session ceilings of the running and the new cell fit the reservation.
"""
from __future__ import annotations
import hashlib, json, os, random, shutil, subprocess, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .bedrock_runner import BedrockAgentConfig, prompt_hash, render_workspace, run_bedrock_session, tool_hash
from .openai_session_v1 import OpenAIAgentConfig, render_prover_prompt, run_openai_session
from .ladder_v1 import STATEMENT, STEPS, load_step, mutation_check, verify_step
from .lean_sandbox import probe_sandbox
from .workspace import WorkspaceRecord

ARMS = ("none", "ladder", "sham", "skeleton", "content", "own", "reference")   # own/reference (v3): SOURCE.md given per cell
SOURCE_NOTE = ("SOURCE.md contains a worked example: a separate formal problem and its complete proof, supplied for\n"
               "reference. It may or may not be useful for this target.\n")
CONTENT_NOTE = ("SOURCE.md contains a mathematical hint about this target, in prose, with no Lean code.\n")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(repo: Path, p: Path) -> str:
    """Repository-relative path when inside the repository, else absolute (tests use temporary worlds)."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(Path(repo).resolve()))
    except ValueError:
        return str(p)


def render_example_md(world_dir: Path, solution_text: str) -> str:
    """A worked example in ONE format for the own and reference arms (v3): the problem's Base.lean and a complete
    verified proof, verbatim. The reference arm uses Hidden/Reference.lean; the own arm the model's own verified
    Solution.lean from stage 1."""
    base = (Path(world_dir) / "World/Base.lean").read_text(encoding="utf-8")
    return ("# Worked example\n\nA separate formal problem (its base definitions) and a complete, machine-verified proof of its target.\n\n"
            "```lean\n" + base + "```\n\n```lean\n" + solution_text + ("" if solution_text.endswith("\n") else "\n") + "```\n")


def materialize_ladder(step_dir: Path, arm: str, destination: Path, *, source_file: Path | None = None, task_note: str | None = None) -> WorkspaceRecord:
    """Expose lakefile, toolchain, Base, the target as World/ChallengeEvaluation.lean, the arm's SOURCE.md, TASK.md."""
    if arm not in ARMS:
        raise ValueError(arm)
    meta = load_step(step_dir)
    if arm == "ladder" and meta["source_files"]["ladder"] is None:
        raise ValueError("no ladder source at the first step")
    if arm in ("own", "reference"):
        if source_file is None or not Path(source_file).is_file():
            raise ValueError(f"arm {arm} requires an explicit source_file")
    elif arm != "none" and meta["source_files"].get(arm) is None:
        raise ValueError(f"world has no source for arm {arm}")
    dest = Path(destination).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for rel in ("lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"):
        out = dest / rel; out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(step_dir / rel, out); copied[rel] = _hash_file(out)
    if arm != "none":
        src = Path(source_file) if arm in ("own", "reference") else step_dir / meta["source_files"][arm]
        shutil.copy2(src, dest / "SOURCE.md"); copied["SOURCE.md"] = _hash_file(dest / "SOURCE.md")
    ns = meta["roles"]["namespace"]
    task = (f"Prove {ns}.{STATEMENT} from World/ChallengeEvaluation.lean.\n"
            "No bridge is supplied.\nSolution.lean must import only World.ChallengeEvaluation.\n"
            "Declare theorem evaluation_solution with exactly that frozen statement type, either\n"
            f"globally or inside exactly namespace {ns}.\n"
            "Write only Solution.lean; do not edit supplied files or any bridge.\n"
            + (CONTENT_NOTE if arm == "content" else SOURCE_NOTE if arm != "none" else "")
            + (("\n" + task_note.rstrip("\n") + "\n") if task_note else ""))
    (dest / "TASK.md").write_text(task, encoding="utf-8"); copied["TASK.md"] = _hash_file(dest / "TASK.md")
    exposed = {str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file()}
    if any(p.startswith(("Hidden/", "Sources/")) or p == "metadata.json" for p in exposed):
        raise AssertionError("hidden artifact leaked into the workspace")
    return WorkspaceRecord(dest, f"{meta['instance']}/{meta['step']}", "ladder_solver", arm, copied, ("Solution.lean",))


def model_input(record: WorkspaceRecord, mode: str = "tool") -> str:
    """What the model receives: the workspace listing (tool mode, Bedrock and open models) or the prover prompt."""
    return render_prover_prompt(record) if mode == "prover" else render_workspace(record)


def model_input_sha(step_dir: Path, arm: str, source_file: Path | None = None, task_note: str | None = None, mode: str = "tool") -> str:
    with tempfile.TemporaryDirectory(prefix="a1-input-") as tmp:
        return sha(model_input(materialize_ladder(step_dir, arm, Path(tmp) / "w", source_file=source_file, task_note=task_note), mode))


def make_plan(repo: Path, *, plan_id: str, phase: str, instances: list[Path], steps: list[str], arms: list[str], attempts: int,
              budgets: dict[str, int], agent: dict, order_seed: int, daily_reserve_usd: float, max_parallel: int = 2,
              notes: list[str] | None = None, main_budget_label: str | None = None,
              arms_from_step2: tuple[str, ...] = ("ladder", "sham"), cell_sources: dict | None = None, task_note: str | None = None) -> dict:
    """Arms in `arms_from_step2` have no cell at the first step (the ladder by necessity, the sham by design).
    `cell_sources` maps (instance, arm) -> repo-relative SOURCE.md for the own/reference arms; instances without an
    entry get no cell in that arm (recorded in the plan)."""
    cells = []; missing = []
    for inst in instances:
        inst = Path(inst)
        for s in steps:
            d = inst / s
            meta = load_step(d)
            for arm in arms:
                if (arm == "ladder" and meta["source_files"]["ladder"] is None) or (arm in arms_from_step2 and meta["step_index"] == 1):
                    continue
                src = None
                if arm in ("own", "reference"):
                    src = (cell_sources or {}).get((meta["instance"], arm))
                    if src is None:
                        missing.append({"instance": meta["instance"], "step": s, "arm": arm}); continue
                for label in budgets:
                    h = model_input_sha(d, arm, repo / src if src else None, task_note, agent.get("mode", "tool"))
                    for a in range(attempts):
                        cells.append({"cell_id": f"{meta['instance']}_{s}_{arm}_{label}_a{a}", "instance": meta["instance"], "step": s, "arm": arm,
                                      "budget_label": label, "max_output_tokens": budgets[label], "attempt": a,
                                      "world": _rel(repo, d), "model_input_sha256": h, "namespace": meta["roles"]["namespace"],
                                      **({"source_file": src} if src else {})})
    random.Random(order_seed).shuffle(cells)
    for i, c in enumerate(cells):
        c["ordinal"] = i
    if agent.get("provider", "bedrock") == "bedrock":
        cfg = BedrockAgentConfig(**{k: v for k, v in agent.items() if k in BedrockAgentConfig.__dataclass_fields__})
        ceilings = {label: (cfg.max_input_tokens * cfg.input_usd_per_million + tok * cfg.output_usd_per_million) / 1e6 for label, tok in budgets.items()}
    else:   # open model on a rented GPU: no per-token cost; the launcher accounts the hours
        ceilings = {label: 0.0 for label in budgets}
    plan = {"schema": "a1_ladder_plan_v1", "plan_id": plan_id, "phase": phase, "status": "prepared", "created_at": datetime.now(timezone.utc).isoformat(),
            "instances": [{"instance": load_step(Path(i) / steps[0])["instance"], "path": _rel(repo, Path(i)),
                           "manifests": {s: _hash_file(Path(i) / s / "manifest.sha256") for s in steps}} for i in instances],
            "steps": steps, "arms": arms, "attempts": attempts, "budgets": budgets, "main_budget_label": main_budget_label,
            "agent": agent, "system_prompt_sha256": prompt_hash(), "tool_schema_sha256": tool_hash(), "order_seed": order_seed,
            "max_parallel": max_parallel, "daily_reserve_usd": daily_reserve_usd, "session_ceiling_usd": ceilings,
            "worst_case_usd": round(sum(ceilings[c["budget_label"]] for c in cells), 2), "cells": cells, "notes": notes or [],
            "missing_source_cells": missing, "task_note": task_note}
    return plan


def preflight(repo: Path, plan: dict, *, lean: bool = True) -> dict:
    """Hash drift of every cell input, Lean verification + mutation check of every step, sandbox probe on one workspace per arm."""
    out = {"ok": True, "cells": len(plan["cells"]), "drift": [], "steps": [], "sandbox": [], "model_calls": 0}
    seen = set()
    for c in plan["cells"]:
        key = (c["world"], c["arm"], c.get("source_file"))
        if key in seen:
            continue
        seen.add(key)
        if model_input_sha(repo / c["world"], c["arm"], repo / c["source_file"] if c.get("source_file") else None, plan.get("task_note"),
                           plan["agent"].get("mode", "tool")) != c["model_input_sha256"]:
            out["drift"].append(c["cell_id"]); out["ok"] = False
    if lean:
        for world in sorted({c["world"] for c in plan["cells"]}):
            v = verify_step(repo / world); m = mutation_check(repo / world)
            rec = {"world": world, "reference_ok": v["reference_ok"], "modules_ok": v["modules_ok"], "mutation_ok": m["reference_rejected"] and m["witness_ok"]}
            out["steps"].append(rec)
            if not (rec["reference_ok"] and rec["modules_ok"] and rec["mutation_ok"]):
                out["ok"] = False
    for arm in plan["arms"]:
        c = next((x for x in plan["cells"] if x["arm"] == arm), None)
        if c is None:
            continue
        with tempfile.TemporaryDirectory(prefix="a1-probe-") as tmp:
            rec = materialize_ladder(repo / c["world"], arm, Path(tmp) / "w", source_file=repo / c["source_file"] if c.get("source_file") else None, task_note=plan.get("task_note"))
            rep = probe_sandbox(rec.path, repo / c["world"] / "Hidden/Reference.lean")
            out["sandbox"].append({"arm": arm, "ok": rep.get("ok")})
            if not rep.get("ok"):
                out["ok"] = False
    return out


def git_state(repo: Path, paths: list[str]) -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=repo, capture_output=True, text=True).stdout.splitlines()
    return {"commit": head, "dirty": dirty}


def run_plan(repo: Path, plan_path: Path, run_root: Path, *, journal: Path, client_factory=None, allow_dirty: bool = False, checker=None,
             run_tag: str | None = None) -> dict:
    """`client_factory` and `checker` exist for offline tests only; production passes neither."""
    from creative_machine.aws_daily_budget import DailyBudget
    plan = json.loads(plan_path.read_text())
    provider = plan["agent"].get("provider", "bedrock")
    base_url = os.environ.get("CM_OPENAI_BASE_URL") if provider != "bedrock" else None
    if provider != "bedrock" and not base_url:
        raise RuntimeError("CM_OPENAI_BASE_URL is required for an open-model plan (the endpoint is not part of the frozen plan)")
    sources = [_rel(repo, plan_path)] + [i["path"] for i in plan["instances"]] + [
        "src/creative_machine/formal_routes/ladder_v1.py", "src/creative_machine/formal_routes/ladder_runner_v1.py",
        "src/creative_machine/formal_routes/bedrock_runner.py", "src/creative_machine/formal_routes/openai_session_v1.py",
        "src/creative_machine/formal_routes/submission.py", "scripts/analysis_a1.py"]
    state = git_state(repo, sources)
    if state["dirty"] and not allow_dirty:
        raise RuntimeError("sources not committed: " + "; ".join(state["dirty"][:5]))
    root = run_root / plan["plan_id"]; root.mkdir(parents=True, exist_ok=True)
    pre = preflight(repo, plan, lean=False)
    if not pre["ok"]:
        raise RuntimeError(f"preflight failed: {pre}")
    (root / "provenance.json").write_text(json.dumps({"git": state, "preflight": pre, "started_at": datetime.now(timezone.utc).isoformat(),
                                                       "system_prompt_sha256": prompt_hash(), "tool_schema_sha256": tool_hash(),
                                                       "provider": provider, "base_url": base_url}, indent=1) + "\n")
    if not (root / "plan.json").exists():
        shutil.copy2(plan_path, root / "plan.json")
    cfg_base = plan["agent"]; reserve = Decimal(str(plan["daily_reserve_usd"]))
    run_id = f"{plan['plan_id']}_{run_tag or datetime.now().strftime('%Y%m%dT%H%M%S')}"  # one reservation per (resumed) run
    budget = None
    if provider == "bedrock":
        budget = DailyBudget(journal); budget.reserve(run_id, reserve)
    lock = threading.Lock(); spent = {"actual": Decimal("0"), "running": 0, "stopped": None}
    pending = [c for c in sorted(plan["cells"], key=lambda c: c["ordinal"]) if not (root / c["cell_id"] / "result.json").exists()]
    log = root / "run.log"

    def say(msg):
        with log.open("a") as h:
            h.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")
        print(msg, flush=True)

    def run_cell(c):
        ceiling = Decimal(str(plan["session_ceiling_usd"][c["budget_label"]]))
        with lock:
            if spent["stopped"]:
                return None
            if spent["actual"] + ceiling * (spent["running"] + 1) > reserve:
                spent["stopped"] = "reserve_exhausted"; return None
            spent["running"] += 1
        cell_root = root / c["cell_id"]
        try:
            rec = materialize_ladder(repo / c["world"], c["arm"], cell_root / "workspace", source_file=repo / c["source_file"] if c.get("source_file") else None, task_note=plan.get("task_note"))
            if sha(model_input(rec, plan["agent"].get("mode", "tool"))) != c["model_input_sha256"]:
                raise ValueError("model input drift")
            (cell_root / "workspace_record.json").write_text(json.dumps({**asdict(rec), "path": str(rec.path)}, indent=1))
            # budget label = the session output cap AND the per-request cap (a single long attempt may use all of it);
            # amended 2026-09-12 23:20 after pilot v1 showed 16k sessions cut at the 8192 per-request cap
            if provider == "bedrock":
                cfg = BedrockAgentConfig(**{**{k: v for k, v in cfg_base.items() if k in BedrockAgentConfig.__dataclass_fields__},
                                            "max_output_tokens": c["max_output_tokens"], "output_per_request": c["max_output_tokens"]})
                res = run_bedrock_session(rec, namespace=c["namespace"], statement=STATEMENT, bridge_supplied=False, artifacts=cell_root / "artifacts",
                                          config=cfg, client=(client_factory(cfg) if client_factory else None), checker=checker)
            else:
                ocfg = OpenAIAgentConfig(**{**{k: v for k, v in cfg_base.items() if k in OpenAIAgentConfig.__dataclass_fields__},
                                            "base_url": base_url, "max_output_tokens": c["max_output_tokens"], "output_per_request": c["max_output_tokens"]})
                res = run_openai_session(rec, namespace=c["namespace"], statement=STATEMENT, bridge_supplied=False, artifacts=cell_root / "artifacts",
                                         config=ocfg, post=(client_factory(ocfg) if client_factory else None), checker=checker)
            row = {"cell": c, "result": res}
            (cell_root / "result.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n")
            cost = Decimal(str(res.get("unresolved_charge_upper_estimate_usd", res["cost_usd_at_published_rates"])))
            with lock:
                spent["actual"] += cost; spent["running"] -= 1
                if res["infrastructure_failure"] or res["status"] == "protocol_violation":
                    spent["stopped"] = f"{res['status']}: {res.get('error')}"
            say(f"{c['cell_id']}: {res['status']} tokens_out={res['tokens']['output_tokens']} cost={cost:.3f} total={spent['actual']:.2f}")
            return row
        except Exception as exc:
            with lock:
                spent["running"] -= 1; spent["stopped"] = f"exception: {type(exc).__name__}: {exc}"
            say(f"{c['cell_id']}: EXCEPTION {type(exc).__name__}: {exc}")
            return None

    workers = int(os.environ.get("CM_MAX_PARALLEL") or plan["max_parallel"])   # operational override (A9 E1): client slots <= what the server can hold
    say(f"run {run_id}: {len(pending)} pending cells, reserve {reserve}, max_parallel {plan['max_parallel']}" + (f" (overridden to {workers})" if workers != plan["max_parallel"] else ""))
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_cell, c) for c in pending]
        for f in as_completed(futures):
            r = f.result()
            if r:
                rows.append(r)
    if budget is not None:
        budget.settle(run_id, spent["actual"].quantize(Decimal("0.01")))
    summary = {"run_id": run_id, "completed": len(rows), "pending_before": len(pending), "stopped": spent["stopped"],
               "actual_usd": str(spent["actual"].quantize(Decimal("0.01"))), "reserve_usd": str(reserve),
               "statuses": {s: sum(1 for r in rows if r["result"]["status"] == s) for s in {r["result"]["status"] for r in rows}}}
    (root / f"summary_{run_id}.json").write_text(json.dumps(summary, indent=1) + "\n")
    say(f"run {run_id} done: {summary}")
    return summary
