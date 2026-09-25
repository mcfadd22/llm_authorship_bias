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

1. **Generate items** — `scripts/generate_items.py` (OpenRouter, `OPENROUTER_API_KEY`). One
   call per (aim × flavour × sample); `severity_tier` is recorded, not crossed (design.md §1).
   `--items-dir` selects the bank and `--generator-tag` (defaulting to a slug of `--model`)
   goes into `item_id`, so banks from different generators never collide — the analysis
   clusters on `item_id`. The script refuses to write into a directory already holding another
   generator's items. Output tracked in git.

   ```bash
   python scripts/generate_items.py --dry-run --limit 1        # prints the prompt, no calls
   python scripts/generate_items.py --samples-per-cell 2 \
       --model openai/gpt-5 --items-dir data/items_gpt5
   ```

2. **Generate clean twins** — `scripts/generate_clean_items.py`. One bug-free, minimal-pair
   counterpart per item, same `item_id`, `code_version: "clean"`. Use `--provider`/`--model` to
   **match the generator that produced the buggy bank**, so an item and its twin share a true
   author: `q_authorship_belief` is asked on clean items too. `--provider openrouter` reaches
   any model on the one key.

   ```bash
   python scripts/generate_clean_items.py --provider openrouter --model openai/gpt-5 \
       --items-dir data/items_gpt5 --out-dir data/items_gpt5_clean
   ```

   See `docs/superpowers/specs/2026-09-16-clean-code-control-design.md` and
   `docs/superpowers/specs/2026-09-25-corpus-grounded-item-generation-design.md`.
3. **Elicit judgments** — `scripts/run_elicitation.py` (Anthropic + OpenAI SDKs,
   `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`). Crosses every item with every `author_label` and
   every applicable question in `config/questions.json` (5 on buggy items: bug-detection,
   three scaled, authorship belief; 2 on clean items: bug-detection and belief), one fresh
   call each, per judge in `config/judge_models.json`. Output: `data/elicitation/{judge_id}.jsonl` (gitignored),
   one row per call in the design.md §4 schema. Resumable; `--dry-run` prints counts and a
   cost estimate. See `docs/superpowers/specs/2026-09-11-elicitation-pipeline-design.md`.

   ```bash
   pip install -r requirements.txt
   python scripts/run_elicitation.py --dry-run
   python scripts/run_elicitation.py --judge claude-sonnet-5 --limit 20   # pilot
   python scripts/run_elicitation.py                                       # full run, all judges
   # confirmatory wave (after locking analysis): buggy + clean, 2 repeats
   python scripts/run_elicitation.py --out-dir data/elicitation_wave2/buggy --repeats 2
   python scripts/run_elicitation.py --out-dir data/elicitation_wave2/clean --items-dir data/items_clean --repeats 2
   ```
4. **Analysis** — `analysis/run_confirmatory.py` implements design.md §6.1: label contrasts
   against `none` with `other_model_A/B` pooled, wild cluster bootstrap clustered by `item_id`,
   Holm-corrected within each (hypothesis × judge_family × judge_tuning) family.

   ```bash
   python analysis/run_confirmatory.py                                  # as locked
   python analysis/run_confirmatory.py --verdicts analysis/item_verdicts-6.csv
   python analysis/run_confirmatory.py --item-fe                        # robustness variant
   python analysis/run_truth_diagnostic.py    # generator-model confound probe (exploratory)
   python analysis/build_item_review.py       # HTML sheet for vetting a bank
   ```

## Wave 1 results (complete, 2026-09-13)

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

Wave 1 predates the bug-detection question and the clean-code control; its rows have no
`code_version` field (read as `buggy`) and no `q_bug_present` rows. Wave 2 adds both.
