#!/usr/bin/env python3
"""Measure the ruler, then use it: re-judge every reviewed window of a
definitive run with k judgments per window and one or more judge models,
blind to condition. Reports (1) intra-window variance per judge — the
instrument's resolution — and (2) per-condition continuous scores with
bootstrap CIs, using the median-of-k as the unit.

    AWS_PROFILE=main-account python scripts/dream_rejudge.py runs/dream_def --k 5 \
        --judges anthropic.claude-opus-5 anthropic.claude-sonnet-5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from creative_machine.blend import BedrockClient, judge_reverie  # noqa: E402
from creative_machine.stats import bootstrap_diff_ci  # noqa: E402

CONDITIONS = ("none", "plain", "clock")


def windows_of(cell_dir: Path, tokenizer, review_tokens: int, earlier_tokens: int) -> list[dict]:
    """Recut the reviewed windows at the judged events. Exact when the cell
    has tokens.json (the stream's ids + per-event positions); otherwise
    re-encode text.txt and cut at the event step (older cells; positions
    drift by the injected text, a few tokens per interruption)."""
    run = json.loads((cell_dir / "run.json").read_text())
    seed = run["seed"]
    tok_path = cell_dir / "tokens.json"
    if tok_path.exists():
        ids = json.loads(tok_path.read_text())["ids"]
        exact = True
    else:
        text = (cell_dir / "text.txt").read_text()
        gen = text[len(seed):] if text.startswith(seed) else text
        ids = tokenizer.encode(gen, add_special_tokens=False)
        exact = False
    out = []
    for ev in run["events"]:
        if not ev.get("judged"):
            continue
        step = ev["step"]
        end = min(ev["pos"] if (exact and "pos" in ev) else step, len(ids))
        w_ids = ids[max(0, end - review_tokens):end]
        e_ids = ids[max(0, end - review_tokens - earlier_tokens): max(0, end - review_tokens)]
        out.append({
            "step": step, "kind": ev["kind"],
            "window": tokenizer.decode(w_ids),
            "earlier": tokenizer.decode(e_ids) if e_ids else seed,
        })
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--judges", nargs="+", default=["anthropic.claude-opus-5", "anthropic.claude-sonnet-5"])
    p.add_argument("--max-windows-per-cell", type=int, default=6, help="cap (clock has 30/cell); takes the highest-step spread")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer  # tokenizer only: never materialize the weights here
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    client = BedrockClient(aws_region=args.region)

    cells = sorted(d for d in args.run_dir.iterdir() if d.is_dir() and (d / "run.json").exists())
    items = []
    for d in cells:
        cond = d.name.split("_", 1)[1]
        wins = windows_of(d, tokenizer, 160, 600)
        if len(wins) > args.max_windows_per_cell:  # even spread across the stream
            idx = np.linspace(0, len(wins) - 1, args.max_windows_per_cell).round().astype(int)
            wins = [wins[i] for i in idx]
        for w in wins:
            items.append({"cell": d.name, "cond": cond, **w})
    print(f"{len(items)} windows to judge x {args.k} x {len(args.judges)} judges", flush=True)

    out_path = args.run_dir / "rejudge.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {(r["cell"], r["step"], r["judge"]) for r in results}
    for it in items:
        for jm in args.judges:
            key = (it["cell"], it["step"], jm)
            if key in done:
                continue
            scores, deltas, conns = [], [], []
            for _ in range(args.k):
                try:
                    v = judge_reverie(client, jm, it["window"], it["earlier"])
                    scores.append(v["score"]); deltas.append(v["delta_significance"]); conns.append(v["connects_distant"])
                except Exception as exc:
                    scores.append(None)
            valid = [s for s in scores if s is not None]
            rec = {"cell": it["cell"], "cond": it["cond"], "step": it["step"], "kind": it["kind"], "judge": jm,
                   "scores": scores, "median": statistics.median(valid) if valid else None,
                   "spread": (max(valid) - min(valid)) if valid else None,
                   "delta_median": statistics.median(deltas) if deltas else None,
                   "connects_median": statistics.median(conns) if conns else None}
            results.append(rec)
            print(f"{it['cell']:<10} step {it['step']:>5} {jm.split('.')[-1]:<16} scores {[round(s,1) if s is not None else None for s in scores]}", flush=True)
            out_path.write_text(json.dumps(results, indent=2))

    print("\n== instrument resolution (intra-window spread of k scores) ==")
    for jm in args.judges:
        sp = [r["spread"] for r in results if r["judge"] == jm and r["spread"] is not None]
        sd = [np.std([s for s in r["scores"] if s is not None]) for r in results if r["judge"] == jm and r["median"] is not None]
        print(f"  {jm:<28} windows {len(sp):>3}  mean spread {np.mean(sp):.2f}  mean within-sd {np.mean(sd):.2f}")
    print("\n== per condition (median-of-k per window; unit = window) ==")
    for jm in args.judges:
        print(f"  judge {jm}")
        by = {c: [r["median"] for r in results if r["judge"] == jm and r["cond"] == c and r["median"] is not None] for c in CONDITIONS}
        for c in CONDITIONS:
            v = by[c]
            if v:
                ci = ""
                if c != "none" and by["none"]:
                    lo, hi = bootstrap_diff_ci(by["none"], v)
                    ci = f"  none-{c} CI [{lo:+.2f}, {hi:+.2f}]"
                print(f"    {c:<6} n={len(v):>3} mean {np.mean(v):.2f}  max {max(v):.2f}  >=4: {sum(1 for x in v if x >= 4)}{ci}")
    print(f"tokens: {client.usage}")


if __name__ == "__main__":
    main()
