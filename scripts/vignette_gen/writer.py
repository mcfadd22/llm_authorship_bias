import json
from pathlib import Path


def _item_path(output_dir: Path, item_id: str) -> Path:
    return output_dir / f"{item_id}.json"


def item_exists(output_dir: Path, item_id: str) -> bool:
    return _item_path(output_dir, item_id).exists()


def write_item(output_dir: Path, item_id: str, record: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _item_path(output_dir, item_id).write_text(json.dumps(record, indent=2))


def append_failure(failures_path: Path, record: dict) -> None:
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    with failures_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
