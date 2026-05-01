"""Parser for Questie's NPC database.

NPC table indices: 1=name, 7=spawns {[zoneID]={{x,y},...}}, 9=primary zoneID.
"""
from __future__ import annotations

import os

from .lua import iter_entries, read_questie_table
from .spawns import extract_spawns


def parse_npc_db(filepath: str) -> dict[int, dict]:
    """Convert into a coords format compatible with `coords.get_npc_coords`:
        npc_id -> {'name': str, 'coords': [{1:x, 2:y, 3:zone}, ...], 'zone': int}
    The `coords` list is sorted so the primary-zone spawn comes first.
    """
    print(f'  parse Questie NPC DB ({os.path.getsize(filepath)//1024} KB)...')
    body = read_questie_table(filepath, 'QuestieDB.npcData = [[')

    npcs: dict[int, dict] = {}
    for npc_id, arr in iter_entries(body):
        name = arr.get(1) or ''
        primary_zone = int(arr.get(9) or 0)
        coords = extract_spawns(arr.get(7))
        if primary_zone and coords:
            coords.sort(key=lambda c: 0 if c[3] == primary_zone else 1)
        npcs[npc_id] = {'name': name, 'coords': coords, 'zone': primary_zone}
    print(f'  ✓ {len(npcs)} NPCs loaded')
    return npcs
