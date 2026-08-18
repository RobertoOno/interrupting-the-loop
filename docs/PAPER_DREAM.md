# Interrupting the Loop: Where Creativity Lives in a Language Model

> Complete working draft v1 (2026-08-16, night). Supersedes the framing
> of PAPER.md (whose Phase-1 results become §3 here) and absorbs
> PAPER_B.md (the negative result, §4). All batteries reported here have
> run; what remains before submission is a human blind rating (pack ready)
> and a revision pass. Lab notebook: PLANO.md.

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
perplexity cost — but this surface novelty does not rise to the level of
ideas: inside a reverie loop, the same push produces no measurable
difference from plain sampling in judged surprise, connection, or novel
delta (1,335 judgments, 2 judges, 3 rubrics). **(2) The prompt.**
Composed inputs built to sit far from any human prompt do not outperform
a typical request when a strong model develops them (Opus 5; n=15/arm,
k=3): improbable inputs are noise. **(3) The loop.** Bare continuous
generation from a base model is dead: it converges on the deepest
attractors of pretraining (literal orbits, website footers, exam keys) and
stays (judged surprise 0.28/10). A closed reverie loop built on the
architecture of spontaneous cognition — salience-gated review, selective
forgetting, reseeding, re-encounter — brings it to life (surprise 3.19;
vs bare, Cliff's δ = +0.88, p ≈ 5×10⁻¹⁵, 10 seeds, Opus 5 k=5). Ablation
and a second battery (18 conditions, 1695 judged windows, k = 5 each) locate
the effect in two operations and say what they are made of. *Habituation*
(not letting the loop feed on its literal past) lifts the stream from
0.28 to 1.70; *interruption* — periodically injecting a new starting
sentence over the preserved context — lifts it to 3.08 and carries all
of the connection (1.08 → 3.15, δ = +0.75). The interruption must lead
away: injecting the premise or the stream's own past is as bad as not
interrupting; a return works only as a short stitch that opens a new
sentence. Its yield depends on the thread it breaks and decays with
distance: interrupting every 75 tokens is dead (0.88), every 150 gives
3.08, and the 150 tokens after breaking a 300–900-token thread score
5.3–5.9 with coherence ~6 — the best text of the program — before the
stream re-settles at ~3.2; the best rhythm is a break every ~300 tokens.
Salience is a good reader and a bad metronome: it selects the windows
worth judging but, as an interruption trigger, fires too rarely and
unevenly (2.18 vs 4.70 for the same stitch on a matched clock). Inside
the network (residual stream at 13 layers, logit lens), bare generation
freezes at every layer, most at the surface, and ends certain (final
entropy 0.34); what the judge calls surprise is surface departure with
deep continuity; and the interruption that works barely moves the deep
state (+0.01–0.03 cosine across an injection, no return to the premise),
whereas forgetting is a deep re-encounter with the beginning (+0.2, and
the premise's own state recovered) that the judge rewards less. The
ladder bare → habituation → interruption → scaffold replicates on two
more generator families (Qwen3-8B-Base: 0.68 → 1.47 → 2.73, connection
0.87 → 3.23, δ = +0.80; OLMo-2-13B: 1.35 → 2.37 → 3.11, connection 0.91
→ 3.17, δ = +0.58 — where the plain interruption also costs coherence
and the scaffold's forgetting preserves it). In this system,
creativity is not in the noise injected into decoding, nor in the
strangeness of the input, nor in an elaborate cognitive scaffold — it is
in **interrupting the loop**: letting a thread develop, then making it
start again somewhere else, over everything it remembers.

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
  (surprise 3.19 vs 0.28, δ = +0.88, p ≈ 5×10⁻¹⁵; windows before 100
  generated tokens excluded, as everywhere in this paper). Salience-only
  reaches 2.63 (scaffold − salience-only CI [−0.22, +1.33]). **Bare + clock
  reseed** — no salience, no forgetting, no kicks — reaches surprise
  3.08 (CI vs scaffold [−0.54, +0.78]), connection 3.15 (scaffold lower:
  δ = −0.58, p ≈ 1.5×10⁻⁷) and coherence 4.78 (δ = −0.42), with 12/60
  windows judged surprising *and* coherent vs 8/47 for the scaffold and
  0/50 for bare. The re-encounter arm never fired (it was gated on the
  retired binary judge), so its ablation is empty here — battery 2 tests
  it directly (§5.1). **Reading**: the interruption carries the effect;
  the rest of the scaffold does not pay for itself at this resolution,
  and forgetting trades connection for return-to-premise. (§5.1 corrects
  one thing: the bare arm also lacked the scaffold's habituation, which
  accounts for part of the gap.)
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
- **Frequency.** The neutral subject change every 75 / 150 / 300 / 600 /
  900 tokens (900 also with the re-encounter stitch: the matched-frequency
  controls for the timing question).

**Results** (60 windows per arm unless noted; Δ are paired-by-seed
bootstrap CIs over the 10 seeds; Cliff's δ and Mann–Whitney on windows).

- **Habituation and interruption are two operations, and both matter.**
  Bare 0.28 → bare + habituation **1.70** (surprise Δ +1.42 [+1.12,
  +1.72]; connection 0.20 → 1.08; coherence 2.06 → 4.08) → bare +
  habituation + clock reseed **3.08** (Δ +1.38 [+0.92, +1.92] over
  habituation alone). Habituation removes the literal orbits and buys
  about half of the surprise gain; the interruption buys the other half
  and **all of the connection** (1.08 → 3.15, Δ +2.07 [+1.63, +2.57],
  δ = +0.75, p ≈ 5×10⁻¹³) and the coherence (4.08 → 4.78). The full
  scaffold over habituation alone: surprise +1.49 [+0.80, +2.19] (paired
  +1.80 [+0.97, +2.75]), connection +0.55 [+0.06, +1.10]. The ablation's
  headline survives corrected: not
  "interruption alone" but "don't let the loop eat its literal past, and
  interrupt it" — with the connection effect belonging to the
  interruption.
- **The interruption must lead away.** With the same clock (150), a
  neutral subject change and a re-encounter stitch are close: 3.08 /
  3.15 / 4.78 vs 2.68 / 3.64 / 4.72 (surprise / connection / coherence;
  the stitch trades some surprise for connection, Δ connection +0.49
  [−0.09, +1.07], not significant). Injecting the **premise itself**
  (1.14 / 1.04 / 3.18) or a window of the stream's **own past** (1.42 /
  1.52 / 3.06) is as bad as not interrupting at all — every paired CI vs
  the neutral change excludes zero (connection −2.11 [−2.83, −1.46] and
  −1.63 [−2.37, −0.91]; coherence −1.60 and −1.72; δ ≈ −0.6 to −0.7).
  Qualitatively, the own-past injection *reinforces* whatever attractor
  the stream is in (an exam-key well fed its own questions back). A
  return works only as a short stitch that still opens a new sentence;
  a literal return closes the loop. (Windows ending before 100 generated
  tokens — the two-token fragment before the first clock cut — are
  excluded from every battery-2 table; 73 such windows, mean surprise
  0.95. Applied to the ablation battery the same rule drops 10 bare and 3
  scaffold windows: bare 0.33 → 0.28, scaffold 3.22 → 3.19, nothing else
  changes; the ablation numbers above are as judged.)
- **Timing: salience is a good reader and a bad metronome.** The
  re-encounter stitch injected on salience events (jump, crystallization,
  recurrence; 1–9 per cell, median ≈5) makes the *event windows* better
  than salience-only without injection (3.92 / 2.99 / 3.75 vs 2.63 / 1.39
  / 3.71; connection Δ +1.6) — but the *stream* it produces is poor:
  uniform windows 2.18 / 1.68 / 3.93, against **4.70 / 3.48 / 5.50** for
  the same stitch on a clock of matched frequency (every 900 tokens;
  surprise Δ +2.02 [+1.62, +2.44] paired by seed, coherence +0.78 [+0.40,
  +1.15]) and 5.48 / 2.87 / 5.95 for a neutral change every 900 (45/60
  windows surprising *and* coherent — the best cell of the program).
  Salience events select good moments to look at, which is why
  salience-gated review beat clock review earlier (§5, dream_def); but as
  an interruption trigger they fire unevenly and rarely, leaving streams
  stuck for thousands of tokens. Salience should decide *where to look*,
  not *when to interrupt*.
- **Frequency: the yield of an interruption depends on the thread it
  breaks, and decays with distance from it.** With the neutral change
  every 75 tokens the stream is dead (surprise 0.88, δ = −0.83 vs 150):
  nothing has time to develop. Every 150: 3.08. Every 300, 600 and 900,
  the windows that end within ~160 tokens *after* an interruption score
  **5.28 / 3.35 / 5.95**, 5.40 / 3.20 / 5.65 and 5.90 / 2.80 / 6.10
  (surprise / connection / coherence; n = 40, 20, 40) — the highest values
  in the program, with 34/60 of the 300-early windows judged surprising
  *and* coherent (12/60 at 150) — while windows deeper into a segment
  fall back to ≈3.2–3.3 surprise and stay there (300: 3.29 / 2.99 /
  6.00; 600: 3.24; 900: 3.20). The same window shape (a break plus 150
  tokens of development) scores 3.08 when the broken thread was 150
  tokens long and 5.3–5.9 when it was 300–900: surprise needs a developed
  background to break. Weighting the two phases by their share of the
  stream (160/period), the period 300 gives the best stream — 4.35 /
  3.18 / 5.97 — against 3.82 / 2.69 / 5.52 (600), 3.68 / 2.43 / 5.35
  (900), 3.08 / 3.15 / 4.78 (150) and 0.88 / 1.35 / 3.15 (75); connection
  falls as segments lengthen. The loop's rhythm is: let a thread develop
  for a few hundred tokens, then break it away.

### 5.2 Two more generator families

The four conditions that carry the argument, re-run on **Qwen3-8B-Base**
(dense, 36 layers) and on **OLMo-2-13B** (a different pretraining diet —
the model that sinks into website footers, §5), same 10 seeds, 4,500
tokens, λ = 0, judged offline as in battery 2.

- *Qwen3-8B.* The ladder replicates with the same shape and slightly
  lower values: bare 0.68 / 0.38 / 3.45 (surprise / connection /
  coherence; 110 windows) → bare + habituation **1.47** / 0.87 / 3.93
  (surprise Δ +0.78 [+0.45, +1.13] paired by seed) → bare + habituation +
  clock reseed **2.73** / **3.23** / 4.42 (Δ +1.26 [+0.52, +2.14] over
  habituation; connection Δ +2.37 [+1.68, +3.12], δ = +0.80, p ≈ 10⁻¹⁴)
  ≈ full scaffold 2.73 / 1.53 / 4.30 (146 windows; connection Δ +0.66
  [+0.27, +1.07] over habituation, again below the plain clock reseed).
- *OLMo-2-13B.* Same ordering on surprise and connection, one new
  nuance on coherence: bare 1.35 / 0.91 / 2.97 (109 windows; OLMo's bare
  stream is less dead than Qwen's because it wanders across web genres
  instead of locking into literal orbits) → bare + habituation **2.37** /
  1.51 / 4.05 (Δ +1.02 [+0.44, +1.62]) → clock reseed **3.11** / **3.17**
  / 3.28 (surprise Δ +0.74 [+0.09, +1.36]; connection Δ +1.66 [+1.10,
  +2.20], δ = +0.58, p ≈ 3×10⁻⁸; **coherence −0.77 [−1.58, +0.03]**) ≈
  full scaffold 3.08 / 1.89 / 4.48 (144 windows; coherence +0.43 over
  habituation). On a generator whose well is web boilerplate, the plain
  interruption buys surprise and connection at a coherence cost — the
  injected narrative seed lands on 4,000 tokens of footers — and the
  scaffold's selective forgetting is what preserves coherence (4.48 vs
  3.28), the mechanism we had inferred from the calibration probes ("the
  accumulated context is the well; forgetting is what lets a seed take").
  Habituation buys part of the surprise, the interruption buys the rest
  and all of the connection, on three families; whether forgetting is
  worth its connection cost depends on how deep the generator's well is.

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

**A second judge family.** To check that the loop results are not the
taste of one model family, a stratified sample of 140 already-judged
windows (20 per condition across bare, habituation, clock reseed,
scaffold, re-encounter stitch, period 300 and salience-timed
re-encounter) was re-judged by Kimi K2.6 (Moonshot, via OpenRouter) with
the same rubric and k = 5. Agreement with Opus 5 on the median-of-5:
surprise Spearman ρ = +0.85, connection +0.77, coherence +0.71 (n = 140,
p < 10⁻²²). Kimi is more generous (means ≈1 point higher) and noisier
(intra-window spread 2.0–2.6 vs Opus's 0.5–0.7), but every condition
ordering replicates: bare 0.55 → habituation 3.15 → clock reseed 4.30 ≈
scaffold 4.10 → period 300 5.65 on surprise, and the neutral reseed and
the re-encounter stitch highest on connection (6.55, 6.45) under both
judges. A human blind rating (63 windows, two independent raters) is in
progress.

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

**Results** (ablation battery, 40 cells, Qwen3-30B-A3B; window vectors
mean-centered per layer before cosine geometry; battery 2 and the 8B
family below).

- **H1 — the freeze is everywhere, deepest at the surface.** Bare
  generation's mean step between consecutive windows is a third to a
  quarter of every interrupted condition's at every layer (0.06 → 0.03
  vs 0.20–0.28 → 0.05–0.08 from layer 0 to 47); its explored radius is
  0.13 at the input layers against 0.42–0.53, and the gap narrows with
  depth but never closes (0.24 vs 0.33–0.34 at layer 47, CIs disjoint).
  The three interrupted conditions are geometrically alike inside the
  network; what separates them is what the judge reads. The logit lens
  adds a twist: in bare generation the top-1 token stabilizes *later*
  (mean stable-commitment index 11.12 [11.04, 11.25] of 12 vs
  10.88–10.96) while the final distribution is far more confident (final
  entropy 0.34 vs 0.42–1.08) — the signature of copying, a late-layer
  computation that ends certain. Within bare cells, the windows judged
  more surprising are the ones that commit earlier (ρ = −0.54, p ≈
  5×10⁻⁵) and with higher entropy (ρ = +0.50).
- **H2 — what the judge calls surprise is surface departure with deep
  continuity.** Pooled over conditions, novelty of the judged window
  against everything before it correlates with judged surprise at the
  input layers (ρ = +0.47 at layer 0) and not at all at the top (−0.04 at
  layer 47) — but the pooled number is carried by the bare/interrupted
  contrast. Within interrupted conditions the sign flips with depth:
  local step at layer 0 correlates positively with surprise (salience-only
  +0.46, scaffold +0.23) and at layer 47 negatively (−0.34, −0.14);
  novelty against the whole past is negative at depth (salience-only
  −0.53 at layer 47, scaffold −0.35). Judged surprise rises with lexical
  change and *falls* with deep-state departure from the stream's own
  past: the windows the judge rewards are new at the surface and continuous
  underneath. Higher final entropy also predicts surprise within
  conditions (salience-only ρ = +0.47, p = 0.004).
- **H3 — the interruption that works barely touches the deep state.**
  Across a scaffold reseed *with forgetting* (context rebuilt from the
  premise), the state 64 tokens after the injection differs from the state
  before it by +0.09 (layer 4) growing to +0.21 (layer 40) cosine beyond
  the random-position control, and its similarity to the premise's own
  state rises by +0.09 → +0.20 with depth: forgetting is a deep
  re-encounter with the beginning, in the network's representation.
  Across a clock reseed *over preserved context* the same measures are
  +0.01–0.03 and ≈0 at every layer — and this is the interruption the
  judge rewards most (§5). Judged surprise and connection are not deep
  representational shifts; they are surface departures over an intact
  deep context, which is also why this arm keeps the most connection.
  Along the stream, similarity to the premise state is U-shaped in depth
  (≈0.9 at layer 0, ≈0.45–0.53 at layer 16, rising again at the top) and
  ordered at the top layer scaffold 0.85 > salience-only 0.79 > clock
  reseed 0.67 > bare 0.55 — the sentence-embedding "return to the
  premise" of the scaffold is a top-layer phenomenon.

**Battery 2 (100 cells) and the Qwen3-8B family (40 cells).**
- *Interruption depth scales with the thread it breaks, not with what is
  injected.* At period 150 every content moves the deep state by
  +0.01–0.02 beyond control (re-encounter stitch, premise, own past
  alike); at 300, +0.02–0.04; at 600, +0.04–0.075; at 75, ≈0. The
  longer the segment, the further the state has drifted and the larger
  the jump the injection produces — the network-internal counterpart of
  the frequency result (§5.1). The salience-timed stitch is the one
  150-token-scale injection that reliably moves the deep state (+0.02
  → +0.05) and brings it toward the premise (+0.02 → +0.03 at every
  layer), and it is also the arm whose stream the judge rates lowest:
  deep movement and judged quality dissociate here too.
- *Geometry by content.* The dead arms are the frozen ones: injecting the
  premise or the own past yields explored radii of 0.20–0.33 (like bare
  + habituation, 0.35–0.42) against 0.42–0.51 for the re-encounter stitch
  and 0.50–0.61 for periods 300–600 — the largest of the program; the
  clock-75 stream sits at 0.25–0.40 with a very confident final
  distribution (entropy 0.24, the lowest of any interrupted arm): a
  stream cut every 75 tokens re-enters a well between cuts. Across all
  668 judged windows of battery 2, layer-0 movement predicts judged
  surprise within every condition (ρ +0.3 to +0.6), and higher final
  entropy predicts it everywhere (ρ +0.3 to +0.6): confident is
  unsurprising.
- *Second family (Qwen3-8B-Base, 36 layers, every 3rd captured).* H1
  replicates: bare radius 0.14 → 0.16 (layer 0 → 35) against 0.46 → 0.23
  (clock reseed) and 0.54 → 0.32 (scaffold), with bare + habituation in
  between (0.33 → 0.23); bare has the most confident final distribution
  (entropy 0.18 vs 0.35–0.96). H3 replicates the dissociation: forgetting
  reseeds move the deep state by +0.03 → +0.10 (peaking mid-network) and
  bring it toward the premise (+0.10 at layer 21); clock reseeds over
  preserved context move it by +0.01–0.03 with no return. The
  commitment-layer ordering does *not* replicate (in the 8B the scaffold
  commits latest, 10.35 vs 9.45–9.92) — we report the late commitment of
  bare generation as a 30B observation, not a law.
- *Third family (OLMo-2-13B, 40 layers, every 3rd captured).* Bare is
  less frozen than in Qwen (radius 0.36 at layer 0 vs 0.48–0.61 for the
  interrupted arms; it wanders across genres), and the H3 dissociation
  replicates a third time, larger: forgetting reseeds move the deep state
  by +0.20 → +0.38 and return it toward the premise by +0.13 → +0.18 at
  every layer; clock reseeds over preserved context move it by
  +0.02–0.06 with no return.

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

Ten seeds; three generator families for the loop's core ladder
(Qwen3-30B-A3B, Qwen3-8B, OLMo-2-13B), one for the content / timing /
frequency battery; LLM judges (Opus 5, calibrated, agreeing with a second
family — Kimi K2.6, ρ 0.71–0.85 — but not yet with humans: a blind
human rating of 63 windows by two independent raters is in progress); English narrative seeds only; the judged
sample of each cell is 6 windows per kind, evenly spread, and the
salience-timed arms are judged on selected moments as well as on a
uniform grid (both reported); the residual-stream analysis is
correlational and uses mean-pooled windows at 13 layers, not attention
or causal interventions. The frequency and content results say what a
good interruption is made of in one system; whether the rhythm (~300
tokens) and the "lead away, then let it come back on its own" rule hold
for other genres and for tasks with a verifier is the next question —
the fusion the program points to: an interrupted loop over a *problem*,
with a verifier in place of the judge. Also next: a salience monitor
used as a reader (which windows to keep) inside a clock-driven loop, the
combination this battery recommends; and human validation of the judge.

## 10. Reproducibility

Everything in this repository (117 tests): sampler core, MLX adapter,
salience monitor, reverie engine, judges, novelty client, experiment
runners with resumable overnight execution and thermal logging. Every
run's per-step telemetry, texts and judgments under `runs/`; dated
decision log in `docs/PLANO.md`. Judge cost of the entire program to
date: ≈US$120.

## References

See `docs/references.bib` — every entry checked against the publisher/arXiv page (2026-08-16/17).
