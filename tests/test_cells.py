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
