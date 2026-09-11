from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import anthropic
import openai

from .cells import enumerate_elicitations, row_key
from .clients import FREE_SCHEMA, SCALED_SCHEMA, ElicitationError, JudgeClient
from .prompt import PROMPT_VERSION, author_sentence, build_elicitation_prompt
from .rivals import resolve_rivals
from .writer import append_row, load_existing_keys

RETRYABLE = (ElicitationError, anthropic.APIError, openai.OpenAIError)


@dataclass
class RunOptions:
    limit: Optional[int]
    repeats: int
    dry_run: bool
    overwrite: bool
    max_retries: int
    concurrency: int
    items_dir: Path
    out_dir: Path


def _question(config: Dict, question_id: str) -> Dict:
    return next(q for q in config["questions"] if q["id"] == question_id)


def _label(config: Dict, label_id: str) -> Dict:
    return next(l for l in config["author_labels"] if l["id"] == label_id)


def _validate(question: Dict, data: Dict) -> None:
    if question["kind"] == "scaled":
        score = data.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not (1 <= score <= 7):
            raise ElicitationError(f"score out of range or missing: {score!r}")
        if not isinstance(data.get("explanation"), str):
            raise ElicitationError("explanation missing")
    else:
        if not isinstance(data.get("answer"), str):
            raise ElicitationError("answer missing")


def elicit_one(
    client: JudgeClient,
    row: Dict,
    judge: Dict,
    config: Dict,
    item: Dict,
    max_retries: int,
) -> Dict:
    label = _label(config, row["author_label"])
    question = _question(config, row["question_type"])
    rivals = resolve_rivals(judge, row["item_index"], config["rival_pool"])
    aim_text = config["stated_aims"][row["aim_id"]]["text"]
    prompt = build_elicitation_prompt(aim_text, item["code"], label, judge, rivals, question)
    schema = SCALED_SCHEMA if question["kind"] == "scaled" else FREE_SCHEMA

    last_error = None
    for _ in range(max_retries):
        try:
            response = client.ask(prompt, schema)
            _validate(question, response.data)
            break
        except RETRYABLE as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    else:
        raise RuntimeError(f"failed after {max_retries} attempts: {last_error}")

    scaled = question["kind"] == "scaled"
    record = {k: v for k, v in row.items() if k != "item_index"}
    record.update(
        {
            "scale_response": response.data["score"] if scaled else None,
            "reasoning_text": response.data["explanation"] if scaled else None,
            "authorship_belief_raw": None if scaled else response.data["answer"],
            "authorship_belief_coded": None,
            "rival_a": rivals[0]["id"],
            "rival_b": rivals[1]["id"],
            "author_sentence": author_sentence(label, judge, rivals),
            "prompt": prompt,
            "raw_response": response.raw_text,
            "response_model": response.model,
            "usage": response.usage,
            "thinking": response.thinking,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
        }
    )
    return record


def plan_rows(judge: Dict, config: Dict, items: List[Dict], options: RunOptions) -> List[Dict]:
    """Rows still to run for this judge after resume filtering and --limit."""
    rows = enumerate_elicitations(
        items, judge, config["author_labels"], config["questions"], options.repeats
    )
    out_path = options.out_dir / f"{judge['id']}.jsonl"
    existing = set() if options.overwrite else load_existing_keys(out_path)
    pending = [r for r in rows if row_key(r) not in existing]
    if options.limit is not None:
        pending = pending[: options.limit]
    return pending, len(rows) - len(pending)


def run_judge(
    client: Optional[JudgeClient],
    judge: Dict,
    config: Dict,
    items: List[Dict],
    options: RunOptions,
) -> Dict:
    items_by_id = {i["item_id"]: i for i in items}
    pending, skipped = plan_rows(judge, config, items, options)
    out_path = options.out_dir / f"{judge['id']}.jsonl"
    failures_path = options.out_dir / "failures.jsonl"

    if options.dry_run:
        return {"planned": len(pending), "skipped": skipped}

    generated = failed = 0

    def work(row):
        return elicit_one(client, row, judge, config, items_by_id[row["item_id"]], options.max_retries)

    with ThreadPoolExecutor(max_workers=options.concurrency) as pool:
        futures = {pool.submit(work, row): row for row in pending}
        for future in as_completed(futures):
            row = futures[future]
            try:
                record = future.result()
            except RuntimeError as exc:
                append_row(failures_path, {**row, "error": str(exc)})
                failed += 1
                print(f"[{judge['id']}] FAILED {row['item_id']} {row['author_label']} {row['question_type']}: {exc}")
                continue
            append_row(out_path, record)
            generated += 1
            if generated % 25 == 0:
                print(f"[{judge['id']}] {generated}/{len(pending)} done")

    print(f"[{judge['id']}] done: {generated} generated, {skipped} skipped, {failed} failed")
    return {"generated": generated, "skipped": skipped, "failed": failed}
