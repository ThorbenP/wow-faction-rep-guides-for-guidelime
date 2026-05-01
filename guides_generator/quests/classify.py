"""Cross-zone classification: split quests into in-zone (kept) vs complex.

Complex quests are emitted into a separate "Complex Quests" sub-section at
the end of the entry-zone's sub-guide. Self-contained sub-trees of a
cross-zone component are extracted back into the kept set so the player
still sees the parts they can do entirely within one zone.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from ..zones import get_pickup_zone, get_turnin_zone


def drop_unreachable_bridge_chains(
    quests: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split quests into (kept, complex) after coordinate attachment.

    `kept` are quests that belong into a normal zone sub-guide. `complex`
    are quests whose chain crosses zone boundaries — they end up in a
    "Complex Quests" section attributed to the entry zone (the zone where
    the chain's first quest can be picked up).

    Cross-zone chains are not dropped wholesale: a self-contained sub-tree
    of a cross-zone component is extracted back into the kept set so the
    player still sees the parts they can do entirely within one zone. For
    example, Q1022 "The Howling Vale" (start + objective + turnin all in
    Ashenvale) is extracted from a chain that later crosses into Darnassus.

    Solo cross-zone quests (no chain partners; pickup zone != turnin zone)
    are also pushed to complex — chained cross-zone tails stay with their
    chain so the visual narrative is not torn apart.
    """
    by_id = {q['id']: q for q in quests}
    components = _connected_components(quests, by_id)

    keep_qids: set[int] = set()
    complex_qids: set[int] = set()
    for comp in components:
        has_bridge = any(q.get('is_bridge') for q in comp)
        if not has_bridge:
            keep_qids.update(q['id'] for q in comp)
            continue
        zones = {get_pickup_zone(q) for q in comp if get_pickup_zone(q) is not None}
        if len(zones) <= 1:
            keep_qids.update(q['id'] for q in comp)
            continue
        # Cross-zone component: extract the in-zone sub-tree, push the rest
        # to the complex set.
        extracted = _extract_in_zone_subset(comp, by_id)
        keep_qids.update(extracted)
        for q in comp:
            if q['id'] not in extracted:
                complex_qids.add(q['id'])

    # Solo cross-zone quests (no chain partner; pickup zone != turnin zone)
    # also belong in the complex section. Chain-integrated cross-zone tails
    # stay in their chain so the chain is not visually fragmented.
    solo_xz = _identify_solo_cross_zone(keep_qids, by_id)
    keep_qids -= solo_xz
    complex_qids |= solo_xz

    kept = [q for q in quests if q['id'] in keep_qids]
    complex_ = [q for q in quests if q['id'] in complex_qids]
    return kept, complex_


def attribute_complex_to_zones(
    complex_quests: list[dict],
) -> dict[int, list[dict]]:
    """Map each complex (cross-zone) connected component to its entry zone.

    The entry zone is the pickup zone of the chain's first quest — quests
    in the component that have no in-component prerequisites. For
    components with multiple entry quests in different zones, the most
    common zone wins; ties are broken by the lowest zone ID. Components
    without any pickup zone fall under key `0`.
    """
    by_id = {q['id']: q for q in complex_quests}
    components = _connected_components(complex_quests, by_id)

    by_zone: dict[int, list[dict]] = defaultdict(list)
    for comp in components:
        comp_ids = {q['id'] for q in comp}
        entries = []
        for q in comp:
            preds = (q.get('pre') or []) + (q.get('preg') or [])
            if not any(p in comp_ids for p in preds):
                entries.append(q)
        zones = [
            get_pickup_zone(e) for e in entries
            if get_pickup_zone(e) is not None
        ]
        if zones:
            zone_counts = Counter(zones)
            top = zone_counts.most_common(1)[0][1]
            zone = min(z for z, c in zone_counts.items() if c == top)
        else:
            zone = 0
        by_zone[zone].extend(comp)
    return dict(by_zone)


def _connected_components(
    quests: list[dict], by_id: dict[int, dict],
) -> list[list[dict]]:
    """Group quests into connected components via undirected pre/preg edges."""
    adj: dict[int, set[int]] = defaultdict(set)
    for q in quests:
        for pid in q['pre'] + q['preg']:
            if pid in by_id:
                adj[q['id']].add(pid)
                adj[pid].add(q['id'])

    visited: set[int] = set()
    components: list[list[dict]] = []
    for q in quests:
        if q['id'] in visited:
            continue
        comp: list[dict] = []
        stack = [q['id']]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(by_id[cur])
            for n in adj[cur]:
                if n not in visited:
                    stack.append(n)
        components.append(comp)
    return components


def _identify_solo_cross_zone(
    keep_qids: set[int], by_id: dict[int, dict],
) -> set[int]:
    """Find rep quests in `keep_qids` that have no chain partners in the
    kept set and whose pickup zone differs from the turnin zone. These
    belong in the complex section of their pickup zone.
    """
    adj: dict[int, set[int]] = defaultdict(set)
    for qid in keep_qids:
        q = by_id[qid]
        for pid in q['pre'] + q['preg']:
            if pid in keep_qids:
                adj[qid].add(pid)
                adj[pid].add(qid)

    result: set[int] = set()
    for qid in keep_qids:
        if adj[qid]:
            continue
        q = by_id[qid]
        if q.get('is_bridge'):
            continue
        pz = get_pickup_zone(q)
        tz = get_turnin_zone(q)
        if pz is None or tz is None:
            continue
        if pz != tz:
            result.add(qid)
    return result


def _extract_in_zone_subset(
    comp: list[dict], by_id: dict[int, dict],
) -> set[int]:
    """Return IDs of quests from `comp` that belong in their own zone.

    A quest qualifies if it is itself self-contained (pickup zone equals
    turnin zone) AND every transitive prerequisite (`pre`/`preg`) is also
    in that same zone for both its pickup and turnin coords. Each extracted
    quest also pulls its in-zone prerequisites along, so bridges and
    pre-rep-quests end up in the right sub-guide.
    """
    extracted: set[int] = set()
    for q in comp:
        if q.get('is_bridge'):
            continue
        zone = get_pickup_zone(q)
        if zone is None or get_turnin_zone(q) != zone:
            continue
        chain_ids: set[int] = {q['id']}
        stack = list((q.get('pre') or []) + (q.get('preg') or []))
        ok = True
        while stack:
            pid = stack.pop()
            if pid in chain_ids:
                continue
            ancestor = by_id.get(pid)
            if ancestor is None:
                continue
            apz = get_pickup_zone(ancestor)
            atz = get_turnin_zone(ancestor)
            if apz != zone or (atz is not None and atz != zone):
                ok = False
                break
            chain_ids.add(pid)
            stack.extend((ancestor.get('pre') or []) + (ancestor.get('preg') or []))
        if ok:
            extracted.update(chain_ids)
    return extracted
