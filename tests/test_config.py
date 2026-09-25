import json
from pathlib import Path

import pytest

from vignette_gen.config import load_config


def _write_config(tmp_path: Path, aims: list, flavors=("logic_error",), tiers=("trivial",)) -> Path:
    (tmp_path / "bug_flavor.json").write_text(
        json.dumps({"levels": [{"id": f, "definition": "d"} for f in flavors]})
    )
    (tmp_path / "severity_tier.json").write_text(
        json.dumps({"levels": [{"id": t, "definition": "d"} for t in tiers]})
    )
    (tmp_path / "stated_aims.json").write_text(json.dumps({"aims": aims}))
    return tmp_path


def _aim(**overrides) -> dict:
    aim = {
        "id": "aim_1",
        "text": "x",
        "contract": "Returns the thing.",
        "contract_status": "confirmed",
        "flavors": {"logic_error": {"severity_tiers": ["trivial"]}},
    }
    aim.update(overrides)
    return aim


def test_load_config_rejects_unknown_bug_flavor(tmp_path):
    _write_config(tmp_path, [_aim(flavors={"not_a_real_flavor": {"severity_tiers": ["trivial"]}})])
    with pytest.raises(ValueError, match="not_a_real_flavor"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_unknown_severity_tier(tmp_path):
    _write_config(tmp_path, [_aim(flavors={"logic_error": {"severity_tiers": ["not_a_real_tier"]}})])
    with pytest.raises(ValueError, match="not_a_real_tier"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_an_aim_with_no_contract(tmp_path):
    """Without a contract the generator invents boundary behaviour per item,
    which is what produced the wave-1 twins that disagreed with each other."""
    _write_config(tmp_path, [_aim(contract="   ")])
    with pytest.raises(ValueError, match="no contract"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_an_aim_with_no_flavors(tmp_path):
    _write_config(tmp_path, [_aim(flavors={})])
    with pytest.raises(ValueError, match="no flavors map"):
        load_config(config_dir=tmp_path)


def test_load_config_rejects_a_flavor_with_no_severity_tiers(tmp_path):
    _write_config(tmp_path, [_aim(flavors={"logic_error": {}})])
    with pytest.raises(ValueError, match="no severity_tiers"):
        load_config(config_dir=tmp_path)


def test_load_config_indexes_flavors_and_severities_by_id(tmp_path):
    _write_config(tmp_path, [_aim()])
    config = load_config(config_dir=tmp_path)

    assert config["bug_flavor"]["logic_error"]["definition"] == "d"
    assert config["severity_tier"]["trivial"]["definition"] == "d"
    assert config["stated_aims"][0]["id"] == "aim_1"
    assert config["stated_aims"][0]["flavors"]["logic_error"]["severity_tiers"] == ["trivial"]


def test_real_config_loads_without_error():
    config = load_config()
    assert len(config["bug_flavor"]) == 7
    assert len(config["severity_tier"]) == 2
    assert config["stated_aims"]


def test_real_config_aim_ids_are_unique():
    ids = [aim["id"] for aim in load_config()["stated_aims"]]
    assert len(ids) == len(set(ids))


def test_real_config_every_aim_contract_is_confirmed():
    unconfirmed = [
        aim["id"] for aim in load_config()["stated_aims"]
        if aim.get("contract_status") != "confirmed"
    ]
    assert unconfirmed == []


def test_real_config_every_bug_flavor_is_reachable():
    """A flavour no aim lists can never be generated, so it would silently
    drop out of the item bank rather than fail loudly."""
    config = load_config()
    used = {f for aim in config["stated_aims"] for f in aim["flavors"]}
    orphans = sorted(set(config["bug_flavor"]) - used)
    assert orphans == []
