import numpy as np
import pytest

from creative_machine.stats import bootstrap_diff_ci, mean_std


def test_ci_excludes_zero_for_separated_samples():
    rng = np.random.default_rng(1)
    a = rng.normal(10.0, 1.0, size=20)
    b = rng.normal(0.0, 1.0, size=20)
    lo, hi = bootstrap_diff_ci(a, b, rng=np.random.default_rng(0))
    assert lo > 8.0
    assert hi < 12.0


def test_ci_covers_zero_for_identical_distributions():
    rng = np.random.default_rng(2)
    a = rng.normal(5.0, 1.0, size=30)
    b = rng.normal(5.0, 1.0, size=30)
    lo, hi = bootstrap_diff_ci(a, b, rng=np.random.default_rng(0))
    assert lo < 0 < hi


def test_ci_deterministic_with_rng():
    a, b = [1.0, 2.0, 3.0], [0.5, 1.5]
    ci1 = bootstrap_diff_ci(a, b, rng=np.random.default_rng(7))
    ci2 = bootstrap_diff_ci(a, b, rng=np.random.default_rng(7))
    assert ci1 == ci2


def test_empty_sample_raises():
    with pytest.raises(ValueError):
        bootstrap_diff_ci([], [1.0])


def test_mean_std():
    m, s = mean_std([2.0, 4.0])
    assert m == 3.0
    assert s == pytest.approx(np.sqrt(2.0))
    assert mean_std([5.0]) == (5.0, 0.0)
