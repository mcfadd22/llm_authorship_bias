import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
KNOWN_PROVIDERS = ("anthropic", "openai")
QUESTION_KINDS = ("scaled", "free", "detect")
CODE_VERSIONS = ("buggy", "clean")


def _load_json(config_dir: Path, name: str) -> dict:
    return json.loads((config_dir / name).read_text())


def load_elicitation_config(config_dir: Optional[Path] = None) -> Dict:
    config_dir = config_dir or DEFAULT_CONFIG_DIR

    judges = _load_json(config_dir, "judge_models.json")["judges"]
    rival_pool = _load_json(config_dir, "rival_model_pool.json")["pool"]
    author_labels = _load_json(config_dir, "author_labels.json")["labels"]
    questions = _load_json(config_dir, "questions.json")["questions"]
    stated_aims = {a["id"]: a for a in _load_json(config_dir, "stated_aims.json")["aims"]}

    if len(rival_pool) < 3:
        raise ValueError(f"rival_model_pool.json must have at least 3 entries, found {len(rival_pool)}")

    for judge in judges:
        if judge["provider"] not in KNOWN_PROVIDERS:
            raise ValueError(
                f"judge '{judge['id']}' has unknown provider '{judge['provider']}'; "
                f"expected one of {KNOWN_PROVIDERS}"
            )
        remaining = [r for r in rival_pool if r["id"] != judge["family"]]
        if len(remaining) < 2:
            raise ValueError(
                f"judge '{judge['id']}' (family '{judge['family']}') leaves only "
                f"{len(remaining)} rival(s) in the pool; need at least 2"
            )

    for q in questions:
        if q["kind"] not in QUESTION_KINDS:
            raise ValueError(
                f"question '{q['id']}' has unknown kind '{q['kind']}'; expected one of {QUESTION_KINDS}"
            )
        q.setdefault("applies_to", ["buggy"])
        bad = [v for v in q["applies_to"] if v not in CODE_VERSIONS]
        if bad:
            raise ValueError(
                f"question '{q['id']}' applies_to has unknown code_version(s) {bad}; "
                f"expected values from {CODE_VERSIONS}"
            )

    return {
        "judges": judges,
        "rival_pool": rival_pool,
        "author_labels": author_labels,
        "questions": questions,
        "stated_aims": stated_aims,
    }
