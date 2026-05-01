"""Addon folder/file naming and the human-readable .toc Title.

The folder prefix `Guidelime_<AUTHOR>_` follows GuideLime's sub-addon
convention (e.g. `Guidelime_Sage`) so addons by the same author group
together in the in-game addon list.
"""
from __future__ import annotations

from ..constants import AUTHOR


def addon_name_for_faction(faction_name: str) -> str:
    """Example: `Darnassus` -> `Guidelime_ThPi_DarnassusRepGuide`."""
    return f'Guidelime_{AUTHOR}_{faction_name.replace(" ", "")}RepGuide'


def guide_title_for_faction(faction_name: str) -> str:
    """`Guidelime <AUTHOR> - <Faction> Rep Farm` — Sage convention plus
    author tag, used as the .toc Title and visible in the WoW addon list.
    """
    return f'Guidelime {AUTHOR} - {faction_name} Rep Farm'
