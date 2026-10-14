import json

import pytest

from multi_model_attribution import _paths  # noqa: F401

CLEAN = "def compute_average(values):\n    if not values:\n        return None\n    total = 0\n    count = 0\n    for v in values:\n        total += v\n        count += 1\n    return total / count"
BUGGY = "def compute_average(values):\n    if not values:\n        return None\n    total = 0\n    count = 0\n    for v in values:\n        total += v\n        count += 1\n    return total"
CORRECT = "def report_average(values):\n    avg = compute_average(values)\n    scaled = avg * 2\n    return round(scaled, 1)"
VIOLATING = "def report_average(values):\n    avg = compute_average([])\n    scaled = avg * 2\n    return round(scaled, 1)"


@pytest.fixture
def record():
    return {"source_item_id": "compute_average__wrong_algorithm__gpt5__000", "bank": "items_gpt5",
            "aim_id": "compute_average", "bug_flavor": "wrong_algorithm", "sample_idx": 0,
            "buggy_code": BUGGY, "clean_code": CLEAN, "bug_rationale": "Returns the sum, never divides.", "caveats": []}


@pytest.fixture
def aim():
    return {"id": "compute_average", "text": "Compute the average of a list of numbers.",
            "contract": "Returns the arithmetic mean of the numbers. Returns None for an empty list."}


@pytest.fixture
def scenario():
    from multi_model_attribution.harness import run, failure_kind
    correct = {"function_name": "report_average", "code": CORRECT, "purpose": "doubles the mean of a reading list",
               "entry_call": "report_average([2, 4, 9])", "expected_repr": "10.0", "violation": ""}
    violating = {"function_name": "report_average", "code": VIOLATING, "purpose": "doubles the mean of a reading list",
                 "entry_call": "report_average([2, 4, 9])", "expected_repr": "10.0",
                 "violation": "Passes an empty list, whose return value None is then used in arithmetic."}
    runs = {"none": {**run(CLEAN, CORRECT, correct["entry_call"], "10.0").to_dict(), "callee_version": "clean", "caller_kind": "correct"},
            "callee": {**run(BUGGY, CORRECT, correct["entry_call"], "10.0").to_dict(), "callee_version": "buggy", "caller_kind": "correct"},
            "caller": {**run(CLEAN, VIOLATING, violating["entry_call"], "10.0").to_dict(), "callee_version": "clean", "caller_kind": "violating"}}
    from multi_model_attribution.harness import RunResult
    kinds = {"callee": "wrong_result", "caller": "exception_in_caller"}
    return {"scenario_id": "compute_average__wrong_algorithm__gpt5__000", "source_item_id": "compute_average__wrong_algorithm__gpt5__000",
            "bank": "items_gpt5", "aim_id": "compute_average", "bug_flavor": "wrong_algorithm", "caveats": [],
            "aim_text": "Compute the average of a list of numbers.",
            "contract": "Returns the arithmetic mean of the numbers. Returns None for an empty list.",
            "callee": {"function_name": "compute_average", "buggy_code": BUGGY, "clean_code": CLEAN, "bug_rationale": "r"},
            "caller": {"correct": correct, "violating": violating}, "runs": runs, "failure_kind": kinds,
            "truth": {"callee": "step_1", "caller": "step_2", "none": "neither"}, "cosmetic": None,
            "review": {"violating_caller_reviewed": False, "note": None}, "build": {}}


@pytest.fixture
def cfg():
    from multi_model_attribution.render import load_config
    return load_config()


@pytest.fixture
def judge():
    return {"id": "qwen3-32b", "family": "qwen", "params_b": 32, "display_name": "Qwen", "provider": "openrouter", "model": "qwen/qwen3-32b"}
