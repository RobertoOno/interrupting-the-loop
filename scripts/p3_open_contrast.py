#!/usr/bin/env python3
"""Degrau 2 — the behavioural contrast in an OPEN model (pre-registered PLANO 2026-09-08 before any generation).
Same frozen Lean worlds, workspaces and exact verifiers as the Opus diagnostic; the proposer is Qwen3.8-27B served
by vLLM (OpenAI-compatible chat endpoint over an SSH tunnel), generation on the pod, verification on this machine.
Protocol difference from the Opus runners (documented): no tool call; the model returns fenced ```lean blocks, each
starting with a `-- FILE: <name>` line; every complete submission is verified and the compiler feedback is returned
as the next user message; the FINAL candidate is the last complete submission (no fallback), as in the Opus runs.

Factors: world (2) x holdout (2) x condition {no_bridge, oracle_bridge} x budget {4096, 8192, 16384} x thinking {off, on}
for recipients (48 sessions); world (2) x arm {D0, D, C2} x budget {8192, 16384} x thinking {off, on} for proposers (24).

    PYTHONPATH=src python scripts/p3_open_contrast.py --base http://localhost:18000/v1 --model Qwen/Qwen3.8-27B [--limit N] [--workers 4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from creative_machine.formal_routes.bedrock_runner import render_workspace  # noqa: E402
from creative_machine.formal_routes.calibration_worlds_v3 import load_v3  # noqa: E402
from creative_machine.formal_routes.production_contract_v1 import (  # noqa: E402
    materialize_production_proposer, render_production_proposer, verify_production)
from creative_machine.formal_routes.submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution  # noqa: E402
from creative_machine.formal_routes.workspace import materialize_evaluator  # noqa: E402

OUT = REPO / "runs/p3/open_contrast_v1"
WORLDS = ("worlds/calibration/CAL3_I_E87C49876088749B", "worlds/calibration/CAL3_R_F76437525B190ECB")
BUDGETS_R, BUDGETS_P = (4096, 8192, 16384), (8192, 16384)
MAX_TURNS, SESSION_S, REQ_S, VERIFY_S = 6, 900, 600, 120
CONTEXT_MARGIN = 512
SYS_R = """You are a Lean 4 proof-solving agent in a controlled experiment. All available files are supplied in the user
message. Follow TASK.md exactly. Use Lean 4.33.1 with Std only (no Mathlib). Prove the exact frozen statement; only the
standard axioms propext, Classical.choice and Quot.sound may appear as transitive dependencies; sorry is forbidden; no
new axioms, metaprogramming, custom notation or hash commands; do not change supplied files. To submit, reply with the
COMPLETE contents of Solution.lean in one fenced block that starts with the line `-- FILE: Solution.lean`:
```lean
-- FILE: Solution.lean
...
```
You will receive the compiler verdict and may revise. A verified proof ends the session. No shell or other files exist."""
SYS_P = """You are a Lean 4 proof-solving agent in a controlled experiment. All available files are supplied in the user
message. Follow TASK.md exactly. Use Lean 4.33.1 with Std only (no Mathlib). Only the standard axioms propext,
Classical.choice and Quot.sound may appear as transitive dependencies; sorry is forbidden; no new axioms,
metaprogramming, custom notation or hash commands; do not change supplied files. Submit TWO files in two fenced blocks,
each starting with a `-- FILE:` line: first Bridge.lean (only the reusable intermediary theorem `candidate_bridge` and
its helpers, importing only World.Base), then Solution.lean (the visible target, importing World.ChallengeVisible and
Bridge). Both files are checked separately; a valid bridge stays valid even if the visible solution fails. You will
receive the verdicts and may revise; both verified ends the session. The last complete submission is the final one."""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def chat(base: str, model: str, messages: list[dict], max_tokens: int, thinking: bool, temperature: float) -> dict:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
               "chat_template_kwargs": {"enable_thinking": thinking}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQ_S) as resp:
        return json.loads(resp.read())


def blocks(text: str) -> dict[str, str]:
    """{filename: source} for every fenced block whose first line is `-- FILE: name`."""
    out = {}
    for m in re.finditer(r"```(?:lean|lean4)?\s*\n(.*?)(?:```|\Z)", text, re.S):
        body = m.group(1)
        mm = re.match(r"\s*--\s*FILE:\s*([A-Za-z0-9_./]+)\s*\n", body)
        if mm:
            out[mm.group(1).strip()] = body[mm.end():]
    return out


def plan() -> list[dict]:
    cells = []
    for w in WORLDS:
        wid = Path(w).name
        for h in (1, 2):
            for cond in ("no_bridge", "oracle_bridge"):
                for b in BUDGETS_R:
                    for th in (False, True):
                        cells.append({"role": "recipient", "world": w, "world_id": wid, "holdout": h, "condition": cond, "budget": b, "thinking": th})
        for arm in ("D0", "D", "C2"):
            for b in BUDGETS_P:
                for th in (False, True):
                    cells.append({"role": "proposer", "world": w, "world_id": wid, "arm": arm, "budget": b, "thinking": th})
    for c in cells:
        key = json.dumps({k: c[k] for k in sorted(c)}, sort_keys=True)
        c["cell_id"] = "OC_" + hashlib.sha256(key.encode()).hexdigest()[:12].upper()
    cells.sort(key=lambda c: hashlib.sha256(("2026090803:" + c["cell_id"]).encode()).hexdigest())  # fixed pseudo-random order
    for i, c in enumerate(cells, 1):
        c["ordinal"] = i
    return cells


def run_cell(cell: dict, a) -> dict:
    root = OUT / cell["cell_id"]; t0 = time.monotonic(); world = REPO / cell["world"]
    row = {"cell": cell, "started_at": datetime.now(timezone.utc).isoformat(), "model": a.model}
    events = []; usage = {"prompt_tokens": 0, "completion_tokens": 0}; status = "request_limit"; last = None; verified = False
    try:
        meta = load_v3(world, phase="calibration"); ns = meta["roles"]["namespace"]
        if cell["role"] == "recipient":
            record = materialize_evaluator(world, cell["holdout"], cell["condition"], root / "workspace")
            stmt = meta["roles"]["holdout_statements"][cell["holdout"] - 1]
            initial, system, need = render_workspace(record), SYS_R, ("Solution.lean",)
        else:
            record = materialize_production_proposer(world, cell["arm"], root / "workspace")
            initial, system, need = render_production_proposer(record), SYS_P, ("Bridge.lean", "Solution.lean")
        row["model_input_sha256"] = sha(initial.encode())
        messages = [{"role": "system", "content": system}, {"role": "user", "content": initial}]
        deadline = t0 + SESSION_S
        for turn in range(1, MAX_TURNS + 1):
            if time.monotonic() > deadline:
                status = "session_limit"; break
            t1 = time.monotonic()
            if events and events[-1].get("prompt_tokens") is not None and \
                    events[-1]["prompt_tokens"] + (events[-1].get("completion_tokens") or 0) + 400 + cell["budget"] + CONTEXT_MARGIN > a.context:
                status = "context_limit"; break   # the next request would not fit the served context window
            resp = chat(a.base, a.model, messages, cell["budget"], cell["thinking"], a.temperature)
            ch = resp["choices"][0]; msg = ch["message"]; text = msg.get("content") or ""
            u = resp.get("usage", {}); usage["prompt_tokens"] += u.get("prompt_tokens", 0); usage["completion_tokens"] += u.get("completion_tokens", 0)
            events.append({"turn": turn, "finish_reason": ch.get("finish_reason"), "seconds": round(time.monotonic() - t1, 1),
                           "completion_tokens": u.get("completion_tokens"), "prompt_tokens": u.get("prompt_tokens"), "reasoning_chars": len(msg.get("reasoning_content") or ""),
                           "content_chars": len(text), "content_head": text[:400]})
            if ch.get("finish_reason") == "length":
                status = "output_limit"; break   # a truncated response is never a submission (same rule as the Opus runner)
            sub = blocks(text)
            if not all(n in sub for n in need):
                status = "model_stopped" if ch.get("finish_reason") == "stop" else "invalid_output"
                if turn < MAX_TURNS and ch.get("finish_reason") == "stop":
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content": "No complete submission found. Reply with the required fenced block(s), each starting with the `-- FILE:` line."})
                    continue
                break
            messages.append({"role": "assistant", "content": text})
            rev = root / "revisions" / f"{turn:02d}"; rev.mkdir(parents=True, exist_ok=True)
            for n in need:
                (record.path / n).write_text(sub[n]); (rev / n).write_text(sub[n])
            if cell["role"] == "recipient":
                rep = verify_evaluator_solution(record.path, namespace=ns, statement=stmt, bridge_supplied=cell["condition"] != "no_bridge",
                                                timeout_s=VERIFY_S, allowed_axioms=STANDARD_LEAN_AXIOMS)
                last = {"ok": rep.ok, "solution_valid": rep.solution_valid, "errors": rep.errors[:8], "declaration": rep.declaration}
                verified = bool(rep.ok and rep.solution_valid); fb = {"solved": verified, "errors": rep.errors[:8]}
            else:
                rep = verify_production(record, namespace=ns, timeout_s=VERIFY_S)
                last = {"bridge": asdict(rep.bridge) | {"stdout": "", "stderr": ""}, "visible": asdict(rep.visible) | {"stdout": "", "stderr": ""}}
                verified = bool(rep.bridge.valid and rep.visible.valid); fb = rep.feedback()
            events[-1]["verdict"] = fb
            if verified:
                status = "verified"; break
            messages.append({"role": "user", "content": "Checker verdict: " + json.dumps(fb) + "\nRevise and resubmit the complete file(s)."})
    except Exception as exc:  # noqa: BLE001
        status = "infrastructure_failure"; row["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    row.update(status=status, verified=verified, last_verification=last, events=events, usage=usage,
               elapsed_seconds=round(time.monotonic() - t0, 1), turns=len(events))
    if cell["role"] == "proposer" and last and last.get("bridge", {}).get("status") == "valid":
        row["bridge_valid"] = True; row["bridge_sha256"] = sha((root / "workspace/Bridge.lean").read_bytes())
    else:
        row["bridge_valid"] = False if cell["role"] == "proposer" else None
    root.mkdir(parents=True, exist_ok=True); (root / "result.json").write_text(json.dumps(row, indent=1, ensure_ascii=False, default=str) + "\n")
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:18000/v1"); ap.add_argument("--model", default="Qwen/Qwen3.8-27B")
    ap.add_argument("--temperature", type=float, default=0.6); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--only", default="", help="comma-separated cell ids")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--context", type=int, default=65536, help="served max-model-len; sessions stop with context_limit before overflowing it")
    ap.add_argument("--retry-infrastructure", action="store_true", help="re-run cells whose result was an infrastructure failure (trace kept aside)")
    a = ap.parse_args()
    cells = plan(); OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps({"created": datetime.now(timezone.utc).isoformat(), "model": a.model, "temperature": a.temperature,
                                               "max_turns": MAX_TURNS, "session_s": SESSION_S, "cells": cells}, indent=1) + "\n")
    if a.plan_only:
        print(len(cells), "cells;", sum(c["role"] == "recipient" for c in cells), "recipients,", sum(c["role"] == "proposer" for c in cells), "proposers"); return
    if a.retry_infrastructure:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); moved = []
        for c in cells:
            rp = OUT / c["cell_id"] / "result.json"
            if rp.exists() and json.loads(rp.read_text()).get("status") == "infrastructure_failure":
                (OUT / c["cell_id"]).rename(OUT / f"{c['cell_id']}.failed.{stamp}"); moved.append(c["cell_id"])
        with (OUT / "restarts.jsonl").open("a") as h: h.write(json.dumps({"at": stamp, "moved_aside": moved}) + "\n")
        print(f"retry: {len(moved)} infrastructure failures moved aside")
    pending = [c for c in cells if not (OUT / c["cell_id"] / "result.json").exists()]
    if a.only: pending = [c for c in pending if c["cell_id"] in a.only.split(",")]
    if a.limit: pending = pending[: a.limit]
    log = OUT / "launcher.jsonl"; halt = False
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {}; queue = list(pending)
        def admit():
            while queue and len(futs) < a.workers and not halt:
                c = queue.pop(0); futs[ex.submit(run_cell, c, a)] = c
        admit()
        while futs:
            f = next(as_completed(list(futs))); futs.pop(f); r = f.result(); c = r["cell"]
            s = {"cell_id": c["cell_id"], "role": c["role"], "world": c["world_id"][:6], "holdout": c.get("holdout"), "arm": c.get("arm"), "cond": c.get("condition"),
                 "budget": c["budget"], "thinking": c["thinking"], "status": r["status"], "verified": r["verified"], "bridge_valid": r.get("bridge_valid"),
                 "turns": r["turns"], "completion_tokens": r["usage"]["completion_tokens"], "elapsed": r["elapsed_seconds"], "error": r.get("error"),
                 "at": datetime.now(timezone.utc).isoformat()}
            with log.open("a") as h: h.write(json.dumps(s) + "\n")
            print(json.dumps(s), flush=True)
            if r["status"] == "infrastructure_failure" and "HTTP Error 5" in str(r.get("error", "")) or "Connection refused" in str(r.get("error", "")):
                halt = True; print("HALT: server unreachable")
            admit()
    print("done", len(pending), "cells")


if __name__ == "__main__":
    main()
