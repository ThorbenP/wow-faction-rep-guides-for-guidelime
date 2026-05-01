"""One `Guidelime.registerGuide([[...]])` block per zone bucket.

Two flavours:
- normal sub-guide for an in-zone bucket (`emit_sub_guide`), with an
  optional Complex section appended for cross-zone chains attributed to
  this zone;
- global Complex fallback (`emit_complex_sub_guide`) for components whose
  entry zone has no normal sub-guide for this faction.
"""
from __future__ import annotations

from typing import Optional

from ..constants import (
    AUTHOR, DEFAULT_CLUSTER_RADIUS, ZONE_CLUSTER_RADIUS, ZONE_MAP,
)
from ..routing import compute_tour_stats, route_subguide
from ..zones import get_zone_tier
from .chain_index import build_chain_index, disambiguate_duplicate_names
from .emitter import GuideEmitter
from .sanitize import safe_text
from .score import compute_efficiency_score


def guide_category(faction_name: str) -> str:
    """The GuideLime "category" label that groups sub-guides in the menu —
    e.g. "ThPi's Darnassus Rep Farm Guide".
    """
    return f"{AUTHOR}'s {faction_name} Rep Farm Guide"


def emit_sub_guide(
    out: list[str],
    emitter: GuideEmitter,
    key: tuple[int, str],
    zone_quests: list[dict],
    faction_name: str,
    side: Optional[str],
    complex_quests: Optional[list[dict]] = None,
) -> dict:
    """Emit one full `Guidelime.registerGuide([[...]])` block. Returns the
    stats dict for the quality report.

    If `complex_quests` are given, they are emitted as a second section at
    the end of the same registerGuide block, separated by an
    `[OC]Complex Quests` banner. These are cross-zone chains that start in
    this zone but lead away.
    """
    complex_quests = complex_quests or []
    zone_id, bucket = key
    zone_name = ZONE_MAP.get(zone_id, f'Zone-{zone_id}' if zone_id else 'Unknown zone')
    display_name = f'{zone_name} (Cleanup)' if bucket == 'cleanup' else zone_name

    all_quests_for_levels = zone_quests + complex_quests
    lvl_min, lvl_max = level_range(all_quests_for_levels, zone_id, bucket)
    zone_rep = sum(q['rep'] for q in zone_quests)
    complex_rep = sum(q['rep'] for q in complex_quests)
    total_rep = zone_rep + complex_rep
    category = guide_category(faction_name)

    # Run the routing first — the efficiency score is part of the title.
    cluster_radius = ZONE_CLUSTER_RADIUS.get(zone_id, DEFAULT_CLUSTER_RADIUS)
    chain_list, quest_pos = build_chain_index(zone_quests)
    display_names = disambiguate_duplicate_names(zone_quests)
    tour, orphans = route_subguide(zone_quests, cluster_radius=cluster_radius)
    normal_pathing = compute_tour_stats(tour)
    score = compute_efficiency_score(
        normal_rep=zone_rep,
        normal_distance=normal_pathing['intra_zone_distance'],
        normal_jumps=normal_pathing['cross_zone_jumps'],
        absorption_rate=normal_pathing['absorption_rate'],
        has_normal_quests=bool(zone_quests),
    )

    safe_display = safe_text(display_name)
    safe_faction = safe_text(faction_name)
    out.append('Guidelime.registerGuide([[')
    out.append(
        f'[N {lvl_min}-{lvl_max} {safe_display} '
        f'(Eff. {score}, +{total_rep} rep)]'
    )
    desc = (
        f'[D {len(zone_quests)} quests in *{safe_display}*. '
        f'\\\\ ~{zone_rep} rep for *{safe_faction}*. '
        f'\\\\ Efficiency score: *{score}/100*.'
    )
    if complex_quests:
        desc += (
            f' \\\\ + {len(complex_quests)} complex quests '
            f'(chain leading to other zones, +{complex_rep} rep).'
        )
    desc += ']'
    out.append(desc)
    if side:
        out.append(f'[GA {side}]')
    out.append('')

    if chain_list:
        out.append('[OC]Quest chains in this zone:')
        for label, names in chain_list:
            chain_summary = ' -> '.join(safe_text(n) for n in names[:4])
            if len(names) > 4:
                chain_summary += ' -> ...'
            out.append(f'[OC]  {label}: {chain_summary}')
        out.append('')

    emitter.emit_tour(tour, orphans, display_names, quest_pos)

    complex_stats = None
    if complex_quests:
        complex_stats = _emit_complex_section(out, emitter, complex_quests)

    out.append(f']], "{category}")')
    out.append('')

    return {
        'name': display_name,
        'level_range': (lvl_min, lvl_max),
        'normal_quests': len(zone_quests),
        'complex_quests': len(complex_quests),
        'normal_steps': step_count(zone_quests),
        'complex_steps': step_count(complex_quests) if complex_quests else None,
        'orphans': len(orphans),
        'rep_total': total_rep,
        'efficiency_score': score,
        'normal_rep': zone_rep,
        'complex_rep': complex_rep,
        'normal_pathing': normal_pathing,
        'complex_pathing': complex_stats['pathing'] if complex_stats else None,
    }


def emit_complex_sub_guide(
    out: list[str],
    emitter: GuideEmitter,
    quests: list[dict],
    faction_name: str,
    side: Optional[str],
) -> dict:
    """Fallback global complex sub-guide for cross-zone chains that could
    not be attributed to any normal zone (e.g. their entry zone has no
    sub-guide for this faction). Same tour builder, but stops are spread
    across many zones — clusters tend to stay small.
    """
    levels = [q['level'] for q in quests if q['level'] > 0]
    lvl_min = min(levels) if levels else 1
    lvl_max = max(levels) if levels else 70
    rep_total = sum(q['rep'] for q in quests if not q.get('is_bridge'))
    category = guide_category(faction_name)

    safe_faction = safe_text(faction_name)
    out.append('Guidelime.registerGuide([[')
    out.append(f'[N {lvl_min}-{lvl_max} Complex (+{rep_total} rep)]')
    out.append(
        f'[D Cross-zone quest chains for *{safe_faction}*. \\\\ '
        f'{len(quests)} quests / ~{rep_total} rep -- prerequisites live in other '
        f'zones, listed here separately.]'
    )
    if side:
        out.append(f'[GA {side}]')
    out.append('')

    chain_list, quest_pos = build_chain_index(quests)
    if chain_list:
        out.append('[OC]Quest chains:')
        for label, names in chain_list:
            chain_summary = ' -> '.join(safe_text(n) for n in names[:4])
            if len(names) > 4:
                chain_summary += ' -> ...'
            out.append(f'[OC]  {label}: {chain_summary}')
        out.append('')

    display_names = disambiguate_duplicate_names(quests)
    tour, orphans = route_subguide(quests)
    pathing = compute_tour_stats(tour)
    emitter.emit_tour(tour, orphans, display_names, quest_pos)

    out.append(f']], "{category}")')
    out.append('')
    return {
        'name': 'Complex (global fallback)',
        'level_range': (lvl_min, lvl_max),
        'normal_quests': 0,
        'complex_quests': len(quests),
        'normal_steps': None,
        'complex_steps': step_count(quests),
        'orphans': len(orphans),
        'rep_total': rep_total,
        'efficiency_score': 0,  # global fallback has no normal section
        'normal_rep': 0,
        'complex_rep': rep_total,
        'normal_pathing': None,
        'complex_pathing': pathing,
    }


def _emit_complex_section(
    out: list[str], emitter: GuideEmitter, quests: list[dict],
) -> dict:
    """Emit the complex section inside an existing zone sub-guide: banner
    + own chain index + tour. The emitter's location state is reset
    because the complex tour usually starts somewhere different from
    where the normal tour ended.
    """
    out.append('')
    out.append('[OC]Complex quests: chains that start here and lead to other zones.')
    out.append('')

    chain_list, quest_pos = build_chain_index(quests)
    if chain_list:
        out.append('[OC]Complex chains:')
        for label, names in chain_list:
            chain_summary = ' -> '.join(safe_text(n) for n in names[:4])
            if len(names) > 4:
                chain_summary += ' -> ...'
            out.append(f'[OC]  {label}: {chain_summary}')
        out.append('')

    display_names = disambiguate_duplicate_names(quests)
    emitter.reset_location()
    tour, orphans = route_subguide(quests)
    pathing = compute_tour_stats(tour)
    emitter.emit_tour(tour, orphans, display_names, quest_pos)
    return {'orphans': len(orphans), 'pathing': pathing}


def level_range(quests: list[dict], zone_id: int, bucket: str) -> tuple[int, int]:
    tier = get_zone_tier(zone_id)
    if bucket == 'natural' and tier:
        return tier
    levels = [q['level'] for q in quests if q['level'] > 0]
    return (min(levels) if levels else 1, max(levels) if levels else 70)


def step_count(quests: list[dict]) -> dict:
    """Count expected QA / QC / QT stops in a quest list."""
    qa = sum(1 for q in quests if q.get('pickup_coords'))
    qc = sum(1 for q in quests if q.get('objective_coords'))
    qt = sum(1 for q in quests if q.get('turnin_coords'))
    no_pickup = sum(1 for q in quests if not q.get('pickup_coords') and not q.get('is_bridge'))
    no_turnin = sum(1 for q in quests if not q.get('turnin_coords'))
    return {
        'qa': qa, 'qc': qc, 'qt': qt,
        'total_steps': qa + qc + qt,
        'rep_quests_no_pickup': no_pickup,
        'quests_no_turnin': no_turnin,
    }
