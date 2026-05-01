"""Compute the centroid of a quest's objective spawn locations.

A mob can spawn in several patches across the same zone; the simple mean of
all spawns lands in no-man's-land. We cluster them first (single-link) and
centre on the densest cluster instead. Spawns outside the pickup zone are
dropped if any in-zone spawns exist.
"""
from __future__ import annotations

from typing import Optional

from .geometry import Coord, SPAWN_CLUSTER_THRESHOLD, centroid, cluster_spawns


def compute_objective_centroid(
    q: dict, npc_db: dict, object_db: dict, item_db: dict,
) -> Optional[Coord]:
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
    return centroid(largest)


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
