# Where Creativity Lives in a Language Model: Not the Sampler, Not the Prompt, but Interrupting the Loop

Code, data and paper for a study of where novelty comes from when a base
language model writes with **no task** — feeding on its own output — and which
of the operations usually credited for it survive measurement.

**Paper**: [`paper/main.pdf`](paper/main.pdf) (LaTeX source in `paper/`);
working draft with every number: [`docs/PAPER_DREAM.md`](docs/PAPER_DREAM.md)
(also rendered as [`docs/manuscript.html`](docs/manuscript.html), and in
Portuguese in `docs/manuscrito.html`). **Lab notebook**, every decision and
result dated: [`docs/PLANO.md`](docs/PLANO.md) (Portuguese; an English
translation, `docs/NOTEBOOK.md`, accompanies the public release).

## The finding, in one paragraph

We tested three hypotheses with one measurement stack (base models run
locally, cross-family LLM judges with *k*-sample medians and measured
resolution, bootstrap CIs, verbatim novelty against a public training corpus).
**The sampler**: an entropy-banded anti-probable decoder doubles *n*-gram
novelty against the training corpus and cuts verbatim training blocks 4× — but
this surface novelty never rises to the level of ideas. **The prompt**: inputs
built to sit far from any human prompt are noise. **The loop**: bare
continuous generation is dead (it converges on the attractors of pretraining
and stays); a reverie loop built on the architecture of spontaneous cognition
brings it to life — but ablation locates the effect in two simple operations:
*habituation* (not letting the loop eat its literal past) and *interruption*
(a new starting sentence injected every few hundred tokens over the preserved
context), which must lead away, has a rhythm (~300 tokens; every 75 is dead),
and is best timed by a clock, not by salience. Replicated on three generator
families and two judge families; inside the network, the interruption that
works barely moves the deep state, while forgetting is a deep re-encounter with
the beginning that the judge rewards less.

## Layout

```
paper/                LaTeX source of the paper (tectonic main.tex → main.pdf)
docs/                 PAPER_DREAM.md (working draft, EN) · PAPER_DREAM_pt.md (PT) ·
                      PLANO.md (lab notebook) · APPENDIX_*.md (auto-generated tables) ·
                      figures/ · references.bib · blind/ (human-rating packs, no labels)
src/creative_machine/
  sampler.py, config.py       entropy-banded anti-probable sampler (pure numpy), habituation, bridge
  dream.py                    the reverie loop: interruption, forgetting, salience-timed re-encounter
  salience.py                 salience monitor (jump / crystallization / recurrence / stagnation)
  blend.py                    judges (Bedrock, OpenRouter): surprise/connection/coherence rubric
  novelty.py, evaluator.py    infini-gram novelty vs training corpus; perplexity judge; detectors
  prompt_space.py             sentence embeddings, distance to real prompts
  adapters/mlx_lm.py          MLX generation adapter
  domains/                    verified-search domain (online bin packing)
scripts/
  dream_run.py                one cell: premise → 4,500-token stream under a condition
  dream_battery2.py           resumable batteries (b2 / b2x / families), thermal logging
  dream_rejudge_surprise.py   offline judging (Opus k=5), two workers + rejudge_merge.py
  hidden_states.py            residual-stream capture (13 layers, logit lens, injection depth)
  hidden_analysis.py          N1–N3 analyses and figures
  analysis.py, analysis_b2.py trajectories.py   all tables and figures from runs/
  judge_agreement.py          second judge family vs Opus
  blind_pack.py, blind_score.py   human blind-rating pack and scoring
  build_manuscript.py         self-contained HTML manuscript (EN/PT)
tests/                        117 tests, synthetic distributions (run anywhere)
runs/                         (not in git) per-cell text, token stream, events, judgments
```

## Reproducing

Mac with Apple silicon (48 GB) is what everything ran on; the sampler core and
tests are pure numpy and run anywhere.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,mlx]"
.venv/bin/python -m pytest                      # 117 tests
```

Base models, quantized locally to 8-bit into `~/models/mlx/`
(`mlx_lm convert -q --q-bits 8`): Qwen3-30B-A3B-Base, Qwen3-8B-Base, OLMo-2-13B.

One cell of the loop (a premise, 4,500 tokens, an interruption every 300 tokens):

```bash
.venv/bin/python scripts/dream_run.py --control bare_reseed --clock-every 300 \
  --seed-text "The town had two clocks, and nobody remembered which one had been right first." \
  --tokens 4500 --no-judge --review-clock 150 --out runs/demo/s0_clock300
```

The batteries of the paper (resumable, overnight-safe), then offline judging
and the residual-stream capture:

```bash
python scripts/dream_battery2.py --battery b2 --out runs/dream_b2
AWS_PROFILE=<your-bedrock-profile> python scripts/dream_rejudge_surprise.py runs/dream_b2 --k 5
python scripts/hidden_states.py runs/dream_b2 && python scripts/hidden_analysis.py runs/dream_b2 --tag b2
python scripts/analysis.py && python scripts/analysis_b2.py    # tables and figures
```

Judges run on Amazon Bedrock (Claude Opus 5 / Sonnet 5) and OpenRouter (Kimi
K2.6); the OpenRouter key goes in `~/.config/creative-machine/openrouter_key`
or `OPENROUTER_API_KEY`. Nothing in this repository contains credentials.

## Data

Every run's per-step telemetry, text, token stream with exact event and
injection positions, and every judgment (`rejudge_surprise.json`) live under
`runs/` (released as an archive with the paper, not tracked in git). The
human-rating packs in `docs/blind/` contain the rated windows without
condition labels; the keys are not public.

## License

Code and documentation are released under the MIT License (see `LICENSE`).

## Citation

```
@misc{ono2026interrupting,
  title  = {Where Creativity Lives in a Language Model: Not the Sampler, Not the Prompt, but Interrupting the Loop},
  author = {Ono Filho, Roberto I.},
  note   = {ORCID 0009-0006-8650-629X},
  year   = {2026},
  howpublished = {Preprint}
}
```

The experiments, analyses and text were produced by the author working with
Claude (Anthropic) as a programming and writing assistant inside Claude Code;
every decision, result and claim was reviewed by the author, and the dated
notebook records the trail.
