"""Pull in `pre`/`preg` prerequisite chains as bridge quests.

A bridge quest grants no rep itself but unlocks a rep-quest. Without bridges,
the player would see a rep-quest they cannot accept yet. The walk is
transitive — bridges of bridges follow.

Bridges are tagged `is_bridge=True, rep=0`. Whether each bridge stays in its
zone or moves into the complex section is decided later by
`classify.drop_unreachable_bridge_chains` (after coordinate resolution).
"""
from __future__ import annotations

from ..questie import arr_get, flatten_ids
from .builder import build_quest_dict


def expand_with_prereq_bridges(
    rep_quests: list[dict], quest_db: dict[int, dict],
) -> list[dict]:
    rep_qids = {q['id'] for q in rep_quests}
    bridges: dict[int, dict] = {}
    visited: set[int] = set()

    def walk(qid: int) -> None:
        if qid in visited:
            return
        visited.add(qid)
        arr = quest_db.get(qid)
        if not arr:
            return
        prereqs = flatten_ids(arr_get(arr, 13)) + flatten_ids(arr_get(arr, 12))
        for pid in prereqs:
            if pid in rep_qids or pid in bridges:
                walk(pid)
                continue
            bridge_arr = quest_db.get(pid)
            if not bridge_arr:
                continue
            bridge = build_quest_dict(pid, bridge_arr, rep_value=0, is_bridge=True)
            if bridge is None:
                continue
            bridges[pid] = bridge
            walk(pid)

    for q in rep_quests:
        walk(q['id'])

    return rep_quests + list(bridges.values())
