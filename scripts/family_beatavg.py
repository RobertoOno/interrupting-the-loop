#!/usr/bin/env python3
"""Programa 2, stage 0b — family features of every beat-the-average final
construction on record (runs/frontier/**/beatavg*/best.py, plus the hint seeds).
Each program is executed in a subprocess (time limit) and the normalized pmf is
summarized: number of atoms, mass near zero, mass near the top, and the number
of log10 distance-from-top bands occupied by top-half atoms. The paper-3
ladder classifier (<= 50 atoms, mass >= 0.3 on {0..3}, >= 3 bands) is applied,
and a 'sparse single-scale' label is proposed for the family every unaided
proposer converges to. Output: docs/APPENDIX_P2_FAMILY.md (table).

    python scripts/family_beatavg.py [--timeout 90]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "runs/frontier"
RUNNER = r'''
import sys, json, resource, numpy as np
try:
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
except Exception:
    pass
src = open(sys.argv[1]).read(); L = int(sys.argv[2]); g = {}
exec(compile(src, sys.argv[1], "exec"), g)
p = np.maximum(np.asarray([float(x) for x in g["construct"](L)], dtype=float), 0.0)
p = p / p.sum(); np.save(sys.argv[3], p)
'''


def features(p: np.ndarray, atom_thr: float = 1e-4) -> dict:
    L = len(p); top = L - 1
    atoms = np.flatnonzero(p > atom_thr)
    hi = atoms[atoms > L // 2]
    bands = sorted({int(np.floor(np.log10(top - i + 1))) for i in hi})
    ent = float(-(p[p > 0] * np.log2(p[p > 0])).sum())
    return {"L": L, "n_atoms": int(len(atoms)), "n_support": int((p > 1e-9).sum()),
            "mass_0_3": float(p[:4].sum()), "mass_top10": float(p[max(0, L - 10):].sum()),
            "mass_mid": float(p[4:L // 2].sum()), "n_top_bands": len(bands), "bands": bands,
            "max_atom": float(p.max()), "entropy_bits": ent}


def label(f: dict) -> str:
    if f["n_atoms"] <= 50 and f["mass_0_3"] >= 0.3 and f["n_top_bands"] >= 3:
        return "ladder"  # paper-3 record-family classifier
    if f["n_atoms"] <= 50 and f["n_top_bands"] <= 2:
        return "sparse-single-scale"
    if f["n_atoms"] <= 50:
        return "sparse-other"
    return "dense"


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--timeout", type=int, default=90); a = ap.parse_args()
    from creative_machine.domains import beatavg  # noqa: E402  (verifier for the score check)
    progs = []
    for bp in sorted(FRONT.rglob("best.py")):
        n = bp.parent.name.lower()
        if n.startswith("beatavg"):
            progs.append((bp, 20000 if "20k" in n else 5000))
    for hp in sorted((ROOT / "docs/hint").glob("seed_family_*.py")):
        progs.append((hp, 5000))
    rows = []
    tmp = ROOT / "runs/p2_family"; tmp.mkdir(parents=True, exist_ok=True)
    for bp, L in progs:
        rel = bp.relative_to(ROOT).as_posix(); npy = tmp / (rel.replace("/", "__") + ".npy")
        try:
            subprocess.run([sys.executable, "-c", RUNNER, str(bp), str(L), str(npy)], check=True,
                           timeout=a.timeout, capture_output=True)
            p = np.load(npy); f = features(p); sc = beatavg.verify(p.tolist(), L)["score"]
            rows.append({"program": rel, **f, "score": sc, "label": label(f)})
        except subprocess.CalledProcessError as e:
            rows.append({"program": rel, "L": L, "error": "exec: " + e.stderr.decode(errors="ignore").strip().splitlines()[-1][:120]})
        except Exception as e:  # noqa: BLE001
            rows.append({"program": rel, "L": L, "error": type(e).__name__})
    ok = [r for r in rows if "error" not in r]
    lines = ["# Programa 2 — famílias do beat-the-average nos finais existentes\n",
             f"{len(ok)} programas executados, {len(rows) - len(ok)} falhas. Rótulos: `ladder` = classificador do paper 3 "
             "(≤ 50 átomos, massa ≥ 0,3 em {0..3}, ≥ 3 bandas log10 de distância ao topo); `sparse-single-scale` = ≤ 50 "
             "átomos em ≤ 2 bandas; `sparse-other`; `dense` = > 50 átomos (limiar 1e-4).\n",
             "| programa | L | score | átomos | suporte | massa {0..3} | massa top-10 | massa meio | bandas | rótulo |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(ok, key=lambda r: -r["score"]):
        lines.append(f"| {r['program']} | {r['L']} | {r['score']:.4f} | {r['n_atoms']} | {r['n_support']} | {r['mass_0_3']:.2f} | "
                     f"{r['mass_top10']:.2f} | {r['mass_mid']:.2f} | {r['n_top_bands']} {r['bands']} | {r['label']} |")
    for r in rows:
        if "error" in r: lines.append(f"| {r['program']} | {r['L']} | erro {r['error']} | | | | | | | |")
    from collections import Counter
    c = Counter(r["label"] for r in ok); lines.append("\nContagem: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    (ROOT / "docs/APPENDIX_P2_FAMILY.md").write_text("\n".join(lines) + "\n")
    (tmp / "features.json").write_text(json.dumps(rows, indent=1))
    print("\n".join(lines[3:]))


if __name__ == "__main__":
    main()
