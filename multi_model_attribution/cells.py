"""Enumerate the cells of the design for a judge, and the resumable row key."""
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

CAUSES = ("none", "callee", "caller")
FIDELITIES = ("full", "summary", "final_only")
NAME_LEVELS = ("frontier_to_small", "small_to_frontier", "self_to_other")
SPINS = ("truthful", "overclaiming")
COSMETIC_NAMES = "frontier_to_small"
COSMETIC_SPIN = "truthful"

RowKey = Tuple[str, str, str, str, str, str, str, str, int]


def row_key(row: Dict) -> RowKey:
    return (row["judge_id"], row["scenario_id"], row["variant"], row["cause"], row["fidelity"],
            row["names"], row["spin"], row["question_type"], int(row["repeat_idx"]))


def load_existing_keys(path: Path) -> Set[RowKey]:
    if not path.exists():
        return set()
    keys = set()
    with path.open() as f:
        for line in f:
            if line.strip():
                keys.add(row_key(json.loads(line)))
    return keys


def has_cosmetic(scenario: Dict) -> bool:
    c = scenario.get("cosmetic")
    return bool(c) and "skipped" not in c


def _cells_for(scenario: Dict, variant: str, names_levels, spins) -> List[Dict]:
    out = []
    for cause in CAUSES:
        for fidelity in FIDELITIES:
            note_shown = fidelity != "final_only"
            spin_levels = spins if (cause != "none" and note_shown) else ("truthful",)
            for names in names_levels:
                for spin in spin_levels:
                    out.append({"variant": variant, "cause": cause, "fidelity": fidelity, "names": names,
                                "spin": spin, "note_shown": note_shown, "truth": scenario["truth"][cause],
                                "failure_kind": scenario["failure_kind"].get(cause) if cause != "none" else None})
    return out


def enumerate_cells(scenarios: List[Dict], judge: Dict, questions: List[Dict], repeats: int) -> List[Dict]:
    rows = []
    for s in sorted(scenarios, key=lambda s: s["scenario_id"]):
        base = _cells_for(s, "base", NAME_LEVELS, SPINS)
        cells = base + (_cells_for(s, "renamed", (COSMETIC_NAMES,), (COSMETIC_SPIN,)) if has_cosmetic(s) else [])
        for cell in cells:
            for q in questions:
                if cell["cause"] not in q["applies_to_cause"]:
                    continue
                for r in range(repeats):
                    rows.append({"judge_id": judge["id"], "judge_family": judge["family"],
                                 "judge_params_b": judge.get("params_b"), "scenario_id": s["scenario_id"],
                                 "source_item_id": s["source_item_id"], "bank": s["bank"], "aim_id": s["aim_id"],
                                 "bug_flavor": s["bug_flavor"], **cell, "question_type": q["id"],
                                 "question_kind": q["kind"], "repeat_idx": r})
    return rows
