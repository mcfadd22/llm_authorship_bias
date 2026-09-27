import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))
import build_item_review  # noqa: E402
import merge_verdicts  # noqa: E402


def _bank(tmp, name, tag, n):
    items, clean = tmp / name, tmp / f"{name}_clean"
    items.mkdir(), clean.mkdir()
    ids = []
    for i in range(n):
        iid = f"cart_total__logic_error__{tag}__{i:03d}"
        ids.append(iid)
        item = {"item_id": iid, "aim_id": "cart_total", "bug_flavor": "logic_error",
                "severity_tier": "trivial", "code": f"def f():\n    return {i}\n",
                "rationale": "r"}
        (items / f"{iid}.json").write_text(json.dumps(item))
        (clean / f"{iid}.json").write_text(json.dumps({"item_id": iid, "code": f"def f():\n    return {i + 1}\n"}))
    return items, ids


def _write_csv(path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "verdict", "twin_verdict", "note"])
        w.writeheader()
        w.writerows(rows)


def test_blind_multi_bank_sheet_skips_reviewed_and_hides_ids(tmp_path):
    a, a_ids = _bank(tmp_path, "items_gpt5", "gpt5", 3)
    b, b_ids = _bank(tmp_path, "items_gemini25pro", "gemini25pro", 2)
    verdicts = tmp_path / "v.csv"
    _write_csv(verdicts, [{"item_id": a_ids[0], "verdict": "ok", "twin_verdict": "ok", "note": ""}])
    out = tmp_path / "sheet.html"
    build_item_review.main(["--items-dir", str(a), str(b), "--verdicts", str(verdicts),
                            "--only-unreviewed", "--blind", "--out", str(out)])
    page = out.read_text()

    assert page.count('class="card"') == 4
    assert f'data-item="{a_ids[0]}"' not in page
    # ids stay in data attributes for the export, but never as visible text
    assert '<code class="iid">' not in page
    for iid in a_ids[1:] + b_ids:
        assert f'data-item="{iid}"' in page


def test_clean_dir_rejected_with_several_banks(tmp_path):
    import pytest
    a, _ = _bank(tmp_path, "items_gpt5", "gpt5", 1)
    b, _ = _bank(tmp_path, "items_gemini25pro", "gemini25pro", 1)
    with pytest.raises(SystemExit):
        build_item_review.parse_args(["--items-dir", str(a), str(b), "--clean-dir", str(a)])


def test_merge_routes_by_tag_and_never_blanks_prior_verdicts(tmp_path):
    prior = tmp_path / "item_verdicts_gpt5.csv"
    _write_csv(prior, [
        {"item_id": "cart_total__logic_error__gpt5__000", "verdict": "ok", "twin_verdict": "ok", "note": "keep"},
        {"item_id": "cart_total__logic_error__gpt5__001", "verdict": "ok", "twin_verdict": "", "note": ""},
    ])
    export = tmp_path / "export.csv"
    _write_csv(export, [
        {"item_id": "cart_total__logic_error__gpt5__000", "verdict": "", "twin_verdict": "", "note": ""},
        {"item_id": "cart_total__logic_error__gpt5__001", "verdict": "drop", "twin_verdict": "", "note": "x"},
        {"item_id": "cart_total__logic_error__gpt5__002", "verdict": "ok", "twin_verdict": "ok", "note": ""},
        {"item_id": "cart_total__logic_error__gemini25pro__000", "verdict": "not_a_bug", "twin_verdict": "", "note": ""},
    ])
    merge_verdicts.merge(export, tmp_path)

    gpt = {r["item_id"]: r for r in csv.DictReader(prior.open())}
    assert gpt["cart_total__logic_error__gpt5__000"]["note"] == "keep"
    assert gpt["cart_total__logic_error__gpt5__001"]["verdict"] == "drop"
    assert gpt["cart_total__logic_error__gpt5__002"]["verdict"] == "ok"
    gem = list(csv.DictReader((tmp_path / "item_verdicts_gemini25pro.csv").open()))
    assert [r["verdict"] for r in gem] == ["not_a_bug"]


def test_also_brings_back_reviewed_items_for_a_recheck(tmp_path):
    a, a_ids = _bank(tmp_path, "items_gpt5", "gpt5", 3)
    verdicts = tmp_path / "v.csv"
    _write_csv(verdicts, [{"item_id": i, "verdict": "ok", "twin_verdict": "ok", "note": ""} for i in a_ids])
    out = tmp_path / "sheet.html"
    build_item_review.main(["--items-dir", str(a), "--verdicts", str(verdicts), "--only-unreviewed",
                            "--also", a_ids[1], "--out", str(out)])
    page = out.read_text()
    assert page.count('class="card"') == 1 and f'data-item="{a_ids[1]}"' in page
