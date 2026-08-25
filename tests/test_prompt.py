import pytest

from vignette_gen.prompt import build_prompt

CONFIG = {
    "stated_aims": [
        {"id": "aim_a", "text": "Compute the average of a list of numbers."}
    ],
    "bug_flavor": {
        "missing_edge_case": {
            "id": "missing_edge_case",
            "definition": "DEF-MEC",
            "reference": "REF-MEC",
            "examples": [{"source": "SRC", "note": "NOTE"}],
        }
    },
    "severity_tier": {
        "trivial": {"id": "trivial", "definition": "DEF-TRIVIAL", "reference": "REF-TRIVIAL"}
    },
}


def _item():
    return {
        "aim_id": "aim_a",
        "bug_flavor": "missing_edge_case",
        "severity_tier": "trivial",
    }


def test_prompt_includes_aim_flavor_and_severity_content():
    prompt = build_prompt(_item(), CONFIG)

    assert "Compute the average of a list of numbers." in prompt
    assert "DEF-MEC" in prompt
    assert "REF-MEC" in prompt
    assert "SRC - NOTE" in prompt
    assert "DEF-TRIVIAL" in prompt
    assert "REF-TRIVIAL" in prompt


def test_prompt_handles_no_examples():
    config = {
        **CONFIG,
        "bug_flavor": {
            "missing_edge_case": {
                **CONFIG["bug_flavor"]["missing_edge_case"],
                "examples": [],
            }
        },
    }
    prompt = build_prompt(_item(), config)
    assert "(none documented)" in prompt


def test_build_prompt_raises_clear_error_for_unknown_aim_id():
    item = _item()
    item["aim_id"] = "does_not_exist"
    with pytest.raises(ValueError, match="does_not_exist"):
        build_prompt(item, CONFIG)


def test_build_prompt_preserves_braces_in_config_content():
    config = {
        **CONFIG,
        "stated_aims": [
            {"id": "aim_a", "text": "Do something with a dict like {'key': 'value'}."}
        ],
    }
    prompt = build_prompt(_item(), config)
    assert "Do something with a dict like {'key': 'value'}." in prompt
