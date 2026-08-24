# Authorship-Label Folk-Psychology Ascription: Prompt Template

**Status:** draft template for elicitation, pending pilot. Designed to slot
into the existing `analyze_sign_wcb.py`-style pipeline (WCB clustering by
item, Holm correction per family/tuning/question) with `author_label_c` and
`purpose_valence_c` replacing `sign_c` as the primary manipulated factors.
No Knobe-style scripted mental-state clause — folk-psych ascriptions
(intent, blame, ability-vs-diligence) are elicited from bare code + label,
not seeded.

---

## 1. Manipulated factors

| Factor | Levels | Notes |
|---|---|---|
| `author_label` | `none` (baseline), `self`, `other_model_A`, `other_model_B`, `generic_ai`, `human_developer` | `self` is resolved per judge model at elicitation time (e.g. judge=llama → label="Llama"). `other_model_A/B` should be named commercial models distinct from the judge, rotated so no single rival model is confounded with a specific bug/item. |
| `stated_aim` | fixed per item, not manipulated | Plain functional description of what the code is supposed to do (e.g. "validate a password-reset token before allowing a password change," "sort a list of files by extension"). Held constant across all other-factor cells for a given item; exists to give `bug_aim_relation` something to be defined against. |
| `bug_aim_relation` | `aim_defeating`, `aim_orthogonal` | Does the bug undermine exactly what the function was stated to do, or is it incidental to that stated purpose? Independent of `severity_tier` (severity = technical consequence; aim_relation = relationship to stated purpose) and independent of `bug_flavor` (any flavor can in principle be either relation — see §1a). Constructed independently per item (not as matched pairs — see §1a): not every flavor naturally supports both relations for an arbitrary stated aim, and forcing a matched sibling for every item was judged not worth the construction cost. Analyzed as a between-item comparison, clustered by `item_id`. |
| `severity_tier` | `trivial`, `significant` | Property of the planted bug itself (technical consequence), held constant across all label/aim-relation cells for a given item. |
| `bug_flavor` | `missing_edge_case`, `logic_error`, `security_vulnerability`, `silent_failure` (core); `copy_paste_residue`, `known_trap` (exploratory, optional) | Not a primary test factor, but should be balanced across items so competence/carelessness/malice narratives have room to differ; worth exploratory `bug_flavor:author_label` and `bug_flavor:bug_aim_relation` interactions. See §1a for definitions, examples, and predicted folk-psych profile per flavor. |

Everything else — the actual code, the actual bug, prompt scaffolding
outside the label/purpose slots — is held byte-identical across cells
within an item. Only the label and purpose sentences vary.

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
| `copy_paste_residue` | Leftover debug print; a variable copy-pasted from a similar function that doesn't match context; dead/commented-out code. | Uniquely diagnostic of carelessness over competence — a stray `print("here")` rarely reads as a skill gap. Cleanest diligence-lapse prototype, complementing `silent_failure`. |
| `known_trap` | Mutable default argument (Python); floating-point equality comparison; integer overflow where easy to forget. | Predicted lowest blame across the board regardless of label — strong "even experts fall into this" folk narrative. Second low-signal contrast to `missing_edge_case`. Risk: judge models may not uniformly recognize a given trap as "classic," which is itself a confound — treat as lower-priority than the other five. |

Recommended allocation: use `missing_edge_case`, `logic_error`,
`security_vulnerability`, `silent_failure` for the primary factorial
(spans ambiguous/diagnostic and competence/diligence/norm-violation
contrasts). Add `copy_paste_residue` and `known_trap` only if the item
bank can support the extra cells without underpowering the core set.

**Constructing `bug_aim_relation` instances.** `bug_aim_relation` is a
separate crossed factor, not a property of `bug_flavor` — any of the four
core flavors can in principle be either aim-defeating or aim-orthogonal
depending on where the bug sits relative to the function's stated
purpose, so it answers a different question (relationship to purpose)
than `bug_flavor` does (type of technical mistake). Each item is
constructed independently: for a given `stated_aim`/`bug_flavor`/
`severity_tier`, decide where the bug sits and label the item
accordingly — no requirement to also construct a matched sibling item
with the opposite `bug_aim_relation`. This was a deliberate simplification:
not every flavor naturally supports both relations for an arbitrary
stated aim (a `security_vulnerability` that's genuinely orthogonal to an
aim like "sort files by extension" is a stretch to write convincingly),
and forcing a matched pair for every item raised the construction cost
without a proportional gain, given `bug_aim_relation` is analyzed
between-item (clustered by `item_id`) rather than as a within-pair
repeated measure. Example (`silent_failure`, `STATED_AIM` = "validate a
password-reset token before allowing a password change"):

- `aim_defeating`: the token-expiry check's exception is swallowed,
  silently allowing an expired token through — the exact thing the
  function was supposed to prevent.
- `aim_orthogonal`: an unrelated logging call's exception is swallowed
  elsewhere in the same function; the token validation itself is
  correct.

Both illustrate the same `bug_flavor`/`severity_tier`, but there is no
requirement that both be constructed from the same specific item.

## 2. Prompt template (elicitation turn)

```
{AIM_SENTENCE}

{AUTHOR_SENTENCE}

{CODE_BLOCK}

Review this code.
```

### `AIM_SENTENCE`

One fixed sentence per item, stating the plain functional purpose —
not manipulated, exists to give `bug_aim_relation` (§1a) something to
be defined against:

> "This function is supposed to {STATED_AIM, e.g. 'validate a
> password-reset token before allowing a password change' / 'sort a
> list of files by extension'}."

`STATED_AIM` is fixed per item and identical across every
`author_label` cell for that item. Whether the bug in `CODE_BLOCK`
defeats or is orthogonal to this stated aim is what `bug_aim_relation`
encodes — see §1a for the matched-pair construction method.

### `AUTHOR_SENTENCE` by level

| `author_label` | Sentence |
|---|---|
| `none` | *(omit AUTHOR_SENTENCE entirely — no authorship claim at all)* |
| `self` | "This function was written by {JUDGE_MODEL_DISPLAY_NAME}." |
| `other_model_A` | "This function was written by {RIVAL_MODEL_A_DISPLAY_NAME}." |
| `other_model_B` | "This function was written by {RIVAL_MODEL_B_DISPLAY_NAME}." |
| `generic_ai` | "This function was written by an AI system." |
| `human_developer` | "This function was written by a human developer." |

`CODE_BLOCK` is the fixed buggy snippet for that item/severity
tier/aim-relation cell, identical across every `author_label` cell.

## 3. Question battery

Ask as **separate elicitations per question** (fresh context per
question, same code+label+purpose preamble repeated) rather than a
single multi-question turn, to avoid answers to later questions being
anchored on earlier ones. Rotate which subset of questions is asked per
item if full coverage per item is too costly, but keep `q_reasoning` and
`q_authorship_belief` universal — those are the two you need on every
item regardless of what else is dropped.

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

**q_authorship_belief** (final, manipulation check — separate
elicitation, asked once per item after all judgment questions for that
item are complete)
> "Independent of anything you were told above, who do you think most
> likely actually wrote this code?"
>
> Free response; code afterward into a small fixed set (matches stated
> label / names a different specific model / says "an AI" generically /
> says "a human" generically / declines to guess) for use as a
> covariate — see §5.

## 4. Response schema (per elicitation row)

```
item_id, judge_family, judge_tuning, author_label,
bug_aim_relation, severity_tier, bug_flavor, question_type,
scale_response, reasoning_text, authorship_belief_raw,
authorship_belief_coded
```

`question_type` ∈ {q_intentionality, q_explanation, q_blame,
q_authorship_belief}. `authorship_belief_*` fields are null except on
the q_authorship_belief row for that item.

## 5. NLP coding pass on `reasoning_text`

Three tiers, cheapest first, same as discussed:

1. **Lexicon coding** (per reasoning_text): counts/rates for
   disposition-fault terms ("careless," "sloppy," "should have"),
   situational-mitigating terms ("understandable," "easy to miss," "edge
   case"), competence-framing terms ("inexperienced," "skilled,"
   "solid grasp"), intent terms ("deliberately," "accidental,"
   "unintentional").
2. **Blind classifier pass**: separate model, blind to
   `author_label`/`bug_aim_relation`, codes each reasoning_text for (a)
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

Four confirmatory hypotheses, each its own correction family per
(family, tuning) cell — i.e. 4 hypotheses × however many (family,
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
- **H3 — label × aim-relation interaction on blame**: `q_blame ~
  author_label_c * bug_aim_relation_c`, testing whether the label
  effect from H1 grows, shrinks, or holds when the bug defeats the
  stated aim vs. is incidental to it. This is the test of whether label
  bias survives a more diagnostic bug, not just an ambiguous one. WCB
  clustered by item_id (aim-defeating and aim-orthogonal items are
  constructed independently per §1a, not as matched pairs, so this is a
  between-item comparison, not a within-pair one).
- **H4 — label main effect on the ability-vs-diligence explanation
  item** (`q_explanation`): the actor-observer prediction specifically
  — does `self` skew toward the ability-gap end and `other_model`/
  `human_developer` toward the diligence-lapse end for otherwise
  identical bugs.

These four are the only tests that get to claim "significant, as
pre-registered" in a final writeup. Everything else below is reported
as suggestive/exploratory, however clean it looks.

### 6.2 Exploratory set (not correction-shielded together with 6.1;
its own separate Holm groups, or reported uncorrected with that
explicitly stated)

- `other_model_A` vs. `other_model_B` specific-rival contrast — the
  finer-grained version of the pooled `other_model_pooled` term in H1/H2/
  H4. This is where a Saraf-et-al.-style asymmetric-rival-label effect
  (e.g. one named model's label helping, another's hurting) would show
  up; deliberately kept out of the confirmatory family so collecting
  both rival labels for this purpose doesn't inflate H1/H2/H4's
  correction burden.
- `bug_flavor:author_label` and `bug_flavor:bug_aim_relation` —
  whether the aim-defeating bump or the label effect concentrates in
  particular flavors (e.g. `silent_failure`, `security_vulnerability`)
  rather than appearing uniformly.
- `severity_tier` main effects and its interactions with `author_label`
  — useful diagnostics, not part of the headline claim.
- All NLP-derived measures (lexicon rates, blind-classifier-coded
  categories) regressed on the same confirmatory contrasts — treated as
  exploratory in this first wave specifically because the coding
  scheme itself is unvalidated; promote to confirmatory in a later wave
  only after checking inter-rater/inter-classifier reliability on a
  held-out subset.
- `authorship_belief_coded` as a moderator on any of the above.
- Any three-way interaction (`author_label:bug_aim_relation:bug_flavor`,
  etc.).

### 6.3 Why the pooling in 6.1 also helps the streamlining question

Pooling `other_model_A`/`other_model_B` into one confirmatory contrast
means the balanced-rotation label design (rotating a subset of the 6
labels per item so every label co-occurs with every flavor/severity
somewhere in the bank) doesn't need to guarantee A and B are evenly
represented *within the confirmatory test itself* — that guarantee is
only needed for the exploratory A-vs-B contrast in 6.2, which can
tolerate a noisier, best-effort balance since it isn't
significance-tested against the same bar as H1–H4.

### 6.4 Reporting convention

State the confirmatory/exploratory split and the exact H1–H4 wording in
the writeup before results, exactly as this section does now — so
nothing here can be silently reclassified after seeing which tests
came back significant.

## 7. Open decisions before piloting

- ~~Whether `other_model_A/B` should be fixed named models across the
  whole item bank or resolved per-judge~~ — **Resolved**: a fixed pool of
  named rival models, with `other_model_A`/`other_model_B` resolved per
  judge/item by excluding whichever model is the current judge and
  rotating assignment across items. See `docs/config-schema.md`
  (`rival_model_pool.json`) for the exact resolution rule.
- Whether q_intentionality/q_explanation/q_blame should all run on
  every item for every label/aim-relation cell, or whether a partial
  (Latin-square) design is needed to keep elicitation cost tractable —
  the design is `author_label` (6) × `bug_aim_relation` (2) ×
  `severity_tier` (2) × `bug_flavor` (4 core), i.e. 96 cells per item
  before even multiplying by question type; full crossing on every item
  is likely not affordable, so decide early whether to (a) run the full
  cross on a small number of items, or (b) run a reduced label set (e.g.
  drop one of `other_model_A/B` or `human_developer`) on more items.
- Number and diversity of `bug_flavor` items needed per severity tier to
  support the exploratory `bug_flavor:author_label` and
  `bug_flavor:bug_aim_relation` interactions without under-powering the
  primary tests.
- ~~Whether `bug_aim_relation` should be analyzed as a within-pair
  repeated measure or treated as fully between-item~~ — **Resolved**:
  fully between-item, clustered by `item_id` (see §1a, §6.1 H3).
