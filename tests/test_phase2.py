"""Phase 2 units that need no network: pair sampling and judgment parsing."""

import numpy as np
import pytest

from creative_machine.blend import parse_judgment
from creative_machine.concepts import (
    load_concepts,
    make_word_embedder,
    pairwise_cosine_distances,
    sample_distant_pairs,
)


def test_load_concepts_dedupes_and_skips_comments(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text("tide\n# comment\nlichen\n\ntide\n")
    assert load_concepts(f) == ["tide", "lichen"]


def test_pairwise_distances_orthogonal_cluster():
    e = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    d = pairwise_cosine_distances(e)
    assert d[0, 1] == pytest.approx(0.0)
    assert d[0, 2] == pytest.approx(1.0)
    assert np.allclose(d, d.T)


def test_sample_distant_pairs_respects_band_and_seed():
    rng = np.random.default_rng(3)
    e = rng.normal(size=(40, 8))
    pairs = sample_distant_pairs(e, n_pairs=10, band=(0.75, 0.95), rng=np.random.default_rng(0))
    d = pairwise_cosine_distances(e)
    iu, ju = np.triu_indices(40, k=1)
    lo, hi = np.percentile(d[iu, ju], [75, 95])
    assert len({(i, j) for i, j, _ in pairs}) == 10
    for i, j, dist in pairs:
        assert i < j
        assert lo <= dist <= hi
    again = sample_distant_pairs(e, n_pairs=10, band=(0.75, 0.95), rng=np.random.default_rng(0))
    assert pairs == again


def test_sample_distant_pairs_band_too_small():
    e = np.eye(4)
    with pytest.raises(ValueError):
        sample_distant_pairs(e, n_pairs=100)


def test_word_embedder_averages_token_embeddings():
    table = np.array([[2.0, 0.0], [0.0, 4.0]])
    embed = make_word_embedder(lambda ids: table[np.asarray(ids)], lambda w: [0, 1])
    out = embed(["anything"])
    assert np.allclose(out, [[1.0, 2.0]])


def test_parse_judgment_tolerates_fences():
    raw = 'Here you go:\n```json\n{"coherence": 7, "surprise": 4.5, "value": 6, "known_equivalent": null, "verdict": "fine."}\n```'
    j = parse_judgment(raw)
    assert j["coherence"] == 7.0
    assert j["surprise"] == 4.5
    assert j["known_equivalent"] is None


def test_parse_judgment_rejects_junk():
    with pytest.raises(ValueError):
        parse_judgment("I refuse to answer in JSON.")
