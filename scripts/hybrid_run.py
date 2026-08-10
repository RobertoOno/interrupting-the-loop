#!/usr/bin/env python3
"""Phase 1+2 hybrid: our sampler's surreal sentences as couture raw material.

Phase A (local): generate short pieces with an aggressive sampler config,
measure their novelty windows, extract each piece's most-novel sentence.
Phase B (API): mechanism-first couture develops each seed sentence; the same
harsh judge scores it with known_equivalent.

Hypothesis vs the concept-pair pilot (21/21 recombinations): seeds born
inside the perturbed distribution yield fewer known equivalents.

    python scripts/hybrid_run.py --model ~/models/mlx/OLMo-2-13B-8bit \
        --out runs/hybrid1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.blend import OpenRouterClient, couture_seed, judge  # noqa: E402
from creative_machine.evolve import extract_novel_sentence, looks_factual  # noqa: E402
from creative_machine.novelty import InfiniGramClient, novelty_report  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402
from novelty_check import ALIASES  # noqa: E402

# Personal belief/theory/habit openings pull invention; "encyclopedia" and
# "field guide" style prompts pull recitation (hybrid run 1's contamination).
SEED_PROMPTS = [
    "The lighthouse keeper had one theory about the sea, and it was this:",
    "The apprentice wrote down the workshop's secret rule:",
    "Her grandmother's last superstition was the strangest one:",
    "The night watchman explained the building's oldest habit:",
]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/OLMo-2-13B-8bit")
    p.add_argument("--couturier", default="moonshotai/kimi-k2.6")
    p.add_argument("--judge", default="anthropic/claude-sonnet-5")
    p.add_argument("--seeds-per-prompt", type=int, default=4)
    p.add_argument("--lam", type=float, default=3.0)
    p.add_argument("--max-tokens", type=int, default=90)
    p.add_argument("--novel-n", type=int, default=6)
    p.add_argument("--index", default="olmo13b")
    p.add_argument("--throttle", type=float, default=0.6)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    from mlx_lm import load, stream_generate

    args.out.mkdir(parents=True, exist_ok=True)
    model, tokenizer = load(str(Path(args.model).expanduser()))
    ig = InfiniGramClient(ALIASES.get(args.index, args.index), throttle_s=args.throttle)

    print("== phase A: local surreal seeds ==", flush=True)
    seeds = []
    for pi, prompt in enumerate(SEED_PROMPTS):
        prompt_ids = tokenizer.encode(prompt)
        for rng_seed in range(args.seeds_per_prompt):
            config = SamplerConfig(lam=args.lam, no_push_ids=eos_ids(tokenizer), seed=rng_seed)
            sampler = MLXAntiprobableSampler(model, config=config)
            sampler.observe_prompt(prompt_ids)
            text = prompt + "".join(
                out.text
                for out in stream_generate(
                    model, tokenizer, prompt, max_tokens=args.max_tokens, sampler=sampler
                )
            )
            rep = novelty_report(ig, text, ns=(args.novel_n,), stride=2)
            sentence = extract_novel_sentence(
                text, rep.novel_starts.get(args.novel_n, []), n=args.novel_n
            )
            if sentence is None:
                continue
            if looks_factual(sentence):
                print(f"  p{pi}_r{rng_seed}: DISCARDED as factual: {sentence[:70]}", flush=True)
                continue
            if sentence not in [s["sentence"] for s in seeds]:
                seeds.append({"name": f"p{pi}_r{rng_seed}", "sentence": sentence, "text": text})
                print(f"  p{pi}_r{rng_seed}: {sentence}", flush=True)

    print(f"\n== phase B: mechanism-first couture on {len(seeds)} seeds ==", flush=True)
    client = OpenRouterClient()
    results = []
    for seed in seeds:
        print(f"\n== {seed['name']}: {seed['sentence']}", flush=True)
        cell = dict(seed)
        try:
            cell["blend"] = couture_seed(client, args.couturier, seed["sentence"])
            print(cell["blend"], flush=True)
            verdict = judge(
                client, args.judge, f"surreal seed sentence: {seed['sentence']}", cell["blend"]
            )
            cell["judgment"] = verdict
            print(
                f"-> score {verdict['score']} (c{verdict['coherence']:.0f}/d{verdict['delta_significance']:.0f}/"
                f"v{verdict['value']:.0f}) nearest={verdict['nearest_equivalent']}\n"
                f"   delta: {verdict['novel_delta']}\n   {verdict['verdict']}",
                flush=True,
            )
        except Exception as exc:
            cell["error"] = str(exc)
            print(f"-> cell failed: {exc}", flush=True)
        results.append(cell)
        (args.out / "hybrids.json").write_text(json.dumps(results, indent=2))

    scored = sorted((r for r in results if "judgment" in r), key=lambda r: -r["judgment"]["score"])
    with_delta = [r for r in scored if r["judgment"].get("novel_delta")]
    print(f"\n== {len(scored)} judged; {len(with_delta)} with a genuine novel delta ==")
    for r in scored[:5]:
        print(f"  {r['judgment']['score']:>5}  {r['sentence'][:70]}")
    print(f"tokens used: {client.usage}; infini-gram requests: {ig.n_requests}")


if __name__ == "__main__":
    main()
