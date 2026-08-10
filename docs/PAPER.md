# Fertile Errors: Entropy-Banded Anti-Probable Decoding with Verified Novelty

> Working draft (pre-paper). Prose claims marked **[TBD]** need numbers from
> experiments specified in §8. Lab notebook with full provenance: PLANO.md.

## Abstract (draft)

Language models compute a full next-token distribution at every step; the
decoding policy that collapses it into text is a separate design choice, and
standard policies are engineered to suppress the improbable. We ask the
opposite question: can a decoding policy deliberately mine the
improbable-but-possible tail for genuine novelty while holding coherence?
We introduce an **entropy-banded anti-probable sampler**: at steps whose
predictive entropy falls inside a calibrated band, candidates passing a
global relative coherence floor are re-scored by
`log P(token) + λ · z(distance)`, where `z(distance)` standardizes the
semantic distance between each candidate's embedding and an exponential
moving average of the context. Below the band, syntax stays untouched;
above it — at document-level forks where register collapses live — the
sampler holds the rails. On OLMo-2-13B, whose training corpus is public and
indexed, machine generations contain **zero 8+-word blocks from the
training data** (baseline: one 9-word block) and triple 4-gram novelty
(12.3%→45.5%, bootstrap CIs excluding zero), at a coherence cost of ~+1.2
perplexity under a cross-family judge. We map three escape modes of
creative decoding — recitation, collage, and factual paraphrase — and show
the third defeats surface novelty metrics entirely, corroborating recent
arguments against n-gram novelty as a creativity metric. In preliminary
verified-search experiments (online bin packing), the anti-probable
operator escaped the best-fit plateau that conventional sampling never
left **[TBD: definitive multi-run experiment]**.

## 1. Introduction

Thesis: new thoughts arrive as prediction errors. Human text carries
surprise near expected entropy, not minimal surprise (typical sampling;
Meister & Cotterell 2022); maximum-probability text is degenerate. Decoding
research has focused on *suppressing* the tail's pathologies (top-p, min-p,
typical sampling). We instead *court* the tail deliberately, under guard.

Contributions:

1. **The entropy band** (§3): deviation is gated to mid-entropy branch
   points. The lower bound protects crystallized structure (syntax, names,
   arithmetic); the upper bound is novel — very-high-entropy steps are
   *document/genre forks*, empirically the site of register collapses (EOS
   bait at H=4.75, quiz/translation-mode switches). Deviate inside the
   narrative; hold the rails at genre crossroads.
2. **A standardized semantic push** (§3): token-embedding spaces are
   anisotropic (candidate distance spreads ~0.08 cosine), making raw
   distance bonuses inert. Per-step z-scoring gives λ a model-independent
   reading (nats per sigma).
3. **A failure taxonomy with detectors** (§5): three escape modes —
   recitation (entropy craters; detectable), collage (cross-family judge
   flags it), factual paraphrase (defeats all surface metrics; open).
4. **Objective novelty against the generator's own training corpus** (§4):
   with OLMo-2 + infini-gram, "generated what was not in training" becomes
   a lookup, not a vibe.
5. **Preliminary evidence in verified search** (§6): the anti-probable
   operator moves where conventional sampling freezes **[TBD]**.

## 2. Related Work

- **Decoding**: nucleus (Holtzman 2019), typical (Meister 2022), min-p
  (arXiv 2407.01082) — our global floor *is* relative min-p; contrastive
  decoding/search; entropy-aware temperature (EDT; Entropy-Aligned
  Decoding, arXiv 2601.01714). All regulate the tail; none actively seek
  semantically distant candidates.
- **Controlled generation**: PPLM (1912.02164), GeDi, FUDGE — steer toward
  attributes via external signals; our signal is distance-from-context
  itself, an anti-attractor rather than an attractor.
- **Novelty measurement**: Rusty-DAWG (2406.13069), infini-gram
  (2401.17377), Creativity Index; "Death of the Novel(ty)" (ICLR 2026,
  2509.22641) argues n-gram novelty alone is insufficient — our factual-
  paraphrase escape mode is an independent, mechanistic confirmation.
  "Measuring LLM Novelty" (OpenReview i7QNKZioN6) frames novelty as
  originality × quality — our funnel instantiates this.
- **Verified LLM search**: FunSearch (Nature 2023), AlphaEvolve (2025) —
  variation via conventional sampling of instruct models at scale; we vary
  the *operator*, on their benchmark, at small scale.
- **Theory**: Boden's novelty/surprise/value triad; Fauconnier & Turner's
  conceptual blending; Lehman & Stanley's novelty search; RLHF mode
  collapse motivating base models as perturbators.

## 3. Method

One decoding step (base model, batch 1):

1. `logprobs = log_softmax(logits / T)`; entropy `H`.
2. **Global coherence floor**: candidates = tokens with
   `p ≥ floor · p_max` (min-p style, every step). An unguarded step can
   fall 500 ranks deep by accident (p≈1e-6) — dumb accidents, not fertile
   errors.
3. If `H ∈ [trigger, ceiling)`: **perturbation**. Distances
   `d_i = 1 − cos(emb(c_i), ctx)` against an EMA of seen-token embeddings
   (prompt included; half-life 16 tokens); push = per-candidate z-score of
   `d`; EOS and other `no_push_ids` stay neutral (the most radical
   deviation — leaving the text — is not a deviation inside it). Sample
   from `softmax(logprobs + λ · push)` (Gumbel-max).
4. Else: plain floored sampling.

Embeddings are the model's own input table (free; dequantizing lookup).
The EMA makes the sampler observe its own deviations: yesterday's deviation
becomes today's context — a built-in anti-attractor (oscillation shown in
synthetic tests). λ=0 recovers exactly min-p sampling.

**Calibration** (Qwen3-8B-Base, transferred unchanged to OLMo-2-13B):
prose band [2.0, 4.5] nats, floor 0.05, λ∈[1,3] (default 1.5). Code
crystallizes far lower (median step entropy 0.57 vs ~2 for prose): code
band [0.9, 4.0] set at matched perturbation rate (~40%).

## 4. Objective novelty with public training data

Setup: OLMo-2-1124-13B (base, 8-bit local), corpus indexed by infini-gram
(`v4_olmo-2-1124-13b-instruct_llama`, superset of the base model's
training). Metric: fraction of n-word windows with corpus count 0; longest
copied span. 3 prompts × 5 seeds × 3 arms, 150 tokens.

| arm | novel 4-grams | novel 6-grams | Δ4 vs baseline (CI95) | max copied |
|---|---|---|---|---|
| min-p baseline | 21.5% ± 10.4 | 70.9% ± 12.4 | — | 10 words |
| λ=1 | 36.0% ± 12.8 | 87.6% ± 7.7 | [+6.9, +23.0]pp | 10 |
| λ=2 | 45.5% ± 11.2 | 89.7% ± 6.1 | [+16.3, +31.4]pp | 13* |

All CIs exclude zero; effect is monotone in λ. In the single-run pilot the
machine arms had **zero** 8+-word training blocks (baseline: one 9-word
block). *The λ=2 max-copied outlier is a genre-collapse cell reciting a
real 13-word credential — crossing genre makes text *less* novel (§5).

Coherence: continuation perplexity under a cross-family judge (Qwen judges
OLMo): baseline 7.3±2.0, machine 8.4–8.5 — the deviation costs ~+1.2 ppl.

**[TBD]** third model family; 20+ prompts; multi-seed longest-copied
statistics; human evaluation (§8-A).

## 5. Failure taxonomy: three escape modes

1. **Recitation** (quiz/exercise modes): mean entropy of the 2nd half
   craters vs the 1st (drop >0.35 vs ~0.2 for healthy settling) —
   detectable from telemetry alone.
2. **Collage** (document-mode switch, e.g. narrative → tourist guide with
   site navigation): entropy stays high; the cross-family judge flags it
   (ppl 15.3 vs ceiling ~10).
3. **Factual paraphrase**: correct real-world content in novel words
   (Ponce de León history: 91% novel 6-grams, judge-approved, stable
   entropy). **No surface metric catches it.** Cheap guard: seed screening
   by factual telltales (digits, internal proper names, attribution
   verbs); real detector open (§8-C).

The funnel (conjunction of detectors, then rank by novelty) passed 20/30
machine cells and independently re-discovered the human-curated gallery
piece — automatic curation approaching the human curator on n=1 **[TBD:
systematic curation agreement]**.

## 6. Verified search (preliminary)

Domain: online bin packing (FunSearch's benchmark), priority-function
contract, deterministic simulator, mean excess over the LP lower bound.
Base model Qwen3-8B; seed-paired arms; only λ differs.

- **V0 (pure sampling, 40/arm)**: quality tied (excess diff CI crosses 0);
  both arms *re-invent best-fit exactly*; neither beats it — as expected
  without evolution. Anti-probable validity 40/40 vs 34/40 **[TBD:
  retest]**.
- **V1 (verified evolution, 5 generations × 20/arm, population prompt)**:
  plain sampling stayed at best-fit for all 100 samples; the anti-probable
  arm escaped at generation 3 with a two-stage nonlinear heuristic
  dominating best-fit on train (0.0590 vs 0.0610) but tying on held-out
  test — train-set overfit. n=1 run/arm: suggestive, not proven.

**[TBD]** Definitive experiment (§8-B): 100+ train instances, ≥5 runs/arm,
escape-time and best-test-excess distributions, significance over curves.

## 7. Discussion & limitations

- Two model families, three prompts, English only; effects should be
  reproduced broadly before strong claims.
- LLM judges have run-to-run variance (same blend scored 3.56 vs 5.65);
  fine-grained judgments need k-sampling. Value remains the hard problem —
  n-gram novelty is recombination-level, not conceptual (our escape mode 3
  and ICLR-2026 concur).
- Conceptual blending via API (Phase 2) produced fluent recombination with
  low delta over nearest equivalents (~2.4/10, ceiling 4) regardless of
  seed type; the couturier's systematic strength is institutional
  second-order consequences, suggesting incentive-rule domains.
- The verified-search signal is n=1; the entire route-B claim rests on §8-B.

## 8. Experiment specifications by claim

- **A (novelty at scale)**: 3rd family (e.g. Llama-3-8B base), 20 prompts
  × 10 seeds × {baseline, λ=1.5}, novelty ns=(4,6,8) stride 2, longest-
  copied per cell; human eval: 3 raters × 30 pairs (machine vs baseline,
  same prompt), preference + coherence Likert. Claim passes if novelty CIs
  exclude zero on ≥2 families with human coherence non-inferior.
- **B (verified search)**: bin packing, 5 runs/arm × 8 generations × 20
  samples, train=100 instances, test=200; metrics: escape time (first gen
  with train excess < best-fit − ε), final test excess, distinct-body
  count; Mann-Whitney on escape times; secondary domain (e.g. flow-shop or
  auction-mechanism simulation) if positive.
- **C (paraphrase detector)**: NER-based entity-density score + retrieval
  probe vs the factual-paraphrase cells; target: separate mode-3 cells
  from gallery pieces at fixed FPR.
- **D (curation agreement)**: funnel ranking vs blinded human ranking on
  30 cells; Kendall τ.

## 9. Reproducibility

All code in this repository (102 tests): sampler core (`src/creative_machine/`),
MLX adapter, novelty client, funnel, verified domain. Models: quantized
8-bit Qwen3-8B-Base / OLMo-2-13B on Apple silicon (~31/17 tok/s). Full
per-step telemetry (JSONL) for every experiment; runs under `runs/`;
decision log with dates in `docs/PLANO.md`. Phase-2 API cost to date:
≈US$0.55.
