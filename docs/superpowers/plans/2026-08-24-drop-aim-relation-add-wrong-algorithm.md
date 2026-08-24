# Drop bug_aim_relation, Add wrong_algorithm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `bug_aim_relation` as a crossed experimental factor from the config, docs, and
already-implemented `vignette_gen` pipeline, and add a new exploratory `wrong_algorithm`
`bug_flavor` in its place.

**Architecture:** This modifies an already-built, already-tested pipeline rather than building
from scratch. Config content changes land first (Tasks 1-3), then the two pipeline modules that
actually branch on `bug_aim_relation` (`config.py`'s validation loop, `cells.py`'s enumeration,
`prompt.py`'s template) get updated test-first, then `orchestrate.py`'s test fixtures get updated
(orchestrate.py itself has no `bug_aim_relation`-specific logic, so needs no code change), then
docs are brought back in sync, then a full-suite + dry-run verification, then cleanup of the 5
stale pilot items built under the old schema.

**Tech Stack:** Python 3.9, `pytest`, existing `vignette_gen` package conventions.

Reference spec: [`docs/superpowers/specs/2026-08-24-drop-aim-relation-add-wrong-algorithm-design.md`](../specs/2026-08-24-drop-aim-relation-add-wrong-algorithm-design.md).

---

### Task 1: Add `wrong_algorithm` to `config/bug_flavor.json`

**Files:**
- Modify: `config/bug_flavor.json`

- [ ] **Step 1: Add a 7th entry to the `levels` array**

The file currently ends with the `known_trap` entry's closing `}` followed by `]` and `}`. Add a
new entry after `known_trap` (before the closing `]`):

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

Make sure the `known_trap` entry's closing `}` now has a trailing comma before this new entry.

- [ ] **Step 2: Validate the JSON parses and has 7 levels**

Run: `python3 -c "import json; d=json.load(open('config/bug_flavor.json')); assert len(d['levels'])==7; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add config/bug_flavor.json
git commit -m "Add wrong_algorithm bug_flavor"
```

---

### Task 2: Update `config/stated_aims.json`

**Files:**
- Modify: `config/stated_aims.json`

- [ ] **Step 1: Replace the file contents**

Flattens `compatible_bug_flavors` from `{flavor_id, orthogonal_plausible}` objects back to a flat
list of flavor-id strings, and adds `"wrong_algorithm"` to `compute_average`, `shipping_cost`, and
`celsius_to_fahrenheit`:

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

- [ ] **Step 2: Validate the JSON parses and still has 20 aims**

Run: `python3 -c "import json; d=json.load(open('config/stated_aims.json')); assert len(d['aims'])==20; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add config/stated_aims.json
git commit -m "Flatten compatible_bug_flavors and add wrong_algorithm to 3 aims"
```

---

### Task 3: Delete `config/bug_aim_relation.json`

**Files:**
- Delete: `config/bug_aim_relation.json`

- [ ] **Step 1: Delete the file**

```bash
rm config/bug_aim_relation.json
```

- [ ] **Step 2: Commit**

```bash
git add -A -- config/bug_aim_relation.json
git commit -m "Delete unused bug_aim_relation.json"
```

---

### Task 4: Update `scripts/vignette_gen/config.py` and its tests

**Files:**
- Modify: `scripts/vignette_gen/config.py`
- Modify: `tests/test_config.py`

The loader's validation loop currently assumes `compatible_bug_flavors` entries are
`{flavor_id, orthogonal_plausible}` objects (`entry["flavor_id"]`). Since Task 2 flattened this to
plain strings, the loop must change first, otherwise every fixture/real-config load will raise
`TypeError: string indices must be integers`.

- [ ] **Step 1: Update the failing tests first**

Replace `tests/test_config.py` in full:

```python
import json
from pathlib import Path

import pytest

from vignette_gen.config import load_config


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


def test_load_config_rejects_unknown_bug_flavor(tmp_path):
    _write_json(tmp_path / "bug_flavor.json", {"levels": [{"id": "logic_error"}]})
    _write_json(tmp_path / "severity_tier.json", {"levels": [{"id": "trivial"}]})
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "bad_aim",
                    "text": "x",
                    "severity_tiers_supported": ["trivial"],
                    "compatible_bug_flavors": ["not_a_real_flavor"],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="not_a_real_flavor"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_unknown_severity_tier(tmp_path):
    _write_json(tmp_path / "bug_flavor.json", {"levels": [{"id": "logic_error"}]})
    _write_json(tmp_path / "severity_tier.json", {"levels": [{"id": "trivial"}]})
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "bad_aim",
                    "text": "x",
                    "severity_tiers_supported": ["not_a_real_tier"],
                    "compatible_bug_flavors": ["logic_error"],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="not_a_real_tier"):
        load_config(config_dir=tmp_path)


def test_load_config_indexes_flavors_and_severities_by_id(tmp_path):
    _write_json(
        tmp_path / "bug_flavor.json",
        {"levels": [{"id": "logic_error", "definition": "d"}]},
    )
    _write_json(
        tmp_path / "severity_tier.json",
        {"levels": [{"id": "trivial", "definition": "d"}]},
    )
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "aim_1",
                    "text": "x",
                    "severity_tiers_supported": ["trivial"],
                    "compatible_bug_flavors": ["logic_error"],
                }
            ]
        },
    )

    config = load_config(config_dir=tmp_path)

    assert config["bug_flavor"]["logic_error"]["definition"] == "d"
    assert config["severity_tier"]["trivial"]["definition"] == "d"
    assert config["stated_aims"][0]["id"] == "aim_1"


def test_real_config_loads_without_error():
    config = load_config()
    assert len(config["bug_flavor"]) == 7
    assert len(config["severity_tier"]) == 2
    assert len(config["stated_aims"]) == 20
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: `test_load_config_rejects_unknown_bug_flavor` and `test_load_config_indexes_flavors_and_severities_by_id` FAIL with a `TypeError` from the old `entry["flavor_id"]` indexing; `test_real_config_loads_without_error` FAILS on the `== 7` assertion (still 6 until config.py changes, but Task 1 already added the 7th to the real file, so this one may already pass — the important failures are the `TypeError`s from the object-vs-string mismatch).

- [ ] **Step 3: Update `scripts/vignette_gen/config.py`'s validation loop**

Find:
```python
    for aim in stated_aims:
        for entry in aim["compatible_bug_flavors"]:
            if entry["flavor_id"] not in bug_flavor:
                raise ValueError(
                    f"aim '{aim['id']}' references unknown bug_flavor '{entry['flavor_id']}'"
                )
        for tier in aim["severity_tiers_supported"]:
            if tier not in severity_tier:
                raise ValueError(
                    f"aim '{aim['id']}' references unknown severity_tier '{tier}'"
                )
```

Replace with:
```python
    for aim in stated_aims:
        for flavor_id in aim["compatible_bug_flavors"]:
            if flavor_id not in bug_flavor:
                raise ValueError(
                    f"aim '{aim['id']}' references unknown bug_flavor '{flavor_id}'"
                )
        for tier in aim["severity_tiers_supported"]:
            if tier not in severity_tier:
                raise ValueError(
                    f"aim '{aim['id']}' references unknown severity_tier '{tier}'"
                )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/config.py tests/test_config.py
git commit -m "Flatten config loader's compatible_bug_flavors validation"
```

---

### Task 5: Update `scripts/vignette_gen/cells.py` and its tests

**Files:**
- Modify: `scripts/vignette_gen/cells.py`
- Modify: `tests/test_cells.py`

- [ ] **Step 1: Replace the failing tests first**

Replace `tests/test_cells.py` in full:

```python
from vignette_gen.cells import enumerate_cells, expand_items

STATED_AIMS = [
    {
        "id": "aim_a",
        "severity_tiers_supported": ["trivial", "significant"],
        "compatible_bug_flavors": ["logic_error", "missing_edge_case"],
    }
]


def test_enumerate_cells_crosses_flavor_and_severity():
    cells = enumerate_cells(STATED_AIMS)
    cell_ids = {c.cell_id for c in cells}

    assert "aim_a__logic_error__trivial" in cell_ids
    assert "aim_a__logic_error__significant" in cell_ids
    assert "aim_a__missing_edge_case__trivial" in cell_ids
    assert "aim_a__missing_edge_case__significant" in cell_ids

    assert len(cells) == 4


def test_expand_items_appends_sample_index_and_keeps_cell_id():
    cells = enumerate_cells(STATED_AIMS)
    items = expand_items(cells[:1], samples_per_cell=3)

    assert [item["item_id"] for item in items] == [
        f"{cells[0].cell_id}__000",
        f"{cells[0].cell_id}__001",
        f"{cells[0].cell_id}__002",
    ]
    assert all(item["cell_id"] == cells[0].cell_id for item in items)
    assert [item["sample_idx"] for item in items] == [0, 1, 2]


def test_expand_items_with_higher_sample_count_is_a_superset():
    cells = enumerate_cells(STATED_AIMS)
    small = expand_items(cells[:1], samples_per_cell=1)
    large = expand_items(cells[:1], samples_per_cell=3)

    small_ids = {item["item_id"] for item in small}
    large_ids = {item["item_id"] for item in large}

    assert small_ids.issubset(large_ids)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_cells.py -v`
Expected: FAIL — old `enumerate_cells` expects `compatible_bug_flavors` entries to be dicts
(`flavor_entry["orthogonal_plausible"]`) and will raise `TypeError` against the new flat-string
fixture.

- [ ] **Step 3: Replace `scripts/vignette_gen/cells.py` in full**

```python
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Cell:
    aim_id: str
    bug_flavor: str
    severity_tier: str

    @property
    def cell_id(self) -> str:
        return f"{self.aim_id}__{self.bug_flavor}__{self.severity_tier}"


def enumerate_cells(stated_aims: List[Dict]) -> List[Cell]:
    cells = []
    for aim in stated_aims:
        for bug_flavor in aim["compatible_bug_flavors"]:
            for severity_tier in aim["severity_tiers_supported"]:
                cells.append(Cell(aim["id"], bug_flavor, severity_tier))
    return cells


def expand_items(cells: List[Cell], samples_per_cell: int) -> List[Dict]:
    items = []
    for cell in cells:
        for sample_idx in range(samples_per_cell):
            items.append(
                {
                    "item_id": f"{cell.cell_id}__{sample_idx:03d}",
                    "cell_id": cell.cell_id,
                    "sample_idx": sample_idx,
                    "aim_id": cell.aim_id,
                    "bug_flavor": cell.bug_flavor,
                    "severity_tier": cell.severity_tier,
                }
            )
    return items
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_cells.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/cells.py tests/test_cells.py
git commit -m "Drop bug_aim_relation from cell/item enumeration"
```

---

### Task 6: Update `scripts/vignette_gen/prompt.py` and its tests

**Files:**
- Modify: `scripts/vignette_gen/prompt.py`
- Modify: `tests/test_prompt.py`

- [ ] **Step 1: Replace the failing tests first**

Replace `tests/test_prompt.py` in full:

```python
import pytest

from vignette_gen.prompt import build_prompt

CONFIG = {
    "stated_aims": [
        {"id": "aim_a", "text": "Compute the average of a list of numbers."}
    ],
    "bug_flavor": {
        "missing_edge_case": {
            "id": "missing_edge_case",
            "definition": "DEF-MEC",
            "reference": "REF-MEC",
            "examples": [{"source": "SRC", "note": "NOTE"}],
        }
    },
    "severity_tier": {
        "trivial": {"id": "trivial", "definition": "DEF-TRIVIAL", "reference": "REF-TRIVIAL"}
    },
}


def _item():
    return {
        "aim_id": "aim_a",
        "bug_flavor": "missing_edge_case",
        "severity_tier": "trivial",
    }


def test_prompt_includes_aim_flavor_and_severity_content():
    prompt = build_prompt(_item(), CONFIG)

    assert "Compute the average of a list of numbers." in prompt
    assert "DEF-MEC" in prompt
    assert "REF-MEC" in prompt
    assert "SRC - NOTE" in prompt
    assert "DEF-TRIVIAL" in prompt
    assert "REF-TRIVIAL" in prompt


def test_prompt_handles_no_examples():
    config = {
        **CONFIG,
        "bug_flavor": {
            "missing_edge_case": {
                **CONFIG["bug_flavor"]["missing_edge_case"],
                "examples": [],
            }
        },
    }
    prompt = build_prompt(_item(), config)
    assert "(none documented)" in prompt


def test_build_prompt_raises_clear_error_for_unknown_aim_id():
    item = _item()
    item["aim_id"] = "does_not_exist"
    with pytest.raises(ValueError, match="does_not_exist"):
        build_prompt(item, CONFIG)


def test_build_prompt_preserves_braces_in_config_content():
    config = {
        **CONFIG,
        "stated_aims": [
            {"id": "aim_a", "text": "Do something with a dict like {'key': 'value'}."}
        ],
    }
    prompt = build_prompt(_item(), config)
    assert "Do something with a dict like {'key': 'value'}." in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_prompt.py -v`
Expected: FAIL — old `build_prompt` requires `item["bug_aim_relation"]`, which the new `_item()`
fixture no longer provides, so it will raise `KeyError`.

- [ ] **Step 3: Replace `scripts/vignette_gen/prompt.py` in full**

```python
from typing import Dict, List

TEMPLATE = """You are generating a single Python function for a research study on how
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
- The function body should be approximately 5-25 lines (signature through
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
{{
  "code": "<code string>",
  "rationale": "<short technical note on what the bug is and where it is in the code - for human vetting only, never shown to judge models>"
}}
"""


def _render_examples(examples: List[Dict]) -> str:
    if not examples:
        return "(none documented)"
    return "; ".join(f"{ex['source']} - {ex['note']}" for ex in examples)


def build_prompt(item: Dict, config: Dict) -> str:
    aim = next((a for a in config["stated_aims"] if a["id"] == item["aim_id"]), None)
    if aim is None:
        raise ValueError(f"unknown aim_id: {item['aim_id']!r}")

    flavor = config["bug_flavor"][item["bug_flavor"]]
    severity = config["severity_tier"][item["severity_tier"]]

    return TEMPLATE.format(
        stated_aim_text=aim["text"],
        bug_flavor_id=flavor["id"],
        bug_flavor_definition=flavor["definition"],
        bug_flavor_reference=flavor["reference"],
        bug_flavor_examples=_render_examples(flavor["examples"]),
        severity_tier_id=severity["id"],
        severity_tier_definition=severity["definition"],
        severity_tier_reference=severity["reference"],
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_prompt.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/prompt.py tests/test_prompt.py
git commit -m "Drop bug_aim_relation from prompt builder"
```

---

### Task 7: Update `tests/test_orchestrate.py` fixtures

**Files:**
- Modify: `tests/test_orchestrate.py`

`scripts/vignette_gen/orchestrate.py` itself has no `bug_aim_relation`-specific logic (it only
passes `item` dicts through opaquely to `build_prompt`/`write_item`), so it needs no code change.
Only the test fixtures need updating to the new item shape.

- [ ] **Step 1: Update the `ITEM` fixture**

Find:
```python
ITEM = {
    "item_id": "aim_a__missing_edge_case__trivial__aim_defeating__000",
    "cell_id": "aim_a__missing_edge_case__trivial__aim_defeating",
    "sample_idx": 0,
    "aim_id": "aim_a",
    "bug_flavor": "missing_edge_case",
    "severity_tier": "trivial",
    "bug_aim_relation": "aim_defeating",
}
```

Replace with:
```python
ITEM = {
    "item_id": "aim_a__missing_edge_case__trivial__000",
    "cell_id": "aim_a__missing_edge_case__trivial",
    "sample_idx": 0,
    "aim_id": "aim_a",
    "bug_flavor": "missing_edge_case",
    "severity_tier": "trivial",
}
```

- [ ] **Step 2: Run the full orchestrate test file**

Run: `pytest tests/test_orchestrate.py -v`
Expected: 9 passed (all existing tests reference `ITEM`/`CONFIG` only, no other
`bug_aim_relation`-specific assertions exist in this file — confirm this by checking the output
has no failures, not just that it runs).

- [ ] **Step 3: Commit**

```bash
git add tests/test_orchestrate.py
git commit -m "Update test_orchestrate.py fixtures for dropped bug_aim_relation"
```

---

### Task 8: Update `docs/design.md`

**Files:**
- Modify: `docs/design.md`

- [ ] **Step 1: Remove the `bug_aim_relation` row from the manipulated-factors table**

Find:
```markdown
| `bug_aim_relation` | `aim_defeating`, `aim_orthogonal` | Does the bug undermine exactly what the function was stated to do, or is it incidental to that stated purpose? Independent of `severity_tier` (severity = technical consequence; aim_relation = relationship to stated purpose) and independent of `bug_flavor` (any flavor can in principle be either relation — see §1a). Constructed independently per item (not as matched pairs — see §1a): not every flavor naturally supports both relations for an arbitrary stated aim, and forcing a matched sibling for every item was judged not worth the construction cost. Analyzed as a between-item comparison, clustered by `item_id`. |
| `severity_tier` | `trivial`, `significant` | Property of the planted bug itself (technical consequence), held constant across all label/aim-relation cells for a given item. |
| `bug_flavor` | `missing_edge_case`, `logic_error`, `security_vulnerability`, `silent_failure` (core); `copy_paste_residue`, `known_trap` (exploratory, optional) | Not a primary test factor, but should be balanced across items so competence/carelessness/malice narratives have room to differ; worth exploratory `bug_flavor:author_label` and `bug_flavor:bug_aim_relation` interactions. See §1a for definitions, examples, and predicted folk-psych profile per flavor. |
```

Replace with:
```markdown
| `severity_tier` | `trivial`, `significant` | Property of the planted bug itself (technical consequence), held constant across all label cells for a given item. |
| `bug_flavor` | `missing_edge_case`, `logic_error`, `security_vulnerability`, `silent_failure` (core); `copy_paste_residue`, `known_trap`, `wrong_algorithm` (exploratory, optional) | Not a primary test factor, but should be balanced across items so competence/carelessness/malice narratives have room to differ; worth an exploratory `bug_flavor:author_label` interaction. See §1a for definitions, examples, and predicted folk-psych profile per flavor. |
```

- [ ] **Step 2: Remove the "Constructing `bug_aim_relation` instances" subsection**

Find (entire block, from the heading through the paragraph ending "...both be constructed from
the same specific item."):
```markdown
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
```

Replace with nothing (delete the block entirely, including its blank lines, leaving the
surrounding sections' spacing intact — i.e. exactly one blank line between the "Recommended
allocation" paragraph above it and the "## 2. Prompt template" heading below it).

- [ ] **Step 3: Add `wrong_algorithm` to the Exploratory flavor table and update "Recommended allocation"**

Find:
```markdown
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
```

Replace with:
```markdown
**Exploratory (optional)**

| Flavor | Example | Predicted profile |
|---|---|---|
| `copy_paste_residue` | Leftover debug print; a variable copy-pasted from a similar function that doesn't match context; dead/commented-out code. | Uniquely diagnostic of carelessness over competence — a stray `print("here")` rarely reads as a skill gap. Cleanest diligence-lapse prototype, complementing `silent_failure`. |
| `known_trap` | Mutable default argument (Python); floating-point equality comparison; integer overflow where easy to forget. | Predicted lowest blame across the board regardless of label — strong "even experts fall into this" folk narrative. Second low-signal contrast to `missing_edge_case`. Risk: judge models may not uniformly recognize a given trap as "classic," which is itself a confound — treat as lower-priority than the other five. |
| `wrong_algorithm` | Computes a sum when asked for an average with no division step anywhere; sorts ascending when descending was asked; checks the wrong field entirely. | Predicted to read as clearly competence-diagnostic once spotted — unlike `missing_edge_case`/`logic_error`, there's no "everyone misses this" framing available, since the code doesn't even attempt the right computation. Best flavor for testing whether label bias survives an unambiguous, low-effort-to-verify failure. Distinct from `known_trap`'s "even experts fall into this" framing — reads more like "didn't understand the task" than "forgot a subtlety." |

Recommended allocation: use `missing_edge_case`, `logic_error`,
`security_vulnerability`, `silent_failure` for the primary factorial
(spans ambiguous/diagnostic and competence/diligence/norm-violation
contrasts). Add `copy_paste_residue`, `known_trap`, and `wrong_algorithm`
only if the item bank can support the extra cells without underpowering
the core set.
```

- [ ] **Step 4: Update the `AIM_SENTENCE` prompt-template section**

Find:
```markdown
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

`CODE_BLOCK` is the fixed buggy snippet for that item/severity
tier/aim-relation cell, identical across every `author_label` cell.
```

Replace with:
```markdown
One fixed sentence per item, stating the plain functional purpose — not
manipulated:

> "This function is supposed to {STATED_AIM, e.g. 'validate a
> password-reset token before allowing a password change' / 'sort a
> list of files by extension'}."

`STATED_AIM` is fixed per item and identical across every
`author_label` cell for that item.

`CODE_BLOCK` is the fixed buggy snippet for that item/severity-tier
cell, identical across every `author_label` cell.
```

- [ ] **Step 5: Remove `bug_aim_relation` from the response schema**

Find:
```markdown
```
item_id, judge_family, judge_tuning, author_label,
bug_aim_relation, severity_tier, bug_flavor, question_type,
scale_response, reasoning_text, authorship_belief_raw,
authorship_belief_coded
```
```

Replace with:
```markdown
```
item_id, judge_family, judge_tuning, author_label,
severity_tier, bug_flavor, question_type,
scale_response, reasoning_text, authorship_belief_raw,
authorship_belief_coded
```
```

- [ ] **Step 6: Drop H3, renumber H4 to H3**

Find:
```markdown
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
```

Replace with:
```markdown
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
```

- [ ] **Step 7: Update the exploratory set's flavor-interaction bullet**

Find:
```markdown
- `bug_flavor:author_label` and `bug_flavor:bug_aim_relation` —
  whether the aim-defeating bump or the label effect concentrates in
  particular flavors (e.g. `silent_failure`, `security_vulnerability`)
  rather than appearing uniformly.
```

Replace with:
```markdown
- `bug_flavor:author_label` — whether the label effect concentrates in
  particular flavors (e.g. `silent_failure`, `security_vulnerability`,
  `wrong_algorithm`) rather than appearing uniformly.
```

- [ ] **Step 8: Update §7's open items — remove the resolved `bug_aim_relation` bullet and the
now-stale cell-count math**

Find:
```markdown
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
```

Replace with:
```markdown
- Whether q_intentionality/q_explanation/q_blame should all run on
  every item for every label cell, or whether a partial (Latin-square)
  design is needed to keep elicitation cost tractable — the design is
  `author_label` (6) × `severity_tier` (2) × `bug_flavor` (4 core), i.e.
  48 cells per item before even multiplying by question type; full
  crossing on every item is likely not affordable, so decide early
  whether to (a) run the full cross on a small number of items, or (b)
  run a reduced label set (e.g. drop one of `other_model_A/B` or
  `human_developer`) on more items.
- Number and diversity of `bug_flavor` items needed per severity tier to
  support the exploratory `bug_flavor:author_label` interaction without
  under-powering the primary tests.
```

- [ ] **Step 9: Commit**

```bash
git add docs/design.md
git commit -m "Remove bug_aim_relation factor and H3 from design.md; add wrong_algorithm"
```

---

### Task 9: Update `docs/generation-prompt.md`

**Files:**
- Modify: `docs/generation-prompt.md`

- [ ] **Step 1: Simplify the "Scope decision" section**

Find:
```markdown
## Scope decision: one code version per call

Each generation call produces a **single** `CODE_BLOCK` for one specific
`(stated_aim, bug_flavor, severity_tier, bug_aim_relation)` combination —
not a matched aim-defeating/aim-orthogonal pair. `bug_aim_relation` is
constructed independently per item (see `design.md` §1a) rather than as
matched pairs, since not every `stated_aim` naturally supports a
plausible instance of both relations, and forcing a matched sibling for
every item raised construction cost without a proportional analytical
gain (`bug_aim_relation` is analyzed between-item, clustered by
`item_id`).
```

Replace with:
```markdown
## Scope decision: one code version per call

Each generation call produces a **single** `CODE_BLOCK` for one specific
`(stated_aim, bug_flavor, severity_tier)` combination.
```

- [ ] **Step 2: Remove the `BUG_AIM_RELATION` block from the prompt template**

Find (inside the fenced template code block):
```
SEVERITY_TIER: {severity_tier_id}
Definition: {severity_tier_definition}
Reference/grounding: {severity_tier_reference}

BUG_AIM_RELATION: {bug_aim_relation_id}
[if aim_defeating] Position the bug so it breaks exactly what STATED_AIM
promises - it undermines the stated purpose directly.
[if aim_orthogonal] Position the bug so it is incidental to STATED_AIM -
the stated purpose still works correctly, but the bug affects something
else in the function.

Before answering, verify: [if aim_defeating] does the code fail
STATED_AIM specifically because of the bug? [if aim_orthogonal] does the
code still fully satisfy STATED_AIM despite the bug? If not, revise
before returning.

Return JSON with exactly these fields:
```

Replace with:
```
SEVERITY_TIER: {severity_tier_id}
Definition: {severity_tier_definition}
Reference/grounding: {severity_tier_reference}

Return JSON with exactly these fields:
```

- [ ] **Step 3: Remove the "Known risk: aim-relation placement" section entirely**

Find (entire section, from the heading through the paragraph ending "...especially in early
batches."):
```markdown
## Known risk: aim-relation placement may not always be achievable

Not every `stated_aim` has enough internal structure to support a
genuine `aim_orthogonal` placement — a single-purpose function with no
peripheral steps leaves nowhere incidental to put the bug. This is more
likely for simple, single-step aims than for aims with multiple sub-steps
(e.g. "validate a token" has a peripheral logging step; "add two numbers"
does not). The self-verification instruction above is meant to catch the
generator fooling itself on this point, but this remains the most
failure-prone part of generation and warrants closer human review than
other fields, especially in early batches.
```

Replace with nothing (delete the block entirely, leaving exactly one blank line between the
"`rationale` field is an informal vetting aid" section above it and the "Sourcing pre-vetted
examples" section below it).

- [ ] **Step 4: Add `wrong_algorithm` to the low-volume/hand-constructed sourcing note**

Find:
```markdown
**`copy_paste_residue` / `known_trap`** — no large corpus to mine; these
stay lower-volume, hand-constructed from the ~10-15 well-known Python
gotchas and manually written copy-paste examples. This matches their
already lower-priority/exploratory status in `design.md` §1a.
```

Replace with:
```markdown
**`copy_paste_residue` / `known_trap` / `wrong_algorithm`** — no large
corpus to mine; these stay lower-volume, hand-constructed from the
~10-15 well-known Python gotchas, manually written copy-paste examples,
and hand-written wrong-algorithm substitutions respectively. This
matches their already lower-priority/exploratory status in `design.md`
§1a.
```

- [ ] **Step 5: Remove the stale "Open items" bullet about aim-relation placement risk**

Find:
```markdown
- Whether to pilot-generate a small batch first to validate the
  aim-relation placement risk noted above before committing to a larger
  generation run.
```

Replace with nothing (delete this bullet; it's the last bullet in the "Open items" list, so no
other list items are affected — leave the list's final remaining bullet as the new last line).

- [ ] **Step 6: Commit**

```bash
git add docs/generation-prompt.md
git commit -m "Remove bug_aim_relation from generation-prompt.md"
```

---

### Task 10: Update `docs/config-schema.md`

**Files:**
- Modify: `docs/config-schema.md`

- [ ] **Step 1: Update the "Why these files exist" section**

Find:
```markdown
`design.md` fixes the experimental factor *names* (`author_label`,
`bug_aim_relation`, `severity_tier`, `bug_flavor`) but leaves two kinds of
detail unresolved, which is what this config fills in:

1. **Classification rubrics** for factors that require judgment calls —
   `bug_flavor` and `severity_tier` — so that whoever builds or labels items
   applies the same criteria. (`author_label` and `bug_aim_relation` don't
   need this: their levels are already unambiguous as defined.)
```

Replace with:
```markdown
`design.md` fixes the experimental factor *names* (`author_label`,
`severity_tier`, `bug_flavor`) but leaves two kinds of detail unresolved,
which is what this config fills in:

1. **Classification rubrics** for factors that require judgment calls —
   `bug_flavor` and `severity_tier` — so that whoever builds or labels items
   applies the same criteria. (`author_label` doesn't need this: its levels
   are already unambiguous as defined.)
```

- [ ] **Step 2: Update the `author_labels.json` section's cross-reference**

Find:
```markdown
The `author_label` factor's levels, with the literal sentence template used
in the prompt's `AUTHOR_SENTENCE` slot (design.md §2). Unlike `bug_flavor`/
`severity_tier`/`bug_aim_relation`, `author_label` is spoken directly in the
prompt text, so the generator needs the actual sentence, not just a tag.
```

Replace with:
```markdown
The `author_label` factor's levels, with the literal sentence template used
in the prompt's `AUTHOR_SENTENCE` slot (design.md §2). Unlike `bug_flavor`/
`severity_tier`, `author_label` is spoken directly in the prompt text, so the
generator needs the actual sentence, not just a tag.
```

- [ ] **Step 3: Remove the `config/bug_aim_relation.json` section entirely**

Find:
```markdown
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

```

Replace with nothing (delete the entire section including its trailing blank line, so the
`### config/severity_tier.json` heading directly follows the `author_labels.json` section with
normal single-blank-line spacing).

- [ ] **Step 4: Add `wrong_algorithm` to the `bug_flavor.json` documentation**

Find:
```markdown
- `known_trap`: community-documented Python gotchas (e.g. mutable default
  arguments) — informal consensus, not a formal taxonomy; treat as
  lower-confidence than the CWE/mutation-testing-grounded flavors, consistent
  with design.md's own flag on this flavor.
```

Replace with:
```markdown
- `known_trap`: community-documented Python gotchas (e.g. mutable default
  arguments) — informal consensus, not a formal taxonomy; treat as
  lower-confidence than the CWE/mutation-testing-grounded flavors, consistent
  with design.md's own flag on this flavor.
- `wrong_algorithm`: Chillarege et al.'s Orthogonal Defect Classification
  (ODC) — the 'Function' defect type (clean code that implements the wrong
  computation entirely), distinct from ODC's 'Algorithm' type which covers
  logic/efficiency issues within an otherwise-correct approach.
```

Find:
```json
    {"id": "copy_paste_residue", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "known_trap", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"}
  ]
}
```

Replace with:
```json
    {"id": "copy_paste_residue", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "known_trap", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"},
    {"id": "wrong_algorithm", "category": "exploratory", "definition": "", "examples": [], "reference": "...", "status": "todo"}
  ]
}
```

- [ ] **Step 5: Revert the `stated_aims.json` section to a flat-list schema**

Find:
```markdown
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
```

Replace with:
```markdown
### `config/stated_aims.json`

Populated with `stated_aim` text used in the prompt's `AIM_SENTENCE` slot (design.md §2), plus two
construction-constraint fields:

- `compatible_bug_flavors`: a flat list of `bug_flavor.json` ids this aim can plausibly support.
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
  "compatible_bug_flavors": ["..."]
}
```
```

- [ ] **Step 6: Update the consistency rules bullet**

Find:
```markdown
- Every `compatible_bug_flavors[].flavor_id` entry in `stated_aims.json` must match an `id` present
  in `bug_flavor.json`.
```

Replace with:
```markdown
- Every `compatible_bug_flavors` entry in `stated_aims.json` must match an `id` present in
  `bug_flavor.json`.
```

- [ ] **Step 7: Commit**

```bash
git add docs/config-schema.md
git commit -m "Revert stated_aims.json schema docs to flat list; remove bug_aim_relation.json section"
```

---

### Task 11: Full test suite and dry-run verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: all tests pass (46 total: 4 config + 3 cells + 12 validate + 4 prompt + 7 writer + 5
client + 9 orchestrate + 2 CLI — note this is fewer than the pre-redesign 49, since `test_prompt.py`
goes from 7 tests to 4 as part of Task 6 (three tests that specifically covered
`bug_aim_relation` behavior are removed, not replaced 1:1); all other test files keep their
current counts).

- [ ] **Step 2: Dry-run a handful of items against the real config**

Run: `python scripts/generate_items.py --dry-run --limit 3`
Expected: prints 3 built prompts, none containing `BUG_AIM_RELATION`, each containing a concrete
`STATED_AIM`, `BUG_FLAVOR`, and `SEVERITY_TIER` section. No errors, no API key needed.

- [ ] **Step 3: Confirm the new cell/item count**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, 'scripts')
from vignette_gen.config import load_config
from vignette_gen.cells import enumerate_cells, expand_items
config = load_config()
cells = enumerate_cells(config['stated_aims'])
items = expand_items(cells, samples_per_cell=1)
print(f'{len(cells)} cells, {len(items)} items at samples_per_cell=1')
"
```
Expected: a specific cell/item count with no errors — this number will be noticeably smaller than
the pre-redesign 50, since removing the `bug_aim_relation` cross roughly halves the enumeration
(offset slightly upward by the 3 new `wrong_algorithm` cells).

---

### Task 12: Delete stale pilot items

**Files:**
- Delete: `data/items/*.json` (the 5 files generated under the old schema)

- [ ] **Step 1: Remove the stale items**

```bash
rm -f data/items/*.json
ls data/items/
```
Expected: empty (or the directory itself may not exist if `data/items/` had no other contents —
either is fine, `generate_items.py` recreates it via `write_item`'s `mkdir(parents=True,
exist_ok=True)`).

Note: `data/` is gitignored, so this is a local-only cleanup — no commit needed for this step.

---

## Notes for whoever runs the next real generation batch

- The item bank is now smaller than before this redesign (no more `bug_aim_relation` cross), so a
  full-batch run costs proportionally fewer API calls than it would have pre-redesign.
- `wrong_algorithm` items are brand new and unvalidated against a real model — the first batch that
  includes them warrants an extra close look to confirm the model actually produces "clean code,
  wrong computation" rather than smuggling in a `logic_error`-style single-operator bug instead
  (the distinguishing test in `config/bug_flavor.json`'s definition exists precisely to guard
  against this ambiguity during human vetting).
