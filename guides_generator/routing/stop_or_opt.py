"""Stop-level or-opt: relocate a 1..3-stop segment to its cheapest
position, with cost-aligned acceptance.

Where stop-level 2-opt reverses a segment, stop-level or-opt
**relocates** a segment without reversing it. The two move kernels
find different classes of improvement — a relocation that moves a
single stop next to its same-coord neighbour produces a cluster the
re-cluster pass picks up; a reversal that flips a segment around the
same point leaves stops in place.

Implementation mirrors `routing.or_opt` but on stops instead of
TourEntries. Cost evaluation is full O(N) per candidate (no
incremental delta) — the per-pass count is small enough on these
tour sizes (typical ~50-300 stops) that the simpler implementation
keeps the bulk-run runtime acceptable.

Designed to run *once* on the multistart winner, after stop-level
2-opt has converged. A second pass with the same moves rarely finds
anything new on the test corpus.
"""
from __future__ import annotations

import math
from typing import Optional

from .feasibility import is_feasible
from .two_opt import JUMP_PENALTY
from .types import Stop, TourEntry

# Maximum number of "first-improving" relocations per call. Two passes
# is the convergence ceiling on the test corpus; more rarely improves.
MAX_PASSES = 2

# Segment lengths to try. k=1..3 is the same range entry-level or-opt
# uses; longer segments at stop level get expensive without
# proportional benefit.
SEGMENT_LENGTHS = (1, 2, 3)


def stop_level_or_opt(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """Run stop-level or-opt and return a re-clustered tour, or the
    input unchanged if no relocation improves cost. Monotone — never
    regresses.
    """
    stops = _flatten(tour)
    n = len(stops)
    if n < 4:
        return tour

    best_stops = stops
    best_tour = tour
    best_cost = _stop_cost(best_stops, start_pos)

    for _ in range(MAX_PASSES):
        improved = False
        for k in SEGMENT_LENGTHS:
            for i in range(n - k + 1):
                segment = best_stops[i:i + k]
                rest = best_stops[:i] + best_stops[i + k:]
                for j in range(len(rest) + 1):
                    if j == i:
                        continue  # no-op: re-insert at original slot
                    cand_stops = rest[:j] + segment + rest[j:]
                    cand_cost = _stop_cost(cand_stops, start_pos)
                    if cand_cost + 1e-6 >= best_cost:
                        continue
                    if not _is_valid_stops(cand_stops, predecessors):
                        continue
                    best_stops = cand_stops
                    best_cost = cand_cost
                    best_tour = _recluster(cand_stops)
                    improved = True
                    break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break

    return best_tour


def _flatten(tour: list[TourEntry]) -> list[Stop]:
    out: list[Stop] = []
    for entry in tour:
        out.extend(entry.stops)
    return out


def _stop_cost(
    stops: list[Stop], start_pos: Optional[tuple[int, float, float]],
) -> float:
    d = 0.0
    cur = start_pos
    for s in stops:
        if cur is not None:
            if cur[0] == s.coord[0]:
                d += math.hypot(cur[1] - s.coord[1], cur[2] - s.coord[2])
            else:
                d += JUMP_PENALTY
        cur = s.coord
    return d


def _is_valid_stops(
    stops: list[Stop], predecessors: dict[int, set[int]],
) -> bool:
    completed: dict[int, set[str]] = {}
    for s in stops:
        if not is_feasible(s, completed, predecessors):
            return False
        completed.setdefault(s.quest_id, set()).add(s.type)
    return True


def _recluster(stops: list[Stop]) -> list[TourEntry]:
    out: list[TourEntry] = []
    for s in stops:
        if out and out[-1].stops[-1].coord == s.coord:
            out[-1] = TourEntry(
                kind='cluster',
                stops=out[-1].stops + [s],
            )
        else:
            out.append(TourEntry(kind='travel', stops=[s]))
    return out
