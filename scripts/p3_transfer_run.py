#!/usr/bin/env python3
"""Programa 3 — production/transfer diagnostic (26 cells of docs/p3/transfer_design_draft_v1.json),
pre-registered in PLANO 2026-09-08 before any call. Reuses the frozen worlds, the proposer and
recipient session components and the Lean contracts of `creative_machine.formal_routes`; adds only
orchestration: order by ordinal, phase barrier (all proposers before any recipient), concurrency 2,
resume by skipping cells with result.json, cost tally with a hard cap, halt of new admissions on
infrastructure failure. Outputs: runs/p3/transfer_v1/<cell_id>/{workspace,artifacts,result.json}.

    PYTHONPATH=src python scripts/p3_transfer_run.py --dry-run           # materialize + render, no model
    PYTHONPATH=src python scripts/p3_transfer_run.py --phase proposers --limit 1
    PYTHONPATH=src python scripts/p3_transfer_run.py --phase all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from creative_machine.formal_routes.bedrock_runner import make_client  # noqa: E402
from creative_machine.formal_routes.calibration_worlds_v3 import load_v3  # noqa: E402
from creative_machine.formal_routes.production_contract_v1 import (  # noqa: E402
    BridgeArtifact, materialize_production_proposer, render_production_proposer)
from creative_machine.formal_routes.production_runner_v1 import production_config, run_production_session  # noqa: E402
from creative_machine.formal_routes.recipient_contract_v1 import materialize_recipient, render_recipient  # noqa: E402
from creative_machine.formal_routes.recipient_runner_v1 import recipient_config, run_recipient_session  # noqa: E402
from creative_machine.formal_routes.transfer_design_v1 import load_blueprint  # noqa: E402

OUT = REPO / "runs/p3/transfer_v1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def parent_artifact(parent_id: str) -> BridgeArtifact | None:
    d = OUT / parent_id / "artifacts" / "selected_bridge"
    if not (d / "artifact.json").exists():
        return None
    meta = json.loads((d / "artifact.json").read_text()); src = (d / "Bridge.lean").read_bytes()
    if sha(src) != meta["sha256"]:
        raise RuntimeError(f"bridge bytes of {parent_id} do not match their recorded hash")
    return BridgeArtifact(src, meta["sha256"], meta["world_id"], meta["namespace"], meta["declaration"],
                          tuple(tuple(x) for x in meta["base_hashes"]))


def run_cell(cell: dict, dry: bool) -> dict:
    cid = cell["cell_id"]; root = OUT / cid; started = time.monotonic()
    row = {"cell": cell, "started_at": datetime.now(timezone.utc).isoformat(), "dry_run": dry}
    if root.exists() and not (root / "result.json").exists() and not dry:
        # an interrupted session (process killed / machine asleep): keep its partial trace aside, run a fresh one
        aside = root.with_name(f"{cid}.interrupted.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
        root.rename(aside); row["interrupted_trace_moved_to"] = aside.name
    try:
        if cell["role"] == "proposer":
            world = REPO / cell["world"]; namespace = load_v3(world, phase="calibration")["roles"]["namespace"]
            record = materialize_production_proposer(world, cell["arm"], root / "workspace")
            rendered = render_production_proposer(record)
            row.update(namespace=namespace, model_input_sha256=sha(rendered.encode()), copied_hashes=record.copied_hashes)
            if not dry:
                cfg = production_config()
                res = run_production_session(record, namespace=namespace, artifacts=root / "artifacts", config=cfg, client=make_client(cfg))
                row["result"] = res
        else:
            candidate = None
            if cell["bridge_kind"] == "candidate":
                candidate = parent_artifact(cell["parent_proposer_id"])
                if candidate is None:
                    row.update(skipped="no_valid_bridge_from_parent", parent=cell["parent_proposer_id"], elapsed_seconds=time.monotonic() - started)
                    if not dry:
                        save(root / "result.json", row)
                    return row
            record = materialize_recipient(REPO, cid, root / "workspace", candidate=candidate)
            rendered = render_recipient(record, repository=REPO, cell_id=cid, candidate=candidate)
            row.update(model_input_sha256=sha(rendered.encode()), copied_hashes=record.copied_hashes,
                       bridge_sha256=(candidate.sha256 if candidate else record.copied_hashes.get("Bridge.lean")))
            if not dry:
                cfg = recipient_config()
                res = run_recipient_session(record, repository=REPO, cell_id=cid, candidate=candidate,
                                            artifacts=root / "artifacts", config=cfg, client=make_client(cfg))
                row["result"] = res
    except Exception as exc:  # noqa: BLE001
        row.update(launcher_error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()[-3000:])
    row["elapsed_seconds"] = time.monotonic() - started
    if not dry:
        save(root / "result.json", row)   # dry runs leave no result.json: the cell stays pending
    else:
        save(root / "dry_run.json", row)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["proposers", "recipients", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true", help="materialize and render every cell; no model call")
    ap.add_argument("--limit", type=int, default=0, help="run at most N pending cells (smoke)")
    ap.add_argument("--cap-usd", type=float, default=40.0, help="stop admitting new cells above this configured-rate total")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--retry-infrastructure", action="store_true",
                    help="re-run cells whose result was an infrastructure failure, a launcher error or a skip; their traces are kept aside; genuine model outcomes are never re-run")
    a = ap.parse_args()
    bp = load_blueprint(REPO); cells = sorted(bp["cells"], key=lambda c: c["ordinal"])
    phases = [("proposer", [c for c in cells if c["role"] == "proposer"]), ("recipient", [c for c in cells if c["role"] == "recipient"])]
    if a.phase == "proposers": phases = phases[:1]
    if a.phase == "recipients": phases = phases[1:]
    OUT.mkdir(parents=True, exist_ok=True)
    if a.retry_infrastructure and not a.dry_run:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); moved = []
        for c in cells:
            rp = OUT / c["cell_id"] / "result.json"
            if not rp.exists(): continue
            r = json.loads(rp.read_text()); res = r.get("result") or {}
            if res.get("infrastructure_failure") or r.get("launcher_error") or r.get("skipped"):
                aside = OUT / f"{c['cell_id']}.failed.{stamp}"; (OUT / c["cell_id"]).rename(aside); moved.append(c["cell_id"])
        with (OUT / "restarts.jsonl").open("a") as h:
            h.write(json.dumps({"at": stamp, "moved_aside": moved, "reason": "infrastructure failures / skips re-admitted; genuine outcomes kept"}) + "\n")
        print(f"retry: {len(moved)} cells moved aside for a fresh run")
    log = OUT / ("dry_run.jsonl" if a.dry_run else "launcher.jsonl")
    spent = sum(json.loads(l).get("cost", 0.0) for l in log.read_text().splitlines()) if (log.exists() and not a.dry_run) else 0.0
    n_run = 0; halt = False
    for name, group in phases:
        if name == "recipient" and not a.dry_run:
            missing = [c["cell_id"] for c in cells if c["role"] == "proposer" and not (OUT / c["cell_id"] / "result.json").exists()]
            if missing:
                print("phase barrier: proposers not finished:", missing); break
        pending = [c for c in group if not (OUT / c["cell_id"] / "result.json").exists() or a.dry_run]
        if a.dry_run:
            for c in pending:
                if (OUT / c["cell_id"] / "workspace").exists():
                    print("skip (workspace exists):", c["cell_id"]); pending = [x for x in pending if x is not c]
        if a.limit: pending = pending[: max(0, a.limit - n_run)]
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {}; queue = list(pending)
            def admit():
                while queue and len(futs) < a.workers:
                    c = queue.pop(0)
                    if halt or spent > a.cap_usd:
                        print("not admitted:", c["cell_id"], "(halt)" if halt else f"(cap {spent:.2f} > {a.cap_usd})"); continue
                    futs[ex.submit(run_cell, c, a.dry_run)] = c
            admit()
            while futs:
                f = next(as_completed(list(futs))); futs.pop(f)
                row = f.result(); res = row.get("result") or {}; cost = float(res.get("cost_usd_at_configured_rates", 0.0) or 0.0)
                spent += cost; n_run += 1
                if res.get("infrastructure_failure"): halt = True
                summary = {"cell_id": row["cell"]["cell_id"], "role": row["cell"]["role"], "arm": row["cell"]["arm"], "holdout": row["cell"].get("holdout"),
                           "status": res.get("status"), "outcome": res.get("production_outcome") or res.get("recipient_outcome"),
                           "visible_solved": res.get("visible_solved"), "target_solved": res.get("target_solved"), "bridge": bool(res.get("selected_bridge")),
                           "revisions": res.get("revisions"), "cost": cost, "skipped": row.get("skipped"), "error": row.get("launcher_error") or res.get("error"),
                           "elapsed": round(row.get("elapsed_seconds", 0.0), 1), "at": datetime.now(timezone.utc).isoformat()}
                with log.open("a") as h: h.write(json.dumps(summary) + "\n")
                print(json.dumps(summary), flush=True)
                admit()
        if halt: print("HALT: infrastructure failure; no new admissions"); break
    print(f"done: {n_run} cells this invocation; configured-rate total so far US${spent:.2f}")


if __name__ == "__main__":
    main()
