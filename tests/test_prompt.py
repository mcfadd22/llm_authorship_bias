import pytest

from vignette_gen.prompt import build_prompt

CONFIG = {
    "stated_aims": [
        {
            "id": "aim_a",
            "text": "Compute the average of a list of numbers.",
            "contract": "Returns the arithmetic mean. Returns None for an empty list.",
        }
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
    assert "Returns the arithmetic mean. Returns None for an empty list." in prompt


def test_prompt_states_the_contract_and_forbids_other_defects():
    """Without this the generator settles boundary behaviour itself, which is
    how the two wave-1 average twins ended up returning None and 0."""
    prompt = build_prompt(_item(), CONFIG)
    assert "CONTRACT" in prompt
    assert "The planted bug must be the only defect." in prompt


def test_prompt_omits_severity_when_the_pairing_admits_both_tiers():
    """severity_tier is recorded, not requested; where the rubric does not force
    one there is nothing to ask the generator for."""
    item = {**_item(), "severity_tier": None}
    prompt = build_prompt(item, CONFIG)
    assert "SEVERITY_TIER" not in prompt
    assert "DEF-TRIVIAL" not in prompt
    assert "DEF-MEC" in prompt


def test_build_prompt_preserves_braces_in_contract_text():
    config = {
        **CONFIG,
        "stated_aims": [
            {
                "id": "aim_a",
                "text": "t",
                "contract": "Returns {'total': n} and nothing else.",
            }
        ],
    }
    prompt = build_prompt(_item(), config)
    assert "Returns {'total': n} and nothing else." in prompt


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
            {
                "id": "aim_a",
                "text": "Do something with a dict like {'key': 'value'}.",
                "contract": "Returns {'ok': True}.",
            }
        ],
    }
    prompt = build_prompt(_item(), config)
    assert "Do something with a dict like {'key': 'value'}." in prompt
