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


def _item(bug_aim_relation):
    return {
        "aim_id": "aim_a",
        "bug_flavor": "missing_edge_case",
        "severity_tier": "trivial",
        "bug_aim_relation": bug_aim_relation,
    }


def test_prompt_includes_aim_flavor_and_severity_content():
    prompt = build_prompt(_item("aim_defeating"), CONFIG)

    assert "Compute the average of a list of numbers." in prompt
    assert "DEF-MEC" in prompt
    assert "REF-MEC" in prompt
    assert "SRC - NOTE" in prompt
    assert "DEF-TRIVIAL" in prompt
    assert "REF-TRIVIAL" in prompt


def test_prompt_aim_defeating_instruction():
    prompt = build_prompt(_item("aim_defeating"), CONFIG)
    assert "undermines the stated purpose directly" in prompt
    assert "does the code fail STATED_AIM specifically because of the bug?" in prompt


def test_prompt_aim_orthogonal_instruction():
    prompt = build_prompt(_item("aim_orthogonal"), CONFIG)
    assert "incidental to STATED_AIM" in prompt
    assert "does the code still fully satisfy STATED_AIM despite the bug?" in prompt


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
    prompt = build_prompt(_item("aim_defeating"), config)
    assert "(none documented)" in prompt
