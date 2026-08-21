# Interrupting the Loop: Periodic Subject Changes Raise Judged Surprise and Connection in Base Language Models

Code, data and paper for a study of where novelty comes from when a base
language model writes with **no task** — feeding on its own output — and which
of the operations usually credited for it survive measurement.

**Paper**: [arXiv:2608.19893](https://arxiv.org/abs/2608.19893) ([`paper/main.pdf`](paper/main.pdf); LaTeX source in `paper/`, the
master; the earlier Markdown/HTML drafts in `docs/` are frozen at v1.) All
tables of the primary analysis: [`docs/APPENDIX_GEN.md`](docs/APPENDIX_GEN.md). **Lab notebook**, every decision and
result dated: [`docs/PLANO.md`](docs/PLANO.md) (Portuguese; an English
translation, `docs/NOTEBOOK.md`, accompanies the public release).

## The finding, in one paragraph

We tested three hypotheses with one measurement stack (base models run
locally, LLM judges from another model family with *k*-sample medians and a
measured instrument, the premise as the unit of inference, verbatim novelty
against a public training corpus). **The sampler**: an entropy-banded
anti-probable decoder doubles *n*-gram novelty against the training corpus
and cuts verbatim training blocks 4x, but shows no detectable effect on judged
surprise or connection. **The prompt**: inputs built to sit far from any human
prompt show no benefit under the operationalizations we tested. **The loop**:
forced continuation from a base model degenerates; a cognitively inspired loop
revives it, and taking the loop apart over 24 conditions locates most of the
effect in one operation, a *new subject injected every few hundred tokens*
(an interruption) into a stream whose literal repetition is damped
(habituation). On windows of generated, fresh text, the interruption raises
judged surprise by 1.2-1.4 points and connection by 0.8 over habituation
alone (Qwen3-30B-A3B-Base, ten premises, paired permutation tests), replicated
on three base models from two families, a post-trained model, an unquantized
model and a second genre, and confirmed by a pre-registered replication on new
premises. Controls: a bare paragraph break does nothing, a continuity
connective hurts, a reset context does at least as well as a kept one, the
salience monitor, the in-loop judge and a judge-gated Review run with a gate
that opens add nothing, and no arm builds an integrated document. **The
instrument**: three things a windowed LLM judge could not see changed the
first version of this study (the injected sentence scored as the model's own;
the model replaying its own earlier segments from beyond the judge's horizon;
local gains that do not compose), and the protocol that corrects them
(generated-only windows, fresh-only estimates, a document-level reading, the
premise as the unit, a pipeline test-retest, a second judge family, human
readers) is, we think, the most general thing here. This characterizes a
simple, controllable intervention and the instrument needed to measure it
honestly; it does not establish a general mechanism of creativity.

**Revision note (2026-08-18/19).** After an external review, the study was
re-analyzed with generated-only windows and the premise as the unit, extended
with a control battery, a pre-registered confirmatory battery, a
document-level judgment, a self-copy analysis, replications on more models and
a second genre, and a judge-gated Review run with a gate that opens. The
earlier claims about a best rhythm (~300 tokens), about the interruption's
yield growing with the thread it breaks, about memory as an ingredient and
about salience as a poor metronome did not survive; the numbers in the paper
are the new ones.

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
  dream_battery2.py           resumable batteries (b2 / b3 / confirm / families), thermal logging
  dream_rejudge_surprise.py   offline judging (Opus k=5), generated-only or event windows, several workers
  hidden_states.py            residual-stream capture (13 layers, logit lens, injection depth)
  hidden_analysis.py          N1–N3 analyses and figures
  analysis_gen.py             primary analysis: generated-only windows, cell as unit, permutation tests
  analysis.py, analysis_b2.py trajectories.py   event-protocol tables and figures (descriptive)
  judge_agreement.py          second judge family vs Opus
  blind_pack.py, blind_pack3.py, blind_score.py   human blind-rating packs (rounds 1 and 2) and scoring
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
AWS_PROFILE=<your-bedrock-profile> python scripts/dream_rejudge_surprise.py runs/dream_b2 --k 5 --protocol gen
python scripts/hidden_states.py runs/dream_b2 && python scripts/hidden_analysis.py runs/dream_b2 --tag b2
python scripts/analysis_gen.py                                 # primary tables and figures
python scripts/analysis.py && python scripts/analysis_b2.py    # event-protocol tables (descriptive)
```

Judges run on Amazon Bedrock (Claude Opus 5 / Sonnet 5) and OpenRouter (Kimi
K2.6); the OpenRouter key goes in `~/.config/creative-machine/openrouter_key`
or `OPENROUTER_API_KEY`. Nothing in this repository contains credentials.

## Data

Every run's per-step telemetry, text, token stream with exact event and
injection positions, and every judgment (`rejudge_gen.json`, generated-only windows;
`rejudge_surprise.json`, event windows) live under
`runs/` (released as an archive with the paper, not tracked in git). The
human-rating packs in `docs/blind/` contain the rated windows without
condition labels; the keys are not public.

## License

Code and documentation are released under the MIT License (see `LICENSE`).

## Citation

```
@misc{ono2026interrupting,
  title  = {Interrupting the Loop: Periodic Subject Changes Raise Judged Surprise and Connection in Base Language Models},
  author = {Ono Filho, Roberto I.},
  year   = {2026},
  eprint = {2608.19893},
  archivePrefix = {arXiv},
  primaryClass = {cs.CL},
  url    = {https://arxiv.org/abs/2608.19893},
  note   = {ORCID 0009-0006-8650-629X}
}
```

The experiments, analyses and text were produced by the author working with
Claude (Anthropic) as a programming and writing assistant inside Claude Code;
every decision, result and claim was reviewed by the author, and the dated
notebook records the trail.
