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
        run_elicitation.main(["--judge", "nope", "--dry-run", "--items-dir", str(items_dir)])


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
