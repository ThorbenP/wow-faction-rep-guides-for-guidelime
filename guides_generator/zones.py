"""Per-quest zone assignment and sub-guide bucketing (natural vs cleanup)."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .constants import CITY_ZONES, TIER_FIT_TOLERANCE, ZONE_LEVEL_TIER, ZONE_MAP

ZoneTier = tuple[int, int]


def get_pickup_zone(q: dict) -> Optional[int]:
    pc = q.get('pickup_coords')
    return pc[0] if pc and pc[0] else None


def get_turnin_zone(q: dict) -> Optional[int]:
    tc = q.get('turnin_coords')
    return tc[0] if tc and tc[0] else None


def assign_primary_zone(q: dict) -> int:
    """Pick the zone a quest belongs to: pickup, then turnin, then zoneOrSort.

    Item-drop bridge quests have no pickup NPC (`pickup_coords` is None) — for
    those we fall back to the turnin zone, otherwise they would never end up
    in any bucket and GuideLime would hide their dependent rep-quests because
    the prereq is not in the same sub-guide.
    """
    pz = get_pickup_zone(q)
    if pz and pz in ZONE_MAP:
        return pz
    tz = get_turnin_zone(q)
    if tz and tz in ZONE_MAP:
        return tz
    z = q.get('zoneOrSort', 0)
    if z and z > 0 and z in ZONE_MAP:
        return z
    return 0


def is_self_contained(q: dict) -> bool:
    """True if pickup and turnin happen in the same zone."""
    pz, tz = get_pickup_zone(q), get_turnin_zone(q)
    return pz is not None and tz is not None and pz == tz


def get_zone_tier(zone_id: int) -> Optional[ZoneTier]:
    """(min, max) level range of a zone's natural tier, or None for cities."""
    if zone_id in CITY_ZONES:
        return None
    return ZONE_LEVEL_TIER.get(zone_id)


def is_tier_fit(quest: dict, tier: Optional[ZoneTier]) -> bool:
    """True if the quest's level lies within the tier's range plus tolerance."""
    if tier is None:
        return True
    lvl = quest.get('level', 0)
    if lvl <= 0:
        return True
    lmin, lmax = tier
    return (lmin - TIER_FIT_TOLERANCE) <= lvl <= (lmax + TIER_FIT_TOLERANCE)


def group_by_zone_and_tier(quests: list[dict]) -> dict[tuple[int, str], list[dict]]:
    """Bucket quests by (zone_id, 'natural' | 'cleanup').

    City zones and unmapped zones are always 'natural'. After the initial
    tier-based bucketing, a chain-coalescing pass merges quests whose
    prerequisite landed in a different bucket of the same zone — GuideLime
    hides steps whose prereq is not present in the same sub-guide, so a
    chain split across natural and cleanup buckets would render incomplete.
    """
    by_bucket: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for q in quests:
        z = assign_primary_zone(q)
        if not z:
            continue
        tier = get_zone_tier(z)
        bucket = 'natural' if is_tier_fit(q, tier) else 'cleanup'
        by_bucket[(z, bucket)].append(q)

    return _coalesce_chain_buckets(by_bucket, quests)


def _coalesce_chain_buckets(
    by_bucket: dict[tuple[int, str], list[dict]],
    quests: list[dict],
) -> dict[tuple[int, str], list[dict]]:
    """Move quests whose prereq sits in a different bucket of the same zone
    into the prereq's bucket. Iterates until fixpoint."""
    by_id = {q['id']: q for q in quests}
    quest_key: dict[int, tuple[int, str]] = {}
    for key, qs in by_bucket.items():
        for q in qs:
            quest_key[q['id']] = key

    changed = True
    while changed:
        changed = False
        for qid, key in list(quest_key.items()):
            zone, _bucket = key
            q = by_id.get(qid)
            if q is None:
                continue
            for pid in (q.get('pre') or []) + (q.get('preg') or []):
                pkey = quest_key.get(pid)
                if pkey and pkey[0] == zone and pkey != key:
                    quest_key[qid] = pkey
                    changed = True
                    break

    new_buckets: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for qid, key in quest_key.items():
        new_buckets[key].append(by_id[qid])
    return new_buckets
