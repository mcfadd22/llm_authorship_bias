import json

from multi_model_attribution.cells import enumerate_cells, load_existing_keys, row_key


def test_cell_counts_base_and_cosmetic(scenario, cfg, judge):
    qs = cfg["questions"]["questions"]
    rows = enumerate_cells([scenario], judge, qs, repeats=2)
    assert len(rows) == 138
    by = {}
    for r in rows: by.setdefault((r["cause"], r["question_type"]), 0); by[(r["cause"], r["question_type"])] += 1
    assert by[("none", "q_attribution")] == 9 * 2 and ("none", "q_blame_split") not in by
    assert by[("callee", "q_attribution")] == 15 * 2 and by[("callee", "q_blame_split")] == 15 * 2
    assert all(r["spin"] == "truthful" for r in rows if r["fidelity"] == "final_only" or r["cause"] == "none")
    assert all(r["note_shown"] == (r["fidelity"] != "final_only") for r in rows)
    assert {r["truth"] for r in rows if r["cause"] == "callee"} == {"step_1"}
    assert all(r["failure_kind"] is None for r in rows if r["cause"] == "none")
    cosmetic = {**scenario, "cosmetic": {"callee_buggy_code": "x", "callee_clean_code": "y", "caller_correct_code": "z",
                                         "caller_violating_code": "w", "rename_map": {}, "runs": scenario["runs"], "failure_kind": scenario["failure_kind"]}}
    rows2 = enumerate_cells([cosmetic], judge, qs, repeats=2)
    assert len(rows2) == 138 + 30
    renamed = [r for r in rows2 if r["variant"] == "renamed"]
    assert {r["names"] for r in renamed} == {"frontier_to_small"} and {r["spin"] for r in renamed} == {"truthful"}
    skipped = {**scenario, "cosmetic": {"skipped": "too few locals"}}
    assert len(enumerate_cells([skipped], judge, qs, repeats=2)) == 138


def test_row_keys_unique_and_roundtrip(scenario, cfg, judge, tmp_path):
    rows = enumerate_cells([scenario], judge, cfg["questions"]["questions"], repeats=2)
    keys = {row_key(r) for r in rows}
    assert len(keys) == len(rows)
    p = tmp_path / "j.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows[:5]) + "\n")
    assert load_existing_keys(p) == {row_key(r) for r in rows[:5]}
    assert load_existing_keys(tmp_path / "none.jsonl") == set()
