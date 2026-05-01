"""Shared loaders + the build-and-write step used by both single and bulk runs."""
from __future__ import annotations

import os

from ..addon import addon_name_for_faction, guide_title_for_faction, write_addon
from ..constants import ADDONS_DIR, CACHE_DIR
from ..coords import attach_coords
from ..output import generate_guide
from ..questie import (
    fetch_or_load, parse_item_db, parse_npc_db, parse_object_db, parse_quest_db,
)
from ..quests import expand_with_prereq_bridges, filter_quests_by_faction


def load_quest_db(expansion: str) -> dict:
    print('[1/4] Questie quest database...')
    qdb_file = fetch_or_load('questie', expansion, CACHE_DIR)
    return parse_quest_db(qdb_file)


def load_world_dbs(expansion: str) -> tuple[dict, dict, dict]:
    npc_file = fetch_or_load('questie_npcs', expansion, CACHE_DIR)
    npc_db = parse_npc_db(npc_file)
    obj_file = fetch_or_load('questie_objects', expansion, CACHE_DIR)
    object_db = parse_object_db(obj_file)
    itm_file = fetch_or_load('questie_items', expansion, CACHE_DIR)
    item_db = parse_item_db(itm_file)
    return npc_db, object_db, item_db


def load_and_filter_quests(
    expansion: str, faction_id: int,
) -> tuple[list[dict], dict]:
    """Single-run path: load DB, filter to one faction, expand bridges."""
    quest_db = load_quest_db(expansion)

    print(f'\n[2/4] filter faction {faction_id}...')
    rep_quests = filter_quests_by_faction(quest_db, faction_id)
    print(f'  -> {len(rep_quests)} rep quests, {sum(q["rep"] for q in rep_quests)} rep total')

    quests = expand_with_prereq_bridges(rep_quests, quest_db)
    n_bridges = len(quests) - len(rep_quests)
    if n_bridges:
        print(f'  -> {n_bridges} prerequisite bridges added (rep=0, unblock rep quests)')
    return quests, quest_db


def build_and_write(
    quests: list[dict], fname: str, expansion: str, faction_id: int, npc_db: dict,
    version: str, changelog_text: str,
    complex_quests: list[dict] | None = None,
) -> tuple[str, dict]:
    """Build the guide source and write the addon directory. Returns
    `(absolute_addon_path, stats_dict)`."""
    addon_name = addon_name_for_faction(fname)
    guide_title = guide_title_for_faction(fname)
    guide_text, stats = generate_guide(
        quests, fname, expansion, faction_id, npc_db=npc_db,
        complex_quests=complex_quests,
    )
    addon_dir = os.path.join(os.path.abspath(ADDONS_DIR), expansion, addon_name)
    write_addon(
        addon_dir, addon_name, guide_title, expansion, fname, guide_text,
        version=version, changelog_text=changelog_text,
    )
    return addon_dir, stats
