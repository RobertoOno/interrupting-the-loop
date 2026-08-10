"""Seed extraction for the selection loop: the surviving deviation becomes
the next generation's starting point.

Given a text and the word-positions of its novel n-gram windows (already
measured by novelty_report — no extra API calls), pick the sentence that
concentrates the most novelty per word. That sentence is the next prompt:
today's validated deviation seeds tomorrow's generation.
"""

from __future__ import annotations

import re


def looks_factual(sentence: str) -> bool:
    """Cheap guard against escape mode 3 (factual paraphrase) in seed picks.

    Real-world assertions carry telltales the surreal doesn't need: digits
    (years, statistics), percent signs, and proper names mid-sentence. The
    n-gram ruler scores paraphrased facts as "novel", so seeds must be
    screened before they poison a pipeline (learned from hybrid run 1:
    Ostman's 1924 Sasquatch account, Alzheimer stats, guild history).
    """
    if re.search(r"[0-9%]", sentence):
        return True
    # Leading "Name wrote/said/claimed ..." is the classic recitation shape.
    if re.match(
        r"^[A-Z][a-z]+ (wrote|said|claimed|reported|argued|explained|described|noted)\b",
        sentence,
    ):
        return True
    words = sentence.split()
    for prev, word in zip(words, words[1:]):
        stripped = word.strip("\"'()[]")
        if (
            re.match(r"^[A-Z][a-z]+", stripped)
            and stripped != "I"
            and not prev.rstrip("\"'")[-1:] in ".!?:"
        ):
            return True
    return False


def split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Split into sentences as (word_start, word_end, sentence) triples.

    Word indices refer to text.split() positions, matching novelty windows.
    """
    out = []
    word_i = 0
    for chunk in re.split(r"(?<=[.!?])\s+", text.strip()):
        words = chunk.split()
        if words:
            out.append((word_i, word_i + len(words), " ".join(words)))
            word_i += len(words)
    return out


def extract_novel_sentence(
    text: str,
    novel_starts: list[int],
    n: int,
    min_words: int = 6,
    max_words: int = 40,
) -> str | None:
    """The sentence with the highest density of novel n-windows fully inside it.

    Returns None when no sentence qualifies (too short/long or no novelty).
    """
    best, best_score = None, 0.0
    starts = set(novel_starts)
    for a, b, sentence in split_sentences(text):
        if not min_words <= b - a <= max_words:
            continue
        slots = b - a - n + 1
        if slots < 1:
            continue
        hits = sum(1 for s in range(a, b - n + 1) if s in starts)
        score = hits / slots
        if score > best_score:
            best, best_score = sentence, score
    return best
