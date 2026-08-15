#!/usr/bin/env python3
"""The full circle: verified evolution with two competing variation operators.

FunSearch-style loop per arm (plain lam=0 vs anti-probable, seed-paired,
same budget): the prompt carries the current top-K verified heuristics,
each generation samples new candidates, reality scores them on TRAIN
instances, and the population keeps the best. The champion is finally
reported on held-out TEST instances. Curves per generation tell whether
the anti-probable operator finds what plain sampling does not.

    python scripts/evolve_verified.py --out runs/evoverify1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np  # noqa: E402

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.code_exec import run_heuristic_code  # noqa: E402
from creative_machine.domains.binpack import best_fit, evaluate, first_fit, generate_instances  # noqa: E402
from creative_machine.heuristic_gen import (  # noqa: E402
    CODE_ENTROPY_BAND,
    build_evolution_prompt,
    extract_function,
)
from generate_mlx import eos_ids  # noqa: E402

FIRST_FIT_CODE = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [0.0] * len(remaining)\n"
BEST_FIT_CODE = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [-(r - item) for r in remaining]\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--gens", type=int, default=5)
    p.add_argument("--samples-per-gen", type=int, default=20)
    p.add_argument("--pop-size", type=int, default=3)
    p.add_argument("--lam", type=float, default=1.5)
    p.add_argument("--max-tokens", type=int, default=180)
    p.add_argument("--runs", type=int, default=1, help="independent runs per arm (§8-B: >=5)")
    p.add_argument("--n-train", type=int, default=20)
    p.add_argument("--n-test", type=int, default=40)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(str(Path(args.model).expanduser()))
    train = generate_instances(args.n_train, 120, np.random.default_rng(99))
    test = generate_instances(args.n_test, 120, np.random.default_rng(777))
    bf_train = evaluate(best_fit, train)["mean_excess"]
    bf_test = evaluate(best_fit, test)["mean_excess"]
    print(f"best-fit excess: train {bf_train:.4f}, test {bf_test:.4f}", flush=True)

    trigger, ceiling = CODE_ENTROPY_BAND
    args.out.mkdir(parents=True, exist_ok=True)
    history: dict[str, list] = {}

    arms = [(0.0, "plain"), (args.lam, "antiprob")]
    for run in range(args.runs):
      for arm_lam, arm_name in arms:
        arm = f"{arm_name}_r{run}" if args.runs > 1 else arm_name
        ff = run_heuristic_code(FIRST_FIT_CODE, train)["mean_excess"]
        bf = run_heuristic_code(BEST_FIT_CODE, train)["mean_excess"]
        population = sorted(
            [(FIRST_FIT_CODE, ff), (BEST_FIT_CODE, bf)], key=lambda t: -t[1]
        )  # worst first, best last (recency)
        arm_history = []
        n_valid_total = 0
        for gen in range(args.gens):
            prompt = build_evolution_prompt(population)
            prompt_ids = tokenizer.encode(prompt)
            candidates = []
            for seed in range(args.samples_per_gen):
                config = SamplerConfig(
                    lam=arm_lam,
                    entropy_trigger=trigger,
                    entropy_ceiling=ceiling,
                    no_push_ids=eos_ids(tokenizer),
                    seed=100_000 * run + 1000 * gen + seed,
                )
                sampler = MLXAntiprobableSampler(model, config=config)
                sampler.observe_prompt(prompt_ids)
                completion = "".join(
                    out.text
                    for out in stream_generate(
                        model, tokenizer, prompt, max_tokens=args.max_tokens, sampler=sampler
                    )
                )
                fn = extract_function(completion)
                if fn is None:
                    continue
                res = run_heuristic_code(fn, train, timeout_s=15.0)
                if res.get("ok"):
                    candidates.append((fn, res["mean_excess"]))
            n_valid_total += len(candidates)
            merged = {code: excess for code, excess in population}
            for code, excess in candidates:
                merged.setdefault(code, excess)
            population = sorted(merged.items(), key=lambda t: -t[1])[-args.pop_size :]
            best_now = population[-1][1]
            arm_history.append(
                {"gen": gen, "valid": len(candidates), "best_train_excess": round(best_now, 4)}
            )
            print(f"{arm} gen{gen}: {len(candidates)} valid, best train excess {best_now:.4f}", flush=True)

        champion_code, champion_train = population[-1]
        champ_test = run_heuristic_code(champion_code, test, timeout_s=30.0)
        escape_gen = next(
            (g["gen"] for g in arm_history if g["best_train_excess"] < bf_train - 1e-9), None
        )
        history[arm] = {
            "arm": arm_name,
            "run": run,
            "generations": arm_history,
            "n_valid_total": n_valid_total,
            "escape_gen": escape_gen,
            "champion_train_excess": round(champion_train, 4),
            "champion_test_excess": round(champ_test.get("mean_excess", float("nan")), 4),
            "champion_code": champion_code,
        }
        (args.out / "history.json").write_text(json.dumps(history, indent=2))

    print(f"\n== verified evolution ({args.runs} runs x {args.gens} gens x {args.samples_per_gen}/arm) ==")
    print(f"  best-fit excess: train {bf_train:.4f}, test {bf_test:.4f}")
    for arm, h in history.items():
        beat = "BEATS best-fit on test" if h["champion_test_excess"] < bf_test - 1e-9 else "ties/loses on test"
        esc = f"escaped gen {h['escape_gen']}" if h["escape_gen"] is not None else "never escaped"
        print(
            f"  {arm:<12} {esc:<16} champion train {h['champion_train_excess']:.4f} "
            f"test {h['champion_test_excess']:.4f} ({beat}); valid {h['n_valid_total']}"
        )
    if args.runs > 1:
        for arm_name in ("plain", "antiprob"):
            hs = [h for h in history.values() if h["arm"] == arm_name]
            escapes = [h["escape_gen"] for h in hs if h["escape_gen"] is not None]
            tests = [h["champion_test_excess"] for h in hs]
            print(
                f"  {arm_name:<9} escaped {len(escapes)}/{len(hs)} runs"
                f" (gens {escapes}); test excess mean {np.mean(tests):.4f}"
                f" min {np.min(tests):.4f}"
            )
    print(f"history -> {args.out}/history.json")


if __name__ == "__main__":
    main()
