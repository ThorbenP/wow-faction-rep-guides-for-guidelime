"""OR-Tools CP-SAT solver for the optimum-pathing problem.

The model is identical in semantics to the Held-Karp formulation, but
instead of enumerating reachable states it uses CP-SAT's circuit
constraint plus rank propagation. This scales to sub-guides Held-Karp
cannot fit in memory (~30 stops upward).

Encoding:
- Node 0 is a virtual depot. Distance d(0, s) is the (Euclidean,
  zone-aware) cost from `sg.start_pos` to stop s, and d(s, 0) = 0
  (free return — we only care about path length, not closing the loop).
- One Boolean arc[i][j] for every ordered pair i != j. AddCircuit
  enforces that the chosen arcs form a Hamiltonian cycle through all
  N+1 nodes.
- A `rank[i]` integer per node (rank[0] := 0) propagates along arcs:
  for each arc (i, j) with j != 0 we enforce rank[j] = rank[i] + 1
  whenever its boolean is true.
- Precedence: for every (predecessor stop a, dependent stop b),
  rank[a+1] < rank[b+1]. The +1 offset comes from depot-shifted node
  indices.
- Objective: sum of arc booleans times integer-scaled distances. We
  scale by 10000 (4 decimal digits of precision) — the Map-Unit
  resolution in WoW is far coarser than that.

The CP-SAT solver returns OPTIMAL only if it has proven optimality.
FEASIBLE means a solution was found within the time budget but the
search did not finish — the result is upper-bounded but not certified
optimal.
"""
from __future__ import annotations

import math
import time
from typing import Optional

from ortools.sat.python import cp_model

from .dataset import (
    SubGuide, build_distance_matrix, build_stop_predecessor_masks,
    distances_from_start,
)

DEFAULT_TIME_LIMIT_SEC = 600  # 10 minutes
DISTANCE_SCALE = 10000        # 4 decimal digits


def solve_ortools(
    sg: SubGuide, *,
    time_limit_sec: float = DEFAULT_TIME_LIMIT_SEC,
    workers: Optional[int] = None,
    log_search: bool = False,
) -> dict:
    """Return the OR-Tools optimum (or best-found within budget) for `sg`."""
    started = time.monotonic()
    n = len(sg.stops)
    if n == 0:
        return _empty_result()
    if n == 1:
        return _single_stop_result(sg, started)

    dmat = build_distance_matrix(sg)
    from_start = distances_from_start(sg)
    pred_masks = build_stop_predecessor_masks(sg)

    big = n + 1  # depot + stops
    model = cp_model.CpModel()

    # Integer-scaled distances (depot = 0; stops 1..n -> sg.stops[0..n-1]).
    def cost(i: int, j: int) -> int:
        if j == 0:
            return 0
        if i == 0:
            return int(round(from_start[j - 1] * DISTANCE_SCALE))
        return int(round(dmat[i - 1][j - 1] * DISTANCE_SCALE))

    # Build arcs and circuit constraint.
    arc_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    for i in range(big):
        for j in range(big):
            if i == j:
                continue
            arc_vars[(i, j)] = model.NewBoolVar(f'a_{i}_{j}')
    model.AddCircuit([(i, j, arc_vars[(i, j)]) for i, j in arc_vars])

    # Rank propagation: rank[0] = 0; arc (i, j) implies rank[j] = rank[i] + 1
    # whenever j != 0 (we leave the closing-arc rank free).
    rank = [model.NewIntVar(0, big - 1, f'r_{i}') for i in range(big)]
    model.Add(rank[0] == 0)
    for (i, j), b in arc_vars.items():
        if j == 0:
            continue
        model.Add(rank[j] == rank[i] + 1).OnlyEnforceIf(b)

    # Precedence: rank[pred + 1] < rank[stop + 1].
    for stop_idx, mask in enumerate(pred_masks):
        if mask == 0:
            continue
        m = mask
        while m:
            low = m & -m
            pred = low.bit_length() - 1
            model.Add(rank[pred + 1] < rank[stop_idx + 1])
            m ^= low

    # Objective: total integer-scaled distance.
    model.Minimize(sum(cost(i, j) * b for (i, j), b in arc_vars.items()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    if workers:
        solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = log_search

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            'sequence': [],
            'rep': 0,
            'distance': 0.0,
            'rep_per_dist': None,
            'elapsed_sec': time.monotonic() - started,
            'method': 'ortools',
            'status': solver.StatusName(status),
            'best_bound': None,
        }

    # Reconstruct path by following the chosen arcs from the depot.
    successor: dict[int, int] = {}
    for (i, j), b in arc_vars.items():
        if solver.Value(b):
            successor[i] = j

    sequence: list[int] = []
    cur = successor[0]
    seen = {0}
    while cur != 0:
        if cur in seen:
            break  # safety — should not happen with a valid circuit
        seen.add(cur)
        sequence.append(cur - 1)
        cur = successor[cur]

    distance = solver.ObjectiveValue() / DISTANCE_SCALE
    rep = sum(
        sg.stops[i].quest.get('rep', 0)
        for i in sequence
        if sg.stops[i].type == 'QT'
    )
    return {
        'sequence': sequence,
        'rep': rep,
        'distance': distance,
        'rep_per_dist': (rep / distance) if distance > 0 else None,
        'elapsed_sec': time.monotonic() - started,
        'method': 'ortools',
        'status': solver.StatusName(status),
        'best_bound': solver.BestObjectiveBound() / DISTANCE_SCALE,
    }


def _empty_result() -> dict:
    return {
        'sequence': [], 'rep': 0, 'distance': 0.0, 'rep_per_dist': None,
        'elapsed_sec': 0.0, 'method': 'ortools', 'status': 'EMPTY',
    }


def _single_stop_result(sg: SubGuide, started: float) -> dict:
    distances = distances_from_start(sg)
    rep = sg.stops[0].quest.get('rep', 0) if sg.stops[0].type == 'QT' else 0
    dist = distances[0]
    return {
        'sequence': [0],
        'rep': rep,
        'distance': dist,
        'rep_per_dist': (rep / dist) if dist > 0 else None,
        'elapsed_sec': time.monotonic() - started,
        'method': 'ortools',
        'status': 'OPTIMAL',
        'best_bound': dist,
    }
