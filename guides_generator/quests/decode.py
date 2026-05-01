"""Race / class bitmask decoders.

Race masks have two convenience aliases: the full Alliance mask collapses to
`['Alliance']`, the full Horde mask to `['Horde']` — that is shorter and
matches GuideLime's `[A Alliance]` / `[A Horde]` short forms.
"""
from __future__ import annotations

from ..constants import (
    ALL_CLASSES_MASK, ALL_RACES_MASK, ALLIANCE_MASK, CLASS_FLAGS,
    HORDE_MASK, RACE_FLAGS,
)


def decode_races(mask: int) -> list[str] | None:
    """Bitmask -> list of race names, or `['Alliance']`/`['Horde']` for the
    full-side masks, or `None` for the all-races mask."""
    if not mask or mask == ALL_RACES_MASK:
        return None
    if mask == ALLIANCE_MASK:
        return ['Alliance']
    if mask == HORDE_MASK:
        return ['Horde']
    return [name for bit, name in RACE_FLAGS if mask & bit]


def decode_classes(mask: int) -> list[str] | None:
    """Bitmask -> list of class names, or `None` for the all-classes mask."""
    if not mask or mask == ALL_CLASSES_MASK:
        return None
    return [name for bit, name in CLASS_FLAGS if mask & bit]
