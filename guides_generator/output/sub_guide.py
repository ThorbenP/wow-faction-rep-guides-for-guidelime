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
from ..routing import compute_tour_stats, pick_start_position, route_subguide
from ..routing.start import pick_start_candidates
from ..zones import get_zone_tier
from .emitter import GuideEmitter
from .sanitize import safe_text


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

    # Spawn anchor only for natural-tier sub-guides: a player arriving in a
    # starter zone naturally begins at the lowest-level quest. Cleanup
    # buckets are off-tier returns where the player drops in from anywhere,
    # so anchoring would just push the route through an arbitrary corner.
    cluster_radius = ZONE_CLUSTER_RADIUS.get(zone_id, DEFAULT_CLUSTER_RADIUS)
    if bucket == 'natural':
        # Multi-anchor: when several quests share the minimum level,
        # building one tour per candidate and keeping the cheapest is
        # essentially free relative to the multistart pipeline cost,
        # and avoids the alphabetical tie-break baking in a suboptimal
        # spawn point. Most natural-tier sub-guides have 1-3 candidates.
        start_pos, tour, orphans = _pick_best_start(
            zone_quests, cluster_radius,
        )
    else:
        start_pos = None
        tour, orphans = route_subguide(
            zone_quests, start_pos=None, cluster_radius=cluster_radius,
        )
    # Pass start_pos so the initial edge from spawn / pickup of the
    # lowest-level quest contributes to intra_zone_distance — otherwise
    # the report under-counts distance by the start-to-first-stop hop
    # and inflates rep/dist correspondingly.
    normal_pathing = compute_tour_stats(tour, start_pos)
    rep_per_dist = (
        zone_rep / normal_pathing['intra_zone_distance']
        if normal_pathing['intra_zone_distance'] > 0 else 0.0
    )

    safe_display = safe_text(display_name)
    safe_faction = safe_text(faction_name)
    out.append('Guidelime.registerGuide([[')
    out.append(
        f'[N {lvl_min}-{lvl_max} {safe_display} '
        f'(+{total_rep} rep)]'
    )
    desc = (
        f'[D {len(zone_quests)} quests in *{safe_display}*. '
        f'\\\\ ~{zone_rep} rep for *{safe_faction}*.'
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

    emitter.emit_tour(tour, orphans)

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
        'rep_per_dist': rep_per_dist,
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

    tour, orphans = route_subguide(quests)
    pathing = compute_tour_stats(tour)
    emitter.emit_tour(tour, orphans)

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
        'rep_per_dist': 0.0,  # global fallback has no normal section
        'normal_rep': 0,
        'complex_rep': rep_total,
        'normal_pathing': None,
        'complex_pathing': pathing,
    }


def _emit_complex_section(
    out: list[str], emitter: GuideEmitter, quests: list[dict],
) -> dict:
    """Emit the complex section inside an existing zone sub-guide: banner
    + tour. The emitter's location state is reset because the complex
    tour usually starts somewhere different from where the normal tour
    ended.
    """
    out.append('')
    out.append('[OC]Complex quests: chains that start here and lead to other zones.')
    out.append('')

    emitter.reset_location()
    tour, orphans = route_subguide(quests)
    pathing = compute_tour_stats(tour)
    emitter.emit_tour(tour, orphans)
    return {'orphans': len(orphans), 'pathing': pathing}


def _pick_best_start(zone_quests, cluster_radius):
    """Build a tour for each min-level pickup candidate and keep the
    cheapest under `compute_tour_stats(tour, start_pos)`. Falls back to
    the single-anchor build when the candidate list is empty (no quest
    with both a usable pickup and a positive level).

    Returns `(best_start_pos, best_tour, best_orphans)`.
    """
    candidates = pick_start_candidates(zone_quests)
    if not candidates:
        # Same code path as before — no min-level pickup to anchor on.
        tour, orphans = route_subguide(
            zone_quests, start_pos=None, cluster_radius=cluster_radius,
        )
        return None, tour, orphans

    best_cost = float('inf')
    best_start = None
    best_tour: list = []
    best_orphans: list = []
    for start in candidates:
        tour, orphans = route_subguide(
            zone_quests, start_pos=start, cluster_radius=cluster_radius,
        )
        # Use the same cost the report will use, so the choice matches
        # what we actually optimise for.
        stats = compute_tour_stats(tour, start)
        # `intra_zone_distance` is the headline metric. Cross-zone jumps
        # are reported separately and contribute zero distance, so two
        # candidates with identical intra-zone distance but different
        # jump counts both look equally cheap here — fine, the optimiser
        # already meets the player's tradeoff in `_tour_cost` via
        # JUMP_PENALTY.
        cost = stats['intra_zone_distance']
        # Tie-break in favour of fewer orphans, then lower jump count.
        key = (len(orphans), cost, stats['cross_zone_jumps'])
        best_key = (len(best_orphans), best_cost, float('inf'))
        if key < best_key:
            best_cost = cost
            best_start = start
            best_tour = tour
            best_orphans = orphans
    return best_start, best_tour, best_orphans


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
