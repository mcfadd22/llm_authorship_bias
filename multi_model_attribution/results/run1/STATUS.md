# Multi-model attribution, run 1: results (2026-10-14)

Six OpenRouter judges, 27 reviewed scenarios (4 with a cosmetic variant), 2 repeats, 3,846 cells
per judge. 23,068 rows in total. Five judges are complete; Qwen3 32B is missing 8 split cells of
one scenario (`is_freezing__logic_error__gemini25pro__001`, cause = caller) where the model never
finished thinking inside the 240 s deadline, even with a 16k output budget. Spend at list prices
was about $4 for the judging plus about $2 for caller generation.

Analysis: `python -m multi_model_attribution.analyze --results-dir multi_model_attribution/results/run1`
(wild cluster bootstrap, B = 4999, clustered by source item, Holm within family × judge). Outputs
`tests.csv`, `descriptives.csv`, `raggedness.csv` in this folder.

## Headline

**The bias we pre-registered as "last-touch" does not exist in these judges. The opposite does,
and only in the small and the Llama models.** When step 1's function is wrong and the failure
surfaces in step 2's call, every judge correctly blames step 1 (96 to 98 percent; Llama 8B 87).
When step 2 misused a correct step 1, four judges still get it right about 90 percent of the
time, but Llama 3.3 70B drops to 79 percent and Llama 3.1 8B to 46 percent, and the wrong
answers go to step 1, the upstream component. Nothing in this design pushed blame downstream.

Pre-registered tests surviving Holm at .05 (6 of 60):

| judge | family | outcome | contrast | estimate | p (Holm) |
|---|---|---|---|---|---|
| Llama 3.1 8B | F2 last-touch | blamed wrong step | cause = caller | +0.41 | 0.0004 |
| Llama 3.1 8B | F2 last-touch | points to wrong step | cause = caller | +17.6 | 0.0004 |
| Llama 3.1 8B | F1 fidelity | correct | summary vs full | +0.09 | 0.037 |
| Qwen3 14B | F2 last-touch | points to wrong step | cause = caller | +14.1 | 0.0012 |
| gpt-oss 20B | F2 last-touch | points to wrong step | cause = caller | +8.7 | 0.0048 |
| Qwen3 14B | F4 status | step 2 points | self_to_other vs frontier_to_small | −3.5 | 0.032 |

The F2 sign convention: positive means blame lands on the wrong step more often (or with more
points) when the caller is at fault than when the callee is. All three significant F2 effects are
positive: upstream blame, not last-touch. The small member of every family shows it in the
points split (8B, 14B, 20B); the large members do not (32B, 70B, 120B all flat in points).

## Per family

**F1 fidelity.** More history does not help, and for Llama 8B it hurts: with both steps' code
and notes shown (full), Llama 8B blames step 1 for a caller-side misuse 77 percent of the time;
shown only the assembled module it gets 64 percent right. Every other judge is within a few
points across the three fidelities. The 70B shows a non-significant drop at final_only (−0.09,
p = 0.054).

**F2 last-touch.** Reversed, see above. The last-touch rate (P(step 2) when the callee is at
fault) is 1 to 4 percent for five judges and 13 percent for Llama 8B.

**F3 plaintext trust.** An at-fault step claiming "handles all edge cases; tested and verified"
moved nothing in any judge. Largest effect: Llama 8B −1.9 points to the at-fault step, p = 0.30.

**F4 status.** Model names on the steps moved nothing, with one marginal exception: Qwen3 14B
gives 3.5 fewer points to step 2 when step 1 carries its own family name, p = 0.032. Against the
pre-registered caveat (self is always step 1 in that level), that is one weak self-favouring
result out of 24 status tests; treat as a lead, not a finding.

## Controls and raggedness (descriptive)

| judge | params | false alarm on passing pipeline | retest flip | retest split gap | cosmetic flip (excess over retest) |
|---|---|---|---|---|---|
| Llama 3.1 8B | 8B | 0.93 | 0.26 | 31.3 | 0.36 (+0.08) |
| Qwen3 14B | 14B | 0.08 | 0.03 | 14.2 | 0.04 (−0.01) |
| gpt-oss 20B | 20B | 0.05 | 0.03 | 15.2 | 0.03 (−0.03) |
| Qwen3 32B | 32B | 0.07 | 0.03 | 3.3 | 0.01 (0.00) |
| Llama 3.3 70B | 70B | 0.56 | 0.05 | 5.9 | 0.10 (+0.07) |
| gpt-oss 120B | 120B | 0.04 | 0.02 | 14.8 | 0.03 (0.00) |

Two things stand out.

1. **The Llama models invent defects in working pipelines.** Shown a pipeline whose integration
   check passed, Llama 8B names a culprit 93 percent of the time and Llama 70B 56 percent. The
   explanations describe real bug classes that are absent from the code shown: on the
   `add_note` scenario both Llamas explain the mutable-default-argument trap in a function that
   uses `notes=None` correctly. The errors are scenario-locked, not random: Llama 8B false-alarms
   on 20 of 27 scenarios at 90 percent or above, the 70B on 12 of 27, gpt-oss 120B on 1. The
   false alarms land on step 1 (Llama 70B: 48 percent step 1, 8 percent step 2), the same
   upstream pull seen in F2.
2. **Size predicts stability within family, but not the same way in each family.** Retest
   flips fall from 26 percent (Llama 8B) to 5 percent (70B); Qwen is already stable at 14B on
   the categorical answer, and its split gap falls from 14 to 3 points at 32B. gpt-oss is stable
   on the categorical answer at both sizes but its split gap is 15 points at both, so its
   responsibility points carry little information about size at all. Qwen3 32B is the steadiest
   judge here on every metric, at a fifth of the price of the frontier APIs.

The hypothesis that motivated the folder, that smaller models attribute more raggedly, holds
within each family for the categorical answer. It is not the whole story: the 70B Llama is
stable but wrong in a specific way (hallucinated upstream defects), and the small gpt-oss is
stable and nearly as accurate as the large one.

## Deviations from the pre-registration, recorded in the rows

- **Split schema reordered** before the run (explanation first, bounded integers) after
  Llama 3.3 70B looped on whitespace under the original integer-first grammar. All rows carry
  `schema_version`; rows from the discarded ordering were dropped for every judge.
- **Llama 3.3 70B's split question ran without a JSON grammar** (`prompted_json_for: ["split"]`
  in `config/judges.json`; rows carry `schema_version = attrib-v1/split-v2-prompted`). On every
  provider tried the model looped on whitespace after the explanation string under constrained
  decoding. The prompt gained one trailing format line for those cells; the attribution question
  kept the grammar. Its 256 grammar-mode split rows were discarded so that all its split rows
  share one mode. Its 70-percent-plus failure rate under the grammar is itself a raggedness
  observation and is noted here rather than in the tables.
- **Qwen output budget raised** from 4,096 to 8,192 (then 16,384 for Qwen3 32B) for the resume
  passes only; about 100 cells per Qwen judge had exhausted the budget while thinking.
  `max_tokens` is an operational setting and not part of the prompt, but the retried cells had
  a longer thinking budget than the rest.
- **Routing changed mid-run** for the slow judges (`judges.json` is not covered by the manifest
  hash; serving provider is recorded per row).
- 8 Qwen3 32B split cells are missing (see top).

Exploratory analyses listed in the README (fidelity × cause, failure_kind, flavour, bank, names
in explanations) have not been run. The scenario-level concentration of Llama false alarms
above is the one exploratory cut made, because it changes how the control result reads.
