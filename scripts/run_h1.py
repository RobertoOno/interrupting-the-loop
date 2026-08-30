#!/usr/bin/env python3
"""Battery H1-minimal cells (phase 5; pre-registration in PLANO before launch).

Four new state arms on the habituated carrier, next to the PULSO-1/2 arms in
runs/state_pulse (same premises, RNG, protocol, judge — those serve as the
carrier control `habit`, the rival control `inter`, and the ladder context
`pulse`/`pulseG`/`pulseG15`). Resumable."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dream_battery2 import NEW_SEEDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "runs/state_pulse"
PY = str(ROOT / ".venv/bin/python")

COMMON = ["--op", "pulse", "--layer", "18", "--habit", "--inject-every", "300", "--pulse-len", "32"]
ARMS = {
    # primary vehicle: guarded translation at the next dose rung
    "pulseG20": [*COMMON, "--pulse-op", "translate", "--alpha", "2.0", "--anchor", "--keep-norm"],
    # the rotor: norm-preserving by construction; no anchor (it would undo the rotation)
    "rotor": [*COMMON, "--pulse-op", "rotate", "--alpha", "0.8", "--keep-norm"],
    # H4, the house prediction: state repulsion WITH the premise anchor...
    "repelA": [*COMMON, "--pulse-op", "repel", "--alpha", "1.5", "--anchor"],
    # ...and WITHOUT any guard (the degeneration half of the law)
    "repelN": [*COMMON, "--pulse-op", "repel", "--alpha", "1.5"],
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
print(f"H1: {len(cells)} cells -> {R}", flush=True)
for name, args in cells:
    run(name, args)
print(f"H1-CELLS DONE {time.strftime('%c')}", flush=True)
