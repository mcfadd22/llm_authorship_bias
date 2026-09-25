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
3. **Verify behaviour by execution.** Run the reference tests against both versions in a
   subprocess with a timeout and no network. Accept a candidate only if:
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

## 7. Amendments to existing docs

- **`docs/generation-prompt.md`** — add §1's source-label/study-label rule and its table
  before the existing source-corpora section; correct the text that treats a Bandit category
  as sufficient for flavour assignment; replace the Open Items provenance placeholder with a
  pointer to §5.
- **`docs/design.md` §1** — `severity_tier` row cites the behavioural rubric (§4).
- **`docs/config-schema.md`** — document the `provenance` object, the per-(aim × flavour)
  gating in §8, and the rewritten `severity_tier.json` definitions.

## 8. Per-(aim × flavour) severity gating

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
map. `scripts/vignette_gen/config.py` validates it; `scripts/vignette_gen/cells.py`
enumerates (aim, flavour, tier) only where the tier is listed for that pair. Impossible cells
are never requested rather than requested and fudged.

## 9. Known limits

- **Flavour coverage.** Mutation over HumanEval/MBPP reaches `missing_edge_case`,
  `logic_error` and `wrong_algorithm` well. It does not reach `security_vulnerability` or
  `silent_failure`, since the base functions perform no auth, IO or persistence. Those keep
  Bandit-seeded, hand-adapted items and therefore keep manual verification.
- **`copy_paste_residue` may be incompatible with the question battery.** The flavour is
  defined by behaviourally inert code — a leftover print, dead assignments. It cannot fail a
  test by construction, and the wave-1 reviewer marked exactly such an item `not_a_bug`
  ("Dead code… produces no behavioral defect"). But `q_intentionality`, `q_explanation` and
  `q_blame` all presuppose a bug. Either the flavour is dropped, or the battery's presupposition
  is relaxed for it. Flagged, not resolved here.
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
- Test runner: sandboxed, timeout-bounded, correctly reports pass/fail; equivalent mutants
  are detected and discarded.
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
