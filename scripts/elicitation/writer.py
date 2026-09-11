import json
import threading
from pathlib import Path
from typing import Dict, List, Set

from .cells import RowKey, row_key

_lock = threading.Lock()


def load_items(items_dir: Path) -> List[Dict]:
    return [json.loads(p.read_text()) for p in sorted(items_dir.glob("*.json"))]


def load_existing_keys(path: Path) -> Set[RowKey]:
    if not path.exists():
        return set()
    keys = set()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                keys.add(row_key(json.loads(line)))
    return keys


def append_row(path: Path, row: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row) + "\n"
    with _lock:
        with path.open("a") as f:
            f.write(line)
            f.flush()
