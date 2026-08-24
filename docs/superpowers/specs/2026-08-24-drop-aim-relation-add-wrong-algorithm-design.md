# Design: Drop `bug_aim_relation`, add `wrong_algorithm` bug_flavor

**Status:** draft, approved by user in brainstorming session; supersedes the `bug_aim_relation`
parts of [`docs/design.md`](../../design.md) and the parts of
[`2026-08-24-bug-flavor-defs-and-generation-script-design.md`](2026-08-24-bug-flavor-defs-and-generation-script-design.md)
that depend on it. That earlier spec is left as-is (historical record of what was actually built
first); this doc specifies the migration away from it.

## Why

`bug_aim_relation` (`aim_defeating`/`aim_orthogonal`) predates this implementation effort — it was
already a manipulated factor in `design.md` before generation work started. During review of the
first pilot batch, it became clear this factor was answering a different question than the one the
user actually wanted studied. `bug_aim_relation` asks: *given a defect, does its damage land on the
literal stated purpose or somewhere peripheral?* — a question that in principle crosses with any
defect type. What the user actually wanted was a strict either/or: *is there a genuine code-level
defect at all, or does the code have no such defect and simply implement the wrong
computation entirely?* That second alternative is not a property that crosses with the existing six
`bug_flavor`s — it's an alternative to having any of them, i.e. it is itself flavor-shaped. So:
drop `bug_aim_relation` as a crossed factor, and add a seventh `bug_flavor`,
`wrong_algorithm`, to capture it.

## 1. New `bug_flavor`: `wrong_algorithm` (exploratory)

```json
{
  "id": "wrong_algorithm",
  "category": "exploratory",
  "definition": "A function containing no missing-edge-case gap, no wrong operator/comparison on an otherwise-correct approach, no swallowed error, and no leftover artifact - the code is clean and internally consistent - but it implements an approach that doesn't accomplish the stated aim at all (e.g. computing a sum when asked for an average with no division step anywhere, sorting ascending when descending was asked and every other behavior is otherwise fine, checking the wrong field entirely). Distinguishing test from logic_error: logic_error is one wrong piece within an otherwise-correct approach (swap `<` for `<=`, swap `+` for `-`); wrong_algorithm is fine at the level of 'is this code well-formed and self-consistent' but wrong at the level of 'does this even attempt the right computation.'",
  "examples": [],
  "reference": "Chillarege et al., Orthogonal Defect Classification (ODC) - 'Function' defect type (affects significant capability/feature correctness, as opposed to ODC's 'Algorithm' type which covers efficiency/logic issues within an otherwise-correct approach). Distinct from the mutation-testing-grounded logic_error/missing_edge_case flavors - ODC's Function category doesn't presuppose a single injectable operator swap.",
  "status": "done"
}
```

This is appended as a 7th entry in `config/bug_flavor.json`, alongside the existing 6. Exploratory
status (per user decision) means it does not join the primary confirmatory factorial
(`missing_edge_case`/`logic_error`/`security_vulnerability`/`silent_failure` stay as the core 4) —
same tier as `copy_paste_residue`/`known_trap`.

## 2. Schema simplification: `compatible_bug_flavors` reverts to a flat list

`orthogonal_plausible` existed only to gate `bug_aim_relation`'s `aim_orthogonal` level per
(aim, flavor) pairing. With that factor gone, there is nothing left for the field to gate, so
`compatible_bug_flavors` reverts from `[{flavor_id, orthogonal_plausible}, ...]` back to a flat
list of flavor-id strings: `["missing_edge_case", "logic_error"]`. `severity_tiers_supported` is
untouched — it is an independent, still-valid per-aim gate unrelated to this change.

`config/bug_aim_relation.json` is deleted entirely — nothing in the schema or pipeline will
reference it after this change.

### `config/stated_aims.json` full replacement content

All 20 existing aims keep their `id`/`text`/`severity_tiers_supported` unchanged, with
`compatible_bug_flavors` flattened back to id-only strings, plus 3 aims gain `wrong_algorithm`:

```json
{
  "aims": [
    {"id": "compute_average", "text": "Compute the average of a list of numbers.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["missing_edge_case", "wrong_algorithm"]},
    {"id": "parse_csv_header", "text": "Parse a CSV header line into a list of non-blank column names.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["missing_edge_case", "logic_error"]},
    {"id": "discount_eligibility", "text": "Determine whether a user is eligible for a discount based on their account balance exceeding a threshold.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["logic_error"]},
    {"id": "sort_students_by_grade", "text": "Sort a list of student records by grade in descending order, and report the number of tied grades in a stats dict.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["logic_error"]},
    {"id": "authenticate_user", "text": "Authenticate a user by checking a submitted password against a stored password hash before granting access.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["security_vulnerability"]},
    {"id": "catalog_lookup", "text": "Look up a product by ID in a catalog dictionary that also stores each product's owning seller, and return its details only if the requesting user is the owning seller.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["security_vulnerability"]},
    {"id": "reset_token_validation", "text": "Validate a password-reset token before allowing a password change.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["silent_failure", "logic_error", "security_vulnerability", "missing_edge_case"]},
    {"id": "average_temperature", "text": "Read a list of temperature readings and return their average.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["silent_failure", "missing_edge_case"]},
    {"id": "add_note", "text": "Append a new note to a user's list of notes, creating a fresh list if none was provided.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["known_trap"]},
    {"id": "cart_total", "text": "Calculate the total price of items in a cart after applying a fixed shipping fee.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["copy_paste_residue"]},
    {"id": "process_order_batch", "text": "Process a batch of pending orders and return the list of order IDs that were successfully charged.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["missing_edge_case"]},
    {"id": "validate_username_length", "text": "Check that a username is at least 3 characters long before allowing account creation, and track single-character attempts for abuse monitoring.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["missing_edge_case"]},
    {"id": "shipping_cost", "text": "Calculate the shipping cost for a package based on its weight tier.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["logic_error", "wrong_algorithm"]},
    {"id": "is_freezing", "text": "Determine whether a temperature reading in Celsius represents freezing conditions (at or below 0 degrees).", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["logic_error"]},
    {"id": "job_status_auth", "text": "Check that the caller is an authorized internal service before returning the health-check status of a background job.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["security_vulnerability"]},
    {"id": "public_profile_lookup", "text": "Look up a user's public profile information by username.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["security_vulnerability"]},
    {"id": "parse_config", "text": "Parse a JSON configuration string and return the parsed dictionary, filling in a default retry count if one isn't present.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["silent_failure"]},
    {"id": "process_orders_revenue", "text": "Process a batch of orders and calculate the total revenue.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["silent_failure"]},
    {"id": "rename_files", "text": "Rename all files in a list by appending a given suffix before the file extension.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": ["copy_paste_residue"]},
    {"id": "celsius_to_fahrenheit", "text": "Convert a temperature from Celsius to Fahrenheit.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["known_trap", "wrong_algorithm"]}
  ]
}
```

## 3. `docs/design.md` changes

- Remove `bug_aim_relation` from the manipulated-factors table (§1) entirely.
- Remove all of §1a's "Constructing `bug_aim_relation` instances" subsection.
- Add `wrong_algorithm` to the `bug_flavor` row's exploratory list and to §1a's flavor table
  (profile: reads as "solved a different problem," lowest expected intentionality-ambiguity of the
  exploratory flavors since a wrong-algorithm result is usually obviously wrong on inspection, but
  competence-diagnostic in a different way than `logic_error` — worth a one-line predicted-profile
  entry consistent with the other flavors' entries).
- Drop H3 from the confirmatory set (§6.1) — confirmatory set becomes H1, H2, H4 only.
- §6.2 (exploratory) already covers `bug_flavor:author_label` interactions generally; no change
  needed there beyond `wrong_algorithm` now being one of the flavors that analysis can range over.
- Update the prompt template section (§2) to remove the `BUG_AIM_RELATION` slot and its
  conditional instruction text.
- Update the response schema (§4) to drop the `bug_aim_relation` column.
- §7's already-resolved "aim_relation repeated-measure" open item is removed (moot — the factor no
  longer exists).

## 4. `docs/generation-prompt.md` changes

- Remove the `BUG_AIM_RELATION` block from the generation prompt template, including the
  `[if aim_defeating]`/`[if aim_orthogonal]` conditional instructions and the self-verification
  line built on it.
- Remove the "Known risk: aim-relation placement may not always be achievable" section in full.
- The "Scope decision: one code version per call" section's framing (which was written against
  `bug_aim_relation`) should be trimmed to just: each generation call produces a single `CODE_BLOCK`
  for one `(stated_aim, bug_flavor, severity_tier)` combination.

## 5. `docs/config-schema.md` changes

- `stated_aims.json` section: revert to documenting `compatible_bug_flavors` as a flat list of
  flavor-id strings (undoing the second edit made earlier this session). Keep
  `severity_tiers_supported` documentation as-is.
- Remove the `bug_aim_relation.json` section entirely.
- Consistency rules: remove the `compatible_bug_flavors[].flavor_id` bullet (revert to
  "every `compatible_bug_flavors` entry must match an id in `bug_flavor.json`"), keep the
  `severity_tiers_supported` bullet.

## 6. Pipeline code changes (`scripts/vignette_gen/`)

- **`cells.py`**: `Cell` drops the `bug_aim_relation` field. `enumerate_cells` becomes a simple
  `aim × compatible_bug_flavors × severity_tiers_supported` cross (no relation-branching logic).
  `cell_id` becomes `f"{aim_id}__{bug_flavor}__{severity_tier}"`; `item_id` stays
  `f"{cell_id}__{sample_idx:03d}"`.
- **`prompt.py`**: `build_prompt` drops all `bug_aim_relation`-related parameters, constants
  (`AIM_DEFEATING_INSTRUCTION` etc.), and template slots. `TEMPLATE` drops the `BUG_AIM_RELATION`
  section entirely.
- **`orchestrate.py`**: no direct references to `bug_aim_relation` today beyond what flows through
  `item` dicts built by `cells.py` — should need no logic changes beyond whatever field-name churn
  cells.py's shape change causes.
- **`writer.py`**: no direct references — item dicts are passed through opaquely.
- **All corresponding tests** (`test_cells.py`, `test_prompt.py`, `test_orchestrate.py`, and any
  fixture data in `test_config.py`/`test_generate_items_cli.py` that embeds a `bug_aim_relation`
  field) need updating to the new shape.

## 7. Cleanup

- Delete the 5 existing pilot items in `data/items/` (built under the old schema — inconsistent
  with the new one, not worth migrating).
- `config/bug_aim_relation.json` file deleted.

## Out of scope for this design

- Re-running the pilot batch under the new schema — that's an implementation-plan/execution step,
  not a design decision.
- Any changes to `severity_tier.json`, the other 6 `bug_flavor` definitions, or `author_labels.json`
  — untouched by this change.
- Populating `judge_models.json`/`rival_model_pool.json` — explicitly left to the user's
  collaborator, per earlier conversation.
