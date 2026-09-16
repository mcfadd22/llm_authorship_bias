# Design: Clean-code control for the confirmatory wave

**Status:** approved by user 2026-09-16.

Wave 1 (`docs/status-2026-09-13.md`) showed the Claude judges shifting the ability-vs-diligence
attribution by author label. Every wave-1 item has a planted bug, so that result cannot
distinguish "the label changes how a found bug is explained" from "the label changes the
judge's impression of the author regardless of the code." This adds a bug-free counterpart to
every item and a detection question, so the confirmatory wave can test both, and can test
whether judges report bugs that are not there under some labels.

## 1. New factor: `code_version`

`code_version ∈ {buggy, clean}`, a property of the item file, not crossed within an item file.

- Buggy items stay in `data/items/` unchanged. Files without a `code_version` field are buggy.
- Clean items live in `data/items_clean/`, one per buggy item, **same `item_id`**, with
  `code_version: "clean"` and `source_item_id` set. Same `cell_id`, `aim_id`, `bug_flavor`,
  `severity_tier` (kept so the clean row can be joined to its buggy twin; they describe the
  bug that was removed, not a property of the clean code).

Clean items are **minimal-pair fixes**: the generator receives the buggy code and its
`rationale` and returns the same function with the bug removed and as little else changed as
possible. Same constraints as generation (one function, no comments/docstrings, neutral
names, 3–25 body lines), enforced by the existing `vignette_gen.validate.validate_code`.

## 2. Clean-item generator

`scripts/generate_clean_items.py`, using `elicitation.clients.AnthropicJudgeClient` with a
structured-output schema `{"code": str, "fix_rationale": str}`. Default model
`claude-sonnet-4-5` to stay close to the wave-1 generator (`anthropic/claude-sonnet-4.5` via
OpenRouter); the model actually used is recorded per item. Resumable (skips existing files),
`--limit`, `--dry-run` (prints prompts), `--overwrite`, `--max-retries`. Failures append to
`data/items_clean/failures.jsonl`.

Output record: buggy item fields (with `code` replaced), plus `code_version: "clean"`,
`source_item_id`, `fix_rationale`, `generation_model`, `timestamp`,
`prompt_version: "2026-09-16-clean-v1"`. The buggy `rationale` field is dropped.

## 3. Detection question

`config/questions.json` gains, first in the battery:

```json
{"id": "q_bug_present", "kind": "detect", "applies_to": ["buggy", "clean"],
 "text": "Does this function have a bug? Answer yes or no, then explain."}
```

Schema `{"has_bug": boolean, "explanation": string}`. Row fields: `bug_detected` (bool) and
`reasoning_text` (the explanation); `scale_response` null.

Every question gets `applies_to`. The three scaled questions apply to `["buggy"]` only, since
they presuppose a bug. `q_authorship_belief` applies to both. A question with no
`applies_to` is treated as `["buggy"]` (backward compatible with wave-1 config).

Per judge, per repeat: buggy items 41 × 6 × 5 = 1,230 calls; clean items 41 × 6 × 2 = 492.

## 4. Elicitation changes

- `--items-dir` already selects the item set; nothing new. Rows carry `code_version` from the
  item (default `"buggy"`).
- Row key becomes `(judge_id, item_id, code_version, author_label, question_type,
  repeat_idx)`. `load_existing_keys` defaults a missing `code_version` to `"buggy"`, so wave-1
  files resume unchanged.
- `enumerate_elicitations` filters questions by `applies_to` against the item's
  `code_version`.
- `elicit_one` handles `kind == "detect"`: validates `has_bug` is a bool and `explanation` is
  non-degenerate text; writes `bug_detected`.
- Dry-run cost estimate accounts for the per-version question count automatically.
- Recommended wave-2 invocation (two runs per judge, distinct out-dirs):

  ```bash
  python scripts/run_elicitation.py --out-dir data/elicitation_wave2/buggy --repeats 2
  python scripts/run_elicitation.py --out-dir data/elicitation_wave2/clean --items-dir data/items_clean --repeats 2
  ```

## 5. Pre-specified analyses added (exploratory, own Holm family)

- **False-positive rate**: `bug_detected ~ author_label` on clean items, logistic, clustered
  by `item_id`, contrasts vs `none`. The headline question this control exists for.
- **Detection rate**: same model on buggy items. If detection varies by label, H1–H3
  contrasts should be re-run on the detected subset as a robustness check.
- **Belief on clean code**: `authorship_belief_coded` on clean items by label, to see whether
  the manipulation check behaves the same without a bug.

H1–H3 are unchanged and still run on buggy items only.

## 6. Testing

Fake clients as before. Cover: config `applies_to` default and `detect` kind accepted;
enumeration count for buggy vs clean; row key with `code_version` and legacy-row defaulting;
detect-row shape and validation; clean-generator prompt content, validation of returned code,
resume, and failure logging; loading `data/items_clean` records.

## Out of scope

- Running wave 2. It runs after the H1–H3 analysis is locked.
- Analysis code.
