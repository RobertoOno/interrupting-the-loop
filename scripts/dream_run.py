#!/usr/bin/env python3
"""Run the reverie loop (DREAM) and its controls.

    AWS_PROFILE=main-account python scripts/dream_run.py --tokens 3000 --out runs/dream1
    ... --control plain      # Control A: same loop, plain sampler (no drift)
    ... --control clock      # Control C: salience off, review every N tokens
    ... --no-judge           # salience calibration only (no API calls)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.blend import BedrockClient, judge_reverie  # noqa: E402
from creative_machine.dream import DreamConfig, dream  # noqa: E402
from creative_machine.salience import SalienceConfig  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402

SEEDS = [
    "The lighthouse keeper had one theory about the sea, and it was this:",
    "She kept a notebook of things that had almost happened.",
    "The map was accurate in every detail except one, and nobody could say which.",
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--tokens", type=int, default=3000)
    p.add_argument("--seed-index", type=int, default=0)
    p.add_argument("--seed-text", default=None, help="explicit seed (overrides --seed-index)")
    p.add_argument("--rng-seed", type=int, default=0)
    p.add_argument("--control", choices=["none", "plain", "clock"], default="none")
    p.add_argument("--clock-every", type=int, default=150)
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--judge-model", default="anthropic.claude-sonnet-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    from mlx_lm import load

    model, tokenizer = load(str(Path(args.model).expanduser()))
    no_push = eos_ids(tokenizer)
    cfg = DreamConfig(total_tokens=args.tokens)
    cfg.drift = SamplerConfig(**{**cfg.drift.__dict__, "no_push_ids": no_push, "seed": args.rng_seed})
    cfg.escalate = SamplerConfig(**{**cfg.escalate.__dict__, "no_push_ids": no_push, "seed": args.rng_seed})

    if args.control == "plain":
        # Control A: no drift — plain (floored) sampling in both regimes
        cfg.drift = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed)
        cfg.escalate = cfg.drift
    if args.control == "clock":
        # Control C: salience off — review on a clock. Emulated by a monitor
        # that fires a "clock" jump every N steps (thresholds unreachable).
        cfg.salience = SalienceConfig(
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            refractory=args.clock_every, snapshot_every=8,
        )
        cfg.salience.jump_lag = 1
        cfg.salience.jump_threshold = -1.0  # always fires; refractory paces it

    sampler = MLXAntiprobableSampler(model, config=cfg.drift)
    judge = None
    if not args.no_judge:
        client = BedrockClient(aws_region=args.region)
        judge = lambda w, e: judge_reverie(client, args.judge_model, w, e)  # noqa: E731

    seed = args.seed_text if args.seed_text else SEEDS[args.seed_index % len(SEEDS)]
    print(f"== DREAM ({args.control}) seed: {seed!r}", flush=True)
    run = dream(model, tokenizer, sampler, seed, cfg, judge=judge)
    run.save(args.out)
    print("\n== summary ==")
    print(run.summary())
    if not args.no_judge:
        print("tokens:", client.usage)
    print(f"-> {args.out}/ (text.txt, insights.json, run.json)")


if __name__ == "__main__":
    main()
