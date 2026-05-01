"""Filter quests by faction and lift each Questie array into a quest dict.

The builder also resolves rep-tier names (`Honored`, `Revered`, ...), profession
skill annotations (`Cooking 50`), and the `repeatable` flag from `specialFlags`.
Quests whose name starts with a deprecated marker are filtered out entirely.
"""
from __future__ import annotations

from typing import Any

from ..questie import arr_get, flatten_ids, flatten_objective_ids

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
        q = build_quest_dict(qid, arr, rep_value=rep_value, is_bridge=False)
        if q is not None:
            result.append(q)
    return result


def build_quest_dict(
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
