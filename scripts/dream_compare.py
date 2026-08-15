#!/usr/bin/env python3
"""Aggregate DREAM runs and controls into one comparison table.

Reads run.json + insights.json from each run directory and reports, per
condition: tokens, salience events, reviews, insight candidates per 1k
tokens, best and mean review score. Also re-scores every reviewed window
from the saved logs when available.

    python scripts/dream_compare.py runs/dream6 runs/dream6_plain runs/dream6_clock
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("runs", nargs="+", type=Path)
    args = p.parse_args()

    print(f"{'run':<24} {'tokens':>6} {'events':>6} {'reviews':>7} {'insights':>8} {'ins/1k':>7} {'best':>6} {'reseeds':>7}")
    for r in args.runs:
        meta = json.loads((r / "run.json").read_text())
        s = meta["summary"]
        insights = json.loads((r / "insights.json").read_text()) if (r / "insights.json").exists() else []
        best = max((i["judgment"].get("score", 0.0) for i in insights), default=0.0)
        # best reviewed score including non-passing reviews, from the log if present
        log = r.parent / f"{r.name}_log.txt"
        if log.exists():
            import re
            scores = [float(x) for x in re.findall(r"score ([0-9.]+)", log.read_text())]
            if scores:
                best = max(best, max(scores))
        print(
            f"{r.name:<24} {s['n_tokens']:>6} {s['n_events']:>6} {s['n_reviews']:>7} "
            f"{s['n_insights']:>8} {s['insights_per_1k']:>7.2f} {best:>6.2f} {s.get('n_reseeds', 0):>7}"
        )


if __name__ == "__main__":
    main()
