import json
from pathlib import Path

import pytest

from elicitation.clients import ElicitationError, JudgeResponse
from elicitation.orchestrate import RunOptions, elicit_one, run_judge

JUDGE = {"id": "j", "family": "claude", "tuning": "t", "display_name": "Claude",
         "provider": "anthropic", "model": "claude-opus-5"}
CONFIG = {
    "judges": [JUDGE],
    "rival_pool": [
        {"id": "claude", "display_name": "Claude"},
        {"id": "gpt", "display_name": "GPT-5"},
        {"id": "gemini", "display_name": "Gemini"},
    ],
    "author_labels": [
        {"id": "none", "sentence_template": None},
        {"id": "other_model_A", "sentence_template": "This function was written by {rival_display_name}."},
    ],
    "questions": [
        {"id": "q_blame", "kind": "scaled", "text": "Blame?"},
        {"id": "q_authorship_belief", "kind": "free", "text": "Who?"},
    ],
    "stated_aims": {"avg": {"id": "avg", "text": "Compute the average."}},
}
ITEMS = [
    {"item_id": "avg__x__trivial__000", "cell_id": "avg__x__trivial", "aim_id": "avg",
     "bug_flavor": "x", "severity_tier": "trivial", "code": "def f(): pass"},
]


class FakeClient:
    def __init__(self, fail_first=0, always_fail=False):
        self.calls = []
        self.fail_first = fail_first
        self.always_fail = always_fail

    def ask(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.always_fail or len(self.calls) <= self.fail_first:
            raise ElicitationError("boom")
        if "score" in schema["properties"]:
            data = {"score": 4, "explanation": "because"}
        else:
            data = {"answer": "a human"}
        return JudgeResponse(data=data, raw_text=json.dumps(data), model="served",
                             usage={"input_tokens": 1}, thinking=None)


def _options(tmp_path, **overrides):
    base = dict(limit=None, repeats=1, dry_run=False, overwrite=False, max_retries=3,
                concurrency=2, items_dir=tmp_path / "items",
                out_dir=tmp_path / "out")
    base.update(overrides)
    return RunOptions(**base)


def _row(label="none", question="q_blame"):
    return {"item_id": "avg__x__trivial__000", "item_index": 0, "cell_id": "avg__x__trivial",
            "aim_id": "avg", "judge_id": "j", "judge_family": "claude", "judge_tuning": "t",
            "author_label": label, "severity_tier": "trivial", "bug_flavor": "x",
            "question_type": question, "repeat_idx": 0}


def test_elicit_one_scaled_row_shape():
    client = FakeClient()
    record = elicit_one(client, _row("other_model_A", "q_blame"), JUDGE, CONFIG,
                        ITEMS[0], max_retries=3)
    assert record["scale_response"] == 4
    assert record["reasoning_text"] == "because"
    assert record["authorship_belief_raw"] is None
    assert record["authorship_belief_coded"] is None
    assert record["rival_a"] == "gpt"
    assert record["rival_b"] == "gemini"
    assert record["author_sentence"] == "This function was written by GPT-5."
    assert record["prompt"].startswith("This function is supposed to compute the average.")
    assert record["prompt"].endswith("Blame?")
    assert record["raw_response"] == json.dumps({"score": 4, "explanation": "because"})
    assert record["response_model"] == "served"
    assert record["usage"] == {"input_tokens": 1}
    assert record["prompt_version"] == "2026-09-11-v1"
    assert "timestamp" in record
    assert "item_index" not in record


def test_elicit_one_free_row_shape():
    client = FakeClient()
    record = elicit_one(client, _row("none", "q_authorship_belief"), JUDGE, CONFIG,
                        ITEMS[0], max_retries=3)
    assert record["scale_response"] is None
    assert record["reasoning_text"] is None
    assert record["authorship_belief_raw"] == "a human"
    assert record["author_sentence"] is None
    assert "written by" not in record["prompt"]


def test_elicit_one_retries_then_succeeds():
    client = FakeClient(fail_first=2)
    record = elicit_one(client, _row(), JUDGE, CONFIG, ITEMS[0], max_retries=3)
    assert record["scale_response"] == 4
    assert len(client.calls) == 3


def test_elicit_one_raises_after_max_retries():
    client = FakeClient(always_fail=True)
    with pytest.raises(RuntimeError, match="failed after 2 attempts"):
        elicit_one(client, _row(), JUDGE, CONFIG, ITEMS[0], max_retries=2)


def test_elicit_one_rejects_out_of_range_score():
    class BadScore(FakeClient):
        def ask(self, prompt, schema):
            data = {"score": 9, "explanation": "x"}
            return JudgeResponse(data=data, raw_text="", model="m", usage={}, thinking=None)

    with pytest.raises(RuntimeError, match="score"):
        elicit_one(BadScore(), _row(), JUDGE, CONFIG, ITEMS[0], max_retries=1)


def test_run_judge_writes_all_rows_and_resumes(tmp_path):
    client = FakeClient()
    opts = _options(tmp_path)
    summary = run_judge(client, JUDGE, CONFIG, ITEMS, opts)
    assert summary == {"generated": 4, "skipped": 0, "failed": 0}
    out = opts.out_dir / "j.jsonl"
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 4
    assert {(r["author_label"], r["question_type"]) for r in rows} == {
        ("none", "q_blame"), ("none", "q_authorship_belief"),
        ("other_model_A", "q_blame"), ("other_model_A", "q_authorship_belief"),
    }

    client2 = FakeClient()
    summary2 = run_judge(client2, JUDGE, CONFIG, ITEMS, opts)
    assert summary2 == {"generated": 0, "skipped": 4, "failed": 0}
    assert client2.calls == []


def test_run_judge_limit_applies_after_resume(tmp_path):
    opts = _options(tmp_path, limit=1)
    run_judge(FakeClient(), JUDGE, CONFIG, ITEMS, opts)
    run_judge(FakeClient(), JUDGE, CONFIG, ITEMS, opts)
    out = opts.out_dir / "j.jsonl"
    assert len(out.read_text().splitlines()) == 2


def test_run_judge_logs_failures_and_continues(tmp_path):
    opts = _options(tmp_path, max_retries=1)
    summary = run_judge(FakeClient(always_fail=True), JUDGE, CONFIG, ITEMS, opts)
    assert summary == {"generated": 0, "skipped": 0, "failed": 4}
    failures = [json.loads(l) for l in (opts.out_dir / "failures.jsonl").read_text().splitlines()]
    assert len(failures) == 4
    assert "boom" in failures[0]["error"]
    assert failures[0]["judge_id"] == "j"


def test_run_judge_dry_run_makes_no_calls_and_writes_nothing(tmp_path):
    client = FakeClient()
    opts = _options(tmp_path, dry_run=True)
    summary = run_judge(client, JUDGE, CONFIG, ITEMS, opts)
    assert summary["planned"] == 4
    assert client.calls == []
    assert not (opts.out_dir / "j.jsonl").exists()
