# Design: Corpus-grounded item generation and a behavioural severity rubric

**Status:** draft, pending user approval. Amends `docs/generation-prompt.md`,
`docs/design.md` §1, and `docs/config-schema.md`.

A first-pass human review of all 41 wave-1 items (`analysis/item_verdicts-6.csv`) passed 13.
Nine were marked `drop`, four `not_a_bug`, seven `wrong_tier`, two `wrong_flavor`. Two items
(`add_note__known_trap__{trivial,significant}`) are byte-identical code carrying different
severity labels.

This is not a generation-quality problem to be fixed with a better prompt. It has two
structural causes, and this spec addresses both.

**Cause 1 — the documented source corpora were never used.** `docs/generation-prompt.md`
already specifies HumanEval/MBPP as ~1,100 clean base functions to mutate, Bandit's
`examples/` for `security_vulnerability`/`silent_failure`, and QuixBugs as a realism check,
with a full licence/attribution table. `scripts/generate_items.py` uses none of it: it passes
a flavour definition string to a model and asks it to invent a function. The corpora are
cited as grounding and then skipped. Every accepted item's ground truth is the generator's
own `rationale`, which `generation-prompt.md` already calls "a screening aid only, not
verified ground truth."

**Cause 2 — `severity_tier` is defined in terms the artefact cannot settle.** The current
definition is about blast radius: persistence, cascading effects, cross-user impact. Those
are deployment-context properties. A 3–25 line self-contained function has no deployment
context, so for many (aim, flavour) pairs the `significant` cell is unrealisable. The
generator complied the only way it could — same code, different prose.

## 1. Source label is not study label

The governing rule for everything below:

> A source's own label establishes that a snippet instantiates a **pattern**. It does not
> establish that the adapted item has the **behavioural effect** our flavour definition
> requires. Those are separate claims and must be separately recorded.

Wave-1 item 36 is the worked example: a real swallowed exception (Bandit's `try_except_pass`
pattern) that raises `UnboundLocalError` rather than silently returning a wrong result. The
pattern label was right; the flavour assignment was wrong.

`docs/generation-prompt.md` currently elides this, treating a Bandit category as sufficient
for flavour assignment. That text is amended per §7.

| Source | What its label establishes | What we must still judge |
|---|---|---|
| CWE / Bandit `examples/` | A specific security or error-handling pattern | Whether this snippet has the claimed effect, and whether the twin removes it |
| QuixBugs | The program contains a documented bug and has a correction | Whether that bug fits our `missing_edge_case` / `logic_error` / `wrong_algorithm` split |
| HumanEval / MBPP | Task, expected behaviour, reference solution, tests | The flavour of a bug *we* introduce — the source cannot label a mutation it never contained |
| Practitioner gotcha corpora | A recognisable pattern (mutable default, dead code) | Whether the pattern causes a defect in this item |

## 2. Source priority, ordered by how much verification they mechanise

HumanEval/MBPP is not one source among four. It is the only one that ships an executable
specification, and that is what converts our two worst defect classes from human judgement
into CI.

1. **HumanEval / MBPP + controlled mutation — primary.** Each problem carries a task
   description, a verified reference solution, and a test suite. The reference solution *is*
   a verified clean twin. The tests *are* the contract.
2. **Bandit `examples/` + CWE — flavour seeds only**, for `security_vulnerability` and
   `silent_failure`, which HumanEval-style pure functions do not exercise.
3. **QuixBugs — realism check.** Sanity-check that injected bugs read as comparable to real
   single-line defects. Not a primary item source.
4. **Hand construction** — `copy_paste_residue`, `known_trap`, `wrong_algorithm` only, per
   the existing lower-priority status in `design.md` §1a.

Against the wave-1 review, executable verification mechanically catches items 2, 6, 12, 18,
21 and the 16/17 pair — six of the thirteen removals, all of them "the defect does not
actually diverge from the spec" or "the spec does not settle the question."

## 3. Generation pipeline

`scripts/generate_items.py` gains a corpus-backed path alongside the existing definition-only
path (retained for the hand-constructed flavours).

1. **Load base problems.** `scripts/corpus/humaneval.py`, `scripts/corpus/mbpp.py` — fetch
   and normalise to `{source, source_id, prompt_text, reference_solution, tests}`.
2. **Mutate.** `scripts/corpus/mutate.py` applies one operator per candidate: ROR, COR, AOR,
   boundary shift, statement deletion — the operators already grounding the
   `logic_error`/`missing_edge_case` rubric in `config/bug_flavor.json`.
3. **Verify behaviour by execution.** Run the aim's tests (§4b) against both versions.
   This needs a subprocess and a timeout, not a security sandbox: mutating a loop condition
   readily produces a non-terminating function, and that must not take the runner down. The
   upstream HumanEval harness sandboxes because it executes free-form model output; here the
   input is corpus code with AST-level operator swaps applied, which cannot acquire file or
   network access the original did not have. Accept a candidate only if:
   - the reference solution **passes** all tests (clean twin verified), and
   - the mutant **fails at least one** test (the defect is real, not cosmetic).
   A mutant that passes everything is an equivalent mutant and is discarded — this is exactly
   the wave-1 `not_a_bug` class.
4. **Assign severity from test outcomes** (§4).
5. **Record provenance** (§5).
6. **Blind second classification** (§6).

Step 3 is the load-bearing change. It replaces "the generator says this is a bug" with "the
reference test suite disagrees with this code."

## 4. `severity_tier` redefined behaviourally

Replaces the CVSS-derived blast-radius definitions in `config/severity_tier.json`.

> **Trivial** — the defect leaves the function's primary result correct across the input
> range the stated aim requires it to handle. It causes a cosmetic issue, unnecessary work,
> or a failure confined to a narrow boundary or degenerate input.
>
> **Significant** — the defect makes the primary result wrong across an ordinary part of the
> input range the stated aim requires it to handle, or causes incorrect behaviour to persist
> across calls.

This is decidable from code plus stated aim alone, which the old definition was not.

**Note on the phrasing.** An earlier draft of this rubric read "ordinary *valid* inputs" and
carried a separate "defeats a required check" clause for security items. Both are dropped in
favour of "the input range the stated aim requires it to handle," because the carve-out is
then unnecessary and the rule stays a single principle. A token validator's stated aim is
*"validate a password-reset token before allowing a password change"* — so a wrong-but-
well-formed token is squarely inside the range it must handle, not a boundary case. A missing
check returns `True` where the aim requires `False`: wrong primary result, ordinary input,
`significant`, with no special-casing. Keeping "valid" would have mis-sorted every security
item as trivial, since authorised callers still get correct results.

**Operationalisation.** Each base problem's tests are tagged once, per test, as `typical` or
`boundary`. Then:

- mutant fails ≥1 `typical` test → `significant`
- mutant fails only `boundary` tests → `trivial`
- mutant fails nothing → discarded as equivalent (§3.3)

Where tags are unavailable, fall back to the share of the suite failed, with the threshold
recorded in the item's provenance. The tag-based rule is primary because it tracks the
definition; the ratio is a documented approximation.

**Consistency check.** Under this rubric `add_note`'s mutable default is *incorrect behaviour
persisting across calls* — unambiguously `significant`, with no trivial variant. Combined with
§8's gating, the identical-code pair becomes unconstructible rather than merely wrong.

## 4a. `severity_tier` demoted from manipulated factor to recorded covariate

**Decision: `severity_tier` is no longer a crossed experimental factor.** It stays on every
item as a recorded field, assigned from §4's rubric, and is available for post-hoc
exploration — but it is not manipulated, and cells are enumerated as (aim × flavour) only.

The reason is that §4's severity rubric and §6a's flavour rubric, applied consistently, make
severity a near-deterministic function of flavour. Five of seven flavours admit exactly one
tier:

| Flavour | Permitted tier | Why the other is empty |
|---|---|---|
| `missing_edge_case` | `trivial` | Flavour requires normal inputs to work; `significant` requires them not to |
| `logic_error` | `significant` | Flavour requires ordinary inputs wrong |
| `wrong_algorithm` | `significant` | Computing a different quantity is not a boundary failure |
| `security_vulnerability` | `significant` | A defeated check is an ordinary input handled wrongly |
| `copy_paste_residue` | `trivial` | Behaviourally inert code cannot make ordinary results wrong |
| `known_trap` | either | `significant` iff the trap persists across calls |
| `silent_failure` | either | `significant` iff it conceals a wrong primary result |

This is not an artefact of the new rubrics. `missing_edge_case × significant` was never
constructible — "normal inputs work, a boundary fails" and "ordinary inputs are wrong" are
direct negations — and both wave-1 items in that cell were flagged in review. The old
blast-radius definition concealed the contradiction by making severity a deployment-context
property that the artefact could not settle either way.

Keeping a factor that is collinear with another factor would mean `severity_tier` main effects
and `severity_tier:author_label` interactions are not separately estimable from `bug_flavor`.
The wave-1 severity moderation reported in `analysis/` (Opus +1.38 significant vs +1.18
trivial) was in part measuring flavour composition.

Consequences:

- `docs/design.md` §1 — `severity_tier` moves out of the manipulated-factors table into a
  recorded-properties note, alongside `stated_aim`.
- `docs/design.md` §6.2 — the `severity_tier` main effect and its `author_label` interaction
  are removed as planned analyses. Any severity contrast reported later is **observational**,
  confounded with flavour, and must be labelled as such.
- §6.1 is untouched. H1–H3 are label contrasts within item; they never used severity.
- Cell enumeration becomes (aim × flavour), 28 pairs rather than 41 triples. **This buys back
  power**: the freed budget goes to `samples_per_cell`, so 28 cells at 3 samples is 84 items
  against wave 1's 41, on the same factor structure.

If a later exploratory pass finds something that makes severity worth manipulating again, the
field is already recorded on every item and the rubric is already written; reinstating it means
re-crossing the factor, not reconstructing the definition.

## 4b. Per-aim contract and executable tests

The wave-1 review's hardest cases were not mislabelled items. They were items where *correct*
was undefined: 16/17 (what should an empty list return?), 12 ("neither the stated aim nor code
defines the intended prices"), 38 (should an invalid token type be reported separately from a
token that fails validation?). A one-sentence `stated_aim` does not settle these, so the
generator settled them — differently each time. The two `average` items' twins return `None`
and `0` respectively for the same situation.

The contract belongs to the **aim**, not the item: it should not vary by which bug was
planted. `config/stated_aims.json` gains a `contract` field, and executable assertions live
per aim in `config/contracts/{aim_id}.py`.

```json
{"id": "compute_average",
 "text": "Compute the average of a list of numbers.",
 "contract": "Returns the arithmetic mean. Returns None for an empty list.",
 "flavors": {"missing_edge_case": {"severity_tiers": ["trivial"]},
             "wrong_algorithm":   {"severity_tiers": ["significant"]}}}
```

`contract` is prose, and is injected into the generation prompt (§7) so the generator is told
what correct means rather than inventing it. `config/contracts/{aim_id}.py` holds the
assertions, each tagged `typical` or `boundary` per §4:

```python
CASES = [
    ("typical",  "assert calculate_average([1, 2, 3]) == 2"),
    ("typical",  "assert calculate_average([10, 20]) == 15"),
    ("boundary", "assert calculate_average([]) is None"),
]
```

For corpus-derived items these come from the source suite (HumanEval and MBPP ship tests).
For hand-constructed items — the security, silent-failure and gotcha flavours — they are
written by hand, roughly five lines per aim. That is the whole unlock: a hand-written test is
the *same artefact* as the missing contract, so one cheap addition fixes the undefined-correct
problem, the equivalent-mutant problem and severity assignment at once, for every flavour.

Items never carry tests themselves. They carry outcomes, in `provenance` (§5).

## 5. Provenance metadata

`docs/generation-prompt.md` flags this as *"not yet specified — see Open Items."* Specified
here; required on every corpus-derived item.

```json
"provenance": {
  "source": "humaneval",
  "source_id": "HumanEval/23",
  "source_label": null,
  "source_license": "MIT",
  "mutation_operator": "ROR",
  "modifications": "renamed function and parameters; removed docstring",
  "tests_passed_by_twin": 8,
  "tests_failed_by_item": 3,
  "severity_basis": "typical_test_failure"
}
```

`source_label` carries the source's *own* category where it has one (a Bandit CWE id, for
example) and stays `null` where the source labels nothing — which is the common case for
mutated HumanEval, and is the §1 distinction made machine-readable. Hand-constructed items
carry `"source": "hand"` and a free-text `modifications`.

Attribution for any public release of the item bank is assembled from these records against
the licence table already in `generation-prompt.md`.

## 6. Blind second classification

New, and not covered by `design.md` §5 (which blind-codes `reasoning_text`, not items).

Every item is classified for `bug_flavor` and `severity_tier` by a second coder who sees the
code, the stated aim, and the flavour/severity definitions — and does **not** see the assigned
flavour, the assigned tier, the generator rationale, or the provenance record. Disagreements
are recorded, not silently resolved. Items that no coder can place are kept visible as
unmappable rather than forced into a category.

If the second coder is a model rather than a person, it must be from a different family than
any of the three judges in `config/judge_models.json`, and the limitation is stated
explicitly: a model is being used to label items for a study of model judgement. Different
task, different role, but it belongs in the write-up.

Agreement rate is reported. Sustained disagreement on a flavour is evidence about the
taxonomy, not only about the items — see §9.

## 6a. Flavour coding rubric

The rubric the blind coders in §6 apply. Each exclusion is drawn from a specific wave-1
failure rather than from the taxonomy in the abstract, which is why it discriminates: applied
back to `analysis/item_verdicts-6.csv` it reproduces the reviewer's call on every contested
item (2, 6, 16/17, 18, 23, 36, 38).

| Flavour | Include when… | Exclude when… |
|---|---|---|
| **missing_edge_case** | Normal inputs work; a specific valid boundary or degenerate input fails because a necessary case is absent. | The alleged boundary already works, or handling it requires an unstated input contract. |
| **logic_error** | The approach addresses the right task, but a wrong condition, operator, or control-flow step gives wrong results for ordinary inputs. | Only a narrow boundary fails, or the code carries out a different task altogether. |
| **security_vulnerability** | A concrete trust boundary is crossed: untrusted input can alter a query, an unauthorised caller passes a check, or a secret is exposed. Name the specific CWE and the behaviour. | The code merely looks security-related, or the alleged bypass returns only data the caller is already authorised to see. |
| **silent_failure** | The code detects an error and then returns or continues as though processing succeeded, without exposing that failure to the caller. | The exception escapes, or a subsequent error makes the failure visible. |
| **copy_paste_residue** | A leftover line or name is visibly inconsistent with this function's purpose and has a specified effect, even if only unwanted output. | "It was copied" is inferred solely from a generic debug print or unused variable with no distinctive prior context. |
| **known_trap** | A documented language behaviour produces a demonstrably wrong result under a specified call sequence. | The pattern exists but causes no incorrect behaviour. |
| **unmappable** | No row above fits without straining it. | — |

`unmappable` is a required option, not a fallback of last resort. Without it coders force-fit,
and §6's instruction to keep disagreements visible cannot be honoured. An item coded
`unmappable` by either coder is excluded from the bank and recorded.

**The rubric derives much of §8's gating.** Read against §4's severity rubric, several
(flavour × tier) pairs are near-contradictory by construction:

| Pair | Why |
|---|---|
| `missing_edge_case` × `significant` | The flavour requires normal inputs to work; the tier requires them not to |
| `logic_error` × `trivial` | The flavour requires ordinary inputs to be wrong; the tier requires them right |
| `wrong_algorithm` × `trivial` | Consistently computing a different thing is not a boundary failure |
| `copy_paste_residue` × `significant` | Behaviourally inert code cannot make ordinary results wrong |

Wave 1 contains two `missing_edge_case` × `significant` items, and both were flagged in
review — that combination was hard to place because it is close to a contradiction. The
exception in each case is cross-call persistence, which §4 admits as `significant`
independently of the input range. So the gating table in §8 should be *derived* from these two
rubrics and then hand-checked, not hand-written from scratch.

**`copy_paste_residue` is narrowed but not resolved.** Requiring "a specified effect, even if
only unwanted output" excludes wave-1 item 2, correctly. But unwanted output is not a
behavioural defect in the sense `q_intentionality`, `q_explanation` and `q_blame` presuppose,
and no test can fail on it. The open question from §9 stands: either the flavour goes, or the
battery's presupposition is relaxed for it.

## 7. Amendments to existing docs

- **`docs/generation-prompt.md`** — add §1's source-label/study-label rule and its table
  before the existing source-corpora section; correct the text that treats a Bandit category
  as sufficient for flavour assignment; replace the Open Items provenance placeholder with a
  pointer to §5.
- **`docs/design.md` §1** — `severity_tier` row cites the behavioural rubric (§4); `stated_aim`
  row notes that each aim now carries a `contract` (§4b).
- **`docs/config-schema.md`** — document the `provenance` object, the `contract` field and
  `config/contracts/`, the per-(aim × flavour) gating in §8, and the rewritten
  `severity_tier.json` definitions.
- **`scripts/vignette_gen/prompt.py`** — `TEMPLATE` gains a `CONTRACT:` slot below
  `STATED_AIM:`, and `build_prompt` passes `aim["contract"]`. This is the only prompt change;
  severity gating (§8) never reaches the prompt, since it governs which cells are enumerated
  rather than what any cell is told.
- **`config/bug_flavor.json`** — populate the `examples` arrays. Five of seven flavours have
  none, so the prompt's `Examples:` slot currently renders `(none documented)` for
  `security_vulnerability`, `silent_failure`, `copy_paste_residue`, `known_trap` and
  `wrong_algorithm`. The plumbing exists; only the data is missing.

## 8. Per-(aim × flavour) schema

Independent of corpus grounding, and required regardless.

`config/stated_aims.json` currently gates severity per **aim**:

```json
{"id": "add_note",
 "severity_tiers_supported": ["trivial", "significant"],
 "compatible_bug_flavors": ["known_trap"]}
```

Realisability is a property of (aim × flavour), not of the aim. `add_note` supports exactly
one flavour, and a mutable default in a three-line append function has exactly one severity.
The config asserted a `significant` variant existed; the generator was asked for one; it
produced the same code with new prose.

Schema becomes:

```json
{"id": "add_note",
 "flavors": {"known_trap": {"severity_tiers": ["significant"]}}}
```

`compatible_bug_flavors` and `severity_tiers_supported` are replaced by this single nested
map. `scripts/vignette_gen/config.py` validates it.

**With §4a's demotion, this map no longer gates enumeration.**
`scripts/vignette_gen/cells.py` enumerates (aim × flavour) pairs, and `severity_tiers` is read
as the tier or tiers a given pair is *expected* to produce — derived from §6a's flavour rubric
crossed with §4's severity rubric, then hand-checked per aim. Its two uses are:

1. **A review check.** An item whose reviewed severity falls outside its pair's expected set is
   a signal that either the item or the rubric is wrong. `add_note × known_trap` expects
   `["significant"]` only, so a `trivial` item under it is flagged rather than silently
   accepted — which is precisely the wave-1 failure.
2. **A reinstatement path.** If a later exploratory pass makes severity worth manipulating
   again (§4a), the pairs that genuinely support both tiers are already identified and
   enumeration can re-cross them without rebuilding the analysis.

Deriving the map from the two rubrics rather than writing it by hand means it encodes the same
distinctions the coders apply, instead of a parallel set of judgements that can drift. Of the
28 (aim × flavour) pairs, 22 are settled by the rubrics alone; the remaining six are all
`known_trap` or `silent_failure`, the two flavours §4a leaves genuinely variable.

## 9. Known limits

- **What limits flavour coverage is the corpus, not the method.** Mutation over HumanEval and
  MBPP reaches `missing_edge_case`, `logic_error` and `wrong_algorithm` directly, because those
  base functions are pure string/list/maths routines with no auth, IO or exception handling —
  there is nothing to mutate *into* a missing authorisation check. That is a property of the
  chosen corpus, not of mutation as a technique. The binding constraint is narrower: **does an
  executable spec exist for this item?** HumanEval ships one; for a Bandit-seeded auth item we
  write one (§4b), roughly five lines asserting an unauthorised caller is rejected. With that
  in place a deleted check fails a `typical` case and severity assignment works identically.
  All seven flavours are reachable; three arrive with tests already written, four need tests
  authored alongside the item.
- **`copy_paste_residue` may be incompatible with the question battery.** See §6a — the rubric
  narrows the flavour but does not resolve whether behaviourally inert code belongs in a
  battery whose questions presuppose a bug. Flagged, not resolved here.
- **Adaptation erodes the source label.** Our constraints — 3–25 lines, one self-contained
  function, no comments or docstrings, neutral names, byte-identical across label cells — mean
  corpus code must be reshaped. The more it is reshaped, the less the source label licenses.
  §5's `modifications` field exists so this is auditable rather than assumed.
- **The taxonomy itself is under test.** Forcing externally-sourced examples into seven
  flavours will expose which are study-specific groupings rather than categories any external
  benchmark recognises. A flavour that no source can be mapped onto, and that coders
  disagree about, is a finding.
- **Severity still requires tagged tests** for the primary rule. That tagging is one-time per
  base problem, but it is human judgement and does not disappear.

## 10. Testing

- Mutation operators: each produces a syntactically valid, behaviourally different function.
- Test runner: subprocess-isolated and timeout-bounded, so a non-terminating mutant is
  recorded as a failure rather than hanging the run; correctly reports pass/fail; equivalent
  mutants are detected and discarded.
- Contracts: every aim has a `contract` and a `config/contracts/{aim_id}.py`; every case is
  tagged `typical` or `boundary`; the reference/clean version passes all of them.
- Severity assignment: `typical`/`boundary` failure patterns map to the §4 rule; the ratio
  fallback is exercised.
- Config: the nested `flavors` map validates, rejects unknown flavours and tiers, and
  `enumerate_cells` emits only listed (aim, flavour, tier) triples — with `add_note` as a
  regression fixture producing no trivial cell.
- Provenance: required fields present on corpus items, `source_label` null where the source
  labels nothing.
- Existing `validate_code` constraints continue to hold on all corpus-derived items.

## Out of scope

- Regenerating the item bank. This specifies the machinery; the regeneration run and the
  decision about how many items to rebuild are separate.
- The generator-model confound (all wave-1 items came from `claude-sonnet-4.5`). Corpus
  grounding reduces its surface, since mutated corpus code is not model-authored prose, but
  crossing `generator_model` as a factor is its own decision.
- Any change to the elicitation battery or to `design.md` §6.1. The confirmatory contrasts
  stay locked.
