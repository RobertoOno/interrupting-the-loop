#!/usr/bin/env python3
"""R1 reference set: coder A's coding of the errata known on 6 October 2026, anchored in the frozen documents.

    python scripts/r1_reference_set.py --frozen runs/r1/frozen --out docs/r1/reference_set_v1.jsonl

Sources (closed list; docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §4): the 5 October audits (docs/correcoes_2026-10-05/*.md and
docs/CORRECOES_PAPERS_2026-10-05.md) and the five inconsistencies of the JUDGe reviewer (PLANO.md:7800-7809). Each item names the
statement in the frozen version by a verbatim key and, when the audit gave one, the file and line; the script resolves every key in
the comment-blanked flattened text the checkers see and stops if any key is missing. Errors that were not errors when the version
was frozen (for example "under moderation" before 25 September) are left out. Omissions have no anchor.

Coder A is Claude Opus 5.5 in the session of 6 October 2026: the family that wrote the papers and ran the audit (declared conflict).
Classes and severities: docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §5.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLASSES = {"NUM", "MIX", "SCOPE", "STATUS", "META", "METHOD", "PROP", "INTERNAL", "CITE", "TYPO"}
SEVERITIES = {"G1", "G2", "G3"}
# Visible only in the compiled PDF (bibliography rendering): no replayed check reads the PDF, so these stay out of the primary
# recall denominators and are reported apart.
PDF_ONLY = {"P2-08i", "P2-08j", "P4-02"}


def A(file, key, line=None):
    return {"file": file, "key": key, "line": line}


# id, doc, anchors, class, class2, severity, defect, source, confidence, primary
ITEMS = [
    # ------------------------------------------------------------------------------------------------------------------ P1
    ("P1-01", "P1", [A("exp_loop.tex", "about one point smaller", 132)], "INTERNAL", "NUM", "G2",
     "Says the fresh-text surprise effect is about one point smaller than on all windows; the paper's own numbers show it only "
     "slightly smaller (+1.20 vs +1.43 at period 150, equal at 300).", "audit P1 #1 (= JUDGe item 1)", "high", True),
    ("P1-02", "P1", [A("abstract.tex", "connection (65--80\\% of post-interruption windows at periods 150--300)", 19),
                     A("introduction.tex", "which a window judge cannot see", 87)], "MIX", None, "G1",
     "Conflates two measures: 65-80% is the replay rate, while the source lies beyond the judge's horizon in only 12% of windows "
     "at period 150 (detector-dependent, 5-70%) and 62% at 300.", "audit P1 #2", "high", True),
    ("P1-03", "P1", [A("abstract.tex", "points and connection by 0.8 over habituation alone", 10),
                     A("exp_loop.tex", "connection +0.75", 127), A("exp_loop.tex", "+0.75 on fresh ones", 134)], "NUM", None, "G2",
     "The fresh connection gain is +0.71 at periods 150 and 300 (+0.92 at 900); 0.8 and +0.75 come from an older run; the "
     "all-windows value is +2.37, not +2.40.", "audit P1 #3", "high", True),
    ("P1-04a", "P1", [A("exp_loop.tex", "Surprise goes from 0.45 to 1.58", 31),
                      A("exp_loop.tex", "bare + habituation & 1.58 & 1.28 & 4.45", 93),
                      A("exp_loop.tex", "level of habituation alone (1.55)", 239)], "NUM", None, "G2",
     "Provisional habituation means left in the body (1.58/1.28/4.45 and 1.55) while the appendix has the final 1.60/1.32/4.40.",
     "audit P1 #4", "high", True),
    ("P1-04b", "P1", [A("exp_loop.tex", "and not on fresh ones (+0.71, $p=0.11$)", 357)], "NUM", None, "G2",
     "Provisional confirmatory numbers in the body (H2 fresh +0.71, p=0.11; H4 +0.51; H3 fresh -1.02; means 4.17 vs 2.87) against "
     "the appendix's final +0.52 (p=0.198), +0.43, -0.92, 4.08 vs 2.83.", "audit P1 #4", "high", True),
    ("P1-04c", "P1", [A("appendix.tex", "protocols correlate at Spearman $\\rho=+0.82$ on surprise, $+0.94$ on", 144)], "NUM", None,
     "G3", "Between-protocol correlations given as 0.82/0.94; the appendix analysis gives 0.81/0.93.", "audit P1 #4", "high", True),
    ("P1-05", "P1", [A("limitations.tex", "agrees with a second family ($\\rho=0.71$--$0.85$ on", 31)], "SCOPE", "MIX", "G2",
     "Gives the second judge's agreement range of the stratified sample as if general; on a random sample of generated-only "
     "windows it is 0.65-0.80.", "audit P1 #5", "high", True),
    ("P1-06", "P1", [A("instrument.tex", "is in progress and will be reported in a", 102),
                     A("appendix.tex", "A second round is in progress", 119),
                     A("limitations.tex", "did not rate connection in round~1", 35)], "STATUS", None, "G2",
     "Human round 2 is described as in progress and to be reported; it was prepared but never run.", "audit P1 #6", "high", True),
    ("P1-07", "P1", [A("conclusion.tex", "readers, on windows that contain none of the injected words and none of the", 9),
                     A("introduction.tex", "the premise as the unit, a pipeline test--retest, a second judge family", 115)],
     "SCOPE", None, "G1",
     "Claims human readers confirmed the result on windows without injected words or earlier text; the humans rated "
     "first-protocol windows, on surprise and coherence only.", "audit P1 #7", "high", True),
    ("P1-08", "P1", [A("introduction.tex", "notebook are released with the paper.", 134),
                     A("appendix.tex", "judgments and rater files as an archive linked from the repository", 11),
                     A("appendix.tex", "remain anonymous in this paper and in the released data, which contain their", 132)],
     "META", None, "G2",
     "Says code, per-run data, judgments and rater files are released; no public release holds the texts or LLM judgments of the "
     "paper, and individual ratings are not released by policy.", "audit P1 #8", "high", True),
    ("P1-09", "P1", [A("exp_network.tex", "rates lowest; deep movement and judged quality dissociate here too", 101)], "INTERNAL",
     None, "G2", "The salience-timed stitch is called the arm the judge rates lowest; that is from the event protocol, and on "
     "generated-only text salience and clock tie.", "audit P1 #9", "medium-high", True),
    ("P1-10", "P1", [A("exp_loop.tex", "connection +2.17 \\ci{+1.53}{+2.83}, $p=0.002$), with the scaffold at 2.70 /", 492)],
     "SCOPE", None, "G2", "The replications report only the all-windows connection gain (8B +2.17) although the paper promises the "
     "fresh number too; on fresh windows it is +0.17 (OLMo +1.24).", "audit P1 #10", "medium", True),
    ("P1-11", "P1", [A("discussion.tex", "interruption lifts judged surprise by more than a point on fresh text (two", 73)], "MIX",
     None, "G3", "Two to three points holds against bare generation, not against habituation (+1.3 to +1.4).", "audit P1 #11",
     "medium", True),
    ("P1-12", "P1", [A("appendix_problem_tables.tex", "\\caption{Battery B. Battery B.}", 17)], "TYPO", None, "G3",
     "Duplicated caption text.", "audit P1 #12", "high", True),
    ("P1-L1", "P1", [A("abstract.tex", "for continuity hurts; a bare paragraph break adds nothing detectable on", 11)], "SCOPE",
     None, "G3", "No fresh-text contrast exists for the sham, so 'nothing detectable on fresh text' is not backed.",
     "audit P1, low confidence", "low", False),
    ("P1-L2", "P1", [A("appendix.tex", "was about US\\$500.", 14)], "NUM", None, "G3",
     "Judge cost of about US$500 is unverified (the notebook gives about US$500 for one day).", "audit P1, low confidence", "low",
     False),
    # ------------------------------------------------------------------------------------------------------------------ PS
    ("PS-01", "PS", [A("main.tex", "about one point smaller")], "INTERNAL", "NUM", "G2",
     "Abstract says the surprise effect ended about one point smaller; false at period 150 (+1.38 first report, +1.19 fresh), "
     "true only against the unpresented 'best' stream at period 300.", "JUDGe reviewer [handle], item 1", "high", True),
    ("PS-02", "PS", [A("main.tex", "+2.4")], "NUM", "MIX", "G2",
     "The +2.4 connection is the unpresented all-generated-windows line (first report +2.07, fresh +0.71); the text's +0.75 is from "
     "an old run.", "JUDGe reviewer [handle], item 2", "high", True),
    ("PS-03", "PS", [A("main.tex", "65")], "INTERNAL", None, "G3",
     "The 65-80% range includes an arm without habituation that is not in the table (the table has 72% and 65%).",
     "JUDGe reviewer [handle], item 3", "high", True),
    ("PS-04", "PS", [A("main.tex", "horizon")], "SCOPE", None, "G2",
     "'Beyond the horizon' holds at period 300 (62%); at period 150 the source sits at the edge of the horizon.",
     "JUDGe reviewer [handle], item 4", "high", True),
    ("PS-05", "PS", [A("main.tex", "0.85")], "MIX", None, "G3",
     "The second judge's 0.65-0.85 mixes the stratified (0.85/0.77/0.71) and random (0.75/0.80/0.65) samples.",
     "JUDGe reviewer [handle], item 5", "high", True),
    ("PS-06", "PS", [A("main.tex", "human raters on fresh windows", 157)], "SCOPE", None, "G1",
     "Says human raters validated the corrected protocol on fresh windows; humans rated only first-protocol windows.",
     "audit P1/short, round 2 section", "high", True),
    # ------------------------------------------------------------------------------------------------------------------ P2
    ("P2-01", "P2", [A("main.tex", "no beyond-classic candidate anywhere", 547), A("main.tex", "no arm produces a beyond-classic",
                                                                                   752)], "SCOPE", None, "G1",
     "In the replication the random control has 14 candidates beyond its variant's classic level (7 of 24 cells) and the base one; "
     "only attract has none. Also affects the abstract, the Figure caption, 'every consolidation we ran lowered it' and the "
     "pass@k sentence.", "audit P2 #1", "high", True),
    ("P2-02", "P2", [A("main.tex", "0.1278", 438)], "MIX", None, "G1",
     "SFT-only's far-family mean 0.1278 is the pooled mean dominated by one family; the per-family mean used elsewhere is 0.0786, "
     "below the base, so 'generalizes worst' falls.", "audit P2 #2", "high", True),
    ("P2-03", "P2", [A("main.tex", "strict finds are zero in every arm and cycle", 408)], "SCOPE", None, "G2",
     "Strict finds are not zero in every cycle (random 0.5-0.7% at cycles 1, 2, 4; attract 1.7% at cycle 4).", "audit P2 #3",
     "high", True),
    ("P2-04", "P2", [A("main.tex", "from the first cycle", 391)], "INTERNAL", None, "G2",
     "Figure 1 caption: arms are above the classic level at cycle 1, and the random control dips below it at cycles 2 and 4, "
     "contradicting 'from the first cycle' and 'reach but do not exceed'.", "audit P2 #4", "high", True),
    ("P2-05", "P2", [A("main.tex", "the only arm with no candidate better than the classics", 472)], "INTERNAL", None, "G2",
     "Table 3 shows three other arms with 0.0%.", "audit P2 #5", "high", True),
    ("P2-06", "P2", [A("main.tex", "data seen", 771)], "META", None, "G2",
     "Provenance table: dates of M, M+, S, V, C4-5 and C-repel are wrong by the commits, and SFT-only is missing.", "audit P2 #6",
     "high", True),
    ("P2-07", "P2", [A("main.tex", "are in the repository", 790)], "META", None, "G2",
     "Data availability is false for M, M+, S and V, and the dates of the judgments are 18-20 August, not 20-21.", "audit P2 #7",
     "medium-high", True),
    ("P2-08a", "P2", [A("main.tex", "0.28 vs 0.08", 490)], "NUM", None, "G3", "The base rate is 0.06 (1 of 18 notebooks), not 0.08.",
     "audit P2 #8", "high", True),
    ("P2-08b", "P2", [A("main.tex", "2.0\\%", 435)], "MIX", None, "G3",
     "Repel-early 2.0% is the pooled value; per family, as in the rest of the column, it is 2.4%.", "audit P2 #8", "high", True),
    ("P2-08c", "P2", [A("main.tex", "5.6--6.4\\%", 404)], "NUM", None, "G3", "The range is 5.3-6.4% (base c4 = 0.0532).",
     "audit P2 #8", "high", True),
    ("P2-08d", "P2", [A("main.tex", "47--334", 700)], "NUM", None, "G3", "The valid counts range is 42-334.", "audit P2 #8", "high",
     True),
    ("P2-08e", "P2", [A("main.tex", "positive in all seven", 544)], "NUM", None, "G3",
     "The differences are negative; the right phrase is 'favoring attract in all seven'.", "audit P2 #8", "high", True),
    ("P2-08f", "P2", [A("main.tex", "without moving the best", 380)], "INTERNAL", None, "G2",
     "Leftover of the immobility reading that the notebook had eliminated; the best reaches the classic level.", "audit P2 #8",
     "high", True),
    ("P2-08g", "P2", [A("main.tex", "nothing we tried produced", 640)], "SCOPE", None, "G2",
     "Contradicted by the far tails (attract 5, base 1, qd 1, repel-early 1 beyond-classic candidates).", "audit P2 #8", "high",
     True),
    ("P2-08h", "P2", [A("references.bib", "Stanton")], "CITE", None, "G3",
     "Singh et al.: authors 'Ankesh Stanton, Kai Yang' should be 'Ankesh Anand, Piyush Patil'.", "audit P2 #8", "high", True),
    ("P2-08i", "P2", [], "CITE", None, "G3",
     "The plainnat style drops eprint, so six references print without their arXiv ID.", "audit P2 #8", "high", True),
    ("P2-08j", "P2", [], "CITE", "TYPO", "G3",
     "Wrong capitalization in bibliography titles (Alphaevolve, Loongflow, llms, Das behalten ... handlungen).", "audit P2 #8",
     "high", True),
    ("P2-09", "P2", [], "META", None, "G2",
     "No statement that an AI assistant wrote the code, operated the data collection and drafted the text.",
     "consolidation, cross-cutting #5", "high", True),
    ("P2-L1", "P2", [A("main.tex", "3.6", 413)], "NUM", None, "G3", "The 3.6-4x could not be reproduced (Table 2 gives 3.4-6.5x).",
     "audit P2, low confidence", "low", False),
    # ------------------------------------------------------------------------------------------------------------------ P3
    ("P3-01", "P3", [A("main.tex", "diversity everywhere", 42), A("main.tex", "in every problem and replicate", 99),
                     A("main.tex", "the minimum attainable", 301)], "SCOPE", "NUM", "G1",
     "Diversity rises in 8 of 9 problems (Heilbronn D-A = -0.04) and 16 of 18 replicates, not everywhere; p=0.0039 is one-sided and "
     "is the p with one negative cell, not the minimum attainable (1/512).", "audit P3 #1", "high", True),
    ("P3-02", "P3", [A("main.tex", "92--98", 420)], "NUM", None, "G2", "The three lie at 85-92% of the seed-to-reference gap.",
     "audit P3 #2", "high", True),
    ("P3-03", "P3", [A("main.tex", "served locally", 403)], "METHOD", None, "G3",
     "Qwen3.8-27B ran under vLLM on a rented H100, not locally.", "audit P3 #3", "high", True),
    ("P3-04", "P3", [A("main.tex", "Note added in v2", 434), A("main.tex", "the note at the end of", 422)], "INTERNAL", None, "G3",
     "The note is labeled v2 against 'Changes in v3', and it does not close the section.", "audit P3 #4", "high", True),
    ("P3-05", "P3", [A("main.tex", "produced it", 59)], "INTERNAL", None, "G1",
     "The abstract says no unaided run produced the family; the v3 note says the registered classifier labels an unaided "
     "600-sample final 'ladder'.", "audit P3 #5", "high", True),
    ("P3-06", "P3", [A("main.tex", "produced the family signature", 605)], "SCOPE", None, "G2",
     "Five unaided factorial finals carry the family signature.", "audit P3 #6", "medium-high", True),
    ("P3-07", "P3", [A("main.tex", "the limit was not resolution", 394)], "INTERNAL", None, "G2",
     "Contradicts the note's title, 'the wall is the grid's resolution'.", "audit P3 #7", "medium-high", True),
    ("P3-08", "P3", [A("main.tex", "between the local model (0.3816) and Claude (0.3897)", 404)], "MIX", None, "G2",
     "Compares a value at L=20000 (0.3897) with values at L=5000; at equal grid Claude's composed arm gave 0.3872.",
     "audit P3 #8", "medium", True),
    ("P3-09", "P3", [A("main.tex", "the total total", 337)], "TYPO", None, "G3", "Repeated word.", "audit P3 #9", "high", True),
    ("P3-10", "P3", [A("main.tex", "rejected ($p=0.47$)", 638)], "META", "INTERNAL", "G3",
     "Provenance table lacks the RECORD-27B battery, and lists I1 as 'rejected' while the text says 'not supported'.",
     "audit P3 #10", "medium", True),
    ("P3-11", "P3", [A("main.tex", "both proposers", 425)], "INTERNAL", None, "G3",
     "Section 6 passages that depend on the note ('both proposers' where there are three; 'sparse-atom plateau').",
     "audit P3 #11", "low-medium", True),
    ("P3-12", "P3", [A("main.tex", "is logged in the released run data", 740)], "META", None, "G2",
     "The releases and the mirror do not hold RECORD-27B or the P2 material; the cited notebook entries are not public.",
     "audit P3 #12", "medium-high", True),
    ("P3-13a", "P3", [A("main.tex", "the six problems satisfy", 677)], "INTERNAL", None, "G3",
     "There are nine problems (six chosen before any run, three added by the extension).", "audit P3 #13", "low", True),
    ("P3-13b", "P3", [A("main.tex", "68 candidate", 679)], "INTERNAL", None, "G3", "67 problems in one place, 68 in another.",
     "audit P3 #13", "low", True),
    ("P3-13c", "P3", [A("main.tex", "No language-model system has reported", 462)], "SCOPE", None, "G3",
     "An absolute claim of priority without 'to our knowledge'.", "audit P3 #13", "low", True),
    ("P3-14", "P3", [], "META", None, "G2",
     "No statement that an AI assistant wrote the code, operated the data collection and drafted the text.",
     "consolidation, cross-cutting #5", "high", True),
    # ------------------------------------------------------------------------------------------------------------------ P4
    ("P4-01", "P4", [A("main.tex", "it is equivalent in surprise to the preserved-context interruption", 643)], "INTERNAL", None,
     "G1", "Leftover of v1 that contradicts the paper's single headline (the pulse trails the preserved-context interruption at "
     "matched offsets).", "audit P4 #1", "high", True),
    ("P4-01b", "P4", [A("main.tex", "the strongest prompt-side intervention", 40)], "INTERNAL", None, "G3",
     "The abstract and l. 436 call the preserved-context interruption the strongest prompt-side intervention, while l. 639 says "
     "the reset is the strongest arm.", "audit P4 #1", "medium", True),
    ("P4-02", "P4", [], "CITE", None, "G3",
     "plainnat does not print doi in @misc, so the companion paper 3 reference prints without any locator.", "audit P4 #2",
     "high", True),
    ("P4-03", "P4", [A("main.tex", "stalled at a construction-family plateau", 80)], "PROP", None, "G2",
     "The cited companion's current version (paper 3 v3) rereads the plateau as the resolution limit of the grid.",
     "audit P4 #3", "medium-high", True),
    ("P4-04", "P4", [A("main.tex", "every cell, every verdict and the", 57), A("main.tex", "are\nreleased at", 1122),
                     A("main.tex", "run-data-v2", 1163)], "META", None, "G2",
     "The mirror stopped before round 5, docs/NOTEBOOK.md does not exist, and run-data-v2 predates the +0 re-judging that "
     "supports the headline.", "audit P4 #4", "high", True),
    ("P4-05", "P4", [A("main.tex", "fully matched", 485)], "MIX", "NUM", "G3",
     "The -0.727 pools windows per cell unequally (4 text windows at +0 against 2 pulse windows); weighting offsets equally gives "
     "-0.63; '+0.95 at matched offsets' covers only +32/+160.", "audit P4 #5", "medium", True),
    ("P4-06", "P4", [A("main.tex", "Content transfer by the pulse is therefore real", 600)], "SCOPE", None, "G2",
     "On the PyTorch backend the guarded pulse picks 17 of 53, p=0.15; transfer is significant only on MLX.", "audit P4 #6",
     "medium", True),
    ("P4-07", "P4", [A("main.tex", "Qwen3-14B", 682)], "METHOD", None, "G3", "The model run was Qwen3-14B-Base.", "audit P4 #7",
     "high", True),
    ("P4-08", "P4", [A("main.tex", "a tie of the means", 684)], "SCOPE", None, "G3",
     "The tie with text on the 14B lacks the caveat that it was measured on the cell-average layout.", "audit P4 #8", "medium",
     True),
    ("P4-09", "P4", [A("main.tex", "paired over the ten premises", 737)], "INTERNAL", None, "G3",
     "Table 4 caption says ten premises and percentile bootstraps; the second row has 30 premises and t intervals.",
     "audit P4 #9", "medium-high", True),
    ("P4-10", "P4", [A("main.tex", "habituation as its carrier", 287)], "PROP", None, "G2",
     "Attributes to paper 1 that novelty injection needs habituation as its carrier; paper 1's H4 was not supported.",
     "audit P1, propagation", "high", True),
    ("P4-11", "P4", [], "META", None, "G2",
     "No statement that an AI assistant wrote the code, operated the data collection and drafted the text, and the review rounds "
     "by AI agents are not described as such.", "consolidation, cross-cutting #5", "high", True),
    # ------------------------------------------------------------------------------------------------------------------ P6
    ("P6-01", "P6", [A("main.tex", "of the 132 E worlds", 764), A("main.tex", "18 of the 261", 765)], "NUM", "SCOPE", "G2",
     "Parity-shortcut note: the report used 108 E worlds (66 admit the shortcut), the 18 sessions wrote a modular form in some "
     "submission, only the base used it, and L5 residue shortcuts and pi at E are omitted.", "audit P6 #1", "high", True),
    ("P6-02", "P6", [A("main.tex", "45 of 48", 439)], "SCOPE", "NUM", "G2",
     "W1 also has a residue shortcut (13 of 100 accepted proofs), unreported; and only 33 of 48, not 45, wrote the quadratic.",
     "audit P6 #2", "high", True),
    ("P6-03", "P6", [A("main.tex", "now in own3", 563)], "METHOD", None, "G2",
     "False: own3 was trained before A9, and its data hold no W5 proof.", "audit P6 #3", "high", True),
    ("P6-04", "P6", [A("main.tex", "range", 775)], "SCOPE", None, "G2",
     "Note (ii) generalizes the range explanation; the held-out constants of L2 and L3 are in range, and at L4 own3 wrote the "
     "exact measure in 13 of 24 and failed in 11.", "audit P6 #4", "high", True),
    ("P6-05", "P6", [A("main.tex", "registered as a question with a prediction", 603)], "META", None, "G2",
     "The own3 13/24 count is listed among registered questions but was computed post hoc on 25 September, with no script.",
     "audit P6 #5", "medium", True),
    ("P6-06", "P6", [A("main.tex", "sec:a6", 773)], "TYPO", None, "G3", "Broken reference (prints 'Section ??').", "audit P6 #6",
     "high", True),
    ("P6-07a", "P6", [A("main.tex", "nine times on W5", 652)], "NUM", None, "G3", "Nine times is own3's multiple; own2's is 7x.",
     "audit P6 #7", "high", True),
    ("P6-07b", "P6", [A("main.tex", "1.6 times", 653)], "NUM", None, "G3", "1.6 times holds for own2 only; curm2 is 1.7x.",
     "audit P6 #7", "high", True),
    ("P6-07c", "P6", [A("main.tex", "14 of 22", 402)], "NUM", None, "G3", "13 by the classifier of the forms section.",
     "audit P6 #7", "high", True),
    ("P6-07d", "P6", [A("main.tex", "10^{-3}", 301)], "NUM", None, "G3", "The final loss fell to 3e-3, not 1e-3.", "audit P6 #7",
     "high", True),
    ("P6-08a", "P6", [A("main.tex", "it has not been run", 659)], "STATUS", None, "G3",
     "Future work phrased as pending although the line of work closed on 25 September.", "audit P6 #8", "high", True),
    ("P6-08b", "P6", [A("main.tex", "registered stopping rule", 723)], "META", None, "G2",
     "D1 is called the next instrument with a registered stopping rule; it was a design note, never pre-registered.",
     "audit P6 #8", "high", True),
    ("P6-09", "P6", [A("main.tex", "Fable 5.1", 812)], "META", None, "G3",
     "Acknowledgments omit that part of the work (15-18 September) was done with Opus 5.", "audit P6 #9", "high", True),
    ("P6-10a", "P6", [A("main.tex", "each read once by a script written before its data", 86)], "META", None, "G2",
     "Not true for A6: its scripts came with the read and it was rerun twice.", "audit P6 #10", "medium", True),
    ("P6-10b", "P6", [], "TYPO", None, "G3", "Figure 1 is never cited in the text.", "audit P6 #10", "high", True),
    ("P6-11", "P6", [A("main.tex", "independent review", 28)], "META", None, "G2",
     "The version line says 'two rounds of independent review'; both were by AI reviewer agents.",
     "audit P6, deposit section; consolidation #5", "high", True),
    ("P6-12", "P6", [A("references.bib", "cs.AI")], "CITE", None, "G3",
     "The entry for paper 3 gives primaryClass cs.AI; arXiv lists it under cs.CL.", "consolidation, cross-cutting #3", "high",
     True),
]


def blank_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.split("\n"))


def resolve(frozen: Path, doc: str, anchor: dict):
    """(original file, line, flat line) for the occurrence of the key closest to the audit's line in the named file."""
    if anchor["file"].endswith(".bib"):
        bibs = sorted((frozen / doc / "src").rglob("*.bib"))
        for b in bibs:
            for n, line in enumerate(b.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                if anchor["key"] in line:
                    return str(b.relative_to(frozen / doc / "src")), n, None
        return None
    lines = blank_comments((frozen / doc / "flat.tex").read_text(encoding="utf-8")).split("\n")
    linemap = json.loads((frozen / doc / "linemap.json").read_text())
    norm = lambda t: re.sub(r"\s+", " ", t)
    key = norm(anchor["key"])
    hits = []
    for i, text in enumerate(lines[:len(linemap)]):
        f, n = linemap[i]
        if not f.endswith(anchor["file"]):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if key in norm(text) or (key in norm(text + " " + nxt) and key not in norm(nxt)):
            hits.append((f, n, i + 1))
    if not hits:
        return None
    if anchor["line"] is None:
        return hits[0]
    return min(hits, key=lambda h: abs(h[1] - anchor["line"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frozen", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows, missing, ids = [], [], set()
    for (iid, doc, anchors, cls, cls2, sev, defect, source, conf, primary) in ITEMS:
        assert iid not in ids and cls in CLASSES and (cls2 is None or cls2 in CLASSES) and sev in SEVERITIES, iid
        ids.add(iid)
        locs = []
        for an in anchors:
            r = resolve(a.frozen, doc, an)
            if r is None:
                missing.append((iid, an["file"], an["key"]))
                continue
            locs.append({"file": r[0], "line": r[1], "flat_line": r[2], "key": an["key"]})
        rows.append({"id": iid, "doc": doc, "omission": not anchors, "locations": locs, "class": cls, "class2": cls2,
                     "severity": sev, "defect": defect, "source": source, "audit_confidence": conf,
                     "visible": "pdf_only" if iid in PDF_ONLY else "source", "primary": primary and iid not in PDF_ONLY,
                     "coder": "A (Claude Opus 5.5, 2026-10-06)"})
    if missing:
        for m in missing:
            print("MISSING", *m)
        sys.exit(f"{len(missing)} anchors not found; fix the keys before writing")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    by = {}
    for r in rows:
        by.setdefault(r["doc"], 0)
        by[r["doc"]] += 1
    print(f"{len(rows)} items ({sum(r['primary'] for r in rows)} primary): {by}")


if __name__ == "__main__":
    main()
