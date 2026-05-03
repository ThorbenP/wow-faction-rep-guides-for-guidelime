"""Held-Karp DP for the optimum-pathing problem.

Brute-force enumerates O(N!) sequences. Held-Karp does the same problem in
O(N²·2^N) by memoising on the state (visited_bitmask, last_stop). Crucially,
because rep is constant across full feasible permutations, the problem
collapses to "minimum-distance Hamiltonian path under precedence" — a
sequential-ordering problem (SOP), exactly what Held-Karp solves.

Precedence pruning: only states whose visited bitmask is a closure under
predecessors are reachable. That cuts the state space by 1–2 orders of
magnitude versus naive 2^N. We grow the reachable-state set on the fly via
forward expansion, which means memory follows the actual reachable
states, not the worst-case bound.

Cross-zone hops cost 0 (matching the existing routing/distance.py model
and `compute_tour_stats`), so a stop in a foreign zone contributes only
its own incoming/outgoing zero-cost transitions.
"""
from __future__ import annotations

import math
import time

from .dataset import (
    SubGuide, build_distance_matrix, build_stop_predecessor_masks,
    distances_from_start,
)


def solve_heldkarp(sg: SubGuide) -> dict:
    """Return the optimum sequence for `sg` and the resulting metrics.

    The dict shape is compatible with the cli result formatter:
      {
        'sequence': [stop_idx, ...],
        'rep': int, 'distance': float, 'rep_per_dist': float | None,
        'states_visited': int, 'elapsed_sec': float, 'method': 'heldkarp',
      }
    """
    n = len(sg.stops)
    started = time.monotonic()
    if n == 0:
        return {
            'sequence': [], 'rep': 0, 'distance': 0.0, 'rep_per_dist': None,
            'states_visited': 0, 'elapsed_sec': 0.0, 'method': 'heldkarp',
        }

    dmat = build_distance_matrix(sg)
    pred_mask = build_stop_predecessor_masks(sg)
    from_start = distances_from_start(sg)
    full_mask = (1 << n) - 1

    # dp: dict[(mask, last_idx) -> (cost, parent_last_idx)]
    # Forward expansion: only enqueue states whose mask is closed under
    # predecessors AND whose last_idx is in the mask.
    dp: dict[tuple[int, int], tuple[float, int]] = {}

    # Seeds: start with each stop that has no precedence predecessors.
    for i in range(n):
        if pred_mask[i] == 0:
            dp[(1 << i, i)] = (from_start[i], -1)

    # BFS by mask popcount so each state is finalised in order.
    # Group states by popcount(mask) to control iteration order.
    states_by_count: list[list[tuple[int, int]]] = [[] for _ in range(n + 1)]
    for (mask, last), _ in dp.items():
        states_by_count[bin(mask).count('1')].append((mask, last))

    states_visited = 0
    for level in range(1, n):  # we expand from levels 1..n-1
        layer = states_by_count[level]
        if not layer:
            continue
        for mask, last in layer:
            cost, _ = dp[(mask, last)]
            states_visited += 1
            # Try to extend with any stop u not in mask whose predecessors
            # are all in mask.
            remaining = full_mask & ~mask
            u = remaining
            while u:
                # iterate set bits of `remaining`
                low = u & -u
                idx = low.bit_length() - 1
                if (pred_mask[idx] & mask) == pred_mask[idx]:
                    new_mask = mask | low
                    new_cost = cost + dmat[last][idx]
                    key = (new_mask, idx)
                    prev = dp.get(key)
                    if prev is None or new_cost < prev[0]:
                        dp[key] = (new_cost, last)
                        if prev is None:
                            states_by_count[level + 1].append((new_mask, idx))
                u ^= low

    # Best terminal state: minimum cost over (full_mask, last) for any last.
    best_last = -1
    best_cost = math.inf
    for last in range(n):
        s = dp.get((full_mask, last))
        if s is not None and s[0] < best_cost:
            best_cost = s[0]
            best_last = last

    if best_last < 0:
        # No feasible full path — should not happen if precedence is consistent.
        return {
            'sequence': [], 'rep': 0, 'distance': 0.0, 'rep_per_dist': None,
            'states_visited': states_visited,
            'elapsed_sec': time.monotonic() - started,
            'method': 'heldkarp',
            'error': 'no feasible full path',
        }

    # Reconstruct sequence by walking parents back.
    seq_rev: list[int] = []
    cur_mask = full_mask
    cur_last = best_last
    while cur_last != -1:
        seq_rev.append(cur_last)
        cost, parent = dp[(cur_mask, cur_last)]
        if parent == -1:
            break
        cur_mask = cur_mask & ~(1 << cur_last)
        cur_last = parent
    sequence = list(reversed(seq_rev))

    rep = sum(sg.stops[i].quest.get('rep', 0)
              for i in sequence if sg.stops[i].type == 'QT')
    rep_per_dist = (rep / best_cost) if best_cost > 0 else None
    return {
        'sequence': sequence,
        'rep': rep,
        'distance': best_cost,
        'rep_per_dist': rep_per_dist,
        'states_visited': states_visited,
        'elapsed_sec': time.monotonic() - started,
        'method': 'heldkarp',
    }
