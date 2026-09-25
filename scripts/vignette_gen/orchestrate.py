import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

import openai

from .cells import enumerate_cells, expand_items
from .client import GenerationError
from .config import load_config as _default_load_config
from .prompt import build_prompt
from .validate import ValidationError, validate_code
from .writer import append_failure, check_bank_generator, item_exists, write_item

PROMPT_VERSION = "2026-09-25-v2"


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
    generator_tag: str = ""
    concurrency: int = 4


def _default_build_items(
    config: Dict, samples_per_cell: int, limit: Optional[int], generator_tag: str
):
    cells = enumerate_cells(config["stated_aims"])
    items = expand_items(cells, samples_per_cell, generator_tag)
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
        except (json.JSONDecodeError, KeyError, ValidationError, openai.OpenAIError, GenerationError) as exc:
            last_error = str(exc)
    raise RuntimeError(f"failed after {max_retries} attempts: {last_error}")


def run(
    client,
    options: RunOptions,
    load_config_fn: Callable[[], Dict] = _default_load_config,
    build_items_fn: Callable = _default_build_items,
) -> Dict:
    config = load_config_fn()
    items = build_items_fn(
        config, options.samples_per_cell, options.limit, options.generator_tag
    )

    if options.dry_run:
        for item in items:
            print(f"=== {item['item_id']} ===")
            print(build_prompt(item, config))
        return {"generated": 0, "skipped": 0, "failed": 0}

    check_bank_generator(options.items_dir, options.generator_tag)

    pending = [
        item for item in items
        if options.overwrite or not item_exists(options.items_dir, item["item_id"])
    ]
    skipped = len(items) - len(pending)

    generated = failed = 0

    def work(item):
        return generate_one(client, item, config, options.max_retries)

    # Retries dominate the wall clock: a rejected candidate costs another full
    # call, and a single security-flavoured item has taken six minutes that way.
    # Results are consumed on this thread, so the counters and writes stay serial.
    with ThreadPoolExecutor(max_workers=max(1, options.concurrency)) as pool:
        futures = {pool.submit(work, item): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except RuntimeError as exc:
                append_failure(options.failures_path, {**item, "error": str(exc)})
                failed += 1
                print(f"FAILED {item['item_id']}: {exc}")
                continue

            record = {
                **item,
                "code": result["code"],
                "rationale": result["rationale"],
                "generation_model": options.model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt_version": PROMPT_VERSION,
                # Corpus-backed generation will populate the source fields; items
                # written from a flavour definition record they have no source.
                "provenance": {
                    "source": "generated",
                    "source_id": None,
                    "source_label": None,
                    "source_license": None,
                    "mutation_operator": None,
                    "modifications": None,
                },
            }
            write_item(options.items_dir, item["item_id"], record)
            generated += 1
            print(f"generated {item['item_id']}  ({generated}/{len(pending)})")

    print(f"done: {generated} generated, {skipped} skipped, {failed} failed")
    return {"generated": generated, "skipped": skipped, "failed": failed}
