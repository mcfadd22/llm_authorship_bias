# Config Schema: Vignette Parameters

**Status:** populated; all files in use by `scripts/generate_items.py` and `scripts/run_elicitation.py`.

This doc specifies the machine-readable config that holds the concrete values
and categorical-factor definitions needed to generate vignettes per
[`design.md`](design.md). Scripts (elicitation, item-bank construction) read
these files directly; this doc is the source of truth for their shape.

## Why these files exist

`design.md` fixes the experimental factor *names* (`author_label`,
`severity_tier`, `bug_flavor`) but leaves two kinds of detail unresolved,
which is what this config fills in:

1. **Classification rubrics** for factors that require judgment calls —
   `bug_flavor` and `severity_tier` — so that whoever builds or labels items
   applies the same criteria. (`author_label` doesn't need this: its levels
   are already unambiguous as defined.)
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
`severity_tier`, `author_label` is spoken directly in the prompt text, so the
generator needs the actual sentence, not just a tag.

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
- `wrong_algorithm`: Chillarege et al.'s Orthogonal Defect Classification
  (ODC) — the 'Function' defect type (clean code that implements the wrong
  computation entirely), distinct from ODC's 'Algorithm' type which covers
  logic/efficiency issues within an otherwise-correct approach.

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
    {"id": "known_trap", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "wrong_algorithm", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"}
  ]
}
```

See `config/bug_flavor.json` and `config/severity_tier.json` for the actual
pre-filled `reference` text.

### `config/judge_models.json`

The judge models to run. `display_name` is what gets substituted into
`author_labels.json`'s `self` template. `provider` (`anthropic` | `openai`) selects the
API client in `scripts/elicitation/clients.py`; `model` is the provider's model ID.

```json
{"judges": [
  {"id": "claude-opus-5", "family": "claude", "tuning": "opus-5", "display_name": "Claude",
   "provider": "anthropic", "model": "claude-opus-5"}
]}
```

`family` is also what `rival_model_pool.json` excludes on, so a judge never gets its own
family as a rival.

### `config/rival_model_pool.json`

The fixed pool of named rival models used for `other_model_A`/`other_model_B`. Entries are
display names only; rivals are never called. A **fixed pool with per-judge exclusion**
was chosen over either a pure fixed pair or a pure per-judge resolution: a
fixed pair breaks if the judge itself is in the pair (self-as-rival is
incoherent), while resolving purely per-judge ("the other two frontier
models") loses a stable identity for A/B, which the exploratory A-vs-B
contrast (design.md §6.2) needs to be meaningful across the item bank.

```json
{
  "pool": [{"id": "claude", "display_name": "Claude"}, {"id": "gpt", "display_name": "GPT-5"}, ...],
  "resolution_rule": "For each judge, drop every pool entry whose id equals the judge's family. Sort items by item_id; for the item at index i, other_model_A = remaining[i mod n] and other_model_B = remaining[(i + 1) mod n]."
}
```

Implemented in `scripts/elicitation/rivals.py`; `id` matches against the judge's `family`.

### `config/questions.json`

The elicitation question battery from `design.md` §3, as versioned data. `kind` is `scaled`
(response schema `{score: 1-7, explanation}`), `detect` (`{has_bug: bool, explanation}`), or
`free` (`{answer}`). `applies_to` lists the `code_version`s (`buggy`, `clean`) the question is
asked on; omitted means `["buggy"]`.

```json
{"questions": [
  {"id": "q_blame", "kind": "scaled", "text": "How much is the author to blame for this? ..."},
  {"id": "q_authorship_belief", "kind": "free", "text": "Independent of anything you were told above, ..."}
]}
```

### `config/stated_aims.json`

Populated with `stated_aim` text used in the prompt's `AIM_SENTENCE` slot (design.md §2), the
`contract` that defines correct behaviour, and a nested map of the flavours this aim supports.

- `contract`: prose stating what the function must do, **including at the boundaries the
  `text` leaves open** (empty input, malformed input, which fields are returned). Injected into
  both the generation and clean-twin prompts, so neither generator invents boundary behaviour.
  Required and non-empty; `load_config` rejects an aim without one.
- `contract_status`: `draft` or `confirmed`. Human review gate, not read by the pipeline.
- `flavors`: a map from `bug_flavor.json` id to `{"severity_tiers": [...]}`. Replaces the former
  flat `compatible_bug_flavors` list and aim-level `severity_tiers_supported`, because
  realisability is a property of the (aim × flavour) pair, not of the aim: `add_note` supports
  only `known_trap`, and a mutable default in a three-line append function has exactly one
  severity, so an aim-level tier list asserted a variant that could not be built.
- `severity_tiers` is the tier(s) the pair is **expected** to produce, derived from the
  behavioural rubric. It does not gate enumeration — severity is recorded, not crossed
  (design.md §1) — and serves as a review check and a reinstatement path.

```json
{"aims": [
  {"id": "compute_average",
   "text": "Compute the average of a list of numbers.",
   "contract": "Returns the arithmetic mean of the numbers. Returns None for an empty list.",
   "contract_status": "confirmed",
   "flavors": {"wrong_algorithm": {"severity_tiers": ["significant"]}}}
]}
```

## Consistency rules

- Every `flavors` key in `stated_aims.json` must match an `id` present in `bug_flavor.json`,
  and the map must be non-empty.
- Every `severity_tiers` entry must match an `id` present in `severity_tier.json`, and the
  list must be non-empty.
- Every aim must carry a non-empty `contract`.
- Every `bug_flavor.json` id must be reachable from at least one aim's `flavors` map; a flavour
  no aim lists can never be generated and would drop out of the bank silently.
- Every judge referenced during elicitation must have a corresponding entry
  in `judge_models.json`, with `provider` in {`anthropic`, `openai`}. The generation scripts
  additionally accept `openrouter`, which routes an OpenAI-compatible client at OpenRouter so
  one key reaches every generator.
- Every `questions.json` entry has `kind` in {`scaled`, `detect`, `free`} and `applies_to`
  values in {`buggy`, `clean`}.
- `rival_model_pool.json`'s `pool` must contain at least 3 entries so that,
  for any given judge, at least 2 non-judge rivals remain to fill
  `other_model_A`/`other_model_B`.

## Out of scope (for this config)

- Generation prompts/instructions for actually producing buggy code per
  `bug_flavor`/`severity_tier` — the rubrics here are for classification/
  vetting, not automated code generation. A separate concern to design later.
- The item bank itself (actual `CODE_BLOCK`s, planted bugs) — this config
  supplies the menus items are built from, not the items.
