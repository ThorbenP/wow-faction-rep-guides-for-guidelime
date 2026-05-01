"""Resolve pickup, turnin, and objective coordinates from the Questie DBs.

Public:
    attach_coords            mutate quests in place with *_coords fields
    compute_objective_centroid
    get_npc_coords           single-NPC lookup with dungeon-entrance fallback
    cluster_spawns / centroid    geometric helpers
    Coord                    type alias `(zone_id, x, y)`
"""
from .geometry import Coord, SPAWN_CLUSTER_THRESHOLD, centroid, cluster_spawns
from .objectives import compute_objective_centroid
from .resolve import (
    attach_coords, get_item_pickup_coords, get_npc_coords, get_object_coords,
)

__all__ = [
    'Coord', 'SPAWN_CLUSTER_THRESHOLD', 'attach_coords', 'centroid',
    'cluster_spawns', 'compute_objective_centroid', 'get_item_pickup_coords',
    'get_npc_coords', 'get_object_coords',
]
