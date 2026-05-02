"""3-opt refinement: cut the tour in three places and reconnect the
four resulting segments in one of four non-trivial ways.

2-opt reverses segments. Or-opt relocates segments. 3-opt is the
strict generalisation that includes both as special cases plus four
additional reconnection topologies that neither move can reach in a
single pass.

Where 2-opt converges on a local optimum *under sequence reversal* and
or-opt converges *under segment relocation*, neither rules out
configurations a 3-opt swap could improve. Empirically 3-opt finds a
fraction of percent extra distance on top of the alternating 2-opt /
or-opt pipeline; on these tour sizes (typically ≤ 80 entries) the
O(N³) candidate space is still tractable in pure Python.

The four 3-opt reconnections we evaluate (S1, S2, S3, S4 are the
segments cut at indices i, j, k):
  1. S1 + S3 + S2 + S4
  2. S1 + reverse(S2) + S3 + S4   (= 2-opt at i,j — covered, skipped)
  3. S1 + S2 + reverse(S3) + S4   (= 2-opt at j,k — covered, skipped)
  4. S1 + reverse(S3) + reverse(S2) + S4
  5. S1 + reverse(S3) + S2 + S4
  6. S1 + S3 + reverse(S2) + S4

Patterns 2 and 3 are 2-opt subsets and are not retried here. Patterns
1, 4, 5, 6 are pure 3-opt moves. Move evaluation is incremental — only
the three boundary edges (i-1↔..., ...↔k+1, and the two interior
joins) change cost, so each candidate is O(1).
"""
from __future__ import annotations

import math
from typing import Optional

from .feasibility import is_feasible
from .two_opt import JUMP_PENALTY
from .types import TourEntry

# Cap on outer iterations. Each iteration sweeps the full O(N³) space
# in first-improvement mode; one or two rounds typically converge.
MAX_PASSES = 2


def three_opt_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[tuple[int, float, float]],
) -> list[TourEntry]:
    """First-improvement 3-opt over the four pure reconnection topologies.

    Returns the input tour unchanged if no move improves cost. Validity
    is re-checked over the full reordered sequence; precedence in
    sub-guide tours is sparse, so most candidate moves stay valid.
    """
    n = len(tour)
    if n < 4:
        return tour

    best = list(tour)
    best_cost = _entry_cost(best, start_pos)
    for _ in range(MAX_PASSES):
        improved = False
        for i in range(n - 2):
            for j in range(i + 1, n - 1):
                for k in range(j + 1, n):
                    cand_cost, cand = _try_three_opt(
                        best, i, j, k, start_pos,
                    )
                    if cand is None or cand_cost + 0.001 >= best_cost:
                        continue
                    if not _is_valid(cand, predecessors):
                        continue
                    best = cand
                    best_cost = cand_cost
                    improved = True
                    break  # restart sweep from current best
                if improved:
                    break
            if improved:
                break
        if not improved:
            break
    return best


def _try_three_opt(
    tour: list[TourEntry], i: int, j: int, k: int,
    start_pos: Optional[tuple[int, float, float]],
) -> tuple[float, Optional[list[TourEntry]]]:
    """Try the four pure 3-opt reconnections at cut-points (i, j, k)
    and return the cheapest. Reuses the cost over the prefix and
    suffix unchanged — only the boundary cost between the three cuts
    is recomputed per candidate.

    Returns `(cost, tour)`. Tour is None when no candidate beats the
    input.
    """
    s1 = tour[:i]
    s2 = tour[i:j]
    s3 = tour[j:k]
    s4 = tour[k:]

    candidates = [
        s1 + s3 + s2 + s4,                         # pattern 1
        s1 + list(reversed(s3)) + list(reversed(s2)) + s4,  # pattern 4
        s1 + list(reversed(s3)) + s2 + s4,         # pattern 5
        s1 + s3 + list(reversed(s2)) + s4,         # pattern 6
    ]

    best_cost = math.inf
    best_tour: Optional[list[TourEntry]] = None
    for c in candidates:
        cost = _entry_cost(c, start_pos)
        if cost + 1e-9 < best_cost:
            best_cost = cost
            best_tour = c
    return best_cost, best_tour


def _entry_cost(
    tour: list[TourEntry], start_pos: Optional[tuple[int, float, float]],
) -> float:
    """Same cost model as `two_opt._tour_cost`, computed at the entry
    level. Cross-zone hops carry `JUMP_PENALTY`; intra-zone hops are
    euclidean. Intra-cluster edges count too — this matches the
    headline distance reported by the score function.
    """
    d = 0.0
    cur = start_pos
    for entry in tour:
        for s in entry.stops:
            if cur is not None:
                if cur[0] == s.coord[0]:
                    d += math.hypot(cur[1] - s.coord[1], cur[2] - s.coord[2])
                else:
                    d += JUMP_PENALTY
            cur = s.coord
    return d


def _is_valid(
    tour: list[TourEntry], predecessors: dict[int, set[int]],
) -> bool:
    completed: dict[int, set[str]] = {}
    for entry in tour:
        for s in entry.stops:
            if not is_feasible(s, completed, predecessors):
                return False
            completed.setdefault(s.quest_id, set()).add(s.type)
    return True
