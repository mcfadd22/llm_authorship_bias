#!/usr/bin/env python3
"""Generate a bug-free counterpart for every item in data/items/.

Each clean item is a minimal-pair fix of its buggy twin: same function, bug removed, as little
else changed as possible. Output: data/items_clean/{item_id}.json with code_version="clean".
Uses the Anthropic SDK directly (ANTHROPIC_API_KEY); rerunning resumes.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from elicitation.clients import AnthropicJudgeClient, ElicitationError, JudgeClient
from elicitation.config import load_elicitation_config
from elicitation.writer import load_items
from vignette_gen.validate import ValidationError, validate_code
from vignette_gen.writer import append_failure, item_exists, write_item

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROMPT_VERSION = "2026-09-16-clean-v1"

CLEAN_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "The corrected function, as a code string."},
        "fix_rationale": {"type": "string", "description": "One or two sentences on what was changed."},
    },
    "required": ["code", "fix_rationale"],
    "additionalProperties": False,
}

TEMPLATE = """You are producing the bug-free version of a Python function for a research study on
how bugs in code are judged. Below is a function that contains a deliberately planted bug,
and a note describing the bug. Return the same function with the bug removed, changing
as little as possible: keep the function name, parameter names, structure, and style;
change only what is needed so the function correctly does what it is supposed to do.

Requirements for the returned code:
- Language: Python only.
- Exactly one self-contained function (no helper functions, no classes). A leading
  module-level import statement is allowed if needed; no other top-level statements.
- No comments and no docstrings in the code.
- Keep variable/function names neutral and typical for the task.
- Function body approximately 3-25 lines (signature through return).

STATED_AIM: "{stated_aim_text}"

BUGGY_CODE:
```python
{code}
```

BUG_NOTE: {rationale}

Return JSON with exactly these fields:
{{
  "code": "<corrected code string>",
  "fix_rationale": "<one or two sentences on what you changed>"
}}
"""


def build_clean_prompt(item: Dict, stated_aims: Dict) -> str:
    return TEMPLATE.format(
        stated_aim_text=stated_aims[item["aim_id"]]["text"],
        code=item["code"],
        rationale=item["rationale"],
    )


def generate_clean_one(client: JudgeClient, item: Dict, stated_aims: Dict, max_retries: int) -> Dict:
    prompt = build_clean_prompt(item, stated_aims)
    last_error = None
    for _ in range(max_retries):
        try:
            response = client.ask(prompt, CLEAN_SCHEMA)
            code = response.data["code"]
            if code.strip() == item["code"].strip():
                raise ElicitationError("returned code is identical to the buggy code")
            validate_code(code)
            break
        except (ElicitationError, ValidationError, KeyError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    else:
        raise RuntimeError(f"failed after {max_retries} attempts: {last_error}")

    record = {k: v for k, v in item.items() if k not in ("code", "rationale", "generation_model",
                                                          "timestamp", "prompt_version")}
    record.update(
        {
            "code_version": "clean",
            "source_item_id": item["item_id"],
            "code": code,
            "fix_rationale": response.data["fix_rationale"],
            "generation_model": response.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
        }
    )
    return record


def run(client: Optional[JudgeClient], items_dir: Path, out_dir: Path, stated_aims: Dict,
        limit: Optional[int], overwrite: bool, max_retries: int, dry_run: bool) -> Dict:
    items = sorted(load_items(items_dir), key=lambda i: i["item_id"])
    if limit is not None:
        items = items[:limit]

    if dry_run:
        for item in items:
            print(f"=== {item['item_id']} ===")
            print(build_clean_prompt(item, stated_aims))
        return {"generated": 0, "skipped": 0, "failed": 0}

    generated = skipped = failed = 0
    for item in items:
        if not overwrite and item_exists(out_dir, item["item_id"]):
            skipped += 1
            continue
        try:
            record = generate_clean_one(client, item, stated_aims, max_retries)
        except RuntimeError as exc:
            append_failure(out_dir / "failures.jsonl", {"item_id": item["item_id"], "error": str(exc)})
            failed += 1
            print(f"FAILED {item['item_id']}: {exc}")
            continue
        write_item(out_dir, item["item_id"], record)
        generated += 1
        print(f"generated {item['item_id']}")

    print(f"done: {generated} generated, {skipped} skipped, {failed} failed")
    return {"generated": generated, "skipped": skipped, "failed": failed}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--items-dir", type=Path, default=DATA_DIR / "items")
    parser.add_argument("--out-dir", type=Path, default=DATA_DIR / "items_clean")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    stated_aims = load_elicitation_config()["stated_aims"]
    client = None
    if not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY environment variable is required.")
        client = AnthropicJudgeClient(model=args.model)
    run(client, args.items_dir, args.out_dir, stated_aims, limit=args.limit,
        overwrite=args.overwrite, max_retries=args.max_retries, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
