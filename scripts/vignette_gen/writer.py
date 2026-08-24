import json
import os
from pathlib import Path


def _item_path(output_dir: Path, item_id: str) -> Path:
    path = output_dir / f"{item_id}.json"
    if path.parent != output_dir:
        raise ValueError(f"unsafe item_id: {item_id!r}")
    return path


def item_exists(output_dir: Path, item_id: str) -> bool:
    return _item_path(output_dir, item_id).exists()


def write_item(output_dir: Path, item_id: str, record: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = _item_path(output_dir, item_id)
    tmp_path = output_dir / f".{item_id}.json.tmp"
    tmp_path.write_text(json.dumps(record, indent=2))
    os.replace(tmp_path, final_path)


def append_failure(failures_path: Path, record: dict) -> None:
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    with failures_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
