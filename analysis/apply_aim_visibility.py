#!/usr/bin/env python3
"""Fold adjudicated aim-visibility flags into analysis/item_caveats.csv (design.md 1c).

Takes the CSV exported from analysis/aim_comparison.html (item_id, aim_visible,
reason). For every item it flags, the contract review's provisional
aim_visibility_likely_* rows are replaced by the adjudicated one:
aim_visibility_no or aim_visibility_borderline ("yes" leaves no row). Items the
adjudication leaves blank keep their provisional rows. Nothing is removed from
the bank; run_confirmatory.py --plan 6.5 excludes by caveat.

    python analysis/apply_aim_visibility.py ~/Downloads/aim_visibility.csv --source "full pass"
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAVEATS = ROOT / "analysis" / "item_caveats.csv"
FIELDS = ["item_id", "caveat", "detail"]


def apply(flags, caveats, source):
    flagged = {r["item_id"]: r for r in flags if r.get("aim_visible") in ("yes", "borderline", "no")}
    kept = [c for c in caveats
            if not (c["item_id"] in flagged and c["caveat"].startswith("aim_visibility_"))]
    for iid, r in sorted(flagged.items()):
        if r["aim_visible"] != "yes":
            kept.append({"item_id": iid, "caveat": f"aim_visibility_{r['aim_visible']}",
                         "detail": f"Adjudicated ({source}): {r.get('reason', '')}".strip()})
    return kept


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("flags", type=Path, help="aim_visibility.csv exported from aim_comparison.html")
    ap.add_argument("--caveats", type=Path, default=CAVEATS)
    ap.add_argument("--source", required=True,
                    help='which human pass informed the flags: "full pass", "subset", or "no human pass"')
    args = ap.parse_args(argv)
    with args.flags.open() as fh:
        flags = list(csv.DictReader(fh))
    with args.caveats.open() as fh:
        caveats = list(csv.DictReader(fh))
    out = apply(flags, caveats, args.source)
    with args.caveats.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    n = sum(1 for r in flags if r.get("aim_visible"))
    print(f"{n} items flagged; {args.caveats} now {len(out)} rows")


if __name__ == "__main__":
    main()
