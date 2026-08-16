# Where Creativity Lives in a Language Model: Not the Sampler, Not the Prompt — Interrupting the Loop

> Main working draft (2026-08-16). Supersedes the framing of PAPER.md
> (whose Phase-1 results become §3 here) and absorbs PAPER_B.md (the
> negative result, §4). Numbers marked **[TBD]** come from the ablation
> battery running today (10 seeds × 5 conditions). Lab notebook: PLANO.md.

## Abstract (draft)

Where does novelty come from when a language model generates text with
no task? We test three hypotheses with one measurement stack (a base
model run locally, cross-family LLM judges with k-sample medians,
bootstrap CIs, and — for one arm — verbatim novelty against the model's
own public training corpus). **(1) The sampler.** An entropy-banded
anti-probable decoder that pushes each step toward semantically distant
tokens cuts the rate of verbatim 8+-word training blocks from 0.80 to 0.20
of generations and roughly doubles 4-gram novelty over min-p sampling
(21.5% → 45.5%; paired Δ +24.0 pp, CI [18.2, 29.5]) at a small
perplexity cost — but
this surface novelty does not rise to the level of ideas: inside a
reverie loop, the same push produces no measurable difference from plain
sampling in judged surprise, connection, or novel delta (1,335
judgments, 2 judges, 3 rubrics). **(2) The prompt.** Composed inputs
built to sit far from any human prompt do not outperform a typical
request when a strong model develops them (Opus 5; n=15/arm, k=3):
improbable inputs are noise. **(3) The loop.** Bare continuous generation from a base model is dead:
it converges on the deepest attractor of pretraining (website footers,
literal orbits) and stays (judged surprise 0.33/10). A closed reverie loop
built on the architecture of spontaneous cognition — salience-gated
review, selective forgetting, reseeding, re-encounter — brings it to life
(surprise 3.22, connection 1.60; vs bare, Cliff's δ = +0.88, p ≈ 10⁻¹⁶,
10 seeds, Opus 5 k=5). But ablation shows that almost the whole effect
is carried by **one operation: periodically interrupting the stream and
injecting a new starting sentence over the preserved context**. Bare
generation plus a clock reseed and nothing else ties the full scaffold on
surprise (3.08 vs 3.22) and beats it on connection (3.15 vs 1.60) and
coherence (4.78 vs 3.72); salience, forgetting and kicks add no surprise
on top, and forgetting costs connection. Salience-gated review does beat
clock review as a *when-to-look* policy, but not as a generation
architecture. Trajectory analysis in sentence-embedding space shows the
geometry: bare generation freezes far from the premise (mean step 0.14,
distance 0.78); interrupted loops explore ~3× the radius and return. In
this system, creativity is not in the noise injected into decoding, nor
in the strangeness of the input, nor in an elaborate cognitive scaffold —
it is in **interrupting the loop**: leaving, and being made to start again.

## 1. Thesis and program

Human insight is not a response to a strange prompt; it arises inside a
closed loop of thought feeding on its own output — during incubation,
mind-wandering, sleep — when a spontaneously generated deviation survives
critical review and is linked back to what came before. Neuroscience
describes three coupled networks: default-mode (spontaneous generation,
memory retrieval), executive (evaluation), and salience (the switch that
decides what deserves attention); more creative people show more
coupling between the first two (Beaty et al.). We built a language-model
analogue of this loop and asked, with controls, which of its parts
matter — and whether the parts we and others usually optimize (decoding,
prompting) matter at all.

## 2. Measurement stack (shared by every experiment)

- **Generator**: base models only (instruct models are mode-collapsed):
  Qwen3-8B-Base, OLMo-2-13B (public corpus), Qwen3-30B-A3B-Base (MoE,
  53 tok/s), 8-bit on Apple silicon via MLX with a numpy sampler that sees
  full logits.
- **Judges**: Claude Sonnet 5 / Opus 5 via Bedrock, always a different
  family from the generator, k-sample medians (k=3–5), rubrics with
  independent 0–10 dimensions; nearest-equivalent + novel-delta rubric for
  ideas; surprise / connection / coherence for reverie windows.
- **Instrument calibration** (§6): intra-window spread of k judgments
  measured before use; effects below ~1 point are declared undetectable.
- **Objective novelty** where available: infini-gram counts against the
  OLMo-2 training corpus.
- **Statistics**: bootstrap CIs on differences; unit = window or seed.

## 3. Hypothesis 1 — the sampler (Phase 1; details in PAPER.md)

Method: at steps whose entropy falls in a calibrated band, re-score
floor-passing candidates by `log P + λ·z(distance to context EMA)`.
Findings: (a) OLMo-2-13B, 3 prompts × 5 seeds, fully paired grid: 4-gram
novelty 21.5% → 45.5% (λ=2), paired bootstrap Δ +24.0 pp [18.2, 29.5]
(λ=1: +14.6 [7.9, 21.9]), monotone in λ and present in each prompt;
P(≥8-word verbatim training block) 0.80 → 0.20 in both machine arms
(a 4× reduction stated as a rate — the pilot's "zero blocks" was one
cell, not the distribution); coherence cost ~+1.2 ppl under a
cross-family judge, uncorrelated with novelty within arms (Spearman
+0.12). (b) The
entropy *ceiling* (genre forks) transfers across model families. (c) Three
escape modes (recitation, collage, factual paraphrase). The recitation
detector (entropy drop between halves) is reported descriptively: on
exp1 it has AUC 0.71 for ≥8-word blocks and precision 0.33 at the 0.35
threshold, and no false-positive rate could be measured because the
baseline arm lacked telemetry — a calibrated detector is future work.
**Limit**: in verified search (bin packing, 8B and 30B, up to 3,200
verified heuristics) the operator does not separate from plain sampling
— a scoped null. And in the reverie loop (§5) the same push yields no
difference in judged surprise, connection or delta. Surface novelty is
real and does not climb.

## 4. Hypothesis 2 — the prompt (PAPER_B.md, negative)

Three input arms (typical request / distant concept pair / composed
improbable context) plus two ablations (fragments-only, register-only),
developed by Opus 5, judged by Sonnet 5 (k=3), n≈15/arm: the typical
prompt matched or beat every improbable arm; two were significantly
worse; input improbability (semantic kNN distance to 10k real prompts, or
perplexity) did not correlate with judged novelty (|r| < 0.2). A pilot
effect (n=8) had not replicated. Improbable inputs from outside are noise.

## 5. Hypothesis 3 — the loop (DREAM)

**Architecture** (Drift–Review–Escalate–Accumulate–Memory): one long
stream, no task, EOS masked, the output as next context; a salience
monitor over the stream's own telemetry (semantic jump, crystallization,
recurrence, stagnation, surface genre-collapse) gates a cross-family judge
(coherence / connects-distant / delta); a passing window triggers
escalation (narrow regime + injected textual return to the premise);
stagnation triggers a kick, then a subject change with **selective
forgetting** (rebuild the working memory: premise + kept windows + new
seed; anchors — regions visited — persist); an optional bridge term in
the sampler rewards moving toward far old regions.

**Calibration by attractor** (7 no-judge probes): a base model left
without a task recites the web — early EOS, erudite rumination, literal
4-sentence orbits, website footers, translation tables — each mapped and
turned into a mechanism (EOS mask; stagnation+kick; graded habituation;
genre detector; forgetting). The generator's pretraining diet was the
dominant variable: OLMo-2 sinks into footers even with forgetting;
Qwen3-30B drifts in prose. **The accumulated context is the well**: with
3k tokens of boilerplate in the cache, every injected seed was pulled
back within ~20 tokens; forgetting is what lets a seed take.

**Results.**
- Push vs plain inside the loop: no separation on any rubric (§3).
- Salience vs clock: salience-gated review beats reviewing on a timer in
  surprise and connection (CIs positive) at ⅓ the judge cost.
- **Scaffold vs bare** (5 seeds, λ=0 in both, Opus k=5): surprise 3.24 ±
  1.77 vs 0.47 ± 0.76 (CI [+1.99, +3.60]); connection 1.48 ± 1.37 vs 0.27
  ± 0.63 (CI [+0.61, +1.87]); coherence 3.48 vs 2.60 (CI [−0.08, +1.74]);
  3/21 scaffold windows with surprise ≥5 and coherence ≥5, 0/30 bare.
- **Ablation** (10 seeds × {full scaffold, salience-only, bare+clock
  reseed, bare}; 212 windows, Opus k=5): scaffold vs bare replicates
  (surprise 3.22 vs 0.33, δ = +0.88, p ≈ 10⁻¹⁶). Salience-only reaches
  2.74 (scaffold − salience-only CI [−0.26, +1.24]). **Bare + clock
  reseed** — no salience, no forgetting, no kicks — reaches surprise
  3.08 (CI vs scaffold [−0.50, +0.80]), connection 3.15 (scaffold lower:
  δ = −0.60, p ≈ 3×10⁻⁸) and coherence 4.78 (δ = −0.41), with 12/60
  windows judged surprising *and* coherent vs 8/50 for the scaffold and
  0/60 for bare. The re-encounter arm never fired (it was gated on the
  retired binary judge), so its ablation is empty. **Reading**: the
  interruption is the mechanism; the rest of the scaffold does not pay
  for itself at this resolution, and forgetting trades connection for
  return-to-premise.
- **Trajectories** (sentence-embedding space, PCA per seed, 10 seeds):
  bare generation has explored radius 0.18 and mean step 0.14 — it
  freezes — ending at distance 0.78 from the premise; the scaffold has
  radius 0.51 (CI vs bare [+0.27, +0.40]) and returns to within 0.57 of
  the premise (CI [−0.37, −0.06] vs bare); clock reseed spreads over the
  space in jumps (48 pseudo-closures) while keeping the whole context,
  which is where its connection advantage comes from.
- Qualitative: the loop elaborates its own finds after re-encounter
  ("Everything that almost happened piled up inside her like snow falling
  sideways through open windowsills into rooms filled with silence
  instead of noise [...] She kept a notebook because sometimes almosts
  piled up too much to be ignored").

### 5.1 What the interruption is made of (battery 2)

The ablation left the effect in one operation and raised four questions
about it. Battery 2 answers them with the same 10 seeds, 4,500 tokens per
cell, λ = 0, no forgetting, no judge in the loop; every cell's windows are
judged offline (Opus 5, k = 5, three dimensions) at two kinds of review
point — **cut** (the 160 tokens right before each injection: what the
stream produced up to the interruption) and **clock** (a uniform grid of
150 generated tokens, points within 20 tokens of a cut dropped) — with
exact token positions (each cell stores its token stream and the position
of every event and injection).

- **Confound control.** While designing the battery we found that the
  `bare` arm of the ablation ran without the scaffold's habituation
  (a graded repetition penalty over the last 512 tokens, factor 1.15),
  which every interrupted arm had. Bare generation dies in *literal*
  orbits ("Highly recommended." ×100, number tables, exam keys) —
  precisely what a repetition penalty undoes — so `bare` vs `bare + clock
  reseed` confounded interruption with habituation. **`bare_habit`**
  (habituation, no interruption of any kind) separates them.
- **Content.** Same clock (150), different injected text: a neutral
  subject change (the ablation's `bare_reseed`), a **re-encounter**
  stitch that asks the stream to return to its beginning ("Which is
  exactly what the first line had meant, seen from here:"), the
  **premise itself**, or a window of the stream's **own past** (≥400
  tokens back; before it has one, the premise) — thought feeding on
  thought.
- **Timing.** The re-encounter stitch injected on the **salience event**
  (jump / crystallization / recurrence, no judge gate) vs on the clock,
  and vs salience-only without injection.
- **Frequency.** The neutral subject change every 75 / 150 / 300 / 600
  tokens.

**Results** (60 windows per arm unless noted; Δ are paired-by-seed
bootstrap CIs over the 10 seeds; Cliff's δ and Mann–Whitney on windows).

- **Habituation and interruption are two operations, and both matter.**
  Bare 0.33 → bare + habituation **1.70** (surprise Δ +1.37 [+1.07,
  +1.67]; connection 0.17 → 1.08; coherence 2.08 → 4.08) → bare +
  habituation + clock reseed **3.08** (Δ +1.38 [+0.92, +1.92] over
  habituation alone). Habituation removes the literal orbits and buys
  about half of the surprise gain; the interruption buys the other half
  and **all of the connection** (1.08 → 3.15, Δ +2.07 [+1.63, +2.57],
  δ = +0.75, p ≈ 5×10⁻¹³) and the coherence (4.08 → 4.78). The full
  scaffold over habituation alone: surprise +1.52 [+0.85, +2.20],
  connection +0.52. The ablation's headline survives corrected: not
  "interruption alone" but "don't let the loop eat its literal past, and
  interrupt it" — with the connection effect belonging to the
  interruption.
- **The interruption must lead away.** With the same clock (150), a
  neutral subject change beats a re-encounter stitch on surprise
  (3.08 vs 2.28, Δ −0.80 [−1.35, −0.25]) and coherence (4.78 vs 4.30),
  and ties on connection (3.15 vs 3.03). Injecting the **premise
  itself** (1.12 / 0.90 / 3.07) or a window of the stream's **own past**
  (1.36 / 1.33 / 2.95) is as bad as not interrupting at all — every
  paired CI vs the neutral change excludes zero (surprise −1.97 [−2.65,
  −1.38] and −1.73 [−2.30, −1.19]; connection −2.25 and −1.82; δ ≈
  −0.7). Qualitatively, the own-past injection *reinforces* whatever
  attractor the stream is in (an exam-key well fed its own questions
  back). The judge sees connection when the stream finds its own way
  back after being sent away — not when it is told to return.
- **Timing.** [TBD — salience-timed re-encounter vs matched-frequency
  clock controls; judging]
- **Frequency: the yield of an interruption depends on the thread it
  breaks, and decays with distance from it.** With the neutral change
  every 75 tokens the stream is dead (surprise 0.88, δ = −0.83 vs 150):
  nothing has time to develop. Every 150: 3.08. Every 300 and 600, the
  windows that end within ~150 tokens *after* an interruption score
  **5.28 / 3.60 / 6.08** and 5.23 / 3.10 / 5.70 (surprise / connection /
  coherence; n = 50 and 30) — the highest values in the whole program,
  and 34/60 of the 300-early windows are judged surprising *and*
  coherent (12/60 at 150) — while windows deeper into the segment fall
  back to ~3.0 / 2.7 / 5.9 and stay there (170–330 and 490–650 tokens
  after the break: 2.95 and 3.06). The same window shape (a break plus
  150 tokens of development) scores 3.08 when the broken thread was 150
  tokens long and 5.3 when it was 300 or 600: surprise needs a developed
  background to break. Over the whole stream the period 300 is best
  (mean surprise 4.01, connection 3.12, coherence 5.98; 600: 3.64 /
  2.64 / 5.50; 150: 3.08 / 3.15 / 4.78; 75: 0.88 / 1.35 / 3.15). The
  loop's rhythm is: let a thread develop for a few hundred tokens, then
  break it away.

### 5.2 A second generator family

[TBD — Qwen3-8B-Base on bare / bare + habituation / bare + clock reseed /
scaffold, 10 seeds; running]

## 6. The instrument, measured

Same 89 windows, k=5, two judges: Opus 5 spread 0.71 (continuous scores,
resolution at ±0.7 noise); Sonnet 5 spread 0.27 but by scoring zero on
`connects_distant` almost everywhere (a ruler that only reads "0" is
consistent). Three-dimension rubric spreads 0.45–0.70. Consequence: LLM
judges detect effects ≥1–2 points (scaffold vs bare, salience vs clock)
and cannot adjudicate half-point effects (push vs plain) — which is why
the push's null is reported as "undetectable at this resolution", not
"absent". A binary threshold on a noisy judge is a coin: the same window
scored 5.24 one night and 4.48 the next.

## 7. Inside the network

Judges and sentence embeddings see the text; the model's own residual
stream sees the computation. We re-run every finished stream through the
generator (one forward pass with a KV cache; exact token positions) and
capture the residual at 13 layers (every 4th of 48 for Qwen3-30B-A3B;
every 3rd of 36 for Qwen3-8B), mean-pooled over 64-token windows (stride
32), plus a logit lens at each captured layer (the final norm and unembedding
applied to the intermediate state). Three questions:

- **H1 — where does the stream freeze?** Per-layer trajectory geometry of
  the window vectors (mean step between consecutive windows, explored
  radius), by condition; and the logit-lens **commitment layer** — the
  captured layer from which the top-1 token no longer changes — as a
  measure of how early the network has decided.
- **H2 — which layer's movement predicts judged surprise?** For every
  judged window, its novelty at layer *l* (cosine distance between the
  window's mean state and the mean state of everything before it) and
  its local step (vs the previous 160 tokens); Spearman with judged
  surprise, pooled and within condition.
- **H3 — how deep does an interruption reach?** Cosine distance between
  the 64 tokens before an injection and the 64 after it (the injected
  text skipped), per layer, minus the same at random positions; and the
  change in similarity to the premise's own state (after − before) —
  whether a re-encounter brings the network back toward its beginning in
  its own representation, and at which depth.

**Results.** [TBD — capture running after the batteries]

## 8. Related work

**Decoding.** Nucleus sampling [holtzman2020curious] truncates the unreliable
tail; locally typical sampling [meister2023typical] targets human-like
surprisal; min-p [nguyen2025minp] scales the truncation with the model's
confidence and is exactly our coherence floor; contrastive decoding
[li2023contrastive] and PPLM-style steering [dathathri2020pplm] shape the
distribution toward or away from a reference. All regulate the tail; our
sampler *courts* it, and we show that buys surface novelty only.
**Novelty measurement.** Infini-gram [liu2024infinigram] and Rusty-DAWG
[merrill2024rustydawg] make verbatim novelty against training data
computable; Saakyan et al. [saakyan2026death] show with 8,618 expert
annotations that ~91% of top-quartile n-gram-novel expressions are not
judged creative — our factual-paraphrase escape mode and the push's
idea-level null are independent, mechanistic confirmations. **Verified
search.** FunSearch [romeraparedes2024funsearch] and AlphaEvolve
[novikov2025alphaevolve] pair an LLM with a hard evaluator; our bin-packing
null and the DREAM scaffold suggest that the loop's structure, not the
sampling operator, is where to look next. **Cognition.** Creative cognition
as coupling of default and executive networks [beaty2016dynamics], with
salience regions coupling first [beaty2018robust]; creativity as
connecting semantically distant concepts [kenett2018semantic]; incubation
effects on problem solving [sio2009incubation]; predictive processing
[clark2013whatever]; dreams as anti-overfitting noise [hoel2021overfitted];
Boden's novelty/surprise/value triad [boden2004creative]; conceptual
blending [fauconnier2002way]; novelty search [stanley2015greatness]. DREAM
is an explicit engineering of the first three into a text loop.

## 9. Limitations and next

Ten seeds; one generator family for the loop (Qwen3-30B-A3B); LLM judges
(calibrated, not human); English narrative only; the re-encounter arm was
never exercised. The ablation's lesson reorders the program: the cheap
operation (interrupt + reseed) carries the effect, so the next questions
are about *it* — interruption frequency, seed quality (which starting
sentences make good interruptions and why), and whether a salience-timed
interruption beats a clock when the seeds are matched. Then: human blind
rating of top windows per condition; a second generator family; and the
fusion the program points to — an interrupted loop over a *problem*, with
a verifier in place of the judge.

## 10. Reproducibility

Everything in this repository (117 tests): sampler core, MLX adapter,
salience monitor, reverie engine, judges, novelty client, experiment
runners with resumable overnight execution and thermal logging. Every
run's per-step telemetry, texts and judgments under `runs/`; dated
decision log in `docs/PLANO.md`. Judge cost of the entire program to
date: ≈US$60.

## References

See `docs/references.bib` (entries marked [verified] were checked against publisher/arXiv pages on 2026-08-16; [check] entries are standard works to confirm before submission).
