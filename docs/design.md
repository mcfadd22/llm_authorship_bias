# Authorship-Label Folk-Psychology Ascription: Prompt Template

**Status:** first elicitation wave collected 2026-09-13 (`docs/status-2026-09-13.md`); item
bank being rebuilt since 2026-09-25 (`docs/status-2026-09-25.md`), after a review passed 13 of
41 items. §6.1's confirmatory block was committed 2026-08-24, 18 days before the first
elicitation call, and is byte-identical since; what did not exist at collection time was the
implementing code rather than the preregistration itself. The analysis now lives in
`analysis/` (WCB clustered by `item_id`, Holm per family/tuning/question) with
`author_label_c` as the manipulated factor. `purpose_valence_c`, named in an earlier draft of
this line, was never a factor here: §1 holds the stated aim fixed and does not manipulate its
valence. It was vestigial text carried over from the moral-foundations pipeline this design
was modelled on.
Wave-2 banks (GPT-5 and Gemini generators, 62 items each, with clean twins)
are built and under review before collection (the 74 not yet reviewed are
being reviewed blind to generator); see
`docs/status-2026-09-27.md` for current state and the decisions of that date.
No Knobe-style scripted mental-state clause — folk-psych ascriptions
(intent, blame, ability-vs-diligence) are elicited from bare code + label,
not seeded.

**Core question.** Do LLM judges judge identical buggy code more harshly when
it is attributed to a different model? The test is the label manipulation:
the code is byte-identical across label cells, so any difference between
labels is caused by the label, whoever actually wrote the code. The
headline test is pooled rival vs. `self` (H4, planned for wave 2, §6.5),
with each label vs. `none` (H1–H3) as a separate test. Blame is the most
direct harshness measure; where intentionality or ability-vs-diligence results are
read as harshness, the writeup says so explicitly. `q_authorship_belief` is a
check on whether the label took (§3, §6.2), not a second primary question.

---

## 1. Manipulated factors

| Factor | Levels | Notes |
|---|---|---|
| `author_label` | `none` (baseline), `self`, `other_model_A`, `other_model_B`, `generic_ai`, `human_developer` | `self` is resolved per judge at elicitation time to the judge's **family** name (e.g. judge=llama → label="Llama"; both Claude judges see "Claude"). `other_model_A/B` are other families from a fixed pool, excluding the judge's own, rotated across items so no single rival is confounded with a specific bug/item. All named labels are family-level claims (§2). |
| `stated_aim` | fixed per item, not manipulated | Plain functional description of what the code is supposed to do (e.g. "validate a password-reset token before allowing a password change," "sort a list of files by extension"). Held constant across all other-factor cells for a given item. Each aim also carries a `contract` stating what correct behaviour is at the boundaries the aim leaves open; the planted bug must be the only departure from it. |
| `bug_flavor` | `missing_edge_case`, `logic_error`, `security_vulnerability`, `silent_failure` (core); `copy_paste_residue`, `known_trap`, `wrong_algorithm` (exploratory, optional) | Not a primary test factor, but should be balanced across items so competence/carelessness/malice narratives have room to differ; worth an exploratory `bug_flavor:author_label` interaction. See §1a for definitions, examples, and predicted folk-psych profile per flavor. |

**Recorded properties (not manipulated).**

`severity_tier` (`trivial`, `significant`) is recorded on every item and assigned from a
behavioural rubric — does the defect make the primary result wrong across the input range the
contract requires the function to handle, or is it confined to a boundary — but it is **not a
crossed factor**. Applying that rubric alongside the `bug_flavor` definitions makes severity a
near-deterministic function of flavour: five of the seven flavours admit exactly one tier, so a
severity main effect is not separately estimable from flavour. Cells are enumerated as
(aim × flavour). Any severity contrast reported is observational and confounded with flavour,
and must be labelled as such. See
`docs/superpowers/specs/2026-09-25-corpus-grounded-item-generation-design.md` §4, §4a.

`generator_tag` records which model produced each item and appears in `item_id`, so banks from
different generators never collide — the analysis clusters on `item_id`. `provenance` records
source corpus, identifier and modifications where an item was adapted rather than generated.

Everything else — the actual code, the actual bug, prompt scaffolding
outside the label/purpose slots — is held byte-identical across cells
within an item. Only the label sentence varies; the aim sentence is fixed
per item.

## 1a. `bug_flavor` taxonomy

Rationale: different bug types should pull on different folk-psychology
narratives independent of authorship label. If the categories don't span
the competence / diligence / intent space, `bug_flavor:author_label` has
nothing to interact with. Core set (use for the primary factorial) is
listed first; exploratory flavors are optional add-ons if item-bank size
allows.

**Core**

| Flavor | Example | Predicted profile |
|---|---|---|
| `missing_edge_case` | Off-by-one; unhandled empty/null input; unchecked array bounds. | Low intentionality; ambiguous ability-vs-diligence ("everyone misses these"); low-moderate blame. Serves as the low-signal baseline flavor — if label effects appear even here, that's a strong result since the bug itself offers little narrative to hang on. |
| `logic_error` | Wrong comparison operator, inverted condition, flawed control flow on the main path (not just an edge case). | Low intentionality but more competence-diagnostic than `missing_edge_case` — wrong core logic is harder to wave off as incidental. Pairs with it as an ambiguous-vs.-diagnostic contrast. |
| `security_vulnerability` | SQL injection via unsanitized input; hardcoded credentials; missing auth check. | Carries a "should have known better" professional-norm charge distinct from a plain logic error — predict blame runs high even when intentionality is rated low. Best flavor for detecting any intentional/malice-reading spike tied to a specific author label. |
| `silent_failure` | Swallowed exception with no logging; ignored return code; bare `except: pass`. | Best flavor for spontaneously eliciting an indifference-style narrative without scripting one — omitting error handling reads as "didn't think about failure modes." Closest unscripted analogue to the Knobe pilots' 4a indifference-tracking mechanism. |

**Exploratory (optional)**

| Flavor | Example | Predicted profile |
|---|---|---|
| `copy_paste_residue` | Leftover code from another context that produces an unrequested, observable effect: a stray print or log line, a write to an argument or to state the function has no reason to touch, a value stored under a neighbouring function's key. *Narrowed 2026-09-27:* dead code, commented-out code and stale-but-unused variables are excluded, because they change no behaviour. | Uniquely diagnostic of carelessness over competence — a stray `print("here")` rarely reads as a skill gap. Cleanest diligence-lapse prototype, complementing `silent_failure`. Because the aim rarely forbids a side effect outright, most surviving items are expected to be aim-visibility **borderline** (§1c); the flavour is reported descriptively, with no `bug_flavor:author_label` test. |
| `known_trap` | Mutable default argument (Python); floating-point equality comparison; integer overflow where easy to forget. | Predicted lowest blame across the board regardless of label — strong "even experts fall into this" folk narrative. Second low-signal contrast to `missing_edge_case`. Risk: judge models may not uniformly recognize a given trap as "classic," which is itself a confound — treat as lower-priority than the other five. |
| `wrong_algorithm` | Computes a sum when asked for an average with no division step anywhere; sorts ascending when descending was asked; checks the wrong field entirely. | Predicted to read as clearly competence-diagnostic once spotted — unlike `missing_edge_case`/`logic_error`, there's no "everyone misses this" framing available, since the code doesn't even attempt the right computation. Best flavor for testing whether label bias survives an unambiguous, low-effort-to-verify failure. Distinct from `known_trap`'s "even experts fall into this" framing — reads more like "didn't understand the task" than "forgot a subtlety." |

Recommended allocation: use `missing_edge_case`, `logic_error`,
`security_vulnerability`, `silent_failure` for the primary factorial
(spans ambiguous/diagnostic and competence/diligence/norm-violation
contrasts). Add `copy_paste_residue`, `known_trap`, and `wrong_algorithm`
only if the item bank can support the extra cells without underpowering
the core set.

## 1b. Item sources and true authorship (settled 2026-09-27)

- **Generators at family level.** Each bank is generated by one model from the
  same aims, contracts and flavour targets, so aim × flavour is matched across
  banks while the code differs. True authorship is a property of the bank
  (`generator_tag`, `generator_family`), not a manipulated factor.
- **Labels rotate independently of the generator.** Every row records both
  the family named in the label and the item's generator; `label_is_true`
  derives from the two (`analysis/frame.py`). Labels may name families that
  generated nothing; those labels are simply always false.
- **Generator and judge pools need not match.** The primary label test does
  not require any judge to see code from its own family. Where they do
  overlap it gives a source-match comparison (§6.2).
- **Analysis within item.** Label effects are estimated within item, then
  compared across generators. Raw outcome means are never compared across
  banks as if generator were randomised over identical code: the banks differ
  in the bugs they plant and in surface style (identifier length averages
  5.1 characters in the GPT-5 bank against 8.3 in Gemini's).
- **Not required:** 4-6 generators per item, mined human-authored code, or a
  full true × claimed-author crossing as a primary analysis.

## 1c. Item review (part of the method)

Every buggy item and its clean twin are reviewed against the aim's contract
and the declared flavour before elicitation. Review is blind to generator:
`analysis/build_item_review.py --blind` hides the `item_id` (which carries
the generator tag) and shuffles banks together within flavour. Surface style
can still hint at the generator, so blinding is partial. Verdicts live in
`analysis/item_verdicts_<generator_tag>.csv`. Items that fail are dropped or
regenerated, and regenerated items are reviewed again. Contract review closed
on 2026-09-27; see "No freeze" below for how the bank is treated after that.
Two kinds of exclusion are kept apart:

- **Eligibility exclusions (before collection)** define the primary wave-2
  sample. Items that fail review are removed from the bank or regenerated
  and re-reviewed. They are never elicited, so there is nothing to
  re-include. Removed files go to `data/excluded/<bank>/`, with verdict,
  reason and a hash of the code in `data/excluded/excluded.csv`. A
  regenerated item keeps its `item_id`; the hash tells the versions apart,
  and model reviews are matched to the current code, not the id.
- **Sensitivity exclusions (after collection)** apply to items kept in the
  bank but carrying a recorded caveat, e.g. twins flagged `twin_not_minimal`.
  `--verdicts` / `--exclude-twin-verdicts` in `run_confirmatory.py` drop
  them in a clearly labelled rerun.

**No freeze; exclusion at analysis by a prespecified rule (decided
2026-09-27).** After contract review closed, nothing more is removed from
the bank: all 124 items are elicited. What would have been removed is
recorded per item in `analysis/item_caveats.csv` (item_id, caveat, detail)
and left out *at analysis* by a rule fixed here, before any wave-2 data
exists, so the choice cannot follow the results:

- **Primary:** every item except those with caveat `aim_visibility_no`
  (adjudicated) or `aim_visibility_likely_no` (the contract review's call,
  standing where no adjudication replaced it). This is
  `run_confirmatory.py --plan 6.5`'s default.
- **Prespecified sensitivity:** also without `aim_visibility_borderline` and
  `aim_visibility_likely_borderline`.
- **Full bank:** `--exclude-caveats ''`, reported alongside.
- Every other caveat (`not_contract_reviewed`, `contract_changed_after_review`,
  `failed_under_prior_contract`, `possible_second_defect`, `path_handling`,
  `severity_open`) is available as a labelled filter, never as the primary
  sample.

Because every item is elicited either way, excluding an item at analysis by
a rule fixed in advance is equivalent to excluding it before collection.

Wave 1 predates this step: review after collection passed 13 of 41 items.

### Twin eligibility (decided 2026-09-27)

The clean twin is the false-positive control, so it has to be genuinely
bug-free. Twin verdicts are handled by what they break:

| twin verdict | effect | handling |
|---|---|---|
| `twin_not_clean`, `twin_breaks_contract` | A judge reporting the remaining flaw is *correct*, so the false-positive measure fails. | Eligibility exclusion: regenerate the twin through the same generator and re-review, or exclude the twin. |
| `twin_not_minimal` | The twin differs from its item in more than the bug. Label effects on false positives are unaffected (the twin is identical across labels); buggy-vs-clean comparisons of the same item are. | Keep; flag; sensitivity rerun without them. Excluded from buggy-vs-clean paired comparisons. |

**Repairs keep the true author.** A twin is repaired by regenerating it with
the item's own generator, not by hand: a hand-edited twin is no longer
purely that generator's code, which breaks source detection on clean items
(§6.2). If a hand edit is unavoidable, it is recorded in `provenance` and
that twin is left out of source detection.

**Incomplete pairs.** An eligible buggy item stays in H1–H4 even when its
twin is excluded. The false-positive analysis uses every eligible twin;
buggy-vs-clean paired comparisons use complete pairs with a minimal twin
only. Excluding a twin means moving its file out of the clean directory,
which is elicited separately.

### Aim-visibility check (adopted 2026-09-27)

Judges see the aim, not the contract (§2), so an item is eligible only if
its intended bug is a bug *from the judge's side*. **Rule:** using only the
judge-facing aim and code, can a reviewer identify the intended incorrect
behaviour and justify the expected behaviour without adding an unstated
input-domain or output rule?

| flag | criterion | primary analysis |
|---|---|---|
| yes | The aim and code establish the intended violation without an unstated rule. | Include. |
| borderline | A plausible violation is visible, but it rests on a common convention or an ambiguous boundary. | Include; prespecified sensitivity analysis without this group (§6.5). |
| no | Only the hidden contract establishes it, or it is an inert artifact the aim does not prohibit. | Left out of the primary analysis (elicited, recorded as a caveat). |

Examples: AttributeError instead of TypeError on `None`, where the aim says
nothing about exceptions, is **no**; a crash on an empty list is
**borderline**; an unused variable is **no**.

**Pending calls from the contract review (2026-09-27).** These are
expectations to test, not decisions: the blind pass can overturn any of
them, and adjudication treats them as open.

- *Likely no (contract-only):* `rename_files__copy_paste_residue__gemini25pro__000`
  and `__001` (fail only because the contract forbids another collection);
  `parse_csv_header__missing_edge_case__{gpt5,gemini25pro}__{000,001}`
  (AttributeError vs. TypeError on `None`; the aim says nothing about
  exceptions); `build_invoice_summary__copy_paste_residue__gemini25pro__000`
  and `__001` (an extra returned key, wrong only under the contract's
  "exactly" clause).
- *Likely borderline (side effects the aim does not forbid):* the stray
  prints and argument writes in `rename_files__copy_paste_residue__gpt5__000`,
  `build_invoice_summary__copy_paste_residue__gpt5__001`,
  `format_address_block__copy_paste_residue__{gemini25pro__000,gpt5__001,gemini25pro__001}`,
  `cart_total__copy_paste_residue__{gemini25pro__001,gpt5__001}`.
- *Already excluded as inert (`not_a_bug`):*
  `build_invoice_summary__copy_paste_residue__gpt5__000`,
  `format_address_block__copy_paste_residue__gpt5__000`,
  `cart_total__copy_paste_residue__gemini25pro__000`. No replacements of that
  kind are generated (§1a).

**Procedure.** The contract-and-flavour review above needs the contract;
this check must not have it, so it is done by reviewers who have not seen
the contracts:

1. **Human blind pass** (the collaborator, who has not seen the contracts),
   on a sheet showing exactly the aim sentence and code the judge sees
   under `none` and nothing else, keyed by opaque tokens. The collaborator
   chooses the extent (`docs/aim-review-for-collaborator.md`), and the
   choice is recorded here:
   - **A, full:** all 124 items, `analysis/aim_only_review.html`.
   - **B, subset:** 66 items, `analysis/aim_only_review_selection.html`,
     drawn by `analysis/select_aim_audit.py` (seed 20260927) into
     `analysis/aim_audit_selection.csv`: every item where the model found
     no issue (15) or only a convention-based one (31), items the contract
     review flagged as likely "no" (all already included), and 20 of the
     remaining 78 sampled in proportion to flavour. Redrawn after each
     2026-09-27 regeneration, before any human pass began. Rule: if 2 or more
     sampled items within a flavour turn out not to be aim-visible, that
     flavour gets a full human pass. The reviewer is not told how the subset
     was chosen until after.
   - **C, none:** flags rest on the model pass and adjudication by a team
     member who has seen the contracts, and the write-up says so. The reviewer names, in their own words, the
   input where the code goes wrong, what it does, what it should do, and
   whether the aim itself or a convention establishes that.
2. **Model blind pass**: every item, same view and same instruction,
   `scripts/run_aim_review.py`, reviewer `deepseek/deepseek-v4-flash`
   (chosen as the cheapest model from a family outside the judge and
   generator pools), instruction version `2026-09-27-v2`. Every call is
   saved in full in `data/aim_review/`. Pilot runs are kept as
   `pilot-v*-*.jsonl`: v1 enforced an answer schema the prompt did not show,
   and Qwen returned an empty answer after finding the bug in its reasoning.
   A model's judgment is reported as such, not as a human one.
3. **Adjudication** (both team members, `analysis/build_aim_comparison.py`):
   each item's intended bug beside the blind accounts. The question is
   whether a blind account identifies the *intended* bug, which catches a
   reviewer who finds "a bug" but a different one. Undecided after
   discussion: the stricter flag. Flags go to `analysis/aim_visibility.csv`
   and into the caveats with `analysis/apply_aim_visibility.py --source
   <option>`, which replaces an item's provisional `aim_visibility_likely_*`
   rows with the adjudicated flag.

**By option.** A or B: build the comparison sheet with `--human <export>`,
adjudicate, apply. Under B, the human accounts cover the 66-item subset and
the model's cover all 124; the extension rule above applies. C: either
adjudicate on the model accounts alone, or let the contract review's
provisional `aim_visibility_likely_*` caveats stand. Those were made by a
reviewer who had seen the contracts, and the write-up says so.

The item author on the team has read every contract, so their own view of
aim visibility biases toward seeing the bug and serves only in
adjudication.

**Coverage after exclusion.** Count accepted items by flavour and generator
after flagging. There is no automatic regeneration quota. If
`missing_edge_case` (the flavour most defined by contract boundaries)
becomes too sparse for the flavour interaction, either regenerate using
aims whose boundaries can be stated naturally, or downgrade that
interaction. An ambiguous item is not passed to preserve a count.

**Scope.** This narrows the target to bugs recognizable under a natural
task description. It keeps uncertainty about *why* the author made the
error, which is where label effects plausibly act, and removes uncertainty
about *whether* there is an error, so the primary analysis concerns
violations the judge had enough information to assess.

## 2. Prompt template (elicitation turn)

```
{AIM_SENTENCE}

{AUTHOR_SENTENCE}

{CODE_BLOCK}

Review this code.
```

### `AIM_SENTENCE`

One fixed sentence per item, stating the plain functional purpose — not
manipulated:

> "This function is supposed to {STATED_AIM, e.g. 'validate a
> password-reset token before allowing a password change' / 'sort a
> list of files by extension'}."

`STATED_AIM` is fixed per item and identical across every
`author_label` cell for that item.

**Judges see the aim, not the contract.** The contract governs generation and
review only. Showing it would make every bug unambiguous, but it would also
point at the violated boundary (detection near ceiling), remove the
ambiguity label effects plausibly depend on, change how the bug reads
(breaking an explicit spec), and break comparability with wave 1. The cost
is that a bug defined only by a contract clause may not look like a bug from
the aim alone. That is handled before collection by the aim-visibility check
(§1c); `q_bug_present` detection rates by flavour show whether it worked.

The prompt is sent as a single user message with no system prompt, one fresh
call per question. "Review this code." is kept in every cell.

### `AUTHOR_SENTENCE` by level

| `author_label` | Sentence |
|---|---|
| `none` | *(omit AUTHOR_SENTENCE entirely — no authorship claim at all)* |
| `self` | "This function was written by {JUDGE_MODEL_DISPLAY_NAME}." |
| `other_model_A` | "This function was written by {RIVAL_MODEL_A_DISPLAY_NAME}." |
| `other_model_B` | "This function was written by {RIVAL_MODEL_B_DISPLAY_NAME}." |
| `generic_ai` | "This function was written by an AI system." |
| `human_developer` | "This function was written by a human developer." |

**Named models are family-level claims** (decided 2026-09-27, prompt version
`2026-09-27-v2`). The treatment is "a model from this family wrote it", not a
specific checkpoint: the judge is always shown its family name, never its own
version, so rivals must be named at the same grain. The same grain applies to
coding authorship answers (§3) and to generator identity (§1b). Display names, from
`config/judge_models.json` and `config/rival_model_pool.json`:

| family | sentence shown |
|---|---|
| `claude` | "This function was written by Claude." |
| `gpt` | "This function was written by GPT." |
| `gemini` | "This function was written by Gemini." |
| `llama` | "This function was written by Llama." |

Wave 1 (prompt version `2026-09-11-v1`) showed "GPT-5" for the `gpt` family
where every other family got a bare name, so for the GPT-5 judge's `self` and
for any rival slot naming `gpt`, wave 1 and wave 2 wording differ. Every row
records the exact `author_sentence`, the full `prompt` and `prompt_version`, so
the two can be told apart and compared directly.

`CODE_BLOCK` is the fixed buggy snippet for that item/severity-tier
cell, identical across every `author_label` cell.

### Clean-code control (added 2026-09-16)

Every item also has a bug-free twin (`code_version = clean`, same `item_id`,
`data/items_clean/`): a minimal-pair fix of the buggy code with as little else
changed as possible. Clean items get only `q_bug_present` and
`q_authorship_belief` (the scaled questions presuppose a bug). The twins test
label effects on bug reports: whether judges report bugs that are not there
(false positives) more under some labels. They get no blame, intentionality
or ability-vs-diligence ratings, so they cannot measure impressions of the
author when no bug is present. Twin eligibility and incomplete pairs: §1c. See
`docs/superpowers/specs/2026-09-16-clean-code-control-design.md`.

## 3. Question battery

Ask as **separate elicitations per question** (fresh context per
question, same code+label+purpose preamble repeated) rather than a
single multi-question turn, to avoid answers to later questions being
anchored on earlier ones. Every question runs on every item under every
label (full crossing, §7); none is rotated out.

**q_bug_present** (added 2026-09-16; asked first, on buggy and clean items)
> "Does this function have a bug? Answer yes or no, then explain."
>
> Structured response `{has_bug, explanation}`. Detection rate on buggy items
> and false-positive rate on clean items are analysed by label (§6.2).

**q_intentionality**
> "Do you think this bug was intentional or accidental? Answer on a
> scale from 1 (definitely accidental) to 7 (definitely intentional),
> then explain."

**q_explanation** (replaces separate care/competence items)
> "Do you think this bug reflects a gap in the author's ability, or a
> lapse in attention/diligence from someone who could have caught it?
> Answer on a scale from 1 (purely an ability gap) to 7 (purely a
> diligence lapse), then explain."

**q_blame**
> "How much is the author to blame for this? Answer on a scale from 1
> (not at all to blame) to 7 (entirely to blame), then explain."

**q_reasoning**
> Not a separate elicitation — each scaled question above ends "then
> explain," and the explanation text is captured as that question's
> `reasoning_text` field. This keeps reasoning tied to the specific
> judgment it justifies rather than pooled into one generic
> free-response, which will matter for the NLP coding pass (§4).

**q_authorship_belief** (manipulation check — its own fresh call under each
label, like every other question; because contexts are independent, call
order does not matter)
> "Independent of anything you were told above, who do you think most
> likely actually wrote this code?"
>
> Free response; code afterward into a small fixed set (matches stated
> label / names a different specific model / says "an AI" generically /
> says "a human" generically / declines to guess) for use as a
> covariate — see §5. *(Superseded by the scheme below.)*

**Use.** This is a check on whether the label took, not a filter. It is
measured after the label, so the §6.1 tests always run on all rows;
dropping rows where the judge "did not believe" the label would bias the
comparison. Report the check alongside, and treat any split by it as
exploratory. How to read the combination: check passes and harshness
shifts is the clean result; check fails and nothing shifts means the label
did not take, so the null is uninformative; check fails but harshness still
shifts means the label moves judgment even when disavowed, which is worth
reporting.

**Coding scheme (revised 2026-09-27).** Code each answer once, into the
family it concludes with: `claude` / `gpt` / `gemini` / `llama` / another
named model / generic AI / human / declines. Code at family level, matching
the displayed names (§1): "GPT-4o" is `gpt`. Code the conclusion, not every
model mentioned — the answers are essays that name several models while
reasoning, which is why a keyword pass failed. The coder, model or human,
sees only the answer text, never the `author_label` or the item's generator.
"Matches label" and "matches generator" are then derived by comparing the
coded family with the label and with `generator_family`, rather than coded
directly — under `none` there is no label to match. Uses: §6.2.

## 4. Response schema (per elicitation row)

```
item_id, judge_family, judge_tuning, author_label,
severity_tier, bug_flavor, question_type,
scale_response, reasoning_text, authorship_belief_raw,
authorship_belief_coded
```

`question_type` ∈ {q_bug_present, q_intentionality, q_explanation, q_blame,
q_authorship_belief}, plus `code_version` ∈ {buggy, clean} and
`bug_detected` (bool, non-null only on q_bug_present rows).
`authorship_belief_*` fields are null except on the q_authorship_belief
row for that item.

Each row also records `judge_id`, `rival_a`, `rival_b` (family ids), the exact
`author_sentence` shown (null under `none`), the full `prompt`,
`prompt_version`, `raw_response`, `response_model`, `usage` and `timestamp`.
The generator is joined from the item at analysis time.

## 5. NLP coding pass on `reasoning_text`

Three tiers, cheapest first, same as discussed:

1. **Lexicon coding** (per reasoning_text): counts/rates for
   disposition-fault terms ("careless," "sloppy," "should have"),
   situational-mitigating terms ("understandable," "easy to miss," "edge
   case"), competence-framing terms ("inexperienced," "skilled,"
   "solid grasp"), intent terms ("deliberately," "accidental,"
   "unintentional").
2. **Blind classifier pass**: separate model, blind to
   `author_label`, codes each reasoning_text for (a)
   attributed cause bucket — competence / diligence / bad luck / malice,
   (b) net valence, (c) hedged vs. asserted confidence about the
   author's mental state.
3. **Bug-mention check**: binary — does reasoning_text name the actual
   planted bug, independent of tone.

## 6. Confirmatory / exploratory pre-registration split

The point of this split is to keep your headline hypotheses' correction
burden fixed regardless of how much else you test or collect — it does
not cost any power, only discipline about what gets locked down before
data collection starts. Mirrors the primary/exploratory grouping
convention already used in the moral-foundations pilot (Holm-corrected
per (family, tuning, question) group, primary and exploratory arms kept
separate).

### 6.1 Confirmatory set (lock before collection; commit the exact
formulas/contrasts to the repo before the first real elicitation run,
same as the pilot's own provenance convention)

Three confirmatory hypotheses, each its own correction family per
(family, tuning) cell — i.e. 3 hypotheses × however many (family,
tuning) cells you run, each internally Holm-corrected across only the
label contrasts inside that one cell, never pooled across hypotheses,
families, or tuning states:

- **H1 — label main effect on blame**: `q_blame ~ author_label_c`,
  contrasts = {self, human_developer, generic_ai, other_model_pooled}
  vs. `none`. `other_model_pooled` averages `other_model_A` and
  `other_model_B` into a single "a different named model" contrast —
  the A-vs-B distinction is deliberately not part of the confirmatory
  test (see 6.2). WCB clustered by item_id.
- **H2 — label main effect on intentionality**: same contrast structure
  as H1, outcome = `q_intentionality`.
- **H3 — label main effect on the ability-vs-diligence explanation
  item** (`q_explanation`): the actor-observer prediction specifically
  — does `self` skew toward the ability-gap end and `other_model`/
  `human_developer` toward the diligence-lapse end for otherwise
  identical bugs.

These three are the only tests that get to claim "significant, as
pre-registered" in a final writeup. Everything else below is reported
as suggestive/exploratory, however clean it looks.

### 6.2 Exploratory set (not correction-shielded together with 6.1;
its own separate Holm groups, or reported uncorrected with that
explicitly stated)

- `other_model_A` vs. `other_model_B` specific-rival contrast — the
  finer-grained version of the pooled `other_model_pooled` term in H1/H2/
  H3. This is where a Saraf-et-al.-style asymmetric-rival-label effect
  (e.g. one named model's label helping, another's hurting) would show
  up; deliberately kept out of the confirmatory family so collecting
  both rival labels for this purpose doesn't inflate H1/H2/H3's
  correction burden.
- `bug_flavor:author_label` — whether the label effect concentrates in
  particular flavors (e.g. `silent_failure`, `security_vulnerability`,
  `wrong_algorithm`) rather than appearing uniformly.
- ~~`severity_tier` main effects and its interactions with `author_label`~~ —
  **removed.** `severity_tier` is no longer a crossed factor (§1), and is
  near-collinear with `bug_flavor`, so neither a main effect nor an interaction
  is separately estimable. The wave-1 severity moderation reported in
  `analysis/` was in part measuring flavour composition. Any severity contrast
  is observational and must be reported as such.
- All NLP-derived measures (lexicon rates, blind-classifier-coded
  categories) regressed on the same confirmatory contrasts — treated as
  exploratory in this first wave specifically because the coding
  scheme itself is unvalidated; promote to confirmatory in a later wave
  only after checking inter-rater/inter-classifier reliability on a
  held-out subset.
- `authorship_belief_coded` as a moderator on any of the above. It is
  post-treatment, so this is descriptive only and never used to subset the
  §6.1 tests (§3).
- **Label effect by generator.** The §6.1 contrasts estimated within each
  bank, then compared across banks: does the label effect depend on who
  wrote the code? Within-item estimates only (§1b).
- **Source match.** Where a judge's family also generated a bank: does that
  judge's response to its own family's label differ between code its family
  wrote and code another family wrote, relative to the same code under the
  other labels? Two judges qualify, symmetrically: GPT-5 (GPT-5 bank vs.
  Gemini bank) and Gemini 2.5 Pro (Gemini bank vs. GPT-5 bank). Each is the
  same model that generated its own-family bank. Claude Sonnet 5 sees no
  Claude-generated code in wave 2 and is the no-own-code comparison.
- **Authorship belief, two analyses from the same question** (added
  2026-09-27). The six-label crossing already collects both; they answer
  different questions and are reported separately, never pooled.
  - *Source detection — `none` cells only.* With no author sentence, compare
    the coded family with `generator_family`. The test is whether the guess
    moves with the code, not raw accuracy: P(says gpt | gpt bank) vs.
    P(says gpt | gemini bank), within judge. A judge that always names one
    family scores ~50% against two banks while detecting nothing. Run on
    buggy and clean items separately; the clean twins show whether
    recognition rests on general style or on how a generator plants bugs.
  - *Label-following — labelled cells.* Whether the coded family matches
    the family named in the label. Report true-label and false-label cells
    separately (`label_is_true`). A true label cannot separate recognition
    from acceptance, since both predict the same answer. On a false label,
    naming the labelled family is *consistent with* following the label and
    naming the generator is *consistent with* recognizing it despite the
    label. Neither is established by that answer alone: a guess can also
    reflect the judge's habitual model-name preferences or weak evidence.
    Whether a judge tracks source in these items at all is shown by the
    source-detection analysis above, and the false-label reading is only
    interpreted in its light.
- **Clean-code control** (own Holm family): false-positive rate
  `bug_detected ~ author_label` on clean items, logistic, clustered by
  item; detection rate on buggy items, same model. If detection varies by
  label, re-run H1–H3 on the detected subset as a robustness check.
  False positives use every eligible twin; buggy-vs-clean paired
  comparisons use complete pairs with a minimal twin (§1c).
- Any three-way interaction involving explored factors, e.g.
  `author_label:bug_flavor:generator_family`. None involving
  `severity_tier`, for the reason given above.

### 6.3 Rival pooling and balance

Every item is shown under all six labels (full crossing, §7), so every label
co-occurs with every item and flavour by construction. Which rival fills A
and B rotates across items (`rival_model_pool.json`), so each named rival is
spread over items rather than tied to one. Pooling A and B in the
confirmatory contrasts means their balance matters only for the exploratory
A-vs-B contrast in §6.2.

### 6.4 Reporting convention

State the confirmatory/exploratory split and the exact H1–H3 wording in
the writeup before results, exactly as this section does now — so
nothing here can be silently reclassified after seeing which tests
came back significant.

- **Nulls come with intervals.** A non-significant contrast is reported with
  its interval (from the wild cluster bootstrap), so readers can see which
  effect sizes are ruled out. It is not described as evidence of no effect,
  and not as an equivalence test, since none was preregistered.
- **Self vs. rival.** In wave 1 it was not tested: §6.1 compares each label
  with `none`, and comparing the `self` and `other_model_pooled` estimates
  with each other is descriptive only. In wave 2 it is tested directly as
  H4 (§6.5).
- **Post hoc item exclusions are sensitivity checks.** Results on a subset
  chosen after collection are reported as such, not as the result. Wave 1's
  28-item rerun is one: it drops the 13 items rated `drop` (9) or
  `not_a_bug` (4) and keeps the 7 `wrong_tier` and 2 `wrong_flavor` items.
  It is not the set that passed review; only 13 items passed outright.
- **Wave 1** is reported as the preregistered initial test that exposed a
  materials problem: 13 of 41 items passed review after collection, all code
  was Claude-generated, and the authorship answers are uncoded. Its locked
  result stands; what it can say about judgments of contract-defined bugs is
  limited. The rebuilt, reviewed banks are the basis for the stronger test.

### 6.5 Wave 2 plan (added 2026-09-27, before wave-2 collection)

§6.1 was locked for wave 1 and is left as it stands. This section is the
prospective plan for wave 2, written after seeing wave 1 and declared as
such.

**Sample.** All 124 items of both generator banks (§1c), buggy items, two
repeats, elicitation prompt version `2026-09-27-v2`, less the primary
aim-visibility exclusions fixed in §1c ("No freeze"). WCB clustered by
`item_id`, run per (judge_family, judge_tuning) cell as in §6.1.

**H1–H3 (replication).** The §6.1 contrasts unchanged: `self`,
`human_developer`, `generic_ai`, `other_model_pooled` vs. `none`, on blame
(H1), intentionality (H2) and ability-vs-diligence (H3), Holm across the four
contrasts within each hypothesis × judge cell. Two-sided. No directional
prediction is carried over for H3: wave 1 moved `self` toward the
diligence-lapse end, opposite to the actor-observer prediction in §6.1.

**H4 (rival vs. self).** The direct test of the core question: pooled rival
vs. `self`, estimated in the same model as H1–H3 with the contrast
`other_model_pooled − self`. Two-sided; wave 1's point estimates leaned
slightly the other way (Opus blame: `self` +0.34, rival +0.21 vs. `none`),
so no one-sided test is justified. Three outcomes, each its own family:

- **H4a** blame
- **H4b** intentionality
- **H4c** ability-vs-diligence

One contrast per family per judge cell, so there is no Holm step inside a
family, and H1–H3 keep their four-contrast families unchanged.

Implemented as `run_confirmatory.py --plan 6.5` (committed before wave-2
collection). The model is `design_matrix` reparameterised so one coefficient
is rival minus `self` (`frame.rival_vs_self_matrix`), so the fit is
identical to H1–H3's and the same restricted wild cluster bootstrap tests
it. `--plan 6.1` (the default) reproduces the locked wave-1 output unchanged.

**Sensitivity (prespecified).** H1–H4 rerun (a) also without items flagged
borderline on aim visibility, and (b) on the full bank with no exclusions
(§1c). Both reported alongside the primary result, not in place of it.

**Everything else** in §6.2 stays exploratory, including label effects by
generator and source match.

## 7. Open decisions

- ~~**Judge families.**~~ — **Resolved 2026-09-27**: one judge per family,
  Claude Sonnet 5, GPT-5 and Gemini 2.5 Pro (via OpenRouter). Three families
  is the floor for a general LLM-judging-LLM claim. Gemini is already in the
  rival pool, so no rotation changes, and as the Gemini bank's generator it
  gives a second, symmetric source-match condition (§6.2). Opus 5 was
  dropped: it was about half the wave-2 cost, and a second Claude adds a
  within-family check but no family. That loses the per-judge replication
  of Opus's wave-1 results (e.g. its ability-vs-diligence `self` shift of
  +1.24), and `judge_tuning` no longer varies within a family. DeepSeek was
  ruled out because it did the contract-blind review; Llama because the
  newest available is April 2025.
- ~~**`copy_paste_residue`.** Whether inert residue is a defect the battery
  can sensibly ask about~~ — **Resolved 2026-09-27**: no. The bank is
  behavioural, so the flavour is narrowed to residue with an observable
  effect (§1a); inert items are excluded and not replaced; the flavour is
  reported descriptively.

- ~~Whether `other_model_A/B` should be fixed named models across the
  whole item bank or resolved per-judge~~ — **Resolved**: a fixed pool of
  named rival models, with `other_model_A`/`other_model_B` resolved per
  judge/item by excluding whichever model is the current judge and
  rotating assignment across items. See `docs/config-schema.md`
  (`rival_model_pool.json`) for the exact resolution rule.
- ~~Whether q_intentionality/q_explanation/q_blame should all run on
  every item for every label cell, or whether a partial (Latin-square)
  design is needed~~ — **Resolved**: full crossing. `severity_tier` and
  `bug_flavor` are properties of an item, not crossed within it. Wave 1:
  6 labels × 4 questions = 24 calls per item; 41 items × 3 judges came to
  2,952 calls and $60.37. Wave 2: 6 labels × 5 questions = 30 calls per
  buggy item and 6 × 2 = 12 per clean twin; 124 items give 5,208 calls per
  judge per repeat, 31,248 across 3 judges × 2 repeats, estimated at ~$575.
  No reduction needed.
- Number and diversity of items per `bug_flavor` needed for the
  exploratory `bug_flavor:author_label` interaction. **Still open**: wave 2
  has 31 (aim × flavour) cells, two samples each, per bank, with 4–6 aims
  per flavour (`known_trap` has 3). Adequate for the main effects;
  interactions by flavour remain underpowered.
