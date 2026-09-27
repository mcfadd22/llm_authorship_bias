import json

import pytest

import run_elicitation


def _make_items(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / "compute_average__missing_edge_case__trivial__000.json").write_text(json.dumps({
        "item_id": "compute_average__missing_edge_case__trivial__000",
        "cell_id": "compute_average__missing_edge_case__trivial",
        "sample_idx": 0, "aim_id": "compute_average",
        "bug_flavor": "missing_edge_case", "severity_tier": "trivial",
        "code": "def f(xs):\n    return sum(xs) / len(xs)",
    }))
    return items_dir


def test_dry_run_prints_counts_and_cost_without_keys(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    items_dir = _make_items(tmp_path)
    run_elicitation.main([
        "--dry-run", "--items-dir", str(items_dir), "--out-dir", str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert "items: 1" in out
    # 1 buggy item x 6 labels x 5 questions (3 scaled + detect + belief) = 30 per judge
    assert "planned    30" in out
    assert "total" in out
    assert "$" in out
    assert not (tmp_path / "out").exists()


def test_dry_run_clean_items_only_get_two_questions(tmp_path, capsys):
    items_dir = tmp_path / "items_clean"
    items_dir.mkdir()
    (items_dir / "compute_average__missing_edge_case__trivial__000.json").write_text(json.dumps({
        "item_id": "compute_average__missing_edge_case__trivial__000",
        "cell_id": "compute_average__missing_edge_case__trivial",
        "sample_idx": 0, "aim_id": "compute_average",
        "bug_flavor": "missing_edge_case", "severity_tier": "trivial",
        "code_version": "clean", "source_item_id": "compute_average__missing_edge_case__trivial__000",
        "code": "def f(xs):\n    if not xs:\n        return 0\n    return sum(xs) / len(xs)",
    }))
    run_elicitation.main(["--dry-run", "--items-dir", str(items_dir), "--out-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    # 1 clean item x 6 labels x 2 questions (detect + belief) = 12 per judge
    assert "planned    12" in out


def test_missing_key_fails_fast(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    items_dir = _make_items(tmp_path)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        run_elicitation.main([
            "--judge", "claude-sonnet-5", "--items-dir", str(items_dir),
            "--out-dir", str(tmp_path / "out"),
        ])


def test_unknown_judge_rejected(tmp_path):
    items_dir = _make_items(tmp_path)
    with pytest.raises(SystemExit, match="unknown judge"):
        run_elicitation.main(["--judge", "nope", "--dry-run", "--items-dir", str(items_dir),
                             "--out-dir", str(tmp_path / "out")])


def test_run_uses_fake_client_and_writes_rows(tmp_path, monkeypatch):
    from elicitation.clients import JudgeResponse

    class Fake:
        def ask(self, prompt, schema):
            if "score" in schema["properties"]:
                data = {"score": 2, "explanation": "explanation long enough to pass"}
            elif "has_bug" in schema["properties"]:
                data = {"has_bug": True, "explanation": "explanation long enough to pass"}
            else:
                data = {"answer": "answer long enough to pass validation"}
            return JudgeResponse(data=data, raw_text=json.dumps(data), model="m", usage={}, thinking=None)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_elicitation, "make_client", lambda judge: Fake())
    items_dir = _make_items(tmp_path)
    run_elicitation.main([
        "--judge", "claude-sonnet-5", "--limit", "5", "--concurrency", "2",
        "--items-dir", str(items_dir), "--out-dir", str(tmp_path / "out"),
    ])
    rows = (tmp_path / "out" / "claude-sonnet-5.jsonl").read_text().splitlines()
    assert len(rows) == 5


def test_items_and_out_dir_are_required(tmp_path):
    with pytest.raises(SystemExit):
        run_elicitation.main(["--dry-run", "--items-dir", str(_make_items(tmp_path))])
    with pytest.raises(SystemExit):
        run_elicitation.main(["--dry-run", "--out-dir", str(tmp_path / "out")])


def test_leg_manifest_ties_an_out_dir_to_one_bank(tmp_path):
    a = _make_items(tmp_path)
    b = tmp_path / "other"
    b.mkdir()
    out = tmp_path / "out"
    run_elicitation.check_leg(out, a, overwrite=False, write=True)
    run_elicitation.check_leg(out, a, overwrite=False, write=False)   # same bank: fine
    with pytest.raises(SystemExit, match="separate --out-dir"):
        run_elicitation.check_leg(out, b, overwrite=False, write=False)


def test_refuses_a_folder_with_rows_but_no_manifest_and_overwrite_on_rows(tmp_path):
    a = _make_items(tmp_path)
    wave1 = tmp_path / "wave1"
    wave1.mkdir()
    (wave1 / "gpt-5.jsonl").write_text('{"x": 1}\n')
    with pytest.raises(SystemExit, match="another run"):
        run_elicitation.check_leg(wave1, a, overwrite=False, write=False)
    leg = tmp_path / "leg"
    run_elicitation.check_leg(leg, a, overwrite=False, write=True)
    (leg / "gpt-5.jsonl").write_text('{"x": 1}\n')
    with pytest.raises(SystemExit, match="duplicate"):
        run_elicitation.check_leg(leg, a, overwrite=True, write=False)


def test_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "out"
    run_elicitation.main(["--dry-run", "--items-dir", str(_make_items(tmp_path)), "--out-dir", str(out)])
    assert not out.exists()
