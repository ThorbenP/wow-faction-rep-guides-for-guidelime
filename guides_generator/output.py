"""Generate the GuideLime Lua source for one addon.

Architecture: for each sub-guide, `routing.route_subguide` produces a tour
of cluster + travel entries. The `GuideEmitter` translates that tour into
GuideLime tags, sharing the inline `[G x,y zone]` hint while the position
does not change between consecutive steps.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Optional

from .chains import find_chains
from .constants import (
    ALLIANCE_FACTIONS, AUTHOR, DEFAULT_CLUSTER_RADIUS, HORDE_FACTIONS,
    LOC_TOL, ZONE_CLUSTER_RADIUS, ZONE_MAP,
)
from .quests import attribute_complex_to_zones, decode_classes, decode_races
from .routing import Stop, TourEntry, compute_tour_stats, route_subguide
from .zones import (
    get_zone_tier, group_by_zone_and_tier, is_self_contained,
)

MAX_TAR_PER_STEP = 5  # GuideLime cap for multi-target macros (TBC)


# ---------------------------------------------------------------------------
# Output sanitiser
# ---------------------------------------------------------------------------
# GuideLime's tag and comment renderer has caused several visible glitches
# when fed multibyte UTF-8 punctuation: empty checkbox for an `[OC]` line
# starting with `×` (U+00D7), mojibake for `→` (U+2192) inside the chain
# index, broken `[D ...]` tag with em-dash `—` (U+2014). To stay portable
# we replace the known offenders with ASCII equivalents and drop everything
# else outside ASCII (a small whitelist of German umlauts is kept since
# they render fine).

_PUNCT_REPLACEMENTS = {
    '→': '->',
    '←': '<-',
    '↔': '<->',
    '×': 'x',
    '—': '--',
    '–': '-',
    '…': '...',
    '‘': "'",
    '’': "'",
    '“': '"',
    '”': '"',
    ' ': ' ',  # NBSP -> normal space
}
_ALLOWED_UTF8 = set('äöüÄÖÜß')


def _safe_text(s: str) -> str:
    """Convert a string to a GuideLime-safe form: replace known bad
    punctuation with ASCII equivalents, drop other non-ASCII characters
    except whitelisted umlauts."""
    if not s:
        return s
    out = []
    for ch in s:
        if ch in _PUNCT_REPLACEMENTS:
            out.append(_PUNCT_REPLACEMENTS[ch])
        elif ord(ch) < 128 or ch in _ALLOWED_UTF8:
            out.append(ch)
        # else: drop silently
    return ''.join(out)


def _safe_tag_content(s: str) -> str:
    """Same as `_safe_text` but additionally replaces square brackets so
    that quest/NPC names like `[PH] Test NPC` cannot prematurely close a
    surrounding `[QA<id> ...]` or `[TAR<id> ...]` tag.
    """
    return _safe_text(s).replace('[', '(').replace(']', ')')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def guide_category(faction_name: str) -> str:
    """The GuideLime "category" label that groups sub-guides in the menu —
    e.g. "ThPi's Darnassus Rep Farm Guide".
    """
    return f"{AUTHOR}'s {faction_name} Rep Farm Guide"


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


def _disambiguate_duplicate_names(quests: list[dict]) -> dict[int, str]:
    """When several quests in the list share the same name (e.g. multiple
    "Tower of Althalaxx" parts), suffix them with `(Pt. N)` in order of
    appearance. Returns `{quest_id: display_name}`.
    """
    name_counts = Counter(q['name'] for q in quests)
    seen: dict[str, int] = {}
    result: dict[int, str] = {}
    for q in quests:
        if name_counts[q['name']] > 1:
            seen[q['name']] = seen.get(q['name'], 0) + 1
            result[q['id']] = f"{q['name']} (Pt. {seen[q['name']]})"
        else:
            result[q['id']] = q['name']
    return result


# ---------------------------------------------------------------------------
# Chain index (sub-guide header + inline annotations)
# ---------------------------------------------------------------------------

def _build_chain_index(
    quests: list[dict],
) -> tuple[list[tuple[str, list[str]]], dict[int, tuple[str, int, int]]]:
    """Detect quest chains in the list and return:
      - `chain_list`: `[(label, [quest_names])]` for the index block at the
        top of the sub-guide.
      - `quest_pos`:  `{quest_id: (label, position, total)}` for the inline
        `*Chain N x/y*` annotation on each step.
    Singletons are not included (no chain marker for them).
    """
    chains, _ = find_chains(quests)
    chain_list: list[tuple[str, list[str]]] = []
    quest_pos: dict[int, tuple[str, int, int]] = {}

    for idx, chain in enumerate(chains, 1):
        names = []
        seen: set[str] = set()
        for q in chain:
            if q['name'] not in seen:
                names.append(q['name'])
                seen.add(q['name'])
        label = f"Chain {idx}"
        chain_list.append((label, names))
        for pos, q in enumerate(chain, 1):
            quest_pos[q['id']] = (label, pos, len(chain))

    return chain_list, quest_pos


# ---------------------------------------------------------------------------
# GuideEmitter — turns the tour into Lua lines
# ---------------------------------------------------------------------------

class GuideEmitter:
    """Stateful emitter. Tracks `last_loc` so the inline `[G x,y zone]`
    coordinate hint is omitted while the position does not change. Uses
    the NPC database for `[TAR<id>]` macros (which auto-resolve names).
    """

    def __init__(
        self,
        out: list[str],
        npc_db: Optional[dict] = None,
        guide_side: Optional[str] = None,
        loc_tol: float = LOC_TOL,
    ):
        self.out = out
        self.guide_side = guide_side
        self.loc_tol = loc_tol
        self.last_loc: Optional[tuple[int, float, float]] = None
        self.npc_names: dict[int, str] = (
            {nid: npc.get('name') for nid, npc in npc_db.items() if npc.get('name')}
            if npc_db else {}
        )

    def reset_location(self) -> None:
        self.last_loc = None

    # ---- Tour output ----

    def emit_tour(
        self,
        tour: list[TourEntry],
        orphans: list[Stop],
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> None:
        """Emit the whole tour: clusters with an `[OC]` header, travel as
        single stops. Combined `[QT][QA]` is emitted when a turnin and a
        pickup at the same NPC follow each other inside one cluster.
        """
        for entry in tour:
            if entry.kind == 'cluster':
                self._emit_cluster(entry.stops, display_names, quest_pos)
            else:
                self._emit_travel(entry.stops[0], display_names, quest_pos)
        if orphans:
            self.out.append('[OC]Unreachable stops (precedence deadlock):')
            for stop in orphans:
                self._emit_stop_line(stop, display_names, quest_pos)

    def _emit_cluster(
        self, stops: list[Stop],
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> None:
        """Cluster header + stops. Header is omitted for size-1 clusters
        (the single step is enough; a header would only repeat its location).
        """
        if not stops:
            return
        if len(stops) > 1:
            first = stops[0]
            zone_label = ZONE_MAP.get(first.coord[0], f'Zone-{first.coord[0]}')
            self.out.append(self._cluster_header(stops, zone_label))

        i = 0
        while i < len(stops):
            cur = stops[i]
            nxt = stops[i + 1] if i + 1 < len(stops) else None
            if (nxt is not None
                    and cur.type == 'QT' and nxt.type == 'QA'
                    and self._same_loc(cur.coord, nxt.coord)):
                self._emit_combined(cur, nxt, display_names, quest_pos)
                i += 2
            else:
                self._emit_stop_line(cur, display_names, quest_pos)
                i += 1

    def _cluster_header(self, stops: list[Stop], zone_label: str) -> str:
        """Build the `[OC]At (x, y) in <zone>: 3x pickup, 1x turnin` header.

        ASCII only and no leading punctuation: certain GuideLime versions
        rendered an empty checkbox when an `[OC]` line started with a non-
        letter character.
        """
        types = Counter(s.type for s in stops)
        parts = []
        if types['QA']:
            parts.append(f"{types['QA']}x pickup")
        if types['QC']:
            parts.append(f"{types['QC']}x objective")
        if types['QT']:
            parts.append(f"{types['QT']}x turnin")
        first = stops[0]
        return _safe_text(
            f"[OC]At ({first.coord[1]:.1f}, {first.coord[2]:.1f}) "
            f"in {zone_label}: {', '.join(parts)}"
        )

    def _emit_travel(
        self, stop: Stop,
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> None:
        """Single travel-stop: same renderer as a stop inside a cluster."""
        self._emit_stop_line(stop, display_names, quest_pos)

    # ---- Step lines ----

    def _emit_stop_line(
        self, stop: Stop,
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> None:
        body = self._build_body(stop, display_names, quest_pos)
        self._emit_with_location(body, stop.coord)

    def _emit_combined(
        self, qt_stop: Stop, qa_stop: Stop,
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> None:
        """Emit a combined `*Name1 -> Name2*: [QT id1] (+rep)[QA id2]` line.

        Used when the same NPC takes a turnin and immediately offers the
        next pickup. If both quests belong to the same chain, only one
        chain marker is emitted, in range form `*Chain X y->z/total*`.
        """
        qt_q = qt_stop.quest
        qa_q = qa_stop.quest
        qt_name = _safe_tag_content(display_names[qt_q['id']])
        qa_name = _safe_tag_content(display_names[qa_q['id']])
        rep = qt_q.get('rep', 0)
        rep_suffix = f' (+{rep} rep)' if rep > 0 else ''
        qt_race = race_class_tag(qt_q, self.guide_side)
        qa_race = race_class_tag(qa_q, self.guide_side)
        qa_annotations = self._quest_annotations(qa_q)

        body = (
            f'*{qt_name} -> {qa_name}*: '
            f'[QT{qt_q["id"]}]{rep_suffix}{qt_race}'
            f'[QA{qa_q["id"]}]{qa_annotations}{qa_race}'
        )
        info_t = quest_pos.get(qt_q['id'])
        info_a = quest_pos.get(qa_q['id'])
        if info_t and info_a and info_t[0] == info_a[0]:
            body += f' *{info_t[0]} {info_t[1]}->{info_a[1]}/{info_t[2]}*'
        else:
            body += self._chain_marker(qt_q, quest_pos)
            body += self._chain_marker(qa_q, quest_pos)
        self._emit_with_location(body, qt_stop.coord)

    def _build_body(
        self, stop: Stop,
        display_names: dict[int, str],
        quest_pos: dict[int, tuple[str, int, int]],
    ) -> str:
        """Tag body for a single stop, without the `[G ...]` prefix."""
        q = stop.quest
        name = display_names.get(q['id'], q['name'])
        chain = self._chain_marker(q, quest_pos)
        if stop.type == 'QA':
            return self._tag_qa(q, name) + chain
        if stop.type == 'QC':
            return self._tag_qc(q, name) + chain
        if stop.type == 'QT':
            return self._tag_qt(q, name) + chain
        return ''

    # Sage-style tag emission: tags carry only the ID; the quest/NPC name
    # is rendered as a `*Name*:` italic prefix in front of the tag. The
    # older `[QA<id> <name>]` format confused GuideLime's
    # `loadStepUseItems` parser on small sub-guides ("step a nil value"
    # Lua errors). GuideLime resolves names from its own DB at runtime.

    def _tag_qa(self, q: dict, name: str) -> str:
        annotations = self._quest_annotations(q)
        tag = race_class_tag(q, self.guide_side)
        prefix = f'*{_safe_tag_content(name)}*: ' if name else ''
        return f'{prefix}[QA{q["id"]}]{annotations}{tag}'

    def _tag_qt(self, q: dict, name: str) -> str:
        rep_suffix = f' (+{q["rep"]} rep)' if q.get('rep', 0) > 0 else ''
        tag = race_class_tag(q, self.guide_side)
        prefix = f'*{_safe_tag_content(name)}*: ' if name else ''
        return f'{prefix}[QT{q["id"]}]{rep_suffix}{tag}'

    def _tag_qc(self, q: dict, name: str) -> str:
        """`[QC<id>]` with the quest name as italic prefix and up to 5
        `[TAR<id>]` macros for the objective creatures."""
        tag = race_class_tag(q, self.guide_side)
        prefix = f'*{_safe_tag_content(name)}*: '
        parts = [prefix, f'[QC{q["id"]}]']
        for cid in q.get('obj_creatures', [])[:MAX_TAR_PER_STEP]:
            if cid and cid in self.npc_names:
                parts.append(f'[TAR{cid}]')
        return ''.join(parts) + tag

    @staticmethod
    def _quest_annotations(q: dict) -> str:
        """Plain-text annotations after the QA tag (parentheses, not brackets
        — square brackets would be parsed as another GuideLime tag)."""
        parts: list[str] = []
        if q.get('repeatable'):
            parts.append('repeatable')
        if q.get('required_min_rep'):
            parts.append(f'needs {q["required_min_rep"]}')
        if q.get('required_skill'):
            parts.append(f'needs {q["required_skill"]}')
        return f' ({", ".join(parts)})' if parts else ''

    @staticmethod
    def _chain_marker(
        q: dict, quest_pos: dict[int, tuple[str, int, int]],
    ) -> str:
        """Inline chain marker for quests that belong to a chain."""
        info = quest_pos.get(q['id'])
        if not info:
            return ''
        label, pos, total = info
        return f' *{label} {pos}/{total}*'

    # ---- Location sharing ----

    def _emit_with_location(
        self, body: str, coord: Optional[tuple[int, float, float]],
    ) -> None:
        """Prepend `[G x,y zone]` only when the position actually changed
        (within `loc_tol`); otherwise just emit the body."""
        if coord is None:
            self.out.append(body)
            self.last_loc = None
            return
        zone_id, x, y = coord
        new_loc = (zone_id, round(x, 1), round(y, 1))
        if self._same_loc(self.last_loc, coord):
            self.out.append(body)
        else:
            zone_label = ZONE_MAP.get(zone_id, f'Zone-{zone_id}')
            self.out.append(f'[G {x:.1f},{y:.1f} {zone_label}]{body}')
            self.last_loc = new_loc

    def _same_loc(
        self, a: Optional[tuple[int, float, float]],
        b: Optional[tuple[int, float, float]],
    ) -> bool:
        if a is None or b is None:
            return False
        return (a[0] == b[0]
                and abs(a[1] - b[1]) < self.loc_tol
                and abs(a[2] - b[2]) < self.loc_tol)


# ---------------------------------------------------------------------------
# Sub-guide generator
# ---------------------------------------------------------------------------

def generate_guide(
    quests: list[dict],
    faction_name: str,
    expansion: str,
    faction_id: int,
    npc_db: Optional[dict] = None,
    complex_quests: Optional[list[dict]] = None,
) -> tuple[str, dict]:
    """Build the full GuideLime Lua source plus a stats dict.

    Cross-zone (complex) chains are attributed to their entry zone and
    emitted as a sub-section at the END of that zone's sub-guide — inside
    the same `Guidelime.registerGuide(...)` block. So the complex part
    stays with the zone where the chain begins, instead of being a global
    "Complex" sub-guide at the end.

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
    out: list[str] = _emit_header(
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
        sg_stats = _emit_sub_guide(
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
        sg_stats = _emit_complex_sub_guide(out, emitter, leftover, faction_name, side)
        stats['sub_guides'].append(sg_stats)

    return '\n'.join(out), stats


def compute_efficiency_score(
    normal_rep: int,
    normal_distance: float,
    normal_jumps: int,
    absorption_rate: float,
    has_normal_quests: bool,
) -> int:
    """Composite efficiency score 0-100 for a sub-guide.

    Components and weights:
      - Rep / distance       (50%): logarithmic, rpd=1 -> 15p, 10 -> 52p,
                                    50 -> 85p, 100+ -> 100p
      - Total rep            (25%): sqrt-scaled, 5000 -> 71p, 10000+ -> 100p
      - Absorption rate      (15%): linear 0..100% -> 0..100p
      - Cross-zone-jump      (10%): penalty, 0 jumps -> 100p, 10+ -> 0p

    The complex section does NOT contribute (same rationale as for
    rep/distance). The score is a heuristic, not an absolute measure: 80+
    is excellent, 60-79 solid, 40-59 mediocre, <20 poor.
    """
    if not has_normal_quests:
        return 0

    # 1) rep / distance (50%)
    if normal_distance > 0:
        rpd = normal_rep / normal_distance
        rpd_score = min(100.0, max(0.0, math.log10(rpd + 1) * 50))
    else:
        # No distance = perfect pathing (everything at the same NPC).
        rpd_score = 100.0 if normal_rep > 0 else 0.0

    # 2) total rep (25%) — sqrt-scaled
    rep_score = min(100.0, math.sqrt(max(0, normal_rep) / 10000) * 100)

    # 3) absorption rate (15%) — linear
    absorption_score = max(0.0, min(100.0, absorption_rate * 100))

    # 4) jump penalty (10%) — every cross-zone jump costs 10 points
    jump_score = max(0.0, 100.0 - normal_jumps * 10)

    score = (
        rpd_score * 0.50
        + rep_score * 0.25
        + absorption_score * 0.15
        + jump_score * 0.10
    )
    return round(score)


def _step_count(quests: list[dict]) -> dict:
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


def _emit_header(
    faction_name: str, expansion: str, n_quests: int, buckets: list,
    by_bucket: dict, complex_by_zone: Optional[dict] = None,
) -> list[str]:
    """File header with a top-zones-by-rep table.

    The complex quests are credited to the zone they will be appended to,
    so the header reflects the actual sub-guide layout.
    """
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
        f'-- {_safe_text(faction_name)} reputation farm guide ({expansion.upper()})',
        f'-- {n_quests} quests in {len(buckets)} sub-guides -- total ~{total_rep} rep.',
        '--',
        '-- Top zones by rep:',
    ]
    for label, rep in top5:
        lines.append(f'--   {_safe_text(label):<35} +{rep} rep')
    lines.extend([
        '--',
        '-- Race/class restrictions are emitted as [A ...] tags -- GuideLime hides',
        '-- non-matching steps at runtime.',
        '-- Routing: cluster discovery + on-the-way absorption + 2-opt refinement.',
        '',
    ])
    return lines


def _emit_sub_guide(
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
    lvl_min, lvl_max = _level_range(all_quests_for_levels, zone_id, bucket)
    zone_rep = sum(q['rep'] for q in zone_quests)
    complex_rep = sum(q['rep'] for q in complex_quests)
    total_rep = zone_rep + complex_rep
    category = guide_category(faction_name)

    # Run the routing first — the efficiency score is part of the title.
    cluster_radius = ZONE_CLUSTER_RADIUS.get(zone_id, DEFAULT_CLUSTER_RADIUS)
    chain_list, quest_pos = _build_chain_index(zone_quests)
    display_names = _disambiguate_duplicate_names(zone_quests)
    tour, orphans = route_subguide(zone_quests, cluster_radius=cluster_radius)
    normal_pathing = compute_tour_stats(tour)
    score = compute_efficiency_score(
        normal_rep=zone_rep,
        normal_distance=normal_pathing['intra_zone_distance'],
        normal_jumps=normal_pathing['cross_zone_jumps'],
        absorption_rate=normal_pathing['absorption_rate'],
        has_normal_quests=bool(zone_quests),
    )

    safe_display = _safe_text(display_name)
    safe_faction = _safe_text(faction_name)
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
            chain_summary = ' -> '.join(_safe_text(n) for n in names[:4])
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
        'normal_steps': _step_count(zone_quests),
        'complex_steps': _step_count(complex_quests) if complex_quests else None,
        'orphans': len(orphans),
        'rep_total': total_rep,
        'efficiency_score': score,
        'normal_rep': zone_rep,
        'complex_rep': complex_rep,
        'normal_pathing': normal_pathing,
        'complex_pathing': complex_stats['pathing'] if complex_stats else None,
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

    chain_list, quest_pos = _build_chain_index(quests)
    if chain_list:
        out.append('[OC]Complex chains:')
        for label, names in chain_list:
            chain_summary = ' -> '.join(_safe_text(n) for n in names[:4])
            if len(names) > 4:
                chain_summary += ' -> ...'
            out.append(f'[OC]  {label}: {chain_summary}')
        out.append('')

    display_names = _disambiguate_duplicate_names(quests)
    emitter.reset_location()
    tour, orphans = route_subguide(quests)
    pathing = compute_tour_stats(tour)
    emitter.emit_tour(tour, orphans, display_names, quest_pos)
    return {'orphans': len(orphans), 'pathing': pathing}


def _level_range(quests: list[dict], zone_id: int, bucket: str) -> tuple[int, int]:
    tier = get_zone_tier(zone_id)
    if bucket == 'natural' and tier:
        return tier
    levels = [q['level'] for q in quests if q['level'] > 0]
    return (min(levels) if levels else 1, max(levels) if levels else 70)


def _emit_complex_sub_guide(
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

    safe_faction = _safe_text(faction_name)
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

    chain_list, quest_pos = _build_chain_index(quests)
    if chain_list:
        out.append('[OC]Quest chains:')
        for label, names in chain_list:
            chain_summary = ' -> '.join(_safe_text(n) for n in names[:4])
            if len(names) > 4:
                chain_summary += ' -> ...'
            out.append(f'[OC]  {label}: {chain_summary}')
        out.append('')

    display_names = _disambiguate_duplicate_names(quests)
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
        'complex_steps': _step_count(quests),
        'orphans': len(orphans),
        'rep_total': rep_total,
        'efficiency_score': 0,  # global fallback has no normal section
        'normal_rep': 0,
        'complex_rep': rep_total,
        'normal_pathing': None,
        'complex_pathing': pathing,
    }
