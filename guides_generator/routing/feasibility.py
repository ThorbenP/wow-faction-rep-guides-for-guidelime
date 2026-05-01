"""Stop-level precedence: which Stops are pickable given what is already done.

Predecessors come from three sources:
    pre / preg     — the quest references its prerequisites directly
    next           — another quest declares this one as its successor

Item-drop bridge quests (no `pickup_coords`) have no QA stop. Their QA is
treated as implicitly satisfied once the triggering item is in the inventory,
so QC and QT for such quests do not wait for a non-existent pickup.
"""
from __future__ import annotations

from .types import Stop


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
    """True if all precedence constraints for `stop` are satisfied."""
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


def mark_done(completed: dict[int, set[str]], stop: Stop) -> None:
    completed.setdefault(stop.quest_id, set()).add(stop.type)
