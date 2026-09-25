import json
from pathlib import Path

import pytest

from vignette_gen.config import load_config


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


def test_load_config_rejects_unknown_bug_flavor(tmp_path):
    _write_json(tmp_path / "bug_flavor.json", {"levels": [{"id": "logic_error"}]})
    _write_json(tmp_path / "severity_tier.json", {"levels": [{"id": "trivial"}]})
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "bad_aim",
                    "text": "x",
                    "severity_tiers_supported": ["trivial"],
                    "compatible_bug_flavors": ["not_a_real_flavor"],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="not_a_real_flavor"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_unknown_severity_tier(tmp_path):
    _write_json(tmp_path / "bug_flavor.json", {"levels": [{"id": "logic_error"}]})
    _write_json(tmp_path / "severity_tier.json", {"levels": [{"id": "trivial"}]})
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "bad_aim",
                    "text": "x",
                    "severity_tiers_supported": ["not_a_real_tier"],
                    "compatible_bug_flavors": ["logic_error"],
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="not_a_real_tier"):
        load_config(config_dir=tmp_path)


def test_load_config_indexes_flavors_and_severities_by_id(tmp_path):
    _write_json(
        tmp_path / "bug_flavor.json",
        {"levels": [{"id": "logic_error", "definition": "d"}]},
    )
    _write_json(
        tmp_path / "severity_tier.json",
        {"levels": [{"id": "trivial", "definition": "d"}]},
    )
    _write_json(
        tmp_path / "stated_aims.json",
        {
            "aims": [
                {
                    "id": "aim_1",
                    "text": "x",
                    "severity_tiers_supported": ["trivial"],
                    "compatible_bug_flavors": ["logic_error"],
                }
            ]
        },
    )

    config = load_config(config_dir=tmp_path)

    assert config["bug_flavor"]["logic_error"]["definition"] == "d"
    assert config["severity_tier"]["trivial"]["definition"] == "d"
    assert config["stated_aims"][0]["id"] == "aim_1"


def test_real_config_loads_without_error():
    config = load_config()
    assert len(config["bug_flavor"]) == 7
    assert len(config["severity_tier"]) == 2
    assert config["stated_aims"]


def test_real_config_aim_ids_are_unique():
    ids = [aim["id"] for aim in load_config()["stated_aims"]]
    assert len(ids) == len(set(ids))


def test_real_config_every_aim_has_a_contract():
    """The contract is what makes 'correct' decidable; an aim without one
    leaves the generator to invent boundary behaviour per item."""
    missing = [
        aim["id"] for aim in load_config()["stated_aims"]
        if not aim.get("contract", "").strip()
    ]
    assert missing == []


def test_real_config_every_bug_flavor_is_reachable():
    """A flavour no aim lists can never be generated, so it would silently
    drop out of the item bank rather than fail loudly."""
    config = load_config()
    used = {f for aim in config["stated_aims"] for f in aim["compatible_bug_flavors"]}
    orphans = sorted(set(config["bug_flavor"]) - used)
    assert orphans == []
