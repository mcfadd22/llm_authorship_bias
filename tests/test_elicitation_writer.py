import json

from elicitation.writer import append_row, load_existing_keys, load_items


def test_append_then_load_keys_roundtrip(tmp_path):
    out = tmp_path / "j.jsonl"
    row = {"judge_id": "j", "item_id": "i", "author_label": "none",
           "question_type": "q_blame", "repeat_idx": 0, "scale_response": 4}
    append_row(out, row)
    append_row(out, {**row, "repeat_idx": 1})
    assert load_existing_keys(out) == {
        ("j", "i", "buggy", "none", "q_blame", 0), ("j", "i", "buggy", "none", "q_blame", 1)
    }
    lines = out.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["scale_response"] == 4


def test_load_existing_keys_missing_file_is_empty(tmp_path):
    assert load_existing_keys(tmp_path / "nope.jsonl") == set()


def test_load_items_reads_all_json_and_skips_tmp(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"item_id": "a", "code": "x"}))
    (tmp_path / ".b.json.tmp").write_text("{}")
    items = load_items(tmp_path)
    assert [i["item_id"] for i in items] == ["a"]
