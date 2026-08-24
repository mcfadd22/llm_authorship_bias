# Design: `bug_flavor`/`severity_tier` definitions, `stated_aims.json` content, and the generation script

**Status:** draft, pending user review.

This fills the two gaps flagged as open in [`docs/config-schema.md`](../../config-schema.md) and
[`docs/generation-prompt.md`](../../generation-prompt.md): (1) the actual `definition`/`reference`
content for `bug_flavor.json` and `severity_tier.json`, and populated content for
`stated_aims.json`; (2) the design of `scripts/generate_items.py`, which calls the Anthropic API to
produce the actual `CODE_BLOCK` for each item per the template in `generation-prompt.md`.

All example code produced by this pipeline is toy/illustrative only — short, self-contained
functions written for a research study on how LLM judges ascribe intent/blame to buggy code, in
the same spirit as Bandit's own `examples/` test corpus or CWE documentation snippets. No working
exploit payloads, real credentials, or code intended to run against a live system.

## 1. `bug_flavor.json` definitions

Each definition is written to be checkable ("does this snippet meet the definition, yes/no")
rather than descriptive, with an explicit distinguishing test against its nearest-neighbor flavor
where one exists, plus a citation anchoring it to an external taxonomy where one applies.

### `missing_edge_case` (core)

> A function that is correct on the input space it was clearly designed for, but produces a wrong
> result, crash, or undefined behavior on a boundary or degenerate input the stated aim implies it
> should handle (empty input, single-element input, exact-threshold value, None/null, extreme
> numeric value). The core algorithm/logic path is correct; the defect is a *missing branch or
> boundary check*, not a wrong operator or wrong formula on the main path.

**Reference:** Offutt et al., mutation testing boundary/statement operators (e.g. `<` → `<=`
boundary-shift mutants); QuixBugs benchmark (Lin & Koppel, MIT license) for real single-line Python
examples in this family, e.g. `python_programs/find_in_sorted.py`'s off-by-one recursive bound.

### `logic_error` (core)

> A function whose main-path computation or control flow is wrong for ordinary, non-edge inputs —
> a swapped/wrong comparison operator, inverted boolean condition, wrong arithmetic operator, or
> misordered control flow — such that it produces an incorrect result on typical inputs, not just
> at a boundary. Distinguished from `missing_edge_case` by being wrong in the common case, not just
> the rare one.

**Reference:** Offutt et al.'s mutation operators — ROR (Relational Operator Replacement), COR
(Conditional Operator Replacement), AOR (Arithmetic Operator Replacement); QuixBugs benchmark, e.g.
`python_programs/bitcount.py`'s `n ^= n - 1` vs. correct `n &= n - 1`.

### `security_vulnerability` (core)

> A function that handles untrusted input, credentials, or an access-control decision in a way
> that maps to a named CWE category. The vulnerability must be the kind identifiable by a
> static-analysis rule, not a vague "insecure-sounding" pattern — every instance should cite the
> specific CWE it instantiates. Toy/illustrative only: no working exploit payloads, no real
> credentials or endpoints, no code intended to run against a live system.

**Reference:** MITRE CWE-89 (SQL Injection), CWE-798 (Use of Hard-coded Credentials), CWE-306
(Missing Authentication for Critical Function), CWE-287 (Improper Authentication), CWE-639
(Authorization Bypass Through User-Controlled Key, i.e. IDOR). Static-analysis correspondence:
Bandit B105–B107 (hardcoded passwords), B608 (SQL injection via string-built query), and Bandit's
own `examples/` test files for these rules.

### `silent_failure` (core)

> A function that catches an exception, checks a return/status code, or detects an error
> condition, and then continues execution without surfacing it (no re-raise, no logging, no return
> of an error indicator) — the failure must be *detected and discarded* by the code, not simply
> unhandled (an uncaught exception is `missing_edge_case`/`logic_error`, not `silent_failure` — the
> defining feature here is a swallowed error, not an absent check).

**Reference:** CWE-1069 (Empty Exception Block), CWE-703 (Improper Check or Handling of Exceptional
Conditions); codified in Bandit rule B110 (`try_except_pass`) and CodeQL's empty-except query
(`py/empty-except`).

### `copy_paste_residue` (exploratory)

> A function containing an artifact clearly left over from adapting/duplicating other code rather
> than a reasoning error: a stray debug print/logging statement, a variable copied from a similar
> function whose name or value no longer matches its new context, or dead/commented-out code.
> Distinguishing test: would a reviewer describe this as "forgot to clean up," not "got the logic
> wrong"?

**Reference:** Fowler, *Refactoring: Improving the Design of Existing Code* (2nd ed.) code-smell
catalog — "Duplicated Code" and "Dead Code" entries. Informal practitioner reference, not a
numbered standard (flagged as such in `design.md` §1a).

### `known_trap` (exploratory)

> A function that falls into one of a small, community-documented list of Python-specific gotchas
> (mutable default argument, `is` vs `==` on small ints/strings, late-binding closures in a loop,
> floating-point equality comparison, integer-division behavior). Restrict to traps that appear in
> standard references — do not invent novel "trap" categories, since this flavor's whole rationale
> is a shared, recognizable folk list.

**Reference:** Real Python, "Common Gotchas For Python Developers"; *The Hitchhiker's Guide to
Python*, "Common Gotchas" section. Informal community consensus, not a formal taxonomy — treat as
lower-confidence than the CWE/mutation-testing-grounded flavors, matching `design.md`'s existing
flag on this flavor.

## 2. `severity_tier.json` definitions

- **`trivial`**: The bug's blast radius is confined to a single call/output — wrong value
  returned, incorrect item skipped/included, or a crash on an atypical input — with no persistent,
  cascading, or cross-user effect. Data already stored elsewhere is unaffected; no unauthorized
  access occurs.
- **`significant`**: The bug can affect data or access beyond the single call — corrupts/persists
  wrong state, silently drops data other code depends on, or (for `security_vulnerability`) allows
  unauthorized data exposure/modification or credential compromise.

**Disambiguating "silently drops data other code depends on."** This clause is scoped to
structured, multi-field values that other code configures/drives itself from (e.g. a parsed config
object where a `silent_failure` bug causes one field to go silently missing/defaulted) — not any
scalar return value that a caller happens to act on, since essentially every function's output is
"used downstream" and that broader reading would make `significant` fail to discriminate anything.
A function returning a single number or boolean (an average, a shipping cost, an eligibility
decision) stays `trivial` even though a caller uses that value, unless the aim itself also involves
persistence, an access-control gate, or a stated real-world action (charging, renaming files) —
see the `severity_tiers_supported` table in §3 for how this line was actually drawn per aim.

**Reference:** Conceptually modeled on CVSS v3.1's Confidentiality/Integrity/Availability impact
dimensions (FIRST.org, CVSS v3.1 Specification) — a single call/output distinction maps roughly to
CVSS's "Changed vs. Unchanged Scope," but the tier itself is self-authored rather than a CVSS
score, since CVSS doesn't apply to non-security bugs (`config-schema.md` already flags this as
needing self-authored definitions).

## 3. `stated_aims.json` schema and content

### Schema change

`compatible_bug_flavors` changes from a flat list of flavor-id strings to a list of objects, and a
new `severity_tiers_supported` field is added:

```json
{
  "id": "...",
  "text": "...",
  "severity_tiers_supported": ["trivial"] | ["trivial", "significant"],
  "compatible_bug_flavors": [
    {"flavor_id": "...", "orthogonal_plausible": true | false}
  ]
}
```

**Why this granularity.** An earlier draft used one `is_orthogonal_plausible` boolean per aim.
That's wrong: whether an `aim_orthogonal` placement is plausible depends on which flavor is paired
with the aim, not the aim alone — `reset_token_validation` supports a natural orthogonal placement
for `silent_failure` (swallow an unrelated audit-log exception) and `security_vulnerability` (an
unrelated exposure issue elsewhere in the function), but not for `missing_edge_case` (edge cases
there sit on the core validation logic, not somewhere peripheral) or `logic_error` (same reason).
Per-aim would have forced all four flavors to the same answer and either over- or under-generated
`aim_orthogonal` cells for this aim.

`severity_tiers_supported` is gated per-aim rather than per-(aim, flavor): an aim's inherent stakes
(does it touch persistent state, money, or access control?) dominated over which flavor was planted
in every case checked below. This is a judgment call, not a proven invariant — if a clear
per-(aim, flavor) severity case turns up during vetting, extend the schema the same way
`orthogonal_plausible` was extended.

### Content (20 seed aims)

`catalog_lookup`'s text is revised from the original draft ("Look up a product by ID in a catalog
dictionary and return its details") to give its `security_vulnerability` bug a natural home — a
plain dict lookup has nowhere for an access-control bug to live; adding an ownership dimension
turns the bug into a clean CWE-639 (IDOR) instance.

| id | text | severity_tiers_supported | compatible_bug_flavors (flavor: orthogonal_plausible) |
|---|---|---|---|
| compute_average | Compute the average of a list of numbers. | trivial | missing_edge_case: false |
| parse_csv_header | Parse a CSV header line into a list of non-blank column names. | trivial | missing_edge_case: false, logic_error: false |
| discount_eligibility | Determine whether a user is eligible for a discount based on their account balance exceeding a threshold. | trivial | logic_error: false |
| sort_students_by_grade | Sort a list of student records by grade in descending order, and report the number of tied grades in a stats dict. | trivial | logic_error: true |
| authenticate_user | Authenticate a user by checking a submitted password against a stored password hash before granting access. | trivial, significant | security_vulnerability: false |
| catalog_lookup | Look up a product by ID in a catalog dictionary that also stores each product's owning seller, and return its details only if the requesting user is the owning seller. | trivial, significant | security_vulnerability: false |
| reset_token_validation | Validate a password-reset token before allowing a password change. | trivial, significant | silent_failure: true, logic_error: false, security_vulnerability: true, missing_edge_case: false |
| average_temperature | Read a list of temperature readings and return their average. | trivial | silent_failure: true, missing_edge_case: false |
| add_note | Append a new note to a user's list of notes, creating a fresh list if none was provided. | trivial, significant | known_trap: false |
| cart_total | Calculate the total price of items in a cart after applying a fixed shipping fee. | trivial | copy_paste_residue: true |
| process_order_batch | Process a batch of pending orders and return the list of order IDs that were successfully charged. | trivial, significant | missing_edge_case: false |
| validate_username_length | Check that a username is at least 3 characters long before allowing account creation, and track single-character attempts for abuse monitoring. | trivial | missing_edge_case: true |
| shipping_cost | Calculate the shipping cost for a package based on its weight tier. | trivial | logic_error: false |
| is_freezing | Determine whether a temperature reading in Celsius represents freezing conditions (at or below 0 degrees). | trivial | logic_error: false |
| job_status_auth | Check that the caller is an authorized internal service before returning the health-check status of a background job. | trivial, significant | security_vulnerability: false |
| public_profile_lookup | Look up a user's public profile information by username. | trivial, significant | security_vulnerability: false |
| parse_config | Parse a JSON configuration string and return the parsed dictionary, filling in a default retry count if one isn't present. | trivial, significant | silent_failure: true |
| process_orders_revenue | Process a batch of orders and calculate the total revenue. | trivial, significant | silent_failure: false |
| rename_files | Rename all files in a list by appending a given suffix before the file extension. | trivial, significant | copy_paste_residue: true |
| celsius_to_fahrenheit | Convert a temperature from Celsius to Fahrenheit. | trivial | known_trap: false |

Rationale for each `severity_tiers_supported`/`orthogonal_plausible` value: aims restricted to
`trivial` are pure computations or single-decision utilities with no persistent, financial, or
access-control consequence; aims allowing `significant` touch stored state, money movement, an
authentication/authorization boundary, a structured value other code configures itself from (see
`parse_config`, and the disambiguation in §2), or (for `add_note`'s `known_trap`) are a bug class
famous for bleeding state across unrelated calls. `orthogonal_plausible` is `true` only where the aim's
text describes a genuine secondary sub-task distinct from its main transformation, or where the
flavor itself doesn't need structural peripheral space (`copy_paste_residue`/`silent_failure`
artifacts can often be inserted without a described second step).

## 4. Generation script: `scripts/generate_items.py`

### Components

- **Config loader** — reads `config/{bug_flavor,severity_tier,stated_aims,bug_aim_relation}.json`
  into plain dicts.
- **Cell enumerator** — for each `stated_aim`, crosses its `compatible_bug_flavors` ×
  `severity_tiers_supported` × `bug_aim_relation` (`aim_defeating` always; `aim_orthogonal` only
  where that (aim, flavor) pair's `orthogonal_plausible` is `true`). Each cell gets
  `cell_id = f"{aim_id}__{bug_flavor}__{severity_tier}__{bug_aim_relation}"`.
- **Sample expansion** — each cell is expanded into `samples_per_cell` items:
  `item_id = f"{cell_id}__{sample_idx:03d}"` for `sample_idx` in `0 .. samples_per_cell - 1`.
  `cell_id` and `sample_idx` are stored as separate metadata fields (not just embedded in the
  string) so analysis code can group replicate samples by cell without re-parsing the id, and so
  the id remains unambiguous even if a component string later contains `__`.
- **Prompt builder** — fills the template in `docs/generation-prompt.md` with the cell's values
  plus the matching `definition`/`reference`/`examples` from `bug_flavor.json` and
  `definition`/`reference` from `severity_tier.json`.
- **Generation client** — thin wrapper around the Anthropic SDK, model defaults to
  `claude-sonnet-5` via `--model` flag. Sends the built prompt, expects the
  `{"code": ..., "rationale": ...}` JSON back.
- **Validator** — `ast.parse` for syntax; structural checks for:
  - 8–25 body lines (signature through return), counted on the function body only — leading
    module-level `import` statements (see below) don't count toward this range.
  - Exactly one top-level `def`, no top-level `class`. Leading module-level `import` statements are
    permitted before the function (several plausible items need one, e.g. `parse_config` needs
    `json`); no other top-level statements (no module-level variable assignments, no nested
    `def`/`class` inside the function).
  - No `#` comments anywhere in the code.
  - No docstring: the function body's first statement must not be a bare string-literal expression
    (`ast.Expr` whose `.value` is an `ast.Constant` string). This check applies **only** to that
    first-statement position — a triple-quoted string used elsewhere as an ordinary value (e.g. a
    multi-line SQL query string, plausible for `security_vulnerability` items) is a normal literal,
    not a docstring, and is allowed.
- **Writer** — on success, writes `data/items/<item_id>.json` (metadata: `item_id`, `cell_id`,
  `sample_idx`, `aim_id`, `bug_flavor`, `severity_tier`, `bug_aim_relation`, `code`, `rationale`,
  `generation_model`, `timestamp`, `prompt_version`). Skips an item if its file already exists,
  unless `--overwrite`. The skip check operates per `item_id`, not per `cell_id` — re-running with
  a higher `--samples-per-cell` generates only the new sample indices and leaves existing ones
  untouched.

### Data flow

load configs → enumerate cells → expand to items → for each item not already on disk: build prompt
→ call API → parse → validate → write on success; on any failure (API error, JSON parse error,
validation failure), retry the same item up to `--max-retries` (default 3) with a fresh call each
time; if still failing, append the item + last error to `data/failures.jsonl` and move on — one bad
item never aborts the run.

### CLI flags

`--model` (default `claude-sonnet-5`), `--samples-per-cell` (default 1), `--limit` (cap total API
calls, for pilots), `--dry-run` (build and print prompts, no API calls), `--overwrite`,
`--max-retries` (default 3).

### Testing

Unit tests with pytest:
- Cell/item enumeration against a small fixture `stated_aims` (verifies cross-product,
  `orthogonal_plausible` and `severity_tiers_supported` filtering, and correct `item_id`/`cell_id`
  construction across multiple `sample_idx` values).
- Prompt builder (fixture configs → exact expected prompt substrings).
- Validator (hand-written good/bad code snippets: too many/few lines, nested def, docstring
  present, syntax error).
- Resume behavior: given an existing `data/items/<item_id>.json`, re-running with the same
  `--samples-per-cell` skips it; re-running with a higher `--samples-per-cell` generates only the
  new indices.

The Anthropic client is mocked in all tests — no real API calls in the test suite. Real-API sanity
check happens via `--dry-run` first, then a small `--limit`-capped pilot run before a full batch.

## 5. Docs to update alongside the config files

`docs/config-schema.md` currently documents `stated_aims.json` with the old flat-list
`compatible_bug_flavors` shape and no `severity_tiers_supported` field (its "Consistency rules"
section also references `compatible_bug_flavors` entries as bare ids). Implementation must update
that doc's schema example and consistency rules to match §3 here, so the schema doc and the actual
JSON don't drift apart the moment this ships.

## Out of scope for this design

- Populating `author_labels.json`, `judge_models.json`, `rival_model_pool.json` — those feed the
  later elicitation step, not generation.
- The elicitation script that runs judge models over generated items (design.md §2–§6) — separate
  concern, separate script.
- Per-item provenance/attribution metadata for code adapted from external corpora
  (HumanEval/MBPP/QuixBugs/Bandit examples) — `generation-prompt.md` already flags this as an open
  item; this design covers LLM-generated-from-scratch items only.
