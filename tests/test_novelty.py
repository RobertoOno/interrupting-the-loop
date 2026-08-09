"""Novelty metrics against a fake in-memory corpus (no network)."""

import os

import pytest

from creative_machine.novelty import InfiniGramClient, novelty_report


class FakeClient:
    """Counts word-sequence containment over a tiny in-memory corpus."""

    def __init__(self, corpus: list[str]):
        self.docs = [d.split() for d in corpus]
        self.index = "fake"
        self.n_requests = 0

    def count(self, text: str) -> int:
        self.n_requests += 1
        q = text.split()
        hits = 0
        for doc in self.docs:
            hits += sum(1 for i in range(len(doc) - len(q) + 1) if doc[i : i + len(q)] == q)
        return hits


CORPUS = ["the sea was calm and grey that morning beyond the pier"]


def test_novelty_profile_and_longest_span():
    client = FakeClient(CORPUS)
    text = "the sea was calm and glowing with borrowed thunder"
    rep = novelty_report(client, text, ns=(4,), stride=1)
    # windows: 2 present ("the sea was calm", "sea was calm and"), 4 novel
    assert rep.novelty_by_n[4] == pytest.approx(4 / 6)
    assert rep.windows_by_n[4] == 6
    # greedy extension: "the sea was calm" + "and" holds, + "glowing" dies
    assert rep.longest_copied == "the sea was calm and"
    assert rep.longest_copied_len == 5
    assert rep.n_requests == client.n_requests


def test_fully_novel_text():
    client = FakeClient(CORPUS)
    rep = novelty_report(client, "quantum lighthouses dream in recursive salt spirals today", ns=(4, 6), stride=1)
    assert rep.novelty_by_n[4] == 1.0
    assert rep.novelty_by_n[6] == 1.0
    assert rep.longest_copied_len == 0
    assert rep.longest_copied == ""


def test_longest_span_falls_back_to_smaller_n():
    # No 8-word window is present, but a 4-word one is: extension must fall
    # back to the largest n with hits instead of reporting 0.
    client = FakeClient(CORPUS)
    text = "the sea was calm and glowing with borrowed thunder tonight it seems"
    rep = novelty_report(client, text, ns=(4, 8), stride=1)
    assert rep.novelty_by_n[8] == 1.0
    assert rep.longest_copied == "the sea was calm and"
    assert rep.longest_copied_len == 5


def test_text_shorter_than_window():
    client = FakeClient(CORPUS)
    rep = novelty_report(client, "too short", ns=(4,), stride=1)
    assert rep.novelty_by_n == {}
    assert rep.longest_copied_len == 0


@pytest.mark.skipif(not os.environ.get("INFINIGRAM_LIVE"), reason="set INFINIGRAM_LIVE=1 for live API test")
def test_live_dolma_smoke():
    client = InfiniGramClient("v4_dolma-v1_7_llama")
    assert client.count("the lighthouse keeper") > 0
    assert client.count("zxqv glorp fnord unheard") == 0
