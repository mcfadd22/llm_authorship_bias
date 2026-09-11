from typing import Dict, Optional, Tuple

PROMPT_VERSION = "2026-09-11-v1"


def aim_sentence(stated_aim_text: str) -> str:
    text = stated_aim_text.strip()
    return "This function is supposed to " + text[0].lower() + text[1:]


def author_sentence(label: Dict, judge: Dict, rivals: Tuple[Dict, Dict]) -> Optional[str]:
    template = label.get("sentence_template")
    if template is None:
        return None
    rival_a, rival_b = rivals
    if label["id"] == "other_model_A":
        return template.format(rival_display_name=rival_a["display_name"])
    if label["id"] == "other_model_B":
        return template.format(rival_display_name=rival_b["display_name"])
    return template.format(judge_display_name=judge["display_name"])


def build_elicitation_prompt(
    stated_aim_text: str,
    code: str,
    label: Dict,
    judge: Dict,
    rivals: Tuple[Dict, Dict],
    question: Dict,
) -> str:
    parts = [aim_sentence(stated_aim_text)]
    sentence = author_sentence(label, judge, rivals)
    if sentence is not None:
        parts.append(sentence)
    parts.append("```python\n" + code + "\n```")
    parts.append("Review this code.")
    parts.append(question["text"])
    return "\n\n".join(parts)
