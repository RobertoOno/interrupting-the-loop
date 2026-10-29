#!/usr/bin/env python3
"""Ablação do gatilho (pre-registered PLANO 2026-09-09 before any call). Yesterday's diagnostic: with a worked
example (relevant or sham) Opus produces a valid bridge 4/4; with the target alone 0/2 (reasons until the output
limit, never submits). Is the trigger the mathematical CONTENT of the example, the FORM of a complete Lean file, or
just an instruction to submit early? Production-only sessions (same proposer protocol, contract and verifier):
  D0  target only (2 more replicates per world)
  T1  target + a worked Lean example from an unrelated domain (arithmetic induction; no invariant, no representation)
  T2  target + a file SKELETON with no mathematics (the two files' shape, trivial bridge, no proof)
  T3  target + one instruction: submit a candidate bridge early and revise after feedback
  T4  target + the KIND of intermediary in words (invariant / representation), no code, no parameters
  T5  T4 + the instruction to FIRST write a complete worked example of that kind on a toy system of its own (two Lean
      files of the submission's shape), then attack the target using that example as its own source (Programa 4:
      can the proposer manufacture the trigger it needs from the words?)
The frozen contract only allows SOURCE.md under the D/C2 allowlist, so T1/T2 workspaces carry the label "C2" in the
runner's input.json; the true arm is recorded here (results.jsonl, ARM.txt) — documented limitation of reuse.

    PYTHONPATH=src python scripts/p3_trigger_ablation.py [--limit N] [--workers 2]     # run
    python scripts/p3_trigger_ablation.py --read                                        # single read
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "runs/p3/trigger_ablation_v1"
WORLDS = ("worlds/calibration/CAL3_I_E87C49876088749B", "worlds/calibration/CAL3_R_F76437525B190ECB")
ARMS = ("D0", "T1", "T2", "T3", "T4", "T5"); REPS = 2   # T4 added 2026-09-09 14:05; T5 added 2026-09-09 (night), both pre-registered before running

FOREIGN = """# Worked example

A separate formal problem and its complete proof.

```lean
import Std

namespace Source

def sumOdd : Nat → Nat
  | 0 => 0
  | n + 1 => sumOdd n + (2 * n + 1)

theorem sumOdd_succ (n : Nat) : sumOdd (n + 1) = sumOdd n + (2 * n + 1) := rfl

theorem sumOdd_sq (n : Nat) : sumOdd n = n * n := by
  induction n with
  | zero => rfl
  | succ k ih =>
    rw [sumOdd_succ, ih]
    have h : (k + 1) * (k + 1) = k * k + (2 * k + 1) := by
      simp [Nat.add_mul, Nat.mul_add, Nat.mul_one, Nat.one_mul]
      omega
    omega

end Source
```
"""

def skeleton(ns: str) -> str:
    return f"""# File skeleton

The shape of the two output files (no mathematics; fill in your own definitions and proofs).

```lean
-- Bridge.lean
import World.Base

namespace {ns}

-- helper definitions and lemmas go here

theorem candidate_bridge : True := trivial   -- replace with the reusable intermediary

end {ns}
```

```lean
-- Solution.lean
import World.ChallengeVisible
import Bridge

namespace {ns}

theorem candidate_solution : VisibleStatement := by
  unfold VisibleStatement
  -- proof using candidate_bridge goes here
  exact ?_

end {ns}
```
"""

KIND_HINT = {  # T4: the KIND of intermediary in words, no code, no parameters
    "CAL3_I_E87C49876088749B": "\nHint: look for a quantity computed from the state that every single step leaves unchanged (an invariant); "
                                "prove it is preserved along any trail, and use it in Bridge.lean.\n",
    "CAL3_R_F76437525B190ECB": "\nHint: look for a change of representation: an action of each mark on a simple object, with an inverse, "
                                "such that related words act identically; prove that, and use it in Bridge.lean.\n",
}
SELF_INSTANTIATE = ("\nMethod: before attacking the target, write a complete worked example of this kind of intermediary on a small "
                    "system of your own invention (not the target's): two Lean files with the shape of the submission (a bridge "
                    "file stating and proving the reusable lemma; a solution file using it), complete and, as far as you can tell, "
                    "correct. Then attack the target, using your own example as the source to imitate.\n")
INSTRUCTION = ("\nStrategy: submit an early check_submission with a candidate Bridge.lean (an invariant, a representation "
               "or another reusable lemma) even before the visible solution is complete; use the checker feedback to revise.\n")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def make_record(world: Path, arm: str, dest: Path, ns: str):
    from creative_machine.formal_routes.production_contract_v1 import materialize_production_proposer
    from creative_machine.formal_routes.workspace import WorkspaceRecord
    base_arm = "D0" if arm in ("D0", "T3", "T4", "T5") else "C2"       # allowlist carrier; the true arm is recorded by this script
    rec = materialize_production_proposer(world, base_arm, dest)
    hashes = dict(rec.copied_hashes)
    if arm == "T1":
        (dest / "SOURCE.md").write_text(FOREIGN); hashes["SOURCE.md"] = sha((dest / "SOURCE.md").read_bytes())
    elif arm == "T2":
        (dest / "SOURCE.md").write_text(skeleton(ns)); hashes["SOURCE.md"] = sha((dest / "SOURCE.md").read_bytes())
    elif arm == "T3":
        t = dest / "TASK.md"; t.write_bytes(t.read_bytes() + INSTRUCTION.encode()); hashes["TASK.md"] = sha(t.read_bytes())
    elif arm == "T4":
        t = dest / "TASK.md"; t.write_bytes(t.read_bytes() + KIND_HINT[rec.world_id].encode()); hashes["TASK.md"] = sha(t.read_bytes())
    elif arm == "T5":
        t = dest / "TASK.md"; t.write_bytes(t.read_bytes() + KIND_HINT[rec.world_id].encode() + SELF_INSTANTIATE.encode()); hashes["TASK.md"] = sha(t.read_bytes())
    return WorkspaceRecord(rec.path, rec.world_id, rec.role, rec.condition, hashes, rec.allowed_outputs)


def cells() -> list[dict]:
    out = []
    for w in WORLDS:
        for arm in ARMS:
            for rep in range(1, REPS + 1):
                cid = "G_" + hashlib.sha256(f"{w}:{arm}:{rep}".encode()).hexdigest()[:10].upper()
                out.append({"cell_id": cid, "world": w, "world_id": Path(w).name, "arm": arm, "rep": rep})
    out.sort(key=lambda c: hashlib.sha256(("2026090901:" + c["cell_id"]).encode()).hexdigest())
    return out


def run_cell(c: dict) -> dict:
    from creative_machine.formal_routes.bedrock_runner import make_client
    from creative_machine.formal_routes.calibration_worlds_v3 import load_v3
    from creative_machine.formal_routes.production_runner_v1 import production_config, run_production_session
    root = OUT / c["cell_id"]; t0 = time.monotonic(); row = {"cell": c, "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        world = REPO / c["world"]; ns = load_v3(world, phase="calibration")["roles"]["namespace"]
        rec = make_record(world, c["arm"], root / "workspace", ns)
        root.mkdir(parents=True, exist_ok=True); (root / "ARM.txt").write_text(c["arm"] + "\n")
        cfg = production_config()
        res = run_production_session(rec, namespace=ns, artifacts=root / "artifacts", config=cfg, client=make_client(cfg))
        row["result"] = res
    except Exception as exc:  # noqa: BLE001
        row["launcher_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    row["elapsed_seconds"] = round(time.monotonic() - t0, 1)
    (root / "result.json").write_text(json.dumps(row, indent=1, ensure_ascii=False, default=str) + "\n")
    return row


def read() -> None:
    rows = {c["cell_id"]: (json.loads((OUT / c["cell_id"] / "result.json").read_text()) if (OUT / c["cell_id"] / "result.json").exists() else None) for c in cells()}
    L = ["# Ablação do gatilho (Opus 5, propositores; leitura única)\n", "| mundo | braço | rep | estado | desfecho | ponte válida | visível | revisões | custo US$ |", "|---|---|---|---|---|---|---|---|---|"]
    tally = {}
    tot = 0.0
    for c in cells():
        r = rows[c["cell_id"]]; res = (r or {}).get("result") or {}; cost = float(res.get("cost_usd_at_configured_rates") or 0); tot += cost
        ok = bool(res.get("selected_bridge")); tally.setdefault(c["arm"], [0, 0]); tally[c["arm"]][0] += ok; tally[c["arm"]][1] += bool(res)
        L.append(f"| {c['world_id'][:6]} | {c['arm']} | {c['rep']} | {res.get('status', 'não rodou' if r is None else (r.get('launcher_error') or '—'))} | {res.get('production_outcome', '—')} | "
                 f"{'sim' if ok else 'não'} | {'sim' if res.get('visible_solved') else 'não'} | {res.get('revisions', '—')} | {cost:.2f} |")
    L.append("\n| braço | pontes válidas / sessões |"); L.append("|---|---|")
    for arm in ARMS: L.append(f"| {arm} | {tally.get(arm, [0, 0])[0]}/{tally.get(arm, [0, 0])[1]} |")
    L.append(f"\nReferência (diagnóstico de 08/09): D 2/2, C2 2/2, D0 0/2. Custo desta ablação: US${tot:.2f}.\n")
    (REPO / "docs/APPENDIX_P3_TRIGGER.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--read", action="store_true"); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.read: read(); return
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "plan.json").write_text(json.dumps(cells(), indent=1) + "\n")
    pending = [c for c in cells() if not (OUT / c["cell_id"] / "result.json").exists()]
    if a.limit: pending = pending[: a.limit]
    log = OUT / "launcher.jsonl"
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(run_cell, c) for c in pending]):
            r = f.result(); res = r.get("result") or {}
            s = {"cell_id": r["cell"]["cell_id"], "world": r["cell"]["world_id"][:6], "arm": r["cell"]["arm"], "rep": r["cell"]["rep"], "status": res.get("status"),
                 "outcome": res.get("production_outcome"), "bridge": bool(res.get("selected_bridge")), "visible": res.get("visible_solved"), "revisions": res.get("revisions"),
                 "cost": res.get("cost_usd_at_configured_rates"), "error": r.get("launcher_error") or res.get("error"), "at": datetime.now(timezone.utc).isoformat()}
            with log.open("a") as h: h.write(json.dumps(s) + "\n")
            print(json.dumps(s), flush=True)
    print("done", len(pending))


if __name__ == "__main__":
    main()
