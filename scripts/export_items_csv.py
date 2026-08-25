#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

DEFAULT_ITEMS_DIR = Path(__file__).resolve().parent.parent / "data" / "items"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "items.csv"

FIELDS = [
    "item_id",
    "cell_id",
    "sample_idx",
    "aim_id",
    "bug_flavor",
    "severity_tier",
    "code",
    "rationale",
    "generation_model",
    "timestamp",
    "prompt_version",
]


def export_items_csv(items_dir: Path, output_path: Path) -> int:
    items = [json.loads(p.read_text()) for p in sorted(items_dir.glob("*.json"))]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow({field: item.get(field, "") for field in FIELDS})

    return len(items)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export data/items/*.json into a single items.csv for convenience."
    )
    parser.add_argument("--items-dir", type=Path, default=DEFAULT_ITEMS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    count = export_items_csv(args.items_dir, args.output)
    print(f"Wrote {count} rows to {args.output}")


if __name__ == "__main__":
    main()
