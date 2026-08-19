#!/usr/bin/env python3
"""Run the reverie loop (DREAM) and its controls.

    AWS_PROFILE=main-account python scripts/dream_run.py --tokens 3000 --out runs/dream1
    ... --control plain      # Control A: same loop, plain sampler (no drift)
    ... --control clock      # Control C: salience off, review every N tokens
    ... --no-judge           # salience calibration only (no API calls)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine import SamplerConfig  # noqa: E402
from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler  # noqa: E402
from creative_machine.blend import BedrockClient, judge_reverie  # noqa: E402
from creative_machine.dream import DreamConfig, dream  # noqa: E402
from creative_machine.salience import SalienceConfig  # noqa: E402
from generate_mlx import eos_ids  # noqa: E402

SEEDS = [
    "The lighthouse keeper had one theory about the sea, and it was this:",
    "She kept a notebook of things that had almost happened.",
    "The map was accurate in every detail except one, and nobody could say which.",
]

# Return-to-the-premise stitches, premise-agnostic (the DreamConfig defaults
# name "the notebook", which fits one seed only). Used by the battery-2
# re-encounter conditions.
REENCOUNTER_TEXTS = (
    "\n\nAnd this, it turned out, was the same thing as the beginning — because",
    "\n\nIt came back to where it had started, of course; it always did, but this time",
    "\n\nWhich is exactly what the first line had meant, seen from here:",
    "\n\nSo the opening sentence had been true after all, only not in the way it seemed:",
)

_HABIT = dict(repetition_window=512, repetition_penalty=1.15)  # the scaffold's habituation (dream.py)


def add_review_points(run, clock: int, near: int = 20) -> None:
    """Mark the windows the offline judge will read, with exact positions:
    kind 'cut' right before every injected text (what the stream produced
    up to the interruption) and kind 'clock' on a fixed grid of generated
    steps (uniform sample), grid points within `near` tokens of a cut dropped."""
    cuts = []
    for r in run.reseeds:
        meta = r[2] if len(r) > 2 and isinstance(r[2], dict) else {}
        if "pos" in meta:
            cuts.append((r[0], meta["pos"]))
    for step, pos in cuts:
        run.events.append({"step": step, "pos": pos, "kind": "cut", "magnitude": 0.0, "judged": True})
    cut_pos = [p for _, p in cuts]
    for s in range(clock, run.n_tokens + 1, clock):
        pos = run.step_pos[s - 1] if run.step_pos else s
        if any(abs(pos - c) <= near for c in cut_pos):
            continue
        run.events.append({"step": s, "pos": pos, "kind": "clock", "magnitude": 0.0, "judged": True})
    run.events.sort(key=lambda e: (e["step"], e.get("pos", 0)))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--tokens", type=int, default=3000)
    p.add_argument("--seed-index", type=int, default=0)
    p.add_argument("--seed-text", default=None, help="explicit seed (overrides --seed-index)")
    p.add_argument("--rng-seed", type=int, default=0)
    p.add_argument("--control", choices=[
        "none", "plain", "clock", "bare", "scaffold0",
        # ablation ladder (all with the push off): what part of the scaffold carries the effect?
        "abl_salience",   # salience-gated review only: no forgetting, no reseed, no kick, no re-encounter
        "abl_forget",     # + forgetting/reseed/kick (subject changes with a short working memory), no re-encounter
        "bare_reseed",    # honesty control: bare generation + subject change on a clock (no salience)
        # battery 2: what is the interruption made of?
        "bare_habit",     # bare + the scaffold's habituation (repetition penalty), NO interruption — the confound control
        "clock_reenc",    # clock interruption injecting a return-to-the-premise stitch instead of a subject change
        "clock_premise",  # clock interruption injecting the opening line itself
        "clock_self",     # clock interruption injecting a window of the stream's own past (thought feeding on thought)
        "sal_reenc",      # salience-timed re-encounter: the event itself injects the stitch (no judge in the loop)
        # battery 3 (external review): factorial and missing baselines
        "nohabit_reseed", # interruption WITHOUT habituation (bare sampler + clock reseed)
        "sham_break",     # habituation + a bare paragraph break injected on the clock (no semantic content)
        "sham_continue",  # habituation + a continuity connective injected on the clock ("And so, as before,")
        "bare_eos",       # habituation, no interruption, EOS allowed: the model may end a document and start another
        "habit_strong",   # habituation with a stronger penalty (1.3), no interruption
        "reset_reseed",   # clock reseed with the context wiped: premise + new subject only (no kept windows)
        "reset_break",    # clock restart with the context wiped: premise + paragraph break (fresh continuation)
        # DREAM's Review, tested with a gate that opens: judge-gated interruption (a find is left to run)
        "judge_gate",     # habituation + clock reseed unless a real judge reads the last window as a find
    ], default="none")
    p.add_argument("--gate-threshold", type=float, default=5.0, help="judge_gate: a find = surprise >= t and coherence >= t (Opus, one call)")
    p.add_argument("--gate-judge", default="anthropic.claude-opus-5")
    p.add_argument("--clock-every", type=int, default=150)
    p.add_argument("--review-clock", type=int, default=0,
                   help="mark offline-review windows: 'cut' before every injection + 'clock' every N generated steps")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--judge-model", default="anthropic.claude-sonnet-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    from mlx_lm import load

    model, tokenizer = load(str(Path(args.model).expanduser()))
    no_push = eos_ids(tokenizer)
    cfg = DreamConfig(total_tokens=args.tokens)
    cfg.drift = SamplerConfig(**{**cfg.drift.__dict__, "no_push_ids": no_push, "seed": args.rng_seed})
    cfg.escalate = SamplerConfig(**{**cfg.escalate.__dict__, "no_push_ids": no_push, "seed": args.rng_seed})

    if args.control == "plain":
        # Control A: no drift — plain (floored) sampling in both regimes
        cfg.drift = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed)
        cfg.escalate = cfg.drift
    if args.control == "scaffold0":
        # Full DREAM scaffold (salience, forgetting, reseed, kick, re-encounter)
        # with the anti-probable push OFF in every regime: isolates the scaffold.
        for name in ("drift", "escalate", "kick"):
            base = getattr(cfg, name)
            setattr(cfg, name, SamplerConfig(**{**base.__dict__, "lam": 0.0, "bridge": 0.0}))
    CLOCK_FAMILY = ("bare_reseed", "clock_reenc", "clock_premise", "clock_self",
                    "sham_break", "sham_continue", "reset_reseed", "reset_break", "judge_gate")
    if args.control in ("abl_salience", "abl_forget", "sal_reenc") + CLOCK_FAMILY:
        for name in ("drift", "escalate", "kick"):
            base = getattr(cfg, name)
            setattr(cfg, name, SamplerConfig(**{**base.__dict__, "lam": 0.0, "bridge": 0.0}))
    if args.control in ("abl_salience", "sal_reenc"):
        cfg.kick_seeds = ()             # no reseed / no kick response
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.salience.stagnation_threshold = -1.0  # stagnation never fires (no kick)
        cfg.salience.entropy_floor = -1.0
    if args.control == "sal_reenc":
        # the salience event itself injects a return to the premise (no judge gate)
        cfg.reencounter_texts = REENCOUNTER_TEXTS
        cfg.reencounter_on_event = True
    if args.control == "abl_forget":
        cfg.reencounter = False         # everything but the re-encounter/escalation
    if args.control in CLOCK_FAMILY:
        # bare + an injection every N tokens by clock (no salience, no forgetting);
        # the family differs only in WHAT is injected
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.kicks_before_reseed = 1
        cfg.salience = SalienceConfig(
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            stagnation_window=1, stagnation_threshold=9.0,  # "stagnation" fires on every check -> reseed
            entropy_floor=-1.0, refractory=args.clock_every, snapshot_every=8,
        )
        if args.control == "sham_break":
            cfg.kick_seeds = ("\n\n",)
        elif args.control == "sham_continue":
            cfg.kick_seeds = ("\n\nAnd so, as before, ",)
        elif args.control == "reset_reseed":
            cfg.forget_on_reseed = True   # wipe: premise + new subject only
            cfg.keep_recent_tokens = 0
            cfg.keep_insight_windows = 0
        elif args.control == "reset_break":
            cfg.forget_on_reseed = True
            cfg.keep_recent_tokens = 0
            cfg.keep_insight_windows = 0
            cfg.kick_seeds = ("\n\n",)
        if args.control == "clock_reenc":
            cfg.kick_seeds = REENCOUNTER_TEXTS
        elif args.control == "clock_premise":
            cfg.reseed_source = "premise"
        elif args.control == "clock_self":
            cfg.reseed_source = "self"   # falls back to the premise until the stream has a past
            cfg.self_min_age, cfg.self_window = 400, 64
    if args.control == "nohabit_reseed":
        # interruption without habituation: the bare sampler (no repetition penalty) + clock reseed
        plain = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed)
        cfg.drift = plain; cfg.escalate = plain; cfg.kick = plain
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.kicks_before_reseed = 1
        cfg.salience = SalienceConfig(
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            stagnation_window=1, stagnation_threshold=9.0,
            entropy_floor=-1.0, refractory=args.clock_every, snapshot_every=8,
        )
    if args.control in ("bare_eos", "habit_strong"):
        pen = 1.15 if args.control == "bare_eos" else 1.3
        cfg.drift = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed,
                                  repetition_window=512, repetition_penalty=pen)
        cfg.escalate = cfg.drift
        cfg.kick = cfg.drift
        cfg.kick_seeds = ()
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.salience = SalienceConfig(
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            stagnation_threshold=-1.0, entropy_floor=-1.0, refractory=args.clock_every, snapshot_every=8,
        )
        if args.control == "bare_eos":
            cfg.mask_eos = False
    if args.control == "bare_habit":
        # bare (no interruption of any kind) + the scaffold's habituation only:
        # separates "not eating your own literal past" from "being interrupted".
        cfg.drift = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed, **_HABIT)
        cfg.escalate = cfg.drift
        cfg.kick = cfg.drift
        cfg.kick_seeds = ()
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.salience = SalienceConfig(   # nothing fires; windows come from --review-clock
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            stagnation_threshold=-1.0, entropy_floor=-1.0, refractory=args.clock_every, snapshot_every=8,
        )
    if args.control == "bare":
        # No scaffold at all: continuous plain generation, EOS masked, judged on
        # a clock for comparable review counts. No forgetting, no reseed, no
        # kick, no re-encounter, no salience.
        cfg.drift = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=no_push, seed=args.rng_seed)
        cfg.escalate = cfg.drift
        cfg.kick = cfg.drift
        cfg.kick_seeds = ()
        cfg.reencounter = False
        cfg.forget_on_reseed = False
        cfg.genre_collapse_threshold = 9.0
        cfg.salience = SalienceConfig(
            jump_threshold=-1.0, jump_lag=1, entropy_drop=9.0, recurrence_threshold=-1.0,
            stagnation_threshold=-1.0, entropy_floor=-1.0, refractory=args.clock_every, snapshot_every=8,
        )
    if args.control == "clock":
        # Control C: salience off — review on a clock. Emulated by a monitor
        # that fires a "clock" jump every N steps (thresholds unreachable).
        cfg.salience = SalienceConfig(
            jump_threshold=9.0, entropy_drop=9.0, recurrence_threshold=-1.0,
            refractory=args.clock_every, snapshot_every=8,
        )
        cfg.salience.jump_lag = 1
        cfg.salience.jump_threshold = -1.0  # always fires; refractory paces it

    sampler = MLXAntiprobableSampler(model, config=cfg.drift)
    judge = None
    if not args.no_judge:
        client = BedrockClient(aws_region=args.region)
        judge = lambda w, e: judge_reverie(client, args.judge_model, w, e)  # noqa: E731
    gate = None
    if args.control == "judge_gate":
        from creative_machine.blend import judge_surprise
        gate_client = BedrockClient(aws_region=args.region)

        def gate(window_text: str, earlier_text: str):
            v = judge_surprise(gate_client, args.gate_judge, window_text, earlier_text)
            ok = v["surprise"] >= args.gate_threshold and v["coherence"] >= args.gate_threshold
            return ok, {"surprise": v["surprise"], "connection": v["connection"], "coherence": v["coherence"]}

    seed = args.seed_text if args.seed_text else SEEDS[args.seed_index % len(SEEDS)]
    print(f"== DREAM ({args.control}) seed: {seed!r}", flush=True)
    run = dream(model, tokenizer, sampler, seed, cfg, judge=judge, gate=gate)
    if args.review_clock > 0:
        if args.no_judge:
            # no judge in the loop: the salience events are still the windows to review offline
            for e in run.events:
                if e["kind"] in ("jump", "crystallize", "recurrence"):
                    e["judged"] = True
        add_review_points(run, args.review_clock)
    run.save(args.out)
    print("\n== summary ==")
    print(run.summary())
    if not args.no_judge:
        print("tokens:", client.usage)
    if args.control == "judge_gate":
        n_gate = sum(1 for e in run.events if e.get("kind") == "gate"); n_pass = sum(1 for e in run.events if e.get("kind") == "gate" and e.get("passed"))
        print(f"gate: {n_gate} reads, {n_pass} finds left to run; tokens: {gate_client.usage}")
    print(f"-> {args.out}/ (text.txt, insights.json, run.json)")


if __name__ == "__main__":
    main()
