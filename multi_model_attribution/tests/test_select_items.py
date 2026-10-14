import json
from pathlib import Path

from multi_model_attribution.select_items import (
    build_pool, eligible, load_caveats, load_verdicts, order_round_robin, select,
)


def _item(iid, aim, flavor, bank_tag, idx=0):
    return {"item_id": iid, "aim_id": aim, "bug_flavor": flavor, "sample_idx": idx,
            "code": f"def {aim}(x):\n    return x\n", "rationale": "r", "generator_tag": bank_tag}


def _write_bank(tmp_path, name, items, twins=True):
    b = tmp_path / name; c = tmp_path / (name + "_clean"); b.mkdir(); c.mkdir()
    for it in items:
        (b / f"{it['item_id']}.json").write_text(json.dumps(it))
        if twins:
            (c / f"{it['item_id']}.json").write_text(json.dumps({**it, "code_version": "clean", "code": it["code"] + "\n"}))
    return b, c


def test_eligible_rules():
    it = _item("a__logic_error__gpt5__000", "a", "logic_error", "gpt5")
    ok = {"verdict": "ok", "twin_verdict": "ok"}
    assert eligible(it, {"code": "x"}, ok, [])
    assert not eligible(it, None, ok, [])
    assert not eligible(it, {"code": "x"}, None, [])
    assert not eligible(it, {"code": "x"}, {"verdict": "ok", "twin_verdict": "twin_not_minimal"}, [])
    assert not eligible(it, {"code": "x"}, {"verdict": "not_a_bug", "twin_verdict": "ok"}, [])
    assert not eligible(it, {"code": "x"}, ok, ["aim_visibility_likely_no"])
    assert eligible(it, {"code": "x"}, ok, ["severity_open"])
    assert not eligible({**it, "bug_flavor": "security_vulnerability"}, {"code": "x"}, ok, [])
    assert not eligible({**it, "bug_flavor": "copy_paste_residue"}, {"code": "x"}, ok, [])


def test_build_pool_and_round_robin(tmp_path):
    items_g = [_item("a__logic_error__gpt5__000", "a", "logic_error", "gpt5"),
               _item("a__logic_error__gpt5__001", "a", "logic_error", "gpt5", 1),
               _item("b__known_trap__gpt5__000", "b", "known_trap", "gpt5"),
               _item("c__security_vulnerability__gpt5__000", "c", "security_vulnerability", "gpt5")]
    items_m = [_item("a__logic_error__gemini25pro__000", "a", "logic_error", "gemini25pro"),
               _item("b__known_trap__gemini25pro__000", "b", "known_trap", "gemini25pro")]
    bg, cg = _write_bank(tmp_path, "items_gpt5", items_g)
    bm, cm = _write_bank(tmp_path, "items_gemini25pro", items_m)
    vcsv = tmp_path / "v.csv"
    vcsv.write_text("item_id,verdict,twin_verdict,note\n" + "\n".join(
        f"{it['item_id']},ok,ok," for it in items_g + items_m if "001" not in it["item_id"]) +
        "\na__logic_error__gpt5__001,ok,twin_not_minimal,\n")
    ccsv = tmp_path / "c.csv"
    ccsv.write_text("item_id,caveat,detail\nb__known_trap__gemini25pro__000,aim_visibility_likely_no,x\n")
    pool = build_pool([("items_gpt5", bg, cg), ("items_gemini25pro", bm, cm)], load_verdicts([vcsv]), load_caveats(ccsv))
    ids = [c["source_item_id"] for c in pool]
    assert "c__security_vulnerability__gpt5__000" not in ids
    assert "a__logic_error__gpt5__001" not in ids           # non-minimal twin
    assert "b__known_trap__gemini25pro__000" not in ids     # aim not visible
    assert sorted(ids) == ["a__logic_error__gemini25pro__000", "a__logic_error__gpt5__000", "b__known_trap__gpt5__000"]
    ordered = [c["source_item_id"] for c in order_round_robin(pool)]
    # aim 'a' (even index) prefers gpt5; aim 'b' (odd) would prefer gemini but only has gpt5 left
    assert ordered == ["a__logic_error__gpt5__000", "b__known_trap__gpt5__000", "a__logic_error__gemini25pro__000"]
    assert [c["source_item_id"] for c in select(pool, 2)] == ordered[:2]
    rec = pool[0]
    assert rec["clean_code"] != rec["buggy_code"] and rec["bug_rationale"] == "r"


def test_round_robin_alternates_bank_priority_across_aims():
    pool = [{"source_item_id": f"{a}__x__{b}__000", "aim_id": a, "bank": f"items_{b}", "sample_idx": 0}
            for a in ("a", "b", "c", "d") for b in ("gpt5", "gemini25pro")]
    first_round = [c["bank"] for c in order_round_robin(pool)[:4]]
    assert first_round == ["items_gpt5", "items_gemini25pro", "items_gpt5", "items_gemini25pro"]


def test_missing_caveats_file_is_empty(tmp_path):
    assert load_caveats(tmp_path / "nope.csv") == {}
