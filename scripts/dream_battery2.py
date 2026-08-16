#!/usr/bin/env python3
"""Battery 2 — what is the interruption made of? And does it hold on a second
generator family? Seeds x conditions, resumable, overnight-safe, no judge in
the loop (windows are judged offline by dream_rejudge_surprise.py).

    python scripts/dream_battery2.py --battery b2 --out runs/dream_b2
    python scripts/dream_battery2.py --battery fam8b --out runs/dream_fam8b \
        --model ~/models/mlx/Qwen3-8B-Base-8bit

Conditions (all λ=0, bridge=0, no forgetting):
  bare_habit    bare + the scaffold's habituation only, no interruption   [confound control]
  clock_reenc   clock 150, inject a return-to-the-premise stitch          [content]
  clock_premise clock 150, inject the opening line itself                 [content]
  clock_self    clock 150, inject a window of the stream's own past       [content]
  sal_reenc     salience-timed re-encounter (event injects the stitch)    [timing]
  clock75/300/600  neutral subject change at other frequencies            [frequency]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))
from dream_definitive import SEEDS, thermal  # noqa: E402

BATTERIES = {
    # name -> (control, extra args)
    "b2": [
        ("bare_habit", "bare_habit", []),
        ("clock_reenc", "clock_reenc", []),
        ("clock_premise", "clock_premise", []),
        ("clock_self", "clock_self", []),
        ("sal_reenc", "sal_reenc", []),
        ("clock75", "bare_reseed", ["--clock-every", "75"]),
        ("clock300", "bare_reseed", ["--clock-every", "300"]),
        ("clock600", "bare_reseed", ["--clock-every", "600"]),
    ],
    # second generator family: the four conditions that carry the argument
    "fam8b": [
        ("bare", "bare", []),
        ("bare_habit", "bare_habit", []),
        ("bare_reseed", "bare_reseed", []),
        ("scaffold0", "scaffold0", []),
    ],
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--battery", choices=sorted(BATTERIES), required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--tokens", type=int, default=4500)
    p.add_argument("--seeds", type=int, default=len(SEEDS))
    p.add_argument("--review-clock", type=int, default=150)
    p.add_argument("--only", nargs="*", default=None, help="subset of condition names")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    progress = args.out / "progress.log"

    def log(msg: str) -> None:
        line = f"{datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        with progress.open("a") as f:
            f.write(line + "\n")

    conds = [c for c in BATTERIES[args.battery] if not args.only or c[0] in args.only]
    # condition-major order: the confound control finishes first and can be judged early
    cells = [(si, c) for c in conds for si in range(args.seeds)]
    log(f"battery {args.battery}: {len(cells)} cells ({args.seeds} seeds x {len(conds)} conditions), "
        f"{args.tokens} tokens, model {args.model}")
    for si, (name, control, extra) in cells:
        cell = f"s{si}_{name}"
        cell_dir = args.out / cell
        if (cell_dir / "run.json").exists():
            log(f"skip {cell} (done)")
            continue
        log(f"start {cell} thermal={thermal()}")
        t0 = time.time()
        cmd = [PY, str(ROOT / "scripts/dream_run.py"), "--model", args.model, "--tokens", str(args.tokens),
               "--seed-text", SEEDS[si], "--control", control, "--no-judge",
               "--review-clock", str(args.review_clock), "--out", str(cell_dir), *extra]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
            (args.out / f"{cell}_log.txt").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr[-4000:])
            status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
        log(f"done  {cell} {status} in {(time.time()-t0)/60:.1f} min thermal={thermal()}")
    log(f"battery {args.battery}: finished")


if __name__ == "__main__":
    main()
