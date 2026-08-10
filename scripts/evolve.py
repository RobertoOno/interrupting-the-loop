#!/usr/bin/env python3
"""The selection loop (roadmap item 6): survivors seed the next generation.

Each generation: generate from the current seed prompts, run the funnel
(collapse filter + cross-family judge + novelty), take the top survivors,
extract each one's most-novel sentence, and use those sentences as the next
generation's prompts. Lineage is recorded — the genealogy is part of the
artifact.

    python scripts/evolve.py --model ~/models/mlx/OLMo-2-13B-8bit \
        --judge ~/models/mlx/Qwen3-8B-Base-8bit --gens 3 --out runs/evo1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.evaluator import (  # noqa: E402
    entropy_drop_score,
    judge_perplexity,
    record_entropies,
)
from creative_machine.evolve import extract_novel_sentence  # noqa: E402
from creative_machine.novelty import InfiniGramClient, novelty_report  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402
from novelty_check import ALIASES  # noqa: E402
from run_experiment import PROMPTS  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--judge", required=True)
    p.add_argument("--gens", type=int, default=3)
    p.add_argument("--seeds-per", type=int, default=2, help="RNG seeds per prompt seed")
    p.add_argument("--top", type=int, default=3, help="survivors seeding the next generation")
    p.add_argument("--lam", type=float, default=2.0)
    p.add_argument("--max-tokens", type=int, default=150)
    p.add_argument("--novel-n", type=int, default=6)
    p.add_argument("--stride", type=int, default=3)
    p.add_argument("--index", default="olmo13b")
    p.add_argument("--throttle", type=float, default=0.6)
    p.add_argument("--collapse-threshold", type=float, default=0.35)
    p.add_argument("--judge-ceiling", type=float, default=10.0)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(args.model)
    judge, judge_tok = load(args.judge)
    client = InfiniGramClient(ALIASES.get(args.index, args.index), throttle_s=args.throttle)
    args.out.mkdir(parents=True, exist_ok=True)

    seeds = list(PROMPTS)
    lineage = []
    for gen in range(args.gens):
        print(f"\n=== generation {gen}: {len(seeds)} seeds ===", flush=True)
        cells = []
        for si, seed_prompt in enumerate(seeds):
            prompt_ids = tokenizer.encode(seed_prompt)
            for rng_seed in range(args.seeds_per):
                name = f"g{gen}_s{si}_r{rng_seed}"
                config = SamplerConfig(
                    lam=args.lam,
                    no_push_ids=eos_ids(tokenizer),
                    seed=rng_seed,
                )
                sampler = MLXAntiprobableSampler(model, config=config)
                sampler.observe_prompt(prompt_ids)
                text = seed_prompt + "".join(
                    out.text
                    for out in stream_generate(
                        model, tokenizer, seed_prompt, max_tokens=args.max_tokens, sampler=sampler
                    )
                )
                (args.out / f"{name}.txt").write_text(text)

                collapse = entropy_drop_score(record_entropies(sampler.telemetry.records))
                jp = judge_perplexity(judge, judge_tok, text, seed_prompt)["judge_ppl"]
                rep = novelty_report(client, text, ns=(args.novel_n,), stride=args.stride)
                cell = {
                    "name": name,
                    "gen": gen,
                    "seed_prompt": seed_prompt,
                    "collapse": round(collapse, 3),
                    "judge_ppl": round(jp, 2),
                    "novelty": rep.novelty_by_n.get(args.novel_n, 0.0),
                    "novel_starts": rep.novel_starts.get(args.novel_n, []),
                    "text": text,
                }
                cells.append(cell)
                print(
                    f"  {name}: novelty {cell['novelty']:.2f} collapse {collapse:.2f} judge {jp:.1f}",
                    flush=True,
                )

        survivors = sorted(
            (
                c
                for c in cells
                if c["collapse"] < args.collapse_threshold and c["judge_ppl"] < args.judge_ceiling
            ),
            key=lambda c: -c["novelty"],
        )[: args.top]
        print(f"  survivors: {[c['name'] for c in survivors]}", flush=True)

        next_seeds = []
        for c in survivors:
            sentence = extract_novel_sentence(c["text"], c["novel_starts"], n=args.novel_n)
            c["next_seed"] = sentence
            if sentence and sentence not in next_seeds:
                next_seeds.append(sentence)
        lineage.extend({k: v for k, v in c.items() if k != "novel_starts"} for c in cells)
        if not next_seeds:
            print("  no viable seeds extracted; stopping early", flush=True)
            break
        seeds = next_seeds

    (args.out / "lineage.json").write_text(json.dumps(lineage, indent=2))
    print(f"\nlineage -> {args.out}/lineage.json ({client.n_requests} API requests)")
    print("\n== final seeds (the evolved deviations) ==")
    for s in seeds:
        print(f"  {s}")


if __name__ == "__main__":
    main()
