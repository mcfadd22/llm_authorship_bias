#!/usr/bin/env python3
"""Ask each judge every cell of every scenario. Resumable; one JSONL per judge in --out-dir.

    python -m multi_model_attribution.run_judges --out-dir multi_model_attribution/results/run1 --dry-run
    python -m multi_model_attribution.run_judges --out-dir ... --judge qwen3-32b --limit 20
"""
import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from multi_model_attribution import _paths  # noqa: F401
from multi_model_attribution.cells import enumerate_cells, load_existing_keys, row_key
from multi_model_attribution.render import CONFIG_DIR, PROMPT_VERSION, build_prompt, load_config
from elicitation.clients import ElicitationError, JudgeClient, make_client
from elicitation.orchestrate import RETRYABLE, _ask_with_deadline, _require_text
from elicitation.writer import append_row, load_items
from run_elicitation import EST_INPUT_CHARS_PER_TOKEN, EST_OUTPUT_TOKENS, KEY_ENV, PRICE_TABLE

HERE = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = HERE / "scenarios"
MANIFEST = "run.json"

# OpenRouter list prices 2026-10-13 (USD per 1M in, out); dry-run sanity figures only.
PRICES = {**PRICE_TABLE,
          "meta-llama/llama-3.1-8b-instruct": (0.02, 0.04), "qwen/qwen3-14b": (0.06, 0.22),
          "openai/gpt-oss-20b": (0.03, 0.09), "qwen/qwen3-32b": (0.08, 0.28),
          "meta-llama/llama-3.3-70b-instruct": (0.10, 0.32), "openai/gpt-oss-120b": (0.15, 0.60)}

STEPS = ["step_1", "step_2", "neither", "cannot_tell"]
ATTRIBUTION_SCHEMA = {"type": "object",
                      "properties": {"step": {"type": "string", "enum": STEPS},
                                     "explanation": {"type": "string"}},
                      "required": ["step", "explanation"], "additionalProperties": False}
# Explanation first, then bounded integers: with the integers first, Llama 3.3 70B fell into a
# whitespace loop under the JSON grammar on every provider; prose first cured most of it.
SPLIT_SCHEMA = {"type": "object",
                "properties": {"explanation": {"type": "string"},
                               "step_1_points": {"type": "integer", "minimum": 0, "maximum": 100},
                               "step_2_points": {"type": "integer", "minimum": 0, "maximum": 100}},
                "required": ["explanation", "step_1_points", "step_2_points"], "additionalProperties": False}
SCHEMAS = {"attribution": ATTRIBUTION_SCHEMA, "split": SPLIT_SCHEMA}
SCHEMA_VERSION = "attrib-v1/split-v2"  # recorded per row; split-v1 rows (integers first) were discarded
# Some models loop on whitespace under a JSON grammar at the position after a string field
# (Llama 3.3 70B on every provider tried). For those, a judge config may list question kinds
# in "prompted_json_for": the prompt then ends with a format line, no grammar is applied, and
# the reply is parsed as JSON. Rows record schema_version "...-prompted" so the caveat is visible.
PROMPTED_FORMAT_LINE = {
    "split": "Respond with a JSON object with exactly these keys: explanation (string), step_1_points (integer), step_2_points (integer).",
    "attribution": "Respond with a JSON object with exactly these keys: step (one of step_1, step_2, neither, cannot_tell), explanation (string).",
}


@dataclass
class RunOptions:
    repeats: int
    limit: Optional[int]
    dry_run: bool
    overwrite: bool
    max_retries: int
    concurrency: int
    out_dir: Path
    require_reviewed: bool = False


def validate(kind: str, data: Dict) -> None:
    if kind == "attribution":
        if data.get("step") not in STEPS:
            raise ElicitationError(f"step not one of {STEPS}: {data.get('step')!r}")
    else:
        a, b = data.get("step_1_points"), data.get("step_2_points")
        for v in (a, b):
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 100:
                raise ElicitationError(f"points out of range: {a!r}, {b!r}")
        if a + b != 100:
            raise ElicitationError(f"points do not sum to 100: {a} + {b}")
    _require_text(data.get("explanation"), "explanation")


def elicit_one(client: JudgeClient, row: Dict, scenario: Dict, judge: Dict, cfg: Dict, max_retries: int) -> Dict:
    prompt = build_prompt(scenario, row, judge, cfg)
    kind = row["question_kind"]
    prompted = kind in judge.get("prompted_json_for", [])
    schema = None if prompted else SCHEMAS[kind]
    if prompted:
        prompt = prompt + "\n\n" + PROMPTED_FORMAT_LINE[kind]
    schema_version = SCHEMA_VERSION + ("-prompted" if prompted else "")
    last = None
    for attempt in range(max_retries):
        if attempt:
            time.sleep(min(60, 5 * 2 ** (attempt - 1)))
        try:
            response = _ask_with_deadline(client, prompt, schema)
            validate(row["question_kind"], response.data)
            break
        except RETRYABLE as exc:
            last = f"{type(exc).__name__}: {exc}"
    else:
        raise RuntimeError(f"failed after {max_retries} attempts: {last}")
    d = response.data
    return {**row,
            "attribution": d.get("step"),
            "step_1_points": d.get("step_1_points"), "step_2_points": d.get("step_2_points"),
            "reasoning_text": d["explanation"], "prompt": prompt, "raw_response": response.raw_text,
            "response_model": response.model, "response_provider": response.provider,
            "usage": response.usage, "thinking": response.thinking,
            "timestamp": datetime.now(timezone.utc).isoformat(), "prompt_version": PROMPT_VERSION,
            "schema_version": schema_version}


def plan_rows(judge: Dict, scenarios: List[Dict], cfg: Dict, options: RunOptions):
    rows = enumerate_cells(scenarios, judge, cfg["questions"]["questions"], options.repeats)
    existing = set() if options.overwrite else load_existing_keys(options.out_dir / f"{judge['id']}.jsonl")
    pending = [r for r in rows if row_key(r) not in existing]
    skipped = len(rows) - len(pending)
    if options.limit is not None:
        pending = pending[: options.limit]
    return pending, skipped


def run_judge(client: Optional[JudgeClient], judge: Dict, scenarios: List[Dict], cfg: Dict, options: RunOptions) -> Dict:
    by_id = {s["scenario_id"]: s for s in scenarios}
    pending, skipped = plan_rows(judge, scenarios, cfg, options)
    out_path = options.out_dir / f"{judge['id']}.jsonl"
    failures_path = options.out_dir / "failures.jsonl"
    if options.dry_run:
        return {"planned": len(pending), "skipped": skipped}
    generated = failed = 0
    with ThreadPoolExecutor(max_workers=options.concurrency) as pool:
        futures = {pool.submit(elicit_one, client, r, by_id[r["scenario_id"]], judge, cfg, options.max_retries): r for r in pending}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                record = fut.result()
            except RuntimeError as exc:
                append_row(failures_path, {**row, "error": str(exc)}); failed += 1
                print(f"[{judge['id']}] FAILED {row['scenario_id']} {row['cause']}/{row['fidelity']} {row['question_type']}: {exc}", flush=True)
                continue
            append_row(out_path, record); generated += 1
            if generated % 100 == 0:
                print(f"[{judge['id']}] {generated}/{len(pending)} done", flush=True)
    print(f"[{judge['id']}] done: {generated} generated, {skipped} skipped, {failed} failed", flush=True)
    return {"generated": generated, "skipped": skipped, "failed": failed}


def _sha(paths: List[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


PROMPT_CONFIG_FILES = ("names.json", "questions.json", "notes.json")  # judges.json is routing, not prompt content


def check_manifest(out_dir: Path, scenario_files: List[Path], config_dir: Path, write: bool) -> None:
    here = {"scenarios_sha256": _sha(scenario_files), "prompt_version": PROMPT_VERSION,
            "config_sha256": _sha([Path(config_dir) / f for f in PROMPT_CONFIG_FILES])}
    path = out_dir / MANIFEST
    if path.exists():
        recorded = json.loads(path.read_text())
        for k, v in here.items():
            if recorded.get(k) != v:
                raise SystemExit(f"{out_dir} was started with {k}={recorded.get(k)!r}, not {v!r}; use a new --out-dir")
    elif write:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**here, "started": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n")


def load_scenarios(scenarios_dir: Path, require_reviewed: bool) -> List[Dict]:
    scenarios = [s for s in load_items(scenarios_dir) if "scenario_id" in s]
    if require_reviewed:
        bad = [s["scenario_id"] for s in scenarios if not s.get("review", {}).get("violating_caller_reviewed")]
        if bad:
            raise SystemExit(f"{len(bad)} scenario(s) not reviewed: {bad[:3]}...")
    return scenarios


def estimate_cost(judge, pending, scenarios, cfg):
    by_id = {s["scenario_id"]: s for s in scenarios}
    tin = sum(len(build_prompt(by_id[r["scenario_id"]], r, judge, cfg)) // EST_INPUT_CHARS_PER_TOKEN for r in pending)
    tout = EST_OUTPUT_TOKENS * len(pending)
    pi, po = PRICES.get(judge["model"], (0.0, 0.0))
    return tin, tout, tin / 1e6 * pi + tout / 1e6 * po


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--judge", action="append", default=None)
    p.add_argument("--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=48)
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--require-reviewed", action="store_true")
    p.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    cfg = load_config(args.config_dir)
    judges = cfg["judges"]["judges"]
    if args.judge:
        by = {j["id"]: j for j in judges}
        unknown = [j for j in args.judge if j not in by]
        if unknown:
            raise SystemExit(f"unknown judge id(s): {unknown}; known: {sorted(by)}")
        judges = [by[j] for j in args.judge]
    scenarios = load_scenarios(args.scenarios_dir, args.require_reviewed)
    if not scenarios:
        raise SystemExit(f"no scenarios in {args.scenarios_dir}")
    options = RunOptions(repeats=args.repeats, limit=args.limit, dry_run=args.dry_run, overwrite=args.overwrite,
                         max_retries=args.max_retries, concurrency=args.concurrency, out_dir=args.out_dir,
                         require_reviewed=args.require_reviewed)
    scenario_files = [p for p in Path(args.scenarios_dir).glob("*.json") if p.name != "selection_log.json"]
    check_manifest(args.out_dir, scenario_files, args.config_dir, write=not args.dry_run)
    if args.dry_run:
        print(f"scenarios: {len(scenarios)} (cosmetic variants: {sum(1 for s in scenarios if s.get('cosmetic') and 'skipped' not in s['cosmetic'])})  repeats: {args.repeats}")
        grand = 0.0
        for judge in judges:
            pending, skipped = plan_rows(judge, scenarios, cfg, options)
            tin, tout, usd = estimate_cost(judge, pending, scenarios, cfg); grand += usd
            print(f"{judge['id']:<16} planned {len(pending):>5}  done {skipped:>5}  ~{tin/1000:.0f}k in / ~{tout/1000:.0f}k out  ~${usd:.2f}")
        print(f"{'total':<16} ~${grand:.2f}")
        return
    missing = sorted({KEY_ENV[j["provider"]] for j in judges if not os.environ.get(KEY_ENV[j["provider"]])})
    if missing:
        raise SystemExit(f"missing API key environment variable(s): {', '.join(missing)}")
    for judge in judges:
        run_judge(make_client(judge), judge, scenarios, cfg, options)


if __name__ == "__main__":
    main()
