"""Multistart router: run K randomized builds, refine each, keep the cheapest.

This is the always-on routing pipeline as of v1.5.0. The greedy
build alone is deterministic (always-nearest-feasible from a fixed
anchor) and converges to whatever local optimum the alternating
2-opt + or-opt reaches from that single starting point. Multistart
breaks the determinism along three orthogonal axes so K=64 candidate
tours land in K different basins; the cheapest under `_tour_cost`
(distance + JUMP_PENALTY × jumps) wins.

Why cost-aligned selection? Total rep is fixed by the input — every
candidate tour for the same sub-guide carries the exact same `rep`,
so the headline metric `rep / dist` reduces to `constant / dist`.
Maximising rep/dist therefore *is* minimising
`distance + JUMP_PENALTY × jumps`. (Earlier v1.3.x branches used a
score-aligned acceptance that mixed in absorption rate, which under
the rep/dist metric leaves distance on the table.)

The three diversification axes:

1. **Random anchor**: instead of the lowest-level quest pickup, start
   the build from a random feasible stop's coord. The tour grows
   from a different corner of the zone and the cluster sequence is
   structurally different.

2. **Stochastic tiebreaker** (`_stochastic_nearest`): when picking
   the next stop, sample from the `STOCHASTIC_K` nearest feasible
   stops weighted by inverse distance instead of always taking the
   absolute-nearest one. This perturbs intermediate decisions; the
   downstream 2-opt/or-opt then drives each candidate back toward an
   optimum — often a *different* local optimum than the
   deterministic build reaches.

3. **Cluster-radius jitter**: a fraction of iterations builds with a
   wider or narrower `cluster_radius` than the zone default. Smaller
   radii split tight quest hubs that a single radius would lump into
   a single cluster; larger radii merge groups the default would
   split. The downstream refinement picks the better grouping.

After K builds the best feasible candidate goes through an ILS
finisher with two perturbation kernels:

- **Segment reverse** — randomized 2-opt-style reversal of a short
  sub-segment.
- **Double-bridge** — Lin-Kernighan-style 4-edge swap that 2-opt
  cannot reach with a single move.

Each ILS round shakes + re-refines; if the result is cheaper it
becomes the new incumbent. Monotone — never regresses.

Finally the chosen tour goes through `tour.refine_tour` (the deep
chain), which adds 3-opt + Held-Karp + stop-level finishers on top
of whatever multistart found. Per-candidate refinement uses the
faster `tour.refine_tour_fast` so the K-loop stays tractable.

The RNG is seeded deterministically from the quest IDs, so output is
reproducible across runs and quality-report diffs stay meaningful.
"""
from __future__ import annotations

import atexit
import math
import multiprocessing
import os
import random
from typing import Optional

from .cluster import absorb_on_the_way, discover_cluster
from .distance import DIFFERENT_ZONE_PENALTY, dist
from .feasibility import (
    build_predecessor_map, build_stop_list, is_feasible, mark_done,
)
from .two_opt import _tour_cost
from .types import Stop, TourEntry

# Number of randomized rebuilds per sub-guide. The serial v1.5.0
# pipeline used K=64; the parallel evaluation introduces a small
# tie-breaking variance (workers can return same-cost candidates in
# a different order than the serial sweep would produce), so we lift
# K to 96 to absorb that variance. Bulk runtime stays around 2-3
# minutes because the extra candidates run in parallel for free on a
# multi-core host.
MULTISTART_ITERATIONS = 96

# Stable RNG seed offset. Combined with the input quest IDs in
# `_derive_seed` it produces a reproducible per-sub-guide RNG so a
# regenerate against unchanged input gives bit-identical output.
RNG_SEED_BASE = 1337

# When sampling the next stop, consider this many of the closest feasible
# candidates and weight them by inverse distance. K=1 collapses back to
# the deterministic nearest pick. K=3 yields meaningful diversity without
# exploding the search space (most picks still go to the closest stop).
STOCHASTIC_K = 3

# Cluster-radius jitter range applied to a fraction of iterations. 0.6..1.5
# spans both noticeably tighter (split-up tight hubs) and looser (merge
# nearby groups) groupings without ever hitting a degenerate radius.
RADIUS_JITTER_LOW = 0.6
RADIUS_JITTER_HIGH = 1.5

# ILS perturbation: how many shake-and-refine rounds to run on the best
# tour after multistart. Rounds alternate between segment-reverse and
# double-bridge kernels so each move type gets independent budget.
# Six rounds (vs three on the segment-reverse-only variant) gives each
# kernel three tries on the test corpus.
ILS_ROUNDS = 6

# Number of worker processes for parallel candidate evaluation. One per
# logical CPU on the host. The pool is created lazily on first use and
# reused for the whole bulk run, so per-task pickling cost amortises
# over many sub-guides.
_POOL_WORKERS = max(1, os.cpu_count() or 1)
_POOL: Optional[multiprocessing.pool.Pool] = None


def _get_pool() -> multiprocessing.pool.Pool:
    """Lazy-create a process pool the first time multistart needs it.

    Forking happens here, well after every routing module is imported,
    so workers inherit a fully-initialised parent. We register an
    atexit handler so the pool is cleaned up at interpreter shutdown
    instead of leaking processes.
    """
    global _POOL
    if _POOL is None:
        _POOL = multiprocessing.Pool(processes=_POOL_WORKERS)
        atexit.register(_close_pool)
    return _POOL


def _close_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL.join()
        _POOL = None


def route_subguide_multistart(
    quests: list[dict],
    start_pos: Optional[tuple[int, float, float]],
    cluster_radius: float,
    detour_threshold: float,
) -> tuple[list[TourEntry], list[Stop]]:
    # Local imports to avoid a circular dependency through tour.py.
    from .tour import _greedy_build, refine_tour, refine_tour_fast

    predecessors = build_predecessor_map(quests)
    n_iter = MULTISTART_ITERATIONS
    seed = _derive_seed(quests)
    rng = random.Random(seed)

    # Candidate 0: the deterministic greedy baseline, always tried first
    # so multistart cannot regress against it. Each candidate (here and
    # below) uses the *fast* refinement chain (2-opt + or-opt + defrag
    # + Held-Karp); 3-opt is reserved for the chosen winner because
    # K=64 candidates × 3-opt would push runtime past acceptable.
    best_tour, best_orphans = _greedy_build(
        quests, predecessors, start_pos, cluster_radius, detour_threshold,
    )
    if not best_orphans:
        best_tour = refine_tour_fast(best_tour, predecessors, start_pos)
    best_cost = (
        _tour_cost(best_tour, start_pos)
        if not best_orphans else math.inf
    )

    anchor_pool = _anchor_pool(quests)

    # Candidates 1..n_iter-1: diversified rebuilds. The first half jitters
    # the anchor only (preserving the zone's tuned cluster radius);
    # the second half also jitters the radius to escape cluster-shape
    # locality. Both halves use the stochastic tiebreaker.
    #
    # The candidates are independent — each is one
    # (stochastic_greedy_build + refine_tour_fast) cycle on its own
    # input — so we hand them to the worker pool and pick the cheapest
    # result. Sub-seeds are pre-drawn from the parent RNG, so the
    # selection of anchors / radius jitter / sub-seeds is deterministic
    # against the input quest set; only the *parallel ordering* of
    # candidate evaluation differs from a serial run, which is fine
    # because cheapest-cost wins regardless of order.
    half = (n_iter - 1) // 2
    candidate_args = []
    for i in range(n_iter - 1):
        anchor = rng.choice(anchor_pool) if anchor_pool else start_pos
        radius = cluster_radius
        if i >= half:
            radius = cluster_radius * rng.uniform(RADIUS_JITTER_LOW, RADIUS_JITTER_HIGH)
        sub_seed = rng.randint(0, 2 ** 63 - 1)
        candidate_args.append((
            quests, predecessors, start_pos, detour_threshold,
            anchor, radius, sub_seed,
        ))

    if _POOL_WORKERS > 1 and len(candidate_args) > 1:
        pool = _get_pool()
        # `chunksize=8` batches eight tasks per worker round-trip,
        # cutting IPC overhead by 8× without sacrificing load
        # balance — each worker still picks up new chunks dynamically
        # when the previous one finishes.
        results = pool.starmap(_run_candidate, candidate_args, chunksize=8)
    else:
        results = [_run_candidate(*args) for args in candidate_args]

    for cost, tour in results:
        if tour is None:
            continue
        if cost + 1e-6 < best_cost:
            best_tour = tour
            best_cost = cost
            best_orphans = []

    # ILS finisher: perturb the best tour and try to refine to a shorter
    # one. Because we keep the best tour found so far, this can only help.
    if not best_orphans:
        best_tour, best_cost = _ils_finish(
            best_tour, best_cost, predecessors, start_pos, rng,
            refine_tour_fast,
        )

    # Deep refinement on the winner only — this is where 3-opt earns
    # its keep. If the deep chain finds a cheaper tour we adopt it;
    # otherwise the multistart winner stays.
    if not best_orphans:
        deep = refine_tour(best_tour, predecessors, start_pos)
        deep_cost = _tour_cost(deep, start_pos)
        if deep_cost + 1e-6 < best_cost:
            best_tour = deep
            best_cost = deep_cost

    return best_tour, best_orphans


def _run_candidate(
    quests: list[dict],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    detour_threshold: float,
    anchor: Optional[tuple[int, float, float]],
    radius: float,
    sub_seed: int,
) -> tuple[float, Optional[list[TourEntry]]]:
    """Compute one multistart candidate end-to-end.

    Top-level (not a closure) so multiprocessing can pickle the
    reference. Each worker call is a fresh, independent build:
    stochastic-greedy from the given anchor and radius, then the
    fast refinement chain. Returns `(cost, tour)`; `tour is None`
    when a precedence deadlock leaves the build incomplete.

    `refine_tour_fast` is imported lazily here for the same reason
    `route_subguide_multistart` does — `tour.py` lazily imports
    `route_subguide_multistart`, so importing it at module load
    would create a cycle.
    """
    from .tour import refine_tour_fast
    rng = random.Random(sub_seed)
    tour, orphans = _stochastic_greedy_build(
        quests, predecessors, anchor, radius, detour_threshold, rng,
    )
    if orphans:
        return (math.inf, None)
    tour = refine_tour_fast(tour, predecessors, start_pos)
    return (_tour_cost(tour, start_pos), tour)


def _ils_finish(
    tour: list[TourEntry],
    cost: float,
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    rng: random.Random,
    refine_tour,
) -> tuple[list[TourEntry], float]:
    """Iterated Local Search tail with mixed perturbation kernels.

    Each round picks one of two perturbation moves at random:

    1. **Segment reversal** — reverse `tour[i:j+1]`. A 2-opt-style move
       that re-targets a single sub-sequence. Cheap and almost always
       feasible; useful for fine-grained escape.
    2. **Double-bridge** — cut the tour at three random points
       (i < j < k) and reorder the four segments as `[A, C, B, D]`.
       This is a 4-edge swap that 2-opt cannot reach with a single
       move. Classical Lin-Kernighan-style escape for routes that
       2-opt + or-opt have driven into a deep local optimum.

    The shaken tour is re-refined; if its cost drops it becomes the
    new incumbent. ILS lets us escape local optima 2-opt and or-opt
    are stuck in without sacrificing the monotone "best so far"
    guarantee — if no perturbation produces a cheaper refined tour,
    the input is returned unchanged.

    `ILS_ROUNDS` doubled (3 -> 6) to give each move type an
    independent budget. Each round is one perturbation + one
    refinement; round-trip cost is the same as before per round.
    """
    n = len(tour)
    if n < 4:
        return tour, cost

    best = tour
    best_cost = cost
    for r in range(ILS_ROUNDS):
        # Alternate the two perturbation kernels round-by-round so
        # both are tried at least once and an unlucky RNG split
        # cannot starve either of them.
        if r % 2 == 0 or n < 8:
            shaken = _segment_reverse(best, rng)
        else:
            shaken = _double_bridge(best, rng)
        if shaken is None or not _is_valid_tour(shaken, predecessors):
            continue
        shaken = refine_tour(shaken, predecessors, start_pos)
        c = _tour_cost(shaken, start_pos)
        if c + 1e-6 < best_cost:
            best = shaken
            best_cost = c
    return best, best_cost


def _segment_reverse(
    tour: list[TourEntry], rng: random.Random,
) -> list[TourEntry]:
    """Reverse a random sub-segment of length up to `n // 4 + 2`.
    Same move shape as 2-opt; randomized."""
    n = len(tour)
    i = rng.randrange(n - 1)
    j = rng.randrange(i + 1, min(n, i + 1 + max(2, n // 4)))
    return tour[:i] + list(reversed(tour[i:j + 1])) + tour[j + 1:]


def _double_bridge(
    tour: list[TourEntry], rng: random.Random,
) -> Optional[list[TourEntry]]:
    """Lin-Kernighan-style double-bridge: cut at three points and
    reorder the four resulting segments as `[A, C, B, D]`. Returns
    None when the tour is too short to split into four non-empty
    segments — the caller then falls back to a segment-reverse.
    """
    n = len(tour)
    if n < 8:
        return None
    # Three cuts producing four non-empty segments. Each segment is at
    # least one entry; the available range for each cut shrinks
    # accordingly.
    i = rng.randint(1, n - 5)
    j = rng.randint(i + 1, n - 3)
    k = rng.randint(j + 1, n - 1)
    return tour[:i] + tour[j:k] + tour[i:j] + tour[k:]


def _stochastic_greedy_build(
    quests: list[dict],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    cluster_radius: float,
    detour_threshold: float,
    rng: random.Random,
) -> tuple[list[TourEntry], list[Stop]]:
    """Like `_greedy_build` but `nearest_feasible` is replaced with a
    stochastic K-nearest sampler. Cluster discovery and on-the-way
    absorption stay deterministic — they cap detours to small radii, so
    randomizing them rarely changes which stops they pick anyway, while
    making clusters non-reproducible would just add noise to the diff.
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

        next_stop = _stochastic_nearest(
            stops, completed, predecessors, cur_pos, rng,
        )
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


def _stochastic_nearest(
    stops: list[Stop],
    completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
    cur_pos: Optional[tuple[int, float, float]],
    rng: random.Random,
) -> Optional[Stop]:
    """Sample one of the STOCHASTIC_K closest feasible stops, weighted by
    inverse distance. Cross-zone candidates carry the synthetic penalty
    (1e6) — they remain pickable only if every in-zone candidate is also
    cross-zone, exactly like the deterministic version.
    """
    feasible = [s for s in stops if is_feasible(s, completed, predecessors)]
    if not feasible:
        return None
    if cur_pos is None:
        # No anchor — fall back to deterministic head pick. With K
        # candidates this would otherwise sample arbitrarily across a
        # zero-distance ring.
        return feasible[0]

    feasible.sort(key=lambda s: dist(cur_pos, s.coord))
    candidates = feasible[:STOCHASTIC_K]

    # Inverse-distance weights with a small floor so a stop sitting on
    # top of cur_pos (dist = 0) does not collapse the distribution.
    weights: list[float] = []
    for s in candidates:
        d = dist(cur_pos, s.coord)
        if d >= DIFFERENT_ZONE_PENALTY:
            weights.append(1e-12)  # cross-zone — nearly never chosen
        else:
            weights.append(1.0 / (d + 1.0))

    return rng.choices(candidates, weights=weights, k=1)[0]


def _anchor_pool(quests: list[dict]) -> list[tuple[int, float, float]]:
    """All distinct pickup/turnin coords across the input. Anchoring on
    one of these makes every candidate start somewhere a player would
    actually be — random points in zone space lead to nonsensical
    initial cluster discovery on the edges of the map.
    """
    seen: set[tuple[int, float, float]] = set()
    pool: list[tuple[int, float, float]] = []
    for q in quests:
        for key in ('pickup_coords', 'turnin_coords'):
            c = q.get(key)
            if c and c not in seen:
                seen.add(c)
                pool.append(c)
    return pool


def _is_valid_tour(
    tour: list[TourEntry], predecessors: dict[int, set[int]],
) -> bool:
    """Re-check precedence on a perturbed tour. Same logic as the 2-opt
    validator — duplicated locally to avoid a cross-module import that
    would entangle tour.py and multistart.py."""
    completed: dict[int, set[str]] = {}
    for entry in tour:
        for s in entry.stops:
            if not is_feasible(s, completed, predecessors):
                return False
            completed.setdefault(s.quest_id, set()).add(s.type)
    return True


def _derive_seed(quests: list[dict]) -> int:
    """Stable seed from the input quest set: same input, same output, so
    the quality-report diff for an unchanged sub-guide stays empty."""
    h = RNG_SEED_BASE
    for q in quests:
        h = (h * 1099511628211) ^ q['id']
        h &= 0xFFFFFFFFFFFFFFFF
    return h
