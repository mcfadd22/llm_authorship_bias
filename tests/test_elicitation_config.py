import json

import pytest

from elicitation.config import load_elicitation_config


def _write(config_dir, name, payload):
    (config_dir / name).write_text(json.dumps(payload))


@pytest.fixture
def config_dir(tmp_path):
    _write(tmp_path, "judge_models.json", {"judges": [
        {"id": "j-claude", "family": "claude", "tuning": "x", "display_name": "Claude",
         "provider": "anthropic", "model": "claude-opus-5"},
        {"id": "j-gpt", "family": "gpt", "tuning": "y", "display_name": "GPT-5",
         "provider": "openai", "model": "gpt-5"},
    ]})
    _write(tmp_path, "rival_model_pool.json", {"pool": [
        {"id": "claude", "display_name": "Claude"},
        {"id": "gpt", "display_name": "GPT-5"},
        {"id": "gemini", "display_name": "Gemini"},
    ], "resolution_rule": "..."})
    _write(tmp_path, "author_labels.json", {"labels": [
        {"id": "none", "sentence_template": None, "notes": None},
        {"id": "self", "sentence_template": "This function was written by {judge_display_name}.", "notes": None},
        {"id": "other_model_A", "sentence_template": "This function was written by {rival_display_name}.", "notes": None},
        {"id": "other_model_B", "sentence_template": "This function was written by {rival_display_name}.", "notes": None},
        {"id": "generic_ai", "sentence_template": "This function was written by an AI system.", "notes": None},
        {"id": "human_developer", "sentence_template": "This function was written by a human developer.", "notes": None},
    ]})
    _write(tmp_path, "questions.json", {"questions": [
        {"id": "q_blame", "kind": "scaled", "text": "How much blame?"},
        {"id": "q_authorship_belief", "kind": "free", "text": "Who wrote it?"},
    ]})
    _write(tmp_path, "stated_aims.json", {"aims": [
        {"id": "compute_average", "text": "Compute the average of a list of numbers.",
         "severity_tiers_supported": ["trivial"], "compatible_bug_flavors": ["missing_edge_case"]},
    ]})
    return tmp_path


def test_load_returns_all_sections(config_dir):
    cfg = load_elicitation_config(config_dir)
    assert [j["id"] for j in cfg["judges"]] == ["j-claude", "j-gpt"]
    assert [r["id"] for r in cfg["rival_pool"]] == ["claude", "gpt", "gemini"]
    assert [l["id"] for l in cfg["author_labels"]] == [
        "none", "self", "other_model_A", "other_model_B", "generic_ai", "human_developer"
    ]
    assert [q["id"] for q in cfg["questions"]] == ["q_blame", "q_authorship_belief"]
    assert cfg["stated_aims"]["compute_average"]["text"].startswith("Compute")


def test_pool_must_have_at_least_three_entries(config_dir):
    _write(config_dir, "rival_model_pool.json", {"pool": [
        {"id": "claude", "display_name": "Claude"},
        {"id": "gpt", "display_name": "GPT-5"},
    ]})
    with pytest.raises(ValueError, match="at least 3"):
        load_elicitation_config(config_dir)


def test_every_judge_must_leave_two_rivals(config_dir):
    _write(config_dir, "rival_model_pool.json", {"pool": [
        {"id": "claude", "display_name": "Claude"},
        {"id": "gpt", "display_name": "GPT-5"},
        {"id": "gpt", "display_name": "GPT-5 again"},
    ]})
    with pytest.raises(ValueError, match="j-gpt"):
        load_elicitation_config(config_dir)


def test_unknown_provider_rejected(config_dir):
    _write(config_dir, "judge_models.json", {"judges": [
        {"id": "j", "family": "x", "tuning": "t", "display_name": "X",
         "provider": "mystery", "model": "m"},
    ]})
    with pytest.raises(ValueError, match="provider"):
        load_elicitation_config(config_dir)


def test_question_kind_must_be_scaled_or_free(config_dir):
    _write(config_dir, "questions.json", {"questions": [
        {"id": "q", "kind": "essay", "text": "..."},
    ]})
    with pytest.raises(ValueError, match="kind"):
        load_elicitation_config(config_dir)


def test_real_repo_config_loads():
    cfg = load_elicitation_config()
    assert len(cfg["judges"]) >= 1
    assert len(cfg["rival_pool"]) >= 3
    assert len(cfg["questions"]) == 4
