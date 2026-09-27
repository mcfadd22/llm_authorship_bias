import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import run_aim_review as ar  # noqa: E402
from elicitation.prompt import build_elicitation_prompt  # noqa: E402

AIMS = {a["id"]: a for a in json.loads((ROOT / "config" / "stated_aims.json").read_text())["aims"]}
ITEM = json.loads(next((ROOT / "data" / "items_gpt5").glob("*.json")).read_text())


def test_reviewer_sees_exactly_the_judge_facing_aim_and_code():
    none_label = {"id": "none", "sentence_template": None}
    judge_prompt = build_elicitation_prompt(AIMS[ITEM["aim_id"]]["text"], ITEM["code"], none_label,
                                            {"display_name": "x"}, ({}, {}), {"text": "Q"})
    assert judge_prompt.startswith(ar.judge_view(ITEM, AIMS) + "\n\nReview this code.")


def test_reviewer_prompt_leaks_nothing_about_the_intended_bug():
    content = ar.build_messages(ITEM, AIMS)[0]["content"]
    contract = AIMS[ITEM["aim_id"]]["contract"]
    for leak in (contract, ITEM["bug_flavor"], ITEM["item_id"], ITEM.get("rationale") or "~",
                 ITEM.get("generator_tag") or "~"):
        assert leak not in content


def test_parse_accepts_fenced_json_and_empty_issue_lists():
    assert ar.parse('```json\n{"issues": []}\n```') == {"issues": []}


def test_parse_rejects_an_unknown_basis():
    bad = {"issues": [{"input": "", "code_does": "", "should_do": "", "basis": "hunch",
                       "justification": ""}]}
    with pytest.raises(ValueError):
        ar.parse(json.dumps(bad))


def test_resume_skips_items_already_reviewed(tmp_path):
    out = tmp_path / "r.jsonl"
    out.write_text(json.dumps({"item_id": "a"}) + "\n")
    assert ar.done_ids(out) == {"a"}
    assert ar.done_ids(tmp_path / "missing.jsonl") == set()


def test_slug_is_filesystem_safe():
    assert ar.slug("qwen/qwen3.8-max-0902") == "qwen-qwen3.8-max-0902"


def _bank(tmp_path):
    import shutil
    for b in ("items_gpt5", "items_gpt5_clean"):
        d = tmp_path / b
        d.mkdir()
        for p in sorted((ROOT / "data" / b).glob("add_note*.json")):
            shutil.copy(p, d)
    return tmp_path / "items_gpt5"


def test_aim_only_sheet_shows_the_judge_view_and_nothing_else(tmp_path):
    sys.path.insert(0, str(ROOT / "analysis"))
    import build_aim_only_sheet as sheet
    bank = _bank(tmp_path)
    out = tmp_path / "s.html"
    sheet.main(["--items-dir", str(bank), "--out", str(out)])
    page = out.read_text()
    items = [json.loads(p.read_text()) for p in bank.glob("*.json")]
    for it in items:
        assert sheet.token(it["item_id"]) in page
        for leak in (it["item_id"], it["bug_flavor"], AIMS[it["aim_id"]]["contract"],
                     it["rationale"], it["generator_tag"]):
            assert leak not in page


def test_comparison_maps_human_tokens_back_to_items(tmp_path):
    sys.path.insert(0, str(ROOT / "analysis"))
    import build_aim_comparison as comp
    import build_aim_only_sheet as sheet
    bank = _bank(tmp_path)
    it = json.loads(next(bank.glob("*.json")).read_text())
    human = tmp_path / "h.csv"
    human.write_text("token,found,input,code_does,should_do,basis,other,note\n"
                     f"{sheet.token(it['item_id'])},yes,UNIQUE-INPUT-MARK,x,y,stated,,\n")
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    out = tmp_path / "c.html"
    comp.main(["--items-dir", str(bank), "--review-dir", str(reviews), "--human", str(human),
               "--out", str(out)])
    assert "UNIQUE-INPUT-MARK" in out.read_text()


def test_audit_selection_takes_every_weak_item_and_a_proportional_sample():
    sys.path.insert(0, str(ROOT / "analysis"))
    import select_aim_audit as sel
    stated = [{"basis": "stated"}]
    reviews = {f"a__f{f}__g__{i:03d}": stated for f in (1, 2) for i in range(10)}
    reviews["a__f1__g__900"] = []
    reviews["a__f2__g__901"] = [{"basis": "convention"}]
    strata = sel.select(reviews, ["a__f1__g__000"], n_sample=4, seed=1)
    assert strata["a__f1__g__900"] == "model_none"
    assert strata["a__f2__g__901"] == "model_convention"
    assert strata["a__f1__g__000"] == "contract_review_flag"
    sampled = [i for i, s in strata.items() if s == "sampled_stated"]
    assert len(sampled) == 4
    assert sum("__f1__" in i for i in sampled) == 2   # 9 vs 10 remaining stated items
    assert sel.select(reviews, [], 4, 1) == sel.select(reviews, [], 4, 1)
