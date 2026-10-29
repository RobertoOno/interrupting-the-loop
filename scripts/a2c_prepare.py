#!/usr/bin/env python3
"""A2 consolidation — training data in the EXACT prover format of the test sessions (docs/A2_CONSOLIDACAO_V1.md).

  render  --train-ids runs/a2/a2c_train_ids.txt --out docs/a2c_data      -> p1.jsonl (E+L5 curated skeleton), p2.jsonl (all six
          steps), p3.jsonl (syntax control: same worlds and header, a NON-inductive target: the moves are pairwise inverses,
          proved by cases/simp/omega without measure, step lemma or bridge), manifest.json (SHA-256 of every example)
  verify  --out docs/a2c_data [--workers 6]  -> every p1/p2 completion goes through extract_prover_solution + the real checker
          (must be accepted); every p3 completion is compiled standalone in a staged workspace (must compile with no sorry)

Each JSONL row: {"instance","step","arm","prompt","completion","sha256"}; prompt = render_prover_prompt of the `none` workspace
(what the held-out sessions receive), completion = the whole Lean file the prover is expected to answer (header, definitions,
auxiliary lemmas, theorem with proof), no fences. Nothing here calls a model.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
from creative_machine.formal_routes import ladder_runner_v1 as R  # noqa: E402
from creative_machine.formal_routes import openai_session_v1 as O  # noqa: E402

STEPS6 = ["L1", "L2", "L3", "L4", "L5", "E"]
INVERSE = {"L1": 2, "L2": 3, "L3": 3, "L4": 2, "L5": 2, "E": 2}   # index of the move that inverts move1 in each schema


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def prompt_for(world_dir: Path) -> tuple[str, dict]:
    with tempfile.TemporaryDirectory(prefix="a2c-") as tmp:
        rec = R.materialize_ladder(world_dir, "none", Path(tmp) / "w")
        return O.render_prover_prompt(rec), O.world_context(rec.path)


def form_completion(w: L.StepWorld, ctx: dict) -> str:
    """The curated skeleton as the prover would write it: header, definitions, measure + step lemma + bridge, theorem."""
    return (O.PROVER_HEADER + "\n" + ctx["definitions"] + "\n" + L._measure_block(w, w.fields, "bridge") + "\n"
            + f"theorem evaluation_solution : {ctx['statement']} := by\n" + L._solution_body(w, "bridge"))


def control_statement(step: str) -> str:
    return f"∀ s : State, move{INVERSE[step]} (move1 s) = s"


def control_completion(step: str, ctx: dict) -> str:
    k = INVERSE[step]
    return (O.PROVER_HEADER + "\n" + ctx["definitions"] + "\n"
            + f"theorem evaluation_solution : {control_statement(step)} := by\n  intro s\n  cases s\n  simp [move1, move{k}]\n  <;> omega\n")


def render(train_ids: list[str], out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows = {"p1": [], "p2": [], "p3": []}
    for inst in train_ids:
        for step in STEPS6:
            d = ROOT / "worlds/ladder" / inst / step
            meta = L.load_step(d); w = L.make_step(meta["seed_label"], step)
            prompt, ctx = prompt_for(d)
            form = form_completion(w, ctx); ctrl = control_completion(step, ctx)
            base = {"instance": inst, "step": step, "prompt": prompt}
            if step in ("L5", "E"):
                rows["p1"].append({**base, "arm": "p1", "completion": form, "sha256": sha(prompt + form)})
            rows["p2"].append({**base, "arm": "p2", "completion": form, "sha256": sha(prompt + form)})
            rows["p3"].append({**base, "arm": "p3", "completion": ctrl, "sha256": sha(prompt + ctrl)})
    manifest = {"train_instances": train_ids, "counts": {k: len(v) for k, v in rows.items()}, "files": {}}
    for arm, rs in rows.items():
        p = out / f"{arm}.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs), encoding="utf-8")
        manifest["files"][f"{arm}.jsonl"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def _check_form(row: dict) -> dict:
    from creative_machine.formal_routes.submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
    d = ROOT / "worlds/ladder" / row["instance"] / row["step"]
    with tempfile.TemporaryDirectory(prefix="a2c-chk-") as tmp:
        rec = R.materialize_ladder(d, "none", Path(tmp) / "w"); ctx = O.world_context(rec.path)
        src, found, why = O.extract_prover_solution("```lean4\n" + row["completion"] + "```", ctx)
        if src is None:
            return {"ok": False, "why": why}
        (rec.path / "Solution.lean").write_text(src)
        rep = verify_evaluator_solution(rec.path, namespace=ctx["namespace"], statement=L.STATEMENT, bridge_supplied=False, timeout_s=600, allowed_axioms=STANDARD_LEAN_AXIOMS)
        return {"ok": rep.ok, "why": "; ".join(rep.errors)[:300]}


def _check_control(row: dict) -> dict:
    """Standalone compile: the control target is not LadderStatement, so it goes to `lake env lean`, not the checker."""
    from creative_machine.formal_routes.submission import attach_shared_lake
    d = ROOT / "worlds/ladder" / row["instance"] / row["step"]
    with tempfile.TemporaryDirectory(prefix="a2c-ctl-") as tmp:
        st = Path(tmp) / "w"; st.mkdir()
        for rel in ("lakefile.toml", "lean-toolchain", "World/Base.lean", "World/ChallengeEvaluation.lean"):
            (st / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(d / rel, st / rel)
        attach_shared_lake(st)
        ctx = O.world_context(st)
        src, found, why = O.extract_prover_solution("```lean4\n" + row["completion"] + "```", ctx)
        if src is None:
            return {"ok": False, "why": why}
        (st / "Control.lean").write_text(src + f"\n#print axioms {ctx['namespace']}.evaluation_solution\n")
        b = subprocess.run(["lake", "build", "World.ChallengeEvaluation"], cwd=st, capture_output=True, text=True, timeout=600)
        if b.returncode != 0:
            return {"ok": False, "why": "build: " + (b.stderr + b.stdout)[-300:]}
        r = subprocess.run(["lake", "env", "lean", "Control.lean"], cwd=st, capture_output=True, text=True, timeout=600)
        txt = r.stdout + r.stderr
        return {"ok": r.returncode == 0 and "sorryAx" not in txt and "error" not in txt.lower(), "why": txt[-300:]}


def verify(out: Path, workers: int) -> dict:
    rows = []
    for arm in ("p1", "p2", "p3"):
        rows += [json.loads(l) for l in (out / f"{arm}.jsonl").read_text().splitlines()]
    seen = set(); todo = []
    for r in rows:   # p1 rows duplicate p2 rows: check each (instance, step, completion) once
        k = (r["instance"], r["step"], r["arm"] == "p3")
        if k not in seen:
            seen.add(k); todo.append(r)
    results = {}; bad = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_check_control if r["arm"] == "p3" else _check_form, r): r for r in todo}
        for f in as_completed(futs):
            r = futs[f]; res = f.result(); key = f"{r['instance']}/{r['step']}/{'control' if r['arm'] == 'p3' else 'form'}"
            results[key] = res
            if not res["ok"]:
                bad.append((key, res["why"]))
            print(json.dumps({"example": key, "ok": res["ok"]}), flush=True)
    summary = {"checked": len(results), "ok": sum(1 for v in results.values() if v["ok"]), "bad": bad[:20]}
    (out / "verification.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--train-ids", type=Path, required=True); r.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("verify"); v.add_argument("--out", type=Path, required=True); v.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    if a.cmd == "render":
        ids = [x.strip() for x in a.train_ids.read_text().splitlines() if x.strip()]
        print(json.dumps(render(ids, a.out)["counts"]))
    else:
        print(json.dumps(verify(a.out, a.workers)))


if __name__ == "__main__":
    main()
