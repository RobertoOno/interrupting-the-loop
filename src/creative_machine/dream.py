"""DREAM — the reverie loop: Drift, Review, Escalate, Accumulate, Memory.

A single long stream with no task prompt: the model's own output is its
next context. Four coupled processes (see PLANO, "O loop de devaneio"):

- Drift:     the anti-probable sampler in a loose regime, EOS masked (the
             mind does not emit end-of-document).
- Salience:  a cheap monitor on the drift's telemetry fires internal
             events (jump / crystallize / recurrence).
- Review:    only on an event, the recent window goes to a judge with
             three questions: coherent? connects two distant regions of
             what came before? delta over the nearest equivalent? A pass
             is an insight candidate with provenance. Nothing is edited.
- Escalate:  after a candidate, the sampler switches to a narrow regime
             for a stretch to develop the find, then returns to drift.

The loop is transport-agnostic about the judge: pass any callable
`(window_text, earlier_text) -> dict` (BedrockClient-backed by default in
the script). Everything else runs locally.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .config import SamplerConfig
from .salience import SalienceConfig, SalienceEvent, SalienceMonitor, genre_collapse_score
from .telemetry import StepRecord

JudgeFn = Callable[[str, str], dict]


_HABIT = dict(repetition_window=64, repetition_penalty=1.3)  # habituation: no literal orbits


@dataclass
class DreamConfig:
    total_tokens: int = 2000
    drift: SamplerConfig = field(
        default_factory=lambda: SamplerConfig(
            lam=2.5, entropy_trigger=1.8, entropy_ceiling=4.5, context_halflife=48, **_HABIT
        )
    )
    escalate: SamplerConfig = field(
        default_factory=lambda: SamplerConfig(
            lam=0.5, entropy_trigger=2.5, entropy_ceiling=4.5, context_halflife=48, **_HABIT
        )
    )
    escalate_tokens: int = 120       # length of the develop-the-find stretch
    kick: SamplerConfig = field(     # rumination breaker: hard push for a stretch
        default_factory=lambda: SamplerConfig(
            lam=4.0, entropy_trigger=1.2, entropy_ceiling=5.0, context_halflife=12, **_HABIT
        )
    )
    kick_tokens: int = 80
    kick_seeds: tuple[str, ...] = (  # if a kick doesn't free the loop, change the subject
        "\n\nThat night she dreamed of something else entirely:",
        "\n\nMeanwhile, in a city with no name,",
        "\n\nThere is an older story about this, and it goes:",
        "\n\nA question nobody had asked yet:",
    )
    kicks_before_reseed: int = 2     # consecutive stagnations before injecting a seed
    forget_on_reseed: bool = True    # rebuild the working memory instead of stacking on the well
    keep_recent_tokens: int = 200    # ...retaining this much of the pre-collapse stream
    keep_insight_windows: int = 3    # ...and the last N insight windows (what salience kept)
    fast_halflife: float = 24.0      # fast context EMA fed to salience (theme, not phrase)
    salience: SalienceConfig = field(default_factory=lambda: SalienceConfig(jump_threshold=0.55))
    genre_check_every: int = 64      # check the recent window for genre collapse every N tokens
    genre_window_tokens: int = 160
    genre_collapse_threshold: float = 0.5
    review_window_tokens: int = 160  # how much recent text the judge sees
    earlier_context_tokens: int = 600  # how much earlier text for the "distant regions" question
    pass_threshold: float = 5.0      # judge score at/above which an event is an insight candidate


@dataclass
class Insight:
    step: int
    event_kind: str
    event_magnitude: float
    window_text: str
    judgment: dict
    regime_before: str


@dataclass
class DreamRun:
    seed: str
    text: str = ""
    insights: list = field(default_factory=list)
    events: list = field(default_factory=list)   # all salience events (kind, step, magnitude, judged?)
    regime_switches: list = field(default_factory=list)  # (step, to_regime)
    reseeds: list = field(default_factory=list)  # (step, seed_text)
    n_tokens: int = 0
    n_reviews: int = 0

    def summary(self) -> dict:
        return {
            "n_tokens": self.n_tokens,
            "n_events": len(self.events),
            "n_reviews": self.n_reviews,
            "n_insights": len(self.insights),
            "n_reseeds": len(self.reseeds),
            "insights_per_1k": round(1000 * len(self.insights) / max(1, self.n_tokens), 3),
            "events_per_1k": round(1000 * len(self.events) / max(1, self.n_tokens), 3),
            "mean_insight_delta": (
                round(float(np.mean([i.judgment.get("delta_significance", 0) for i in self.insights])), 2)
                if self.insights else None
            ),
        }

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "text.txt").write_text(self.text)
        (path / "insights.json").write_text(
            json.dumps([asdict(i) for i in self.insights], indent=2)
        )
        (path / "run.json").write_text(
            json.dumps(
                {"seed": self.seed, "summary": self.summary(), "events": self.events,
                 "regime_switches": self.regime_switches, "reseeds": self.reseeds},
                indent=2,
            )
        )


def dream(
    model,
    tokenizer,
    sampler,                # MLXAntiprobableSampler (regime-switchable)
    seed: str,
    config: DreamConfig,
    judge: Optional[JudgeFn] = None,
    log=print,
) -> DreamRun:
    import mlx.core as mx
    from mlx_lm.generate import generate_step

    eos_ids = set(getattr(tokenizer, "eos_token_ids", None) or [])
    if tokenizer.eos_token_id is not None:
        eos_ids.add(tokenizer.eos_token_id)

    def mask_eos(tokens, logits):
        # The reverie never ends by itself.
        if eos_ids:
            logits = logits.at[:, list(eos_ids)].add(mx.array(-1e9))
        return logits

    run = DreamRun(seed=seed, text=seed)
    monitor = SalienceMonitor(config.salience)
    sampler.switch_regime(config.drift)
    regime = "drift"
    regime_until = -1
    generated_ids: list[int] = []
    prompt_ids = tokenizer.encode(seed)
    sampler.observe_prompt(prompt_ids)
    detok = tokenizer.detokenizer
    detok.reset()

    # Fast context EMA for salience: the sampler's own EMA is slow (long
    # half-life = the thought's memory); jumps show up as fast-vs-slow
    # divergence, which the monitor sees as movement of the vector we feed it.
    fast_decay = 0.5 ** (1.0 / config.fast_halflife)
    fast_ctx = None
    embed_fn = sampler.core.embed_fn

    def salience_vector(tok: int):
        nonlocal fast_ctx
        if embed_fn is None:
            return sampler.core.context
        vec = np.asarray(embed_fn(np.array([tok])), dtype=np.float64)[0]
        fast_ctx = vec.copy() if fast_ctx is None else fast_decay * fast_ctx + (1 - fast_decay) * vec
        return fast_ctx

    from mlx_lm.models.cache import make_prompt_cache

    # One KV cache for the whole reverie; segments restart generate_step
    # only when a reseed injects text (the cache already holds everything
    # before it, so only the injected tokens are prefilled).
    cache = make_prompt_cache(model)
    pending_prompt = list(prompt_ids)
    consecutive_stagnations = 0
    reseed_i = 0

    def do_reseed(seed_text: str, collapsed: bool):
        """Change the subject. With forgetting: rebuild the working memory —
        initial seed + what salience kept (insight windows) + a slice of the
        stream from before the collapse + the new seed — in a fresh KV cache,
        so the well cannot pull the seed back. Without forgetting: just
        append the seed on top of everything (the pre-forgetting behavior)."""
        nonlocal regime, fast_ctx
        seed_ids = tokenizer.encode(seed_text, add_special_tokens=False)
        # the reseed text becomes part of the visible stream either way
        for sid in seed_ids:
            generated_ids.append(sid)
            detok.add_token(sid)
        sampler.switch_regime(config.drift)
        regime = "drift"
        if not config.forget_on_reseed:
            sampler.observe_prompt(seed_ids)
            return seed_ids, cache
        # working memory: initial seed + kept insight windows + recent stream + new seed
        kept = [prompt_ids]
        for ins in run.insights[-config.keep_insight_windows :]:
            kept.append(tokenizer.encode(ins.window_text, add_special_tokens=False))
        # generated_ids now ends with seed_ids; take the stretch before them
        stream_before = generated_ids[: -len(seed_ids)]
        if collapsed:
            # skip the collapsed window itself: keep what came before it
            stream_before = stream_before[: -config.genre_window_tokens] or stream_before
        kept.append(stream_before[-config.keep_recent_tokens :])
        kept.append(seed_ids)
        memory_ids = [t for part in kept for t in part]
        # the sampler's own context EMA restarts from the kept memory too
        sampler.core.reset()
        sampler.observe_prompt(memory_ids)
        fast_ctx = None
        run.reseeds[-1] = (run.reseeds[-1][0], seed_text, {"working_memory_tokens": len(memory_ids)})
        return memory_ids, make_prompt_cache(model)

    while run.n_tokens < config.total_tokens:
      step_iter = generate_step(
          mx.array(pending_prompt), model, max_tokens=config.total_tokens - run.n_tokens,
          sampler=sampler, logits_processors=[mask_eos], prompt_cache=cache,
      )
      pending_prompt = None
      reseed_now = False
      for token, _ in step_iter:
        tok = int(token)
        generated_ids.append(tok)
        detok.add_token(tok)
        rec: StepRecord = sampler.telemetry.records[-1]
        run.n_tokens += 1
        step = run.n_tokens

        # regime bookkeeping: escalate/kick stretches end -> back to drift
        if regime != "drift" and step >= regime_until:
            sampler.switch_regime(config.drift)
            regime = "drift"
            run.regime_switches.append((step, "drift"))

        # Genre collapse (web boilerplate, tag clouds, footers) is the deepest
        # attractor of a base model left without a task: detect it on the
        # surface and change the subject at once. Not reviewed, not kicked.
        if step % config.genre_check_every == 0 and config.kick_seeds:
            recent_text = tokenizer.decode(generated_ids[-config.genre_window_tokens :])
            gscore = genre_collapse_score(recent_text)
            if gscore >= config.genre_collapse_threshold:
                seed_text = config.kick_seeds[reseed_i % len(config.kick_seeds)]
                reseed_i += 1
                log(f"[step {step}] genre collapse ({gscore:.2f}) -> reseed {seed_text.strip()!r}")
                run.events.append({"step": step, "kind": "genre_collapse", "magnitude": round(gscore, 3), "judged": False})
                run.reseeds.append((step, seed_text))
                pending_prompt, cache = do_reseed(seed_text, collapsed=True)
                consecutive_stagnations = 0
                reseed_now = True
                break

        event: SalienceEvent | None = monitor.observe(salience_vector(tok), rec.entropy)
        if event is None or regime != "drift":
            continue

        if event.kind == "stagnation":
            # Rumination is not reviewed; it is broken. First a kick (hard
            # push); if it persists, change the subject (inject a seed).
            consecutive_stagnations += 1
            run.events.append({"step": step, "kind": "stagnation", "magnitude": round(event.magnitude, 3), "judged": False})
            if consecutive_stagnations >= config.kicks_before_reseed and config.kick_seeds:
                seed_text = config.kick_seeds[reseed_i % len(config.kick_seeds)]
                reseed_i += 1
                consecutive_stagnations = 0
                log(f"[step {step}] stagnation persists -> reseed {seed_text.strip()!r}")
                run.reseeds.append((step, seed_text))
                pending_prompt, cache = do_reseed(seed_text, collapsed=False)
                reseed_now = True
                break
            log(f"[step {step}] stagnation ({event.magnitude:.2f}) -> kick")
            sampler.switch_regime(config.kick)
            regime = "kick"
            regime_until = step + config.kick_tokens
            run.regime_switches.append((step, "kick"))
            continue
        consecutive_stagnations = 0

        # Review on event: judge sees the recent window and earlier text
        detok.finalize()
        full_text = seed + detok.text
        run.text = full_text
        window_text = tokenizer.decode(generated_ids[-config.review_window_tokens :])
        earlier_ids = generated_ids[: -config.review_window_tokens][-config.earlier_context_tokens :]
        earlier_text = tokenizer.decode(earlier_ids) if earlier_ids else seed
        judged = False
        if judge is not None:
            run.n_reviews += 1
            try:
                verdict = judge(window_text, earlier_text)
                judged = True
            except Exception as exc:  # judge failures never stop the reverie
                verdict = {"error": str(exc), "score": 0.0}
            if verdict.get("score", 0.0) >= config.pass_threshold:
                run.insights.append(
                    Insight(step, event.kind, round(event.magnitude, 3), window_text, verdict, regime)
                )
                log(f"[step {step}] INSIGHT via {event.kind}: score {verdict.get('score')} "
                    f"delta {verdict.get('delta_significance')}")
                sampler.switch_regime(config.escalate)
                regime = "escalate"
                regime_until = step + config.escalate_tokens
                run.regime_switches.append((step, "escalate"))
            else:
                log(f"[step {step}] event {event.kind} ({event.magnitude:.2f}) -> no insight "
                    f"(score {verdict.get('score')})")
        else:
            log(f"[step {step}] event {event.kind} ({event.magnitude:.2f})")
        run.events.append({"step": step, "kind": event.kind, "magnitude": round(event.magnitude, 3), "judged": judged})
      if not reseed_now:
          break  # generator exhausted: budget reached

    detok.finalize()
    run.text = seed + detok.text
    return run
