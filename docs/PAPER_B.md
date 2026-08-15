# Improbable Inputs: Prompting from the Tail of the Prompt Distribution

> **Status (2026-08-15): the pilot effect did not replicate.** Definitive
> run (5 arms, k=3 judgments, n≈15/arm when stopped): the typical prompt
> matched or beat every improbable arm; two improbable arms were
> significantly *worse*; input improbability (semantic or perplexity) did
> not correlate with judged novelty (|r| < 0.2). This document is kept as
> an honest negative result and as the motivation for the reverie-loop
> program (PLANO → "O loop de devaneio"): the fertile improbable is
> generated from inside a closed loop, not injected from outside.
> Details: PLANO.md ("Experimento do input improvável" → "Definitivo").

> Working draft (pre-paper B). Thesis by Roberto Onofilho; pilot 2026-08-15.
> Lab notebook: PLANO.md ("Experimento do input improvável").

## Abstract (draft)

Every prompt a human writes is a sample from roughly the same distribution
the model was trained on. In aggregate, prompts therefore activate the same
regions of a language model, and the model's "creativity" is the average
creativity of its training distribution, reprocessed. We hypothesize that
the improbable lives not only in the tail of the model's *output*
distribution — where decoding research has looked — but in the tail of the
*prompt* distribution, which nobody explores systematically: an input no
human would compose activates internal configurations no human has
activated. We test this with three input arms developed by one strong model
(Claude Opus 5) under one instruction and judged by a second family (Claude
Sonnet 5) with a delta-over-nearest-equivalent rubric. In a pilot (n=8 per
arm) the composed-improbable arm produced the highest novel delta (5.1 vs
4.4–4.5 on a 10-point scale), the top three ideas of the experiment, and the
first judged deltas of 6/10 across all our conceptual-blending work. Token
perplexity of the input, our first candidate for the independent variable,
did **not** track judged novelty (r = −0.26): syntactic improbability is not
semantic improbability. We propose measuring an input's distance from the
distribution of real prompts instead, and specify the definitive
experiment.

## 1. Thesis and prior work

- **Decoding-side novelty** (our Paper A; min-p, typical sampling): pushes
  the model's *output* into its own tail. Complementary, not competing.
- **Prompt engineering / role prompting / persona injection**: alters
  register but stays inside the space of prompts people write.
- **Conceptual blending prompts** (Fauconnier & Turner; our Phase 2):
  distant *content* with a familiar *request shape* — "blend A and B" is a
  common request. Our pilot suggests the request shape matters more than
  the content distance.
- **The gap**: no work we found treats *the improbability of the whole
  input* as a controlled independent variable and measures its effect on
  judged novelty with a strong developer and a cross-family judge.

## 2. Method

**Arms** (same task, same developer, same judge; only the input differs):

1. *typical* — the prompt most people would write ("Give me an innovative
   idea related to X").
2. *concepts* — two semantically distant concepts (percentile 75–95 of
   pairwise cosine distance in the model's own embedding space); Phase 2
   control.
3. *improbable* — a composed context built to sit far from any plausible
   prompt: four distant concept fragments + an alien register ("as
   instructions left for a successor who will not be human") + a
   non-natural constraint ("it must work worse the more people believe in
   it").

**Developer**: Claude Opus 5 (Amazon Bedrock), effort high, one instruction:
derive a mechanism first, then name the phenomenon, then one non-obvious
consequence; treat all input as material, never dismiss it.

**Judge**: Claude Sonnet 5, blind to arm, rubric: coherence, nearest existing
equivalent (always named), novel delta over it, delta significance (0–10),
value; score = geometric mean of coherence × delta significance × value.

**Independent variable**: input improbability. Pilot: mean per-token
perplexity of the input under Qwen3-8B-Base (local).

## 3. Pilot results (n = 8 per arm; 23 judged, 1 refusal)

| arm | input ppl (Qwen) | delta significance | score mean (max) |
|---|---|---|---|
| typical | 287 | 4.43 ± 0.49 | 5.86 (6.54) |
| concepts | 777 | 4.50 ± 0.87 | 5.83 (6.95) |
| **improbable** | 256 | **5.12 ± 0.93** | **6.64 (7.56)** |

The improbable arm holds the top three ideas and the only deltas of 6.
Difference vs the other arms ≈ +0.65 delta (≈ 0.9σ at n=8) **[TBD:
significance at n≥30]**.

Examples (improbable arm, judged delta 6): an archive that measures
collective longing and is erasable not by censorship but by "administered
kindness"; an agent's capability budget minted from the min-entropy of an
unbriefable poll about that agent, so consensus is self-defeating; a
calendar whose intercalation is a thermodynamic receipt for fuel burned.

## 4. The measurement finding

Perplexity ranks the arms *backwards*: bare concept pairs have the highest
ppl (two loose words are "strange" to a language model) and the lowest
delta; the composed context has *low* ppl (it is fluent prose) and the
highest delta. Correlation between log input-ppl and delta: −0.26.

Interpretation: **syntactic improbability ≠ semantic improbability**. What
plausibly matters is how far the *request* sits from the requests people
actually make — a property of the input's position in prompt-space, not of
its surface likelihood. This is itself a contribution: it disqualifies the
obvious operationalization and motivates the one in §6.

## 5. Why a strong developer matters

In Phase 2, a smaller couturier (Kimi K2.6) domesticated every input into
fluent recombination of the known (all deltas ≤ 4). Opus 5 sustained the
alien frame without normalizing it and derived mechanisms with internal
logic. The pilot therefore also bounds the hypothesis: improbable inputs
help only when the developer can hold the frame; with weaker developers the
input is regressed to the mean **[TBD: replicate with a second developer
family to separate "Opus is good" from "improbable inputs help"]**.

## 6. Definitive experiment (specification)

- **Independent variable**: semantic improbability = cosine distance from
  the input's sentence embedding to the centroid (and to the k nearest
  neighbors) of a reference corpus of real prompts (a public instruction
  set, ≥10k items). Report both ppl and this distance; the claim is about
  the latter.
- **Arms**: typical / concepts / improbable / **improbable-without-register**
  (fragments + constraint only) / **register-only** (typical request in the
  alien register) — separates the register effect from the fragment effect.
- **n ≥ 30 per arm**, seeds independent; **k = 3 judgments per cell** (judge
  variance was ±2 points on the same text in Phase 2), report the median.
- **Two developers** (Opus 5, one non-Anthropic strong model) × one judge
  family not equal to the developer.
- **Analysis**: delta ~ semantic-distance (mixed model with arm as factor);
  bootstrap CIs on arm differences; correlation of delta with semantic
  distance *within* arms.
- **Refusal handling**: retry with a fallback developer; log rate.
- **Human check**: 3 raters on the top-10 vs bottom-10 judged ideas,
  blind, "would a domain expert find this genuinely new?".
- Cost estimate: ~US$15–25 on Bedrock.

## 7. Relation to Paper A

Paper A moves the *output* into the tail (decoding). Paper B moves the
*input* into the tail (prompting). Both are instances of one program: the
improbable-but-coherent as the site of the new, with the model as the
integrator that rationalizes the accident. A natural joint experiment —
Paper A's sampler generating Paper B's improbable inputs — was piloted as
the "hybrid" (PLANO) and is queued after the register/fragment ablation.
