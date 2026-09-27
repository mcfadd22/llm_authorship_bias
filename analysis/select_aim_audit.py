#!/usr/bin/env python3
"""Draw the reduced set for a human contract-blind pass (design.md 1c, option B).

The model pass covers every item; the human pass then covers:
  - every item where the model found no issue,
  - every item where it found only convention-based issues,
  - every item the contract review flagged as a likely aim-visibility "no",
  - a random sample of the rest (model found a "stated" issue), drawn in
    proportion to flavour with a fixed seed, as a check on permissive calls.
Writes analysis/aim_audit_selection.csv (item_id, stratum). Do not show that
file to the blind reviewer: the stratum says what the model found.

    python analysis/select_aim_audit.py
    python analysis/build_aim_only_sheet.py --only analysis/aim_audit_selection.csv \\
        --out analysis/aim_only_review_selection.html
"""
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# contract-review notes that named these as likely aim-visibility "no"
FLAGGED = [
    "rename_files__copy_paste_residue__gemini25pro__000",
    "rename_files__copy_paste_residue__gemini25pro__001",
    "parse_csv_header__missing_edge_case__gemini25pro__000",
    "parse_csv_header__missing_edge_case__gemini25pro__001",
    "parse_csv_header__missing_edge_case__gpt5__000",
    "parse_csv_header__missing_edge_case__gpt5__001",
]


def model_support(issues):
    bases = {i["basis"] for i in issues}
    return "stated" if "stated" in bases else "convention" if bases else "none"


def select(reviews, flagged, n_sample, seed):
    strata = {}
    for iid, issues in reviews.items():
        s = model_support(issues)
        if s != "stated":
            strata[iid] = f"model_{s}"
    for iid in flagged:
        strata.setdefault(iid, "contract_review_flag")

    rest = sorted(iid for iid in reviews if iid not in strata)
    by_flavor = defaultdict(list)
    for iid in rest:
        by_flavor[iid.split("__")[1]].append(iid)
    rng = random.Random(seed)
    # largest-remainder allocation of n_sample across flavours, proportional to size
    quotas = {f: n_sample * len(v) / len(rest) for f, v in by_flavor.items()}
    alloc = {f: int(q) for f, q in quotas.items()}
    for f in sorted(quotas, key=lambda f: quotas[f] - alloc[f], reverse=True)[: n_sample - sum(alloc.values())]:
        alloc[f] += 1
    for f in sorted(by_flavor):
        for iid in rng.sample(by_flavor[f], min(alloc[f], len(by_flavor[f]))):
            strata[iid] = "sampled_stated"
    return strata


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review", type=Path,
                    default=ROOT / "data" / "aim_review" / "deepseek-deepseek-v4-flash.jsonl")
    ap.add_argument("--n-sample", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--out", type=Path, default=ROOT / "analysis" / "aim_audit_selection.csv")
    args = ap.parse_args(argv)

    with args.review.open() as fh:
        reviews = {r["item_id"]: r["issues"] for r in map(json.loads, fh)}
    strata = select(reviews, FLAGGED, args.n_sample, args.seed)
    with args.out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "stratum"])
        for iid in sorted(strata):
            w.writerow([iid, strata[iid]])
    counts = defaultdict(int)
    for s in strata.values():
        counts[s] += 1
    print(f"wrote {args.out}: {len(strata)} items {dict(counts)} (seed {args.seed})")


if __name__ == "__main__":
    main()
