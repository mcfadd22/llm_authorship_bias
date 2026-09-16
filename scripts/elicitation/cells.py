from typing import Dict, List, Tuple

RowKey = Tuple[str, str, str, str, str, int]
DEFAULT_CODE_VERSION = "buggy"


def row_key(row: Dict) -> RowKey:
    return (
        row["judge_id"],
        row["item_id"],
        row.get("code_version", DEFAULT_CODE_VERSION),
        row["author_label"],
        row["question_type"],
        int(row["repeat_idx"]),
    )


def enumerate_elicitations(
    items: List[Dict],
    judge: Dict,
    author_labels: List[Dict],
    questions: List[Dict],
    repeats: int,
) -> List[Dict]:
    """One dict per (item, author_label, question, repeat) for a single judge.

    Items are sorted by item_id so `item_index` (used for rival rotation) is stable across runs.
    Only questions whose `applies_to` includes the item's `code_version` are asked; a question
    with no `applies_to` applies to buggy items only.
    """
    rows = []
    for item_index, item in enumerate(sorted(items, key=lambda i: i["item_id"])):
        code_version = item.get("code_version", DEFAULT_CODE_VERSION)
        for label in author_labels:
            for question in questions:
                if code_version not in question.get("applies_to", [DEFAULT_CODE_VERSION]):
                    continue
                for repeat_idx in range(repeats):
                    rows.append(
                        {
                            "item_id": item["item_id"],
                            "item_index": item_index,
                            "cell_id": item["cell_id"],
                            "aim_id": item["aim_id"],
                            "judge_id": judge["id"],
                            "judge_family": judge["family"],
                            "judge_tuning": judge["tuning"],
                            "author_label": label["id"],
                            "severity_tier": item["severity_tier"],
                            "bug_flavor": item["bug_flavor"],
                            "code_version": code_version,
                            "question_type": question["id"],
                            "repeat_idx": repeat_idx,
                        }
                    )
    return rows
