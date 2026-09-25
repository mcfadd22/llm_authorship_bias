import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_json(config_dir: Path, name: str) -> dict:
    return json.loads((config_dir / name).read_text())


def load_config(config_dir: Optional[Path] = None) -> Dict:
    config_dir = config_dir or DEFAULT_CONFIG_DIR

    bug_flavor = {lvl["id"]: lvl for lvl in _load_json(config_dir, "bug_flavor.json")["levels"]}
    severity_tier = {
        lvl["id"]: lvl for lvl in _load_json(config_dir, "severity_tier.json")["levels"]
    }
    stated_aims = _load_json(config_dir, "stated_aims.json")["aims"]

    for aim in stated_aims:
        if not aim.get("contract", "").strip():
            raise ValueError(f"aim '{aim['id']}' has no contract")

        flavors = aim.get("flavors")
        if not isinstance(flavors, dict) or not flavors:
            raise ValueError(f"aim '{aim['id']}' has no flavors map")

        for flavor_id, spec in flavors.items():
            if flavor_id not in bug_flavor:
                raise ValueError(
                    f"aim '{aim['id']}' references unknown bug_flavor '{flavor_id}'"
                )
            tiers = spec.get("severity_tiers")
            if not tiers:
                raise ValueError(
                    f"aim '{aim['id']}' flavor '{flavor_id}' has no severity_tiers"
                )
            for tier in tiers:
                if tier not in severity_tier:
                    raise ValueError(
                        f"aim '{aim['id']}' flavor '{flavor_id}' references "
                        f"unknown severity_tier '{tier}'"
                    )

    return {
        "bug_flavor": bug_flavor,
        "severity_tier": severity_tier,
        "stated_aims": stated_aims,
    }
