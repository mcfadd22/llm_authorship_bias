import pytest

from multi_model_attribution.cosmetic import SkipCosmetic, apply_renames, rename_pair, renameable_names
from multi_model_attribution.harness import run

CALLEE = "def compute_average(values):\n    if not values:\n        return None\n    total = 0\n    count = 0\n    for x in values:\n        total += x\n        count += 1\n    return total / count"
CALLER = "def report_average(values, scale=2):\n    avg = compute_average(values)\n    result = round(avg * scale, 1)\n    return result"


def test_renameable_excludes_params_and_function_names():
    names = renameable_names(CALLEE, set())
    assert names == ["count", "total", "x"]
    assert "values" not in names and "compute_average" not in names


def test_rename_pair_is_consistent_and_preserves_behaviour():
    new_callee, new_caller, mapping = rename_pair(CALLEE, CALLER)
    assert "total" in mapping and "avg" in mapping and "result" in mapping
    assert "values" not in mapping and "scale" not in mapping and "compute_average" not in mapping
    assert "def compute_average(values)" in new_callee
    assert "def report_average(values, scale=2)" in new_caller
    assert "compute_average(values)" in new_caller
    assert len(new_callee.splitlines()) == len(CALLEE.splitlines())
    before = run(CALLEE, CALLER, "report_average([2, 4, 9])", "10.0")
    after = run(new_callee, new_caller, "report_average([2, 4, 9])", "10.0")
    assert before.outcome == after.outcome == "ok" and before.result_repr == after.result_repr


def test_attributes_and_keyword_args_untouched():
    code = "def f(items):\n    total = 0\n    seen = []\n    for item in items:\n        total += item.total\n        seen.append(g(total=item, key=1))\n    return seen"
    out = apply_renames(code, {"total": "acc", "item": "entry", "seen": "visited"})
    assert "entry.total" in out              # attribute name kept
    assert "g(total=entry, key=1)" in out    # keyword-arg name kept, value renamed
    assert "acc += entry.total" in out
    assert "visited.append" in out


def test_skip_when_too_few_locals():
    with pytest.raises(SkipCosmetic):
        rename_pair("def f(a):\n    return a + 1", "def g(a):\n    return f(a) * 2")
