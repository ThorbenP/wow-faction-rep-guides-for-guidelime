"""Stop-level 2-opt with cost-aligned acceptance.

Flattens the tour into a stop sequence, runs 2-opt over stops, then
re-clusters the result. Lets a single stop leave its discovery-time
cluster when a different position has a lower `_tour_cost` (distance
+ JUMP_PENALTY × jumps) — under v1.4.0's rep/dist metric this is
exactly what we want, since rep is fixed and minimising cost ≡
maximising rep/dist.

Acceptance is on the post-recluster cost so a move that fragments a
cluster but does not actually shorten the route gets rejected
(the re-cluster pass would lose the same-coord adjacency, and the
recombined cost would not improve).

Uses MAX_PASSES=2 — the per-stop O(N²) sweep is cheap once but
diminishing returns kick in fast on these tour sizes. Designed to
run *once* on the multistart winner, not inside the multistart loop.
"""
from __future__ import annotations

import math
from typing import Optional

from .feasibility import is_feasible
from .two_opt import JUMP_PENALTY
from .types import Stop, TourEntry

# Per-pass complexity is O(N²) where N is total stops. With ~280 stops
# in Stormwind sub-guides this is ~80k candidates per pass; two passes
# is the convergence ceiling on the test corpus.
MAX_PASSES = 2


def stop_level_2opt(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """Run stop-level 2-opt and return a re-clustered tour, or the
    input unchanged if no move improves cost. Monotone — never
    regresses.
    """
    stops = _flatten(tour)
    n = len(stops)
    if n < 4:
        return tour

    # Incumbent is the *input* tour, not its re-clustered flatten;
    # re-clustering with strict same-coord splits any radius-based
    # cluster the build pipeline produced, which the input does not
    # need to give back to find improvements against.
    best_stops = stops
    best_tour = tour
    best_cost = _stop_cost(best_stops, start_pos)

    for _ in range(MAX_PASSES):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand_stops = (
                    best_stops[:i] + list(reversed(best_stops[i:j + 1])) +
                    best_stops[j + 1:]
                )
                cand_cost = _stop_cost(cand_stops, start_pos)
                if cand_cost + 1e-6 >= best_cost:
                    continue
                if not _is_valid_stops(cand_stops, predecessors):
                    continue
                best_stops = cand_stops
                best_cost = cand_cost
                best_tour = _recluster(cand_stops)
                improved = True
        if not improved:
            break

    return best_tour


def _flatten(tour: list[TourEntry]) -> list[Stop]:
    """Concatenate every entry's stop list."""
    out: list[Stop] = []
    for entry in tour:
        out.extend(entry.stops)
    return out


def _stop_cost(
    stops: list[Stop], start_pos: Optional[tuple[int, float, float]],
) -> float:
    """Same cost model as `two_opt._tour_cost`, evaluated stop-by-stop."""
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
    """Group consecutive same-coord stops into cluster TourEntries."""
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
