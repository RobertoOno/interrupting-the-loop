#!/usr/bin/env python3
"""Programa 2 stage 2 — pick the top-K transplants per arm from stage 1 as seed programs
(pre-registered: family exits first, then theta). Writes runs/p2/<run>_seeds/<arm>_<model>/<k>.py
and a manifest. Run once, after the single read of stage 1.

    python scripts/p2_pick_seeds.py --run stage1 --top 5
"""
import argparse, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXIT_T = 1.10


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--run", default="stage1"); ap.add_argument("--top", type=int, default=5); a = ap.parse_args()
    run = ROOT / "runs/p2" / a.run; out = ROOT / "runs/p2" / f"{a.run}_seeds"; manifest = []
    for f in sorted(run.glob("*.jsonl")):
        rows = [json.loads(l) for l in f.read_text().splitlines()]
        rc = run / f"{f.stem}.reclass.json"; over = json.loads(rc.read_text()) if rc.exists() else {}
        for r in rows:
            k = f"{r['entry']}|{r['attempt']}"
            if k in over and over[k]: r["family"] = over[k]["family"]
        valid = [r for r in rows if r.get("ok") and r.get("score") is not None and r.get("code")]
        best_per_entry = {}
        for r in valid:
            e = r["entry"]
            if e not in best_per_entry or r["score"] > best_per_entry[e]["score"]:
                best_per_entry[e] = r
        ranked = sorted(best_per_entry.values(), key=lambda r: (-(r["score"] >= EXIT_T and r.get("family") not in (None, "F0")), -r["score"]))
        d = out / f.stem; d.mkdir(parents=True, exist_ok=True)
        for k, r in enumerate(ranked[: a.top], 1):
            (d / f"{k}.py").write_text(r["code"])
            manifest.append({"arm": f.stem, "k": k, "entry": r["entry"], "score": r["score"], "family": r.get("family"), "exit": bool(r["score"] >= EXIT_T and r.get("family") not in (None, "F0"))})
            print(f"{f.stem:10s} {k} {r['score']:.5f} {r.get('family')} exit={manifest[-1]['exit']} <- {r['entry']}")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
