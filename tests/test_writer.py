import json

from vignette_gen.writer import append_failure, item_exists, write_item


def test_item_exists_false_when_missing(tmp_path):
    assert item_exists(tmp_path, "some_item") is False


def test_write_item_then_item_exists_true(tmp_path):
    write_item(tmp_path, "some_item", {"code": "x = 1"})
    assert item_exists(tmp_path, "some_item") is True


def test_write_item_creates_parent_dir(tmp_path):
    output_dir = tmp_path / "nested" / "items"
    write_item(output_dir, "some_item", {"code": "x = 1"})
    assert (output_dir / "some_item.json").exists()


def test_write_item_content_round_trips(tmp_path):
    record = {"item_id": "some_item", "code": "x = 1", "sample_idx": 0}
    write_item(tmp_path, "some_item", record)
    loaded = json.loads((tmp_path / "some_item.json").read_text())
    assert loaded == record


def test_append_failure_writes_one_json_line_per_call(tmp_path):
    failures_path = tmp_path / "failures.jsonl"
    append_failure(failures_path, {"item_id": "a", "error": "boom"})
    append_failure(failures_path, {"item_id": "b", "error": "boom2"})

    lines = failures_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["item_id"] == "a"
    assert json.loads(lines[1])["item_id"] == "b"
