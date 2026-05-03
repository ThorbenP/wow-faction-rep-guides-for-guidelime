"""Held-Karp DP for small sub-guides — provably-optimal ordering.

Two variants:

- `held_karp_pass` (entry-level): the classical Held-Karp DP over
  TourEntries (clusters atomic). Capped at `MAX_ENTRIES = 12` because
  the dense `list[list]` table is `O(N · 2^N)` and that is the practical
  ceiling in pure Python.

- `held_karp_stop_level_pass` (stop-level): expands the same DP to the
  flattened stop sequence using a sparse dict over reachable states.
  Precedence pruning means the reachable-state count is far smaller
  than 2^N in practice, so this scales to ~30 stops in well under a
  second. After the DP it re-clusters consecutive same-coord stops
  into TourEntries, identical to what `_recluster` in the stop-level
  finishers does, so downstream passes see the usual structure.

Both variants are monotone: if the DP cannot find anything cheaper
than the input cost they return the tour unchanged.
"""
from __future__ import annotations

import math
from typing import Optional

from .two_opt import JUMP_PENALTY, _tour_cost
from .types import Stop, TourEntry

# Beyond 12 entries Python's pure-Python state explosion makes the DP
# slower than the 2-opt / or-opt converged tour we already have. The
# break-even moves up to ~16 with PyPy or a C accelerator; not worth
# chasing here.
MAX_ENTRIES = 12

# Stop-level DP scales further because the reachable-state set under
# precedence is a tiny fraction of 2^N. 30 stops finish in well under a
# second in practice. Above 30, runtime starts to dominate the rest of
# the refine chain.
MAX_STOPS = 30


def held_karp_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """Replace `tour` with the provably-optimal entry permutation
    *only* for short tours (≤ `MAX_ENTRIES`). Larger tours are
    returned unchanged so the caller's refinement chain is preserved.
    """
    n = len(tour)
    if n < 3 or n > MAX_ENTRIES:
        return tour

    entry_predecessors = _entry_predecessor_masks(tour, predecessors)
    edge = _edge_matrix(tour, start_pos)

    # dp[mask][last] = (cost, prev_last)
    # `mask` is the set of visited entries, `last` is the entry we
    # arrived at last. `prev_last` is needed for path reconstruction.
    INF = math.inf
    dp: list[list[tuple[float, int]]] = [
        [(INF, -1)] * n for _ in range(1 << n)
    ]

    # Base cases: single-entry tours starting from `start_pos`. Only
    # entries with no predecessors in the input set may go first.
    for i in range(n):
        if entry_predecessors[i] == 0:
            dp[1 << i][i] = (edge[-1][i], -1)

    # Forward pass over masks in ascending popcount. `bin(mask).count('1')`
    # is fine here — n ≤ 12 means at most 4096 masks.
    for mask in range(1, 1 << n):
        for last in range(n):
            if not (mask & (1 << last)):
                continue
            cost_last, _ = dp[mask][last]
            if cost_last == INF:
                continue
            # Try extending with every unvisited entry whose precedence
            # is satisfied by the current mask.
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                if (entry_predecessors[nxt] & ~mask) != 0:
                    continue
                new_mask = mask | (1 << nxt)
                new_cost = cost_last + edge[last][nxt]
                if new_cost + 1e-9 < dp[new_mask][nxt][0]:
                    dp[new_mask][nxt] = (new_cost, last)

    # Best terminal state is the cheapest dp[full][k]. Path TSPs end
    # anywhere — we are not closing the loop.
    full = (1 << n) - 1
    best_cost = INF
    best_last = -1
    for last in range(n):
        c, _ = dp[full][last]
        if c < best_cost:
            best_cost = c
            best_last = last

    if best_last < 0 or best_cost >= _tour_cost(tour, start_pos):
        # Either the DP found no feasible ordering (unreachable
        # configuration) or it could not beat the input — return the
        # tour as-is.
        return tour

    # Reconstruct the optimal entry order by walking `prev_last` links.
    order: list[int] = []
    mask = full
    cur = best_last
    while cur >= 0:
        order.append(cur)
        _, prev = dp[mask][cur]
        mask ^= 1 << cur
        cur = prev
    order.reverse()
    return [tour[i] for i in order]


def _entry_predecessor_masks(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
) -> list[int]:
    """For each entry index, a bitmask of entry indices that must come
    before it. Computed by mapping every (quest_id, stop_type) to the
    entry that contains it; an entry's predecessors are the entries
    holding the stop-level predecessors of any of its stops, plus the
    intra-quest precedence (QA -> QC -> QT).
    """
    n = len(tour)
    quest_stops_to_entry: dict[tuple[int, str], int] = {}
    for i, e in enumerate(tour):
        for s in e.stops:
            quest_stops_to_entry[(s.quest_id, s.type)] = i

    masks = [0] * n
    for i, e in enumerate(tour):
        bits = 0
        for s in e.stops:
            qid = s.quest_id
            # Cross-quest precedence: every predecessor quest's QT
            # must be visited (i.e. in an earlier entry).
            if s.type == 'QA':
                for pid in predecessors.get(qid, ()):
                    key = (pid, 'QT')
                    if key in quest_stops_to_entry:
                        idx = quest_stops_to_entry[key]
                        if idx != i:
                            bits |= 1 << idx
            # Intra-quest precedence: QC waits on QA, QT waits on
            # QC (or QA if QC has no coords).
            if s.type == 'QC':
                key = (qid, 'QA')
                if key in quest_stops_to_entry:
                    idx = quest_stops_to_entry[key]
                    if idx != i:
                        bits |= 1 << idx
            if s.type == 'QT':
                for predtype in ('QC', 'QA'):
                    key = (qid, predtype)
                    if key in quest_stops_to_entry:
                        idx = quest_stops_to_entry[key]
                        if idx != i:
                            bits |= 1 << idx
        masks[i] = bits
    return masks


def _edge_matrix(
    tour: list[TourEntry],
    start_pos: Optional[tuple[int, float, float]],
) -> list[list[float]]:
    """`edge[i][j]` is the cost of flying from the *last* stop of
    entry `i` to the *first* stop of entry `j`, plus the entry's own
    intra-cluster cost amortised on entry into it.

    `edge[-1][j]` is the boundary edge from `start_pos` to entry `j`.
    Cross-zone hops use `JUMP_PENALTY` (consistent with `_tour_cost`).

    The intra-cluster edges are folded into the *entering* edge so the
    DP works on a linear cost — same trick the entry-level 2-opt uses.
    """
    from .two_opt import JUMP_PENALTY
    n = len(tour)
    edge = [[0.0] * n for _ in range(n + 1)]  # last row = start_pos

    # Per-entry intra-cluster cost: sum of consecutive stop-to-stop
    # edges inside the entry. Same metric as the standard cost.
    intra = [0.0] * n
    for i, e in enumerate(tour):
        for k in range(1, len(e.stops)):
            a = e.stops[k - 1].coord
            b = e.stops[k].coord
            if a[0] != b[0]:
                intra[i] += JUMP_PENALTY
            else:
                intra[i] += math.hypot(a[1] - b[1], a[2] - b[2])

    def boundary(a, b: tuple[int, float, float]) -> float:
        if a is None:
            return 0.0
        if a[0] != b[0]:
            return JUMP_PENALTY
        return math.hypot(a[1] - b[1], a[2] - b[2])

    for j in range(n):
        first = tour[j].stops[0].coord
        edge[-1][j] = boundary(start_pos, first) + intra[j]
        for i in range(n):
            if i == j:
                continue
            last = tour[i].stops[-1].coord
            edge[i][j] = boundary(last, first) + intra[j]

    return edge


# ---------------------------------------------------------------------------
# Stop-level Held-Karp — sparse dict DP over reachable states.
#
# Where the entry-level pass treats clusters as atomic, this pass dissolves
# them and finds the provably-optimal stop ordering. Precedence pruning is
# essential: without it 2^N would not fit in memory at N = 30; with it the
# reachable-state set is typically a few thousand to a few hundred thousand
# even at the cap.
# ---------------------------------------------------------------------------


def held_karp_stop_level_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
    max_stops: int = MAX_STOPS,
) -> list[TourEntry]:
    """Replace `tour` with the provably-optimal stop ordering for tours
    of up to `max_stops` flattened stops. Larger tours are returned
    unchanged so the rest of the refinement chain stays untouched.

    Cost model is identical to `_tour_cost`: zone-aware euclidean within
    a zone, `JUMP_PENALTY` per cross-zone edge.
    """
    flat = [s for entry in tour for s in entry.stops]
    n = len(flat)
    if n < 3 or n > max_stops:
        return tour

    pred_masks = _stop_predecessor_masks(flat, predecessors)
    dmat = _stop_distance_matrix(flat)
    from_start = _stop_distances_from_start(flat, start_pos)
    full_mask = (1 << n) - 1

    # Forward expansion via dict; only reachable states (mask closed under
    # predecessors) ever appear. `states_by_count[k]` holds the masks at
    # popcount k, processed in order so each transition extends a finalised
    # state to a level-k+1 state.
    dp: dict[tuple[int, int], tuple[float, int]] = {}
    states_by_count: list[list[tuple[int, int]]] = [[] for _ in range(n + 1)]

    for i in range(n):
        if pred_masks[i] == 0:
            dp[(1 << i, i)] = (from_start[i], -1)
            states_by_count[1].append((1 << i, i))

    for level in range(1, n):
        for mask, last in states_by_count[level]:
            cost, _ = dp[(mask, last)]
            remaining = full_mask & ~mask
            u = remaining
            while u:
                low = u & -u
                idx = low.bit_length() - 1
                if (pred_masks[idx] & mask) == pred_masks[idx]:
                    new_mask = mask | low
                    new_cost = cost + dmat[last][idx]
                    key = (new_mask, idx)
                    prev = dp.get(key)
                    if prev is None or new_cost < prev[0]:
                        dp[key] = (new_cost, last)
                        if prev is None:
                            states_by_count[level + 1].append((new_mask, idx))
                u ^= low

    best_last = -1
    best_cost = math.inf
    for last in range(n):
        s = dp.get((full_mask, last))
        if s is not None and s[0] < best_cost:
            best_cost = s[0]
            best_last = last

    if best_last < 0:
        # No feasible full ordering reachable — should not happen if the
        # input tour is itself feasible. Fall back to the input.
        return tour

    current_cost = _tour_cost(tour, start_pos)
    if best_cost + 1e-9 >= current_cost:
        return tour  # input is already optimal — leave it alone

    # Reconstruct the optimal stop ordering by walking parents.
    seq_rev: list[int] = []
    cur_mask = full_mask
    cur_last = best_last
    while cur_last >= 0:
        seq_rev.append(cur_last)
        _, parent = dp[(cur_mask, cur_last)]
        cur_mask ^= 1 << cur_last
        cur_last = parent
    sequence = list(reversed(seq_rev))

    return _recluster_stops([flat[i] for i in sequence])


def _stop_predecessor_masks(
    stops: list[Stop], predecessors: dict[int, set[int]],
) -> list[int]:
    """Per stop, the bitmask of stop-indices that must come before it.

    Translates `predecessors` (per quest_id, post-`build_predecessor_map`)
    plus the intra-quest QA → QC → QT chain into one bitmask per stop.
    Item-drop bridge quests have no QA stop — their dependents pick up
    the predecessor's QT through the QT chain (a QT stop only depends on
    the same quest's QA / QC, never on another quest's QT).
    """
    n = len(stops)
    qa_idx_for: dict[int, int] = {}
    qc_idx_for: dict[int, int] = {}
    qt_idx_for: dict[int, int] = {}
    for i, s in enumerate(stops):
        if s.type == 'QA':
            qa_idx_for[s.quest_id] = i
        elif s.type == 'QC':
            qc_idx_for[s.quest_id] = i
        elif s.type == 'QT':
            qt_idx_for[s.quest_id] = i

    masks: list[int] = [0] * n
    for i, s in enumerate(stops):
        qid = s.quest_id
        if s.type == 'QA':
            for pid in predecessors.get(qid, ()):
                qt = qt_idx_for.get(pid)
                if qt is not None:
                    masks[i] |= 1 << qt
        elif s.type == 'QC':
            qa = qa_idx_for.get(qid)
            if qa is not None:
                masks[i] |= 1 << qa
        elif s.type == 'QT':
            qa = qa_idx_for.get(qid)
            if qa is not None:
                masks[i] |= 1 << qa
            qc = qc_idx_for.get(qid)
            if qc is not None:
                masks[i] |= 1 << qc
    return masks


def _stop_distance_matrix(stops: list[Stop]) -> list[list[float]]:
    """Pairwise stop-to-stop cost. Same metric as `_tour_cost`: euclidean
    within a zone, `JUMP_PENALTY` across zones."""
    n = len(stops)
    coords = [s.coord for s in stops]
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        zi, xi, yi = coords[i]
        for j in range(n):
            if i == j:
                continue
            zj, xj, yj = coords[j]
            if zi != zj:
                mat[i][j] = JUMP_PENALTY
            else:
                mat[i][j] = math.hypot(xi - xj, yi - yj)
    return mat


def _stop_distances_from_start(
    stops: list[Stop], start_pos: Optional[tuple[int, float, float]],
) -> list[float]:
    """Cost from `start_pos` to each stop, with the same metric."""
    if start_pos is None:
        return [0.0] * len(stops)
    sz, sx, sy = start_pos
    out: list[float] = []
    for s in stops:
        zi, xi, yi = s.coord
        if zi != sz:
            out.append(JUMP_PENALTY)
        else:
            out.append(math.hypot(sx - xi, sy - yi))
    return out


def _recluster_stops(stops: list[Stop]) -> list[TourEntry]:
    """Group consecutive same-coord stops into cluster TourEntries.

    Mirrors `stop_2opt._recluster` so the output structure matches what
    the rest of the refinement chain produces. Kept inline rather than
    imported to avoid a circular dependency.
    """
    out: list[TourEntry] = []
    for s in stops:
        if out and out[-1].stops[-1].coord == s.coord:
            out[-1] = TourEntry(kind='cluster', stops=out[-1].stops + [s])
        else:
            out.append(TourEntry(kind='travel', stops=[s]))
    return out
