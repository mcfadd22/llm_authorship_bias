from typing import Dict, List, Tuple


def resolve_rivals(judge: Dict, item_index: int, pool: List[Dict]) -> Tuple[Dict, Dict]:
    """Pick (other_model_A, other_model_B) for one judge/item.

    Drops every pool entry whose id equals the judge's family, then rotates through the
    remainder by item index so each rival cycles across items and A != B always.
    """
    remaining = [r for r in pool if r["id"] != judge["family"]]
    n = len(remaining)
    if n < 2:
        raise ValueError(
            f"judge '{judge['id']}' leaves only {n} rival(s) after excluding family "
            f"'{judge['family']}'; need at least 2"
        )
    return remaining[item_index % n], remaining[(item_index + 1) % n]
