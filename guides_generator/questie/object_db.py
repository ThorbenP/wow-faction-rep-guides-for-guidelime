"""Parser for Questie's world-object database.

Object table indices: 1=name, 2=questStarts, 3=questEnds, 4=spawns, 5=zoneID.
"""
from __future__ import annotations

import os

from .lua import flatten_ids, iter_entries, read_questie_table
from .spawns import extract_spawns


def parse_object_db(filepath: str) -> dict[int, dict]:
    """Returns: object_id -> {'name': str, 'coords': [(zone, x, y), ...], ...}.
    Coords are tuples here (NPC DB uses dicts; both formats are handled by
    the coord-resolver)."""
    print(f'  parse Questie object DB ({os.path.getsize(filepath)//1024} KB)...')
    body = read_questie_table(filepath, 'QuestieDB.objectData = [[')

    objects: dict[int, dict] = {}
    for obj_id, arr in iter_entries(body):
        spawns_dict = extract_spawns(arr.get(4))
        coords_tuples = [(c[3], c[1], c[2]) for c in spawns_dict]
        objects[obj_id] = {
            'name': arr.get(1) or '',
            'coords': coords_tuples,
            'questStarts': flatten_ids(arr.get(2)),
            'questEnds': flatten_ids(arr.get(3)),
        }
    print(f'  ✓ {len(objects)} objects loaded')
    return objects
