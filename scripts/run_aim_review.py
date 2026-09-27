#!/usr/bin/env python3
"""Contract-blind item review by models outside the judge and generator pools.

Each reviewer sees exactly the judge-facing aim sentence and code block that
run_elicitation.py builds under the `none` label -- no contract, flavour,
rationale, twin, author label or item_id -- and is asked to name any incorrect
behaviour and say whether the aim alone establishes it (design.md 1c). It is
not told the intended bug; matching its account against the intended bug is a
human step (analysis/build_aim_comparison.py).

Every call is saved in full to data/aim_review/<reviewer-slug>.jsonl: the exact
messages sent, request settings, raw response, parsed answer, returned model
id, reasoning text if returned, usage, and timestamp. Resumable per item.

    python scripts/run_aim_review.py --dry-run --limit 1
    python scripts/run_aim_review.py --reviewer deepseek/deepseek-v4-flash \\
        --items-dir data/items_gpt5 data/items_gemini25pro
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from elicitation.prompt import aim_sentence  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"
INSTRUCTION_VERSION = "2026-09-27-v2"
MAX_OUTPUT_TOKENS = 16000

INSTRUCTION = """You are reviewing a short Python function. You are given only a one-sentence
description of what it is supposed to do, and the code. You have no other
specification.

Using only that description and the code, list every input or condition on
which the code does something incorrect. For each one, state the input, what
the code does, and what it should do instead.

Only count behaviour as incorrect if you can justify the expected behaviour
from the description, or from a convention so widely shared that a typical
reviewer would apply it without being told. Do not assume an input-domain or
output rule the description does not state: if the description does not say
whether an input is valid, or what should happen for it, do not invent an
answer. Style issues, missing comments, performance, and code that has no effect
on behaviour are not incorrect behaviour.

For each issue, classify its basis:
- "stated": the description itself establishes the expected behaviour.
- "convention": the expected behaviour rests on a common convention or an
  ambiguous boundary, not on the description itself.

It is correct and expected to answer that there are no issues when you cannot
justify one. Do not search for a problem to report.

Answer with a JSON object of this form, and nothing else:
{"issues": [{"input": "...", "code_does": "...", "should_do": "...",
             "basis": "stated" or "convention", "justification": "..."}]}
Use {"issues": []} if there are none."""

SCHEMA = {
    "name": "aim_review",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["issues"],
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["input", "code_does", "should_do", "basis", "justification"],
                    "properties": {
                        "input": {"type": "string"},
                        "code_does": {"type": "string"},
                        "should_do": {"type": "string"},
                        "basis": {"type": "string", "enum": ["stated", "convention"]},
                        "justification": {"type": "string"},
                    },
                },
            }
        },
    },
}


def judge_view(item, aims):
    """The aim sentence and code block exactly as the judge sees them under `none`."""
    return aim_sentence(aims[item["aim_id"]]["text"]) + "\n\n```python\n" + item["code"] + "\n```"


def build_messages(item, aims):
    return [{"role": "user", "content": judge_view(item, aims) + "\n\n" + INSTRUCTION}]


def slug(model):
    return re.sub(r"[^A-Za-z0-9.]+", "-", model).strip("-")


def load_items(dirs):
    items = []
    for d in dirs:
        items += [json.loads(p.read_text()) for p in sorted(Path(d).glob("*.json"))]
    return items


def done_ids(path):
    if not path.exists():
        return set()
    with path.open() as fh:
        return {json.loads(line)["item_id"] for line in fh if line.strip()}


def done_prompts(path):
    """(item_id, prompt) pairs already reviewed. A regenerated item keeps its item_id
    but not its code, so resuming on item_id alone would skip it."""
    if not path.exists():
        return set()
    with path.open() as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return {(r["item_id"], r["messages"][0]["content"]) for r in rows}


def parse(content):
    text = content.strip()
    m = re.match(r"^```(?:json)?\s*\n(.*)\n```$", text, re.DOTALL)
    data = json.loads(m.group(1) if m else text)
    if not isinstance(data.get("issues"), list):
        raise ValueError("no issues list")
    for issue in data["issues"]:
        if issue.get("basis") not in ("stated", "convention"):
            raise ValueError(f"bad basis: {issue.get('basis')!r}")
    return data


def call(session, api_key, reviewer, messages, settings, max_retries=5):
    body = {"model": reviewer, "messages": messages, "response_format":
            {"type": "json_schema", "json_schema": SCHEMA}, **settings}
    last = None
    for attempt in range(max_retries):
        try:
            r = session.post(API_URL, headers={"Authorization": f"Bearer {api_key}"},
                             json=body, timeout=600)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            resp = r.json()
            choice = resp["choices"][0]
            content = choice["message"].get("content") or ""
            if choice.get("finish_reason") == "length":
                raise RuntimeError("truncated at the output cap")
            return resp, content, parse(content)
        except Exception as exc:  # retry transport, HTTP and parse failures alike
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed after {max_retries} attempts: {last}")


def record(item, reviewer, messages, settings, resp, content, parsed):
    choice = resp["choices"][0]
    return {
        "item_id": item["item_id"],
        "generator_tag": item.get("generator_tag"),
        "reviewer": reviewer,
        "response_model": resp.get("model"),
        "generation_id": resp.get("id"),
        "instruction_version": INSTRUCTION_VERSION,
        "settings": settings,
        "messages": messages,
        "raw_response": content,
        "reasoning": choice["message"].get("reasoning"),
        "issues": parsed["issues"],
        "usage": resp.get("usage"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reviewer", default="deepseek/deepseek-v4-flash")
    ap.add_argument("--items-dir", nargs="+",
                    default=[ROOT / "data" / "items_gpt5", ROOT / "data" / "items_gemini25pro"])
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data" / "aim_review")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--dry-run", action="store_true", help="print the prompt, make no calls")
    args = ap.parse_args(argv)

    aims = {a["id"]: a for a in json.loads((ROOT / "config" / "stated_aims.json").read_text())["aims"]}
    items = load_items(args.items_dir)
    out = args.out_dir / f"{slug(args.reviewer)}.jsonl"
    done = done_prompts(out)
    todo = [it for it in items
            if (it["item_id"], build_messages(it, aims)[0]["content"]) not in done][: args.limit]
    settings = {"max_tokens": MAX_OUTPUT_TOKENS, "seed": args.seed}

    if args.dry_run:
        print(f"{len(items)} items, {len(todo)} to run -> {out}\n")
        if todo:
            print(build_messages(todo[0], aims)[0]["content"])
        return

    import requests
    api_key = os.environ["OPENROUTER_API_KEY"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    failures = 0
    with ThreadPoolExecutor(args.workers) as pool, out.open("a") as fh:
        futs = {}
        for it in todo:
            msgs = build_messages(it, aims)
            futs[pool.submit(call, session, api_key, args.reviewer, msgs, settings)] = (it, msgs)
        for n, fut in enumerate(as_completed(futs), 1):
            it, msgs = futs[fut]
            try:
                resp, content, parsed = fut.result()
            except Exception as exc:
                failures += 1
                print(f"[{n}/{len(todo)}] FAIL {it['item_id']}: {exc}", flush=True)
                continue
            fh.write(json.dumps(record(it, args.reviewer, msgs, settings, resp, content, parsed)) + "\n")
            fh.flush()
            print(f"[{n}/{len(todo)}] {it['item_id']}: {len(parsed['issues'])} issue(s)", flush=True)
    print(f"done: {len(todo) - failures} written, {failures} failed -> {out}")


if __name__ == "__main__":
    main()
