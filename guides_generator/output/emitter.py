"""GuideEmitter — turns a tour into GuideLime-tagged Lua lines.

Stateful: `last_loc` lets consecutive stops share an inline `[G x,y zone]`
hint when the position does not change. NPC names are looked up so multi-
target macros (`[TAR<id>]`) can be emitted only for known NPCs.

Step bodies are verb-led prose ("Pick up [QA<id>]", "Kill [TAR<a>],
[TAR<b>] for [QC<id>]", "Turn in [QT<id>] (+rep rep)") so the player
sees an action and a target instead of a quest-ID dump. The quest name
itself is not printed by the emitter — GuideLime resolves `[QA<id>]` /
`[QT<id>]` / `[QC<id>]` to the quest name at runtime.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from ..constants import LOC_TOL, ZONE_MAP
from ..routing import Stop, TourEntry
from .sanitize import safe_text
from .tags import race_class_tag

MAX_TAR_PER_STEP = 5  # GuideLime cap for multi-target macros (TBC)


class GuideEmitter:
    """Renders Stops/TourEntries into GuideLime tag lines on `out`."""

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
    ) -> None:
        """Emit the whole tour: clusters with an `[OC]` header, travel as
        single stops. Combined `[QT][QA]` is emitted when a turnin and a
        pickup at the same NPC follow each other inside one cluster.
        """
        for entry in tour:
            if entry.kind == 'cluster':
                self._emit_cluster(entry.stops)
            else:
                self._emit_travel(entry.stops[0])
        if orphans:
            self.out.append('[OC]Unreachable stops (precedence deadlock):')
            for stop in orphans:
                self._emit_stop_line(stop)

    def _emit_cluster(self, stops: list[Stop]) -> None:
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
                self._emit_combined(cur, nxt)
                i += 2
            else:
                self._emit_stop_line(cur)
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
        return safe_text(
            f"[OC]At ({first.coord[1]:.1f}, {first.coord[2]:.1f}) "
            f"in {zone_label}: {', '.join(parts)}"
        )

    def _emit_travel(self, stop: Stop) -> None:
        """Single travel-stop: same renderer as a stop inside a cluster."""
        self._emit_stop_line(stop)

    # ---- Step lines ----

    def _emit_stop_line(self, stop: Stop) -> None:
        body = self._build_body(stop)
        self._emit_with_location(body, stop.coord)

    def _emit_combined(self, qt_stop: Stop, qa_stop: Stop) -> None:
        """Emit a combined "Turn in [QT...] (+rep), pick up [QA...]" line.

        Used when the same NPC takes a turnin and immediately offers the
        next pickup — keeps the two GuideLime steps on one source line.
        """
        qt_q = qt_stop.quest
        qa_q = qa_stop.quest
        rep = qt_q.get('rep', 0)
        rep_suffix = f' (+{rep} rep)' if rep > 0 else ''
        qt_race = race_class_tag(qt_q, self.guide_side)
        qa_race = race_class_tag(qa_q, self.guide_side)
        qa_annotations = self._quest_annotations(qa_q)
        body = (
            f'Turn in [QT{qt_q["id"]}]{rep_suffix}{qt_race}, '
            f'pick up [QA{qa_q["id"]}]{qa_annotations}{qa_race}'
        )
        self._emit_with_location(body, qt_stop.coord)

    def _build_body(self, stop: Stop) -> str:
        """Tag body for a single stop, without the `[G ...]` prefix."""
        q = stop.quest
        if stop.type == 'QA':
            return self._tag_qa(q)
        if stop.type == 'QC':
            return self._tag_qc(q)
        if stop.type == 'QT':
            return self._tag_qt(q)
        return ''

    def _tag_qa(self, q: dict) -> str:
        annotations = self._quest_annotations(q)
        tag = race_class_tag(q, self.guide_side)
        return f'Pick up [QA{q["id"]}]{annotations}{tag}'

    def _tag_qt(self, q: dict) -> str:
        rep_suffix = f' (+{q["rep"]} rep)' if q.get('rep', 0) > 0 else ''
        tag = race_class_tag(q, self.guide_side)
        return f'Turn in [QT{q["id"]}]{rep_suffix}{tag}'

    def _tag_qc(self, q: dict) -> str:
        """`[QC<id>]` with an action verb and up to 5 `[TAR<id>]` macros
        for the objective creatures. When the quest has no known kill
        target, fall back to a generic verb so the line still reads as
        an instruction instead of a bare ID."""
        tag = race_class_tag(q, self.guide_side)
        creature_tags: list[str] = []
        for cid in q.get('obj_creatures', [])[:MAX_TAR_PER_STEP]:
            if cid and cid in self.npc_names:
                creature_tags.append(f'[TAR{cid}]')
        qc_tag = f'[QC{q["id"]}]'
        if creature_tags:
            body = f'Kill {", ".join(creature_tags)} for {qc_tag}'
        elif q.get('obj_objects') or q.get('obj_items'):
            body = f'Loot for {qc_tag}'
        else:
            body = f'Complete {qc_tag}'
        return body + tag

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
