#!/usr/bin/env python3
"""Battery PULSE cells (phase 5; pre-registered PLANO 2026-08-29 ~23h).

The state transposition of the paper-1 winner: habituated carrier in all
three arms; state-translation BURSTS (32 tokens every 300, rotating kick
directions) vs the verbatim text interruption vs habituated bare.
Resumable: cells with run.json are skipped."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dream_battery2 import NEW_SEEDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "runs/state_pulse"
PY = str(ROOT / ".venv/bin/python")

ARMS = {
    "habit": ["--op", "none", "--habit"],
    "pulse": ["--op", "pulse", "--layer", "18", "--alpha", "1.0", "--habit",
              "--inject-every", "300", "--pulse-len", "32"],
    "inter": ["--op", "prompt", "--inject-rotate", "--habit", "--inject-every", "300"],
}


def run(name: str, args) -> None:
    out = R / name
    if (out / "run.json").exists():
        print(f"skip {name}", flush=True)
        return
    cmd = ["caffeinate", "-is", PY, str(ROOT / "scripts/state_inject.py"), "--out", str(out),
           "--max-tokens", "1500", "--temp", "1.0", "--top-p", "0.95", "--rng-seed", "0", *args]
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT)
    print(f"{'ok' if p.returncode == 0 else 'FAIL'} {name} {time.time() - t:.0f}s", flush=True)


cells = [(f"p{i}_{arm}", ["--seed-text", prem, *flags])
         for i, prem in enumerate(NEW_SEEDS) for arm, flags in ARMS.items()]
print(f"PULSE: {len(cells)} cells -> {R}", flush=True)
for name, args in cells:
    run(name, args)
print(f"PULSE-CELLS DONE {time.strftime('%c')}", flush=True)
