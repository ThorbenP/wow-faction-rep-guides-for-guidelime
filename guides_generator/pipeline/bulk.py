"""Bulk generator — `--all` runs every faction and writes the quality report."""
from __future__ import annotations

import os

from ..addon import read_changelog
from ..constants import ADDONS_DIR, CHANGELOG_DIR, FACTION_NAMES
from ..coords import attach_coords
from ..quests import (
    drop_unreachable_bridge_chains, expand_with_prereq_bridges,
    filter_quests_by_faction,
)
from ..report import write_addon_report, write_global_report
from .console import print_bulk_summary
from .loader import build_and_write, load_quest_db, load_world_dbs


def run_all(expansion: str) -> None:
    print(f'\n=== bulk generator: all factions ({expansion.upper()}) ===\n')

    print('[A/D] load quest DB...')
    quest_db = load_quest_db(expansion)

    print('\n[B/D] load world DBs (NPC / object / item)...')
    npc_db, object_db, item_db = load_world_dbs(expansion)

    version, changelog_text = read_changelog(CHANGELOG_DIR)
    print(f'\n[C/D] filter and write per faction (v{version})...')
    results: list[tuple[str, int, str | None, int, dict | None]] = []
    addons_top = os.path.abspath(ADDONS_DIR)            # parent dir, for report path
    addons_root = os.path.join(addons_top, expansion)   # actual write target
    os.makedirs(addons_root, exist_ok=True)

    faction_ids = sorted(FACTION_NAMES)
    total = len(faction_ids)
    for idx, faction_id in enumerate(faction_ids, start=1):
        fname = FACTION_NAMES[faction_id]
        rep_quests = filter_quests_by_faction(quest_db, faction_id)
        if not rep_quests:
            print(f'  [{idx}/{total}] · {fname} (ID {faction_id}) — no quests, skipped')
            results.append((fname, faction_id, None, 0, None))
            continue
        quests = expand_with_prereq_bridges(rep_quests, quest_db)
        attach_coords(quests, npc_db, object_db, item_db)
        quests, complex_quests = drop_unreachable_bridge_chains(quests)
        addon_path, stats = build_and_write(
            quests, fname, expansion, faction_id, npc_db,
            version=version, changelog_text=changelog_text,
            complex_quests=complex_quests,
        )
        write_addon_report(
            stats, addon_path, fname, faction_id, version, expansion,
        )
        n_total = len(quests) + len(complex_quests)
        n_dropped = stats['totals']['dropped_no_zone']
        flag = f' (! {n_dropped} without zone)' if n_dropped else ''
        print(f'  [{idx}/{total}] ✓ {fname} (ID {faction_id}) — {n_total} quests{flag} -> {os.path.basename(addon_path)}')
        results.append((fname, faction_id, addon_path, n_total, stats))

    print('\n[D/D] bulk run finished.')
    print_bulk_summary(results, addons_root, version)
    global_path = write_global_report(results, addons_top, version, expansion)
    if global_path:
        print(f'global summary: {global_path}')
