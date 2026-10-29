#!/usr/bin/env python3
"""Programa 2, stage 0a — the family library, mined from existing verified-search
runs (no program is executed here; scores and behaviour signatures come from the
runs' own state.json). Every island elite of every run on the source problems is
collected, deduplicated by behaviour signature, and the top-K per problem (by
verified score) is written as an executable program with a header. The target
problem(s) (--exclude, default sumdiff3) are EXCLUDED: the library must not
contain the family under test. Hand-written classical families from other
problems live in docs/transfer_library/classical/ (not touched here).

    python scripts/transfer_library.py [--top 8] [--out docs/transfer_library]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "runs/frontier"
spec = importlib.util.spec_from_file_location("fs", ROOT / "scripts/frontier_search.py")
fs = importlib.util.module_from_spec(spec); spec.loader.exec_module(fs)
PROBLEMS = fs.PROBLEMS


def problem_of(run: Path) -> str | None:
    name = run.name.lower()
    for k in sorted(PROBLEMS, key=len, reverse=True):
        if name.startswith(k + "_") or name == k:
            return k
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--out", default="docs/transfer_library")
    ap.add_argument("--exclude", default="sumdiff3", help="comma-separated target problems to keep OUT of the library")
    a = ap.parse_args()
    EXCLUDE = set(a.exclude.split(","))
    out = ROOT / a.out; out.mkdir(parents=True, exist_ok=True)
    pool: dict[str, dict[str, dict]] = defaultdict(dict)  # problem -> sig -> member
    n_runs = 0
    for st in sorted(FRONT.rglob("state.json")):
        run = st.parent; prob = problem_of(run)
        if prob is None or prob in EXCLUDE or "smoke" in run.name:
            continue
        try:
            d = json.loads(st.read_text())
        except Exception:
            continue
        n_runs += 1
        for isl in d.get("islands", []):
            for m in isl:
                code, sc, sig = m.get("code", ""), m.get("score"), m.get("sig") or m.get("hash")
                if sc is None or not code.strip() or m.get("hash") == "seed":
                    continue
                cur = pool[prob].get(sig)
                better = PROBLEMS[prob]["maximize"] and (cur is None or sc > cur["score"]) or \
                    (not PROBLEMS[prob]["maximize"] and (cur is None or sc < cur["score"]))
                if better:
                    pool[prob][sig] = {"code": code, "score": sc, "sig": sig,
                                       "run": run.relative_to(FRONT).as_posix()}
    index = []
    for prob, members in sorted(pool.items()):
        P = PROBLEMS[prob]; rev = P["maximize"]
        ranked = sorted(members.values(), key=lambda m: m["score"], reverse=rev)[: a.top]
        pdir = out / prob; pdir.mkdir(exist_ok=True)
        for r, m in enumerate(ranked, 1):
            fn = pdir / f"{r:02d}_{m['sig'][:8]}.py"
            header = (f"# transfer-library entry | problem: {prob} | rank {r}/{len(ranked)} | verified score {m['score']:.6g}"
                      f" (best known {P.get('best_known')}) | source run {m['run']} | signature {m['sig']}\n"
                      f"# statement: {P['statement']}\n")
            fn.write_text(header + m["code"].rstrip() + "\n")
            index.append({"problem": prob, "rank": r, "file": fn.relative_to(ROOT).as_posix(),
                          "score": m["score"], "best_known": P.get("best_known"), "run": m["run"], "sig": m["sig"]})
        print(f"{prob:13s} runs-pooled elites {len(members):4d} distinct sigs -> kept {len(ranked)} "
              f"(best {ranked[0]['score']:.6g} vs known {P.get('best_known')})")
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{n_runs} runs scanned; {len(index)} programs written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
