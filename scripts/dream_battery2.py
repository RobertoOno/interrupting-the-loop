#!/usr/bin/env python3
"""Battery 2 — what is the interruption made of? And does it hold on a second
generator family? Seeds x conditions, resumable, overnight-safe, no judge in
the loop (windows are judged offline by dream_rejudge_surprise.py).

    python scripts/dream_battery2.py --battery b2 --out runs/dream_b2
    python scripts/dream_battery2.py --battery fam8b --out runs/dream_fam8b \
        --model ~/models/mlx/Qwen3-8B-Base-8bit

Conditions (all λ=0, bridge=0, no forgetting):
  bare_habit    bare + the scaffold's habituation only, no interruption   [confound control]
  clock_reenc   clock 150, inject a return-to-the-premise stitch          [content]
  clock_premise clock 150, inject the opening line itself                 [content]
  clock_self    clock 150, inject a window of the stream's own past       [content]
  sal_reenc     salience-timed re-encounter (event injects the stitch)    [timing]
  clock75/300/600  neutral subject change at other frequencies            [frequency]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))
from dream_definitive import SEEDS, thermal  # noqa: E402

# Confirmatory replication (external review, P1): ten NEW premises, written on
# 2026-08-18 before any battery-3 result was seen, never used before; a
# different RNG seed (1). Pre-registered contrasts in docs/PLANO.md.
NEW_SEEDS = [
    "The bridge had been built for a river that never came.",
    "On the last day of every month the town's dogs walked, together, to the station.",
    "She had learned to read from a book with the ending torn out, and never quite recovered.",
    "The orchard remembered the fruit better than the family did.",
    "In the museum of small mistakes, his was the only one under glass.",
    "The tailor measured everyone twice: once for the coat, once for whatever came after it.",
    "The village had one telephone, and it rang only for people who had already left.",
    "Every winter the lake returned a different object from the year the boat sank.",
    "The choir kept singing a verse nobody had written.",
    "His grandmother had a word for the hour before a storm, and no one else did.",
]

# Second genre (external review, P1): expository / essayistic openings, not narrative;
# written 2026-08-18 evening, never used before.
GENRE_SEEDS = [
    "The history of the umbrella is mostly a history of people refusing to carry one.",
    "Every map of the ocean floor is out of date by the time it is printed.",
    "Salt was once the reason cities existed where they do.",
    "Most of what a library holds has not been read in fifty years, and that is its function.",
    "The first clocks did not tell time; they told monks when to pray.",
    "There is no word for the smell of rain on hot stone in most languages, and yet everyone knows it.",
    "A bridge is a promise made by one generation to another.",
    "The oldest recipes are lists of ingredients with no quantities.",
    "Whistled languages exist wherever valleys are deep and neighbors are far.",
    "Nobody has ever measured how much of a city is doors.",
]

BATTERIES = {
    # name -> (control, extra args)
    # the interrupted loop over a problem with a verifier (use --premises problem): 10 bin-packing variants
    "problem": [
        ("plain", "problem_plain", []),
        ("angle300", "problem_angle", ["--clock-every", "300"]),
        ("reset300", "problem_reset", ["--clock-every", "300"]),
        ("sham300", "problem_sham", ["--clock-every", "300"]),
    ],
    # reset vs preserved vs sham at period 300 on another model (use --model; pairs with that model's bare_habit cells)
    "reset_ladder": [
        ("clock300", "bare_reseed", ["--clock-every", "300"]),
        ("reset_reseed300", "reset_reseed", ["--clock-every", "300"]),
        ("sham_break300", "sham_break", ["--clock-every", "300"]),
    ],
    # DREAM's Review with a gate that opens: judge-gated interruption at period 150 (Opus reads the last 128 tokens
    # before each scheduled reseed; a find, surprise >= 5 and coherence >= 5, is left to run)
    "gate": [
        ("judge_gate150", "judge_gate", ["--clock-every", "150", "--gate-threshold", "5"]),
    ],
    # paper 2, battery M: schematic memory and return-to-conflict (period 300)
    "m": [
        ("schema300", "schema_reseed", ["--clock-every", "300"]),
        ("anomaly300", "anomaly_reseed", ["--clock-every", "300"]),
    ],
    # M+: memory + agenda combined in one injection
    "mplus": [
        ("agenda300", "agenda_reseed", ["--clock-every", "300"]),
    ],
    # second genre on the main generator (use --premises genre)
    "genre": [
        ("bare_habit", "bare_habit", []),
        ("clock300", "bare_reseed", ["--clock-every", "300"]),
        ("reset_reseed300", "reset_reseed", ["--clock-every", "300"]),
    ],
    # confirmatory replication of the period-300 contrast on new premises (use --premises new --rng-seed 1)
    "confirm": [
        ("bare_habit", "bare_habit", []),
        ("clock300", "bare_reseed", ["--clock-every", "300"]),
        ("sham_break300", "sham_break", ["--clock-every", "300"]),
        ("nohabit300", "nohabit_reseed", ["--clock-every", "300"]),
        ("reset_reseed300", "reset_reseed", ["--clock-every", "300"]),
    ],
    "b2": [
        ("bare_habit", "bare_habit", []),
        ("clock_reenc", "clock_reenc", []),
        ("clock_premise", "clock_premise", []),
        ("clock_self", "clock_self", []),
        ("sal_reenc", "sal_reenc", []),
        ("clock75", "bare_reseed", ["--clock-every", "75"]),
        ("clock300", "bare_reseed", ["--clock-every", "300"]),
        ("clock600", "bare_reseed", ["--clock-every", "600"]),
    ],
    # matched-frequency controls for sal_reenc (~5 injections per 4,500 tokens): every 900 on the clock
    "b2x": [
        ("clock900_reenc", "clock_reenc", ["--clock-every", "900"]),
        ("clock900", "bare_reseed", ["--clock-every", "900"]),
    ],
    # generator families: the four conditions that carry the argument (fam8b = Qwen3-8B; also used for OLMo-2)
    # battery 3 (external review): habituation x interruption factorial and missing baselines
    "b3": [
        ("nohabit150", "nohabit_reseed", ["--clock-every", "150"]),
        ("nohabit300", "nohabit_reseed", ["--clock-every", "300"]),
        ("sham_break300", "sham_break", ["--clock-every", "300"]),
        ("sham_cont300", "sham_continue", ["--clock-every", "300"]),
        ("bare_eos", "bare_eos", []),
        ("habit_strong", "habit_strong", []),
        ("reset_reseed300", "reset_reseed", ["--clock-every", "300"]),
        ("reset_break300", "reset_break", ["--clock-every", "300"]),
    ],
    # the core ladder on another model (use --model): unquantized 8B, or the post-trained Qwen3-8B
    "ladder3": [
        ("bare", "bare", []),
        ("bare_habit", "bare_habit", []),
        ("bare_reseed", "bare_reseed", []),
    ],
    "fam8b": [
        ("bare", "bare", []),
        ("bare_habit", "bare_habit", []),
        ("bare_reseed", "bare_reseed", []),
        ("scaffold0", "scaffold0", []),
    ],
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--battery", choices=sorted(BATTERIES), required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--tokens", type=int, default=4500)
    p.add_argument("--seeds", type=int, default=len(SEEDS))
    p.add_argument("--review-clock", type=int, default=150)
    p.add_argument("--only", nargs="*", default=None, help="subset of condition names")
    p.add_argument("--premises", choices=["orig", "new", "genre", "problem"], default="orig", help="orig: the ten premises of the program; new: the ten confirmatory premises; genre: ten expository openings; problem: ten bin-packing notebook variants")
    p.add_argument("--rng-seed", type=int, default=0, help="sampler RNG seed passed to dream_run.py")
    args = p.parse_args()
    if args.premises == "problem":
        sys.path.insert(0, str(ROOT / "src"))
        from creative_machine.problem_premises import VARIANTS, premise
        seeds = [premise(lo, hi) for lo, hi in VARIANTS]
    else:
        seeds = {"orig": SEEDS, "new": NEW_SEEDS, "genre": GENRE_SEEDS}[args.premises]
    args.out.mkdir(parents=True, exist_ok=True)
    progress = args.out / "progress.log"

    def log(msg: str) -> None:
        line = f"{datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        with progress.open("a") as f:
            f.write(line + "\n")

    conds = [c for c in BATTERIES[args.battery] if not args.only or c[0] in args.only]
    # condition-major order: the confound control finishes first and can be judged early
    cells = [(si, c) for c in conds for si in range(args.seeds)]
    log(f"battery {args.battery}: {len(cells)} cells ({args.seeds} seeds x {len(conds)} conditions), "
        f"{args.tokens} tokens, model {args.model}, premises {args.premises}, rng seed {args.rng_seed}")
    for si, (name, control, extra) in cells:
        cell = f"s{si}_{name}"
        cell_dir = args.out / cell
        if (cell_dir / "run.json").exists():
            log(f"skip {cell} (done)")
            continue
        log(f"start {cell} thermal={thermal()}")
        t0 = time.time()
        cmd = [PY, str(ROOT / "scripts/dream_run.py"), "--model", args.model, "--tokens", str(args.tokens),
               "--seed-text", seeds[si], "--control", control, "--no-judge", "--rng-seed", str(args.rng_seed),
               "--review-clock", str(args.review_clock), "--out", str(cell_dir), *extra]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
            (args.out / f"{cell}_log.txt").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr[-4000:])
            status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
        except subprocess.TimeoutExpired:
            status = "timeout"
        log(f"done  {cell} {status} in {(time.time()-t0)/60:.1f} min thermal={thermal()}")
    log(f"battery {args.battery}: finished")


if __name__ == "__main__":
    main()
