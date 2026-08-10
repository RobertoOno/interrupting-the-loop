from creative_machine.evolve import extract_novel_sentence, split_sentences


def test_split_sentences_tracks_word_positions():
    text = "The sea was calm. It dreamed in salt! Nothing moved."
    sents = split_sentences(text)
    assert sents == [
        (0, 4, "The sea was calm."),
        (4, 8, "It dreamed in salt!"),
        (8, 10, "Nothing moved."),
    ]


def test_extracts_sentence_with_densest_novelty():
    text = (
        "The keeper watched the waves roll in every night. "
        "Storms are sailors who forgot how to drown quietly. "
        "He wrote it all down in the old logbook."
    )
    # novel 4-gram windows concentrated in the middle sentence (words 9-18)
    novel_starts = [9, 10, 11, 12, 13, 14, 0]
    got = extract_novel_sentence(text, novel_starts, n=4, min_words=6)
    assert got == "Storms are sailors who forgot how to drown quietly."


def test_returns_none_when_no_sentence_qualifies():
    assert extract_novel_sentence("Too short. Also tiny.", [0], n=4) is None
    long_text = " ".join(["word"] * 50) + "."
    assert extract_novel_sentence(long_text, [], n=4, max_words=40) is None
