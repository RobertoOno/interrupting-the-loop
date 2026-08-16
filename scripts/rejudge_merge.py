#!/usr/bin/env python3
"""Coverage report and merge for a two-worker rejudge: how many of the run's
review windows are judged in rejudge_surprise.json ∪ rejudge_surprise_w2.json,
and (with --merge) fold w2 into the main file, deduplicated by (cell, step).

    python scripts/rejudge_merge.py runs/dream_fam8b [--merge] [--tokenizer-model ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dream_rejudge import windows_of  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--merge", action="store_true")
    p.add_argument("--max-windows-per-cell", type=int, default=6)
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    args = p.parse_args()
    from mlx_lm.utils import load_tokenizer
    tok = load_tokenizer(Path(args.tokenizer_model).expanduser())
    keys = set()
    for d in sorted(x for x in args.run_dir.iterdir() if x.is_dir() and (x / "run.json").exists()):
        by_kind: dict[str, list] = {}
        for w in windows_of(d, tok, 160, 600):
            by_kind.setdefault(w["kind"], []).append(w)
        for kind, ws in by_kind.items():
            if len(ws) > args.max_windows_per_cell:
                idx = np.linspace(0, len(ws) - 1, args.max_windows_per_cell).round().astype(int)
                ws = [ws[i] for i in idx]
            for w in ws:
                keys.add((d.name, w["step"]))
    main_p, w2_p = args.run_dir / "rejudge_surprise.json", args.run_dir / "rejudge_surprise_w2.json"
    main = json.loads(main_p.read_text()) if main_p.exists() else []
    w2 = json.loads(w2_p.read_text()) if w2_p.exists() else []
    done_main = {(r["cell"], r["step"]) for r in main}
    done_w2 = {(r["cell"], r["step"]) for r in w2}
    union = done_main | done_w2
    print(f"windows: {len(keys)} total; main {len(done_main)}, w2 {len(done_w2)}, union {len(union & keys)} "
          f"({len(keys - union)} missing)")
    if args.merge:
        merged = list(main)
        for r in w2:
            if (r["cell"], r["step"]) not in done_main:
                merged.append(r)
        main_p.write_text(json.dumps(merged, indent=2))
        print(f"merged -> {main_p} ({len(merged)} records)")


if __name__ == "__main__":
    main()
