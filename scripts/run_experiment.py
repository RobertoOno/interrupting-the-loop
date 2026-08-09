#!/usr/bin/env python3
"""Multi-seed, multi-prompt experiment: machine arms vs min-p baseline.

Phase 1 (default) generates the full grid (prompts x seeds x arms) with one
model load, saves texts + telemetry + manifest, and prints the telemetry
aggregate. Phase 2 (--novelty) reads the manifest, measures n-gram novelty
of every cell against an infini-gram index, and prints per-arm aggregates
with bootstrap CIs of the difference vs baseline.

    python scripts/run_experiment.py --model ~/models/mlx/OLMo-2-13B-8bit \
        --arms baseline,1,2 --seeds 0,1,2,3,4 --out runs/exp1
    python scripts/run_experiment.py --out runs/exp1 --novelty --index olmo13b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.novelty import InfiniGramClient, novelty_report  # noqa: E402
from creative_machine.stats import bootstrap_diff_ci, mean_std  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402
from novelty_check import ALIASES  # noqa: E402

PROMPTS = [
    "The lighthouse keeper had one theory about the sea, and it was this:",
    "In the last workshop on the street of clockmakers, there was a clock that",
    "The cartographer knew the map was wrong, but she also knew",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=None)
    p.add_argument("--arms", default="baseline,1,2", help='"baseline" and/or lambda values')
    p.add_argument("--seeds", default="0,1,2,3,4")
    p.add_argument("--max-tokens", type=int, default=150)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--entropy-trigger", type=float, default=2.0)
    p.add_argument("--entropy-ceiling", type=float, default=4.5)
    p.add_argument("--coherence-floor", type=float, default=0.05)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--novelty", action="store_true", help="phase 2: measure novelty of an existing run")
    p.add_argument("--index", default="olmo13b")
    p.add_argument("--ns", default="4,6")
    p.add_argument("--stride", type=int, default=4)
    p.add_argument("--throttle", type=float, default=0.5)
    return p.parse_args()


def generate_phase(args: argparse.Namespace) -> None:
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(args.model)
    args.out.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    arms = args.arms.split(",")
    cells = []
    for pi, prompt in enumerate(PROMPTS):
        prompt_ids = tokenizer.encode(prompt)
        for seed in seeds:
            for arm in arms:
                name = f"p{pi}_s{seed}_{arm if arm == 'baseline' else 'lam' + arm}"
                mx.random.seed(seed)
                summary = {}
                if arm == "baseline":
                    sampler = make_sampler(temp=args.temperature, min_p=args.coherence_floor)
                else:
                    config = SamplerConfig(
                        temperature=args.temperature,
                        entropy_trigger=args.entropy_trigger,
                        entropy_ceiling=args.entropy_ceiling,
                        coherence_floor=args.coherence_floor,
                        lam=float(arm),
                        no_push_ids=eos_ids(tokenizer),
                        seed=seed,
                    )
                    sampler = MLXAntiprobableSampler(model, config=config)
                    sampler.observe_prompt(prompt_ids)
                text = "".join(
                    out.text
                    for out in stream_generate(
                        model, tokenizer, prompt, max_tokens=args.max_tokens, sampler=sampler
                    )
                )
                if arm != "baseline":
                    summary = sampler.telemetry.summary()
                    sampler.telemetry.to_jsonl(args.out / f"{name}.jsonl")
                (args.out / f"{name}.txt").write_text(prompt + text)
                cells.append(
                    {"name": name, "prompt_i": pi, "seed": seed, "arm": arm, "summary": summary}
                )
                print(f"done {name}", flush=True)

    manifest = {"config": {k: str(v) for k, v in vars(args).items()}, "cells": cells}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print("\n== telemetry aggregate (machine arms) ==")
    for arm in arms:
        if arm == "baseline":
            continue
        summaries = [c["summary"] for c in cells if c["arm"] == arm]
        line = f"lam={arm}: "
        for key in ("perplexity", "perturb_rate", "mean_rank_perturbed", "mean_distance_perturbed"):
            m, s = mean_std([x[key] for x in summaries if key in x])
            line += f"{key} {m:.2f}±{s:.2f}  "
        print(line)
    print(f"\nmanifest -> {args.out}/manifest.json")


def novelty_phase(args: argparse.Namespace) -> None:
    manifest = json.loads((args.out / "manifest.json").read_text())
    index = ALIASES.get(args.index, args.index)
    ns = tuple(int(x) for x in args.ns.split(","))
    client = InfiniGramClient(index, throttle_s=args.throttle)

    results: dict[str, list[dict]] = {}
    for cell in manifest["cells"]:
        text = (args.out / f"{cell['name']}.txt").read_text()
        rep = novelty_report(client, text, ns=ns, stride=args.stride)
        results.setdefault(cell["arm"], []).append(rep.summary())
        print(f"measured {cell['name']}: {rep.summary()['novelty_by_n']}", flush=True)
    (args.out / "novelty.json").write_text(json.dumps(results, indent=2))

    print(f"\n== novelty aggregate (index {index}, {client.n_requests} requests) ==")
    base = results.get("baseline", [])
    for arm, reps in results.items():
        line = f"{arm:<10}"
        for n in ns:
            vals = [r["novelty_by_n"][str(n)] for r in reps]
            m, s = mean_std(vals)
            line += f"  novel{n} {m:.3f}±{s:.3f}"
            if arm != "baseline" and base:
                lo, hi = bootstrap_diff_ci(vals, [r["novelty_by_n"][str(n)] for r in base])
                sig = "*" if lo > 0 or hi < 0 else " "
                line += f" (Δ [{lo:+.3f},{hi:+.3f}]{sig})"
        copied = [r["longest_copied_len"] for r in reps]
        line += f"  max_copied {max(copied)}"
        print(line)


def main() -> None:
    args = parse_args()
    if args.novelty:
        novelty_phase(args)
    else:
        if not args.model:
            raise SystemExit("--model is required for the generation phase")
        generate_phase(args)


if __name__ == "__main__":
    main()
