from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Cell:
    aim_id: str
    bug_flavor: str
    severity_tier: str

    @property
    def cell_id(self) -> str:
        return f"{self.aim_id}__{self.bug_flavor}__{self.severity_tier}"


def enumerate_cells(stated_aims: List[Dict]) -> List[Cell]:
    cells = []
    for aim in stated_aims:
        for bug_flavor in aim["compatible_bug_flavors"]:
            for severity_tier in aim["severity_tiers_supported"]:
                cells.append(Cell(aim["id"], bug_flavor, severity_tier))
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
                }
            )
    return items
