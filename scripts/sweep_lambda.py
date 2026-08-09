#!/usr/bin/env python3
"""Calibration sweep: same model, prompt and seed across a range of lambdas.

Loads the model once, generates for each lambda plus a min-p baseline, saves
per-step telemetry under --out, and prints a comparison table followed by the
generated texts.

Example:

    python scripts/sweep_lambda.py \
        --model ~/models/mlx/Qwen3-8B-Base-8bit \
        --prompt "The true purpose of a lighthouse is" \
        --lams 0,3,6,10 --max-tokens 150 --seed 0 --out runs/sweep1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--lams", default="0,0.5,1,2,3", help="comma-separated lambda values")
    p.add_argument("--distance-scale", choices=["raw", "standardize"], default="standardize")
    p.add_argument("--max-tokens", type=int, default=150)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--entropy-trigger", type=float, default=2.0)
    p.add_argument("--entropy-ceiling", type=float, default=4.5)
    p.add_argument("--coherence-floor", type=float, default=0.05)
    p.add_argument("--halflife", type=float, default=16.0)
    p.add_argument("--choice", choices=["sample", "argmax"], default="sample")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=Path("runs/sweep"))
    return p.parse_args()


def generate(model, tokenizer, prompt: str, max_tokens: int, sampler) -> tuple[str, float]:
    from mlx_lm import stream_generate

    pieces, tps = [], 0.0
    for out in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
        pieces.append(out.text)
        tps = out.generation_tps
    return "".join(pieces), tps


def main() -> None:
    args = parse_args()
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(args.model)
    args.out.mkdir(parents=True, exist_ok=True)
    prompt_ids = tokenizer.encode(args.prompt)

    runs: list[tuple[str, str, dict]] = []

    base = make_sampler(temp=args.temperature, min_p=args.coherence_floor)
    text, tps = generate(model, tokenizer, args.prompt, args.max_tokens, base)
    runs.append(("baseline min-p", text, {"tps": tps}))
    (args.out / "baseline.txt").write_text(args.prompt + text)

    for lam in (float(x) for x in args.lams.split(",")):
        config = SamplerConfig(
            temperature=args.temperature,
            entropy_trigger=args.entropy_trigger,
            entropy_ceiling=args.entropy_ceiling,
            coherence_floor=args.coherence_floor,
            lam=lam,
            distance_scale=args.distance_scale,
            no_push_ids=eos_ids(tokenizer),
            context_halflife=args.halflife,
            perturb_choice=args.choice,
            seed=args.seed,
        )
        sampler = MLXAntiprobableSampler(model, config=config)
        sampler.observe_prompt(prompt_ids)
        text, tps = generate(model, tokenizer, args.prompt, args.max_tokens, sampler)
        summary = sampler.telemetry.summary()
        summary["tps"] = tps
        label = f"lam={lam:g}"
        sampler.telemetry.to_jsonl(args.out / f"{label}.jsonl")
        (args.out / f"{label}.txt").write_text(args.prompt + text)
        runs.append((label, text, summary))

    cols = ["perturb_rate", "mean_rank", "mean_rank_perturbed", "mean_distance_perturbed", "mean_distance_spread", "perplexity", "tps"]
    header = f"{'run':<16}" + "".join(f"{c:>24}" for c in cols)
    print("\n" + header)
    print("-" * len(header))
    for label, _, summary in runs:
        row = f"{label:<16}"
        for c in cols:
            v = summary.get(c)
            row += f"{v:>24.3f}" if isinstance(v, float) else f"{'-':>24}"
        print(row)

    for label, text, _ in runs:
        print(f"\n=== {label} ===")
        print(args.prompt + text)

    (args.out / "summaries.json").write_text(
        json.dumps({label: s for label, _, s in runs}, indent=2)
    )
    print(f"\ntelemetry + texts -> {args.out}/")


if __name__ == "__main__":
    main()
