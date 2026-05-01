"""Greedy-nearest-feasible tour routing for sub-guides, with 2-opt refinement.

A sub-guide is a set of Stops (QA, QC, QT for each quest). The tour builder
emits an ordered sequence of Cluster entries (multiple stops at the same
location) and Travel entries (single stops reached by travel). On every
travel leg, additional stops are absorbed if they sit on the way with a
small detour. Finally a 2-opt post-pass reorders entries when that shortens
the total tour cost without violating precedence.

Stop-level precedence rules (enforced by `is_feasible`):
  - QA: pickup; predecessors must have their QT done
  - QC: objective; the quest's QA must be done (or the quest has no pickup)
  - QT: turnin; QA and QC must be done if applicable
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# Default cluster radius — overridable per zone via
# `constants.ZONE_CLUSTER_RADIUS`. Sparse zones (e.g. Tanaris) need a wider
# radius than dense city hubs (Stormwind), see ZONE_CLUSTER_RADIUS comments.
CLUSTER_RADIUS = 12.0

# Maximum acceptable detour for "on-the-way" absorption: a stop is picked up
# during travel only if the extra distance via that stop is below this value.
DETOUR_THRESHOLD = 6.0

# Synthetic distance used when two stops are in different zones. Effectively
# means "infinity" so the routing never picks a cross-zone neighbour as the
# nearest stop and never tries to absorb across zone boundaries.
DIFFERENT_ZONE_PENALTY = 1e6


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


def build_stop_list(quests: list[dict]) -> list[Stop]:
    """Build 1-3 stops per quest (QA, QC, QT), each only if coords exist."""
    stops: list[Stop] = []
    for q in quests:
        if q.get('pickup_coords'):
            stops.append(Stop('QA', q, q['pickup_coords']))
        if q.get('objective_coords'):
            stops.append(Stop('QC', q, q['objective_coords']))
        if q.get('turnin_coords'):
            stops.append(Stop('QT', q, q['turnin_coords']))
    return stops


def build_predecessor_map(quests: list[dict]) -> dict[int, set[int]]:
    """For each quest, the set of quest IDs whose QT must be done before
    this quest's QA is feasible.

    Sources:
      - q.pre / q.preg: quest references its prerequisites directly.
      - other.next == q.id: another quest declares q as its successor — that
        other quest is therefore a prerequisite of q.

    Predecessors outside the input list are ignored (they cannot block).
    """
    quest_ids = {q['id'] for q in quests}
    predecessors: dict[int, set[int]] = {qid: set() for qid in quest_ids}

    for q in quests:
        qid = q['id']
        for pid in (q.get('pre') or []) + (q.get('preg') or []):
            if pid in quest_ids:
                predecessors[qid].add(pid)
        nxt = q.get('next')
        if nxt and nxt in quest_ids and nxt != qid:
            predecessors[nxt].add(qid)
    return predecessors


def is_feasible(
    stop: Stop, completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
) -> bool:
    """True if all precedence constraints for `stop` are satisfied.

    Quests without `pickup_coords` (item-drop bridges, auto-starting quests)
    have no QA stop — their QA is treated as implicitly done once the
    triggering item is in the inventory. QC/QT for such quests therefore do
    not wait for a QA stop.
    """
    qid = stop.quest_id
    done_for_quest = completed.get(qid, set())
    has_pickup = bool(stop.quest.get('pickup_coords'))

    if stop.type == 'QA':
        for pid in predecessors.get(qid, ()):
            if 'QT' not in completed.get(pid, set()):
                return False
        return True

    if stop.type == 'QC':
        return 'QA' in done_for_quest or not has_pickup

    if stop.type == 'QT':
        if has_pickup and 'QA' not in done_for_quest:
            return False
        if stop.quest.get('objective_coords'):
            return 'QC' in done_for_quest
        return True

    return False


def _dist(a: Optional[tuple[int, float, float]],
          b: tuple[int, float, float]) -> float:
    """Euclidean distance within a zone; cross-zone returns the penalty."""
    if a is None:
        return 0.0
    if a[0] != b[0]:
        return DIFFERENT_ZONE_PENALTY
    return math.hypot(a[1] - b[1], a[2] - b[2])


def route_subguide(
    quests: list[dict],
    start_pos: Optional[tuple[int, float, float]] = None,
    cluster_radius: float = CLUSTER_RADIUS,
    detour_threshold: float = DETOUR_THRESHOLD,
) -> tuple[list[TourEntry], list[Stop]]:
    """Build a tour from the given quests, then refine it with 2-opt.

    Returns (tour, orphans) where `orphans` is non-empty only if the
    precedence chain is broken and some stops are unreachable (deadlock
    fallback — output emits them under a "Not reachable" banner).
    """
    stops = build_stop_list(quests)
    predecessors = build_predecessor_map(quests)
    completed: dict[int, set[str]] = {}
    cur_pos = start_pos
    tour: list[TourEntry] = []

    while stops:
        # Step 1: cluster discovery around cur_pos. Marks completed in-place.
        cluster_stops = _discover_cluster(
            stops, completed, predecessors, cur_pos, cluster_radius,
        )
        if cluster_stops:
            cur_pos = cluster_stops[-1].coord
            tour.append(TourEntry(kind='cluster', stops=cluster_stops))

        if not stops:
            break

        # Step 2: pick the next reachable stop further away.
        next_stop = _nearest_feasible(stops, completed, predecessors, cur_pos)
        if next_stop is None:
            return tour, list(stops)

        # Step 3: on the way to next_stop, absorb stops with a small detour.
        stops.remove(next_stop)
        absorbed = _absorb_on_the_way(
            stops, completed, predecessors, cur_pos, next_stop.coord,
            detour_threshold, cluster_radius,
        )
        for s in absorbed:
            cur_pos = s.coord
            tour.append(TourEntry(kind='travel', stops=[s]))

        _mark_done(completed, next_stop)
        cur_pos = next_stop.coord
        tour.append(TourEntry(kind='travel', stops=[next_stop]))

    tour = _two_opt_pass(tour, predecessors, start_pos)
    return tour, []


def _two_opt_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """Classical 2-opt refinement on the tour.

    Tries to reverse every (i, j)-segment of the tour. A swap is accepted if
    the total cost drops AND every stop's precedence constraints still hold
    in the new ordering. Iterates until no swap improves the cost.

    Operates on TourEntries as atomic units (clusters are not broken up):
    breaking up clusters destroys their visual grouping, and the gain on
    intra-cluster ordering is negligible compared to the inter-entry swaps.
    """
    # Cross-zone jumps are penalised so 2-opt does not "shorten" the
    # intra-zone distance by re-routing through extra zone changes — in WoW,
    # every jump is a flightpath/portal hop that costs real travel time.
    # JP=45 was empirically calibrated: at 30 jumps still increase by ~7%,
    # at 60 the distance gain shrinks visibly. 45 yields both -4% distance
    # and -3% jumps versus the un-refined tour.
    JUMP_PENALTY = 45.0

    def tour_cost(t: list[TourEntry]) -> float:
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

    def is_valid(t: list[TourEntry]) -> bool:
        completed: dict[int, set[str]] = {}
        for entry in t:
            for s in entry.stops:
                if not is_feasible(s, completed, predecessors):
                    return False
                completed.setdefault(s.quest_id, set()).add(s.type)
        return True

    n = len(tour)
    if n < 3:
        return tour
    best = list(tour)
    best_d = tour_cost(best)
    max_passes = 3
    for _ in range(max_passes):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                # Reverse the segment between i and j (the textbook 2-opt move).
                cand = best[:i] + list(reversed(best[i:j + 1])) + best[j + 1:]
                if not is_valid(cand):
                    continue
                d = tour_cost(cand)
                if d + 0.001 < best_d:
                    best = cand
                    best_d = d
                    improved = True
        if not improved:
            break
    return best


def _mark_done(completed: dict[int, set[str]], stop: Stop) -> None:
    completed.setdefault(stop.quest_id, set()).add(stop.type)


def _discover_cluster(
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
            and _dist(pos, s.coord) <= cluster_radius
        ]
        if not candidates:
            break
        if pos is None:
            nearest = candidates[0]
        else:
            nearest = min(candidates, key=lambda s: _dist(pos, s.coord))
        stops.remove(nearest)
        cluster.append(nearest)
        pos = nearest.coord
        # Marking the just-picked stop as done can unlock further stops in
        # the next iteration (e.g. a QA enables the same quest's QC).
        completed.setdefault(nearest.quest_id, set()).add(nearest.type)

    return cluster


def _nearest_feasible(
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
    return min(feasible, key=lambda s: _dist(cur_pos, s.coord))


def compute_tour_stats(
    tour: list[TourEntry],
    start_pos: Optional[tuple[int, float, float]] = None,
) -> dict:
    """Aggregate pathing metrics for a tour. Used by the quality report.

    Returned dict:
      - intra_zone_distance: sum of euclidean distances within the same zone.
        Cross-zone hops do NOT contribute since they are flightpath/portal
        travel, not running distance.
      - cross_zone_jumps: number of zone changes along the tour.
      - cluster_count / cluster_sizes / avg_cluster_size / max_cluster_size
      - travel_count: number of single-stop travel entries.
      - total_stops, clustered_stops (members of clusters with size >= 2).
      - absorption_rate: clustered_stops / total_stops, higher is better.
    """
    total_dist = 0.0
    cross_zone_jumps = 0
    cluster_sizes: list[int] = []
    travel_count = 0
    cur_pos = start_pos

    for entry in tour:
        if entry.kind == 'cluster':
            cluster_sizes.append(len(entry.stops))
            for stop in entry.stops:
                if cur_pos is not None:
                    if cur_pos[0] != stop.coord[0]:
                        cross_zone_jumps += 1
                    else:
                        total_dist += math.hypot(
                            cur_pos[1] - stop.coord[1],
                            cur_pos[2] - stop.coord[2],
                        )
                cur_pos = stop.coord
        else:  # travel
            travel_count += 1
            stop = entry.stops[0]
            if cur_pos is not None:
                if cur_pos[0] != stop.coord[0]:
                    cross_zone_jumps += 1
                else:
                    total_dist += math.hypot(
                        cur_pos[1] - stop.coord[1],
                        cur_pos[2] - stop.coord[2],
                    )
            cur_pos = stop.coord

    total_stops = sum(cluster_sizes) + travel_count
    clustered_stops = sum(s for s in cluster_sizes if s > 1)
    return {
        'intra_zone_distance': round(total_dist, 1),
        'cross_zone_jumps': cross_zone_jumps,
        'cluster_count': len(cluster_sizes),
        'cluster_sizes': cluster_sizes,
        'avg_cluster_size': round(sum(cluster_sizes) / len(cluster_sizes), 2) if cluster_sizes else 0.0,
        'max_cluster_size': max(cluster_sizes) if cluster_sizes else 0,
        'travel_count': travel_count,
        'total_stops': total_stops,
        'clustered_stops': clustered_stops,
        'absorption_rate': round(clustered_stops / total_stops, 3) if total_stops else 0.0,
    }


def _absorb_on_the_way(
    stops: list[Stop],
    completed: dict[int, set[str]],
    predecessors: dict[int, set[int]],
    cur_pos: tuple[int, float, float],
    target_pos: tuple[int, float, float],
    detour_threshold: float,
    cluster_radius: float = CLUSTER_RADIUS,
) -> list[Stop]:
    """Greedy: while a feasible stop adds only a small detour to the trip
    cur -> s -> target, absorb it.

    Stops that already sit close to `target_pos` (within cluster_radius) are
    NOT absorbed here — the next cluster-discovery around target_pos will
    pick them up, which keeps them grouped instead of scattered as
    individual travel entries near the same location.
    """
    if _dist(cur_pos, target_pos) >= DIFFERENT_ZONE_PENALTY:
        return []

    absorbed: list[Stop] = []
    pos = cur_pos

    while True:
        feasible = [s for s in stops if is_feasible(s, completed, predecessors)]
        best: Optional[Stop] = None
        best_detour = detour_threshold

        direct = _dist(pos, target_pos)
        if direct >= DIFFERENT_ZONE_PENALTY:
            break
        for s in feasible:
            if _dist(s.coord, target_pos) <= cluster_radius:
                continue
            via = _dist(pos, s.coord) + _dist(s.coord, target_pos)
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
