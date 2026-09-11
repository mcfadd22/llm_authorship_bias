from typing import Dict, List, Tuple

RowKey = Tuple[str, str, str, str, int]


def row_key(row: Dict) -> RowKey:
    return (
        row["judge_id"],
        row["item_id"],
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
    """
    rows = []
    for item_index, item in enumerate(sorted(items, key=lambda i: i["item_id"])):
        for label in author_labels:
            for question in questions:
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
                            "question_type": question["id"],
                            "repeat_idx": repeat_idx,
                        }
                    )
    return rows
