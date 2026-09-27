#!/usr/bin/env python3
"""Merge a review sheet's exported verdicts into the per-bank verdict CSVs.

A sheet built with several --items-dir banks exports one CSV covering all of
them. Each row goes to analysis/item_verdicts_<generator_tag>.csv, keyed by the
tag in its item_id (aim__flavour__<tag>__NNN). Rows with no item verdict are
skipped, so exporting a half-finished sheet never blanks an earlier verdict;
a row with a verdict replaces that item's existing row.

    python analysis/merge_verdicts.py ~/Downloads/item_verdicts.csv
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["item_id", "verdict", "twin_verdict", "note"]


def generator_tag(item_id):
    parts = item_id.split("__")
    if len(parts) != 4:
        raise ValueError(f"item_id has no generator tag: {item_id!r}")
    return parts[2]


def merge(export, out_dir):
    with Path(export).open() as fh:
        new = [r for r in csv.DictReader(fh) if r.get("verdict")]
    by_tag = defaultdict(list)
    for r in new:
        by_tag[generator_tag(r["item_id"])].append(r)

    written = {}
    for tag, rows in sorted(by_tag.items()):
        path = Path(out_dir) / f"item_verdicts_{tag}.csv"
        existing = {}
        if path.exists():
            with path.open() as fh:
                existing = {r["item_id"]: r for r in csv.DictReader(fh)}
        replaced = sum(r["item_id"] in existing for r in rows)
        existing.update({r["item_id"]: r for r in rows})
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            for iid in sorted(existing):
                w.writerow({k: existing[iid].get(k, "") for k in FIELDS})
        written[path] = (len(rows) - replaced, replaced, len(existing))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export", type=Path, help="CSV exported from a review sheet")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "analysis")
    args = ap.parse_args(argv)
    for path, (added, replaced, total) in merge(args.export, args.out_dir).items():
        print(f"{path}: {added} added, {replaced} replaced, {total} total")


if __name__ == "__main__":
    main()
