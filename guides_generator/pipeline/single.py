"""Single-faction generator — interactive or via `--faction`.

Writes the same per-addon `QUALITY_REPORT.md` a bulk run would, so the
same artefact is available for diffing whether you regenerate one
faction or all of them. The slim global `_quality_report.md` is bulk-only
— a one-row summary would not be useful.
"""
from __future__ import annotations

import sys

from ..addon import read_changelog
from ..constants import CHANGELOG_DIR, FACTION_NAMES
from ..coords import attach_coords
from ..prompts import prompt_expansion, prompt_faction
from ..quests import drop_unreachable_bridge_chains
from ..report import write_addon_report
from ..zones import group_by_zone_and_tier
from .console import (
    print_bucket_stats, print_coverage, print_quest_stats, print_summary,
)
from .loader import build_and_write, load_and_filter_quests, load_world_dbs


def run_single(
    faction_id: int | None = None, expansion: str | None = None,
) -> None:
    """Generate the addon for one faction. Without arguments the user is
    prompted; with arguments (e.g. via `--faction`) it runs unattended."""
    if faction_id is None:
        faction_id = prompt_faction()
    if expansion is None:
        expansion = prompt_expansion()

    fname = FACTION_NAMES.get(faction_id, f'Faction-{faction_id}')

    print(f'\n=== {fname} rep generator ({expansion.upper()}) ===\n')

    quests, _ = load_and_filter_quests(expansion, faction_id)
    if not quests:
        print('\n  ! no quests for this faction in this expansion.')
        sys.exit(1)

    npc_db, object_db, item_db = load_world_dbs(expansion)
    attach_coords(quests, npc_db, object_db, item_db)
    quests, complex_quests = drop_unreachable_bridge_chains(quests)
    if complex_quests:
        print(f'  -> {len(complex_quests)} quests moved to complex section '
              f'(bridge chains crossing zones)')
    print_coverage(quests)

    buckets = group_by_zone_and_tier(quests)
    print_bucket_stats(buckets)

    version, changelog_text = read_changelog(CHANGELOG_DIR)
    print(f'  changelog: v{version}')

    print('\n[4/4] writing addon directory...')
    addon_path, stats = build_and_write(
        quests, fname, expansion, faction_id, npc_db,
        version=version, changelog_text=changelog_text,
        complex_quests=complex_quests,
    )
    report_path = write_addon_report(
        stats, addon_path, fname, faction_id, version, expansion,
    )
    print_summary(fname, faction_id, quests, buckets, addon_path, version)
    print_quest_stats(stats)
    print(f'quality report: {report_path}')
