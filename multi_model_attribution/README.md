# Multi-model attribution: who gets blamed when a two-step code pipeline fails?

**A separate question from the authorship-label study in the rest of this repository.** That
study asks whether a judge treats identical buggy code differently depending on who it is
told wrote it. This one asks: in a pipeline where one model writes a component and another
writes the component that uses it, and a failure surfaces in the second step but was caused
in the first (or vice versa), do judge models attribute the defect to the right step, and
what distorts that attribution? Motivation: multi-model execution of code is becoming
standard, the models talk to each other in plaintext and code, and some model ends up
deciding whose fault a failure is.

Working hypothesis (from the open-weight pilot of the other study, where cheap models were
not more biased than Claude but far noisier: qwen3-32b flipped its answer to an identical
question one time in three): smaller models attribute more raggedly.

This folder imports the elicitation client and writer code from `scripts/` and the
bootstrap from `analysis/` as libraries, and uses the existing item banks as raw material. It
adds nothing to the other study's configs or data.

## Design

A **scenario** is built from one source item: step 1 is a callee function (the item's buggy
or clean twin), step 2 is a caller written against the callee's contract. Callers are
generated and validated in a sandbox so the three `cause` conditions are true by construction:

| cause | step 1 | step 2 | what the judge sees | truth |
|---|---|---|---|---|
| `callee` | buggy twin | correct caller whose input hits the bug | failure surfaces in step 2's call | step_1 |
| `caller` | clean twin | caller that violates one contract clause | failure | step_2 |
| `none` | clean twin | correct caller | integration check passes | neither |

Factors crossed within each scenario:

- `fidelity`: `full` (both steps' code, each step's handoff note, trace with per-step files),
  `summary` (one-line notes, assembled module, trace), `final_only` (assembled module, names only).
  The specification (aim + contract) is shown at every fidelity.
- `names`: `frontier_to_small` (Claude → Gemma), `small_to_frontier`, `self_to_other` (the
  judge's own family → Gemini). Family-level names only.
- `spin`: the at-fault step's handoff note is `truthful` or `overclaiming` ("handles all edge
  cases; tested and verified"). Only where a note is shown and cause ≠ none.
- `cosmetic`: a variable-renamed variant on a seeded third of scenarios (names and spin fixed).
- 2 repeats of every cell.

Questions (fresh context, structured output): `q_attribution` (step_1 / step_2 / neither /
cannot_tell + explanation; all causes) and `q_blame_split` (100 responsibility points over
the two steps + explanation; cause ≠ none).

Judges: six open models on OpenRouter, a small and a large member of three families:
Llama 3.1 8B, Qwen3 14B, gpt-oss 20B, Qwen3 32B, Llama 3.3 70B, gpt-oss 120B. Claude Sonnet 5
(also via OpenRouter) was added as a seventh judge on 2026-10-15, after run 1's results were
known; it is not part of the pre-registered judge set. It wrote the step-2 callers, and its
family name is the ladder's frontier name (`self_in_ladder` in `config/judges.json`), so its F4
status contrasts are not comparable with the other judges'.

Source items: the 65 items whose verdict and twin verdict are `ok`, whose aim-visibility is not
"no", and whose flavour is observable from a contract-correct caller (logic_error,
wrong_algorithm, missing_edge_case, silent_failure, known_trap). 30 are taken round-robin over
aims, alternating bank priority.

## Pre-registered analysis (locked before the full run)

Cluster = source item. Linear probability / OLS, wild cluster bootstrap (B = 4999, seed 0),
Holm within each (family, judge). Baselines: full / callee / frontier_to_small / truthful.
`cannot_tell` counts as incorrect. Every model includes the other factors as additive dummies.

| family | rows | outcomes | tested |
|---|---|---|---|
| F1 fidelity | cause ≠ none, attribution | correct | summary − full, final_only − full |
| F2 last-touch | cause ≠ none | blamed_wrong_step; points_to_wrong_step | cause=caller (negative = blaming step 2 under cause=callee exceeds the reverse) |
| F3 plaintext trust | cause ≠ none, fidelity ≠ final_only | correct; points_to_at_fault | overclaiming |
| F4 status | cause ≠ none | blames_step2; step_2_points | small_to_frontier, self_to_other vs frontier_to_small |

Descriptives with cluster-bootstrap CIs: accuracy by fidelity × cause × judge; last-touch rate
P(step_2 | cause=callee); control false-alarm rate. Raggedness (descriptive): R1 retest flip
rate, R2 retest split gap, R3/R4 cosmetic flip and gap in excess of retest noise, R5 control
false alarms; then raggedness against parameter count within family. Exploratory, flagged as
such: fidelity × cause, `failure_kind` as moderator, flavour, bank, mentions of model names in
explanations. Sensitivity: rerun excluding scenarios whose item carries any caveat.

Caveat fixed in advance: in `self_to_other` the judge's family is always step 1, so the self
contrast is reported against `frontier_to_small` (also a strong name at step 1).

## Results

Run 1 (2026-10-14, six judges, 23,068 rows; Claude Sonnet 5 added 2026-10-15, 26,914 rows) is in
`results/run1/`; findings and deviations from this pre-registration are in `results/run1/STATUS.md`.
In short: no last-touch bias in any judge; an upstream-blame bias in the small members of each
family and in both Llamas; the Llamas name a culprit in most pipelines that actually passed;
handoff-note spin and model names moved nothing. Sonnet 5 is the most accurate and stable judge
and shows none of the pre-registered effects. Three caller-fault scenarios turned out to depend on
facts the judge is not shown; an exploratory re-analysis without them leaves the headline intact.

## How to run

```bash
# from the repo root, with OPENROUTER_API_KEY set
uv run --with-requirements requirements.txt python -m pytest multi_model_attribution/tests
python -m multi_model_attribution.build_scenarios --dry-run --limit 1     # prints a generation prompt
python -m multi_model_attribution.build_scenarios                          # ~$2; writes scenarios/ and review.md
# read scenarios/review.md; mark violating callers reviewed in the scenario files
python -m multi_model_attribution.run_judges --out-dir multi_model_attribution/results/run1 --dry-run
python -m multi_model_attribution.run_judges --out-dir multi_model_attribution/results/run1 --judge qwen3-32b --limit 20
python -m multi_model_attribution.run_judges --out-dir multi_model_attribution/results/run1
python -m multi_model_attribution.analyze --results-dir multi_model_attribution/results/run1
# exploratory, labelled in STATUS.md: drop named scenarios, outputs get suffix _excl
python -m multi_model_attribution.analyze --results-dir multi_model_attribution/results/run1 \
  --exclude-scenarios is_freezing__logic_error__gemini25pro__001,celsius_to_fahrenheit__wrong_algorithm__gemini25pro__001,average_temperature__missing_edge_case__gpt5__001
```

Operational settings inherited from the pilot: 4,096-token output cap, 240 s per-attempt
deadline, fresh connection per call, 48 concurrent per judge, Groq-first routing for gpt-oss,
price-sorted routing with `require_parameters` for the others, serving provider recorded per
row. A judge may list question kinds under `prompted_json_for` to run them without a JSON
grammar (one trailing format line, reply parsed); used for Llama 3.3 70B's split question. A judge may
set `rpm` (requests per minute, enforced across workers) and `sdk_max_retries` where the provider caps
request rate; Sonnet 5 runs at 18 per minute with SDK retries off, under OpenRouter's 20-per-minute
new-account cap. Long runs go through a launcher script in a tmux session under `caffeinate`.
