# Multi-model attribution, run 1: results (2026-10-14; Claude Sonnet 5 added 2026-10-15)

Six OpenRouter judges, 27 reviewed scenarios (4 with a cosmetic variant), 2 repeats, 3,846 cells
per judge. 23,068 rows in total. Five judges are complete; Qwen3 32B is missing 8 split cells of
one scenario (`is_freezing__logic_error__gemini25pro__001`, cause = caller) where the model never
finished thinking inside the 240 s deadline, even with a 16k output budget. Spend at list prices
was about $4 for the judging plus about $2 for caller generation.

On 2026-10-15 Claude Sonnet 5 was added as a seventh judge on the same 3,846 cells (complete,
$25.60). The six original judges were not re-run, and their tests, descriptives and raggedness
numbers are byte-identical after the re-analysis. 26,914 rows in total. See the update section
directly below; the sections after it are the original six-judge write-up.

Analysis: `python -m multi_model_attribution.analyze --results-dir multi_model_attribution/results/run1`
(wild cluster bootstrap, B = 4999, clustered by source item, Holm within family × judge). Outputs
`tests.csv`, `descriptives.csv`, `raggedness.csv` in this folder. The exploratory re-analysis below
adds `--exclude-scenarios <the three ids>` and writes `tests_excl.csv`, `descriptives_excl.csv`,
`raggedness_excl.csv`.

## Update 2026-10-15: Claude Sonnet 5, and three scenarios whose truth the judge cannot see

**Sonnet 5 is the most accurate and most stable judge in the run, and shows none of the
pre-registered effects.** None of its 10 pre-registered tests survives Holm. It never blames
step 1 for a caller-side misuse (0 of 834; Llama 8B 54 percent, Llama 70B 19). It names a culprit
in 4 percent of passing pipelines, level with gpt-oss 120B. It changes its categorical answer on
an identical retest 0.8 percent of the time (next best: gpt-oss 120B 2.0, Qwen3 32B 2.7) and its
responsibility points are as steady as Qwen3 32B's (retest gap 3.2 points against 3.3). Its
last-touch rate, 3.6 percent, comes from one scenario: all 29 of its wrong-step answers are on
`reset_token_validation__missing_edge_case__gpt5__001`, where it blames step 2 for a step-1 bug.
That concentration is also why its F2 categorical test returns p = 1: with one item carrying all
the variation, the wild cluster bootstrap has nothing to resample.

| judge | caller at fault: correct | blames step 1 | says "neither" | callee at fault: correct | false alarm | retest flip |
|---|---|---|---|---|---|---|
| Llama 3.1 8B | 0.46 | 0.54 | 0.00 | 0.87 | 0.92 | 0.26 |
| Qwen3 14B | 0.90 | 0.00 | 0.10 | 0.98 | 0.07 | 0.03 |
| gpt-oss 20B | 0.91 | 0.01 | 0.08 | 0.98 | 0.06 | 0.03 |
| Qwen3 32B | 0.90 | 0.00 | 0.10 | 0.97 | 0.08 | 0.03 |
| Llama 3.3 70B | 0.79 | 0.19 | 0.01 | 0.96 | 0.56 | 0.05 |
| gpt-oss 120B | 0.93 | 0.00 | 0.07 | 0.97 | 0.04 | 0.02 |
| Claude Sonnet 5 | 0.89 | 0.00 | 0.11 | 0.96 | 0.04 | 0.01 |

(Base variant, attribution question, all fidelities, names and spins pooled. Retest flip is R1 from
`raggedness.csv`, which includes the cosmetic variants; so does the false-alarm column of the six-judge
table further down, which is why its figures differ from this one by up to 0.01.)

Three things limit what Sonnet's results can say. All three were known before its results
were read.

1. **Sonnet 5 wrote every step-2 caller** (`build_scenarios.py` generated them with it). When the
   caller is at fault it is judging its own code. Self-leniency would show as blame moved to
   step 1 or to "neither". It never moves blame to step 1, and its "neither" answers sit in the
   four scenarios described next (83 of 89 in the three set aside, 6 in the fourth), where every
   non-Llama judge gives the same answer at a similar rate. Nothing here points to
   self-leniency, but the design cannot rule it out.
2. **"Claude" is both the ladder's frontier name and Sonnet's own name.** For Sonnet,
   `frontier_to_small` is also self-to-small, and its "self" contrast (`self_to_other` against
   `frontier_to_small`) changes only the step-2 name. Its F4 tests are in `tests.csv` but do not
   mean what they mean for the other judges. None is significant. The judge carries
   `self_in_ladder: true` in `config/judges.json`.
3. **Sonnet was added after run 1's results were known.** It is not part of the pre-registered
   judge set, though its analysis is the pre-registered one, unchanged.

### Three caller-fault scenarios test something the judge is not shown

On 23 of 27 scenarios no judge answers "neither" when the caller is at fault. On a fourth, the
non-Llama judges all do so 20 percent of the time; on three, Sonnet and both Qwen and gpt-oss
models do so 30 to 100 percent of the time:

| scenario (caller at fault) | Qwen3 14B | gpt-oss 20B | Qwen3 32B | gpt-oss 120B | Sonnet 5 |
|---|---|---|---|---|---|
| `is_freezing__logic_error__gemini25pro__001` | 1.00 | 0.97 | 1.00 | 0.97 | 1.00 |
| `average_temperature__missing_edge_case__gpt5__001` | 0.77 | 0.60 | 0.80 | 0.30 | 0.93 |
| `celsius_to_fahrenheit__wrong_algorithm__gemini25pro__001` | 0.70 | 0.43 | 0.67 | 0.33 | 0.83 |

Their explanations make the same argument, and on reading the prompts it is correct: the truth
label depends on a fact that is in neither the specification nor the step-2 task the judge sees.
In two scenarios the integration check's expected value only makes sense if the readings are
Fahrenheit, while the step-2 task says only "temperature readings" (`count_freezing_days([32, 20,
50, -5])` is expected to return 3). In the third the expected average skips a `None` reading,
while step 1's contract says `None` is invalid and readings are never silently omitted. A judge
answering "neither" there is right on the information it has. The pre-run review ("violation
plausible and grounded in the judge-facing spec") was a model pass with no human check and missed
this. Qwen3 32B's 8 missing cells are in the first of these scenarios, where it never finished
deciding. The fourth scenario with some "neither" answers, `is_freezing__logic_error__gemini25pro__000`
(20 percent), does say "Fahrenheit" in the step-2 task and is kept.

The Llamas mostly name a step on these three. Llama 8B splits between step 1 and step 2;
Llama 70B answers "neither" or `cannot_tell` only on the first (40 percent) and otherwise names
a step, step 1 in 17 to 60 percent of cells. Excluding the three, caller-fault accuracy is 0.99
for every non-Llama judge (Sonnet 0.992, gpt-oss 20B 0.990, Qwen3 14B 0.990, Qwen3 32B 0.989,
gpt-oss 120B 0.988); Llama 70B 0.84, Llama 8B 0.47.

**Exploratory re-analysis without the three** (decided after seeing the data; label it as such):

- **The run-1 headline holds.** The upstream bias in the small members survives: Llama 8B +16.9
  points (p_holm .0004) and +0.39 on the categorical answer (.0004); Qwen3 14B +10.1 points
  (.0048, was +14.1); gpt-oss 20B +7.3 points (.020, was +8.7). For Qwen3 14B and gpt-oss 20B the
  bias is in the points only. Their categorical answer is right 99 percent of the time, but when step 2
  is at fault they still put 15 to 18 points on step 1, against 5 to 10 on step 2 when step 1 is
  at fault.
- Llama 8B's fidelity effect no longer survives (p_holm .098).
- Two plaintext-trust (F3) effects appear: when the at-fault step's note overclaims, Sonnet gives
  that step 1.4 fewer points (p_holm .0004) and gpt-oss 20B 3.1 fewer (.027). Both are small and
  post hoc, and neither is present in the full data (−0.1 and −1.5 points, p_holm 1.0 and .58).
  Treat them as leads.
- Qwen3 14B's self-name effect (F4) is unchanged (−3.9 points, .022).

### Analysis fix

`wcb_test` (`analysis/wcb.py`, shared with the authorship study) returned the minimum p-value,
1/(B+1), when the observed standard error was zero, so a constant outcome looked highly
significant. It now returns p = 1. No committed result had a zero standard error: not this run's
60 original tests, and not the authorship study's open-weight pilot. It was found because Sonnet's
partial data had no wrong-step answers. A related limitation remains: bootstrap draws whose
standard error is undefined count as not extreme, which pushes p down when only one or two items
vary. Here that happens only in three Sonnet tests on the reduced data, all with p ≥ 0.57.

### Sonnet run notes

Served by Anthropic through OpenRouter (`anthropic/claude-sonnet-5`, every row), same prompts,
schema (`attrib-v1/split-v2`, grammar on both questions) and 4,096-token output cap as the others.
Adaptive thinking was left at the model's default: it thought on 75 percent of calls, 295
reasoning tokens on average. OpenRouter limits new accounts to 20 requests per minute on this
model, so the judge ran at 18 per minute (`rpm` in `judges.json`, SDK-internal retries off) over
about four hours. 28 cells failed on rate limits in the first, uncapped minute and were rerun; 4
attempts ran out of output budget and succeeded on retry.

## Headline (six judges, 2026-10-14)

**The bias we pre-registered as "last-touch" does not exist in these judges. The opposite does,
and only in the small and the Llama models.** When step 1's function is wrong and the failure
surfaces in step 2's call, every judge correctly blames step 1 (96 to 98 percent; Llama 8B 87).
When step 2 misused a correct step 1, four judges still get it right about 90 percent of the
time, but Llama 3.3 70B drops to 79 percent and Llama 3.1 8B to 46 percent, and the wrong
answers go to step 1, the upstream component. Nothing in this design pushed blame downstream.
(Added 2026-10-15: nearly all of the four judges' remaining 10 percent are "neither" answers on
three scenarios whose truth the judge cannot see; see the update above.)

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
| Claude Sonnet 5 (added 2026-10-15) | not published | 0.04 | 0.01 | 3.2 | 0.00 (0.00) |

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
in explanations) have not been run. Two exploratory cuts have been made, each because it changes
how a pre-registered result reads: the scenario-level concentration of Llama false alarms above,
and (2026-10-15) the re-analysis without three caller-fault scenarios in the update section. The
pre-registered sensitivity analysis (`--exclude-caveated`) has not been run either.
