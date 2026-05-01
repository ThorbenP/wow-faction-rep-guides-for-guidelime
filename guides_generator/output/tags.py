"""Race/class restriction tag — emitted next to the quest tag to hide steps
from non-matching characters at runtime."""
from __future__ import annotations

from typing import Optional

from ..quests import decode_classes, decode_races


def race_class_tag(q: dict, guide_side: Optional[str] = None) -> str:
    """Build the `[A race/class,...]` tag that hides a step for non-matching
    characters. Suppresses a redundant `Alliance` / `Horde` part when the
    sub-guide is already restricted via `[GA Alliance]` / `[GA Horde]`.
    """
    races = decode_races(q['race'])
    classes = decode_classes(q['class'])
    parts: list[str] = []
    if races:
        if not (guide_side and races == [guide_side]):
            parts.extend(races)
    if classes:
        parts.extend(classes)
    return f'[A {",".join(parts)}]' if parts else ''
