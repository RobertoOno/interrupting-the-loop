#!/usr/bin/env python3
"""Cross-family judge agreement: re-judge a stratified sample of already-judged
windows with a second judge from another model family (via OpenRouter), k
samples each, and report Spearman agreement with the Opus judgments per
dimension, plus per-condition means under both judges. Resumable.

    python scripts/judge_agreement.py --judge moonshotai/kimi-k2.6 --per-cond 20 --k 5
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from creative_machine.blend import OpenRouterClient, judge_surprise  # noqa: E402
from dream_rejudge import windows_generated, windows_of  # noqa: E402

RUNS = ROOT / "runs"
DIMS = ("surprise", "connection", "coherence")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--judge", default="moonshotai/kimi-k2.6")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--per-cond", type=int, default=20)
    p.add_argument("--runs", nargs="+", default=["dream_scaffold", "dream_b2"])
    p.add_argument("--conds", nargs="*", default=["bare", "bare_habit", "bare_reseed", "scaffold0", "clock_reenc", "clock300", "sal_reenc"])
    p.add_argument("--seed", type=int, default=3)
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--protocol", choices=["events", "gen"], default="events",
                   help="which Opus judgments to sample from and which windows to recut (gen = generated-only, post-interruption)")
    p.add_argument("--sampling", choices=["stratified", "random"], default="stratified",
                   help="stratified: evenly across the Opus surprise range; random: uniform over judged windows")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer
    tok = load_tokenizer(Path(args.tokenizer_model).expanduser())
    rng = random.Random(args.seed)
    out_dir = RUNS / "judge_agreement"; out_dir.mkdir(exist_ok=True)
    tag = args.judge.replace("/", "_") + ("_gen" if args.protocol == "gen" else "")
    out_path = out_dir / f"{tag}.json"
    results = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {(r["run"], r["cell"], r["step"]) for r in results}

    # stratified sample: per condition, evenly across the Opus surprise range
    pool = []
    names = ("rejudge_gen.json", "rejudge_gen_w2.json", "rejudge_gen_w3.json") if args.protocol == "gen" else ("rejudge_surprise.json",)
    seen = set()
    for run in args.runs:
        for name in names:
            pth = RUNS / run / name
            if pth.exists():
                for r in json.loads(pth.read_text()):
                    if r.get("surprise") is None or r["cond"] not in args.conds or (run, r["cell"], r["step"]) in seen:
                        continue
                    if args.protocol == "gen" and r.get("since") not in (32, None):
                        continue
                    if args.protocol == "events" and r["step"] < 100:
                        continue
                    seen.add((run, r["cell"], r["step"])); pool.append({**r, "run": run})
    sample = []
    for cond in args.conds:
        rows = sorted((r for r in pool if r["cond"] == cond), key=lambda r: r["surprise"])
        if not rows:
            continue
        if args.sampling == "random":
            sample.extend(rng.sample(rows, min(args.per_cond, len(rows))))
        else:
            idx = np.linspace(0, len(rows) - 1, min(args.per_cond, len(rows))).round().astype(int)
            sample.extend(rows[i] for i in sorted(set(idx)))
    print(f"{len(sample)} windows, judge {args.judge}, k={args.k}", flush=True)

    client = OpenRouterClient()
    cache = {}
    for r in sample:
        key = (r["run"], r["cell"], r["step"])
        if key in done:
            continue
        ck = (r["run"], r["cell"])
        if ck not in cache:
            if args.protocol == "gen":
                cache[ck] = {(w["step"], "gen"): w for w in windows_generated(RUNS / r["run"] / r["cell"], tok)}
            else:
                cache[ck] = {(w["step"], w["kind"]): w for w in windows_of(RUNS / r["run"] / r["cell"], tok, 160, 600)}
        w = cache[ck].get((r["step"], r["kind"]))
        if not w:
            continue
        vs = []
        for _ in range(args.k):
            try:
                vs.append(judge_surprise(client, args.judge, w["window"], w["earlier"]))
            except Exception as exc:
                print(f"  error: {str(exc)[:100]}", flush=True)
        if not vs:
            continue
        rec = {"run": r["run"], "cell": r["cell"], "cond": r["cond"], "step": r["step"], "kind": r["kind"], "k": len(vs),
               "opus": {d: r[d] for d in DIMS}}
        for d in DIMS:
            vals = [v[d] for v in vs]
            rec[d] = statistics.median(vals); rec[d + "_spread"] = max(vals) - min(vals)
        results.append(rec)
        print(f"{r['cell']:<16} step {r['step']:>5}  {tag}: S {rec['surprise']} C {rec['connection']} H {rec['coherence']}   Opus: S {r['surprise']} C {r['connection']} H {r['coherence']}", flush=True)
        out_path.write_text(json.dumps(results, indent=2))

    print(f"\n== agreement with Opus ({len(results)} windows) ==")
    for d in DIMS:
        a = [r[d] for r in results]; b = [r["opus"][d] for r in results]
        rho, pv = spearmanr(a, b)
        sp = np.mean([r[d + "_spread"] for r in results])
        print(f"  {d:<11} Spearman ρ={rho:+.2f} (p={pv:.1e}); mean {tag} {np.mean(a):.2f} vs Opus {np.mean(b):.2f}; {tag} intra-window spread {sp:.2f}")
    print("\n== per condition (second judge vs Opus, surprise / connection / coherence) ==")
    for cond in args.conds:
        rs = [r for r in results if r["cond"] == cond]
        if rs:
            print(f"  {cond:<12} n={len(rs):>3}  {tag}: " + " / ".join(f"{np.mean([r[d] for r in rs]):.2f}" for d in DIMS)
                  + "   Opus: " + " / ".join(f"{np.mean([r['opus'][d] for r in rs]):.2f}" for d in DIMS))
    print("tokens:", client.usage)


if __name__ == "__main__":
    main()
