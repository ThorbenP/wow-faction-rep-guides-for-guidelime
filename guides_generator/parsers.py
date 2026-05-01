"""Parsers for Questie's positional Lua tables (quests, NPCs, objects, items)."""
from __future__ import annotations

import os
import re
from typing import Any

try:
    from slpp import slpp as lua
except ImportError:
    print("ERROR: 'slpp' is not installed. Run: pip install slpp")
    raise

# Matches one entry of the form `[<id>] = { ... },` inside Questie's
# `[[return { ... }]]` long-string blocks.
ENTRY_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*=\s*(\{.*\})\s*,?\s*$')


# ---------------------------------------------------------------------------
# Lua helpers
# ---------------------------------------------------------------------------

def _read_questie_table(filepath: str, marker: str) -> str:
    """Extract the body of a Questie table written as `<marker>return {...}]]`
    and return the inner Lua source string.
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    start = content.find(marker)
    if start < 0:
        raise ValueError(f'marker {marker!r} not found in {filepath}')
    end = content.find(']]', start)
    body = content[start + len(marker):end]
    if body.lstrip().startswith('return'):
        body = body.lstrip()[len('return'):]
    return body


def arr_get(arr: Any, idx: int) -> Any:
    """Read index `idx` (1-based) from a positional Lua array (slpp produces
    either a dict with int keys or a list)."""
    if isinstance(arr, dict):
        return arr.get(idx)
    if isinstance(arr, list) and 0 < idx <= len(arr):
        return arr[idx - 1]
    return None


def flatten_ids(value: Any) -> list[int]:
    """Flatten a Lua array (dict with int keys, list, or scalar) into a flat
    list of ints — discarding the keys."""
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, dict):
        value = [value[k] for k in sorted(value.keys())]
    if isinstance(value, list):
        out: list[int] = []
        for v in value:
            out.extend(flatten_ids(v))
        return out
    return []


def flatten_objective_ids(value: Any) -> list[int]:
    """Questie objectives are nested like `{{creatureId, text?, icon?}, ...}`.
    Return only the IDs (the first element of each sub-list/dict)."""
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, dict):
        value = [value[k] for k in sorted(value.keys())]
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for entry in value:
        if isinstance(entry, int):
            out.append(entry)
        elif isinstance(entry, dict):
            cid = entry.get(1)
            if isinstance(cid, int):
                out.append(cid)
        elif isinstance(entry, list) and entry:
            cid = entry[0]
            if isinstance(cid, int):
                out.append(cid)
    return out


def _decode_entry_array(text: str) -> dict | None:
    """Parse one Lua array literal; normalise to a 1-based dict for indexing."""
    try:
        arr = lua.decode(text)
    except Exception:
        return None
    if isinstance(arr, list):
        return {i + 1: v for i, v in enumerate(arr)}
    if isinstance(arr, dict):
        return arr
    return None


def _iter_entries(body: str):
    """Yield (id, dict) for every `[id] = {...},` line in the table body."""
    for line in body.splitlines():
        m = ENTRY_LINE_RE.match(line)
        if not m:
            continue
        entry_id = int(m.group(1))
        arr = _decode_entry_array(m.group(2))
        if arr is None:
            continue
        yield entry_id, arr


# ---------------------------------------------------------------------------
# Quest DB
# ---------------------------------------------------------------------------
# questKeys (excerpt):
#   1=name, 2=startedBy {creatures, objects, items}, 3=finishedBy,
#   4=requiredLevel, 5=questLevel, 6=requiredRaces, 7=requiredClasses,
#   10=objectives {creatures, objects, items},
#   12=preQuestGroup, 13=preQuestSingle, 17=zoneOrSort, 22=nextQuestInChain,
#   26=reputationReward {{factionID, value}, ...}

def parse_quest_db(filepath: str) -> dict[int, dict]:
    print(f'  parse Questie quest DB ({os.path.getsize(filepath)//1024} KB)...')
    body = _read_questie_table(filepath, 'QuestieDB.questData = [[')
    quests = dict(_iter_entries(body))
    print(f'  ✓ {len(quests)} quests loaded')
    return quests


# ---------------------------------------------------------------------------
# NPC DB
# ---------------------------------------------------------------------------
# npcKeys: 1=name, 7=spawns {[zoneID]={{x,y},...}}, 9=primary zoneID

def parse_npc_db(filepath: str) -> dict[int, dict]:
    """Convert into a coords format compatible with `coords.get_npc_coords`:
        npc_id -> {'name': str, 'coords': [{1:x, 2:y, 3:zone}, ...], 'zone': int}
    The `coords` list is sorted so the primary-zone spawn comes first.
    """
    print(f'  parse Questie NPC DB ({os.path.getsize(filepath)//1024} KB)...')
    body = _read_questie_table(filepath, 'QuestieDB.npcData = [[')

    npcs: dict[int, dict] = {}
    for npc_id, arr in _iter_entries(body):
        name = arr.get(1) or ''
        primary_zone = int(arr.get(9) or 0)
        coords = _extract_spawns(arr.get(7))
        if primary_zone and coords:
            coords.sort(key=lambda c: 0 if c[3] == primary_zone else 1)
        npcs[npc_id] = {'name': name, 'coords': coords, 'zone': primary_zone}
    print(f'  ✓ {len(npcs)} NPCs loaded')
    return npcs


# ---------------------------------------------------------------------------
# Object DB
# ---------------------------------------------------------------------------
# objectKeys: 1=name, 2=questStarts, 3=questEnds, 4=spawns, 5=zoneID

def parse_object_db(filepath: str) -> dict[int, dict]:
    """Returns: object_id -> {'name': str, 'coords': [(zone, x, y), ...], ...}.
    Coords are tuples here (NPC DB uses dicts; both formats are handled by
    the coord-resolver)."""
    print(f'  parse Questie object DB ({os.path.getsize(filepath)//1024} KB)...')
    body = _read_questie_table(filepath, 'QuestieDB.objectData = [[')

    objects: dict[int, dict] = {}
    for obj_id, arr in _iter_entries(body):
        spawns_dict = _extract_spawns(arr.get(4))
        coords_tuples = [(c[3], c[1], c[2]) for c in spawns_dict]
        objects[obj_id] = {
            'name': arr.get(1) or '',
            'coords': coords_tuples,
            'questStarts': flatten_ids(arr.get(2)),
            'questEnds': flatten_ids(arr.get(3)),
        }
    print(f'  ✓ {len(objects)} objects loaded')
    return objects


# ---------------------------------------------------------------------------
# Item DB
# ---------------------------------------------------------------------------
# itemKeys: 1=name, 2=npcDrops, 3=objectDrops, 5=startQuest, 14=vendors

def parse_item_db(filepath: str) -> dict[int, dict]:
    """Items have no coords of their own — drop locations are resolved by
    following npcDrops / objectDrops / vendors into the NPC and object DBs.
    """
    print(f'  parse Questie item DB ({os.path.getsize(filepath)//1024} KB)...')
    body = _read_questie_table(filepath, 'QuestieDB.itemData = [[')

    items: dict[int, dict] = {}
    for item_id, arr in _iter_entries(body):
        items[item_id] = {
            'name':        arr.get(1) or '',
            'npcDrops':    flatten_ids(arr.get(2)),
            'objectDrops': flatten_ids(arr.get(3)),
            'vendors':     flatten_ids(arr.get(14)),
        }
    print(f'  ✓ {len(items)} items loaded')
    return items


# ---------------------------------------------------------------------------
# Spawn extraction (used by NPC + object DB)
# ---------------------------------------------------------------------------

def _extract_spawns(spawns_raw: Any) -> list[dict]:
    """Convert Questie's `spawns` field {[zoneID] = {{x, y}, ...}} into a
    flat list of dicts `{1: x, 2: y, 3: zone}`. Sentinel coords (e.g.
    `(-1, -1)` used for instance NPCs) are filtered out."""
    out: list[dict] = []
    if not isinstance(spawns_raw, dict):
        return out
    for zone_id, zone_spawns in spawns_raw.items():
        if not isinstance(zone_spawns, (dict, list)):
            continue
        pairs = list(zone_spawns.values()) if isinstance(zone_spawns, dict) else zone_spawns
        for pair in pairs:
            if isinstance(pair, dict):
                x, y = pair.get(1), pair.get(2)
            elif isinstance(pair, list) and len(pair) >= 2:
                x, y = pair[0], pair[1]
            else:
                continue
            if x is None or y is None:
                continue
            try:
                fx, fy = float(x), float(y)
            except (TypeError, ValueError):
                continue
            if not (0.0 < fx < 100.0 and 0.0 < fy < 100.0):
                continue  # sentinel or out-of-bounds
            out.append({1: fx, 2: fy, 3: int(zone_id)})
    return out
