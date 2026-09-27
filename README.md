# llm_authors

Study on how LLM judges ascribe folk-psychological states (intentionality,
blame, ability-vs-diligence) to buggy code based on claimed authorship
(self, other named model, generic AI, human developer, or no label),
crossed with bug type and severity.

The core question: do LLM judges judge identical buggy code more harshly when it is attributed
to a different model? Code is byte-identical across labels, so any difference comes from the
label. A final "who do you think wrote this?" question checks whether the label took; it is
analysed separately under no label (can the judge identify the real generator?) and under a
label (does its guess follow the label?). Named labels are family-level ("Claude", "GPT",
"Gemini", "Llama").

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
3. **Review items** — every item and twin is checked against its contract and flavour before
   elicitation, blind to generator (design.md §1c). Failures are dropped or regenerated and
   re-reviewed; the accepted bank is frozen before collection.

   ```bash
   python analysis/build_item_review.py --blind --only-unreviewed \
       --items-dir data/items_gpt5 data/items_gemini25pro \
       --verdicts analysis/item_verdicts_gpt5.csv --out analysis/item_review_pending.html
   python analysis/merge_verdicts.py ~/Downloads/item_verdicts.csv   # -> item_verdicts_<tag>.csv
   ```

   A second, contract-blind check asks whether each bug is a bug from the judge's side (aim and
   code only; design.md §1c). A reviewer who has not seen the contracts fills in
   `analysis/aim_only_review.html`; a model does the same pass; both team members adjudicate.

   ```bash
   python analysis/build_aim_only_sheet.py                   # -> analysis/aim_only_review.html
   python scripts/run_aim_review.py                          # deepseek/deepseek-v4-flash -> data/aim_review/
   python analysis/build_aim_comparison.py --human aim_only_review.csv   # -> aim_comparison.html
   ```

4. **Elicit judgments** — `scripts/run_elicitation.py` (Anthropic + OpenAI SDKs,
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
   ```

   **Wave 2** runs two banks, each buggy and clean, two repeats, after both banks pass review.
   It uses prompt version `2026-09-27-v2`, which names the GPT family "GPT" rather than wave 1's
   "GPT-5"; every row records the exact `author_sentence` and `prompt`. Four legs, each
   resumable and each writing its own directory. `--items-dir` is required: the
   default is the wave-1 bank.

   ```bash
   B=data/elicitation_wave2
   python scripts/run_elicitation.py --repeats 2 --items-dir data/items_gpt5 --out-dir $B/gpt5_buggy
   python scripts/run_elicitation.py --repeats 2 --items-dir data/items_gpt5_clean --out-dir $B/gpt5_clean
   python scripts/run_elicitation.py --repeats 2 --items-dir data/items_gemini25pro --out-dir $B/gemini_buggy
   python scripts/run_elicitation.py --repeats 2 --items-dir data/items_gemini25pro_clean --out-dir $B/gemini_clean
   ```

   Estimated cost at two repeats, from wave-1 token actuals: $205 + $82 per bank,
   **~$575 total** for both banks at 62 items. Run `--dry-run` on each leg first to confirm against current
   prices. Needs `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.
5. **Analysis** — `analysis/run_confirmatory.py` implements design.md §6.1 (default) and, with `--plan 6.5`, the wave-2 plan, which adds H4. §6.1 is label contrasts
   against `none` with `other_model_A/B` pooled, wild cluster bootstrap clustered by `item_id`,
   Holm-corrected within each (hypothesis × judge_family × judge_tuning) family.

   ```bash
   python analysis/run_confirmatory.py                                  # as locked
   python analysis/run_confirmatory.py --verdicts analysis/item_verdicts-6.csv
   python analysis/run_confirmatory.py --item-fe                        # robustness variant
   python analysis/run_confirmatory.py --plan 6.5 --elicitation-dir <wave-2 dir>  # + H4, rival vs self
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

**Interpretation.** Wave 1 is the preregistered initial test, and it exposed a materials
problem: review after collection passed 13 of 41 items, all code was Claude-generated (so
`self` was the true label for both Claude judges), and the authorship answers are still
uncoded. Under the locked analysis, 10 of 36 contrasts survive Holm. None is a named-rival
label increasing blame relative to no label, which is not evidence that no rival effect
exists, nor a test of self against rival. The 28-item rerun is a post hoc sensitivity check.
See design.md §6.4 and `docs/status-2026-09-25.md`.

Wave 1 predates the bug-detection question and the clean-code control; its rows have no
`code_version` field (read as `buggy`) and no `q_bug_present` rows. Wave 2 adds both.
