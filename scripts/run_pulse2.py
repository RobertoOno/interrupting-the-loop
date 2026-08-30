#!/usr/bin/env python3
"""Battery PULSE-2 cells (phase 5; pre-registered PLANO 2026-08-30 morning).

Guards on the pulse: anchor + norm shell during bursts, at alpha 1.0 and 1.5.
Cells land in runs/state_pulse next to the PULSO-1 arms (same premises, RNG,
protocol), which serve as the pre-registered controls. Resumable."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dream_battery2 import NEW_SEEDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "runs/state_pulse"
PY = str(ROOT / ".venv/bin/python")

BASE = ["--op", "pulse", "--layer", "18", "--habit", "--inject-every", "300",
        "--pulse-len", "32", "--anchor", "--keep-norm"]
ARMS = {"pulseG": [*BASE, "--alpha", "1.0"], "pulseG15": [*BASE, "--alpha", "1.5"]}


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
print(f"PULSE-2: {len(cells)} cells -> {R}", flush=True)
for name, args in cells:
    run(name, args)
print(f"PULSE2-CELLS DONE {time.strftime('%c')}", flush=True)
