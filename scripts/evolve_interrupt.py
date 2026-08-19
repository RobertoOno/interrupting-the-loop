#!/usr/bin/env python3
"""Battery S: the interruption as a diversity operator INSIDE a selection loop.

FunSearch-style evolution on online bin packing, seed-paired arms with the
same sample budget, plain sampler everywhere (lambda=0; the sampler question
is settled). The arms differ only in the prompt of each sample:

  plain    - population (worst-to-best) + header, as in evolve_verified.py
  angle    - the same, plus ONE 'new angle' comment line inserted between the
             population and the header; the angle cycles through 15 distinct
             lines (never repeating within a generation), the analog of the
             interrupted loop's injected subject change.

Cell = one size-distribution variant (10, as in battery B). Per cell and arm:
G generations x N samples; candidates verified on TRAIN instances; population
keeps the top-K; the champion is scored on held-out TEST instances of the
same variant. Records per generation: n valid, n distinct valid (normalized
body hash, cumulative), best train excess. Pre-registered contrasts are in
docs/PLANO.md (S1: champion held-out gain, angle > plain, one-sided; S2:
cumulative distinct valid candidates, angle > plain, one-sided; S3: escape
generation, two-sided; S4 exploratory).

    python scripts/evolve_interrupt.py --out runs/evointerrupt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.code_exec import run_heuristic_code  # noqa: E402
from creative_machine.domains.binpack import generate_instances  # noqa: E402
from creative_machine.heuristic_gen import CODE_ENTROPY_BAND, HEADER, extract_function  # noqa: E402
from creative_machine.problem_premises import ANGLES, VARIANTS  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402

FIRST_FIT_CODE = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [0.0] * len(remaining)\n"
BEST_FIT_CODE = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [-(r - item) for r in remaining]\n"


def module_doc(lo: float, hi: float) -> str:
    return f'''"""Online bin packing heuristics.

An item arrives; `remaining` lists the residual capacity of each bin the
item currently fits in. Return one score per feasible bin: the item is
placed in the bin with the highest score. If no bin fits, a new bin is
opened. Goal: use as few bins as possible over the whole stream. In this
variant item sizes are drawn uniformly from [{lo:.2f}, {hi:.2f}].
"""

import math
'''


def build_prompt(population, lo, hi, angle: str | None) -> str:
    parts = [module_doc(lo, hi)]
    for i, (code, excess) in enumerate(population):
        renamed = code.replace("def priority(", f"def priority_v{i}(", 1)
        parts.append(f"\n# mean excess over lower bound: {excess:.4f} (lower is better)\n{renamed}")
    if angle is not None:
        parts.append("\n" + angle.strip() + "\n")
    parts.append("\n# Improve on all versions above: lower mean excess than every one of them.\n" + HEADER)
    return "".join(parts)


def norm(code: str) -> str:
    body = "\n".join(l.strip() for l in code.splitlines()[1:] if l.strip() and not l.strip().startswith('"""'))
    return hashlib.md5(re.sub(r"\s+", " ", body).encode()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--gens", type=int, default=8)
    p.add_argument("--samples-per-gen", type=int, default=16)
    p.add_argument("--pop-size", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=200)
    p.add_argument("--n-train", type=int, default=5)
    p.add_argument("--n-test", type=int, default=5)
    p.add_argument("--n-items", type=int, default=100)
    p.add_argument("--variants", type=int, default=len(VARIANTS))
    p.add_argument("--rng-seed", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(str(Path(args.model).expanduser()))
    trigger, ceiling = CODE_ENTROPY_BAND
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "history.json"
    history = json.loads(out_path.read_text()) if out_path.exists() else {}

    for vi in range(args.variants):
        lo, hi = VARIANTS[vi]
        train = generate_instances(args.n_train, args.n_items, np.random.default_rng(100 + vi), lo, hi)
        test = generate_instances(args.n_test, args.n_items, np.random.default_rng(200 + vi), lo, hi)
        bf_train = run_heuristic_code(BEST_FIT_CODE, train)["mean_excess"]
        bf_test = run_heuristic_code(BEST_FIT_CODE, test)["mean_excess"]
        ff_train = run_heuristic_code(FIRST_FIT_CODE, train)["mean_excess"]
        for arm in ("plain", "angle"):
            key = f"v{vi}_{arm}"
            if key in history:
                continue
            population = sorted([(FIRST_FIT_CODE, ff_train), (BEST_FIT_CODE, bf_train)], key=lambda t: -t[1])
            seen_hashes: set[str] = set()
            gens_log = []
            angle_i = 0
            for gen in range(args.gens):
                candidates = []
                n_valid = 0
                for si in range(args.samples_per_gen):
                    angle = None
                    if arm == "angle":
                        angle = ANGLES[angle_i % len(ANGLES)]
                        angle_i += 1
                    prompt = build_prompt(population, lo, hi, angle)
                    config = SamplerConfig(
                        lam=0.0, entropy_trigger=trigger, entropy_ceiling=ceiling,
                        no_push_ids=eos_ids(tokenizer),
                        seed=10_000_000 * args.rng_seed + 100_000 * vi + 1000 * gen + si,
                    )
                    sampler = MLXAntiprobableSampler(model, config=config)
                    sampler.observe_prompt(tokenizer.encode(prompt))
                    completion = "".join(
                        out.text for out in stream_generate(model, tokenizer, prompt,
                                                            max_tokens=args.max_tokens, sampler=sampler))
                    fn = extract_function(completion)
                    if fn is None:
                        continue
                    res = run_heuristic_code(fn, train, timeout_s=15.0)
                    if res.get("ok"):
                        n_valid += 1
                        seen_hashes.add(norm(fn))
                        candidates.append((fn, res["mean_excess"]))
                merged = {code: excess for code, excess in population}
                for code, excess in candidates:
                    merged.setdefault(code, excess)
                population = sorted(merged.items(), key=lambda t: -t[1])[-args.pop_size:]
                gens_log.append({"gen": gen, "valid": n_valid, "distinct_cum": len(seen_hashes),
                                 "best_train_excess": round(population[-1][1], 4)})
                print(f"{key} gen{gen}: valid {n_valid}, distinct_cum {len(seen_hashes)}, best train {population[-1][1]:.4f}", flush=True)
            champion_code, champion_train = population[-1]
            champ = run_heuristic_code(champion_code, test, timeout_s=30.0)
            escape_gen = next((g["gen"] for g in gens_log if g["best_train_excess"] < bf_train - 1e-9), None)
            history[key] = {"variant": vi, "arm": arm, "generations": gens_log,
                            "distinct_total": len(seen_hashes), "escape_gen": escape_gen,
                            "champion_train_excess": round(champion_train, 4),
                            "champion_test_excess": round(champ.get("mean_excess", float("nan")), 4),
                            "bf_train": round(bf_train, 4), "bf_test": round(bf_test, 4),
                            "champion_code": champion_code}
            out_path.write_text(json.dumps(history, indent=1))
            print(f"== {key}: champion test {history[key]['champion_test_excess']} (best fit {bf_test:.4f}), "
                  f"distinct {len(seen_hashes)}, escape {escape_gen}", flush=True)


if __name__ == "__main__":
    main()
