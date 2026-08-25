from typing import Dict, List

TEMPLATE = """You are generating a single Python function for a research study on how
bugs in code are judged.

Requirements:
- Language: Python only.
- Exactly one self-contained function (no helper functions, no classes). A
  leading module-level import statement is allowed if needed (e.g. `import
  json`); no other top-level statements.
- No comments and no docstrings in the code.
- No suggestive variable/function names or coding style that hints at
  whether the bug is intentional, careless, or reflects a competence gap.
  Use names that would be typical and neutral for this task.
- The function body should be approximately 5-25 lines (signature through
  return) - long enough for the bug to be clearly present, not padded
  with unrelated logic.

STATED_AIM: "{stated_aim_text}"

BUG_FLAVOR: {bug_flavor_id}
Definition: {bug_flavor_definition}
Reference/grounding: {bug_flavor_reference}
Examples: {bug_flavor_examples}

SEVERITY_TIER: {severity_tier_id}
Definition: {severity_tier_definition}
Reference/grounding: {severity_tier_reference}

Return JSON with exactly these fields:
{{
  "code": "<code string>",
  "rationale": "<short technical note on what the bug is and where it is in the code - for human vetting only, never shown to judge models>"
}}
"""


def _render_examples(examples: List[Dict]) -> str:
    if not examples:
        return "(none documented)"
    return "; ".join(f"{ex['source']} - {ex['note']}" for ex in examples)


def build_prompt(item: Dict, config: Dict) -> str:
    aim = next((a for a in config["stated_aims"] if a["id"] == item["aim_id"]), None)
    if aim is None:
        raise ValueError(f"unknown aim_id: {item['aim_id']!r}")

    flavor = config["bug_flavor"][item["bug_flavor"]]
    severity = config["severity_tier"][item["severity_tier"]]

    return TEMPLATE.format(
        stated_aim_text=aim["text"],
        bug_flavor_id=flavor["id"],
        bug_flavor_definition=flavor["definition"],
        bug_flavor_reference=flavor["reference"],
        bug_flavor_examples=_render_examples(flavor["examples"]),
        severity_tier_id=severity["id"],
        severity_tier_definition=severity["definition"],
        severity_tier_reference=severity["reference"],
    )
