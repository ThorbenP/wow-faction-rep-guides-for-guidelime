"""Parser for Questie's item database.

Item table indices: 1=name, 2=npcDrops, 3=objectDrops, 5=startQuest, 14=vendors.
Items have no coords of their own — drop locations are resolved via the
referenced NPC and object DBs (see `coords.resolve.get_item_pickup_coords`).
"""
from __future__ import annotations

import os

from .lua import flatten_ids, iter_entries, read_questie_table


def parse_item_db(filepath: str) -> dict[int, dict]:
    print(f'  parse Questie item DB ({os.path.getsize(filepath)//1024} KB)...')
    body = read_questie_table(filepath, 'QuestieDB.itemData = [[')

    items: dict[int, dict] = {}
    for item_id, arr in iter_entries(body):
        items[item_id] = {
            'name':        arr.get(1) or '',
            'npcDrops':    flatten_ids(arr.get(2)),
            'objectDrops': flatten_ids(arr.get(3)),
            'vendors':     flatten_ids(arr.get(14)),
        }
    print(f'  ✓ {len(items)} items loaded')
    return items
