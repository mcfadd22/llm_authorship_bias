# llm_authors

Study on how LLM judges ascribe folk-psychological states (intentionality,
blame, ability-vs-diligence) to buggy code based on claimed authorship
(self, other named model, generic AI, human developer, or no label),
crossed with bug type and severity.

See [`docs/design.md`](docs/design.md) for the full design doc: manipulated
factors, prompt template, question battery, response schema, and the
confirmatory/exploratory pre-registration split.

## Structure

- `docs/` — design docs, pre-registration notes
- `config/` — machine-readable vignette parameters (see `docs/config-schema.md`)
- `scripts/` — elicitation and data-generation scripts
- `analysis/` — analysis code (WCB clustering, Holm correction, NLP coding pass)
- `data/` — raw/intermediate data (gitignored except the item bank)

## Pipeline

1. **Generate items** — `scripts/generate_items.py` (OpenRouter, `OPENROUTER_API_KEY`). Output:
   `data/items/*.json`, tracked in git. Already run: 41 items, one per cell.
2. **Elicit judgments** — `scripts/run_elicitation.py` (Anthropic + OpenAI SDKs,
   `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Crosses every item with every `author_label` and
   every question in `config/questions.json`, one fresh call each, per judge in
   `config/judge_models.json`. Output: `data/elicitation/{judge_id}.jsonl` (gitignored),
   one row per call in the design.md §4 schema. Resumable; `--dry-run` prints counts and a
   cost estimate. See `docs/superpowers/specs/2026-09-11-elicitation-pipeline-design.md`.

   ```bash
   pip install -r requirements.txt
   python scripts/run_elicitation.py --dry-run
   python scripts/run_elicitation.py --judge claude-sonnet-5 --limit 20   # pilot
   python scripts/run_elicitation.py                                       # full run, all judges
   ```
3. **Analysis** — not yet written (`analysis/`).

## Results (complete, 2026-09-13)

Raw elicitation rows are tracked in `data/elicitation/{judge_id}.jsonl` to enable analysis
directly from the repo. One row per call; see the spec above for the field list. Full crossing:
41 items x 6 author labels x 4 questions = 984 rows per judge, one repeat.

| judge | served model | rows | notes |
|---|---|---|---|
| `claude-opus-5` | `claude-opus-5` | 984 | |
| `claude-sonnet-5` | `claude-sonnet-5` | 984 | 7 empty belief answers + 6 max_tokens truncations were re-asked (see git history) |
| `gpt-5` | `gpt-5-2025-08-07` | 984 | |

Provider defaults for thinking/reasoning were left in place and differ across judges; the
`thinking` field is null on every row because neither provider returns reasoning text by default.
