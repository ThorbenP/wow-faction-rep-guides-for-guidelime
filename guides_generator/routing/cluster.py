"""Cluster discovery and on-the-way absorption — the two stop-grouping passes.

`discover_cluster` greedily collects all feasible stops within `cluster_radius`
of the current position, growing the cluster as each new stop redefines the
centre. `absorb_on_the_way` picks up stops that lie almost on the straight
line to a far-away target.
"""
from __future__ import annotations

from typing import Optional

from .distance import DIFFERENT_ZONE_PENALTY, dist
from .feasibility import is_feasible
from .types import Stop


def discover_cluster(
    stops: list[Stop],
    completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
    cur_pos: Optional[tuple[int, float, float]],
    cluster_radius: float,
) -> list[Stop]:
    """Iteratively collect feasible stops within `cluster_radius` of `pos`.

    Each collected stop becomes the new cluster centre, so the cluster grows
    incrementally as long as new feasible neighbours are within range.
    Removes the picked stops from `stops` as a side effect.
    """
    cluster: list[Stop] = []
    pos = cur_pos

    while True:
        candidates = [
            s for s in stops
            if is_feasible(s, completed, predecessors)
            and dist(pos, s.coord) <= cluster_radius
        ]
        if not candidates:
            break
        if pos is None:
            nearest = candidates[0]
        else:
            nearest = min(candidates, key=lambda s: dist(pos, s.coord))
        stops.remove(nearest)
        cluster.append(nearest)
        pos = nearest.coord
        # Marking the just-picked stop as done can unlock further stops in
        # the next iteration (e.g. a QA enables the same quest's QC).
        completed.setdefault(nearest.quest_id, set()).add(nearest.type)

    return cluster


def nearest_feasible(
    stops: list[Stop],
    completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
    cur_pos: Optional[tuple[int, float, float]],
) -> Optional[Stop]:
    """Closest still-feasible stop across all remaining stops."""
    feasible = [s for s in stops if is_feasible(s, completed, predecessors)]
    if not feasible:
        return None
    if cur_pos is None:
        return feasible[0]
    return min(feasible, key=lambda s: dist(cur_pos, s.coord))


def absorb_on_the_way(
    stops: list[Stop],
    completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
    cur_pos: tuple[int, float, float],
    target_pos: tuple[int, float, float],
    detour_threshold: float,
    cluster_radius: float,
) -> list[Stop]:
    """Greedy: while a feasible stop adds only a small detour to the trip
    cur -> s -> target, absorb it.

    Stops that already sit close to `target_pos` (within cluster_radius) are
    NOT absorbed here — the next cluster-discovery around target_pos will
    pick them up, which keeps them grouped instead of scattered as
    individual travel entries near the same location.
    """
    if dist(cur_pos, target_pos) >= DIFFERENT_ZONE_PENALTY:
        return []

    absorbed: list[Stop] = []
    pos = cur_pos

    while True:
        feasible = [s for s in stops if is_feasible(s, completed, predecessors)]
        best: Optional[Stop] = None
        best_detour = detour_threshold

        direct = dist(pos, target_pos)
        if direct >= DIFFERENT_ZONE_PENALTY:
            break
        for s in feasible:
            if dist(s.coord, target_pos) <= cluster_radius:
                continue
            via = dist(pos, s.coord) + dist(s.coord, target_pos)
            if via >= DIFFERENT_ZONE_PENALTY:
                continue
            detour = via - direct
            if detour < best_detour:
                best = s
                best_detour = detour

        if best is None:
            break
        stops.remove(best)
        absorbed.append(best)
        completed.setdefault(best.quest_id, set()).add(best.type)
        pos = best.coord

    return absorbed
