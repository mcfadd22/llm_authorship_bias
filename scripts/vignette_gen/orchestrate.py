import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from .cells import enumerate_cells, expand_items
from .config import load_config as _default_load_config
from .prompt import build_prompt
from .validate import ValidationError, validate_code
from .writer import append_failure, item_exists, write_item

PROMPT_VERSION = "2026-08-24-v1"


@dataclass
class RunOptions:
    model: str
    samples_per_cell: int
    limit: Optional[int]
    dry_run: bool
    overwrite: bool
    max_retries: int
    items_dir: Path
    failures_path: Path


def _default_build_items(config: Dict, samples_per_cell: int, limit: Optional[int]):
    cells = enumerate_cells(config["stated_aims"])
    items = expand_items(cells, samples_per_cell)
    if limit is not None:
        items = items[:limit]
    return items


def generate_one(client, item: Dict, config: Dict, max_retries: int) -> Dict:
    last_error = None
    for _ in range(max_retries):
        prompt = build_prompt(item, config)
        try:
            raw = client.generate(prompt)
            parsed = json.loads(raw)
            code = parsed["code"]
            rationale = parsed["rationale"]
            validate_code(code)
            return {"code": code, "rationale": rationale}
        except (json.JSONDecodeError, KeyError, ValidationError) as exc:
            last_error = str(exc)
    raise RuntimeError(f"failed after {max_retries} attempts: {last_error}")


def run(
    client,
    options: RunOptions,
    load_config_fn: Callable[[], Dict] = _default_load_config,
    build_items_fn: Callable = _default_build_items,
) -> Dict:
    config = load_config_fn()
    items = build_items_fn(config, options.samples_per_cell, options.limit)

    if options.dry_run:
        for item in items:
            print(f"=== {item['item_id']} ===")
            print(build_prompt(item, config))
        return {"generated": 0, "skipped": 0, "failed": 0}

    generated = skipped = failed = 0
    for item in items:
        if not options.overwrite and item_exists(options.items_dir, item["item_id"]):
            skipped += 1
            continue
        try:
            result = generate_one(client, item, config, options.max_retries)
        except RuntimeError as exc:
            append_failure(options.failures_path, {**item, "error": str(exc)})
            failed += 1
            continue

        record = {
            **item,
            "code": result["code"],
            "rationale": result["rationale"],
            "generation_model": options.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
        }
        write_item(options.items_dir, item["item_id"], record)
        generated += 1
        print(f"generated {item['item_id']}")

    print(f"done: {generated} generated, {skipped} skipped, {failed} failed")
    return {"generated": generated, "skipped": skipped, "failed": failed}
