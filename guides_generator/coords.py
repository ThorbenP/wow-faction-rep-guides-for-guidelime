"""Resolve pickup, turnin, and objective coordinates from the Questie DBs."""
from __future__ import annotations

import math
from typing import Optional

from .constants import DUNGEON_BOSS_NPCS, DUNGEON_ENTRANCES, ZONE_MAP


Coord = tuple[int, float, float]  # (zone_id, x, y)
SPAWN_CLUSTER_THRESHOLD = 12.0  # map units, single-link clustering radius


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


def compute_objective_centroid(
    q: dict, npc_db: dict, object_db: dict, item_db: dict,
) -> Optional[Coord]:
    """Centroid of the largest spawn cluster of all quest objectives.

    A mob can spawn in several patches across the same zone; the simple mean
    of all spawns lands in no-man's-land. We cluster them first (single-link
    by SPAWN_CLUSTER_THRESHOLD) and centre on the densest cluster instead.
    Spawns outside the pickup zone are dropped if any in-zone spawns exist.
    """
    spawns = _collect_objective_spawns(q, npc_db, object_db, item_db)
    if not spawns:
        return None

    pickup_coords = q.get('pickup_coords')
    pickup_zone = pickup_coords[0] if pickup_coords else None
    if pickup_zone:
        in_zone = [s for s in spawns if s[0] == pickup_zone]
        if in_zone:
            spawns = in_zone

    clusters = cluster_spawns(spawns, threshold=SPAWN_CLUSTER_THRESHOLD)
    largest = max(clusters, key=len)
    return _centroid(largest)


def _collect_objective_spawns(
    q: dict, npc_db: dict, object_db: dict, item_db: dict,
) -> list[Coord]:
    """Aggregate spawn coords from all quest objectives: creatures, objects,
    and the spawn locations of items mentioned by the objective."""
    spawns: list[Coord] = []
    for cid in q.get('obj_creatures', []):
        _collect_npc_spawns(spawns, npc_db, cid)
    for oid in q.get('obj_objects', []):
        obj = object_db.get(oid) if object_db else None
        if obj:
            spawns.extend(obj.get('coords', []))
    for iid in q.get('obj_items', []):
        itm = item_db.get(iid) if item_db else None
        if not itm:
            continue
        for npc_id in itm.get('npcDrops', []):
            _collect_npc_spawns(spawns, npc_db, npc_id)
        for obj_id in itm.get('objectDrops', []):
            obj = object_db.get(obj_id) if object_db else None
            if obj:
                spawns.extend(obj.get('coords', []))
    return spawns


def _collect_npc_spawns(spawns: list[Coord], npc_db: dict, npc_id: int) -> None:
    npc = npc_db.get(npc_id) or {}
    for c in npc.get('coords', []):
        if isinstance(c, dict):
            spawns.append((c.get(3, 0), c.get(1, 0), c.get(2, 0)))


def cluster_spawns(spawns: list[Coord], threshold: float) -> list[list[Coord]]:
    """Greedy single-link clustering by map distance. Points in the same zone
    are clustered if their distance is below the threshold; points in
    different zones are never merged."""
    clusters: list[list[Coord]] = []
    for p in spawns:
        attached = False
        for c in clusters:
            if any(_close(p, q, threshold) for q in c):
                c.append(p)
                attached = True
                break
        if not attached:
            clusters.append([p])
    return clusters


def _close(a: Coord, b: Coord, threshold: float) -> bool:
    if a[0] != b[0]:
        return False
    return math.hypot(a[1] - b[1], a[2] - b[2]) < threshold


def _centroid(spawns: list[Coord]) -> Coord:
    cz = spawns[0][0]
    cx = sum(s[1] for s in spawns) / len(spawns)
    cy = sum(s[2] for s in spawns) / len(spawns)
    return (cz, cx, cy)
