#!/usr/bin/env python3
"""Programa 2 — family features of every sum-difference III final on record
(runs/frontier/**/sumdiff3*/best.py), executed in a subprocess. Features of U:
size, max, |U+U|/|U|^2, |U-U|/|U|^2, theta, and the DIGIT signature: the smallest base
b in 2..25 such that every element's base-b digits are <= (b-1)/2 (carry-free
encoding, the record family's property), the max digit in base 2 representation
count (popcount) and whether U is closed under 'sums of <= t powers of two'.
Writes docs/APPENDIX_P2_FAMILY_SUMDIFF3.md.

    PYTHONPATH=src python scripts/family_sumdiff3.py
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "runs/frontier"
RUNNER = r'''
import sys, json, resource
try:
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
except Exception:
    pass
src = open(sys.argv[1]).read(); g = {}
exec(compile(src, sys.argv[1], "exec"), g)
U = g["construct"](); json.dump([int(x) for x in U], open(sys.argv[2], "w"))
'''


def digits(x: int, b: int) -> list[int]:
    d = []
    while x: d.append(x % b); x //= b
    return d or [0]


def carry_free_base(U: list[int], max_base: int = 2001) -> int | None:
    """Smallest base b (2..max_base) in which every element's digits are <= (b-1)/2, so that
    sums and differences never carry (the record family's mechanism; a base-(2m+1) tensor
    power of a seed set in [0, m] passes with b = 2m+1). Vectorized; the bound was 25 until
    2026-09-03 23:00 and missed every tensor power with m >= 13 (stage-1 read)."""
    arr = np.array(sorted(set(U)), dtype=np.int64)
    if len(arr) < 2:
        return None
    for b in range(2, max_base + 1):
        x = arr.copy(); ok = True; half = (b - 1) // 2
        while x.any():
            if (x % b > half).any():
                ok = False; break
            x //= b
        if ok:
            return b
    return None


def features(U: list[int]) -> dict:
    s = sorted(set(U)); n = len(s); arr = np.array(s, dtype=np.int64)
    sums = np.unique((arr[:, None] + arr[None, :]).ravel()); diffs = np.unique((arr[:, None] - arr[None, :]).ravel())
    pc = [bin(x).count("1") for x in s]
    return {"n": n, "max": int(arr[-1]), "sum_ratio": len(sums) / n ** 2, "diff_ratio": len(diffs) / n ** 2,
            "carry_free_base": carry_free_base(s), "max_popcount": max(pc), "mean_popcount": float(np.mean(pc)),
            "frac_pow2_sums_le3": float(np.mean([p <= 3 for p in pc]))}


def main() -> None:
    from creative_machine.domains import sumdiff3
    tmp = ROOT / "runs/p2_family"; tmp.mkdir(parents=True, exist_ok=True)
    rows = []
    progs = [bp for bp in sorted(FRONT.rglob("best.py")) if bp.parent.name.lower().startswith("sumdiff3")]
    for bp in progs:
        rel = bp.relative_to(ROOT).as_posix(); out = tmp / (rel.replace("/", "__") + ".json")
        try:
            subprocess.run([sys.executable, "-c", RUNNER, str(bp), str(out)], check=True, timeout=120, capture_output=True)
            U = json.load(open(out)); r = sumdiff3.verify(U)
            f = features(U); f["theta"] = r.get("score"); f["ok"] = r.get("ok"); rows.append({"program": rel, **f})
        except subprocess.CalledProcessError as e:
            rows.append({"program": rel, "error": e.stderr.decode(errors="ignore").strip().splitlines()[-1][:100]})
        except Exception as e:  # noqa: BLE001
            rows.append({"program": rel, "error": type(e).__name__})
    ok = [r for r in rows if "error" not in r and r.get("ok")]
    lines = ["# Programa 2 — famílias do sum-difference III nos finais existentes\n",
             f"{len(ok)} finais válidos de {len(rows)} programas. `base s/ vai-um` = menor base b (2..25) em que todos os "
             "dígitos ≤ (b−1)/2 (propriedade da família do recorde); `pop≤3` = fração dos elementos que são somas de ≤ 3 "
             "potências de 2 (família dos laços).\n",
             "| programa | θ | |U| | max U | |U+U|/|U|² | |U−U|/|U|² | base s/ vai-um | pop máx | pop≤3 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(ok, key=lambda r: -r["theta"]):
        lines.append(f"| {r['program']} | {r['theta']:.5f} | {r['n']} | {r['max']} | {r['sum_ratio']:.3f} | {r['diff_ratio']:.3f} | "
                     f"{r['carry_free_base']} | {r['max_popcount']} | {r['frac_pow2_sums_le3']:.2f} |")
    for r in rows:
        if "error" in r or not r.get("ok"): lines.append(f"| {r['program']} | erro {r.get('error', 'invalid')} | | | | | | | |")
    # the record family inside the cap, for reference
    import itertools
    def U_rec(m, L, B):
        base = 2 * B + 1
        return sorted({sum(xk * base ** k for k, xk in enumerate(x)) for x in itertools.product(range(B + 1), repeat=m) if sum(x) <= L})
    Ur = U_rec(8, 6, 4); fr = features(Ur); fr["theta"] = sumdiff3.verify(Ur)["score"]
    lines.append(f"| (referência) família do recorde m=8 L=6 B=4 | {fr['theta']:.5f} | {fr['n']} | {fr['max']} | {fr['sum_ratio']:.3f} | "
                 f"{fr['diff_ratio']:.3f} | {fr['carry_free_base']} | {fr['max_popcount']} | {fr['frac_pow2_sums_le3']:.2f} |")
    (ROOT / "docs/APPENDIX_P2_FAMILY_SUMDIFF3.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[3:]))


if __name__ == "__main__":
    main()
