# Generation Prompt: Producing Vignette Code

**Status:** draft, pending pilot generation runs.

This doc specifies how the actual buggy `CODE_BLOCK` for each item (per
[`design.md`](design.md)) gets produced, and where to source real,
pre-vetted example bugs to seed that process. It is a separate concern
from [`config-schema.md`](config-schema.md), which defines the
classification rubric (`bug_flavor`/`severity_tier` definitions) this
generation prompt reads from.

## Scope decision: one code version per call

Each generation call produces a **single** `CODE_BLOCK` for one specific
`(stated_aim, bug_flavor, severity_tier)` combination.

## Generation prompt template

```
You are generating a single Python function for a research study on how
bugs in code are judged.

Requirements:
- Language: Python only.
- Exactly one self-contained function (no helper functions, no classes). A
  leading module-level import statement is allowed if needed (e.g. `import
  json`); no other top-level statements.
- No comments and no docstrings in the code.
- No suggestive variable/function names or coding style that hints at
  whether the bug is intentional, careless, or reflects a competence gap.
  Use names that would be typical and neutral for this task.
- The function body should be approximately 3-25 lines (signature through
  return) - long enough for the bug to be clearly present, not padded
  with unrelated logic.

STATED_AIM: "{stated_aim_text}"

BUG_FLAVOR: {bug_flavor_id}
Definition: {bug_flavor_definition}
Reference/grounding: {bug_flavor_reference}
Examples: {bug_flavor_examples}

SEVERITY_TIER: {severity_tier_id}
Definition: {severity_tier_definition}
Reference/grounding: {severity_tier_reference}

Return JSON with exactly these fields:
{
  "code": "<code string>",
  "rationale": "<short technical note on what the bug is and where it is in the code - for human vetting only, never shown to judge models>"
}
```

`bug_flavor_definition`/`reference`/`examples` and
`severity_tier_definition`/`reference` are pulled directly from
`config/bug_flavor.json` and `config/severity_tier.json`, so the
generation prompt and the classification rubric used to vet/verify items
afterward stay identical by construction — one source of truth, not two
that can drift apart.

## The `rationale` field is an informal vetting aid, not ground truth

`rationale` is meant to help you and your collaborator quickly screen
which generated items are worth a closer look, not to serve as a
certified, automatically-used ground truth in analysis. In particular
it is **not** currently wired into the Tier 3 "bug-mention check" in
`design.md` §5 — that would require the generator's self-report to be
treated as verified data, which raises the vetting bar considerably
higher than a screening aid needs. Revisit this only if manual vetting
becomes a bottleneck and a validated ground-truth field becomes worth
the added rigor.

## Sourcing pre-vetted examples

**A source's label is not our label.** A source's own category establishes that a snippet
instantiates a *pattern*. It does not establish that the adapted item has the *behavioural
effect* our flavour definition requires, and the two must be recorded separately. Wave-1 item
36 is the worked example: a real swallowed exception (Bandit's `try_except_pass` pattern) that
raised `UnboundLocalError` rather than silently returning a wrong result. The pattern label was
right; the flavour assignment was wrong. So "Bandit example for an empty exception block" is
strong evidence of a swallowed-exception pattern, and is *not* on its own evidence that the
function silently returns a wrong result. Every adapted item is checked against the flavour's
behavioural definition and against its clean twin, and coded blind by a second coder who does
not see the assigned flavour, the generator rationale, or the provenance record. See
`docs/superpowers/specs/2026-09-25-corpus-grounded-item-generation-design.md` §1, §6, §6a.


Rather than relying solely on hand-invented examples, mine real,
permissively-licensed code as seed material — both to ground the
`bug_flavor.json` rubric `examples` fields and, more importantly, to
supply a large pool of base material for generation, which matters for
statistical power (more pre-vetted examples → more items → better
powered confirmatory tests).

**`missing_edge_case` / `logic_error`** — these need a clean base function
plus an injected bug:

- **HumanEval** (OpenAI, MIT license) — 164 short Python functions, each
  with a natural-language description (a ready-made `stated_aim`
  candidate) and a canonical correct solution, mostly within our 3-25
  line range.
- **MBPP** (Google Research, CC-BY-4.0 license - requires attribution) —
  ~974 more of the same shape (description + canonical solution + tests).
- Together, ~1,100 clean base functions with built-in aim descriptions.
  Inject a bug via a controlled mutation operator (manually, or with a
  mutation-testing tool such as `MutPy`, applying the same ROR/COR/AOR
  operators already grounding the `logic_error`/`missing_edge_case`
  rubric in `config/bug_flavor.json`) - this scales to as many items as
  vetting time allows, not a fixed small pool.
- **QuixBugs** (MIT license) — ~40 real, *already-buggy* Python programs
  (single-line defects, bug pre-planted rather than injected) - useful
  both as direct examples and as a sanity check that injected bugs read
  as "real."

**`security_vulnerability` / `silent_failure`** — mine **Bandit's own
`examples/` directory** (Apache License 2.0), which has short, purpose-
built files for exactly these categories: `sql_statements.py`,
`hardcoded-passwords.py`, `try_except_pass.py`, plus command injection,
insecure deserialization, weak crypto, and disabled TLS verification
examples. These are already vetted as belonging to a specific CWE
category by a widely-used static-analysis tool's own test suite.

**`copy_paste_residue` / `known_trap` / `wrong_algorithm`** — no large
corpus to mine; these stay lower-volume, hand-constructed from the
~10-15 well-known Python gotchas, manually written copy-paste examples,
and hand-written wrong-algorithm substitutions respectively. This
matches their already lower-priority/exploratory status in `design.md`
§1a.

### Licensing / attribution

All three corpora above are permissively licensed but not public domain -
attribution is required when adapting code from them:

| Source | License | Attribution needed |
|---|---|---|
| HumanEval | MIT | Yes - retain copyright notice |
| MBPP | CC-BY-4.0 | Yes - explicit attribution required |
| QuixBugs | MIT | Yes - retain copyright notice (© James Koppel) |
| Bandit examples | Apache 2.0 | Yes - retain license/attribution |

When an item's code is adapted from one of these sources, record the
source and any modification in that item's metadata (not yet specified -
see Open Items) so attribution can be assembled for any resulting
publication or public release of the item bank.

## Open items

- Whether bug injection into HumanEval/MBPP base functions is done by
  hand, by an LLM (using a variant of this same generation prompt with
  the base function supplied instead of generated from scratch), or with
  a dedicated mutation-testing tool (e.g. `MutPy`) - affects tooling but
  not the rubric/reference grounding already established.
- ~~Exact per-item metadata schema for recording provenance (source corpus,
  original problem ID, license)~~ — **resolved.** Every item carries a
  `provenance` object: `source`, `source_id`, `source_label`,
  `source_license`, `mutation_operator`, `modifications`. `source_label`
  holds the source's *own* category where it has one and stays `null`
  where the source labels nothing — the source-label/study-label
  distinction above, made machine-readable. Items written from a flavour
  definition rather than adapted record `source: "generated"` with the
  rest null. Attribution for any public release is assembled from these
  records against the licence table above. Specified in
  `docs/superpowers/specs/2026-09-25-corpus-grounded-item-generation-design.md` §5.
