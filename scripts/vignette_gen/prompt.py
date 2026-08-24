from typing import Dict, List

AIM_DEFEATING_INSTRUCTION = (
    "Position the bug so it breaks exactly what STATED_AIM promises - it "
    "undermines the stated purpose directly."
)
AIM_ORTHOGONAL_INSTRUCTION = (
    "Position the bug so it is incidental to STATED_AIM - the stated "
    "purpose still works correctly, but the bug affects something else "
    "in the function."
)
AIM_DEFEATING_VERIFICATION = "does the code fail STATED_AIM specifically because of the bug?"
AIM_ORTHOGONAL_VERIFICATION = "does the code still fully satisfy STATED_AIM despite the bug?"

_RELATION_CONTENT = {
    "aim_defeating": (AIM_DEFEATING_INSTRUCTION, AIM_DEFEATING_VERIFICATION),
    "aim_orthogonal": (AIM_ORTHOGONAL_INSTRUCTION, AIM_ORTHOGONAL_VERIFICATION),
}

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
- The function body should be approximately 8-25 lines (signature through
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

BUG_AIM_RELATION: {bug_aim_relation_id}
{bug_aim_relation_instruction}

Before answering, verify: {bug_aim_relation_verification} If not, revise
before returning.

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

    relation = item["bug_aim_relation"]
    if relation not in _RELATION_CONTENT:
        raise ValueError(f"unknown bug_aim_relation: {relation!r}")
    instruction, verification = _RELATION_CONTENT[relation]

    return TEMPLATE.format(
        stated_aim_text=aim["text"],
        bug_flavor_id=flavor["id"],
        bug_flavor_definition=flavor["definition"],
        bug_flavor_reference=flavor["reference"],
        bug_flavor_examples=_render_examples(flavor["examples"]),
        severity_tier_id=severity["id"],
        severity_tier_definition=severity["definition"],
        severity_tier_reference=severity["reference"],
        bug_aim_relation_id=relation,
        bug_aim_relation_instruction=instruction,
        bug_aim_relation_verification=verification,
    )
