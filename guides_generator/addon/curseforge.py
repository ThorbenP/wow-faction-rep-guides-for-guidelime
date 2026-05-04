"""Bundle-level documents for the CurseForge umbrella project.

CurseForge moderation rejects multiple similar projects from the same
author ("Fair Play" rule in their moderation policies), so the 30 rep
guides ship as one umbrella project rather than 30 separate ones. This
module builds the two markdown documents that pair with the bundled
zip:

- `build_bundle_readme` — `README.md` written into the zip root, so a
  player who downloads the bundle gets a one-stop install guide and a
  pointer to the per-faction folders for the details.
- `build_curseforge_description` — paste-ready markdown for the project
  page on CurseForge. Listed by faction group so the page mirrors the
  in-game addon list.
- `write_curseforge_description` — drops the project-page text next to
  the bundle zip in `dist/<expansion>/`.
"""
from __future__ import annotations

import os

from ..constants import (
    AUTHOR, DIST_DIR, FACTION_GROUPS, FACTION_NAMES, INTERFACE_VERSION,
    REPO_URL,
)
from .expansions import EXPANSION_ADDON_FOLDER, EXPANSION_LABEL
from .names import addon_name_for_faction
from .zipper import BUNDLE_PREFIX


CURSEFORGE_DESCRIPTION_FILENAME = 'CURSEFORGE_DESCRIPTION.md'

SUPPORT_LINK = 'https://buymeacoffee.com/thpi'


def _bundled_factions(expansion: str) -> list[tuple[str, list[int]]]:
    """Return `(group_label, [faction_id, ...])` pairs in display order,
    keeping only the groups relevant for `expansion`. Groups labelled
    `TBC -` are skipped on era; `Classic -` groups appear on both since
    those factions exist on TBC too. Groups that end up empty are
    dropped."""
    keep: list[tuple[str, list[int]]] = []
    for label, ids in FACTION_GROUPS:
        if expansion == 'era' and label.startswith('TBC -'):
            continue
        members = [fid for fid in ids if fid in FACTION_NAMES]
        if members:
            keep.append((label, members))
    return keep


def _faction_table(expansion: str) -> list[str]:
    """Render the bundled factions as a markdown table grouped by faction
    group. One row per faction with its in-game addon folder name."""
    out: list[str] = []
    for label, ids in _bundled_factions(expansion):
        out.append(f'### {label}')
        out.append('')
        out.append('| Faction | Addon folder |')
        out.append('|---|---|')
        for fid in ids:
            fname = FACTION_NAMES[fid]
            out.append(f'| {fname} | `{addon_name_for_faction(fname)}` |')
        out.append('')
    return out


def build_bundle_readme(expansion: str, version: str) -> str:
    """README that lands at the zip root — explains what the bundle is,
    how to install, and how to enable only the factions you want."""
    expansion_label = EXPANSION_LABEL.get(expansion, expansion.upper())
    interface = INTERFACE_VERSION[expansion]
    addons_folder = EXPANSION_ADDON_FOLDER.get(expansion, '_classic_')
    n_factions = sum(len(ids) for _, ids in _bundled_factions(expansion))

    lines = [
        f"# Guidelime {AUTHOR} - Reputation Farm Guides ({expansion_label})",
        '',
        f'Bundle of **{n_factions} GuideLime sub-addons**, one per WoW '
        f'reputation faction available on **{expansion_label}** '
        f'(Interface `{interface}`). Bundle version **v{version}**.',
        '',
        '## What is in this archive',
        '',
        'Each top-level folder is a standalone GuideLime sub-addon for one'
        ' faction. The bundle exists to keep the project as a single'
        ' CurseForge upload — once installed, every folder behaves like an'
        ' independent addon, with its own toggle in the WoW AddOns list.',
        '',
        '## Installation',
        '',
        '**Prerequisite**: make sure'
        ' [GuideLime](https://www.curseforge.com/wow/addons/guidelime)'
        ' is installed and enabled — every folder in this bundle is a'
        ' GuideLime sub-addon and depends on it.',
        '',
        '### Recommended: CurseForge desktop app',
        '',
        'The CurseForge app understands multi-folder bundles natively. Install'
        ' via the app and every faction guide lands in the right place — no'
        ' manual file moving required.',
        '',
        '### Manual install (downloaded zip)',
        '',
        'When you extract the zip, your unzipper will usually create a wrapper'
        f' folder named like `{BUNDLE_PREFIX}-{expansion}-v{version}/`'
        ' containing this `README.md` and the per-faction addon folders. The'
        ' wrapper folder is **not** the addon — WoW only sees addons that sit'
        f' directly inside `Interface/AddOns/`.',
        '',
        'Open the wrapper folder and copy **the addon folders inside it**'
        f' (each named `Guidelime_{AUTHOR}_<Faction>RepGuide`) into:',
        '',
        f'`World of Warcraft/{addons_folder}/Interface/AddOns/`',
        '',
        'Do **not** copy the wrapper folder itself or this `README.md`. After'
        ' copying you should see something like:',
        '',
        '```',
        'Interface/AddOns/',
        '├── Guidelime/                                 ← the parent addon',
        f'├── Guidelime_{AUTHOR}_DarnassusRepGuide/         ✅',
        f'├── Guidelime_{AUTHOR}_OrgrimmarRepGuide/         ✅',
        '└── ...',
        '',
        'NOT:',
        '',
        'Interface/AddOns/',
        f'└── {BUNDLE_PREFIX}-{expansion}-v{version}/    ❌ extra layer, WoW',
        f'    ├── Guidelime_{AUTHOR}_DarnassusRepGuide/         won\'t load anything',
        '    └── ...',
        '```',
        '',
        '### After install',
        '',
        '1. Open the WoW AddOns screen and enable **only the factions you'
        ' plan to farm**. Disabled folders never load, so the GuideLime guide'
        ' list stays clean.',
        '2. Launch WoW, open `/guidelime`, pick the faction guide and the zone'
        ' sub-guide that matches your level.',
        '',
        '## Bundled factions',
        '',
        'Each folder ships with its own README, CHANGELOG and LICENSE so it'
        ' stays self-contained if you copy a single folder somewhere else.',
        '',
        *_faction_table(expansion),
        '## Notes',
        '',
        '- **Auto-generated**: every guide is produced programmatically from'
        ' the [Questie](https://github.com/Questie/Questie) database rather'
        ' than written by hand. Coverage is broad and consistent, but'
        ' individual quests can occasionally have an odd waypoint or a'
        ' sub-optimal route.',
        f'- **Source code & bug reports**: <{REPO_URL}>',
        f'- **Support the project (optional)**: ☕ <{SUPPORT_LINK}>',
        '',
        '## License',
        '',
        'Each addon folder bundles its own GPL-3.0 LICENSE. The full text is'
        ' also at <https://www.gnu.org/licenses/gpl-3.0.html>. GPL-3.0 is'
        ' chosen so the addons stay license-compatible with **GuideLime**'
        ' (GPL-2.0-or-later).',
        '',
    ]
    return '\n'.join(lines)


def build_curseforge_description(expansion: str, version: str) -> str:
    """Paste-ready markdown for the CurseForge project page.

    One per expansion bundle — paste into the project description on
    CurseForge, or merge multiple expansion descriptions if a single
    project page covers more than one client version.
    """
    expansion_label = EXPANSION_LABEL.get(expansion, expansion.upper())
    interface = INTERFACE_VERSION[expansion]
    n_factions = sum(len(ids) for _, ids in _bundled_factions(expansion))

    lines = [
        f"# Guidelime {AUTHOR} - Reputation Farm Guides",
        '',
        f'A bundle of **{n_factions} reputation farming guides** for '
        f'**{expansion_label}**, delivered as **GuideLime** sub-addons. '
        f'Every faction is its own folder inside the download — install the '
        f'archive once, then enable only the factions you actually farm.',
        '',
        f'Bundle version **v{version}** · Interface `{interface}`.',
        '',
        '## Why one bundle?',
        '',
        'Every faction is a self-contained GuideLime sub-addon, but they all '
        'live in the same zip and are released under the same project so the '
        'page stays a single place to look for updates. Inside the WoW '
        'AddOns screen they remain individually toggleable: only enabled '
        "factions load, and only their guides appear in GuideLime's list — "
        'so disabling Sporeggar and Ogri\'la (for instance) keeps your guide '
        'feed clean if you only farm capitals.',
        '',
        '## Features',
        '',
        '- **Coverage**: every rep-granting quest for every faction listed'
        ' below, plus the prerequisite chain quests needed to unlock them.',
        '- **Routing**: a multistart pipeline (K=96 randomized rebuilds, ILS'
        ' escape) followed by a deep refinement chain (2-opt, or-opt, 3-opt,'
        ' defragmentation, entry-level Held-Karp, stop-level 2-opt and'
        ' or-opt, plus a final stop-level Held-Karp DP that finds the'
        ' provably-optimal stop ordering for sub-guides up to 30 stops).',
        '- **Per-zone sub-guides**: every faction guide is split into one'
        ' sub-guide per zone, each labelled with its level range and'
        ' estimated rep yield in the title.',
        '- **Map waypoints**: `[G x,y zone]` markers for every pickup,'
        ' objective and turn-in.',
        '- **Race / class filtering**: restrictions are emitted as native'
        ' GuideLime tags, so the same addon serves every applicable character'
        ' without manual editing.',
        '- **Cross-zone chains**: extracted into a "Complex" section at the'
        ' end of each zone, so the in-zone path stays clean.',
        '',
        '## Installation',
        '',
        '1. Install [GuideLime](https://www.curseforge.com/wow/addons/guidelime).',
        '2. Drop the contents of this zip into your `Interface/AddOns/`'
        ' directory — every top-level folder is a standalone GuideLime'
        ' sub-addon.',
        '3. Enable only the factions you intend to farm in the WoW AddOns'
        ' screen. Anything you leave disabled never loads.',
        '4. Open `/guidelime`, pick the faction guide, then the zone'
        ' sub-guide that matches your level.',
        '',
        '## Bundled factions',
        '',
        *_faction_table(expansion),
        '## A note on the guide content',
        '',
        'These guides are produced **programmatically** from the'
        ' [Questie](https://github.com/Questie/Questie) database, not written'
        ' by hand. Coverage is broad and consistent, but individual quests'
        ' can occasionally have an odd waypoint or a sub-optimal route.'
        f' Bug reports go to <{REPO_URL}/issues> — patches very welcome.',
        '',
        '## Credits',
        '',
        '- **GuideLime** by *borick* — the framework that makes all of this'
        ' possible.',
        '- **Questie** — quest, NPC, object and rep-reward database.',
        f'- This guide bundle is published by **{AUTHOR}** and is not'
        ' affiliated with Blizzard, GuideLime or Questie.',
        '',
        '## Support the project',
        '',
        'If these guides save you time and you want to say thanks, you can'
        ' buy me a coffee — entirely optional, all guides stay free either'
        ' way.',
        '',
        f'- ☕ <{SUPPORT_LINK}>',
        '',
        '## License',
        '',
        'Released under the **GNU General Public License v3.0 or later**'
        ' (GPL-3.0-or-later). Each addon folder ships with its own LICENSE'
        f' file. Source code: <{REPO_URL}>.',
        '',
    ]
    return '\n'.join(lines)


def write_curseforge_description(expansion: str, version: str) -> str:
    """Write the CurseForge project-page markdown to
    `<DIST_DIR>/<expansion>/CURSEFORGE_DESCRIPTION.md` and return the
    written path."""
    dist_root = os.path.join(os.path.abspath(DIST_DIR), expansion)
    os.makedirs(dist_root, exist_ok=True)
    out_path = os.path.join(dist_root, CURSEFORGE_DESCRIPTION_FILENAME)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(build_curseforge_description(expansion, version))
    return out_path
