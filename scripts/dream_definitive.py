#!/usr/bin/env python3
"""The definitive DREAM experiment: seeds x conditions, resumable, overnight-safe.

Runs dream_run.py as a subprocess per cell (one model load each — slower
than sharing, but a crash in one cell cannot take the others down), skips
cells whose run.json already exists (resumable), logs thermal state, and
aggregates at the end.

    AWS_PROFILE=main-account python scripts/dream_definitive.py --out runs/dream_def
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

SEEDS = [
    "She kept a notebook of things that had almost happened.",
    "The map was accurate in every detail except one, and nobody could say which.",
    "Every morning the baker counted the loaves twice, and every morning the count was different.",
    "He had inherited his grandfather's watch and, with it, the habit of arriving early to places that no longer existed.",
    "The river changed its name each time it crossed the border, and the villagers kept all the names.",
]
CONDITIONS = ["none", "plain", "clock"]


def thermal() -> str:
    try:
        out = subprocess.run([PY, str(ROOT / "scripts/thermal_watch.py"), "--once"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return out.split()[-2] if out else "?"
    except Exception:
        return "?"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tokens", type=int, default=4500)
    p.add_argument("--seeds", type=int, default=len(SEEDS))
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    progress = args.out / "progress.log"

    def log(msg: str) -> None:
        line = f"{datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        with progress.open("a") as f:
            f.write(line + "\n")

    cells = [(si, cond) for si in range(args.seeds) for cond in CONDITIONS]
    log(f"definitive: {len(cells)} cells ({args.seeds} seeds x {len(CONDITIONS)} conditions), {args.tokens} tokens each")
    for si, cond in cells:
        name = f"s{si}_{cond}"
        cell_dir = args.out / name
        if (cell_dir / "run.json").exists():
            log(f"skip {name} (done)")
            continue
        log(f"start {name} thermal={thermal()}")
        t0 = time.time()
        cmd = [PY, str(ROOT / "scripts/dream_run.py"), "--tokens", str(args.tokens),
               "--seed-index", str(si), "--control", cond, "--out", str(cell_dir)]
        # dream_run picks seeds from its own list; pass ours via env-free override below
        env_seed = SEEDS[si]
        cmd += ["--seed-text", env_seed]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
            (cell_dir if cell_dir.exists() else args.out).mkdir(parents=True, exist_ok=True)
            (args.out / f"{name}_log.txt").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr[-4000:])
            status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
        log(f"done  {name} {status} in {(time.time()-t0)/60:.1f} min thermal={thermal()}")

    # aggregate
    log("aggregating")
    rows = []
    for si, cond in cells:
        d = args.out / f"s{si}_{cond}"
        if not (d / "run.json").exists():
            continue
        meta = json.loads((d / "run.json").read_text())["summary"]
        ins = json.loads((d / "insights.json").read_text()) if (d / "insights.json").exists() else []
        best_ins = max((i["judgment"].get("score", 0.0) for i in ins), default=0.0)
        rows.append({"seed": si, "cond": cond, **meta, "best_insight": best_ins})
    (args.out / "aggregate.json").write_text(json.dumps(rows, indent=2))
    import numpy as np
    sys.path.insert(0, str(ROOT / "src"))
    from creative_machine.stats import bootstrap_diff_ci
    by = {c: [r for r in rows if r["cond"] == c] for c in CONDITIONS}
    log(f"{'cond':<8} {'n':>2} {'ins/1k mean':>12} {'insights':>9} {'reviews':>8}  CI(ins/1k - none)")
    base = [r["insights_per_1k"] for r in by["none"]]
    for c in CONDITIONS:
        rs = by[c]
        if not rs:
            continue
        v = [r["insights_per_1k"] for r in rs]
        ci = ""
        if c != "none" and base and len(base) > 1 and len(v) > 1:
            lo, hi = bootstrap_diff_ci(v, base)
            ci = f"[{lo:+.3f}, {hi:+.3f}]"
        log(f"{c:<8} {len(rs):>2} {np.mean(v):>12.3f} {sum(r['n_insights'] for r in rs):>9} {sum(r['n_reviews'] for r in rs):>8}  {ci}")
    log("definitive: finished")


if __name__ == "__main__":
    main()
