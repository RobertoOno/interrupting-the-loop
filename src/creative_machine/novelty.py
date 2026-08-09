"""Objective novelty via infini-gram: is a generated sequence in the corpus?

For OLMo-2 models the training data is public and indexed, so novelty stops
being vibes and becomes a lookup: n-grams with count 0 in the index were
never seen in training. This module measures (a) the fraction of novel
n-grams at several sizes and (b) the longest span of the text that IS in the
corpus (the longest copied stretch).

Windows are over whitespace words — transparent, tokenizer-independent
(the API tokenizes queries with its own Llama tokenizer server-side).

Zero new dependencies: urllib only. Be polite to the public API (throttle).
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.infini-gram.io/"

# Training-corpus indexes (full family corpus: superset of what the base saw,
# hence conservative for "was this ever seen in training?").
INDEX_OLMO2_13B = "v4_olmo-2-1124-13b-instruct_llama"
INDEX_OLMO2_32B = "v4_olmo-2-0325-32b-instruct_llama"
INDEX_DOLMA = "v4_dolma-v1_7_llama"


class InfiniGramClient:
    """Minimal count-query client with throttle and retry."""

    def __init__(
        self,
        index: str,
        base_url: str = DEFAULT_BASE_URL,
        throttle_s: float = 0.6,
        max_retries: int = 6,
    ) -> None:
        self.index = index
        self.base_url = base_url
        self.throttle_s = throttle_s
        self.max_retries = max_retries
        self._last_call = 0.0
        self.n_requests = 0

    def count(self, text: str) -> int:
        """Corpus count of the exact token sequence for ``text``."""
        payload = {"index": self.index, "query_type": "count", "query": text}
        body = json.dumps(payload).encode()
        for attempt in range(self.max_retries):
            wait = self.throttle_s - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            req = urllib.request.Request(
                self.base_url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "creative-machine-research/0.1",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    out = json.loads(resp.read())
                self.n_requests += 1
            except urllib.error.HTTPError as e:
                if attempt == self.max_retries - 1:
                    raise
                if e.code in (403, 429):  # rate limited: back off long, then resume
                    time.sleep(15.0 * (attempt + 1))
                else:
                    time.sleep(2.0**attempt)
                continue
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2.0**attempt)
                continue
            if "error" in out:
                raise RuntimeError(f"infini-gram error: {out['error']}")
            return int(out["count"])
        raise RuntimeError("unreachable")


@dataclass
class NoveltyReport:
    """Novelty profile of one text against one index."""

    index: str
    n_words: int
    novelty_by_n: dict[int, float] = field(default_factory=dict)  # n -> novel fraction
    windows_by_n: dict[int, int] = field(default_factory=dict)  # n -> windows checked
    longest_copied: str = ""
    longest_copied_len: int = 0  # in words
    n_requests: int = 0

    def summary(self) -> dict:
        return {
            "index": self.index,
            "n_words": self.n_words,
            "novelty_by_n": {str(k): round(v, 3) for k, v in self.novelty_by_n.items()},
            "longest_copied_len": self.longest_copied_len,
            "longest_copied": self.longest_copied,
            "n_requests": self.n_requests,
        }


def _windows(words: list[str], n: int, stride: int) -> list[tuple[int, str]]:
    return [(i, " ".join(words[i : i + n])) for i in range(0, len(words) - n + 1, stride)]


def novelty_report(
    client: InfiniGramClient,
    text: str,
    ns: tuple[int, ...] = (4, 6, 8),
    stride: int = 2,
    extend_from_n: int | None = None,
) -> NoveltyReport:
    """Profile ``text`` against the client's index.

    For each n in ``ns``, slide an n-word window (with ``stride``) and count
    the fraction of windows absent from the corpus. Then take the largest
    ``ns`` (or ``extend_from_n``) windows that ARE present and greedily extend
    each rightward, one word at a time, to find the longest copied span
    (counts are monotone non-increasing under extension, so dead ends stop
    immediately).
    """
    words = text.split()
    report = NoveltyReport(index=client.index, n_words=len(words))
    start_requests = client.n_requests

    present_by_n: dict[int, list[int]] = {}  # n -> starts of found windows
    for n in sorted(ns):
        wins = _windows(words, n, stride)
        if not wins:
            continue
        novel = 0
        for start, q in wins:
            if client.count(q) == 0:
                novel += 1
            else:
                present_by_n.setdefault(n, []).append(start)
        report.novelty_by_n[n] = novel / len(wins)
        report.windows_by_n[n] = len(wins)

    # Extend from the largest n that has any window present (falling back to
    # smaller n keeps the metric honest when all large windows are novel).
    base_n = extend_from_n if extend_from_n in present_by_n else max(present_by_n, default=None)
    present = [(start, base_n) for start in present_by_n.get(base_n, [])]

    best_start, best_len = -1, 0
    for start, length in present:
        while start + length < len(words):
            if client.count(" ".join(words[start : start + length + 1])) == 0:
                break
            length += 1
        if length > best_len:
            best_start, best_len = start, length
    if best_len:
        report.longest_copied = " ".join(words[best_start : best_start + best_len])
        report.longest_copied_len = best_len

    report.n_requests = client.n_requests - start_requests
    return report
