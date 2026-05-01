"""File-header comment block at the top of each generated `<addon>.lua`.

Shows quest count, total rep, and a top-5 zone-by-rep table. The complex
quests are credited to the zone they will be appended to, so the table
reflects the actual sub-guide layout the player sees in-game.
"""
from __future__ import annotations

from typing import Optional

from ..constants import ZONE_MAP
from .sanitize import safe_text


def emit_header(
    faction_name: str, expansion: str, n_quests: int, buckets: list,
    by_bucket: dict, complex_by_zone: Optional[dict] = None,
) -> list[str]:
    complex_by_zone = complex_by_zone or {}
    total_rep = sum(sum(q['rep'] for q in qs) for qs in by_bucket.values())
    total_rep += sum(sum(q['rep'] for q in qs) for qs in complex_by_zone.values())

    target_key: dict[int, tuple[int, str]] = {}
    for key in buckets:
        zid, _ = key
        if zid in complex_by_zone and zid not in target_key:
            target_key[zid] = key

    bucket_reps = []
    for key, qs in by_bucket.items():
        zone_id, bucket = key
        zone_name = ZONE_MAP.get(zone_id, f'Zone-{zone_id}')
        label = f'{zone_name} (Cleanup)' if bucket == 'cleanup' else zone_name
        rep = sum(q['rep'] for q in qs)
        if target_key.get(zone_id) == key:
            rep += sum(q['rep'] for q in complex_by_zone[zone_id])
        bucket_reps.append((label, rep))
    leftover_rep = sum(
        sum(q['rep'] for q in qs)
        for zid, qs in complex_by_zone.items() if zid not in target_key
    )
    if leftover_rep:
        bucket_reps.append(('Complex', leftover_rep))
    bucket_reps.sort(key=lambda x: -x[1])
    top5 = bucket_reps[:5]

    lines = [
        f'-- {safe_text(faction_name)} reputation farm guide ({expansion.upper()})',
        f'-- {n_quests} quests in {len(buckets)} sub-guides -- total ~{total_rep} rep.',
        '--',
        '-- Top zones by rep:',
    ]
    for label, rep in top5:
        lines.append(f'--   {safe_text(label):<35} +{rep} rep')
    lines.extend([
        '--',
        '-- Race/class restrictions are emitted as [A ...] tags -- GuideLime hides',
        '-- non-matching steps at runtime.',
        '-- Routing: cluster discovery + on-the-way absorption + 2-opt refinement.',
        '',
    ])
    return lines
