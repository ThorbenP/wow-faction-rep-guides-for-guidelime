"""Tour orchestrator.

Builds a tour for one sub-guide and runs the full refinement chain.
There is no method switch — every run uses multistart with the
combined refinement chain that the v1.4.0 experiments identified as
optimal under rep/dist:

    Construction (`_greedy_build`)
        Greedy cluster discovery + on-the-way absorption from the
        spawn anchor (or no anchor for cleanup buckets).

    Multistart (`multistart.route_subguide_multistart`)
        K=64 randomized rebuilds with cost-aligned acceptance
        (distance + JUMP_PENALTY × jumps). Each candidate uses
        `refine_tour_fast` (no 3-opt) so the K-loop stays tractable;
        diversification is on three axes (random anchor, stochastic
        top-3 tiebreaker, cluster-radius jitter for half the budget).
        ILS finisher with mixed segment-reverse + double-bridge
        kernels escapes deeper local optima.

    Deep refinement on the winner (`refine_tour`)
        2-opt + or-opt convergence, 3-opt for tours with ≤ 50
        entries, defragmentation pass, Held-Karp DP for tours with
        ≤ 12 entries, and stop-level 2-opt + or-opt finishers that
        can break clusters where doing so shortens the route.

Returns `(tour, orphans)` — `orphans` is non-empty only if a
precedence deadlock leaves some Stops unreachable. Output emits them
under a "Not reachable" banner so the player at least sees them.
"""
from __future__ import annotations

from typing import Optional

from .cluster import absorb_on_the_way, discover_cluster, nearest_feasible
from .feasibility import build_predecessor_map, build_stop_list, mark_done
from .held_karp import held_karp_pass, held_karp_stop_level_pass
from .or_opt import or_opt_pass
from .stop_2opt import stop_level_2opt
from .stop_or_opt import stop_level_or_opt
from .three_opt import three_opt_pass
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
# chance to unlock each other's moves.
MAX_REFINE_ROUNDS = 8

# 3-opt is O(N³) per sweep. Past ~50 entries the per-sub-guide
# runtime starts to dominate the bulk run; sub-guides above the cap
# stay at 2-opt + or-opt.
THREE_OPT_MAX_ENTRIES = 50


def route_subguide(
    quests: list[dict],
    start_pos: Optional[tuple[int, float, float]] = None,
    cluster_radius: float = CLUSTER_RADIUS,
    detour_threshold: float = DETOUR_THRESHOLD,
) -> tuple[list[TourEntry], list[Stop]]:
    """Build and refine a tour for one sub-guide.

    `start_pos`: optional anchor for cluster discovery and the cost
    function. Pass `pick_start_position(quests)` for natural-tier zones to
    bias the tour toward the lowest-level quest (the racial spawn point in
    starter zones); leave `None` for cleanup or complex sections, where
    "where the player arrives" is not a meaningful concept.

    Always runs the multistart pipeline — there is no fast/exhaustive
    switch. Single-faction runs cost a few seconds, the full
    `--all` bulk pass takes ~8 minutes.
    """
    # Local import to avoid a circular dependency through tour.py.
    from .multistart import route_subguide_multistart
    return route_subguide_multistart(
        quests, start_pos=start_pos, cluster_radius=cluster_radius,
        detour_threshold=detour_threshold,
    )


def _greedy_build(
    quests: list[dict],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    cluster_radius: float,
    detour_threshold: float,
) -> tuple[list[TourEntry], list[Stop]]:
    """Greedy cluster + on-the-way absorption build (no refinement).

    Used by both the deterministic baseline and the per-candidate
    builds in multistart, so the two share the exact same construction
    semantics. Refinement is a separate step (`refine_tour` /
    `refine_tour_fast`).
    """
    stops = build_stop_list(quests)
    completed: dict[int, set[str]] = {}
    cur_pos = start_pos
    tour: list[TourEntry] = []

    while stops:
        cluster_stops = discover_cluster(
            stops, completed, predecessors, cur_pos, cluster_radius,
        )
        if cluster_stops:
            cur_pos = cluster_stops[-1].coord
            tour.append(TourEntry(kind='cluster', stops=cluster_stops))

        if not stops:
            break

        next_stop = nearest_feasible(stops, completed, predecessors, cur_pos)
        if next_stop is None:
            return tour, list(stops)

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

    return tour, []


def refine_tour(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    max_rounds: int = MAX_REFINE_ROUNDS,
) -> list[TourEntry]:
    """The full refinement chain. Runs once on the multistart winner.

      1. Alternating 2-opt + or-opt to convergence.
      2. 3-opt for tours with ≤ THREE_OPT_MAX_ENTRIES entries.
      3. Defragmentation pass (merges same-coord adjacencies).
      4. Held-Karp DP for tours with ≤ 12 entries.
      5. Stop-level 2-opt — can pull a stop out of its discovery-time
         cluster when a different position is geometrically cheaper.
      6. Stop-level or-opt — relocations of length 1..3 stops.

    Each step is monotone (cost never goes up), so the chain is safe
    regardless of where the input came from.
    """
    if not tour:
        return tour

    tour = _converge_two_or_opt(tour, predecessors, start_pos, max_rounds)

    if len(tour) <= THREE_OPT_MAX_ENTRIES:
        tour = three_opt_pass(tour, predecessors, start_pos)

    tour = _defragment_clusters(tour)
    tour = held_karp_pass(tour, predecessors, start_pos)
    tour = stop_level_2opt(tour, predecessors, start_pos)
    tour = stop_level_or_opt(tour, predecessors, start_pos)
    # Final exact pass: provably-optimal stop ordering for tours up to
    # `held_karp.MAX_STOPS` (30). Anything larger is left untouched.
    tour = held_karp_stop_level_pass(tour, predecessors, start_pos)
    return tour


def refine_tour_fast(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    max_rounds: int = MAX_REFINE_ROUNDS,
) -> list[TourEntry]:
    """Faster refinement chain used per multistart candidate.

    Drops 3-opt and the stop-level finishers — those are the steps
    whose per-pass cost grows fast enough that K=64 candidates would
    push runtime past acceptable. Held-Karp stays because it only
    fires on tours with ≤ 12 entries and finishes in milliseconds, so
    it pays for itself even inside the multistart loop.

    The deep `refine_tour` runs once afterwards on the chosen winner.
    """
    if not tour:
        return tour

    tour = _converge_two_or_opt(tour, predecessors, start_pos, max_rounds)
    tour = _defragment_clusters(tour)
    tour = held_karp_pass(tour, predecessors, start_pos)
    return tour


def _converge_two_or_opt(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    max_rounds: int,
) -> list[TourEntry]:
    """Alternate 2-opt and or-opt until neither improves cost or the
    cap is reached. Shared between fast and full refinement so both
    use the same convergence semantics.
    """
    prev_cost = _tour_cost(tour, start_pos)
    for _ in range(max_rounds):
        tour = two_opt_pass(tour, predecessors, start_pos)
        tour = or_opt_pass(tour, predecessors, start_pos)
        cost = _tour_cost(tour, start_pos)
        if cost + 0.001 >= prev_cost:
            break
        prev_cost = cost
    return tour


def _defragment_clusters(tour: list[TourEntry]) -> list[TourEntry]:
    """Merge consecutive entries whose join boundary is a zero-distance
    hop into one cluster.

    Two entries can be merged when the *last* stop of the first sits
    at the exact same `(zone, x, y)` as the *first* stop of the
    second. The merged entry is always a cluster, so single-stop
    travels that or-opt placed adjacent to a cluster at the same NPC
    are recovered as cluster members. Visit order and total distance
    are unchanged — only the cluster labelling shifts, which keeps the
    emitted Lua tighter without affecting rep/dist.
    """
    if len(tour) < 2:
        return tour
    merged: list[TourEntry] = []
    for entry in tour:
        if merged and merged[-1].stops[-1].coord == entry.stops[0].coord:
            merged[-1] = TourEntry(
                kind='cluster',
                stops=merged[-1].stops + entry.stops,
            )
        else:
            merged.append(entry)
    return merged
