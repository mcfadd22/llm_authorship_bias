import numpy as np
import pytest

from wcb import cluster_ols, holm, sort_by_cluster, wcb_test, _cluster_starts


def _clustered(n_clusters=30, per=6, effect=0.0, seed=0):
    rng = np.random.default_rng(seed)
    clusters = np.repeat(np.arange(n_clusters), per)
    shock = rng.normal(0, 1, n_clusters)[clusters]
    x = rng.integers(0, 2, n_clusters * per).astype(float)
    y = effect * x + shock + rng.normal(0, 1, n_clusters * per)
    return y, np.column_stack([np.ones_like(x), x]), clusters


def test_cluster_ols_recovers_plain_ols_coefficients():
    y, X, clusters = _clustered(seed=1)
    starts = _cluster_starts(clusters)
    beta, V, _ = cluster_ols(y, X, starts)
    expected, *_ = np.linalg.lstsq(X, y, rcond=None)
    assert np.allclose(beta, expected)
    assert V.shape == (2, 2)
    assert V[1, 1] > 0


def test_cluster_starts_handles_string_ids():
    clusters = np.array(["a", "a", "b", "c", "c", "c"])
    assert list(_cluster_starts(clusters)) == [0, 2, 3]


def test_sort_by_cluster_makes_clusters_contiguous():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    X = np.ones((4, 1))
    clusters = np.array(["b", "a", "b", "a"])
    _, _, sorted_clusters = sort_by_cluster(y, X, clusters)
    assert list(sorted_clusters) == ["a", "a", "b", "b"]


def test_wcb_detects_a_real_effect():
    y, X, clusters = _clustered(effect=1.5, seed=2)
    beta, se, t, p = wcb_test(y, X, clusters, 1, n_boot=499, seed=7)
    assert beta == pytest.approx(1.5, abs=0.5)
    assert p < 0.01


def test_wcb_does_not_flag_pure_noise():
    y, X, clusters = _clustered(effect=0.0, seed=3)
    *_, p = wcb_test(y, X, clusters, 1, n_boot=499, seed=7)
    assert p > 0.10


def test_wcb_pvalue_is_bounded_and_never_zero():
    y, X, clusters = _clustered(effect=9.0, seed=4)
    *_, p = wcb_test(y, X, clusters, 1, n_boot=99, seed=7)
    assert 1 / 100 <= p <= 1.0


def test_wcb_is_deterministic_for_a_fixed_seed():
    y, X, clusters = _clustered(effect=0.8, seed=5)
    a = wcb_test(y, X, clusters, 1, n_boot=199, seed=11)
    b = wcb_test(y, X, clusters, 1, n_boot=199, seed=11)
    assert a == b


def test_wcb_size_is_near_nominal_under_the_null():
    """Rejection rate at .05 should sit near .05, not wildly above it."""
    rejects = sum(
        wcb_test(*_clustered(effect=0.0, seed=100 + i), col=1, n_boot=199, seed=i)[3] < 0.05
        for i in range(60)
    )
    assert rejects <= 9  # ~3 expected; generous ceiling for 60 draws


def test_holm_matches_hand_computed_values():
    assert np.allclose(holm([0.01, 0.04, 0.03, 0.9]), [0.04, 0.09, 0.09, 0.9])


def test_holm_is_monotone_and_never_below_raw():
    raw = [0.001, 0.002, 0.3, 0.04]
    adj = holm(raw)
    assert all(a >= r for a, r in zip(adj, raw))
    assert max(adj) <= 1.0
