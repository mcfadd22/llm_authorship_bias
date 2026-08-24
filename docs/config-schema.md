# Config Schema: Vignette Parameters

**Status:** draft, pending fill-in of rubric/model/aim content by collaborators.

This doc specifies the machine-readable config that holds the concrete values
and categorical-factor definitions needed to generate vignettes per
[`design.md`](design.md). Scripts (elicitation, item-bank construction) read
these files directly; this doc is the source of truth for their shape.

## Why these files exist

`design.md` fixes the experimental factor *names* (`author_label`,
`bug_aim_relation`, `severity_tier`, `bug_flavor`) but leaves two kinds of
detail unresolved, which is what this config fills in:

1. **Classification rubrics** for factors that require judgment calls —
   `bug_flavor` and `severity_tier` — so that whoever builds or labels items
   applies the same criteria. (`author_label` and `bug_aim_relation` don't
   need this: their levels are already unambiguous as defined.)
2. **Concrete content** — actual judge models, actual rival model names, and
   actual `stated_aim` text — that `design.md` deliberately left as
   placeholders (`{JUDGE_MODEL_DISPLAY_NAME}`, `{RIVAL_MODEL_A_DISPLAY_NAME}`,
   etc.).

Rubrics here are **classification aids for humans** (or any process
constructing/vetting items), not generation prompts fed to an LLM to write
code — that's a separate, later concern.

## File format

JSON, one file per parameter, under `config/`. Splitting per parameter keeps
diffs small when only one thing changes and makes it obvious where to look
for a given value.

## Files

### `config/author_labels.json`

The `author_label` factor's levels, with the literal sentence template used
in the prompt's `AUTHOR_SENTENCE` slot (design.md §2). Unlike `bug_flavor`/
`severity_tier`/`bug_aim_relation`, `author_label` is spoken directly in the
prompt text, so the generator needs the actual sentence, not just a tag.

```json
{
  "labels": [
    {
      "id": "none",
      "sentence_template": null,
      "notes": "Omit AUTHOR_SENTENCE entirely - no authorship claim at all"
    },
    {
      "id": "self",
      "sentence_template": "This function was written by {judge_display_name}.",
      "notes": "judge_display_name resolved from judge_models.json for the current judge"
    },
    {
      "id": "other_model_A",
      "sentence_template": "This function was written by {rival_display_name}.",
      "notes": "resolved from rival_model_pool.json per its resolution_rule"
    },
    {
      "id": "other_model_B",
      "sentence_template": "This function was written by {rival_display_name}.",
      "notes": "distinct from other_model_A for the same item"
    },
    {
      "id": "generic_ai",
      "sentence_template": "This function was written by an AI system.",
      "notes": null
    },
    {
      "id": "human_developer",
      "sentence_template": "This function was written by a human developer.",
      "notes": null
    }
  ]
}
```

### `config/bug_aim_relation.json`

Plain enum. No rubric needed — the two levels are already unambiguous given
a `stated_aim` and a bug (design.md §1a, matched-pair construction).

```json
{
  "levels": [
    {"id": "aim_defeating", "notes": "Bug undermines exactly what STATED_AIM promises"},
    {"id": "aim_orthogonal", "notes": "Bug is incidental to STATED_AIM; stated purpose still works"}
  ]
}
```

### `config/severity_tier.json`

Classification rubric. `definition`/`examples` start empty (`"status":
"todo"`) — to be filled in collaboratively, since "trivial" vs. "significant"
is a judgment call that needs a tight, shared definition to apply
consistently. `reference` notes that, unlike `bug_flavor`, no clean external
standard applies here (CVSS-style severity scoring is security-specific);
this factor's definitions will be self-authored rather than anchored to an
external taxonomy.

```json
{
  "levels": [
    {"id": "trivial", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "significant", "definition": "", "examples": [], "reference": "...", "status": "todo"}
  ]
}
```

### `config/bug_flavor.json`

Classification rubric, same shape as `severity_tier.json`, plus `category`
(distinguishing core primary-factorial flavors from the optional exploratory
ones, per design.md §1a) and `reference` — a pointer to an established
external taxonomy or source grounding that flavor, pre-filled since it's
factual/citable rather than a judgment call:

- `missing_edge_case` / `logic_error`: mutation-testing operators (Offutt et
  al. — ROR, COR, AOR, boundary/statement operators) and the QuixBugs
  benchmark for real example defects.
- `security_vulnerability`: MITRE CWE (CWE-89 SQL injection, CWE-306 missing
  auth, CWE-287 improper auth, CWE-798 hardcoded credentials).
- `silent_failure`: CWE-1069 (Empty Exception Block), CWE-703, and static
  analysis rules that codify it (Bandit B110, CodeQL empty-except).
- `copy_paste_residue`: Fowler's code-smell catalog (Duplicated Code, Dead
  Code) — a canonical but informal practitioner reference, not a numbered
  standard.
- `known_trap`: community-documented Python gotchas (e.g. mutable default
  arguments) — informal consensus, not a formal taxonomy; treat as
  lower-confidence than the CWE/mutation-testing-grounded flavors, consistent
  with design.md's own flag on this flavor.

`definition`/`examples` still start empty/`"todo"` — the `reference` gives
whoever fills them in a concrete anchor rather than a blank page. This same
field is intended to do double duty as both the classification rubric
(verifying an item after the fact) and a constraint fed to the generation
prompt (steering what gets planted) — one source of truth for both, so the
two can't drift apart. `known_trap` needs particular care since design.md
flags it as the flavor most likely to be judged inconsistently across
items/coders.

```json
{
  "levels": [
    {"id": "missing_edge_case", "category": "core", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "logic_error", "category": "core", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "security_vulnerability", "category": "core", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "silent_failure", "category": "core", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "copy_paste_residue", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "known_trap", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"}
  ]
}
```

See `config/bug_flavor.json` and `config/severity_tier.json` for the actual
pre-filled `reference` text.

### `config/judge_models.json`

Empty list to populate with the actual judge models to run. `display_name`
is what gets substituted into `author_labels.json`'s `self` template.

```json
{"judges": []}
```

Each entry, once filled in: `{"id": "...", "family": "...", "tuning": "...",
"display_name": "..."}`.

### `config/rival_model_pool.json`

Empty pool to populate with the fixed set of named rival models used for
`other_model_A`/`other_model_B`. A **fixed pool with per-judge exclusion**
was chosen over either a pure fixed pair or a pure per-judge resolution: a
fixed pair breaks if the judge itself is in the pair (self-as-rival is
incoherent), while resolving purely per-judge ("the other two frontier
models") loses a stable identity for A/B, which the exploratory A-vs-B
contrast (design.md §6.2) needs to be meaningful across the item bank.

```json
{
  "pool": [],
  "resolution_rule": "For each judge/item, select two distinct entries from `pool`, excluding any entry whose id matches the current judge, and rotate assignment across items so no single rival is confounded with a specific item/bug. Assign one to other_model_A, one to other_model_B."
}
```

Each pool entry, once filled in: `{"id": "...", "display_name": "..."}`.

### `config/stated_aims.json`

Populated with `stated_aim` text used in the prompt's `AIM_SENTENCE` slot (design.md §2), plus two
construction-constraint fields:

- `compatible_bug_flavors`: a list of `{flavor_id, orthogonal_plausible}` objects, not a flat list
  of ids. `flavor_id` references `bug_flavor.json`; `orthogonal_plausible` says whether this
  specific (aim, flavor) pairing can plausibly support an `aim_orthogonal` placement (see
  `design.md` §1a and the generation-script design doc for why this is gated per-pairing, not
  per-aim).
- `severity_tiers_supported`: a list drawn from `severity_tier.json`'s ids, saying which severity
  tiers this aim can plausibly support (e.g. a pure computation like "compute an average" can't
  plausibly support `significant`).

```json
{"aims": []}
```

Each entry, once filled in:
```json
{
  "id": "...",
  "text": "...",
  "severity_tiers_supported": ["trivial"],
  "compatible_bug_flavors": [{"flavor_id": "...", "orthogonal_plausible": false}]
}
```

## Consistency rules

- Every `compatible_bug_flavors[].flavor_id` entry in `stated_aims.json` must match an `id` present
  in `bug_flavor.json`.
- Every `severity_tiers_supported` entry in `stated_aims.json` must match an `id` present in
  `severity_tier.json`.
- Every judge referenced during elicitation must have a corresponding entry
  in `judge_models.json`.
- `rival_model_pool.json`'s `pool` must contain at least 3 entries so that,
  for any given judge, at least 2 non-judge rivals remain to fill
  `other_model_A`/`other_model_B`.

## Out of scope (for this config)

- Generation prompts/instructions for actually producing buggy code per
  `bug_flavor`/`severity_tier` — the rubrics here are for classification/
  vetting, not automated code generation. A separate concern to design later.
- The item bank itself (actual `CODE_BLOCK`s, planted bugs) — this config
  supplies the menus items are built from, not the items.
