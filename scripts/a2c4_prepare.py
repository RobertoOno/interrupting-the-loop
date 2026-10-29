#!/usr/bin/env python3
"""A2 sem curador, ITERATION 2 — cumulative training data, no selection (docs/A2_SEM_CURADOR_ITER2_V1.md).

  render  --prod-run runs/a2c4/a2c4_prod_v1 --prior docs/a2c3_data/own.jsonl --curated docs/a2c2_data/p2.jsonl --out docs/a2c4_data
          own.jsonl  : the prior own rows (iteration 1, byte-identical) + one row per iteration-2 production cell whose final submission
                       the verifier accepted, rendered exactly as in scripts/a2c3_prepare.py (header + world definitions + the verified
                       body the model wrote). No edits, no dedup, no ordering.
          curm.jsonl : the CURATED rows of docs/a2c2_data/p2.jsonl for exactly the same (instance, step) cells, prior and new.
          manifest.json: yield of the new production per step, n_prior, n_new, n_own, gate (n_new >= MIN_NEW), SHA-256 of the files.
  verify  --out docs/a2c4_data [--workers 6]   -> every own/curm row goes through extract_prover_solution + the real checker
          (scripts/a2c3_prepare.verify); verification.json (summary.checked == summary.ok is the data gate).
Nothing here calls a model.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import openai_session_v1 as O  # noqa: E402
from a2c_prepare import prompt_for, sha  # noqa: E402
from a2c3_prepare import accepted_source, body_of, verify  # noqa: E402

MIN_NEW = 12


def render(prod_run: Path, prior: Path, curated: Path, out: Path, min_new: int = MIN_NEW) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cur = {}
    for line in curated.read_text().splitlines():
        if line.strip():
            r = json.loads(line); cur[(r["instance"], r["step"])] = r
    own = [json.loads(l) for l in prior.read_text().splitlines() if l.strip()]
    n_prior = len(own); new, per_step, solved = [], {}, []
    for cell in sorted(d for d in prod_run.iterdir() if d.is_dir() and ".failed" not in d.name):
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
        prompt, ctx = prompt_for(ROOT / "worlds/ladder" / inst / step)
        completion = O.PROVER_HEADER + "\n" + ctx["definitions"] + "\n" + body_of(src)
        new.append({"instance": inst, "step": step, "arm": "own", "prompt": prompt, "completion": completion, "sha256": sha(prompt + completion), "source_cell": cell.name, "iteration": 2})
    own = own + new
    curm = []
    for r in own:
        c = cur.get((r["instance"], r["step"]))
        if c is None:
            raise SystemExit(f"no curated row for {r['instance']}/{r['step']}")
        curm.append({"instance": r["instance"], "step": r["step"], "arm": "curm", "prompt": c["prompt"], "completion": c["completion"], "sha256": sha(c["prompt"] + c["completion"]),
                     "source_cell": r.get("source_cell"), "iteration": r.get("iteration", 1)})
    manifest = {"production_run": str(prod_run), "prior": str(prior), "yield_new": {s: f"{v[1]}/{v[0]}" for s, v in sorted(per_step.items())}, "n_prior": n_prior, "n_new": len(new),
                "n_own": len(own), "min_new": min_new, "gate_passed": len(new) >= min_new, "solved_cells_new": solved, "counts": {"own": len(own), "curm": len(curm)}, "files": {}}
    for arm, rows in (("own", own), ("curm", curm)):
        p = out / f"{arm}.jsonl"; p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
        manifest["files"][f"{arm}.jsonl"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--prod-run", type=Path, required=True); r.add_argument("--prior", type=Path, required=True)
    r.add_argument("--curated", type=Path, default=ROOT / "docs/a2c2_data/p2.jsonl"); r.add_argument("--out", type=Path, required=True); r.add_argument("--min-new", type=int, default=MIN_NEW)
    v = sub.add_parser("verify"); v.add_argument("--out", type=Path, required=True); v.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    if a.cmd == "render":
        m = render(a.prod_run, a.prior, a.curated, a.out, a.min_new); print(json.dumps({k: m[k] for k in ("yield_new", "n_prior", "n_new", "n_own", "gate_passed", "counts")}))
    else:
        print(json.dumps(verify(a.out, a.workers)))


if __name__ == "__main__":
    main()
