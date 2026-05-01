"""Map distance helper used everywhere in the routing pipeline.

Cross-zone distance returns a synthetic penalty (`DIFFERENT_ZONE_PENALTY`) so
the algorithm never picks a cross-zone neighbour as nearest and never absorbs
across a zone boundary. Cross-zone movement in WoW is flightpath / portal
travel and not comparable to walking distance.
"""
from __future__ import annotations

import math
from typing import Optional

# Synthetic distance used when two stops are in different zones. Effectively
# means "infinity" so the routing never picks a cross-zone neighbour as the
# nearest stop and never tries to absorb across zone boundaries.
DIFFERENT_ZONE_PENALTY = 1e6


def dist(a: Optional[tuple[int, float, float]],
         b: tuple[int, float, float]) -> float:
    """Euclidean distance within a zone; cross-zone returns the penalty."""
    if a is None:
        return 0.0
    if a[0] != b[0]:
        return DIFFERENT_ZONE_PENALTY
    return math.hypot(a[1] - b[1], a[2] - b[2])
