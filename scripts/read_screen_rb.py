#!/usr/bin/env python3
"""Screen RB cheap read (exploratory tier): per arm — valid production,
rediscovery rate against the pass-1 pool (B-CONF none arm), and per-variant
best gaps vs the control. Prints a table; no verdicts, screens decide seats."""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
P1 = ROOT / "runs/state_bconf/none"
R = ROOT / "runs/state_rb"
ARMS = ("ctrl", "rb1", "rb2")


def load_ok(path):
    cands = json.loads((path / "candidates.json").read_text())
    return [c for c in cands.values() if c.get("ok") and c.get("train") is not None]


pool1 = {c["hash"] for c in load_ok(P1) if c["which"] == "train"}
print(f"pool passada-1 (none/train): {len(pool1)} hashes válidos distintos\n")
print(f"{'arm':>5} | {'valid':>5} {'dist':>5} | {'redesc':>7} | {'melhor gap':>11} | finds")
best_by = {}
for arm in ARMS:
    ok = [c for c in load_ok(R / arm) if c["which"] == "train"]
    hashes = {c["hash"] for c in ok}
    redisc = len(hashes & pool1) / max(1, len(hashes))
    gaps = [c["train"] - min(c["bf_train"], c["ff_train"]) for c in ok]
    finds = sum(1 for c in ok if c.get("find"))
    best_by[arm] = {}
    for c in ok:
        g = c["train"] - min(c["bf_train"], c["ff_train"])
        v = c["variant"]
        if v not in best_by[arm] or g < best_by[arm][v]:
            best_by[arm][v] = g
    print(f"{arm:>5} | {len(ok):5d} {len(hashes):5d} | {100*redisc:6.1f}% | {min(gaps):+.5f} | {finds}")

print("\nmelhor gap por variante (train):")
print(f"{'v':>3} | " + " | ".join(f"{a:>9}" for a in ARMS))
for v in range(10):
    row = [f"{best_by[a].get(v, float('nan')):+9.5f}" if v in best_by[a] else "        —" for a in ARMS]
    print(f"{v:>3} | " + " | ".join(row))
for arm in ("rb1", "rb2"):
    d = [best_by[arm][v] - best_by["ctrl"][v] for v in range(10)
         if v in best_by[arm] and v in best_by["ctrl"]]
    if d:
        print(f"\n{arm} − ctrl (melhor gap, pareado, n={len(d)}): média {np.mean(d):+.5f}, "
              f"mediana {np.median(d):+.5f}, variantes mais fundas: {sum(1 for x in d if x < -1e-9)}")
