# creative-machine

**Fertile errors for language models.** An entropy-banded, anti-probable
decoding policy with a coherence guard, coupled to a selection loop — built
to generate what was *not* in the training data, and to measure that claim
against the training data itself.

> Thesis: new thoughts arrive as prediction errors. LLMs compute a full
> next-token distribution at every step; the tail already holds the
> improbable-but-possible. Standard decoding suppresses it. We court it,
> under guard, and let a selection loop keep what survives.

Working draft of the paper: [`docs/PAPER.md`](docs/PAPER.md). Lab notebook
with every decision, dated: [`docs/PLANO.md`](docs/PLANO.md) (PT-BR).
Kept artifacts: [`docs/GALERIA.md`](docs/GALERIA.md).

## What it does

At each decoding step the sampler measures the entropy of the model's
next-token distribution. Below a trigger (peaked: syntax, names, arithmetic)
it samples normally. Inside a calibrated **entropy band** it re-scores the
candidates that pass a relative **coherence floor** by

    score(token) = log P(token | context) + λ · z(distance(token, context))

deliberately favoring semantically distant continuations. Above the band —
document/genre forks, where register collapses live — it holds the rails.
The model then does what base models do: rationalizes the accident into
sense. We supply the accident; it supplies the seam.

Headline result (OLMo-2-13B-Base, whose training corpus is public and
indexed): machine generations contain **zero 8+-word blocks from the
training data** (baseline: one 9-word block), 4-gram novelty rises from
21.5% to 45.5% (bootstrap CIs exclude zero), at ~+1.2 perplexity under a
cross-family judge.

## Layout

```
src/creative_machine/
  sampler.py        entropy-banded anti-probable sampler (pure numpy)
  config.py         SamplerConfig: band, floor, λ, EMA half-life, no_push_ids
  telemetry.py      per-step JSONL: entropy, rank, distance, perturbed
  adapters/mlx_lm.py  plug into mlx-lm generate/stream_generate
  novelty.py        infini-gram client + n-gram novelty vs training corpus
  evaluator.py      cross-family judge perplexity, genre-collapse detector
  evolve.py         seed extraction for the selection loop
  concepts.py, blend.py   Phase 2: concept-pair blending via API
  domains/binpack.py, code_exec.py, heuristic_gen.py   verified-search domain
scripts/
  generate_mlx.py, sweep_lambda.py     generate / calibrate
  run_experiment.py, evaluate_experiment.py   multi-seed grid + funnel
  novelty_check.py, evolve.py          novelty vs corpus, selection loop
  blend_run.py, hybrid_run.py, rejudge.py   Phase 2
  verify_run.py, evolve_verified.py    verified search (bin packing)
  thermal_watch.py                     macOS thermal pressure for long runs
tests/                                 102 tests, synthetic distributions
```

## Setup (Mac, Apple silicon)

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,mlx]"
.venv/bin/python -m pytest
```

Models are quantized locally to 8-bit (`mlx_lm convert -q --q-bits 8`) into
`~/models/mlx/`; the code targets **base** models only (instruct models are
mode-collapsed by RLHF and make poor perturbators). The core sampler is
pure numpy and the test suite runs anywhere; only the adapter needs MLX.

Generate with the calibrated defaults:

```bash
.venv/bin/python scripts/generate_mlx.py --model ~/models/mlx/Qwen3-8B-Base-8bit \
  --prompt "The lighthouse keeper had one theory about the sea, and it was this:" \
  --baseline --telemetry runs/first.jsonl
```

Phase 2 (API couturier + judge via OpenRouter) needs a key in
`~/.config/creative-machine/openrouter_key` or `OPENROUTER_API_KEY`.

## Status

Roadmap items 1–6 done (sampler, calibration on two model families,
experiment harness with bootstrap CIs, objective novelty, evaluator funnel,
selection loop); Phase 2 piloted; verified-search route (item 7) built,
definitive experiment in progress. See `docs/PLANO.md` for the trail.
