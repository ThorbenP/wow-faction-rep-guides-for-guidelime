"""Quest filtering by faction; race/class bitmask decoders; cross-zone
classification (kept vs complex)."""
from __future__ import annotations

from typing import Any

from .constants import (
    ALL_CLASSES_MASK, ALL_RACES_MASK, ALLIANCE_MASK, CLASS_FLAGS,
    HORDE_MASK, RACE_FLAGS,
)
from .parsers import arr_get, flatten_ids, flatten_objective_ids

DEPRECATED_PREFIXES = ('[old]', '[dep]', '[unused]')

# Profession skill IDs that we recognise for the "needs Cooking 50" style
# quest annotation. Anything else is dropped silently.
SKILL_NAMES = {
    129: 'First Aid', 164: 'Blacksmithing', 165: 'Leatherworking',
    171: 'Alchemy', 182: 'Herbalism', 185: 'Cooking', 186: 'Mining',
    197: 'Tailoring', 202: 'Engineering', 333: 'Enchanting',
    356: 'Fishing', 393: 'Skinning',
}

# Reputation-tier thresholds. The value in `requiredMinRep` is the lower
# bound of the named standing.
REP_TIER_THRESHOLDS = [
    (3000, 'Friendly'),
    (6000, 'Honored'),
    (12000, 'Revered'),
    (21000, 'Exalted'),
]


def _rep_tier_name(value: int) -> str | None:
    if value < REP_TIER_THRESHOLDS[0][0]:
        return None
    for threshold, name in REP_TIER_THRESHOLDS:
        if value < threshold + 1:
            return name
    return 'Exalted'


def _extract_pair(value: object) -> tuple[int | None, int | None]:
    """Read `{skill_id, value}` or `{faction_id, value}` as a (id, value) tuple."""
    if isinstance(value, dict):
        keys = sorted(value.keys())
        a = value.get(keys[0]) if keys else None
        b = value.get(keys[1]) if len(keys) > 1 else None
        return a, b
    if isinstance(value, list) and len(value) >= 2:
        return value[0], value[1]
    return None, None


def filter_quests_by_faction(quest_db: dict[int, dict], faction_id: int) -> list[dict]:
    """Return all quests that grant reputation for the given faction.

    Quests whose name starts with a deprecated marker (`[OLD]`, `[DEP]`,
    `[UNUSED]`) are filtered out entirely.
    """
    result: list[dict] = []
    for qid, arr in quest_db.items():
        rep_value = _extract_rep_value(arr_get(arr, 26), faction_id)
        if rep_value <= 0:
            continue
        q = _build_quest_dict(qid, arr, rep_value=rep_value, is_bridge=False)
        if q is not None:
            result.append(q)
    return result


def expand_with_prereq_bridges(
    rep_quests: list[dict], quest_db: dict[int, dict],
) -> list[dict]:
    """Add bridge quests to the rep-quest list.

    A bridge quest grants no rep itself but is a `pre`/`preg` prerequisite
    for a rep-quest. Without bridges in the output the player would see a
    rep-quest they cannot accept. Walking is transitive — bridges of bridges
    are pulled in too.

    Bridges are tagged `is_bridge=True` and `rep=0`. After coordinate
    resolution, `drop_unreachable_bridge_chains` decides whether each
    bridge chain stays in its zone or moves to the complex section.
    """
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
            bridge = _build_quest_dict(pid, bridge_arr, rep_value=0, is_bridge=True)
            if bridge is None:
                continue
            bridges[pid] = bridge
            walk(pid)

    for q in rep_quests:
        walk(q['id'])

    return rep_quests + list(bridges.values())


def _build_quest_dict(
    qid: int, arr: Any, rep_value: int, is_bridge: bool,
) -> dict | None:
    """Build the quest dict from a positional Questie array."""
    name = arr_get(arr, 1) or f'Quest {qid}'
    if isinstance(name, str) and name.lower().startswith(DEPRECATED_PREFIXES):
        return None

    started_by = arr_get(arr, 2)
    finished_by = arr_get(arr, 3)
    obj_raw = arr_get(arr, 10)
    special_flags = int(arr_get(arr, 24) or 0)

    # Required profession skill (idx 18: {skill_id, value}).
    skill_id, skill_val = _extract_pair(arr_get(arr, 18))
    required_skill = None
    if skill_id and skill_id in SKILL_NAMES:
        if skill_val:
            required_skill = f'{SKILL_NAMES[skill_id]} {skill_val}'
        else:
            required_skill = SKILL_NAMES[skill_id]

    # Required minimum standing (idx 19: {faction_id, value}).
    _, minrep_val = _extract_pair(arr_get(arr, 19))
    required_min_rep = _rep_tier_name(int(minrep_val)) if minrep_val else None

    return {
        'id':       qid,
        'name':     name,
        'rep':      rep_value,
        'is_bridge': is_bridge,
        'repeatable': bool(special_flags & 1),  # specialFlags bit 0 = repeatable
        'required_skill':  required_skill,
        'required_min_rep': required_min_rep,
        'level':    int(arr_get(arr, 5) or 0),
        'minLevel': int(arr_get(arr, 4) or 0),
        'race':     int(arr_get(arr, 6) or 0),
        'class':    int(arr_get(arr, 7) or 0),
        'pre':      flatten_ids(arr_get(arr, 13)),
        'preg':     flatten_ids(arr_get(arr, 12)),
        'next':     arr_get(arr, 22),
        'zoneOrSort': int(arr_get(arr, 17) or 0),
        'start_npcs':    flatten_ids(arr_get(started_by, 1)) if started_by else [],
        'start_objects': flatten_ids(arr_get(started_by, 2)) if started_by else [],
        'start_items':   flatten_ids(arr_get(started_by, 3)) if started_by else [],
        'end_npcs':      flatten_ids(arr_get(finished_by, 1)) if finished_by else [],
        'end_objects':   flatten_ids(arr_get(finished_by, 2)) if finished_by else [],
        'obj_creatures': flatten_objective_ids(arr_get(obj_raw, 1)) if obj_raw else [],
        'obj_objects':   flatten_objective_ids(arr_get(obj_raw, 2)) if obj_raw else [],
        'obj_items':     flatten_objective_ids(arr_get(obj_raw, 3)) if obj_raw else [],
    }


def drop_unreachable_bridge_chains(
    quests: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split quests into (kept, complex) after coordinate attachment.

    `kept` are quests that belong into a normal zone sub-guide. `complex`
    are quests whose chain crosses zone boundaries — they end up in a
    "Complex Quests" section attributed to the entry zone (the zone where
    the chain's first quest can be picked up).

    Cross-zone chains are not dropped wholesale: a self-contained sub-tree
    of a cross-zone component is extracted back into the kept set so the
    player still sees the parts they can do entirely within one zone. For
    example, Q1022 "The Howling Vale" (start + objective + turnin all in
    Ashenvale) is extracted from a chain that later crosses into Darnassus.

    Solo cross-zone quests (no chain partners; pickup zone != turnin zone)
    are also pushed to complex — chained cross-zone tails stay with their
    chain so the visual narrative is not torn apart.
    """
    from collections import defaultdict
    from .zones import get_pickup_zone

    by_id = {q['id']: q for q in quests}
    adj: dict[int, set[int]] = defaultdict(set)
    for q in quests:
        for pid in q['pre'] + q['preg']:
            if pid in by_id:
                adj[q['id']].add(pid)
                adj[pid].add(q['id'])

    visited: set[int] = set()
    components: list[list[dict]] = []
    for q in quests:
        if q['id'] in visited:
            continue
        comp: list[dict] = []
        stack = [q['id']]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(by_id[cur])
            for n in adj[cur]:
                if n not in visited:
                    stack.append(n)
        components.append(comp)

    keep_qids: set[int] = set()
    complex_qids: set[int] = set()
    for comp in components:
        has_bridge = any(q.get('is_bridge') for q in comp)
        if not has_bridge:
            keep_qids.update(q['id'] for q in comp)
            continue
        zones = {get_pickup_zone(q) for q in comp if get_pickup_zone(q) is not None}
        if len(zones) <= 1:
            keep_qids.update(q['id'] for q in comp)
            continue
        # Cross-zone component: extract the in-zone sub-tree, push the rest
        # to the complex set.
        extracted = _extract_in_zone_subset(comp, by_id)
        keep_qids.update(extracted)
        for q in comp:
            if q['id'] not in extracted:
                complex_qids.add(q['id'])

    # Solo cross-zone quests (no chain partner; pickup zone != turnin zone)
    # also belong in the complex section. Chain-integrated cross-zone tails
    # stay in their chain so the chain is not visually fragmented.
    solo_xz = _identify_solo_cross_zone(keep_qids, by_id)
    keep_qids -= solo_xz
    complex_qids |= solo_xz

    kept = [q for q in quests if q['id'] in keep_qids]
    complex_ = [q for q in quests if q['id'] in complex_qids]
    return kept, complex_


def _identify_solo_cross_zone(
    keep_qids: set[int], by_id: dict[int, dict],
) -> set[int]:
    """Find rep quests in `keep_qids` that have no chain partners in the
    kept set and whose pickup zone differs from the turnin zone. These
    belong in the complex section of their pickup zone.
    """
    from collections import defaultdict
    from .zones import get_pickup_zone, get_turnin_zone

    adj: dict[int, set[int]] = defaultdict(set)
    for qid in keep_qids:
        q = by_id[qid]
        for pid in q['pre'] + q['preg']:
            if pid in keep_qids:
                adj[qid].add(pid)
                adj[pid].add(qid)

    result: set[int] = set()
    for qid in keep_qids:
        if adj[qid]:
            continue
        q = by_id[qid]
        if q.get('is_bridge'):
            continue
        pz = get_pickup_zone(q)
        tz = get_turnin_zone(q)
        if pz is None or tz is None:
            continue
        if pz != tz:
            result.add(qid)
    return result


def attribute_complex_to_zones(
    complex_quests: list[dict],
) -> dict[int, list[dict]]:
    """Map each complex (cross-zone) connected component to its entry zone.

    The entry zone is the pickup zone of the chain's first quest — quests
    in the component that have no in-component prerequisites. For
    components with multiple entry quests in different zones, the most
    common zone wins; ties are broken by the lowest zone ID. Components
    without any pickup zone fall under key `0`.
    """
    from collections import defaultdict, Counter
    from .zones import get_pickup_zone

    by_id = {q['id']: q for q in complex_quests}
    adj: dict[int, set[int]] = defaultdict(set)
    for q in complex_quests:
        for pid in q['pre'] + q['preg']:
            if pid in by_id:
                adj[q['id']].add(pid)
                adj[pid].add(q['id'])

    visited: set[int] = set()
    components: list[list[dict]] = []
    for q in complex_quests:
        if q['id'] in visited:
            continue
        comp: list[dict] = []
        stack = [q['id']]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(by_id[cur])
            for n in adj[cur]:
                if n not in visited:
                    stack.append(n)
        components.append(comp)

    by_zone: dict[int, list[dict]] = defaultdict(list)
    for comp in components:
        comp_ids = {q['id'] for q in comp}
        entries = []
        for q in comp:
            preds = (q.get('pre') or []) + (q.get('preg') or [])
            if not any(p in comp_ids for p in preds):
                entries.append(q)
        zones = [
            get_pickup_zone(e) for e in entries
            if get_pickup_zone(e) is not None
        ]
        if zones:
            zone_counts = Counter(zones)
            top = zone_counts.most_common(1)[0][1]
            zone = min(z for z, c in zone_counts.items() if c == top)
        else:
            zone = 0
        by_zone[zone].extend(comp)
    return dict(by_zone)


def _extract_in_zone_subset(
    comp: list[dict], by_id: dict[int, dict],
) -> set[int]:
    """Return IDs of quests from `comp` that belong in their own zone.

    A quest qualifies if it is itself self-contained (pickup zone equals
    turnin zone) AND every transitive prerequisite (`pre`/`preg`) is also
    in that same zone for both its pickup and turnin coords. Each extracted
    quest also pulls its in-zone prerequisites along, so bridges and
    pre-rep-quests end up in the right sub-guide.
    """
    from .zones import get_pickup_zone, get_turnin_zone

    extracted: set[int] = set()
    for q in comp:
        if q.get('is_bridge'):
            continue
        zone = get_pickup_zone(q)
        if zone is None or get_turnin_zone(q) != zone:
            continue
        chain_ids: set[int] = {q['id']}
        stack = list((q.get('pre') or []) + (q.get('preg') or []))
        ok = True
        while stack:
            pid = stack.pop()
            if pid in chain_ids:
                continue
            ancestor = by_id.get(pid)
            if ancestor is None:
                continue
            apz = get_pickup_zone(ancestor)
            atz = get_turnin_zone(ancestor)
            if apz != zone or (atz is not None and atz != zone):
                ok = False
                break
            chain_ids.add(pid)
            stack.extend((ancestor.get('pre') or []) + (ancestor.get('preg') or []))
        if ok:
            extracted.update(chain_ids)
    return extracted


def _extract_rep_value(rep_reward: Any, faction_id: int) -> int:
    """Read the rep value out of `reputationReward = {{factionID, value}, ...}`
    for the given faction, returning the highest matching value (0 if none)."""
    if not rep_reward:
        return 0
    if isinstance(rep_reward, dict):
        entries = [rep_reward[k] for k in sorted(rep_reward.keys())]
    elif isinstance(rep_reward, list):
        entries = rep_reward
    else:
        return 0

    rep_value = 0
    for entry in entries:
        if isinstance(entry, dict):
            pair = [entry.get(k) for k in sorted(entry.keys())]
        elif isinstance(entry, list):
            pair = entry
        else:
            continue
        if len(pair) >= 2 and pair[0] == faction_id and pair[1]:
            rep_value = max(rep_value, int(pair[1]))
    return rep_value


def decode_races(mask: int) -> list[str] | None:
    """Bitmask -> list of race names, or `['Alliance']`/`['Horde']` for the
    full-side masks, or `None` for the all-races mask."""
    if not mask or mask == ALL_RACES_MASK:
        return None
    if mask == ALLIANCE_MASK:
        return ['Alliance']
    if mask == HORDE_MASK:
        return ['Horde']
    return [name for bit, name in RACE_FLAGS if mask & bit]


def decode_classes(mask: int) -> list[str] | None:
    """Bitmask -> list of class names, or `None` for the all-classes mask."""
    if not mask or mask == ALL_CLASSES_MASK:
        return None
    return [name for bit, name in CLASS_FLAGS if mask & bit]
