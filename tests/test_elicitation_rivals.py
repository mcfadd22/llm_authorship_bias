import pytest

from elicitation.rivals import resolve_rivals

POOL = [
    {"id": "claude", "display_name": "Claude"},
    {"id": "gpt", "display_name": "GPT-5"},
    {"id": "gemini", "display_name": "Gemini"},
    {"id": "llama", "display_name": "Llama"},
]
CLAUDE_JUDGE = {"id": "claude-opus-5", "family": "claude"}
GPT_JUDGE = {"id": "gpt-5", "family": "gpt"}


def test_judge_family_is_excluded():
    for i in range(10):
        a, b = resolve_rivals(CLAUDE_JUDGE, i, POOL)
        assert "claude" not in (a["id"], b["id"])
        a, b = resolve_rivals(GPT_JUDGE, i, POOL)
        assert "gpt" not in (a["id"], b["id"])


def test_a_and_b_are_distinct():
    for i in range(10):
        a, b = resolve_rivals(CLAUDE_JUDGE, i, POOL)
        assert a["id"] != b["id"]


def test_rotation_is_deterministic_and_cycles():
    seq = [resolve_rivals(CLAUDE_JUDGE, i, POOL)[0]["id"] for i in range(6)]
    assert seq == ["gpt", "gemini", "llama", "gpt", "gemini", "llama"]
    seq_b = [resolve_rivals(CLAUDE_JUDGE, i, POOL)[1]["id"] for i in range(6)]
    assert seq_b == ["gemini", "llama", "gpt", "gemini", "llama", "gpt"]
    assert resolve_rivals(CLAUDE_JUDGE, 4, POOL) == resolve_rivals(CLAUDE_JUDGE, 4, POOL)


def test_fewer_than_two_rivals_raises():
    with pytest.raises(ValueError):
        resolve_rivals(CLAUDE_JUDGE, 0, POOL[:2])
