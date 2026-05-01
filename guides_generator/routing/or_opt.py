"""Or-opt refinement: move short segments to a better position in the tour.

Complement to 2-opt. Where 2-opt reverses (i, j)-segments, or-opt picks
up a contiguous segment of length 1..4 TourEntries and re-inserts it
elsewhere — without reversing it. Some reorderings 2-opt cannot reach
in one move are reachable by an or-opt relocation, and vice versa. The
two are alternated by `tour.route_subguide` until both converge.

Cost is evaluated **incrementally**: an or-opt move changes at most six
boundary edges (three removed, three added), so each candidate is O(1)
instead of the O(n) a full `_tour_cost` recompute would cost. With ~80
entries in the larger sub-guides this is the difference between a
15-second bulk run and a 90-second one.

Feasibility is checked only when the cost delta is already negative —
most candidates are dropped on the cheaper cost test first.

Segment-length sweep on the 30-faction TBC corpus:
    k in (1, 2, 3)       -> baseline
    k in (1, 2, 3, 4)    -> -0.3% extra distance
    k in (1, 2, 3, 4, 5) -> regresses (longer segments are too rigid for
                            precedence-bound chains)
"""
from __future__ import annotations

import math
from typing import Optional

from .feasibility import is_feasible
from .two_opt import JUMP_PENALTY
from .types import TourEntry

# Maximum number of "first-improving" relocations applied per call. The
# outer alternation in `tour.route_subguide` re-invokes us anyway and
# detects convergence one level up, so a generous cap here is fine.
MAX_PASSES = 3

Coord = tuple[int, float, float]


def or_opt_pass(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[Coord],
) -> list[TourEntry]:
    """Pick up segments of length 1..4 and try inserting them at every
    other position. Accept the relocation if cost drops AND every stop's
    precedence is still satisfied. Iterate until no relocation improves
    the cost (or `MAX_PASSES` reached).
    """
    n = len(tour)
    if n < 4:
        return tour

    best = list(tour)
    for _ in range(MAX_PASSES):
        candidate = _first_improving_relocation(best, predecessors, start_pos)
        if candidate is None:
            break
        best = candidate
    return best


def _first_improving_relocation(
    tour: list[TourEntry],
    predecessors: dict[int, set[int]],
    start_pos: Optional[Coord],
) -> Optional[list[TourEntry]]:
    """Return the first relocation that lowers the cost, or None when no
    relocation in the (k, i, j) search space improves on the current tour.

    Uses incremental cost (`_move_cost_delta`) to evaluate candidates in
    O(1) — feasibility is checked only when the delta is negative.
    """
    n = len(tour)
    firsts = [e.stops[0].coord for e in tour]
    lasts = [e.stops[-1].coord for e in tour]

    for k in (1, 2, 3, 4):
        for i in range(n - k + 1):
            for j in range(n - k + 1):
                if j == i:
                    continue  # no-op: re-insert at the same spot
                delta = _move_cost_delta(firsts, lasts, i, k, j, start_pos)
                if delta + 0.001 >= 0:
                    continue
                cand = _apply_move(tour, i, k, j)
                if not _is_valid(cand, predecessors):
                    continue
                return cand
    return None


def _apply_move(
    tour: list[TourEntry], i: int, k: int, j: int,
) -> list[TourEntry]:
    """Build the relocated tour. `j` is the insertion index in the tour
    with the segment removed."""
    rest = tour[:i] + tour[i + k:]
    return rest[:j] + tour[i:i + k] + rest[j:]


def _move_cost_delta(
    firsts: list[Coord], lasts: list[Coord],
    i: int, k: int, j: int,
    start_pos: Optional[Coord],
) -> float:
    """Cost change for moving tour[i:i+k] to position j in the segment-less
    tour. Positive = relocation makes the tour worse; negative = better.

    Six edges are involved at most:
        REMOVED: edge into the original segment slot
                 edge out of the original segment slot
                 edge being split at the new insertion point (if any)
        ADDED:   edge that closes the original gap
                 edge into the segment at its new position
                 edge out of the segment at its new position
    Edge cases (segment at tour boundary, insertion at tour boundary) drop
    one or two of these; `_edge_at_boundary` returns 0 for the missing ones.
    """
    n = len(firsts)
    seg_first = firsts[i]
    seg_last = lasts[i + k - 1]

    # --- REMOVED edges around the original segment slot ---
    # Edge into segment (or start_pos if segment is at the front)
    prev_to_seg = _coord_before(lasts, i, start_pos)
    cost_in_seg_orig = _edge(prev_to_seg, seg_first)
    # Edge out of segment (or 0 if segment is at the end)
    next_after_seg = firsts[i + k] if i + k < n else None
    cost_out_seg_orig = _edge(seg_last, next_after_seg) if next_after_seg is not None else 0.0

    # --- ADDED edge closing the gap (only when both ends exist) ---
    cost_gap = _edge(prev_to_seg, next_after_seg) if next_after_seg is not None else 0.0
    # If i == 0 and segment was at front, the "gap-closing" edge becomes
    # start_pos -> next_after_seg. _coord_before handles this via start_pos.

    # --- The insertion point is at index `j` of `rest = tour without segment`. ---
    # rest[m] = tour[m] for m < i, tour[m + k] for m >= i.
    prev_in_rest = _rest_prev(lasts, i, k, j, start_pos)
    next_in_rest = _rest_next(firsts, i, k, j, n)

    # REMOVED: the edge being split at the insertion point (if present and not at boundary)
    cost_split_orig = (
        _edge(prev_in_rest, next_in_rest)
        if prev_in_rest is not None and next_in_rest is not None
        else 0.0
    )

    # ADDED: edges into and out of the segment at its new position
    cost_in_seg_new = _edge(prev_in_rest, seg_first)
    cost_out_seg_new = _edge(seg_last, next_in_rest) if next_in_rest is not None else 0.0

    return (
        - cost_in_seg_orig
        - cost_out_seg_orig
        + cost_gap
        - cost_split_orig
        + cost_in_seg_new
        + cost_out_seg_new
    )


def _coord_before(
    lasts: list[Coord], i: int, start_pos: Optional[Coord],
) -> Optional[Coord]:
    """The coord of the entry that precedes index `i` in the original tour.
    Returns `start_pos` when `i == 0` (which may itself be None)."""
    return start_pos if i == 0 else lasts[i - 1]


def _rest_prev(
    lasts: list[Coord], i: int, k: int, j: int, start_pos: Optional[Coord],
) -> Optional[Coord]:
    """Coord of the entry preceding the insertion point in `rest = tour[:i] + tour[i+k:]`.
    Returns `start_pos` when `j == 0`."""
    if j == 0:
        return start_pos
    rest_idx = j - 1
    # rest[m] = tour[m] for m < i, tour[m + k] for m >= i.
    orig_idx = rest_idx if rest_idx < i else rest_idx + k
    return lasts[orig_idx]


def _rest_next(
    firsts: list[Coord], i: int, k: int, j: int, n: int,
) -> Optional[Coord]:
    """Coord of the entry following the insertion point in `rest`.
    Returns None when `j == len(rest)` (segment goes at the very end)."""
    rest_len = n - k
    if j == rest_len:
        return None
    orig_idx = j if j < i else j + k
    return firsts[orig_idx]


def _edge(a: Optional[Coord], b: Optional[Coord]) -> float:
    """Boundary-edge cost between two entries. Returns 0 for a None
    predecessor (start of tour with no anchor) and uses JUMP_PENALTY for
    cross-zone hops, mirroring `two_opt._tour_cost`."""
    if a is None or b is None:
        return 0.0
    if a[0] != b[0]:
        return JUMP_PENALTY
    return math.hypot(a[1] - b[1], a[2] - b[2])


def _is_valid(t: list[TourEntry], predecessors: dict[int, set[int]]) -> bool:
    completed: dict[int, set[str]] = {}
    for entry in t:
        for s in entry.stops:
            if not is_feasible(s, completed, predecessors):
                return False
            completed.setdefault(s.quest_id, set()).add(s.type)
    return True
