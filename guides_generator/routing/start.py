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

`pick_start_candidates` is the multi-anchor variant: when several quests
share the minimum level (a starter zone usually has 3-6 of them), there
is no a-priori best one to begin from — an outlier quest is sometimes
worth visiting first because the spawn-to-its-pickup edge is then free
and the rest of the cluster is visited contiguously afterwards. The
caller (typically `output/sub_guide.py`) builds a tour for each
candidate and keeps the cheapest.
"""
from __future__ import annotations

from typing import Optional

# Cap how many pickups we try as start anchors. Each candidate runs
# its own multistart-and-refine pipeline, so per-sub-guide runtime
# scales linearly with this cap. 6 is the empirical sweet spot — most
# sub-guides have far fewer distinct candidates anyway, but city + hub
# buckets occasionally surface 4-6 useful spawn anchors that pay off.
MAX_START_CANDIDATES = 6

# How many levels above min_level still count as a candidate. The
# starter zone has several quests at the same minimum level by
# definition, but a quest one or two levels up is sometimes a better
# spawn anchor — it may be geographically outlying and visiting it
# first amortises the trip across the whole cluster. 2 is empirically
# the sweet spot; >2 starts diluting the candidate pool with quests
# the player would not naturally pick first.
LEVEL_TOLERANCE = 2


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


def pick_start_candidates(
    quests: list[dict], max_k: int = MAX_START_CANDIDATES,
) -> list[tuple[int, float, float]]:
    """Up to `max_k` distinct pickup coords drawn from the quests
    within `LEVEL_TOLERANCE` levels of the minimum level. Returns `[]`
    when no quest has a usable pickup + positive level (same condition
    under which `pick_start_position` returns None).

    Distinct on coord, not on quest — multiple quests at the same NPC
    collapse to one candidate. Sort key is `(level, quest_id)`, so
    min-level pickups always come first and the tie-break is stable
    across runs even when the input order shifts.
    """
    candidates = [
        q for q in quests
        if q.get('pickup_coords') and q.get('level', 0) > 0
    ]
    if not candidates:
        return []
    candidates.sort(key=lambda q: (q['level'], q['id']))
    min_level = candidates[0]['level']
    seen: set[tuple[int, float, float]] = set()
    out: list[tuple[int, float, float]] = []
    for q in candidates:
        if q['level'] > min_level + LEVEL_TOLERANCE:
            break
        c = q['pickup_coords']
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= max_k:
            break
    return out
