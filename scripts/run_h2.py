#!/usr/bin/env python3
"""Battery H2 cells (phase 5, confirmatory; pre-registered PLANO 2026-08-29).

140 cells on the 8B Base, 10 confirmatory premises (NEW_SEEDS), fixed concept:
band core {L14, L18, L22} x alpha {0.25, 0.5, 0.75}; dose curve L18 x
{0.1, 1, 1.5}; controls bare and prompt-matched (concept as text every 300).
Resumable: cells with run.json are skipped. Judging and analysis are separate
steps (run_h2.sh chains them)."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dream_battery2 import NEW_SEEDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "runs/state_h2"
PY = str(ROOT / ".venv/bin/python")
CONCEPT = "She kept a notebook of things that had almost happened."


def run(name: str, *args: str) -> None:
    out = R / name
    if (out / "run.json").exists():
        print(f"skip {name}", flush=True)
        return
    cmd = ["caffeinate", "-is", PY, str(ROOT / "scripts/state_inject.py"), "--out", str(out),
           "--max-tokens", "1500", "--temp", "1.0", "--top-p", "0.95", "--rng-seed", "0", *args]
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT)
    print(f"{'ok' if p.returncode == 0 else 'FAIL'} {name} {time.time() - t:.0f}s", flush=True)


cells = []
for i, prem in enumerate(NEW_SEEDS):
    cells.append((f"p{i}_bare", ["--seed-text", prem, "--op", "none"]))
    cells.append((f"p{i}_prompt", ["--seed-text", prem, "--op", "prompt",
                                   "--inject-text", CONCEPT, "--inject-every", "300"]))
    for L in (14, 18, 22):
        for a in ("0.25", "0.5", "0.75"):
            cells.append((f"p{i}_L{L}_a{a}", ["--seed-text", prem, "--op", "translate",
                                              "--layer", str(L), "--alpha", a, "--concept-a", CONCEPT]))
    for a in ("0.1", "1", "1.5"):
        cells.append((f"p{i}_L18_a{a}", ["--seed-text", prem, "--op", "translate",
                                         "--layer", "18", "--alpha", a, "--concept-a", CONCEPT]))

print(f"H2: {len(cells)} cells -> {R}", flush=True)
for name, args in cells:
    run(name, *args)
print(f"H2-CELLS DONE {time.strftime('%c')}", flush=True)
