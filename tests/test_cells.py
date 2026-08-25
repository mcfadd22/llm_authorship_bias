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
