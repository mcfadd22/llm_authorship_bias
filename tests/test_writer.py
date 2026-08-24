import json

import pytest

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


def test_write_item_uses_atomic_rename_not_direct_write(tmp_path, monkeypatch):
    # Simulate a crash: write_text succeeds but os.replace never runs.
    import os as os_module

    original_replace = os_module.replace
    calls = []

    def failing_replace(src, dst):
        calls.append((src, dst))
        raise OSError("simulated crash before rename completes")

    monkeypatch.setattr(os_module, "replace", failing_replace)

    try:
        write_item(tmp_path, "some_item", {"code": "x = 1"})
    except OSError:
        pass

    # The final item file must NOT exist - a "crash" before the atomic
    # rename must never leave a corrupt or partial file at the real path.
    assert not (tmp_path / "some_item.json").exists()


def test_write_item_rejects_path_traversal_in_item_id(tmp_path):
    with pytest.raises(ValueError, match="unsafe item_id"):
        write_item(tmp_path, "../../evil", {"code": "x = 1"})
