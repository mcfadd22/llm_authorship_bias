import json

import pytest

from multi_model_attribution.generate_callers import (
    CALLER_SCHEMA, build_caller_prompt, generate_caller, static_checks, validate_runs,
)
from multi_model_attribution.tests.conftest import CORRECT, VIOLATING
from elicitation.clients import ElicitationError, JudgeResponse


def _caller(code, name="report_average", purpose="doubles the mean of a reading list", entry="report_average([2, 4, 9])", expected="10.0", violation=""):
    return {"code": code, "function_name": name, "purpose": purpose, "entry_call": entry, "expected_repr": expected, "violation": violation}


class Scripted:
    def __init__(self, answers):
        self.answers = list(answers); self.prompts = []
    def ask(self, prompt, schema):
        assert schema == CALLER_SCHEMA
        self.prompts.append(prompt)
        data = self.answers.pop(0)
        return JudgeResponse(data=data, raw_text=json.dumps(data), model="gen", usage={}, thinking=None)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import elicitation.orchestrate as orch
    monkeypatch.setattr(orch.time, "sleep", lambda s: None)


def test_prompt_contents(record, aim):
    p = build_caller_prompt(record, aim, "correct")
    assert aim["contract"] in p and record["clean_code"] in p and record["buggy_code"] in p and "MODE: CORRECT" in p
    v = build_caller_prompt(record, aim, "violating", previous_error="boom")
    assert "NOTE (the alternative" not in v and "MODE: VIOLATING" in v and "rejected: boom" in v
    assert "NOTE (the alternative" in p


def test_static_checks_accept_and_reject():
    static_checks(_caller(CORRECT), "compute_average")
    with pytest.raises(ElicitationError, match="never calls"):
        static_checks(_caller("def report_average(values):\n    total = sum(values)\n    n = len(values)\n    return total / n"), "compute_average")
    with pytest.raises(ElicitationError, match="try/except"):
        static_checks(_caller("def report_average(values):\n    try:\n        avg = compute_average(values)\n    except Exception:\n        avg = 0\n    return avg"), "compute_average")
    with pytest.raises(ElicitationError, match="leak word"):
        static_checks(_caller(CORRECT, purpose="tests the buggy average"), "compute_average")
    with pytest.raises(ElicitationError, match="does not match"):
        static_checks(_caller(CORRECT, name="other_name"), "compute_average")
    with pytest.raises(ElicitationError, match="code validation"):
        static_checks(_caller("def report_average(values):\n    # note\n    avg = compute_average(values)\n    x = 1\n    return avg"), "compute_average")


def test_validate_runs_correct_mode(record):
    runs = validate_runs("correct", record, _caller(CORRECT))
    assert runs["none"].outcome == "ok" and runs["callee"].outcome == "wrong_result"
    with pytest.raises(ElicitationError, match="did not pass"):
        validate_runs("correct", record, _caller(CORRECT, expected="999"))
    insensitive = "def report_average(values):\n    avg = compute_average(values)\n    n = len(values)\n    return n"
    with pytest.raises(ElicitationError, match="still passed"):
        validate_runs("correct", record, _caller(insensitive, expected="3"))


def test_validate_runs_violating_mode(record):
    runs = validate_runs("violating", record, _caller(VIOLATING, violation="passes an empty list"))
    assert runs["caller"].outcome == "exception" and runs["caller"].exc_type == "TypeError"
    with pytest.raises(ElicitationError, match="did not fail"):
        validate_runs("violating", record, _caller(CORRECT, violation="x"))
    broken = "def report_average(values):\n    avg = compute_average(values)\n    out = undefined_name + avg\n    return out"
    with pytest.raises(ElicitationError, match="broken"):
        validate_runs("violating", record, _caller(broken, violation="x"))


def test_generate_caller_retries_with_feedback_then_succeeds(record, aim):
    bad = _caller(CORRECT, purpose="tests the buggy path")
    client = Scripted([bad, _caller(CORRECT)])
    out = generate_caller(client, record, aim, "correct", max_retries=3)
    assert out["attempts"] == 2 and out["mode"] == "correct" and out["runs"]["callee"]["outcome"] == "wrong_result"
    assert "rejected: ElicitationError: leak word" in client.prompts[1]
    assert out["callee_function_name"] == "compute_average"


def test_generate_caller_gives_up(record, aim):
    client = Scripted([_caller(CORRECT, purpose="a test")] * 2)
    with pytest.raises(RuntimeError, match="failed after 2 attempts"):
        generate_caller(client, record, aim, "correct", max_retries=2)
