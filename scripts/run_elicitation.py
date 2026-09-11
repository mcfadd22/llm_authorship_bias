#!/usr/bin/env python3
"""Run the judge elicitation over the generated item bank.

One call per (item, author_label, question, repeat) per judge. Rows are appended to
data/elicitation/{judge_id}.jsonl as they complete; rerunning resumes.
"""
import argparse
import os
from pathlib import Path

from elicitation.clients import make_client
from elicitation.config import load_elicitation_config
from elicitation.orchestrate import RunOptions, plan_rows, run_judge
from elicitation.writer import load_items

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# USD per 1M tokens (input, output). Sanity figures for --dry-run, not accounting.
PRICE_TABLE = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-5": (1.25, 10.00),
}
EST_INPUT_CHARS_PER_TOKEN = 4
EST_OUTPUT_TOKENS = 300


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", action="append", default=None,
                        help="judge id from config/judge_models.json; repeatable; default all")
    parser.add_argument("--limit", type=int, default=None,
                        help="max elicitations per judge this run (after resume filtering)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true",
                        help="print planned call counts and a cost estimate; make no calls")
    parser.add_argument("--overwrite", action="store_true", help="ignore existing rows")
    parser.add_argument("--items-dir", type=Path, default=DATA_DIR / "items")
    parser.add_argument("--out-dir", type=Path, default=DATA_DIR / "elicitation")
    return parser.parse_args(argv)


def select_judges(config, judge_ids):
    if not judge_ids:
        return config["judges"]
    by_id = {j["id"]: j for j in config["judges"]}
    unknown = [j for j in judge_ids if j not in by_id]
    if unknown:
        raise SystemExit(f"unknown judge id(s): {unknown}; known: {sorted(by_id)}")
    return [by_id[j] for j in judge_ids]


def estimate_cost(judge, pending, config, items_by_id):
    from elicitation.prompt import build_elicitation_prompt
    from elicitation.rivals import resolve_rivals

    in_price, out_price = PRICE_TABLE.get(judge["model"], (0.0, 0.0))
    total_in = 0
    for row in pending:
        label = next(l for l in config["author_labels"] if l["id"] == row["author_label"])
        question = next(q for q in config["questions"] if q["id"] == row["question_type"])
        rivals = resolve_rivals(judge, row["item_index"], config["rival_pool"])
        prompt = build_elicitation_prompt(
            config["stated_aims"][row["aim_id"]]["text"],
            items_by_id[row["item_id"]]["code"], label, judge, rivals, question,
        )
        total_in += len(prompt) // EST_INPUT_CHARS_PER_TOKEN
    total_out = EST_OUTPUT_TOKENS * len(pending)
    usd = total_in / 1e6 * in_price + total_out / 1e6 * out_price
    return total_in, total_out, usd


def main(argv=None):
    args = parse_args(argv)
    config = load_elicitation_config()
    judges = select_judges(config, args.judge)
    items = load_items(args.items_dir)
    if not items:
        raise SystemExit(f"no items found in {args.items_dir}")
    items_by_id = {i["item_id"]: i for i in items}

    options = RunOptions(
        limit=args.limit, repeats=args.repeats, dry_run=args.dry_run,
        overwrite=args.overwrite, max_retries=args.max_retries,
        concurrency=args.concurrency, items_dir=args.items_dir, out_dir=args.out_dir,
    )

    if args.dry_run:
        print(f"items: {len(items)}  labels: {len(config['author_labels'])}  "
              f"questions: {len(config['questions'])}  repeats: {args.repeats}")
        grand = 0.0
        for judge in judges:
            pending, skipped = plan_rows(judge, config, items, options)
            tin, tout, usd = estimate_cost(judge, pending, config, items_by_id)
            grand += usd
            print(f"{judge['id']:<18} planned {len(pending):>5}  already done {skipped:>5}  "
                  f"~{tin/1000:.0f}k in / ~{tout/1000:.0f}k out tokens  ~${usd:.2f}")
        print(f"{'total':<18} ~${grand:.2f}")
        return

    missing = sorted({KEY_ENV[j["provider"]] for j in judges if not os.environ.get(KEY_ENV[j["provider"]])})
    if missing:
        raise SystemExit(f"missing API key environment variable(s): {', '.join(missing)}")

    for judge in judges:
        client = make_client(judge)
        run_judge(client, judge, config, items, options)


if __name__ == "__main__":
    main()
