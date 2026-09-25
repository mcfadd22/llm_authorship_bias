import pytest

from vignette_gen.cells import Cell, enumerate_cells, expand_items, generator_tag

STATED_AIMS = [
    {
        "id": "aim_a",
        "flavors": {
            "logic_error": {"severity_tiers": ["significant"]},
            "missing_edge_case": {"severity_tiers": ["trivial"]},
        },
    }
]
TAG = "claudesonnet45"


def test_enumerate_cells_is_one_per_aim_and_flavor():
    """severity_tier is recorded, not crossed, so it must not multiply cells."""
    cells = enumerate_cells(STATED_AIMS)
    assert {c.cell_id for c in cells} == {"aim_a__logic_error", "aim_a__missing_edge_case"}
    assert len(cells) == 2


def test_enumerate_cells_carries_the_expected_severity_tiers():
    cells = {c.bug_flavor: c for c in enumerate_cells(STATED_AIMS)}
    assert cells["logic_error"].expected_severity_tiers == ("significant",)
    assert cells["missing_edge_case"].expected_severity_tiers == ("trivial",)


def test_item_id_carries_the_generator_tag():
    """Two banks must never share an item_id: analysis clusters on it, so a
    collision would silently merge two distinct stimuli into one cluster."""
    cells = enumerate_cells(STATED_AIMS)[:1]
    mine = expand_items(cells, 1, "claudesonnet45")[0]["item_id"]
    theirs = expand_items(cells, 1, "gpt5")[0]["item_id"]

    assert mine == "aim_a__logic_error__claudesonnet45__000"
    assert theirs == "aim_a__logic_error__gpt5__000"
    assert mine != theirs


def test_expand_items_appends_sample_index_and_keeps_cell_id():
    cells = enumerate_cells(STATED_AIMS)[:1]
    items = expand_items(cells, samples_per_cell=3, generator_tag=TAG)

    assert [i["item_id"] for i in items] == [
        f"aim_a__logic_error__{TAG}__00{n}" for n in range(3)
    ]
    assert all(i["cell_id"] == "aim_a__logic_error" for i in items)
    assert [i["sample_idx"] for i in items] == [0, 1, 2]
    assert all(i["generator_tag"] == TAG for i in items)


def test_expand_items_with_higher_sample_count_is_a_superset():
    """samples_per_cell must be toppable later without regenerating the bank."""
    cells = enumerate_cells(STATED_AIMS)[:1]
    small = {i["item_id"] for i in expand_items(cells, 1, TAG)}
    large = {i["item_id"] for i in expand_items(cells, 3, TAG)}
    assert small.issubset(large)


def test_severity_tier_is_set_when_the_rubric_forces_one():
    item = expand_items(enumerate_cells(STATED_AIMS)[:1], 1, TAG)[0]
    assert item["expected_severity_tiers"] == ["significant"]
    assert item["severity_tier"] == "significant"


def test_severity_tier_is_left_open_when_the_pair_admits_both():
    """known_trap and silent_failure genuinely vary; the review pass decides."""
    aims = [{"id": "a", "flavors": {"silent_failure": {"severity_tiers": ["trivial", "significant"]}}}]
    item = expand_items(enumerate_cells(aims), 1, TAG)[0]
    assert item["expected_severity_tiers"] == ["trivial", "significant"]
    assert item["severity_tier"] is None


@pytest.mark.parametrize("model,expected", [
    ("anthropic/claude-sonnet-4.5", "claudesonnet45"),
    ("claude-sonnet-4-5-20250929", "claudesonnet4520250929"),
    ("openai/gpt-5", "gpt5"),
    ("GPT-5", "gpt5"),
])
def test_generator_tag_sanitises_model_ids(model, expected):
    assert generator_tag(model) == expected


def test_generator_tag_rejects_a_model_with_no_usable_characters():
    with pytest.raises(ValueError, match="generator tag"):
        generator_tag("///")
