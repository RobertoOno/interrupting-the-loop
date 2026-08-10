#!/usr/bin/env python3
"""Phase 2 pipeline: distant concept pairs -> API couturier -> API judge.

    python scripts/blend_run.py --n-pairs 12 --out runs/blend1 \
        --embed-model ~/models/mlx/OLMo-2-13B-8bit

Requires an OpenRouter key (env OPENROUTER_API_KEY or
~/.config/creative-machine/openrouter_key).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine.adapters.mlx_lm import _make_embed_fn  # noqa: E402
from creative_machine.blend import OpenRouterClient, couture, judge  # noqa: E402
from creative_machine.concepts import (  # noqa: E402
    load_concepts,
    make_word_embedder,
    sample_distant_pairs,
)

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--concepts", type=Path, default=ROOT / "data" / "concepts.txt")
    p.add_argument("--embed-model", default="~/models/mlx/OLMo-2-13B-8bit")
    p.add_argument("--couturier", default="moonshotai/kimi-k2.6")
    p.add_argument("--judge", default="anthropic/claude-sonnet-5")
    p.add_argument("--n-pairs", type=int, default=12)
    p.add_argument("--band", default="0.75,0.95")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    import numpy as np
    from mlx_lm import load

    concepts = load_concepts(args.concepts)
    print(f"{len(concepts)} concepts; embedding with the house ruler...", flush=True)
    model, tokenizer = load(str(Path(args.embed_model).expanduser()))
    embed_words = make_word_embedder(
        _make_embed_fn(model), lambda w: tokenizer.encode(w, add_special_tokens=False)
    )
    embeddings = embed_words(concepts)

    band = tuple(float(x) for x in args.band.split(","))
    pairs = sample_distant_pairs(
        embeddings, args.n_pairs, band=band, rng=np.random.default_rng(args.seed)
    )

    client = OpenRouterClient()
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for i, j, dist in pairs:
        a, b = concepts[i], concepts[j]
        print(f"\n== {a} + {b} (dist {dist:.3f})", flush=True)
        blend_text = couture(client, args.couturier, a, b)
        print(blend_text, flush=True)
        verdict = judge(client, args.judge, a, b, blend_text)
        print(
            f"-> score {verdict['score']} (c{verdict['coherence']:.0f}/s{verdict['surprise']:.0f}/"
            f"v{verdict['value']:.0f}) known={verdict['known_equivalent']}: {verdict['verdict']}",
            flush=True,
        )
        results.append(
            {"a": a, "b": b, "distance": dist, "blend": blend_text, "judgment": verdict}
        )

    results.sort(key=lambda r: -r["judgment"]["score"])
    (args.out / "blends.json").write_text(json.dumps(results, indent=2))
    print(f"\n== top blends -> {args.out}/blends.json ==")
    for r in results[:5]:
        print(f"  {r['judgment']['score']:>5}  {r['a']} + {r['b']}")
    print(f"tokens used: {client.usage}")


if __name__ == "__main__":
    main()
