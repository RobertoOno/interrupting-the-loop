#!/usr/bin/env python3
"""Refine: small-item uniform family uni[lo,hi]; headroom of best fit vs simple alternatives, 20 instances."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.domains.binpack import evaluate, best_fit, first_fit
from headroom import HEUR
rows = []
for lo in (0.02, 0.04, 0.06, 0.08, 0.10):
    for hi in (0.35, 0.40, 0.45, 0.50, 0.55):
        rng = np.random.default_rng(7)
        inst = [list(np.clip(rng.uniform(lo, hi, 100), 0.01, 1.0)) for _ in range(20)]
        res = {h: evaluate(f, inst)["mean_excess"] for h, f in HEUR.items()}
        bf = res["best_fit"]; alt = min((v, h) for h, v in res.items() if h != "best_fit")
        rows.append((lo, hi, bf, res["first_fit"], alt[0], alt[1], bf - alt[0]))
        print(f"uni[{lo:.2f},{hi:.2f}]  BF {bf:.4f}  FF {res['first_fit']:.4f}  alt {alt[0]:.4f} ({alt[1]:18s})  headroom {bf-alt[0]:+.4f}")
