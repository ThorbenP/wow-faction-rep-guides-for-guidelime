"""Top-level guide assembly: header + one sub-guide per (zone, bucket).

Cross-zone (complex) chains are attributed to their entry zone and emitted
as a sub-section at the END of that zone's sub-guide — inside the same
`Guidelime.registerGuide(...)` block. So the complex part stays with the
zone where the chain begins, instead of being a global "Complex" sub-guide
at the end. Components whose entry zone has no normal sub-guide for this
faction fall through to a global Complex fallback at the very end.
"""
from __future__ import annotations

from typing import Optional

from ..constants import ALLIANCE_FACTIONS, HORDE_FACTIONS
from ..quests import attribute_complex_to_zones
from ..zones import get_zone_tier, group_by_zone_and_tier
from .emitter import GuideEmitter
from .header import emit_header
from .sub_guide import emit_complex_sub_guide, emit_sub_guide


def generate_guide(
    quests: list[dict],
    faction_name: str,
    expansion: str,
    faction_id: int,
    npc_db: Optional[dict] = None,
    complex_quests: Optional[list[dict]] = None,
) -> tuple[str, dict]:
    """Build the full GuideLime Lua source plus a stats dict.

    Returns:
        (guide_text, stats) where stats is
        `{'totals': {...per-faction counts...},
          'sub_guides': [{...per-sub-guide counts...}]}`.
    """
    side = _faction_side(faction_id)
    by_bucket = group_by_zone_and_tier(quests)
    bucket_order = _sort_buckets(by_bucket)

    complex_quests = complex_quests or []
    complex_by_zone = (
        attribute_complex_to_zones(complex_quests) if complex_quests else {}
    )

    # Stats: count quests that didn't end up in any bucket (zone unknown,
    # e.g. battleground zones not present in ZONE_MAP).
    bucketed_ids = {q['id'] for qs in by_bucket.values() for q in qs}
    dropped_quests = [q for q in quests if q['id'] not in bucketed_ids]

    stats: dict = {
        'totals': {
            'rep_quests': sum(1 for q in quests + complex_quests if not q.get('is_bridge')),
            'bridge_quests': sum(1 for q in quests + complex_quests if q.get('is_bridge')),
            'total_input': len(quests) + len(complex_quests),
            'in_kept': len(quests),
            'in_complex': len(complex_quests),
            'in_buckets': len(bucketed_ids),
            'dropped_no_zone': len(dropped_quests),
            'dropped_quests': [(q['id'], q['name']) for q in dropped_quests],
        },
        'sub_guides': [],
    }

    total_count = len(quests) + len(complex_quests)
    out: list[str] = emit_header(
        faction_name, expansion, total_count, bucket_order, by_bucket,
        complex_by_zone=complex_by_zone,
    )

    # For each zone, the first bucket (natural preferred, otherwise
    # cleanup) gets the complex section appended. Each complex component
    # therefore lands in exactly one sub-guide.
    complex_target_key: dict[int, tuple[int, str]] = {}
    for key in bucket_order:
        zone_id, _bucket = key
        if zone_id in complex_by_zone and zone_id not in complex_target_key:
            complex_target_key[zone_id] = key

    for key in bucket_order:
        zone_quests = by_bucket[key]
        if not zone_quests:
            continue
        zone_id, bucket = key
        complex_for_zone = (
            complex_by_zone[zone_id]
            if complex_target_key.get(zone_id) == key else []
        )
        emitter = GuideEmitter(out, npc_db=npc_db, guide_side=side)
        sg_stats = emit_sub_guide(
            out, emitter, key, zone_quests, faction_name, side,
            complex_quests=complex_for_zone,
        )
        stats['sub_guides'].append(sg_stats)

    # Complex components without an assigned zone (no bucket present, or
    # zone-id 0 because no pickup coords) fall into a global complex
    # sub-guide at the end.
    leftover: list[dict] = []
    for zone_id, qs in complex_by_zone.items():
        if zone_id not in complex_target_key:
            leftover.extend(qs)

    if leftover:
        emitter = GuideEmitter(out, npc_db=npc_db, guide_side=side)
        sg_stats = emit_complex_sub_guide(out, emitter, leftover, faction_name, side)
        stats['sub_guides'].append(sg_stats)

    return '\n'.join(out), stats


def _faction_side(faction_id: int) -> Optional[str]:
    if faction_id in ALLIANCE_FACTIONS:
        return 'Alliance'
    if faction_id in HORDE_FACTIONS:
        return 'Horde'
    return None


def _sort_buckets(by_bucket: dict) -> list[tuple[int, str]]:
    """Order sub-guides in the addon: natural-tier zones come in level
    order; cleanup buckets and city-zones use the average quest level."""
    def avg_lvl(qs: list[dict]) -> float:
        lvls = [q['level'] for q in qs if q['level'] > 0]
        return sum(lvls) / len(lvls) if lvls else 99.0

    def key_func(key: tuple[int, str]) -> tuple:
        zone_id, bucket = key
        qs = by_bucket[key]
        tier = get_zone_tier(zone_id)
        if tier and bucket == 'natural':
            return (tier[0], tier[1], zone_id, 0)
        a = avg_lvl(qs)
        return (a, a, zone_id, 1 if bucket == 'cleanup' else 0)

    return sorted(by_bucket.keys(), key=key_func)
