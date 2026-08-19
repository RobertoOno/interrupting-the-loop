#!/usr/bin/env python3
"""Verify every priority function a problem-notebook stream wrote, and score
the cells: the interrupted loop over a problem with a verifier.

For each cell (one bin-packing variant, one arm): extract every top-level
`def priority*(item: float, remaining: list[float]) -> list[float]:` with its
indented body (commented-out definitions are ignored), rename it `priority`,
run it in the sandbox on held-out instances of the cell's variant (and on a
training set, reported too), and record ok / mean_excess. Per cell: number of
candidates, number valid, number of distinct valid bodies, best mean excess
(lower is better), and the best-fit and first-fit baselines on the same
instances. Then paired contrasts across the ten variants (exact sign-flip
permutation), as in the narrative batteries.

    python scripts/problem_verify.py runs/dream_problem
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_machine.code_exec import run_heuristic_code  # noqa: E402
from creative_machine.domains import binpack  # noqa: E402
from creative_machine.problem_premises import VARIANTS  # noqa: E402

HEAD = re.compile(r"^def (priority\w*)\(item: float, remaining: list\[float\]\) -> list\[float\]:\s*$")
BEST_FIT = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [-(r - item) for r in remaining]\n"
FIRST_FIT = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [0.0] * len(remaining)\n"


def extract_functions(text: str, skip_baselines: bool = True) -> list[str]:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if not m:
            i += 1; continue
        name = m.group(1)
        body = []
        j = i + 1
        while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith((" ", "\t"))):
            body.append(lines[j]); j += 1
        while body and body[-1].strip() == "":
            body.pop()
        if body and any(l.strip() for l in body):
            if not (skip_baselines and name in ("priority_first_fit", "priority_best_fit")):
                out.append("def priority(item: float, remaining: list[float]) -> list[float]:\n" + "\n".join(body) + "\n")
        i = j
    return out


def norm(code: str) -> str:
    body = "\n".join(l.strip() for l in code.splitlines()[1:] if l.strip() and not l.strip().startswith('"""'))
    return hashlib.md5(re.sub(r"\s+", " ", body).encode()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--n-instances", type=int, default=5)
    p.add_argument("--n-items", type=int, default=100)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    out_path = args.out or (args.run_dir / "verified.json")
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    cells = sorted(d for d in args.run_dir.iterdir() if d.is_dir() and (d / "text.txt").exists())
    for d in cells:
        if d.name in results:
            continue
        seed_i = int(d.name.split("_", 1)[0][1:]); cond = d.name.split("_", 1)[1]
        lo, hi = VARIANTS[seed_i]
        train = binpack.generate_instances(args.n_instances, args.n_items, np.random.default_rng(100 + seed_i), lo, hi)
        held = binpack.generate_instances(args.n_instances, args.n_items, np.random.default_rng(200 + seed_i), lo, hi)
        base = {"best_fit": run_heuristic_code(BEST_FIT, held)["mean_excess"], "first_fit": run_heuristic_code(FIRST_FIT, held)["mean_excess"]}
        text = (d / "text.txt").read_text()
        cands = extract_functions(text)
        recs, seen = [], set()
        for c in cands:
            h = norm(c)
            r_tr = run_heuristic_code(c, train, timeout_s=20)
            r_he = run_heuristic_code(c, held, timeout_s=20) if r_tr.get("ok") else {"ok": False, "error": r_tr.get("error", "")}
            recs.append({"hash": h, "ok": bool(r_he.get("ok")), "train_excess": r_tr.get("mean_excess"), "held_excess": r_he.get("mean_excess"),
                         "error": (r_tr.get("error") or r_he.get("error") or "")[:80], "code": c})
            seen.add(h)
        valid = [r for r in recs if r["ok"]]
        distinct_valid = {r["hash"] for r in valid}
        best = min((r["held_excess"] for r in valid), default=None)
        results[d.name] = {"cond": cond, "variant": seed_i, "n_candidates": len(cands), "n_valid": len(valid),
                           "n_distinct_valid": len(distinct_valid), "best_held_excess": best, "baselines": base,
                           "beats_best_fit": bool(best is not None and best < base["best_fit"] - 1e-9),
                           "n_beating_best_fit": sum(1 for r in valid if r["held_excess"] < base["best_fit"] - 1e-9),
                           "candidates": recs}
        print(f"{d.name:<18} cands {len(cands):>3} valid {len(valid):>3} distinct {len(distinct_valid):>3} best {best if best is None else round(best, 4)}  best_fit {base['best_fit']:.4f}", flush=True)
        out_path.write_text(json.dumps(results, indent=1))
    # ---- cell-level summary and paired contrasts
    conds = sorted({v["cond"] for v in results.values()})
    print("\n== per arm (unit = variant; mean over cells) ==")
    table = {}
    for c in conds:
        rs = [v for v in results.values() if v["cond"] == c]
        best = [v["best_held_excess"] if v["best_held_excess"] is not None else v["baselines"]["first_fit"] for v in rs]  # no valid candidate: count as first-fit
        table[c] = {v["variant"]: {"best": (v["best_held_excess"] if v["best_held_excess"] is not None else v["baselines"]["first_fit"]),
                                   "gain": v["baselines"]["best_fit"] - (v["best_held_excess"] if v["best_held_excess"] is not None else v["baselines"]["first_fit"]),
                                   "valid": v["n_valid"], "distinct": v["n_distinct_valid"], "beats": int(v["beats_best_fit"])} for v in rs}
        print(f"  {c:<10} n={len(rs)}  best excess {np.mean(best):.4f}  gain over best fit {np.mean([table[c][k]['gain'] for k in table[c]]):+.4f}  "
              f"valid {np.mean([v['n_valid'] for v in rs]):.1f}  distinct {np.mean([v['n_distinct_valid'] for v in rs]):.1f}  cells beating best fit {sum(v['beats_best_fit'] for v in rs)}/{len(rs)}")

    def paired(a, b, key):
        ks = sorted(set(a) & set(b))
        d = np.array([a[k][key] - b[k][key] for k in ks], float)
        if len(d) < 3:
            return None
        obs = abs(d.mean()); n = len(d)
        cnt = sum(1 for signs in itertools.product((1, -1), repeat=n) if abs((d * np.array(signs)).mean()) >= obs - 1e-12)
        rng = np.random.default_rng(0); bs = [rng.choice(d, len(d)).mean() for _ in range(5000)]
        return d.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5), cnt / 2 ** n, n
    print("\n== paired contrasts (exact permutation) ==")
    for a, b in (("angle300", "plain"), ("reset300", "plain"), ("sham300", "plain"), ("angle300", "reset300"), ("angle300", "sham300")):
        if a in table and b in table:
            for key in ("gain", "valid", "distinct", "beats"):
                pr = paired(table[a], table[b], key)
                if pr:
                    print(f"  {a} - {b}  {key:<8} Δ {pr[0]:+.4f} [{pr[1]:+.4f}, {pr[2]:+.4f}]  p={pr[3]:.3f}  n={pr[4]}")


if __name__ == "__main__":
    main()
