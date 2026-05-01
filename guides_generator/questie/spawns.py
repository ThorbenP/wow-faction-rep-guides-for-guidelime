"""Extract spawn coordinate lists from Questie's nested spawn tables.

Used by both the NPC and object DB parsers — the format is identical:
`spawns = {[zoneID] = {{x, y}, {x, y}, ...}, ...}`.
"""
from __future__ import annotations

from typing import Any


def extract_spawns(spawns_raw: Any) -> list[dict]:
    """Convert Questie's `spawns` field {[zoneID] = {{x, y}, ...}} into a
    flat list of dicts `{1: x, 2: y, 3: zone}`. Sentinel coords (e.g.
    `(-1, -1)` used for instance NPCs) are filtered out."""
    out: list[dict] = []
    if not isinstance(spawns_raw, dict):
        return out
    for zone_id, zone_spawns in spawns_raw.items():
        if not isinstance(zone_spawns, (dict, list)):
            continue
        pairs = list(zone_spawns.values()) if isinstance(zone_spawns, dict) else zone_spawns
        for pair in pairs:
            if isinstance(pair, dict):
                x, y = pair.get(1), pair.get(2)
            elif isinstance(pair, list) and len(pair) >= 2:
                x, y = pair[0], pair[1]
            else:
                continue
            if x is None or y is None:
                continue
            try:
                fx, fy = float(x), float(y)
            except (TypeError, ValueError):
                continue
            if not (0.0 < fx < 100.0 and 0.0 < fy < 100.0):
                continue  # sentinel or out-of-bounds
            out.append({1: fx, 2: fy, 3: int(zone_id)})
    return out
