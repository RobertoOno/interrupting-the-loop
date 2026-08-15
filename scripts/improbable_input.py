#!/usr/bin/env python3
"""The improbable-input experiment (Roberto's original idea).

Hypothesis: prompts are samples from the same distribution the model was
trained on, so they activate the same regions and yield the same average
creativity. An input no human would write activates configurations no human
has activated. Test: three input arms, one task, one strong model, one harsh
judge — does the judged novel delta rise with the input's improbability?

Arms (all developed by the same model with the same instruction):
  typical    — what most people would type ("give me an innovative idea about X")
  concepts   — two distant concepts (Phase 2 control)
  improbable — a composed context built to sit far from any plausible prompt:
               distant fragments + alien register + non-natural constraints
Input improbability is MEASURED: mean per-token perplexity of the input under
the local base model (Qwen3-8B). This is the independent variable.

    AWS_PROFILE=main-account python scripts/improbable_input.py --n 8 --out runs/improb1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from creative_machine.blend import BedrockClient, develop, judge  # noqa: E402
from creative_machine.concepts import load_concepts, make_word_embedder, sample_distant_pairs  # noqa: E402
from creative_machine.adapters.mlx_lm import _make_embed_fn  # noqa: E402
from creative_machine.evaluator import judge_perplexity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

TYPICAL_TEMPLATES = [
    "Give me an innovative idea related to {a}.",
    "What is a creative new use for {a}?",
    "Suggest a novel invention involving {a}.",
    "Brainstorm an original concept about {a} and {b}.",
]

REGISTERS = [
    "written as a maintenance log entry from a machine that has never been switched off",
    "phrased as a legal deposition given by a tide",
    "in the voice of an inventory of a room that does not exist yet",
    "as instructions left for a successor who will not be human",
    "as marginalia in a cookbook for extinct animals",
    "as a weather report for the inside of a word",
]

CONSTRAINTS = [
    "Every claim must be reversible.",
    "Nothing in it may have a name yet.",
    "It must be true only on the second reading.",
    "The mechanism must run backwards on holidays.",
    "It must cost exactly one memory to use.",
    "It must work worse the more people believe in it.",
]


def build_improbable(rng: np.random.Generator, concepts: list[str], embeddings: np.ndarray) -> str:
    """Compose a context far from any plausible prompt: 3-4 distant concept
    fragments, an alien register, and a non-natural constraint."""
    picks = sample_distant_pairs(embeddings, 2, band=(0.85, 0.99), rng=rng)
    words = []
    for i, j, _ in picks:
        words += [concepts[i], concepts[j]]
    register = REGISTERS[rng.integers(len(REGISTERS))]
    constraint = CONSTRAINTS[rng.integers(len(CONSTRAINTS))]
    return (
        f"Fragments: {words[0]} / {words[1]} / {words[2]} / {words[3]}. "
        f"Register: {register}. Constraint: {constraint}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=8, help="cells per arm")
    p.add_argument("--developer", default="anthropic.claude-opus-5")
    p.add_argument("--judge", default="anthropic.claude-sonnet-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--embed-model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    from mlx_lm import load

    rng = np.random.default_rng(args.seed)
    concepts = load_concepts(ROOT / "data" / "concepts.txt")
    model, tokenizer = load(str(Path(args.embed_model).expanduser()))
    embed_words = make_word_embedder(
        _make_embed_fn(model), lambda w: tokenizer.encode(w, add_special_tokens=False)
    )
    embeddings = embed_words(concepts)

    def input_ppl(text: str) -> float:
        # perplexity of the whole input as a continuation of an empty prompt
        return judge_perplexity(model, tokenizer, "\n" + text, "\n")["judge_ppl"]

    cells = []
    for k in range(args.n):
        i, j, dist = sample_distant_pairs(embeddings, 1, band=(0.75, 0.95), rng=rng)[0]
        a, b = concepts[i], concepts[j]
        typical = TYPICAL_TEMPLATES[k % len(TYPICAL_TEMPLATES)].format(a=a, b=b)
        cells.append({"arm": "typical", "k": k, "input": typical})
        cells.append({"arm": "concepts", "k": k, "input": f"Concepts: {a} + {b}"})
        cells.append({"arm": "improbable", "k": k, "input": build_improbable(rng, concepts, embeddings)})

    for c in cells:
        c["input_ppl"] = round(input_ppl(c["input"]), 2)
    print("== input perplexity by arm (independent variable) ==")
    for arm in ("typical", "concepts", "improbable"):
        v = [c["input_ppl"] for c in cells if c["arm"] == arm]
        print(f"  {arm:<11} mean {np.mean(v):8.1f}  min {min(v):8.1f}  max {max(v):8.1f}")

    client = BedrockClient(aws_region=args.region)
    args.out.mkdir(parents=True, exist_ok=True)
    for c in cells:
        print(f"\n== {c['arm']} k={c['k']} ppl={c['input_ppl']}: {c['input'][:90]}", flush=True)
        try:
            c["idea"] = develop(client, args.developer, c["input"])
            print(c["idea"][:400], flush=True)
            v = judge(client, args.judge, f"input context: {c['input']}", c["idea"])
            c["judgment"] = v
            print(
                f"-> score {v['score']} (c{v['coherence']:.0f}/d{v['delta_significance']:.0f}/v{v['value']:.0f})"
                f" nearest={v['nearest_equivalent']}\n   delta: {v['novel_delta']}",
                flush=True,
            )
        except Exception as exc:
            c["error"] = str(exc)
            print(f"-> cell failed: {exc}", flush=True)
        (args.out / "cells.json").write_text(json.dumps(cells, indent=2))

    print("\n== results by arm ==")
    for arm in ("typical", "concepts", "improbable"):
        js = [c["judgment"] for c in cells if c["arm"] == arm and "judgment" in c]
        if not js:
            continue
        d = [j["delta_significance"] for j in js]
        s = [j["score"] for j in js]
        print(
            f"  {arm:<11} n={len(js)}  delta_signif {np.mean(d):.2f}±{np.std(d):.2f} (max {max(d):.0f})"
            f"  score {np.mean(s):.2f} (max {max(s):.2f})"
        )
    xs = [c["input_ppl"] for c in cells if "judgment" in c]
    ys = [c["judgment"]["delta_significance"] for c in cells if "judgment" in c]
    if len(xs) > 3:
        r = np.corrcoef(np.log(xs), ys)[0, 1]
        print(f"  corr(log input_ppl, delta_significance) = {r:+.3f}  (n={len(xs)})")
    print(f"tokens: {client.usage}")


if __name__ == "__main__":
    main()
