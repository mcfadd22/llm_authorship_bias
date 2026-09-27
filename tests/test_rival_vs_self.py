import numpy as np
import pandas as pd

from frame import H4, RIVAL_VS_SELF_COL, design_matrix, rival_vs_self_matrix
from run_confirmatory import run, run_h4

LABELS = ["none", "self", "other_model_A", "other_model_B", "generic_ai", "human_developer"]


def _frame(means, n_items=30, noise=0.5, seed=0):
    """Every item under every label, each H4 outcome, one judge cell."""
    rng = np.random.default_rng(seed)
    rows = []
    for q in H4.values():
        for i in range(n_items):
            shift = rng.normal(0, 0.5)
            for lab in LABELS:
                rows.append(dict(item_id=f"i{i:03d}", author_label=lab, question_type=q,
                                 code_version="buggy", judge_cell="claude/opus-5",
                                 scale_response=means[lab] + shift + rng.normal(0, noise)))
    return pd.DataFrame(rows)


def test_reparameterisation_spans_the_same_model():
    sub = pd.DataFrame({"author_label": LABELS, "scale_response": [1, 2, 3, 4, 5, 6],
                        "item_id": ["i"] * 6})
    _, X, _ = design_matrix(sub)
    _, Xr, _ = rival_vs_self_matrix(sub)
    assert np.linalg.matrix_rank(np.column_stack([X, Xr])) == np.linalg.matrix_rank(X) == Xr.shape[1]


def test_tested_coefficient_is_rival_minus_self():
    means = dict(none=4, self=5, other_model_A=3, other_model_B=3, generic_ai=4, human_developer=4)
    sub = _frame(means, noise=0.0)
    sub = sub[sub["question_type"] == "q_blame"]
    y, X, _ = rival_vs_self_matrix(sub)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    assert np.isclose(beta[RIVAL_VS_SELF_COL], 3 - 5)


def test_run_h4_finds_a_real_gap_and_reports_three_families():
    means = dict(none=4, self=4, other_model_A=5, other_model_B=5, generic_ai=4, human_developer=4)
    res = run_h4(_frame(means), n_boot=499, seed=1)
    assert sorted(res["hypothesis"]) == ["H4a", "H4b", "H4c"]
    assert (res["contrast"] == "other_model_pooled - self").all()
    assert (res["estimate"].between(0.5, 1.5)).all() and (res["p_raw"] < 0.01).all()
    # one contrast per family: nothing to correct within it
    assert np.allclose(res["p_holm"], res["p_raw"])


def test_run_h4_does_not_flag_equal_self_and_rival():
    means = dict(none=4, self=5, other_model_A=5, other_model_B=5, generic_ai=4, human_developer=4)
    res = run_h4(_frame(means, seed=2), n_boot=499, seed=3)
    assert (res["estimate"].abs() < 0.3).all() and (res["p_raw"] > 0.01).all()


def test_h1_h3_results_are_unchanged_by_h4():
    means = dict(none=4, self=5, other_model_A=3, other_model_B=3, generic_ai=4, human_developer=4)
    df = _frame(means, seed=4)
    before = run(df, n_boot=199, seed=5)
    run_h4(df, n_boot=199, seed=5)
    after = run(df, n_boot=199, seed=5)
    pd.testing.assert_frame_equal(before, after)
