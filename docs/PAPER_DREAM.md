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

## 7. Related work

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

## 8. Limitations and next

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

## 9. Reproducibility

Everything in this repository (117 tests): sampler core, MLX adapter,
salience monitor, reverie engine, judges, novelty client, experiment
runners with resumable overnight execution and thermal logging. Every
run's per-step telemetry, texts and judgments under `runs/`; dated
decision log in `docs/PLANO.md`. Judge cost of the entire program to
date: ≈US$60.

## References

See `docs/references.bib` (entries marked [verified] were checked against publisher/arXiv pages on 2026-08-16; [check] entries are standard works to confirm before submission).
