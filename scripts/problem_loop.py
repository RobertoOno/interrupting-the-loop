#!/usr/bin/env python3
"""Battery V: the verifier inside the loop.

The bin-packing notebook of battery B, generated in chunks; whenever the
stream completes a `def priority...` function (closed by a dedented line),
the harness scores it on the TRAINING instances at once and injects the
verdict into the notebook as a comment. The `fbagenda` arm additionally
injects, every ~300 generated tokens, a deterministic scoreboard (schematic
memory of results + a value-anchored open question). No LLM judge anywhere:
progression is measured by the verifier (improvements on the notebook's own
training best); the ceiling by the held-out best. Injected comments never
match the function extractor, so no window bookkeeping is needed.

    python scripts/problem_loop.py --arm fb300 --rng-seed 0 --out runs/dream_v/fb300_r0
"""

from __future__ import annotations

import argparse
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
from creative_machine.problem_premises import VARIANTS, premise  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402

BEST_FIT_CODE = "def priority(item: float, remaining: list[float]) -> list[float]:\n    return [-(r - item) for r in remaining]\n"
HEAD = re.compile(r"^def (priority\w*)\(item: float, remaining: list\[float\]\) -> list\[float\]:\s*$")


def inside_open_function(text: str) -> bool:
    """True when the text currently ends inside a priority function that has
    not yet been closed by a non-blank dedented line (do not inject there)."""
    lines = text.splitlines()
    open_fn = False
    for ln in lines:
        if HEAD.match(ln):
            open_fn = True
        elif open_fn and ln.strip() != "" and not ln.startswith((" ", "\t")):
            open_fn = False
    return open_fn


def closed_functions(text: str) -> list[tuple[str, str]]:
    """(name, source) of every COMPLETE priority function: body followed by a
    non-blank dedented line (so a function still being written never counts)."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i])
        if not m:
            i += 1; continue
        name = m.group(1)
        body, j = [], i + 1
        while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith((" ", "\t"))):
            body.append(lines[j]); j += 1
        closed = j < len(lines) and lines[j].strip() != ""
        while body and body[-1].strip() == "":
            body.pop()
        if closed and body and name not in ("priority_first_fit", "priority_best_fit"):
            out.append((name, "def priority(item: float, remaining: list[float]) -> list[float]:\n" + "\n".join(body) + "\n"))
        i = j
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--arm", choices=["fb300", "fbagenda"], required=True)
    p.add_argument("--rng-seed", type=int, default=0)
    p.add_argument("--tokens", type=int, default=4500)
    p.add_argument("--chunk", type=int, default=128)
    p.add_argument("--variants", type=int, default=len(VARIANTS))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    from mlx_lm import load, stream_generate

    model, tokenizer = load(str(Path(args.model).expanduser()))
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "cells.json"
    cells = json.loads(out_path.read_text()) if out_path.exists() else {}

    for vi in range(args.variants):
        key = f"v{vi}"
        if key in cells:
            continue
        lo, hi = VARIANTS[vi]
        train = generate_instances(5, 100, np.random.default_rng(100 + vi), lo, hi)
        bf_train = run_heuristic_code(BEST_FIT_CODE, train)["mean_excess"]
        text = premise(lo, hi)
        n_gen = 0
        seen: set[str] = set()          # function sources already verified
        results = []                    # (name, train_excess or None, error)
        best_train = None
        improvements = 0
        v_counter = 0
        next_board = 300
        pending = ""
        cfg = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=eos_ids(tokenizer),
                            seed=args.rng_seed * 1000 + vi, repetition_window=512, repetition_penalty=1.15)
        while n_gen < args.tokens:
            sampler = MLXAntiprobableSampler(model, config=cfg)
            sampler.observe_prompt(tokenizer.encode(text))
            chunk = "".join(o.text for o in stream_generate(model, tokenizer, text,
                                                            max_tokens=min(args.chunk, args.tokens - n_gen), sampler=sampler))
            if not chunk:
                break
            text += chunk
            n_gen += min(args.chunk, args.tokens - n_gen)
            # event: any newly closed function -> verify, queue the verdict
            inject = pending; pending = ""
            for name, src in closed_functions(text):
                if src in seen:
                    continue
                seen.add(src)
                v_counter += 1
                res = run_heuristic_code(src, train, timeout_s=15.0)
                if res.get("ok"):
                    x = res["mean_excess"]
                    new_best = best_train is None or x < best_train - 1e-9
                    if new_best:
                        if best_train is not None:
                            improvements += 1
                        best_train = x
                    verdict = ("new best of this notebook" if new_best else "no improvement")
                    cmp_bf = "better than best fit" if x < bf_train - 1e-9 else "worse than best fit" if x > bf_train + 1e-9 else "equal to best fit"
                    inject += (f"\n\n# Verifier: {name} scored mean excess {x:.4f} on the training instances "
                               f"({cmp_bf}, {bf_train:.4f}); {verdict}.\n")
                    results.append({"name": name, "train_excess": x, "src": src})
                else:
                    inject += f"\n\n# Verifier: {name} failed: {str(res.get('error', ''))[:80]}.\n"
                    results.append({"name": name, "train_excess": None, "src": src, "error": str(res.get("error", ""))[:80]})
            if args.arm == "fbagenda" and n_gen >= next_board and not inside_open_function(text):
                next_board += 300
                ok = [r for r in results if r["train_excess"] is not None]
                best_s = f"the best is {min(ok, key=lambda r: r['train_excess'])['name']} at {best_train:.4f}" if ok else "none has run yet"
                inject += (f"\n\n# So far: {len(results)} functions tried, {len(ok)} ran; {best_s}; best fit sits at {bf_train:.4f}."
                           f"\n# Open question: what structure would beat best fit on items from [{lo:.2f}, {hi:.2f}]?\n")
            if inject and inside_open_function(text):
                pending = inject          # hold the verdicts until the model closes the function
            else:
                text += inject
        if pending:
            text += pending
        (args.out / f"{key}.txt").write_text(text)
        cells[key] = {"variant": vi, "arm": args.arm, "rng": args.rng_seed, "n_functions": len(results),
                      "n_ok": sum(1 for r in results if r["train_excess"] is not None),
                      "best_train": best_train, "improvements": improvements, "bf_train": round(bf_train, 4),
                      "results": [{k: v for k, v in r.items() if k != "src"} for r in results],
                      "sources": [r["src"] for r in results]}
        out_path.write_text(json.dumps(cells, indent=1))
        print(f"{args.arm} r{args.rng_seed} v{vi}: {len(results)} fns, {cells[key]['n_ok']} ok, "
              f"best train {best_train}, improvements {improvements} (bf {bf_train:.4f})", flush=True)


if __name__ == "__main__":
    main()
