"""Held-Karp DP for small sub-guides — provably-optimal entry ordering.

The classical Held-Karp dynamic program solves TSP exactly by sweeping
all `(visited_mask, last_entry)` states. Cost is O(N² · 2^N), which
caps the practical size at around 14-18 entries in pure Python before
runtime explodes. Set `MAX_ENTRIES` to cap input — anything larger
falls back to whatever tour the caller passed in.

Where greedy + 2-opt + or-opt find a *local* optimum, Held-Karp finds
the *global* optimum at the entry level. Clusters are not broken
(treated as atomic units, like the entry-level 2-opt / or-opt do),
but the order in which entries are visited is provably the cheapest
precedence-respecting permutation.

Precedence constraints are enforced by computing an entry-precedence
DAG: entry A must precede entry B if any stop in B has a stop-level
predecessor in A. The DP transition then only visits states where
the proposed `last` has all its predecessor entries already in the
mask.

The result is monotone: if the DP cannot find anything cheaper than
the input cost (e.g. greedy already hit the same global optimum),
the original tour is returned unchanged.
"""
from __future__ import annotations

import math
from typing import Optional

from .two_opt import _tour_cost
from .types import TourEntry

# Beyond 12 entries Python's pure-Python state explosion makes the DP
# slower than the 2-opt / or-opt converged tour we already have. The
# break-even moves up to ~16 with PyPy or a C accelerator; not worth
# chasing here.
MAX_ENTRIES = 12


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
