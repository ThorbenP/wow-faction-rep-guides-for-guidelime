"""Look up pickup / turnin coords through the NPC, object, and item DBs.

Quests carry references like `start_npcs`, `start_objects`, `start_items` —
this module follows the cascade NPC -> Object -> Item-drop until it hits a
real spawn coord or gives up.

`attach_coords` mutates each quest in-place; later stages of the pipeline
read `q['pickup_coords']`, `q['turnin_coords']`, `q['objective_coords']`.
"""
from __future__ import annotations

from typing import Optional

from ..constants import DUNGEON_BOSS_NPCS, DUNGEON_ENTRANCES, ZONE_MAP
from .geometry import Coord
from .objectives import compute_objective_centroid


# Safety invariant: the dungeon-instance zone IDs must not overlap with the
# open-world zone IDs, otherwise the dungeon-entrance fallback below would
# fire on world NPCs. WoW assigns disjoint zone IDs to dungeons and outdoor
# zones; this assertion guards future additions to either map.
assert not (set(DUNGEON_ENTRANCES) & set(ZONE_MAP)), (
    'DUNGEON_ENTRANCES contains open-world zone IDs! '
    f'Conflict: {set(DUNGEON_ENTRANCES) & set(ZONE_MAP)}'
)


def get_npc_coords(npc_db: dict, npc_id: int) -> Optional[Coord]:
    """Return the NPC's primary spawn point as (zone, x, y), or None.

    Fallback for NPCs without world coordinates: if the NPC lives in a known
    instance (npc.zone matches DUNGEON_ENTRANCES, or npc_id is overridden in
    DUNGEON_BOSS_NPCS), return the dungeon entrance instead. Typically used
    by item-drop bridges whose source item drops from a dungeon boss.
    """
    if not npc_id:
        return None
    npc = npc_db.get(npc_id) or npc_db.get(str(npc_id))
    if not isinstance(npc, dict):
        return None
    coords = npc.get('coords')
    if coords:
        if isinstance(coords, dict):
            coords = list(coords.values())
        if isinstance(coords, list) and coords:
            first = coords[0]
            if isinstance(first, dict):
                return (first.get(3, 0), first.get(1, 0), first.get(2, 0))
            if isinstance(first, list) and len(first) >= 3:
                return (first[2], first[0], first[1])
            if isinstance(first, tuple) and len(first) == 3:
                return first
    # Fallback: dungeon entrance via npc.zone or explicit npc-id override.
    npc_zone = int(npc.get('zone') or 0)
    if npc_zone and npc_zone in DUNGEON_ENTRANCES:
        return DUNGEON_ENTRANCES[npc_zone]
    override_zone = DUNGEON_BOSS_NPCS.get(npc_id)
    if override_zone and override_zone in DUNGEON_ENTRANCES:
        return DUNGEON_ENTRANCES[override_zone]
    return None


def get_object_coords(object_db: dict, obj_id: int) -> Optional[Coord]:
    if not obj_id:
        return None
    obj = object_db.get(obj_id) if object_db else None
    if not obj:
        return None
    coords = obj.get('coords') or []
    if coords:
        return coords[0]  # already a tuple
    return None


def get_item_pickup_coords(
    item_db: dict, npc_db: dict, object_db: dict, item_id: int,
) -> Optional[Coord]:
    """Resolve where a quest-starting item can be obtained.

    Items can drop from NPCs, world objects, or be sold by vendors. The first
    source with usable coordinates wins.
    """
    if not item_id:
        return None
    itm = item_db.get(item_id) if item_db else None
    if not itm:
        return None
    for npc_id in itm.get('npcDrops', []):
        c = get_npc_coords(npc_db, npc_id)
        if c:
            return c
    for npc_id in itm.get('vendors', []):
        c = get_npc_coords(npc_db, npc_id)
        if c:
            return c
    for obj_id in itm.get('objectDrops', []):
        c = get_object_coords(object_db, obj_id)
        if c:
            return c
    return None


def attach_coords(quests: list[dict], npc_db: dict, object_db: dict, item_db: dict) -> None:
    """Mutates each quest in-place: adds pickup_coords, turnin_coords, and
    (if applicable) objective_coords. Resolution cascade: NPC -> Object ->
    Item drop sources.
    """
    for q in quests:
        q['pickup_coords'] = _resolve_pickup(q, npc_db, object_db, item_db)
        q['turnin_coords'] = _resolve_turnin(q, npc_db, object_db)
        if not q.get('pickup_coords'):
            del q['pickup_coords']
        if not q.get('turnin_coords'):
            del q['turnin_coords']
        oc = compute_objective_centroid(q, npc_db, object_db, item_db)
        if oc:
            q['objective_coords'] = oc


def _resolve_pickup(q: dict, npc_db: dict, object_db: dict, item_db: dict) -> Optional[Coord]:
    for npc_id in q.get('start_npcs', []):
        c = get_npc_coords(npc_db, npc_id)
        if c:
            return c
    for obj_id in q.get('start_objects', []):
        c = get_object_coords(object_db, obj_id)
        if c:
            return c
    for itm_id in q.get('start_items', []):
        c = get_item_pickup_coords(item_db, npc_db, object_db, itm_id)
        if c:
            return c
    return None


def _resolve_turnin(q: dict, npc_db: dict, object_db: dict) -> Optional[Coord]:
    for npc_id in q.get('end_npcs', []):
        c = get_npc_coords(npc_db, npc_id)
        if c:
            return c
    for obj_id in q.get('end_objects', []):
        c = get_object_coords(object_db, obj_id)
        if c:
            return c
    return None
