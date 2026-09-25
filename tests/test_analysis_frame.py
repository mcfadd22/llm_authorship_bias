import json

import numpy as np
import pandas as pd
import pytest

from frame import CONTRASTS, _generator_family, _named_author, design_matrix, load_frame

ROW = {"item_id": "a__x__trivial__000", "judge_id": "claude-opus-5", "judge_family": "claude",
       "judge_tuning": "opus-5", "author_label": "self", "question_type": "q_blame",
       "severity_tier": "trivial", "bug_flavor": "x", "repeat_idx": 0, "scale_response": 5,
       "rival_a": "gpt", "rival_b": "gemini", "reasoning_text": "t",
       "authorship_belief_raw": None, "authorship_belief_coded": None}


@pytest.mark.parametrize("model,expected", [
    ("anthropic/claude-sonnet-4.5", "claude"),
    ("claude-sonnet-4-5-20250929", "claude"),
    ("openai/gpt-5", "gpt"),
    ("google/gemini-2.5-pro", "gemini"),
    (None, None),
])
def test_generator_family_parses_provider_prefixed_ids(model, expected):
    assert _generator_family(model) == expected


@pytest.mark.parametrize("label,expected", [
    ("self", "claude"), ("other_model_A", "gpt"), ("other_model_B", "gemini"),
    ("none", None), ("generic_ai", None), ("human_developer", None),
])
def test_named_author_resolves_per_label(label, expected):
    assert _named_author({**ROW, "author_label": label}) == expected


def _write(tmp_path, rows, generation_model="anthropic/claude-sonnet-4.5"):
    el, items = tmp_path / "el", tmp_path / "items"
    el.mkdir(), items.mkdir()
    (el / "j.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    for iid in {r["item_id"] for r in rows}:
        (items / f"{iid}.json").write_text(json.dumps(
            {"item_id": iid, "generation_model": generation_model, "code": "def f(): pass"}))
    return el, items


def test_label_is_true_flags_self_for_a_matching_generator(tmp_path):
    el, items = _write(tmp_path, [ROW])
    df = load_frame(el, items)
    assert df.loc[0, "generator_family"] == "claude"
    assert df.loc[0, "label_is_true"] is True


def test_label_is_true_flags_a_truthful_rival_label(tmp_path):
    """GPT-5 judges saw a truthful 'written by Claude' label on some items."""
    row = {**ROW, "judge_id": "gpt-5", "judge_family": "gpt", "judge_tuning": "gpt-5",
           "author_label": "other_model_A", "rival_a": "claude", "rival_b": "gemini"}
    el, items = _write(tmp_path, [row])
    assert load_frame(el, items).loc[0, "label_is_true"] is True


def test_label_is_true_is_na_when_no_model_is_named(tmp_path):
    el, items = _write(tmp_path, [{**ROW, "author_label": "human_developer"}])
    assert pd.isna(load_frame(el, items).loc[0, "label_is_true"])


def test_label_is_false_for_a_non_matching_named_model(tmp_path):
    el, items = _write(tmp_path, [{**ROW, "author_label": "other_model_A"}])
    assert load_frame(el, items).loc[0, "label_is_true"] is False


def test_wave_one_rows_default_to_buggy_code_version(tmp_path):
    el, items = _write(tmp_path, [ROW])
    assert load_frame(el, items).loc[0, "code_version"] == "buggy"


def test_design_matrix_pools_the_two_rival_labels():
    labels = ["none", "self", "other_model_A", "other_model_B", "generic_ai", "human_developer"]
    sub = pd.DataFrame({"author_label": labels, "scale_response": [1, 2, 3, 4, 5, 6],
                        "item_id": ["i"] * 6})
    y, X, clusters = design_matrix(sub)
    assert X.shape == (6, 1 + len(CONTRASTS))
    pooled = X[:, 1 + CONTRASTS.index("other_model_pooled")]
    assert list(pooled) == [0, 0, 1, 1, 0, 0]
    assert list(X[:, 0]) == [1] * 6          # intercept
    assert np.allclose(y, [1, 2, 3, 4, 5, 6])
    assert list(clusters) == ["i"] * 6


def test_design_matrix_baseline_row_is_all_zero_contrasts():
    sub = pd.DataFrame({"author_label": ["none"], "scale_response": [4], "item_id": ["i"]})
    _, X, _ = design_matrix(sub)
    assert list(X[0]) == [1, 0, 0, 0, 0]
