"""Cluster-robust OLS and the wild cluster bootstrap used by design.md 6.1.

With 41 item clusters, cluster-robust t-statistics are badly behaved in their
asymptotic form; the wild cluster bootstrap (Cameron/Gelbach/Miller) is the
standard fix at this G. We impose the null when resampling (the "restricted"
or WCR variant), which is the version that performs well in small-G settings.
"""
import numpy as np


def _cluster_starts(clusters):
    """Row indices where each cluster begins. Requires rows sorted by cluster."""
    clusters = np.asarray(clusters)
    change = np.flatnonzero(clusters[1:] != clusters[:-1]) + 1
    return np.concatenate([[0], change]).astype(int)


def sort_by_cluster(y, X, clusters):
    order = np.argsort(clusters, kind="stable")
    return y[order], X[order], clusters[order]


def cluster_ols(y, X, starts, XtX_inv=None):
    """OLS with CR1 cluster-robust covariance. Rows must be cluster-contiguous."""
    if XtX_inv is None:
        XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    u = y - X @ beta
    # Per-cluster score sums: G x K
    S = np.column_stack([np.add.reduceat(X[:, k] * u, starts) for k in range(X.shape[1])])
    n, k = X.shape
    g = len(starts)
    c = (g / (g - 1)) * ((n - 1) / (n - k))
    V = XtX_inv @ (S.T @ S) @ XtX_inv * c
    return beta, V, u


def wcb_test(y, X, clusters, col, n_boot=4999, seed=0):
    """Wild cluster bootstrap p-value for H0: beta[col] == 0.

    Returns (beta, cluster_robust_se, t_observed, p_value). Rademacher weights,
    null imposed via the restricted fit.
    """
    y, X, clusters = sort_by_cluster(np.asarray(y, float), np.asarray(X, float),
                                     np.asarray(clusters))
    starts = _cluster_starts(clusters)
    g = len(starts)

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta, V, _ = cluster_ols(y, X, starts, XtX_inv)
    se = np.sqrt(V[col, col])
    t_obs = beta[col] / se if se > 0 else 0.0

    # Restricted fit: drop the tested column, so the null holds by construction.
    keep = np.ones(X.shape[1], bool)
    keep[col] = False
    Xr = X[:, keep]
    beta_r, _, u_r = cluster_ols(y, Xr, starts)
    fitted_r = Xr @ beta_r

    # Expand one Rademacher draw per cluster back out to rows.
    sizes = np.diff(np.concatenate([starts, [len(y)]]))
    rng = np.random.default_rng(seed)
    extreme = 0
    for _ in range(n_boot):
        w = np.repeat(rng.integers(0, 2, g) * 2.0 - 1.0, sizes)
        y_star = fitted_r + u_r * w
        b, Vb, _ = cluster_ols(y_star, X, starts, XtX_inv)
        se_b = np.sqrt(Vb[col, col])
        if se_b > 0 and abs(b[col] / se_b) >= abs(t_obs) - 1e-12:
            extreme += 1
    p = (extreme + 1) / (n_boot + 1)
    return beta[col], se, t_obs, p


def holm(pvalues):
    """Holm-Bonferroni step-down adjusted p-values, order preserved."""
    p = np.asarray(pvalues, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(running, 1.0)
    return adj
