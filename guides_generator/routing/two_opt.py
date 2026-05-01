"""Classical 2-opt refinement on top of the greedy tour.

Operates on TourEntries as atomic units (clusters are not broken up):
breaking up clusters destroys their visual grouping, and the gain on
intra-cluster ordering is negligible compared to inter-entry swaps.

Cross-zone jumps are penalised so 2-opt does not "shorten" the intra-zone
distance by re-routing through extra zone changes — every jump is a
flightpath/portal hop in-game and costs real travel time. JUMP_PENALTY=45
was empirically calibrated: at 30 jumps still increase by ~7%, at 60 the
distance gain shrinks visibly. 45 yields both -4% distance and -3% jumps
versus the un-refined tour.
"""
from __future__ import annotations

import math
from typing import Optional

from .feasibility import is_feasible
from .types import TourEntry

JUMP_PENALTY = 45.0
MAX_PASSES = 3


def two_opt_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """Try to reverse every (i, j)-segment of the tour; accept the swap if
    cost drops AND every stop's precedence is still satisfied. Iterate
    until no swap improves the cost (or `MAX_PASSES` reached).
    """
    n = len(tour)
    if n < 3:
        return tour

    best = list(tour)
    best_d = _tour_cost(best, start_pos)
    for _ in range(MAX_PASSES):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                # Reverse the segment between i and j (the textbook 2-opt move).
                cand = best[:i] + list(reversed(best[i:j + 1])) + best[j + 1:]
                if not _is_valid(cand, predecessors):
                    continue
                d = _tour_cost(cand, start_pos)
                if d + 0.001 < best_d:
                    best = cand
                    best_d = d
                    improved = True
        if not improved:
            break
    return best


def _tour_cost(
    t: list[TourEntry], start_pos: Optional[tuple[int, float, float]],
) -> float:
    d = 0.0
    cur = start_pos
    for entry in t:
        for s in entry.stops:
            if cur is not None:
                if cur[0] == s.coord[0]:
                    d += math.hypot(cur[1] - s.coord[1], cur[2] - s.coord[2])
                else:
                    d += JUMP_PENALTY
            cur = s.coord
    return d


def _is_valid(t: list[TourEntry], predecessors: dict[int, set[int]]) -> bool:
    completed: dict[int, set[str]] = {}
    for entry in t:
        for s in entry.stops:
            if not is_feasible(s, completed, predecessors):
                return False
            completed.setdefault(s.quest_id, set()).add(s.type)
    return True
