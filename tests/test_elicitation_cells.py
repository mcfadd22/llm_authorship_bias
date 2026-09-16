from elicitation.cells import enumerate_elicitations, row_key

ITEMS = [
    {"item_id": "b__x__trivial__000", "cell_id": "b__x__trivial", "aim_id": "b",
     "bug_flavor": "x", "severity_tier": "trivial", "code": "def b(): pass"},
    {"item_id": "a__x__trivial__000", "cell_id": "a__x__trivial", "aim_id": "a",
     "bug_flavor": "x", "severity_tier": "trivial", "code": "def a(): pass"},
]
JUDGE = {"id": "j", "family": "claude", "tuning": "t", "display_name": "Claude"}
LABELS = [{"id": "none"}, {"id": "self"}, {"id": "other_model_A"}]
QUESTIONS = [
    {"id": "q_blame", "kind": "scaled", "applies_to": ["buggy"]},
    {"id": "q_authorship_belief", "kind": "free", "applies_to": ["buggy", "clean"]},
]
CLEAN_ITEMS = [{**i, "code_version": "clean"} for i in ITEMS]


def test_count_is_items_times_labels_times_questions_times_repeats():
    rows = enumerate_elicitations(ITEMS, JUDGE, LABELS, QUESTIONS, repeats=2)
    assert len(rows) == 2 * 3 * 2 * 2


def test_items_are_sorted_by_item_id_and_indexed():
    rows = enumerate_elicitations(ITEMS, JUDGE, LABELS, QUESTIONS, repeats=1)
    assert rows[0]["item_id"] == "a__x__trivial__000"
    assert rows[0]["item_index"] == 0
    last_item_rows = [r for r in rows if r["item_id"] == "b__x__trivial__000"]
    assert all(r["item_index"] == 1 for r in last_item_rows)


def test_row_carries_item_judge_label_question_and_repeat():
    rows = enumerate_elicitations(ITEMS, JUDGE, LABELS, QUESTIONS, repeats=1)
    row = rows[0]
    assert row["judge_id"] == "j"
    assert row["judge_family"] == "claude"
    assert row["judge_tuning"] == "t"
    assert row["author_label"] == "none"
    assert row["question_type"] == "q_blame"
    assert row["repeat_idx"] == 0
    assert row["cell_id"] == "a__x__trivial"
    assert row["severity_tier"] == "trivial"
    assert row["bug_flavor"] == "x"


def test_row_keys_are_unique():
    rows = enumerate_elicitations(ITEMS, JUDGE, LABELS, QUESTIONS, repeats=3)
    keys = {row_key(r) for r in rows}
    assert len(keys) == len(rows)


def test_row_key_shape_includes_code_version():
    rows = enumerate_elicitations(ITEMS, JUDGE, LABELS, QUESTIONS, repeats=1)
    assert rows[0]["code_version"] == "buggy"
    assert row_key(rows[0]) == ("j", "a__x__trivial__000", "buggy", "none", "q_blame", 0)


def test_row_key_defaults_legacy_rows_to_buggy():
    legacy = {"judge_id": "j", "item_id": "i", "author_label": "none",
              "question_type": "q_blame", "repeat_idx": 0}
    assert row_key(legacy) == ("j", "i", "buggy", "none", "q_blame", 0)


def test_clean_items_only_get_applicable_questions():
    rows = enumerate_elicitations(CLEAN_ITEMS, JUDGE, LABELS, QUESTIONS, repeats=1)
    assert len(rows) == 2 * 3 * 1
    assert {r["question_type"] for r in rows} == {"q_authorship_belief"}
    assert all(r["code_version"] == "clean" for r in rows)


def test_question_without_applies_to_is_buggy_only():
    qs = [{"id": "q_old", "kind": "scaled"}]
    assert len(enumerate_elicitations(ITEMS, JUDGE, LABELS, qs, repeats=1)) == 6
    assert enumerate_elicitations(CLEAN_ITEMS, JUDGE, LABELS, qs, repeats=1) == []
