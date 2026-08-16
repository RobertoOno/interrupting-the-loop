#!/usr/bin/env python3
"""Re-judge the definitive run's windows on three INDEPENDENT dimensions —
surprise / connection / coherence — with no geometric mean. Tests reading
(3): does the anti-probable drift buy surprise that the connection-only
rubric could not see?

    AWS_PROFILE=main-account python scripts/dream_rejudge_surprise.py runs/dream_def --k 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from creative_machine.blend import BedrockClient, judge_surprise  # noqa: E402
from creative_machine.stats import bootstrap_diff_ci  # noqa: E402
from dream_rejudge import CONDITIONS, windows_of  # noqa: E402

DIMS = ("surprise", "connection", "coherence")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--judge", default="anthropic.claude-opus-5")
    p.add_argument("--max-windows-per-cell", type=int, default=6)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer  # tokenizer only: never materialize the weights here
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    client = BedrockClient(aws_region=args.region)

    items = []
    for d in sorted(x for x in args.run_dir.iterdir() if x.is_dir() and (x / "run.json").exists()):
        cond = d.name.split("_", 1)[1]
        wins = windows_of(d, tokenizer, 160, 600)
        # cap per (cell, kind), evenly spread over the stream: a cell may carry
        # both salience-event windows and uniform 'clock'/'cut' review points
        by_kind: dict[str, list] = {}
        for w in wins:
            by_kind.setdefault(w["kind"], []).append(w)
        for kind, ws in by_kind.items():
            if len(ws) > args.max_windows_per_cell:
                idx = np.linspace(0, len(ws) - 1, args.max_windows_per_cell).round().astype(int)
                ws = [ws[i] for i in idx]
            for w in ws:
                items.append({"cell": d.name, "cond": cond, **w})
    print(f"{len(items)} windows x k={args.k}, judge {args.judge}", flush=True)

    out_path = args.run_dir / "rejudge_surprise.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {(r["cell"], r["step"]) for r in results}
    for it in items:
        if (it["cell"], it["step"]) in done:
            continue
        vs = []
        for _ in range(args.k):
            try:
                vs.append(judge_surprise(client, args.judge, it["window"], it["earlier"]))
            except Exception:
                pass
        rec = {"cell": it["cell"], "cond": it["cond"], "step": it["step"], "kind": it["kind"], "k": len(vs)}
        for dim in DIMS:
            vals = [v[dim] for v in vs]
            rec[dim] = statistics.median(vals) if vals else None
            rec[dim + "_spread"] = (max(vals) - min(vals)) if vals else None
        rec["notes"] = [v.get("note", "") for v in vs[:2]]
        results.append(rec)
        print(f"{it['cell']:<10} step {it['step']:>5}  S {rec['surprise']}  C {rec['connection']}  H {rec['coherence']}", flush=True)
        out_path.write_text(json.dumps(results, indent=2))

    print("\n== resolution (median intra-window spread) ==")
    for dim in DIMS:
        sp = [r[dim + "_spread"] for r in results if r.get(dim + "_spread") is not None]
        print(f"  {dim:<11} mean spread {np.mean(sp):.2f}")
    print("\n== per condition x window kind (unit = window, median of k) ==")
    keys = sorted({(r["cond"], r["kind"]) for r in results})
    print(f"  {'cond':<14} {'kind':<12} {'n':>3}  " + "  ".join(f"{d:>11}" for d in DIMS))
    for cond, kind in keys:
        rs = [r for r in results if r["cond"] == cond and r["kind"] == kind]
        line = f"  {cond:<14} {kind:<12} {len(rs):>3}  "
        for dim in DIMS:
            v = [r[dim] for r in rs if r.get(dim) is not None]
            line += f"  {np.mean(v):5.2f}±{np.std(v):4.2f}" if v else "        —  "
        print(line)
    if all(any(r["cond"] == c for r in results) for c in CONDITIONS):
        for dim in DIMS:
            by = {c: [r[dim] for r in results if r["cond"] == c and r.get(dim) is not None] for c in CONDITIONS}
            for c in ("plain", "clock"):
                if by["none"] and by[c]:
                    lo, hi = bootstrap_diff_ci(by["none"], by[c])
                    print(f"  {dim} none-{c} [{lo:+.2f},{hi:+.2f}]{'*' if lo > 0 or hi < 0 else ''}")
    # top windows by surprise*coherence, to read
    print("\n== top 5 windows by surprise (coherence >= 5) ==")
    top = sorted((r for r in results if (r.get("coherence") or 0) >= 5), key=lambda r: -(r.get("surprise") or 0))[:5]
    for r in top:
        print(f"  {r['cell']:<10} step {r['step']:>5}  S {r['surprise']} C {r['connection']} H {r['coherence']}  — {r['notes'][0][:100]}")
    print(f"tokens: {client.usage}")


if __name__ == "__main__":
    main()
