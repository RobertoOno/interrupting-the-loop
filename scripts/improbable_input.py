#!/usr/bin/env python3
"""The improbable-input experiment (Roberto's original idea) — definitive form.

Hypothesis: prompts are samples from the same distribution the model was
trained on, so they activate the same regions and yield the same average
creativity. An input no human would write activates configurations no human
has activated. One task, one developer, one harsh judge; only the input
differs across arms:

  typical      what most people would type ("give me an innovative idea about X")
  concepts     two distant concepts (Phase 2 control)
  improbable   composed context: distant fragments + alien register + constraint
  fragments    the same composed context WITHOUT the register (ablation)
  register     the typical request in the alien register, no fragments (ablation)

Independent variable: semantic improbability = distance of the input from a
corpus of real prompts (contrastive sentence embeddings; centroid + kNN).
Token perplexity is also recorded (the pilot showed it ranks backwards).
Each idea is judged k times; the median verdict is used.

    AWS_PROFILE=main-account python scripts/improbable_input.py --n 30 --k 3 --out runs/improb2
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from creative_machine.adapters.mlx_lm import _make_embed_fn  # noqa: E402
from creative_machine.blend import BedrockClient, develop, judge  # noqa: E402
from creative_machine.concepts import load_concepts, make_word_embedder, sample_distant_pairs  # noqa: E402
from creative_machine.evaluator import judge_perplexity  # noqa: E402
from creative_machine.prompt_space import PromptSpace, SentenceEmbedder  # noqa: E402
from creative_machine.stats import bootstrap_diff_ci  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALPACA = (
    Path.home()
    / ".cache/huggingface/hub/datasets--tatsu-lab--alpaca/snapshots/"
    "dce01c9b08f87459cf36a430d809084718273017/data/train-00000-of-00001-a09b74b3ef9c3b56.parquet"
)

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

ARMS = ("typical", "concepts", "improbable", "fragments", "register")


def make_cells(k_index: int, rng: np.random.Generator, concepts: list[str], embeddings: np.ndarray) -> list[dict]:
    i, j, _ = sample_distant_pairs(embeddings, 1, band=(0.75, 0.95), rng=rng)[0]
    a, b = concepts[i], concepts[j]
    picks = sample_distant_pairs(embeddings, 2, band=(0.85, 0.99), rng=rng)
    frags = [concepts[x] for pair in picks for x in pair[:2]]
    register = REGISTERS[rng.integers(len(REGISTERS))]
    constraint = CONSTRAINTS[rng.integers(len(CONSTRAINTS))]
    typical = TYPICAL_TEMPLATES[k_index % len(TYPICAL_TEMPLATES)].format(a=a, b=b)
    frag_text = f"Fragments: {frags[0]} / {frags[1]} / {frags[2]} / {frags[3]}."
    return [
        {"arm": "typical", "k": k_index, "input": typical},
        {"arm": "concepts", "k": k_index, "input": f"Concepts: {a} + {b}"},
        {"arm": "improbable", "k": k_index, "input": f"{frag_text} Register: {register}. Constraint: {constraint}"},
        {"arm": "fragments", "k": k_index, "input": f"{frag_text} Constraint: {constraint}"},
        {"arm": "register", "k": k_index, "input": f"{typical} Register: {register}."},
    ]


def median_judgment(verdicts: list[dict]) -> dict:
    """Per-field median across k judgments; text fields from the median-score verdict."""
    scores = [v["score"] for v in verdicts]
    ref = sorted(verdicts, key=lambda v: v["score"])[len(verdicts) // 2]
    out = dict(ref)
    for key in ("coherence", "delta_significance", "value", "score"):
        out[key] = statistics.median(v[key] for v in verdicts)
    out["k"] = len(verdicts)
    out["score_spread"] = round(max(scores) - min(scores), 2)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=30, help="cells per arm")
    p.add_argument("--k", type=int, default=3, help="judgments per cell")
    p.add_argument("--developer", default="anthropic.claude-opus-5")
    p.add_argument("--fallback-developer", default="anthropic.claude-opus-4-8")
    p.add_argument("--judge", default="anthropic.claude-sonnet-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--embed-model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--corpus-size", type=int, default=10000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    import pyarrow.parquet as pq
    from mlx_lm import load

    rng = np.random.default_rng(args.seed)
    concepts = load_concepts(ROOT / "data" / "concepts.txt")
    model, tokenizer = load(str(Path(args.embed_model).expanduser()))
    embed_words = make_word_embedder(
        _make_embed_fn(model), lambda w: tokenizer.encode(w, add_special_tokens=False)
    )
    concept_emb = embed_words(concepts)

    cells = []
    for k in range(args.n):
        cells.extend(make_cells(k, rng, concepts, concept_emb))

    # Independent variables: semantic distance from real prompts (+ ppl for the record)
    st = SentenceEmbedder()
    table = pq.read_table(ALPACA)
    idx = np.random.default_rng(0).choice(table.num_rows, size=args.corpus_size, replace=False)
    corpus = [table.column("instruction")[int(i)].as_py() for i in idx]
    space = PromptSpace.build(st, corpus, cache=ROOT / "runs" / f"prompt_space_alpaca{args.corpus_size}_mpnet.npy")
    for c, d in zip(cells, space.distances(st([c["input"] for c in cells]), k=10)):
        c.update({k2: round(v, 4) for k2, v in d.items()})
        c["input_ppl"] = round(judge_perplexity(model, tokenizer, "\n" + c["input"], "\n")["judge_ppl"], 2)
    print("== independent variables by arm ==")
    for arm in ARMS:
        sub = [c for c in cells if c["arm"] == arm]
        print(
            f"  {arm:<11} knn_dist {np.mean([c['knn_distance'] for c in sub]):.3f}"
            f"  centroid_dist {np.mean([c['centroid_distance'] for c in sub]):.3f}"
            f"  ppl {np.mean([c['input_ppl'] for c in sub]):7.1f}"
        )

    client = BedrockClient(aws_region=args.region)
    args.out.mkdir(parents=True, exist_ok=True)
    for c in cells:
        label = f"{c['arm']} k={c['k']}"
        try:
            try:
                c["idea"] = develop(client, args.developer, c["input"])
                c["developer"] = args.developer
            except RuntimeError as exc:
                if "refus" not in str(exc):
                    raise
                c["idea"] = develop(client, args.fallback_developer, c["input"])
                c["developer"] = args.fallback_developer
            verdicts = [judge(client, args.judge, f"input context: {c['input']}", c["idea"]) for _ in range(args.k)]
            c["judgments"] = verdicts
            c["judgment"] = median_judgment(verdicts)
            j = c["judgment"]
            print(f"{label:<16} score {j['score']:.2f} delta {j['delta_significance']:.0f} (spread {j['score_spread']})", flush=True)
        except Exception as exc:
            c["error"] = str(exc)
            print(f"{label:<16} FAILED: {exc}", flush=True)
        (args.out / "cells.json").write_text(json.dumps(cells, indent=2))

    print("\n== results by arm (median of k judgments per cell) ==")
    by_arm = {arm: [c["judgment"] for c in cells if c["arm"] == arm and "judgment" in c] for arm in ARMS}
    base = [j["delta_significance"] for j in by_arm["typical"]]
    for arm in ARMS:
        js = by_arm[arm]
        if not js:
            continue
        d = [j["delta_significance"] for j in js]
        s = [j["score"] for j in js]
        line = f"  {arm:<11} n={len(js):<3} delta {np.mean(d):.2f}±{np.std(d):.2f}  score {np.mean(s):.2f} (max {max(s):.2f})"
        if arm != "typical" and base:
            lo, hi = bootstrap_diff_ci(d, base)
            line += f"  Δdelta vs typical [{lo:+.2f},{hi:+.2f}]{'*' if lo > 0 or hi < 0 else ''}"
        print(line)
    judged = [c for c in cells if "judgment" in c]
    y = [c["judgment"]["delta_significance"] for c in judged]
    for key in ("knn_distance", "centroid_distance", "input_ppl"):
        x = [c[key] for c in judged]
        if key == "input_ppl":
            x = list(np.log(x))
        print(f"  corr({key}, delta) = {np.corrcoef(x, y)[0, 1]:+.3f}  (n={len(x)})")
    print(f"tokens: {client.usage}")


if __name__ == "__main__":
    main()
