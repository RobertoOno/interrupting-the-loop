#!/usr/bin/env python3
"""The verifier showdown: anti-probable vs plain sampling, judged by reality.

Two arms, seed-paired, same model and budget; the only delta is lam. Each
sample completes the bin-packing priority prompt, the extracted function is
scored by simulation on fixed instances, and the arms are compared on
validity rate, excess distribution, diversity, and wins over best fit.

    python scripts/verify_run.py --model ~/models/mlx/Qwen3-8B-Base-8bit \
        --n-samples 40 --out runs/verify1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.code_exec import run_heuristic_code  # noqa: E402
from creative_machine.domains.binpack import best_fit, evaluate, generate_instances  # noqa: E402
from creative_machine.heuristic_gen import BINPACK_PROMPT, extract_function  # noqa: E402
from creative_machine.stats import bootstrap_diff_ci, mean_std  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--n-samples", type=int, default=40, help="per arm")
    p.add_argument("--lam", type=float, default=1.5, help="anti-probable arm's lambda")
    p.add_argument("--entropy-trigger", type=float, default=2.0)
    p.add_argument("--entropy-ceiling", type=float, default=4.5)
    p.add_argument("--max-tokens", type=int, default=160)
    p.add_argument("--n-instances", type=int, default=20)
    p.add_argument("--n-items", type=int, default=120)
    p.add_argument("--eval-seed", type=int, default=99)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(str(Path(args.model).expanduser()))
    prompt_ids = tokenizer.encode(BINPACK_PROMPT)
    instances = generate_instances(
        args.n_instances, args.n_items, np.random.default_rng(args.eval_seed)
    )
    bf_excess = evaluate(best_fit, instances)["mean_excess"]
    print(f"best-fit baseline mean_excess: {bf_excess:.4f}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    cells = []
    for arm_lam, arm in ((0.0, "plain"), (args.lam, "antiprob")):
        for seed in range(args.n_samples):
            config = SamplerConfig(
                lam=arm_lam,
                entropy_trigger=args.entropy_trigger,
                entropy_ceiling=args.entropy_ceiling,
                no_push_ids=eos_ids(tokenizer),
                seed=seed,
            )
            sampler = MLXAntiprobableSampler(model, config=config)
            sampler.observe_prompt(prompt_ids)
            completion = "".join(
                out.text
                for out in stream_generate(
                    model, tokenizer, BINPACK_PROMPT, max_tokens=args.max_tokens, sampler=sampler
                )
            )
            fn = extract_function(completion)
            cell = {
                "arm": arm,
                "seed": seed,
                "perturb_rate": sampler.telemetry.summary().get("perturb_rate"),
                "code": fn,
            }
            if fn is None:
                cell["ok"] = False
                cell["error"] = "no function extracted"
            else:
                cell.update(run_heuristic_code(fn, instances, timeout_s=15.0))
            cells.append(cell)
            status = f"excess {cell['mean_excess']:.4f}" if cell.get("ok") else cell.get("error", "?")[:40]
            print(f"{arm} s{seed}: {status}", flush=True)
            (args.out / "cells.json").write_text(json.dumps(cells, indent=2))

    print(f"\n== showdown (n={args.n_samples}/arm, lam={args.lam}, best_fit={bf_excess:.4f}) ==")
    summary = {"best_fit_excess": bf_excess, "arms": {}}
    excess_by_arm = {}
    for arm in ("plain", "antiprob"):
        sub = [c for c in cells if c["arm"] == arm]
        valid = [c for c in sub if c.get("ok")]
        excesses = [c["mean_excess"] for c in valid]
        excess_by_arm[arm] = excesses
        bodies = {"".join(c["code"].split()) for c in valid}
        beats = [c for c in valid if c["mean_excess"] < bf_excess - 1e-9]
        pr = [c["perturb_rate"] for c in sub if c.get("perturb_rate") is not None]
        m, s = mean_std(excesses) if excesses else (float("nan"), 0.0)
        arm_summary = {
            "valid": f"{len(valid)}/{len(sub)}",
            "excess_mean": round(m, 4),
            "excess_std": round(s, 4),
            "excess_min": round(min(excesses), 4) if excesses else None,
            "distinct_bodies": len(bodies),
            "beats_best_fit": len(beats),
            "perturb_rate_mean": round(float(np.mean(pr)), 3) if pr else None,
        }
        summary["arms"][arm] = arm_summary
        print(f"  {arm:<9} {arm_summary}")
    if all(excess_by_arm.values()):
        lo, hi = bootstrap_diff_ci(excess_by_arm["antiprob"], excess_by_arm["plain"])
        summary["excess_diff_ci"] = [round(lo, 4), round(hi, 4)]
        print(f"  excess diff (antiprob - plain) CI95: [{lo:+.4f}, {hi:+.4f}]")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
