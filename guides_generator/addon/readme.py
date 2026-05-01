"""Per-addon README.md — faction- and expansion-specific.

Mirrors the CurseForge project description but narrows the scope to a
single faction and game version. Carries the same support / repo links
so a player who installs only the addon folder still has them on hand.
"""
from __future__ import annotations

from ..constants import AUTHOR, INTERFACE_VERSION, REPO_URL
from .expansions import EXPANSION_ADDON_FOLDER, EXPANSION_LABEL


def build_readme(
    addon_name: str, faction_name: str, expansion: str, version: str,
) -> str:
    expansion_label = EXPANSION_LABEL.get(expansion, expansion.upper())
    interface = INTERFACE_VERSION[expansion]
    addons_folder = EXPANSION_ADDON_FOLDER.get(expansion, '_classic_')

    lines = [
        f'# {addon_name}',
        '',
        f'In-game reputation farming guide for **{faction_name}** on '
        f'**{expansion_label}**, delivered as a **GuideLime** sub-addon.',
        '',
        '## Support the project',
        '',
        "If these guides save you time and you'd like to say thanks, you can buy me a",
        'coffee — entirely optional, all guides stay free either way.',
        '',
        '- ☕ **Buy me a coffee**: <https://buymeacoffee.com/thpi>',
        '',
        '## Addon info',
        '',
        f'- **Faction**: {faction_name}',
        f'- **Game version**: {expansion_label} (Interface `{interface}`)',
        f'- **Addon version**: {version}',
        f'- **Author**: {AUTHOR}',
        f'- **Repository**: <{REPO_URL}>',
        '',
        '## Requirements',
        '',
        '- [GuideLime](https://www.curseforge.com/wow/addons/guidelime) must be',
        f"  installed and enabled. This addon registers itself as a sub-guide and",
        "  shows up under GuideLime's faction category in-game.",
        '',
        '## What this addon contains',
        '',
        f'A complete, routed walkthrough of every rep-granting quest for '
        f'**{faction_name}**, plus the prerequisite chain quests needed to '
        f'unlock them. The guide is split per zone, with a level range and '
        f'an estimated rep yield per zone, e.g. `Ashenvale (Eff. 65, +10350 rep)`.',
        '',
        '- Map waypoints (`[G x,y zone]`) for every pickup, objective and turn-in.',
        '- Cross-zone chains live in a separate "Complex" section at the end of',
        "  each zone, so the in-zone path stays clean.",
        '- Race / class restrictions are emitted as native GuideLime tags, so the',
        '  same addon serves every applicable character.',
        '',
        '## Installation',
        '',
        '1. Make sure **GuideLime** is installed and enabled.',
        f'2. Copy the `{addon_name}` folder into your',
        f'   `World of Warcraft/{addons_folder}/Interface/AddOns/` directory.',
        f'3. Launch WoW. The guide appears inside GuideLime under '
        f'*{faction_name} Rep Farm*.',
        '',
        '## Usage',
        '',
        '1. Open GuideLime in-game (`/guidelime`).',
        f'2. Pick the *{faction_name} Rep Farm* guide.',
        '3. Choose a zone sub-guide that matches your level. Each one shows its',
        '   level range and estimated rep yield in the title.',
        '4. Follow the on-screen waypoints. GuideLime hides steps that do not',
        '   apply to your race / class automatically.',
        '',
        '## A note on the guide content',
        '',
        'This guide is produced **programmatically** from the',
        '[Questie](https://github.com/Questie/Questie) database rather than',
        'written by hand. Coverage is broad and consistent, but individual',
        'quests can occasionally have an odd waypoint, a missing objective',
        'coordinate, or a sub-optimal route.',
        '',
        f'Source and bug reports: <{REPO_URL}/issues>',
        '',
        '## Credits',
        '',
        '- **GuideLime** by *borick* — the framework that makes all of this possible.',
        '- **Questie** — quest, NPC, object and rep-reward database.',
        '- This guide is published by **ThPi** and is not affiliated with',
        '  Blizzard, GuideLime or Questie.',
        '',
        '## License',
        '',
        'See the project repository for licensing terms.',
        '',
    ]
    return '\n'.join(lines)
