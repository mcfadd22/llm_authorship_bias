"""Choose the source items for scenarios. Pure functions; pre-registered rule.

Pool: item verdict ok, twin verdict ok, no aim-visibility "no" caveat, flavour observable from
a contract-correct caller, and a clean twin present. Order: round-robin over aims (gpt5 bank
before gemini within an aim) so the chosen set spreads across aims.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

OBSERVABLE_FLAVORS = {"logic_error", "wrong_algorithm", "missing_edge_case", "silent_failure", "known_trap"}
EXCLUDING_CAVEATS = {"aim_visibility_no", "aim_visibility_likely_no"}
BANK_ORDER = {"items_gpt5": 0, "items_gemini25pro": 1}


def load_verdicts(paths: Iterable[Path]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for p in paths:
        with open(p, newline="") as f:
            for row in csv.DictReader(f):
                out[row["item_id"]] = row
    return out


def load_caveats(path: Path) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    if not Path(path).exists():
        return out
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[row["item_id"]].append(row["caveat"])
    return out


def eligible(item: Dict, twin: Dict | None, verdict: Dict[str, str] | None, caveats: List[str]) -> bool:
    if twin is None or verdict is None:
        return False
    if verdict.get("verdict") != "ok" or verdict.get("twin_verdict") != "ok":
        return False
    if set(caveats) & EXCLUDING_CAVEATS:
        return False
    return item["bug_flavor"] in OBSERVABLE_FLAVORS


def build_pool(banks: List[Tuple[str, Path, Path]], verdicts: Dict[str, Dict[str, str]],
               caveats: Dict[str, List[str]]) -> List[Dict]:
    """banks: (bank name, buggy dir, clean dir). Returns eligible candidate records."""
    pool = []
    for bank, buggy_dir, clean_dir in banks:
        for p in sorted(Path(buggy_dir).glob("*.json")):
            item = json.loads(p.read_text())
            twin_path = Path(clean_dir) / p.name
            twin = json.loads(twin_path.read_text()) if twin_path.exists() else None
            iid = item["item_id"]
            if not eligible(item, twin, verdicts.get(iid), caveats.get(iid, [])):
                continue
            pool.append({
                "source_item_id": iid,
                "bank": bank,
                "aim_id": item["aim_id"],
                "bug_flavor": item["bug_flavor"],
                "sample_idx": item.get("sample_idx", 0),
                "buggy_code": item["code"],
                "clean_code": twin["code"],
                "bug_rationale": item.get("rationale", ""),
                "caveats": sorted(caveats.get(iid, [])),
            })
    return pool


def order_round_robin(pool: List[Dict]) -> List[Dict]:
    """Deterministic: within an aim sort by (bank order, sample_idx), with the bank priority
    alternating across aims so both banks are drawn evenly; then interleave aims."""
    by_aim: Dict[str, List[Dict]] = defaultdict(list)
    aims = sorted({c["aim_id"] for c in pool})
    flip = {a: (i % 2 == 1) for i, a in enumerate(aims)}
    def bank_rank(c):
        r = BANK_ORDER.get(c["bank"], 9)
        return (1 - r) if (flip[c["aim_id"]] and r in (0, 1)) else r
    for c in sorted(pool, key=lambda c: (c["aim_id"], bank_rank(c), c["sample_idx"], c["source_item_id"])):
        by_aim[c["aim_id"]].append(c)
    ordered = []
    while any(by_aim[a] for a in aims):
        for a in aims:
            if by_aim[a]:
                ordered.append(by_aim[a].pop(0))
    return ordered


def select(pool: List[Dict], n: int) -> List[Dict]:
    return order_round_robin(pool)[:n]
