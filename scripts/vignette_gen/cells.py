from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Cell:
    aim_id: str
    bug_flavor: str
    severity_tier: str
    bug_aim_relation: str

    @property
    def cell_id(self) -> str:
        return f"{self.aim_id}__{self.bug_flavor}__{self.severity_tier}__{self.bug_aim_relation}"


def enumerate_cells(stated_aims: List[Dict]) -> List[Cell]:
    cells = []
    for aim in stated_aims:
        for flavor_entry in aim["compatible_bug_flavors"]:
            relations = ["aim_defeating"]
            if flavor_entry["orthogonal_plausible"]:
                relations.append("aim_orthogonal")
            for severity_tier in aim["severity_tiers_supported"]:
                for relation in relations:
                    cells.append(
                        Cell(aim["id"], flavor_entry["flavor_id"], severity_tier, relation)
                    )
    return cells


def expand_items(cells: List[Cell], samples_per_cell: int) -> List[Dict]:
    items = []
    for cell in cells:
        for sample_idx in range(samples_per_cell):
            items.append(
                {
                    "item_id": f"{cell.cell_id}__{sample_idx:03d}",
                    "cell_id": cell.cell_id,
                    "sample_idx": sample_idx,
                    "aim_id": cell.aim_id,
                    "bug_flavor": cell.bug_flavor,
                    "severity_tier": cell.severity_tier,
                    "bug_aim_relation": cell.bug_aim_relation,
                }
            )
    return items
