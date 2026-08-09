#!/usr/bin/env python3
"""Run the anti-probable sampler against a real model on the Mac.

Example:

    python scripts/generate_mlx.py \
        --model mlx-community/Qwen3-8B-Base-8bit \
        --prompt "The true purpose of a lighthouse is" \
        --max-tokens 200 --lam 3.0 --entropy-trigger 2.0 \
        --telemetry runs/first.jsonl --baseline

--baseline additionally generates with mlx-lm's default sampling at the same
temperature, for a side-by-side feel of what the perturbation changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="mlx-lm model path or HF id (use a BASE model)")
    p.add_argument("--prompt", required=True)
    p.add_argument("--max-tokens", type=int, default=200)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--entropy-trigger", type=float, default=2.0)
    p.add_argument("--entropy-ceiling", type=float, default=4.5)
    p.add_argument("--coherence-floor", type=float, default=0.05)
    p.add_argument("--lam", type=float, default=1.5)
    p.add_argument("--distance-scale", choices=["raw", "standardize"], default="standardize")
    p.add_argument("--halflife", type=float, default=16.0)
    p.add_argument("--choice", choices=["sample", "argmax"], default="sample")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--telemetry", type=Path, default=None, help="write per-step JSONL here")
    p.add_argument("--baseline", action="store_true", help="also generate with default sampling")
    return p.parse_args()


def eos_ids(tokenizer) -> tuple[int, ...]:
    """EOS ids to exempt from the distance push (never push out of the text)."""
    ids = getattr(tokenizer, "eos_token_ids", None)
    if not ids and tokenizer.eos_token_id is not None:
        ids = [tokenizer.eos_token_id]
    return tuple(ids or ())


def main() -> None:
    args = parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(args.model)
    config = SamplerConfig(
        temperature=args.temperature,
        entropy_trigger=args.entropy_trigger,
        entropy_ceiling=args.entropy_ceiling,
        coherence_floor=args.coherence_floor,
        lam=args.lam,
        distance_scale=args.distance_scale,
        no_push_ids=eos_ids(tokenizer),
        context_halflife=args.halflife,
        perturb_choice=args.choice,
        seed=args.seed,
    )
    sampler = MLXAntiprobableSampler(model, config=config)
    sampler.observe_prompt(tokenizer.encode(args.prompt))

    print("=== anti-probable ===")
    print(args.prompt, end="", flush=True)
    for out in stream_generate(model, tokenizer, args.prompt, max_tokens=args.max_tokens, sampler=sampler):
        print(out.text, end="", flush=True)
    print("\n")
    print(json.dumps(sampler.telemetry.summary(), indent=2))

    if args.telemetry:
        args.telemetry.parent.mkdir(parents=True, exist_ok=True)
        sampler.telemetry.to_jsonl(args.telemetry)
        print(f"telemetry -> {args.telemetry}")

    if args.baseline:
        from mlx_lm.sample_utils import make_sampler

        # Fair baseline: same relative floor (min-p), same temperature, no
        # distance push — isolates the effect of lam. Plain categorical at
        # T=1 degenerates on its own in small base models.
        print("\n=== baseline (min-p at same floor) ===")
        print(args.prompt, end="", flush=True)
        base = make_sampler(temp=args.temperature, min_p=args.coherence_floor)
        for out in stream_generate(model, tokenizer, args.prompt, max_tokens=args.max_tokens, sampler=base):
            print(out.text, end="", flush=True)
        print()


if __name__ == "__main__":
    main()
