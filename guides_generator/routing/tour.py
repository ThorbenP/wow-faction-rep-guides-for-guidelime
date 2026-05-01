"""Tour orchestrator: alternates cluster discovery, on-the-way absorption,
and direct travel until every Stop is placed; then refines the tour by
alternating 2-opt and or-opt passes until both converge.

Returns `(tour, orphans)` — `orphans` is non-empty only if a precedence
deadlock leaves some Stops unreachable. Output emits them under a
"Not reachable" banner so the player at least sees them.
"""
from __future__ import annotations

from typing import Optional

from .cluster import absorb_on_the_way, discover_cluster, nearest_feasible
from .feasibility import build_predecessor_map, build_stop_list, mark_done
from .or_opt import or_opt_pass
from .two_opt import _tour_cost, two_opt_pass
from .types import Stop, TourEntry

# Default cluster radius — overridable per zone via
# `constants.zones.ZONE_CLUSTER_RADIUS`. Sparse zones (e.g. Tanaris) need
# a wider radius than dense city hubs (Stormwind).
CLUSTER_RADIUS = 12.0

# Maximum acceptable detour for "on-the-way" absorption: a stop is picked up
# during travel only if the extra distance via that stop is below this value.
DETOUR_THRESHOLD = 6.0

# Upper bound on (2-opt + or-opt) refinement rounds. Each pass has its
# own internal MAX_PASSES; the outer loop just gives the two heuristics a
# chance to unlock each other's moves. The loop also breaks early as soon
# as one round leaves the cost unchanged, so most sub-guides terminate
# well before the cap.
MAX_REFINE_ROUNDS = 8


def route_subguide(
    quests: list[dict],
    start_pos: Optional[tuple[int, float, float]] = None,
    cluster_radius: float = CLUSTER_RADIUS,
    detour_threshold: float = DETOUR_THRESHOLD,
) -> tuple[list[TourEntry], list[Stop]]:
    """Build a tour from the given quests, then refine it with alternating
    2-opt and or-opt passes until convergence (or `MAX_REFINE_ROUNDS`).

    `start_pos`: optional anchor for cluster discovery and the cost
    function. Pass `pick_start_position(quests)` for natural-tier zones to
    bias the tour toward the lowest-level quest (the racial spawn point in
    starter zones); leave `None` for cleanup or complex sections, where
    "where the player arrives" is not a meaningful concept.
    """
    stops = build_stop_list(quests)
    predecessors = build_predecessor_map(quests)
    completed: dict[int, set[str]] = {}
    cur_pos = start_pos
    tour: list[TourEntry] = []

    while stops:
        # Step 1: cluster discovery around cur_pos. Marks completed in-place.
        cluster_stops = discover_cluster(
            stops, completed, predecessors, cur_pos, cluster_radius,
        )
        if cluster_stops:
            cur_pos = cluster_stops[-1].coord
            tour.append(TourEntry(kind='cluster', stops=cluster_stops))

        if not stops:
            break

        # Step 2: pick the next reachable stop further away.
        next_stop = nearest_feasible(stops, completed, predecessors, cur_pos)
        if next_stop is None:
            return tour, list(stops)

        # Step 3: on the way to next_stop, absorb stops with a small detour.
        stops.remove(next_stop)
        absorbed = absorb_on_the_way(
            stops, completed, predecessors, cur_pos, next_stop.coord,
            detour_threshold, cluster_radius,
        )
        for s in absorbed:
            cur_pos = s.coord
            tour.append(TourEntry(kind='travel', stops=[s]))

        mark_done(completed, next_stop)
        cur_pos = next_stop.coord
        tour.append(TourEntry(kind='travel', stops=[next_stop]))

    # Alternate 2-opt and or-opt until neither finds a further improvement.
    # 2-opt reverses (i, j)-segments; or-opt relocates short sub-sequences.
    # Each can unlock moves the other cannot reach in a single pass, so
    # alternating squeezes more distance out of the route. We bail as soon
    # as one round leaves the cost unchanged — by then both heuristics have
    # converged on the same local optimum.
    prev_cost = _tour_cost(tour, start_pos)
    for _ in range(MAX_REFINE_ROUNDS):
        tour = two_opt_pass(tour, predecessors, start_pos)
        tour = or_opt_pass(tour, predecessors, start_pos)
        cost = _tour_cost(tour, start_pos)
        if cost + 0.001 >= prev_cost:
            break
        prev_cost = cost
    return tour, []
