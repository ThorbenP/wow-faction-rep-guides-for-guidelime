"""Write the finished addon directory (.toc + .lua + CHANGELOG.md + README.md) to disk."""
from __future__ import annotations

import os
import re

from .constants import (
    AUTHOR, FALLBACK_VERSION, INTERFACE_VERSION, REPO_URL,
)

VERSION_FILENAME_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)(?:_.*)?\.md$', re.IGNORECASE)

EXPANSION_LABEL = {
    'era': 'WoW Classic Era / Anniversary',
    'tbc': 'WoW Burning Crusade Classic / TBC Anniversary',
}
EXPANSION_ADDON_FOLDER = {
    'era': '_classic_era_',
    'tbc': '_classic_',
}


def write_addon(
    addon_dir: str,
    addon_name: str,
    guide_title: str,
    expansion: str,
    faction_name: str,
    guide_text: str,
    version: str,
    changelog_text: str,
) -> tuple[str, str, str, str]:
    """Create `addon_dir` and write the four files of an addon:
      <addon_name>.toc — addon metadata (Interface version, dependency on
                        GuideLime, author, etc.)
      <addon_name>.lua — the generated guide source
      CHANGELOG.md     — concatenated history
      README.md        — faction- and expansion-specific player-facing readme

    Returns the (toc_path, lua_path, changelog_path, readme_path) of the
    written files.
    """
    os.makedirs(addon_dir, exist_ok=True)

    lua_path = os.path.join(addon_dir, f'{addon_name}.lua')
    with open(lua_path, 'w', encoding='utf-8') as f:
        f.write(guide_text)

    toc_path = os.path.join(addon_dir, f'{addon_name}.toc')
    with open(toc_path, 'w', encoding='utf-8') as f:
        f.write(_build_toc(addon_name, guide_title, expansion, faction_name, version))

    changelog_path = os.path.join(addon_dir, 'CHANGELOG.md')
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(changelog_text)

    readme_path = os.path.join(addon_dir, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(_build_readme(addon_name, faction_name, expansion, version))

    return toc_path, lua_path, changelog_path, readme_path


def read_changelog(changelog_dir: str) -> tuple[str, str]:
    """Read all `vX.Y.Z[_<slug>].md` files from `changelog_dir` and return
    `(latest_version, concatenated_text)`. Concatenation is reverse
    chronological (newest first). If the directory is empty or missing,
    returns the fallback version with a placeholder text.
    """
    if not os.path.isdir(changelog_dir):
        return FALLBACK_VERSION, '# Changelog\n\nNo entries yet.\n'

    entries: list[tuple[tuple[int, int, int], str]] = []
    for fname in sorted(os.listdir(changelog_dir)):
        m = VERSION_FILENAME_RE.match(fname)
        if not m:
            continue
        vt = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        with open(os.path.join(changelog_dir, fname), 'r', encoding='utf-8') as f:
            entries.append((vt, f.read().strip()))

    if not entries:
        return FALLBACK_VERSION, '# Changelog\n\nNo entries yet.\n'

    entries.sort(key=lambda e: e[0], reverse=True)
    latest_version = '.'.join(str(n) for n in entries[0][0])

    body_parts: list[str] = []
    for i, (_, content) in enumerate(entries):
        body_parts.append(content)
        if i < len(entries) - 1:
            body_parts.append('---')
    body = '\n\n'.join(body_parts)
    return latest_version, f'# Changelog\n\n{body}\n'


def _build_toc(
    addon_name: str, guide_title: str, expansion: str, faction_name: str, version: str,
) -> str:
    """Build the .toc file content. The dependency name must match
    GuideLime's addon folder exactly — it is `Guidelime` (lowercase L).
    """
    lines = [
        f'## Interface: {INTERFACE_VERSION[expansion]}',
        f'## Title: {guide_title}',
        f'## Notes: Auto-generated reputation farming guide for {faction_name} ({expansion.upper()}) by {AUTHOR}',
        f'## Author: {AUTHOR}',
        f'## Version: {version}',
        '## Dependencies: Guidelime',
        '## X-Category: Quests',
        '',
        f'{addon_name}.lua',
    ]
    return '\n'.join(lines) + '\n'


def addon_name_for_faction(faction_name: str) -> str:
    """Build the addon directory/file name. Example:
        `Darnassus` -> `Guidelime_ThPi_DarnassusRepGuide`
    The `Guidelime_<AUTHOR>_` prefix follows GuideLime's sub-addon
    convention (e.g. `Guidelime_Sage`) so addons by the same author group
    together in the addon list.
    """
    return f'Guidelime_{AUTHOR}_{faction_name.replace(" ", "")}RepGuide'


def guide_title_for_faction(faction_name: str) -> str:
    """`Guidelime <AUTHOR> - <Faction> Rep Farm` — Sage convention plus
    author tag, used as the .toc Title and visible in the WoW addon list.
    """
    return f'Guidelime {AUTHOR} - {faction_name} Rep Farm'


def _build_readme(
    addon_name: str, faction_name: str, expansion: str, version: str,
) -> str:
    """Per-addon README.md — faction- and expansion-specific.

    Mirrors the CurseForge project description but narrows the scope to a
    single faction and game version. Carries the same support / repo links
    so a player who installs only the addon folder still has them on hand.
    """
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
        '☕ **Buy me a coffee**: <https://buymeacoffee.com/thpi>',
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
