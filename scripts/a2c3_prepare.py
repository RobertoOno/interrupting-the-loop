#!/usr/bin/env python3
"""A2 sem curador — training data from the model's OWN verified proofs (docs/A2_SEM_CURADOR_V1.md), no selection.

  render  --prod-run runs/a2c3/a2c3_prod_v1 --curated docs/a2c2_data/p2.jsonl --out docs/a2c3_data
          own.jsonl  : one row per production cell whose final submission the verifier accepted (target_solved); prompt = the prover
                       prompt of the `none` workspace (identical to the curated rows); completion = header + world definitions + the
                       verified body the model wrote (auxiliary lemmas and theorem, taken from the accepted submission, without the
                       namespace wrapper and without the header lines repeated by the transplant). No edits, no dedup, no ordering.
          curm.jsonl : the CURATED rows of docs/a2c2_data/p2.jsonl for exactly the same (instance, step) cells (matched control).
          manifest.json: yield per step, solved cells, gate (>= 24), SHA-256 of the files.
  verify  --out docs/a2c3_data [--workers 6]   -> every own/curm completion goes through extract_prover_solution + the real checker
          (must be accepted), as in scripts/a2c_prepare.py; writes verification.json (summary.checked == summary.ok is the data gate).
Nothing here calls a model.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.formal_routes import openai_session_v1 as O  # noqa: E402
from a2c_prepare import _check_form, prompt_for, sha  # noqa: E402

MIN_YIELD = 24
_DROP = re.compile(r"^\s*(import|namespace|end)\b")


def accepted_source(cell: Path):
    """The source of the LAST verification event whose report was accepted (the session stops at the first valid submission)."""
    ev = cell / "artifacts" / "events.jsonl"
    if not ev.exists():
        return None
    src = None
    for line in ev.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("event") == "verification" and (e.get("report") or {}).get("ok") and (e.get("report") or {}).get("solution_valid"):
            src = e.get("source")
    return src


def body_of(source: str) -> str:
    """The model's body: the transplanted file minus import/namespace/end lines and minus the header lines the transplant repeats."""
    header = {l.strip() for l in O.PROVER_HEADER.splitlines() if l.strip()}
    keep = [l for l in source.splitlines() if not _DROP.match(l) and l.strip() not in header]
    while keep and not keep[0].strip():
        keep.pop(0)
    while keep and not keep[-1].strip():
        keep.pop()
    return "\n".join(keep) + "\n"


def render(prod_run: Path, curated: Path, out: Path, allow_missing: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cur = {}
    for line in curated.read_text().splitlines():
        if line.strip():
            r = json.loads(line); cur[(r["instance"], r["step"])] = r
    own, curm, solved, per_step = [], [], [], {}
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
        own.append({"instance": inst, "step": step, "arm": "own", "prompt": prompt, "completion": completion, "sha256": sha(prompt + completion), "source_cell": cell.name})
        c = cur.get((inst, step))
        if c is None:
            if allow_missing:   # test runs on instances without curated rows only
                continue
            raise SystemExit(f"no curated row for {inst}/{step}")
        curm.append({"instance": inst, "step": step, "arm": "curm", "prompt": c["prompt"], "completion": c["completion"], "sha256": sha(c["prompt"] + c["completion"]), "source_cell": cell.name})
    manifest = {"production_run": str(prod_run), "yield": {s: f"{v[1]}/{v[0]}" for s, v in sorted(per_step.items())}, "n_own": len(own), "min_yield": MIN_YIELD,
                "gate_passed": len(own) >= MIN_YIELD, "solved_cells": solved, "counts": {"own": len(own), "curm": len(curm)}, "files": {}}
    for arm, rows in (("own", own), ("curm", curm)):
        p = out / f"{arm}.jsonl"; p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
        manifest["files"][f"{arm}.jsonl"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def verify(out: Path, workers: int) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    rows = []
    for arm in ("own", "curm"):
        rows += [json.loads(l) for l in (out / f"{arm}.jsonl").read_text().splitlines() if l.strip()]
    results, bad = {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_check_form, r): r for r in rows}
        for f in as_completed(futs):
            r = futs[f]; res = f.result(); key = f"{r['instance']}/{r['step']}/{r['arm']}/{r.get('source_cell', '')}"
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
    r = sub.add_parser("render"); r.add_argument("--prod-run", type=Path, required=True); r.add_argument("--curated", type=Path, default=ROOT / "docs/a2c2_data/p2.jsonl"); r.add_argument("--out", type=Path, required=True); r.add_argument("--allow-missing-curated", action="store_true", help="tests only")
    v = sub.add_parser("verify"); v.add_argument("--out", type=Path, required=True); v.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    if a.cmd == "render":
        m = render(a.prod_run, a.curated, a.out, a.allow_missing_curated); print(json.dumps({k: m[k] for k in ("yield", "n_own", "gate_passed", "counts")}))
    else:
        print(json.dumps(verify(a.out, a.workers)))


if __name__ == "__main__":
    main()
