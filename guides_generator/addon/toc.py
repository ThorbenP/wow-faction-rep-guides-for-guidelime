"""Build the `<addon>.toc` file content.

The dependency name must match GuideLime's addon folder name exactly —
it is `Guidelime` (lowercase L), not `GuideLime`.
"""
from __future__ import annotations

from ..constants import AUTHOR, INTERFACE_VERSION


def build_toc(
    addon_name: str, guide_title: str, expansion: str, faction_name: str, version: str,
) -> str:
    lines = [
        f'## Interface: {INTERFACE_VERSION[expansion]}',
        f'## Title: {guide_title}',
        f'## Notes: Auto-generated reputation farming guide for {faction_name} ({expansion.upper()}) by {AUTHOR}',
        f'## Author: {AUTHOR}',
        f'## Version: {version}',
        '## Dependencies: Guidelime',
        '## DefaultState: disabled',
        '## LoadOnDemand: 0',
        '## X-Category: Quests',
        '## X-License: GPL-3.0-or-later',
        '',
        f'{addon_name}.lua',
    ]
    return '\n'.join(lines) + '\n'
