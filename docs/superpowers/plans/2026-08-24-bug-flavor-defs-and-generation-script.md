# Bug-Flavor Definitions and Vignette Generation Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill in the `bug_flavor`/`severity_tier`/`stated_aims` config content per the approved design, and build a working `scripts/generate_items.py` that calls the Anthropic API to generate, validate, and save buggy-code vignettes to `data/items/`.

**Architecture:** A small `scripts/vignette_gen/` package with one focused module per responsibility (config loading, cell/item enumeration, prompt building, code validation, API client, output writing, run orchestration), each unit-tested independently with a fake API client so the test suite never makes real network calls. `scripts/generate_items.py` is a thin CLI wrapper around `vignette_gen.orchestrate.run`. Config content changes (Tasks 2–5) land first since the script's tests exercise the real config files as a consistency check.

**Tech Stack:** Python 3.9 (matches the system interpreter in this environment — avoid 3.10+-only syntax like `X | Y` union types; use `typing.Optional`/`typing.List` instead), `anthropic` SDK, `pytest`, stdlib `ast`/`tokenize` for code validation.

Reference spec: [`docs/superpowers/specs/2026-08-24-bug-flavor-defs-and-generation-script-design.md`](../specs/2026-08-24-bug-flavor-defs-and-generation-script-design.md).

---

### Task 1: Python environment and test scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
anthropic>=0.40.0
pytest>=7.4.0
```

- [ ] **Step 2: Create the venv and install dependencies**

Run:
```bash
cd /Users/mer_home/Documents/Me/Research/llm_authors
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Expected: both packages install without error. `.venv/` is already covered by `.gitignore`.

- [ ] **Step 3: Create root `conftest.py` so tests can import the `vignette_gen` package**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt conftest.py
git commit -m "Add Python environment scaffolding for generation script"
```

---

### Task 2: Fill in `config/bug_flavor.json` definitions and references

**Files:**
- Modify: `config/bug_flavor.json`

- [ ] **Step 1: Replace the file contents**

Write the full file (preserves existing `examples`/`category` fields, fills `definition`/`reference`, sets `status` to `"done"`):

```json
{
  "levels": [
    {
      "id": "missing_edge_case",
      "category": "core",
      "definition": "A function that is correct on the input space it was clearly designed for, but produces a wrong result, crash, or undefined behavior on a boundary or degenerate input the stated aim implies it should handle (empty input, single-element input, exact-threshold value, None/null, extreme numeric value). The core algorithm/logic path is correct; the defect is a missing branch or boundary check, not a wrong operator or wrong formula on the main path.",
      "examples": [
        {
          "source": "QuixBugs (MIT License, (c) James Koppel) - python_programs/find_in_sorted.py",
          "note": "Recursive binary search; the upper-half recursive call is `binsearch(mid, end)` instead of `binsearch(mid + 1, end)`, an off-by-one boundary bug."
        }
      ],
      "reference": "Offutt et al., mutation testing boundary/statement operators (e.g. `<` to `<=` boundary-shift mutants); QuixBugs benchmark (Lin & Koppel, MIT license) for real single-line Python examples in this family, e.g. python_programs/find_in_sorted.py's off-by-one recursive bound.",
      "status": "done"
    },
    {
      "id": "logic_error",
      "category": "core",
      "definition": "A function whose main-path computation or control flow is wrong for ordinary, non-edge inputs - a swapped/wrong comparison operator, inverted boolean condition, wrong arithmetic operator, or misordered control flow - such that it produces an incorrect result on typical inputs, not just at a boundary. Distinguished from missing_edge_case by being wrong in the common case, not just the rare one.",
      "examples": [
        {
          "source": "QuixBugs (MIT License, (c) James Koppel) - python_programs/bitcount.py",
          "note": "Kernighan's bit-count trick uses `n ^= n - 1` instead of `n &= n - 1` - a wrong bitwise operator (XOR swapped for AND) that produces an incorrect count on the main path, not just an edge case."
        }
      ],
      "reference": "Offutt et al.'s mutation operators - ROR (Relational Operator Replacement), COR (Conditional Operator Replacement), AOR (Arithmetic Operator Replacement); QuixBugs benchmark, e.g. python_programs/bitcount.py's `n ^= n - 1` vs. correct `n &= n - 1`.",
      "status": "done"
    },
    {
      "id": "security_vulnerability",
      "category": "core",
      "definition": "A function that handles untrusted input, credentials, or an access-control decision in a way that maps to a named CWE category. The vulnerability must be the kind identifiable by a static-analysis rule, not a vague 'insecure-sounding' pattern - every instance should cite the specific CWE it instantiates. Toy/illustrative only: no working exploit payloads, no real credentials or endpoints, no code intended to run against a live system.",
      "examples": [],
      "reference": "MITRE CWE-89 (SQL Injection), CWE-798 (Use of Hard-coded Credentials), CWE-306 (Missing Authentication for Critical Function), CWE-287 (Improper Authentication), CWE-639 (Authorization Bypass Through User-Controlled Key, i.e. IDOR). Static-analysis correspondence: Bandit B105-B107 (hardcoded passwords), B608 (SQL injection via string-built query), and Bandit's own examples/ test files for these rules.",
      "status": "done"
    },
    {
      "id": "silent_failure",
      "category": "core",
      "definition": "A function that catches an exception, checks a return/status code, or detects an error condition, and then continues execution without surfacing it (no re-raise, no logging, no return of an error indicator) - the failure must be detected and discarded by the code, not simply unhandled (an uncaught exception is missing_edge_case/logic_error, not silent_failure - the defining feature here is a swallowed error, not an absent check).",
      "examples": [],
      "reference": "CWE-1069 (Empty Exception Block), CWE-703 (Improper Check or Handling of Exceptional Conditions); codified in Bandit rule B110 (try_except_pass) and CodeQL's empty-except query (py/empty-except).",
      "status": "done"
    },
    {
      "id": "copy_paste_residue",
      "category": "exploratory",
      "definition": "A function containing an artifact clearly left over from adapting/duplicating other code rather than a reasoning error: a stray debug print/logging statement, a variable copied from a similar function whose name or value no longer matches its new context, or dead/commented-out code. Distinguishing test: would a reviewer describe this as 'forgot to clean up,' not 'got the logic wrong'?",
      "examples": [],
      "reference": "Fowler, Refactoring: Improving the Design of Existing Code (2nd ed.) code-smell catalog - 'Duplicated Code' and 'Dead Code' entries. Informal practitioner reference, not a numbered standard.",
      "status": "done"
    },
    {
      "id": "known_trap",
      "category": "exploratory",
      "definition": "A function that falls into one of a small, community-documented list of Python-specific gotchas (mutable default argument, `is` vs `==` on small ints/strings, late-binding closures in a loop, floating-point equality comparison, integer-division behavior). Restrict to traps that appear in standard references - do not invent novel 'trap' categories, since this flavor's whole rationale is a shared, recognizable folk list.",
      "examples": [],
      "reference": "Real Python, 'Common Gotchas For Python Developers'; The Hitchhiker's Guide to Python, 'Common Gotchas' section. Informal community consensus, not a formal taxonomy - treat as lower-confidence than the CWE/mutation-testing-grounded flavors.",
      "status": "done"
    }
  ]
}
```

- [ ] **Step 2: Validate the JSON parses**

Run: `python3 -c "import json; json.load(open('config/bug_flavor.json'))"`
Expected: no output (no exception).

- [ ] **Step 3: Commit**

```bash
git add config/bug_flavor.json
git commit -m "Fill in bug_flavor definitions and references"
```

---

### Task 3: Fill in `config/severity_tier.json` definitions and references

**Files:**
- Modify: `config/severity_tier.json`

- [ ] **Step 1: Replace the file contents**

```json
{
  "levels": [
    {
      "id": "trivial",
      "definition": "The bug's blast radius is confined to a single call/output - wrong value returned, incorrect item skipped/included, or a crash on an atypical input - with no persistent, cascading, or cross-user effect. Data already stored elsewhere is unaffected; no unauthorized access occurs.",
      "examples": [],
      "reference": "Conceptually modeled on CVSS v3.1's Confidentiality/Integrity/Availability impact dimensions (FIRST.org, CVSS v3.1 Specification) - self-authored rather than a CVSS score, since CVSS doesn't apply to non-security bugs.",
      "status": "done"
    },
    {
      "id": "significant",
      "definition": "The bug can affect data or access beyond the single call - corrupts/persists wrong state, silently drops data other code depends on, or (for security_vulnerability) allows unauthorized data exposure/modification or credential compromise. 'Silently drops data other code depends on' is scoped to structured, multi-field values that other code configures/drives itself from (e.g. a parsed config object missing a field) - not any scalar value a caller happens to act on.",
      "examples": [],
      "reference": "Conceptually modeled on CVSS v3.1's Confidentiality/Integrity/Availability impact dimensions (FIRST.org, CVSS v3.1 Specification) - self-authored rather than a CVSS score, since CVSS doesn't apply to non-security bugs.",
      "status": "done"
    }
  ]
}
```

- [ ] **Step 2: Validate the JSON parses**

Run: `python3 -c "import json; json.load(open('config/severity_tier.json'))"`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add config/severity_tier.json
git commit -m "Fill in severity_tier definitions and references"
```

---

### Task 4: Populate `config/stated_aims.json`

**Files:**
- Modify: `config/stated_aims.json`

- [ ] **Step 1: Replace the file contents**

```json
{
  "aims": [
    {"id": "compute_average", "text": "Compute the average of a list of numbers.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "missing_edge_case", "orthogonal_plausible": false}]},
    {"id": "parse_csv_header", "text": "Parse a CSV header line into a list of non-blank column names.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "missing_edge_case", "orthogonal_plausible": false}, {"flavor_id": "logic_error", "orthogonal_plausible": false}]},
    {"id": "discount_eligibility", "text": "Determine whether a user is eligible for a discount based on their account balance exceeding a threshold.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "logic_error", "orthogonal_plausible": false}]},
    {"id": "sort_students_by_grade", "text": "Sort a list of student records by grade in descending order, and report the number of tied grades in a stats dict.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "logic_error", "orthogonal_plausible": true}]},
    {"id": "authenticate_user", "text": "Authenticate a user by checking a submitted password against a stored password hash before granting access.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "security_vulnerability", "orthogonal_plausible": false}]},
    {"id": "catalog_lookup", "text": "Look up a product by ID in a catalog dictionary that also stores each product's owning seller, and return its details only if the requesting user is the owning seller.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "security_vulnerability", "orthogonal_plausible": false}]},
    {"id": "reset_token_validation", "text": "Validate a password-reset token before allowing a password change.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "silent_failure", "orthogonal_plausible": true}, {"flavor_id": "logic_error", "orthogonal_plausible": false}, {"flavor_id": "security_vulnerability", "orthogonal_plausible": true}, {"flavor_id": "missing_edge_case", "orthogonal_plausible": false}]},
    {"id": "average_temperature", "text": "Read a list of temperature readings and return their average.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "silent_failure", "orthogonal_plausible": true}, {"flavor_id": "missing_edge_case", "orthogonal_plausible": false}]},
    {"id": "add_note", "text": "Append a new note to a user's list of notes, creating a fresh list if none was provided.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "known_trap", "orthogonal_plausible": false}]},
    {"id": "cart_total", "text": "Calculate the total price of items in a cart after applying a fixed shipping fee.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "copy_paste_residue", "orthogonal_plausible": true}]},
    {"id": "process_order_batch", "text": "Process a batch of pending orders and return the list of order IDs that were successfully charged.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "missing_edge_case", "orthogonal_plausible": false}]},
    {"id": "validate_username_length", "text": "Check that a username is at least 3 characters long before allowing account creation, and track single-character attempts for abuse monitoring.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "missing_edge_case", "orthogonal_plausible": true}]},
    {"id": "shipping_cost", "text": "Calculate the shipping cost for a package based on its weight tier.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "logic_error", "orthogonal_plausible": false}]},
    {"id": "is_freezing", "text": "Determine whether a temperature reading in Celsius represents freezing conditions (at or below 0 degrees).", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "logic_error", "orthogonal_plausible": false}]},
    {"id": "job_status_auth", "text": "Check that the caller is an authorized internal service before returning the health-check status of a background job.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "security_vulnerability", "orthogonal_plausible": false}]},
    {"id": "public_profile_lookup", "text": "Look up a user's public profile information by username.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "security_vulnerability", "orthogonal_plausible": false}]},
    {"id": "parse_config", "text": "Parse a JSON configuration string and return the parsed dictionary, filling in a default retry count if one isn't present.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "silent_failure", "orthogonal_plausible": true}]},
    {"id": "process_orders_revenue", "text": "Process a batch of orders and calculate the total revenue.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "silent_failure", "orthogonal_plausible": false}]},
    {"id": "rename_files", "text": "Rename all files in a list by appending a given suffix before the file extension.", "severity_tiers_supported": ["trivial", "significant"], "compatible_bug_flavors": [{"flavor_id": "copy_paste_residue", "orthogonal_plausible": true}]},
    {"id": "celsius_to_fahrenheit", "text": "Convert a temperature from Celsius to Fahrenheit.", "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": [{"flavor_id": "known_trap", "orthogonal_plausible": false}]}
  ]
}
```

- [ ] **Step 2: Validate the JSON parses and has 20 aims**

Run: `python3 -c "import json; d=json.load(open('config/stated_aims.json')); assert len(d['aims'])==20; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add config/stated_aims.json
git commit -m "Populate stated_aims.json with 20 seed aims"
```

---

### Task 5: Update `docs/config-schema.md` for the new `stated_aims.json` shape

**Files:**
- Modify: `docs/config-schema.md`

- [ ] **Step 1: Replace the `stated_aims.json` section**

Find the existing section (starting `### \`config/stated_aims.json\`` through its closing code block and "Each entry..." line) and replace it with:

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

- [ ] **Step 2: Update the "Consistency rules" section**

Find:
```markdown
- Every `compatible_bug_flavors` entry in `stated_aims.json` must match an `id` present in
  `bug_flavor.json`.
```

Replace with:
```markdown
- Every `compatible_bug_flavors[].flavor_id` entry in `stated_aims.json` must match an `id` present
  in `bug_flavor.json`.
- Every `severity_tiers_supported` entry in `stated_aims.json` must match an `id` present in
  `severity_tier.json`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/config-schema.md
git commit -m "Update config-schema.md for new stated_aims.json shape"
```

---

### Task 6: `vignette_gen` package skeleton + `config.py`

**Files:**
- Create: `scripts/vignette_gen/__init__.py`
- Create: `scripts/vignette_gen/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create the package skeleton**

```bash
mkdir -p scripts/vignette_gen tests
touch scripts/vignette_gen/__init__.py
```

- [ ] **Step 2: Write the failing tests**

`tests/test_config.py`:
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
                    "compatible_bug_flavors": [
                        {"flavor_id": "not_a_real_flavor", "orthogonal_plausible": False}
                    ],
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
                    "compatible_bug_flavors": [
                        {"flavor_id": "logic_error", "orthogonal_plausible": False}
                    ],
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
                    "compatible_bug_flavors": [
                        {"flavor_id": "logic_error", "orthogonal_plausible": False}
                    ],
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
    assert len(config["bug_flavor"]) == 6
    assert len(config["severity_tier"]) == 2
    assert len(config["stated_aims"]) == 20
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.config'` (or similar import failure).

- [ ] **Step 4: Write `scripts/vignette_gen/config.py`**

```python
import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_json(config_dir: Path, name: str) -> dict:
    return json.loads((config_dir / name).read_text())


def load_config(config_dir: Optional[Path] = None) -> Dict:
    config_dir = config_dir or DEFAULT_CONFIG_DIR

    bug_flavor = {lvl["id"]: lvl for lvl in _load_json(config_dir, "bug_flavor.json")["levels"]}
    severity_tier = {
        lvl["id"]: lvl for lvl in _load_json(config_dir, "severity_tier.json")["levels"]
    }
    stated_aims = _load_json(config_dir, "stated_aims.json")["aims"]

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

    return {
        "bug_flavor": bug_flavor,
        "severity_tier": severity_tier,
        "stated_aims": stated_aims,
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/vignette_gen/__init__.py scripts/vignette_gen/config.py tests/test_config.py
git commit -m "Add vignette_gen config loader with consistency checks"
```

---

### Task 7: `cells.py` — cell and item enumeration

**Files:**
- Create: `scripts/vignette_gen/cells.py`
- Create: `tests/test_cells.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cells.py`:
```python
from vignette_gen.cells import enumerate_cells, expand_items

STATED_AIMS = [
    {
        "id": "aim_a",
        "severity_tiers_supported": ["trivial", "significant"],
        "compatible_bug_flavors": [
            {"flavor_id": "logic_error", "orthogonal_plausible": True},
            {"flavor_id": "missing_edge_case", "orthogonal_plausible": False},
        ],
    }
]


def test_enumerate_cells_crosses_flavor_severity_and_relation():
    cells = enumerate_cells(STATED_AIMS)
    cell_ids = {c.cell_id for c in cells}

    # logic_error supports both relations for both severities: 2 x 2 = 4
    assert "aim_a__logic_error__trivial__aim_defeating" in cell_ids
    assert "aim_a__logic_error__trivial__aim_orthogonal" in cell_ids
    assert "aim_a__logic_error__significant__aim_defeating" in cell_ids
    assert "aim_a__logic_error__significant__aim_orthogonal" in cell_ids

    # missing_edge_case only supports aim_defeating: 2 severities x 1 relation = 2
    assert "aim_a__missing_edge_case__trivial__aim_defeating" in cell_ids
    assert "aim_a__missing_edge_case__trivial__aim_orthogonal" not in cell_ids
    assert "aim_a__missing_edge_case__significant__aim_defeating" in cell_ids

    assert len(cells) == 6


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
Expected: `ModuleNotFoundError: No module named 'vignette_gen.cells'`

- [ ] **Step 3: Write `scripts/vignette_gen/cells.py`**

```python
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Cell:
    aim_id: str
    bug_flavor: str
    severity_tier: str
    bug_aim_relation: str

    @property
    def cell_id(self) -> str:
        return f"{self.aim_id}__{self.bug_flavor}__{self.severity_tier}__{self.bug_aim_relation}"


def enumerate_cells(stated_aims: List[Dict]) -> List[Cell]:
    cells = []
    for aim in stated_aims:
        for flavor_entry in aim["compatible_bug_flavors"]:
            relations = ["aim_defeating"]
            if flavor_entry["orthogonal_plausible"]:
                relations.append("aim_orthogonal")
            for severity_tier in aim["severity_tiers_supported"]:
                for relation in relations:
                    cells.append(
                        Cell(aim["id"], flavor_entry["flavor_id"], severity_tier, relation)
                    )
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
                    "bug_aim_relation": cell.bug_aim_relation,
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
git commit -m "Add cell/item enumeration with sample-index item ids"
```

---

### Task 8: `validate.py` — generated code validator

**Files:**
- Create: `scripts/vignette_gen/validate.py`
- Create: `tests/test_validate.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_validate.py`:
```python
import pytest

from vignette_gen.validate import ValidationError, validate_code

GOOD_CODE = """def compute_average(numbers):
    total = 0
    count = 0
    for number in numbers:
        total += number
        count += 1
    if count == 0:
        return 0
    return total / count
"""

GOOD_CODE_WITH_IMPORT = """import json


def parse_config(raw):
    data = json.loads(raw)
    retries = data.get("retries")
    if retries is None:
        data["retries"] = 3
    return data
"""

GOOD_CODE_WITH_MIDFUNCTION_TRIPLE_QUOTE = '''def build_query(user_id):
    query = """
    SELECT * FROM users
    WHERE id = %s
    """
    return query % user_id
'''


def test_valid_code_passes():
    validate_code(GOOD_CODE)


def test_valid_code_with_leading_import_passes():
    validate_code(GOOD_CODE_WITH_IMPORT)


def test_midfunction_triple_quoted_string_is_not_a_docstring():
    validate_code(GOOD_CODE_WITH_MIDFUNCTION_TRIPLE_QUOTE)


def test_syntax_error_is_rejected():
    with pytest.raises(ValidationError, match="syntax"):
        validate_code("def broken(:\n    pass\n")


def test_docstring_as_first_statement_is_rejected():
    code = '''def f(x):
    """docstring"""
    return x
'''
    with pytest.raises(ValidationError, match="docstring"):
        validate_code(code)


def test_comment_is_rejected():
    code = """def f(x):
    y = x + 1  # add one
    return y
"""
    with pytest.raises(ValidationError, match="comment"):
        validate_code(code)


def test_nested_function_is_rejected():
    code = """def outer(x):
    def inner(y):
        return y
    return inner(x)
"""
    with pytest.raises(ValidationError, match="nested"):
        validate_code(code)


def test_top_level_class_is_rejected():
    code = """class Foo:
    def f(self, x):
        return x
"""
    with pytest.raises(ValidationError, match="class"):
        validate_code(code)


def test_too_few_lines_is_rejected():
    code = """def f(x):
    return x
"""
    with pytest.raises(ValidationError, match="8-25"):
        validate_code(code)


def test_too_many_lines_is_rejected():
    body_lines = "\n".join(f"    x += {i}" for i in range(30))
    code = f"def f(x):\n{body_lines}\n    return x\n"
    with pytest.raises(ValidationError, match="8-25"):
        validate_code(code)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_validate.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.validate'`

- [ ] **Step 3: Write `scripts/vignette_gen/validate.py`**

```python
import ast
import io
import tokenize

MIN_BODY_LINES = 8
MAX_BODY_LINES = 25


class ValidationError(Exception):
    pass


def _has_comment(code: str) -> bool:
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    return any(tok.type == tokenize.COMMENT for tok in tokens)


def _is_docstring_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def validate_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValidationError(f"syntax error: {exc}") from exc

    top_level_funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    top_level_classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    top_level_other = [
        n
        for n in tree.body
        if not isinstance(n, (ast.FunctionDef, ast.Import, ast.ImportFrom))
    ]

    if top_level_classes:
        raise ValidationError("top-level class definition not allowed")
    if len(top_level_funcs) != 1:
        raise ValidationError(
            f"expected exactly one top-level function, found {len(top_level_funcs)}"
        )
    if top_level_other:
        raise ValidationError(
            "only leading import statements and one function definition allowed at top level"
        )

    func = top_level_funcs[0]

    for node in ast.walk(func):
        if node is not func and isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            raise ValidationError("nested function or class not allowed")

    if func.body and _is_docstring_expr(func.body[0]):
        raise ValidationError("docstring not allowed")

    if _has_comment(code):
        raise ValidationError("comment not allowed")

    body_line_count = func.body[-1].end_lineno - func.lineno + 1
    if not (MIN_BODY_LINES <= body_line_count <= MAX_BODY_LINES):
        raise ValidationError(
            f"function body has {body_line_count} lines, expected {MIN_BODY_LINES}-{MAX_BODY_LINES}"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_validate.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/validate.py tests/test_validate.py
git commit -m "Add generated-code validator (syntax, structure, docstring, comment checks)"
```

---

### Task 9: `prompt.py` — prompt builder

**Files:**
- Create: `scripts/vignette_gen/prompt.py`
- Create: `tests/test_prompt.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_prompt.py`:
```python
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


def _item(bug_aim_relation):
    return {
        "aim_id": "aim_a",
        "bug_flavor": "missing_edge_case",
        "severity_tier": "trivial",
        "bug_aim_relation": bug_aim_relation,
    }


def test_prompt_includes_aim_flavor_and_severity_content():
    prompt = build_prompt(_item("aim_defeating"), CONFIG)

    assert "Compute the average of a list of numbers." in prompt
    assert "DEF-MEC" in prompt
    assert "REF-MEC" in prompt
    assert "SRC - NOTE" in prompt
    assert "DEF-TRIVIAL" in prompt
    assert "REF-TRIVIAL" in prompt


def test_prompt_aim_defeating_instruction():
    prompt = build_prompt(_item("aim_defeating"), CONFIG)
    assert "undermines the stated purpose directly" in prompt
    assert "does the code fail STATED_AIM specifically because of the bug?" in prompt


def test_prompt_aim_orthogonal_instruction():
    prompt = build_prompt(_item("aim_orthogonal"), CONFIG)
    assert "incidental to STATED_AIM" in prompt
    assert "does the code still fully satisfy STATED_AIM despite the bug?" in prompt


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
    prompt = build_prompt(_item("aim_defeating"), config)
    assert "(none documented)" in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_prompt.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.prompt'`

- [ ] **Step 3: Write `scripts/vignette_gen/prompt.py`**

```python
from typing import Dict, List

AIM_DEFEATING_INSTRUCTION = (
    "Position the bug so it breaks exactly what STATED_AIM promises - it "
    "undermines the stated purpose directly."
)
AIM_ORTHOGONAL_INSTRUCTION = (
    "Position the bug so it is incidental to STATED_AIM - the stated "
    "purpose still works correctly, but the bug affects something else "
    "in the function."
)
AIM_DEFEATING_VERIFICATION = "does the code fail STATED_AIM specifically because of the bug?"
AIM_ORTHOGONAL_VERIFICATION = "does the code still fully satisfy STATED_AIM despite the bug?"

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
- The function body should be approximately 8-25 lines (signature through
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

BUG_AIM_RELATION: {bug_aim_relation_id}
{bug_aim_relation_instruction}

Before answering, verify: {bug_aim_relation_verification} If not, revise
before returning.

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
    aim = next(a for a in config["stated_aims"] if a["id"] == item["aim_id"])
    flavor = config["bug_flavor"][item["bug_flavor"]]
    severity = config["severity_tier"][item["severity_tier"]]

    if item["bug_aim_relation"] == "aim_defeating":
        instruction = AIM_DEFEATING_INSTRUCTION
        verification = AIM_DEFEATING_VERIFICATION
    else:
        instruction = AIM_ORTHOGONAL_INSTRUCTION
        verification = AIM_ORTHOGONAL_VERIFICATION

    return TEMPLATE.format(
        stated_aim_text=aim["text"],
        bug_flavor_id=flavor["id"],
        bug_flavor_definition=flavor["definition"],
        bug_flavor_reference=flavor["reference"],
        bug_flavor_examples=_render_examples(flavor["examples"]),
        severity_tier_id=severity["id"],
        severity_tier_definition=severity["definition"],
        severity_tier_reference=severity["reference"],
        bug_aim_relation_id=item["bug_aim_relation"],
        bug_aim_relation_instruction=instruction,
        bug_aim_relation_verification=verification,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_prompt.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/prompt.py tests/test_prompt.py
git commit -m "Add prompt builder for generation-prompt.md template"
```

---

### Task 10: `writer.py` — output writer and resume support

**Files:**
- Create: `scripts/vignette_gen/writer.py`
- Create: `tests/test_writer.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_writer.py`:
```python
import json

from vignette_gen.writer import append_failure, item_exists, write_item


def test_item_exists_false_when_missing(tmp_path):
    assert item_exists(tmp_path, "some_item") is False


def test_write_item_then_item_exists_true(tmp_path):
    write_item(tmp_path, "some_item", {"code": "x = 1"})
    assert item_exists(tmp_path, "some_item") is True


def test_write_item_creates_parent_dir(tmp_path):
    output_dir = tmp_path / "nested" / "items"
    write_item(output_dir, "some_item", {"code": "x = 1"})
    assert (output_dir / "some_item.json").exists()


def test_write_item_content_round_trips(tmp_path):
    record = {"item_id": "some_item", "code": "x = 1", "sample_idx": 0}
    write_item(tmp_path, "some_item", record)
    loaded = json.loads((tmp_path / "some_item.json").read_text())
    assert loaded == record


def test_append_failure_writes_one_json_line_per_call(tmp_path):
    failures_path = tmp_path / "failures.jsonl"
    append_failure(failures_path, {"item_id": "a", "error": "boom"})
    append_failure(failures_path, {"item_id": "b", "error": "boom2"})

    lines = failures_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["item_id"] == "a"
    assert json.loads(lines[1])["item_id"] == "b"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_writer.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.writer'`

- [ ] **Step 3: Write `scripts/vignette_gen/writer.py`**

```python
import json
from pathlib import Path


def _item_path(output_dir: Path, item_id: str) -> Path:
    return output_dir / f"{item_id}.json"


def item_exists(output_dir: Path, item_id: str) -> bool:
    return _item_path(output_dir, item_id).exists()


def write_item(output_dir: Path, item_id: str, record: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _item_path(output_dir, item_id).write_text(json.dumps(record, indent=2))


def append_failure(failures_path: Path, record: dict) -> None:
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    with failures_path.open("a") as f:
        f.write(json.dumps(record) + "\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_writer.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/writer.py tests/test_writer.py
git commit -m "Add item writer with resume-friendly per-item file layout"
```

---

### Task 11: `client.py` — Anthropic API wrapper

**Files:**
- Create: `scripts/vignette_gen/client.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write the failing test**

This only checks that the wrapper constructs correctly and calls the SDK the way we expect — it does not make a real network call.

`tests/test_client.py`:
```python
from vignette_gen.client import GenerationClient


class _FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs

        class _Content:
            text = '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'

        class _Response:
            content = [_Content()]

        return _Response()


class _FakeAnthropic:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.messages = _FakeMessages()


def test_generate_calls_sdk_with_model_and_prompt(monkeypatch):
    monkeypatch.setattr("vignette_gen.client.anthropic.Anthropic", _FakeAnthropic)

    client = GenerationClient(model="claude-sonnet-5", api_key="fake-key")
    result = client.generate("hello prompt")

    assert result == '{"code": "def f(x):\\n    return x\\n", "rationale": "none"}'
    assert client._client.messages.last_kwargs["model"] == "claude-sonnet-5"
    assert client._client.messages.last_kwargs["messages"] == [
        {"role": "user", "content": "hello prompt"}
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_client.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.client'`

- [ ] **Step 3: Write `scripts/vignette_gen/client.py`**

```python
from typing import Optional

import anthropic


class GenerationClient:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_client.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/client.py tests/test_client.py
git commit -m "Add Anthropic API client wrapper for generation calls"
```

---

### Task 12: `orchestrate.py` — retry loop and run orchestration

**Files:**
- Create: `scripts/vignette_gen/orchestrate.py`
- Create: `tests/test_orchestrate.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_orchestrate.py`:
```python
import json

from vignette_gen.orchestrate import RunOptions, generate_one, run

CONFIG = {
    "stated_aims": [
        {"id": "aim_a", "text": "Compute the average of a list of numbers."}
    ],
    "bug_flavor": {
        "missing_edge_case": {
            "id": "missing_edge_case",
            "definition": "DEF",
            "reference": "REF",
            "examples": [],
        }
    },
    "severity_tier": {
        "trivial": {"id": "trivial", "definition": "DEF", "reference": "REF"}
    },
}

ITEM = {
    "item_id": "aim_a__missing_edge_case__trivial__aim_defeating__000",
    "cell_id": "aim_a__missing_edge_case__trivial__aim_defeating",
    "sample_idx": 0,
    "aim_id": "aim_a",
    "bug_flavor": "missing_edge_case",
    "severity_tier": "trivial",
    "bug_aim_relation": "aim_defeating",
}

GOOD_CODE = "def f(x):\n    total = 0\n    for n in x:\n        total += n\n    if not x:\n        return 0\n    return total / len(x)\n"


class _ScriptedClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return self._responses.pop(0)


def test_generate_one_returns_code_and_rationale_on_first_success():
    client = _ScriptedClient(
        [json.dumps({"code": GOOD_CODE, "rationale": "off-by-one on empty list"})]
    )

    result = generate_one(client, ITEM, CONFIG, max_retries=3)

    assert result["code"] == GOOD_CODE
    assert result["rationale"] == "off-by-one on empty list"
    assert client.calls == 1


def test_generate_one_retries_on_invalid_code_then_succeeds():
    client = _ScriptedClient(
        [
            json.dumps({"code": "not valid python(", "rationale": "bad"}),
            json.dumps({"code": GOOD_CODE, "rationale": "good"}),
        ]
    )

    result = generate_one(client, ITEM, CONFIG, max_retries=3)

    assert result["code"] == GOOD_CODE
    assert client.calls == 2


def test_generate_one_raises_after_exhausting_retries():
    client = _ScriptedClient([json.dumps({"code": "bad(", "rationale": "x"})] * 3)

    try:
        generate_one(client, ITEM, CONFIG, max_retries=3)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    assert client.calls == 3


def test_run_writes_item_and_reports_counts(tmp_path):
    client = _ScriptedClient(
        [json.dumps({"code": GOOD_CODE, "rationale": "off-by-one on empty list"})]
    )
    options = RunOptions(
        model="claude-sonnet-5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    def fake_load_config():
        return CONFIG

    def fake_build_items(config, samples_per_cell, limit):
        return [ITEM]

    counts = run(client, options, load_config_fn=fake_load_config, build_items_fn=fake_build_items)

    assert counts == {"generated": 1, "skipped": 0, "failed": 0}
    written = json.loads((tmp_path / "items" / f"{ITEM['item_id']}.json").read_text())
    assert written["code"] == GOOD_CODE
    assert written["cell_id"] == ITEM["cell_id"]
    assert written["generation_model"] == "claude-sonnet-5"


def test_run_skips_existing_item_without_calling_client(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir(parents=True)
    (items_dir / f"{ITEM['item_id']}.json").write_text("{}")

    client = _ScriptedClient([])  # would raise IndexError if called
    options = RunOptions(
        model="claude-sonnet-5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=items_dir,
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 1, "failed": 0}


def test_run_records_failure_and_continues(tmp_path):
    client = _ScriptedClient([json.dumps({"code": "bad(", "rationale": "x"})] * 3)
    options = RunOptions(
        model="claude-sonnet-5",
        samples_per_cell=1,
        limit=1,
        dry_run=False,
        overwrite=False,
        max_retries=3,
        items_dir=tmp_path / "items",
        failures_path=tmp_path / "failures.jsonl",
    )

    counts = run(
        client,
        options,
        load_config_fn=lambda: CONFIG,
        build_items_fn=lambda config, samples_per_cell, limit: [ITEM],
    )

    assert counts == {"generated": 0, "skipped": 0, "failed": 1}
    failures = (tmp_path / "failures.jsonl").read_text().splitlines()
    assert len(failures) == 1
    assert json.loads(failures[0])["item_id"] == ITEM["item_id"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_orchestrate.py -v`
Expected: `ModuleNotFoundError: No module named 'vignette_gen.orchestrate'`

- [ ] **Step 3: Write `scripts/vignette_gen/orchestrate.py`**

```python
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from .cells import enumerate_cells, expand_items
from .config import load_config as _default_load_config
from .prompt import build_prompt
from .validate import ValidationError, validate_code
from .writer import append_failure, item_exists, write_item

PROMPT_VERSION = "2026-08-24-v1"


@dataclass
class RunOptions:
    model: str
    samples_per_cell: int
    limit: Optional[int]
    dry_run: bool
    overwrite: bool
    max_retries: int
    items_dir: Path
    failures_path: Path


def _default_build_items(config: Dict, samples_per_cell: int, limit: Optional[int]):
    cells = enumerate_cells(config["stated_aims"])
    items = expand_items(cells, samples_per_cell)
    if limit is not None:
        items = items[:limit]
    return items


def generate_one(client, item: Dict, config: Dict, max_retries: int) -> Dict:
    last_error = None
    for _ in range(max_retries):
        prompt = build_prompt(item, config)
        try:
            raw = client.generate(prompt)
            parsed = json.loads(raw)
            code = parsed["code"]
            rationale = parsed["rationale"]
            validate_code(code)
            return {"code": code, "rationale": rationale}
        except (json.JSONDecodeError, KeyError, ValidationError) as exc:
            last_error = str(exc)
    raise RuntimeError(f"failed after {max_retries} attempts: {last_error}")


def run(
    client,
    options: RunOptions,
    load_config_fn: Callable[[], Dict] = _default_load_config,
    build_items_fn: Callable = _default_build_items,
) -> Dict:
    config = load_config_fn()
    items = build_items_fn(config, options.samples_per_cell, options.limit)

    if options.dry_run:
        for item in items:
            print(f"=== {item['item_id']} ===")
            print(build_prompt(item, config))
        return {"generated": 0, "skipped": 0, "failed": 0}

    generated = skipped = failed = 0
    for item in items:
        if not options.overwrite and item_exists(options.items_dir, item["item_id"]):
            skipped += 1
            continue
        try:
            result = generate_one(client, item, config, options.max_retries)
        except RuntimeError as exc:
            append_failure(options.failures_path, {**item, "error": str(exc)})
            failed += 1
            continue

        record = {
            **item,
            "code": result["code"],
            "rationale": result["rationale"],
            "generation_model": options.model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION,
        }
        write_item(options.items_dir, item["item_id"], record)
        generated += 1
        print(f"generated {item['item_id']}")

    print(f"done: {generated} generated, {skipped} skipped, {failed} failed")
    return {"generated": generated, "skipped": skipped, "failed": failed}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_orchestrate.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/vignette_gen/orchestrate.py tests/test_orchestrate.py
git commit -m "Add generation run orchestration with retry and resume logic"
```

---

### Task 13: `scripts/generate_items.py` — CLI entrypoint

**Files:**
- Create: `scripts/generate_items.py`
- Create: `tests/test_generate_items_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_generate_items_cli.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_items import parse_args  # noqa: E402


def test_parse_args_defaults():
    args = parse_args([])
    assert args.model == "claude-sonnet-5"
    assert args.samples_per_cell == 1
    assert args.limit is None
    assert args.dry_run is False
    assert args.overwrite is False
    assert args.max_retries == 3


def test_parse_args_overrides():
    args = parse_args(
        [
            "--model",
            "claude-opus-5",
            "--samples-per-cell",
            "5",
            "--limit",
            "10",
            "--dry-run",
            "--overwrite",
            "--max-retries",
            "1",
        ]
    )
    assert args.model == "claude-opus-5"
    assert args.samples_per_cell == 5
    assert args.limit == 10
    assert args.dry_run is True
    assert args.overwrite is True
    assert args.max_retries == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_generate_items_cli.py -v`
Expected: `ModuleNotFoundError: No module named 'generate_items'`

- [ ] **Step 3: Write `scripts/generate_items.py`**

```python
#!/usr/bin/env python3
import argparse
from pathlib import Path

from vignette_gen.client import GenerationClient
from vignette_gen.orchestrate import RunOptions, run

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate buggy-code vignettes via the Anthropic API."
    )
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--samples-per-cell", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    options = RunOptions(
        model=args.model,
        samples_per_cell=args.samples_per_cell,
        limit=args.limit,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        max_retries=args.max_retries,
        items_dir=DATA_DIR / "items",
        failures_path=DATA_DIR / "failures.jsonl",
    )
    client = None if args.dry_run else GenerationClient(model=args.model)
    run(client, options)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_generate_items_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_items.py tests/test_generate_items_cli.py
git commit -m "Add generate_items.py CLI entrypoint"
```

---

### Task 14: Full test suite run

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: all tests across `tests/test_config.py`, `tests/test_cells.py`, `tests/test_validate.py`, `tests/test_prompt.py`, `tests/test_writer.py`, `tests/test_client.py`, `tests/test_orchestrate.py`, `tests/test_generate_items_cli.py` pass (32 tests total). No real API calls are made anywhere in this run.

---

### Task 15: Dry-run sanity check against the real config

**Files:** none (verification only)

- [ ] **Step 1: Dry-run a handful of items and eyeball the prompts**

Run: `python scripts/generate_items.py --dry-run --limit 3`
Expected: prints 3 fully-built prompts (one per item), each containing a concrete `STATED_AIM`, the matching `bug_flavor` definition/reference, the `severity_tier` definition/reference, and the correct `aim_defeating`/`aim_orthogonal` instruction — no errors, no API calls made (this doesn't require `ANTHROPIC_API_KEY` to be set).

- [ ] **Step 2: Confirm the total cell/item count matches expectations**

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
Expected: a specific cell/item count with no errors (sanity check that enumeration runs cleanly end-to-end against the real config — the exact number isn't pre-specified here since it falls directly out of the `stated_aims.json` content from Task 4).

---

### Task 16: Real pilot generation run

**Files:** none (verification only; writes to `data/items/`, which is gitignored)

- [ ] **Step 1: Set the API key for this shell session**

Ask the user to run (not you — this is a secret):
```bash
export ANTHROPIC_API_KEY=sk-...
```

- [ ] **Step 2: Run a small real pilot**

Run: `python scripts/generate_items.py --limit 5`
Expected: output like `generated <item_id>` five times, ending with `done: 5 generated, 0 skipped, 0 failed` (a `failed` count above 0 is not necessarily fatal — check `data/failures.jsonl` for the reason if so; it likely means either the model didn't return parseable JSON or the returned code didn't pass validation, both retried up to 3 times automatically already).

- [ ] **Step 3: Inspect a generated item**

Run: `cat data/items/*.json | head -50` (or open one file directly)
Expected: valid JSON with `item_id`, `cell_id`, `sample_idx`, `aim_id`, `bug_flavor`, `severity_tier`, `bug_aim_relation`, `code`, `rationale`, `generation_model`, `timestamp`, `prompt_version` — and `code` should read as a plausible, toy Python function matching its declared `bug_flavor`/`bug_aim_relation`.

- [ ] **Step 4: Re-run with the same limit to confirm resume/skip behavior**

Run: `python scripts/generate_items.py --limit 5`
Expected: `done: 0 generated, 5 skipped, 0 failed` — confirms the resume-by-`item_id` check works and no duplicate API calls happen on a re-run.

---

## Notes for whoever reviews the generated pilot batch

- `rationale` is a screening aid only, not verified ground truth (see the generation-prompt.md doc) — a human should still read the 5 pilot items and confirm each one actually reads as its declared `bug_flavor`/`bug_aim_relation`/`severity_tier` before trusting a larger batch.
- `aim_orthogonal` items are the highest-risk category per the design doc's own flag — if any of the 5 pilot items happen to be `aim_orthogonal`, give those an extra close look.
- If several pilot items land in `data/failures.jsonl`, look at which `bug_flavor`/`bug_aim_relation` combination is failing before scaling up — it may indicate the prompt's `Definition`/`Reference` text for that flavor needs to be more directive, or that a specific aim's `orthogonal_plausible: true` call in Task 4 was too optimistic.
