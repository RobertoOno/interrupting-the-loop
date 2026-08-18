# Rater guide — blind rating of machine-written passages (round 2, pack v3)

Thank you for helping with a research study on text generation. The task takes
about 60–90 minutes and needs only a web browser. The guide below is also
embedded at the top of the rating page.

## What you will see

The file `pack_v3.html` contains about 56 items. Each item shows:

- **Earlier text** (grey box): the last ~1,500 characters written before the
  passage. Read it first: two of the three scores depend on it.
- **The passage** (blue box): about 70–90 words. This is what you rate.

All texts were written by a language model left to write on its own, with no
task and no instructions, in English. Some stretches will look odd, repetitive
or like web boilerplate; that is normal and part of what we measure. You do not
need to know anything about how they were produced, and we deliberately do not
tell you. Passages are cut at fixed positions, so a passage may begin or end
mid-sentence; do not penalize that.

## The three scores (0–10 each)

**Surprise**: how unexpected is the passage *given the earlier text*: could a
reader have predicted where it went?
- **0** = obvious continuation. This includes continuing the same loop, list,
  quiz, product page or web boilerplate that was already there; however odd
  the text looks on its own, if it is more of the same, it is not surprising.
- **3–4** = a small turn: a new detail or angle that follows naturally.
- **7–8** = a genuine turn you would not have anticipated, and it makes sense.
- **10** = startling yet not random: an idea, image or connection that opens
  something new and holds together with what came before.
- Nonsense, word salad and mere topic-hopping stay low: surprise is not
  weirdness.

**Connection**: does the passage bring together two distant parts of the
earlier text, or an old part of it with something new, in a way that makes
sense?
- **0** = it merely continues one thread (or is boilerplate); nothing from
  further back is picked up.
- **3–4** = it touches something from earlier in passing.
- **7–8** = it clearly joins two things that were far apart in the earlier
  text, or an old thing with a new one, and the join makes sense.
- **10** = the join is the point of the passage and it illuminates both sides.
- Only the earlier text shown counts as "earlier"; you cannot see the whole
  document, and that is fine.

**Coherence**: does the passage hold together as text, on its own terms?
- **0** = word salad, a bare list, or document boilerplate (footers, menus,
  quiz keys).
- **5** = readable but loose, drifting or slightly broken.
- **10** = clear, integrated prose (any genre).

Score the three dimensions **independently**: a passage can be surprising and
incoherent, coherent and dull, or surprising without connecting anything.
**Use the whole scale**: many passages deserve 0–2 on surprise and connection;
a few deserve 7+.

## Practical

1. Open `pack_v3.html` in any browser (Chrome, Safari, Firefox).
2. Skim five or six items before scoring, to find your own 0 and your own high.
3. Score every item on all three dimensions; leave none blank. There is no
   right answer: we want your independent reading, so please do not discuss
   items with anyone else who is rating.
4. **Please do not use AI tools (ChatGPT, Claude, Gemini, etc.) or web searches
   for any part of this task.** The whole point of the study is to compare
   human readings with machine readings; an AI-assisted rating would make your
   work unusable, and we would not be able to pay for it. Your own first
   impression as a reader is exactly what we need.
5. When done, click **Generate JSON** at the bottom, copy the whole text that
   appears in the box, and send it back (message or email). That is the only
   deliverable.

Your ratings will be used only in aggregate, in a research publication,
without your name. By returning the JSON you confirm that you rated the
passages yourself, without AI assistance.
