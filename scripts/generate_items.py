#!/usr/bin/env python3
import argparse
from pathlib import Path

from vignette_gen.client import GenerationClient
from vignette_gen.orchestrate import RunOptions, run

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate buggy-code vignettes via the Anthropic API."
    )
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--samples-per-cell", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    options = RunOptions(
        model=args.model,
        samples_per_cell=args.samples_per_cell,
        limit=args.limit,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        max_retries=args.max_retries,
        items_dir=DATA_DIR / "items",
        failures_path=DATA_DIR / "failures.jsonl",
    )
    client = None if args.dry_run else GenerationClient(model=args.model)
    run(client, options)


if __name__ == "__main__":
    main()
