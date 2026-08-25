import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from export_items_csv import export_items_csv  # noqa: E402


def _write_item(items_dir, item_id, **overrides):
    record = {
        "item_id": item_id,
        "cell_id": f"cell_{item_id}",
        "sample_idx": 0,
        "aim_id": f"aim_{item_id}",
        "bug_flavor": "logic_error",
        "severity_tier": "trivial",
        "code": "def f(x):\n    return x",
        "rationale": "test rationale",
        "generation_model": "test-model",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "prompt_version": "v1",
    }
    record.update(overrides)
    (items_dir / f"{item_id}.json").write_text(json.dumps(record))
    return record


def test_export_items_csv_writes_one_row_per_item(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    _write_item(items_dir, "a", code="def f(x):\n    return x")
    _write_item(items_dir, "b", code="def g(y):\n    return y", severity_tier="significant")

    output_path = tmp_path / "items.csv"
    count = export_items_csv(items_dir, output_path)

    assert count == 2
    with output_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["item_id"] == "a"
    assert rows[0]["code"] == "def f(x):\n    return x"
    assert rows[1]["item_id"] == "b"
    assert rows[1]["severity_tier"] == "significant"


def test_export_items_csv_preserves_multiline_code_and_commas(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    tricky_code = "def f(x, y):\n    total = x + y\n    return total"
    tricky_rationale = "Uses a comma, a \"quote\", and multiple\nlines in the explanation."
    _write_item(items_dir, "a", code=tricky_code, rationale=tricky_rationale)

    output_path = tmp_path / "items.csv"
    export_items_csv(items_dir, output_path)

    with output_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["code"] == tricky_code
    assert rows[0]["rationale"] == tricky_rationale


def test_export_items_csv_handles_empty_directory(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    output_path = tmp_path / "items.csv"

    count = export_items_csv(items_dir, output_path)

    assert count == 0
    with output_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == []


def test_export_items_csv_creates_output_parent_dir(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    _write_item(items_dir, "a")

    output_path = tmp_path / "nested" / "items.csv"
    count = export_items_csv(items_dir, output_path)

    assert count == 1
    assert output_path.exists()
