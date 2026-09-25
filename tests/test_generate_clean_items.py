import json

import pytest

import generate_clean_items as gci
from elicitation.clients import ElicitationError, JudgeResponse

BUGGY = {
    "item_id": "compute_average__wrong_algorithm__trivial__000",
    "cell_id": "compute_average__wrong_algorithm__trivial",
    "sample_idx": 0, "aim_id": "compute_average",
    "bug_flavor": "wrong_algorithm", "severity_tier": "trivial",
    "code": "def calculate_average(numbers):\n    if not numbers:\n        return 0\n    total = 0\n    for num in numbers:\n        total += num\n    return total",
    "rationale": "Never divides by the count.",
    "generation_model": "anthropic/claude-sonnet-4.5",
    "timestamp": "2026-08-25T01:00:46+00:00", "prompt_version": "2026-08-24-v1",
}
AIMS = {"compute_average": {
    "id": "compute_average",
    "text": "Compute the average of a list of numbers.",
    "contract": "Returns the arithmetic mean. Returns None for an empty list.",
}}
GOOD_CODE = "def calculate_average(numbers):\n    if not numbers:\n        return 0\n    total = 0\n    for num in numbers:\n        total += num\n    return total / len(numbers)"


class FakeClient:
    def __init__(self, code=GOOD_CODE, fail_first=0):
        self.code = code
        self.fail_first = fail_first
        self.calls = []

    def ask(self, prompt, schema):
        self.calls.append((prompt, schema))
        if len(self.calls) <= self.fail_first:
            raise ElicitationError("boom")
        data = {"code": self.code, "fix_rationale": "Added the division by len(numbers)."}
        return JudgeResponse(data=data, raw_text=json.dumps(data), model="served", usage={}, thinking=None)


def test_prompt_contains_aim_code_rationale_and_constraints():
    prompt = gci.build_clean_prompt(BUGGY, AIMS)
    assert "Compute the average of a list of numbers." in prompt
    assert BUGGY["code"] in prompt
    assert "Never divides by the count." in prompt
    assert "as little as possible" in prompt
    assert "No comments and no docstrings" in prompt


def test_prompt_states_the_contract():
    """Without it the twin generator settles boundary behaviour itself, which is
    how the two wave-1 average twins came back returning None and 0."""
    prompt = gci.build_clean_prompt(BUGGY, AIMS)
    assert "CONTRACT" in prompt
    assert "Returns the arithmetic mean. Returns None for an empty list." in prompt


def test_prompt_requires_a_wholly_defect_free_twin():
    """The twin is the false-positive control: a reviewer reporting a genuine
    remaining flaw would be right, and the measurement would be wrong. Wave-1
    items 24 and 26 kept hardcoded keys and plaintext password storage."""
    prompt = gci.build_clean_prompt(BUGGY, AIMS)
    assert "NO defect of any kind" in prompt
    assert "prefer the\n  defect-free result" in prompt


def test_generate_clean_one_returns_record():
    client = FakeClient()
    record = gci.generate_clean_one(client, BUGGY, AIMS, max_retries=3)
    assert record["code"] == GOOD_CODE
    assert record["code_version"] == "clean"
    assert record["source_item_id"] == BUGGY["item_id"]
    assert record["item_id"] == BUGGY["item_id"]
    assert record["fix_rationale"] == "Added the division by len(numbers)."
    assert record["generation_model"] == "served"
    assert record["prompt_version"] == gci.PROMPT_VERSION
    assert "rationale" not in record
    assert record["bug_flavor"] == "wrong_algorithm"
    assert "timestamp" in record
    assert client.calls[0][1] == gci.CLEAN_SCHEMA


def test_generate_clean_one_rejects_invalid_code_and_retries():
    client = FakeClient(code="def f(x):\n    # comment\n    return x")
    with pytest.raises(RuntimeError, match="comment"):
        gci.generate_clean_one(client, BUGGY, AIMS, max_retries=2)
    assert len(client.calls) == 2


def test_generate_clean_one_rejects_unchanged_code():
    client = FakeClient(code=BUGGY["code"])
    with pytest.raises(RuntimeError, match="identical"):
        gci.generate_clean_one(client, BUGGY, AIMS, max_retries=1)


def test_generate_clean_one_retries_then_succeeds():
    client = FakeClient(fail_first=1)
    record = gci.generate_clean_one(client, BUGGY, AIMS, max_retries=3)
    assert record["code"] == GOOD_CODE


def test_run_writes_resumes_and_logs_failures(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / f"{BUGGY['item_id']}.json").write_text(json.dumps(BUGGY))
    # sorts after the good item, so it is the second call
    bad = {**BUGGY, "item_id": "zzz_bad__wrong_algorithm__trivial__000", "aim_id": "compute_average"}
    (items_dir / f"{bad['item_id']}.json").write_text(json.dumps(bad))
    out_dir = tmp_path / "items_clean"

    class Selective(FakeClient):
        def ask(self, prompt, schema):
            self.calls.append((prompt, schema))
            # first call succeeds; the second returns the buggy code unchanged and is rejected
            code = GOOD_CODE if len(self.calls) == 1 else BUGGY["code"]
            data = {"code": code, "fix_rationale": "x"}
            return JudgeResponse(data=data, raw_text="", model="m", usage={}, thinking=None)

    summary = gci.run(Selective(), items_dir, out_dir, AIMS, limit=None, overwrite=False,
                      max_retries=1, dry_run=False)
    assert summary == {"generated": 1, "skipped": 0, "failed": 1}
    written = json.loads((out_dir / f"{BUGGY['item_id']}.json").read_text())
    assert written["code_version"] == "clean"
    failures = [json.loads(l) for l in (out_dir / "failures.jsonl").read_text().splitlines()]
    assert len(failures) == 1 and failures[0]["item_id"] == bad["item_id"]

    summary2 = gci.run(FakeClient(), items_dir, out_dir, AIMS, limit=None, overwrite=False,
                       max_retries=1, dry_run=False)
    assert summary2["skipped"] == 1 and summary2["generated"] == 1


def test_dry_run_prints_prompt_and_writes_nothing(tmp_path, capsys):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / f"{BUGGY['item_id']}.json").write_text(json.dumps(BUGGY))
    client = FakeClient()
    summary = gci.run(client, items_dir, tmp_path / "clean", AIMS, limit=None, overwrite=False,
                      max_retries=1, dry_run=True)
    assert summary == {"generated": 0, "skipped": 0, "failed": 0}
    assert client.calls == []
    assert BUGGY["item_id"] in capsys.readouterr().out
    assert not (tmp_path / "clean").exists()


def test_parse_args_defaults():
    args = gci.parse_args([])
    assert args.model == "claude-sonnet-4-5"
    assert args.dry_run is False
    assert args.limit is None
    assert args.max_retries == 3


def test_parse_args_defaults_to_anthropic_and_accepts_a_provider():
    assert gci.parse_args([]).provider == "anthropic"
    assert gci.parse_args(["--provider", "openai", "--model", "gpt-5"]).provider == "openai"


def test_parse_args_rejects_an_unknown_provider():
    with pytest.raises(SystemExit):
        gci.parse_args(["--provider", "not_a_provider"])
