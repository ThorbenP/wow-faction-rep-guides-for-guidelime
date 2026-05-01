"""Pick the starting position of a sub-guide tour.

Heuristic: start at the pickup of the lowest-level quest. In starter zones
this is the racial tutorial area near the spawn point — exactly where the
player arrives. The tour builder uses this as the initial cluster centre,
and 2-opt uses it as the cost-function anchor, so stops near the spawn
end up at the front of the tour even when greedy ordering would otherwise
pick a more central stop first.

Falls back to `None` (unanchored greedy start) when no quest with both a
usable pickup coord and a level > 0 is available — typical for bridge-only
chains or hub zones with auto-start quests only.

Tiebreaker on equal levels: the lowest quest ID, so the choice is stable
across runs even when the input order shifts.
"""
from __future__ import annotations

from typing import Optional


def pick_start_position(
    quests: list[dict],
) -> Optional[tuple[int, float, float]]:
    candidates = [
        q for q in quests
        if q.get('pickup_coords') and q.get('level', 0) > 0
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda q: (q['level'], q['id']))
    return candidates[0]['pickup_coords']
