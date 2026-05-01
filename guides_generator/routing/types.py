"""Stop and TourEntry — the data carriers shared across the routing pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Stop:
    """One routing waypoint. `type` is one of QA (pickup), QC (objective), QT (turnin)."""
    type: str
    quest: dict
    coord: tuple[int, float, float]  # (zone, x, y)

    @property
    def quest_id(self) -> int:
        return self.quest['id']


@dataclass
class TourEntry:
    """One entry in the emitted tour.

    `kind == 'cluster'`: multiple stops at roughly the same location, visited
    in sequence without a separate travel hop.
    `kind == 'travel'`: a single stop reached by travel from the previous
    position.
    """
    kind: str  # 'cluster' | 'travel'
    stops: list[Stop] = field(default_factory=list)
