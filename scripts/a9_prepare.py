#!/usr/bin/env python3
"""A9 — cumulative training data for the third adapter of the loop, no selection (docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md).

  render  --prod-run runs/a8/a8_own2_v1 --prior docs/a2c4_data/own.jsonl --out docs/a9_data
          own3.jsonl : the prior own rows (iterations 1 and 2, byte-identical) + one row per session of the A8 own2 arm whose final
                       submission the verifier accepted (wall families W1..W4, produced with thinking by a2c4-own2 on instances that
                       from now on are TRAINING instances), rendered exactly as in scripts/a2c3_prepare.py: prover prompt of the `none`
                       workspace, completion = header + world definitions + the verified body the model wrote. No edits, no dedup, no
                       ordering, every accepted session kept (up to three per instance).
          manifest.json: yield per family, n_prior, n_new, n_own, gate (n_new >= 12), SHA-256 of the file.
  verify  --out docs/a9_data [--workers 6]   -> every NEW row goes through extract_prover_solution + the real checker; the prior rows are
          compared byte by byte with docs/a2c4_data/own.jsonl, whose 270/270 verification is on record (docs/a2c4_data/verification.json).
Nothing here calls a model.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import ladder_v1 as L  # noqa: E402
from creative_machine.formal_routes import ladder_runner_v1 as R  # noqa: E402
from creative_machine.formal_routes import openai_session_v1 as O  # noqa: E402
from a2c_prepare import prompt_for, sha  # noqa: E402
from a2c3_prepare import accepted_source, body_of  # noqa: E402

MIN_NEW = 12


def world_dir(inst: str, step: str) -> Path:
    return ROOT / ("worlds/walls" if step.startswith("W") else "worlds/ladder") / inst / step


def render(prod_run: Path, prior: Path, out: Path, min_new: int = MIN_NEW) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    prior_lines = [l for l in prior.read_text(encoding="utf-8").splitlines() if l.strip()]
    new, per_step, solved = [], {}, []
    for cell in sorted(d for d in prod_run.iterdir() if d.is_dir() and ".failed" not in d.name and ".interrupted" not in d.name):
        res = cell / "result.json"
        if not res.exists():
            continue
        r = json.load(open(res))["result"]; inst, step = cell.name.split("_")[0], cell.name.split("_")[1]
        per_step.setdefault(step, [0, 0]); per_step[step][0] += 1
        if not r.get("target_solved"):
            continue
        src = accepted_source(cell)
        if src is None:
            raise SystemExit(f"{cell.name}: target_solved but no accepted verification event")
        per_step[step][1] += 1; solved.append(cell.name)
        prompt, ctx = prompt_for(world_dir(inst, step))
        completion = O.PROVER_HEADER + "\n" + ctx["definitions"] + "\n" + body_of(src)
        new.append({"instance": inst, "step": step, "arm": "own", "prompt": prompt, "completion": completion, "sha256": sha(prompt + completion), "source_cell": cell.name, "iteration": 3})
    p = out / "own3.jsonl"
    p.write_text("".join(l + "\n" for l in prior_lines) + "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in new), encoding="utf-8")
    manifest = {"production_run": str(prod_run), "prior": str(prior), "prior_sha256": hashlib.sha256(prior.read_bytes()).hexdigest(), "yield_new": {s: f"{v[1]}/{v[0]}" for s, v in sorted(per_step.items())},
                "n_prior": len(prior_lines), "n_new": len(new), "n_own": len(prior_lines) + len(new), "min_new": min_new, "gate_passed": len(new) >= min_new, "solved_cells_new": solved,
                "training_instances_new": sorted({c.split("_")[0] for c in solved}), "files": {"own3.jsonl": hashlib.sha256(p.read_bytes()).hexdigest()}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def _check_row(row: dict) -> dict:
    from creative_machine.formal_routes.submission import STANDARD_LEAN_AXIOMS, verify_evaluator_solution
    with tempfile.TemporaryDirectory(prefix="a9-chk-") as tmp:
        rec = R.materialize_ladder(world_dir(row["instance"], row["step"]), "none", Path(tmp) / "w"); ctx = O.world_context(rec.path)
        src, found, why = O.extract_prover_solution("```lean4\n" + row["completion"] + "```", ctx)
        if src is None:
            return {"ok": False, "why": why}
        (rec.path / "Solution.lean").write_text(src)
        rep = verify_evaluator_solution(rec.path, namespace=ctx["namespace"], statement=L.STATEMENT, bridge_supplied=False, timeout_s=600, allowed_axioms=STANDARD_LEAN_AXIOMS)
        return {"ok": rep.ok, "why": "; ".join(rep.errors)[:300]}


def verify(out: Path, workers: int, prior: Path) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    lines = [l for l in (out / "own3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    prior_lines = [l for l in prior.read_text(encoding="utf-8").splitlines() if l.strip()]
    identical = lines[: len(prior_lines)] == prior_lines
    rows = [json.loads(l) for l in lines[len(prior_lines):]]
    results, bad = {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_check_row, r): r for r in rows}
        for f in as_completed(futs):
            r = futs[f]; res = f.result(); key = f"{r['instance']}/{r['step']}/{r['source_cell']}"
            results[key] = res
            if not res["ok"]:
                bad.append((key, res["why"]))
            print(json.dumps({"example": key, "ok": res["ok"]}), flush=True)
    pv = json.loads((prior.parent / "verification.json").read_text())["summary"]
    summary = {"checked": len(results), "ok": sum(1 for v in results.values() if v["ok"]), "bad": bad[:20], "prior_rows": len(prior_lines), "prior_byte_identical": identical,
               "prior_verification_on_record": {"file": str((prior.parent / "verification.json").relative_to(ROOT)), "checked": pv["checked"], "ok": pv["ok"]}}
    (out / "verification.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--prod-run", type=Path, required=True); r.add_argument("--prior", type=Path, required=True); r.add_argument("--out", type=Path, required=True)
    v = sub.add_parser("verify"); v.add_argument("--out", type=Path, required=True); v.add_argument("--prior", type=Path, required=True); v.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    if a.cmd == "render":
        m = render(a.prod_run.resolve(), a.prior.resolve(), a.out.resolve()); print(json.dumps({k: m[k] for k in ("yield_new", "n_prior", "n_new", "n_own", "gate_passed")}))
    else:
        print(json.dumps(verify(a.out.resolve(), a.workers, a.prior.resolve())))


if __name__ == "__main__":
    main()
