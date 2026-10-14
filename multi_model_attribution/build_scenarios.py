#!/usr/bin/env python3
"""Build scenarios: select source items, generate both callers, validate, add cosmetic variants.

Writes scenarios/<source_item_id>.json, scenarios/selection_log.json and scenarios/review.md
(violating callers for a human pass). Resumable: existing scenario files are skipped.
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from multi_model_attribution import _paths  # noqa: F401
from multi_model_attribution.cosmetic import SkipCosmetic, rename_pair
from multi_model_attribution.generate_callers import generate_caller, build_caller_prompt
from multi_model_attribution.harness import HARNESS_VERSION, failure_kind, run
from multi_model_attribution.select_items import build_pool, load_caveats, load_verdicts, order_round_robin
from elicitation.clients import make_client
from elicitation.config import load_elicitation_config

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_OUT = HERE / "scenarios"
BANKS = [("items_gpt5", ROOT / "data/items_gpt5", ROOT / "data/items_gpt5_clean"),
         ("items_gemini25pro", ROOT / "data/items_gemini25pro", ROOT / "data/items_gemini25pro_clean")]
VERDICTS = [ROOT / "analysis/item_verdicts_gpt5.csv", ROOT / "analysis/item_verdicts_gemini25pro.csv"]
CAVEATS = ROOT / "analysis/item_caveats.csv"
TRUTH = {"callee": "step_1", "caller": "step_2", "none": "neither"}


def _runs_for(callee_buggy: str, callee_clean: str, correct: Dict, violating: Dict) -> Dict:
    """The three cause runs, computed fresh from the given code strings."""
    none_run = run(callee_clean, correct["code"], correct["entry_call"], correct["expected_repr"])
    callee_run = run(callee_buggy, correct["code"], correct["entry_call"], correct["expected_repr"])
    caller_run = run(callee_clean, violating["code"], violating["entry_call"], violating["expected_repr"])
    runs = {"none": {**none_run.to_dict(), "callee_version": "clean", "caller_kind": "correct"},
            "callee": {**callee_run.to_dict(), "callee_version": "buggy", "caller_kind": "correct"},
            "caller": {**caller_run.to_dict(), "callee_version": "clean", "caller_kind": "violating"}}
    kinds = {"callee": failure_kind(callee_run), "caller": failure_kind(caller_run)}
    return runs, kinds


def runs_match_truth(runs: Dict) -> bool:
    return (runs["none"]["outcome"] == "ok"
            and runs["callee"]["outcome"] in ("exception", "wrong_result")
            and runs["caller"]["outcome"] in ("exception", "wrong_result"))


def build_one(client, record: Dict, aim: Dict, max_retries: int, want_cosmetic: bool) -> Dict:
    correct = generate_caller(client, record, aim, "correct", max_retries)
    violating = generate_caller(client, record, aim, "violating", max_retries)
    runs, kinds = _runs_for(record["buggy_code"], record["clean_code"], correct, violating)
    if not runs_match_truth(runs):
        raise RuntimeError(f"assembled runs do not match the truth table: { {k: v['outcome'] for k, v in runs.items()} }")
    cosmetic = None
    if want_cosmetic:
        try:
            b2, c2, map_b = rename_pair(record["buggy_code"], correct["code"])
            k2, _, map_k = rename_pair(record["clean_code"], correct["code"])
            _, v2, _ = rename_pair(record["clean_code"], violating["code"])
            # one consistent map for the callee: rename the clean twin with the buggy twin's map
            from multi_model_attribution.cosmetic import apply_renames
            k2 = apply_renames(record["clean_code"], map_b)
            v2 = apply_renames(violating["code"], map_b)
            c2 = apply_renames(correct["code"], map_b)
            cruns, ckinds = _runs_for(b2, k2, {**correct, "code": c2}, {**violating, "code": v2})
            same = all(cruns[k]["outcome"] == runs[k]["outcome"] and cruns[k].get("exc_type") == runs[k].get("exc_type")
                       and cruns[k].get("result_repr") == runs[k].get("result_repr") for k in runs)
            if not same:
                raise SkipCosmetic("renamed variant changed behaviour")
            cosmetic = {"callee_buggy_code": b2, "callee_clean_code": k2, "caller_correct_code": c2,
                        "caller_violating_code": v2, "rename_map": map_b, "runs": cruns, "failure_kind": ckinds}
        except SkipCosmetic as exc:
            cosmetic = {"skipped": str(exc)}
    callee_fn = correct["callee_function_name"]
    strip = lambda d: {k: v for k, v in d.items() if k not in ("runs", "callee_function_name", "mode")}
    return {
        "scenario_id": record["source_item_id"],
        "source_item_id": record["source_item_id"], "bank": record["bank"], "aim_id": record["aim_id"],
        "bug_flavor": record["bug_flavor"], "caveats": record["caveats"],
        "aim_text": aim["text"], "contract": aim["contract"],
        "callee": {"function_name": callee_fn, "buggy_code": record["buggy_code"],
                   "clean_code": record["clean_code"], "bug_rationale": record["bug_rationale"]},
        "caller": {"correct": strip(correct), "violating": strip(violating)},
        "runs": runs, "failure_kind": kinds, "truth": dict(TRUTH), "cosmetic": cosmetic,
        "review": {"violating_caller_reviewed": False, "note": None},
        "build": {"harness_version": HARNESS_VERSION, "python": sys.version.split()[0],
                  "timestamp": datetime.now(timezone.utc).isoformat()},
    }


def write_review(out_dir: Path) -> None:
    lines = ["# Violating callers for human review\n",
             "For each: does the caller plausibly misuse the callee by the stated clause, and is the clean callee itself correct?\n"]
    for p in sorted(out_dir.glob("*.json")):
        if p.name in ("selection_log.json",): continue
        s = json.loads(p.read_text())
        v = s["caller"]["violating"]
        lines += [f"\n## {s['scenario_id']}\n", f"Contract: {s['contract']}\n", f"Stated violation: {v['violation']}\n",
                  f"Observed: {s['runs']['caller']['outcome']} {s['runs']['caller'].get('exc_type') or ''} {s['runs']['caller'].get('exc_message') or ''}\n",
                  "```python\n" + s["callee"]["clean_code"] + "\n\n" + v["code"] + "\n```\n",
                  f"Entry: `{v['entry_call']}` expected `{v['expected_repr']}`\n"]
    (out_dir / "review.md").write_text("".join(lines))


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--cosmetic-n", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--generator-model", default="anthropic/claude-sonnet-5")
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--limit", type=int, default=None, help="build at most this many this run")
    p.add_argument("--dry-run", action="store_true", help="print the first candidates' prompts; no calls")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    aims = load_elicitation_config()["stated_aims"]
    pool = build_pool(BANKS, load_verdicts(VERDICTS), load_caveats(CAVEATS))
    ordered = order_round_robin(pool)
    chosen = ordered[: args.n]
    cosmetic_ids = set(c["source_item_id"] for c in random.Random(args.seed).sample(chosen, min(args.cosmetic_n, len(chosen))))
    print(f"pool {len(pool)} eligible; selecting {len(chosen)}; cosmetic on {len(cosmetic_ids)}")
    if args.dry_run:
        for rec in chosen[: (args.limit or 2)]:
            print(f"=== {rec['source_item_id']} ({rec['bug_flavor']}) ===")
            print(build_caller_prompt(rec, aims[rec["aim_id"]], "correct"))
        return
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    client = make_client({"provider": "openrouter", "model": args.generator_model,
                          "openrouter": {"provider": {"require_parameters": True}}, "max_tokens": 8192})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / "selection_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"built": [], "failed": [], "skipped": []}
    built = 0
    for rec in chosen:
        path = args.out_dir / f"{rec['source_item_id']}.json"
        if path.exists() and not args.overwrite:
            log["skipped"].append(rec["source_item_id"]); continue
        if args.limit is not None and built >= args.limit:
            break
        try:
            scenario = build_one(client, rec, aims[rec["aim_id"]], args.max_retries, rec["source_item_id"] in cosmetic_ids)
        except RuntimeError as exc:
            print(f"FAILED {rec['source_item_id']}: {exc}", flush=True)
            log["failed"].append({"source_item_id": rec["source_item_id"], "error": str(exc)})
            continue
        path.write_text(json.dumps(scenario, indent=2) + "\n")
        log["built"].append(rec["source_item_id"]); built += 1
        print(f"built {rec['source_item_id']}  cause runs: {', '.join(f'{k}={v['outcome']}' for k, v in scenario['runs'].items())}"
              f"  cosmetic={'yes' if scenario['cosmetic'] and 'skipped' not in scenario['cosmetic'] else 'no'}", flush=True)
    log_path.write_text(json.dumps(log, indent=2) + "\n")
    write_review(args.out_dir)
    print(f"done: built {built}, failed {len(log['failed'])}, scenarios on disk {len(list(args.out_dir.glob('*__*.json')))}")


if __name__ == "__main__":
    main()
