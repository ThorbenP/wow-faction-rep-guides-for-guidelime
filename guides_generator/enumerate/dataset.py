"""Load Questie data and produce sub-guide handles for the enumerator.

Reuses the same pipeline the addon generator uses (filter -> bridges ->
attach_coords -> drop_unreachable_bridge_chains -> group_by_zone_and_tier),
so what goes into the enumerator matches one-to-one what the live addon
ships. From there we keep going past the routing layer: each bucket is
turned into a `SubGuide` carrying the precomputed stop list, predecessor
map, and start position the brute-force DFS needs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import math

from ..constants import ZONE_MAP
from ..coords import attach_coords
from ..pipeline.loader import load_and_filter_quests, load_world_dbs
from ..quests import drop_unreachable_bridge_chains
from ..routing.feasibility import build_predecessor_map, build_stop_list
from ..routing.start import pick_start_position
from ..routing.types import Stop
from ..zones import group_by_zone_and_tier


@dataclass
class SubGuide:
    """One zone bucket of one faction, ready for enumeration."""
    faction_id: int
    faction_name: str
    expansion: str
    zone_id: int
    zone_name: str
    tier: str  # 'natural' | 'cleanup'
    quests: list[dict]
    stops: list[Stop]
    predecessors: dict[int, set[int]]
    start_pos: Optional[tuple[int, float, float]]

    @property
    def total_quest_rep(self) -> int:
        """Sum of rep across all quests in this bucket."""
        return sum(q.get('rep', 0) for q in self.quests)

    @property
    def reachable_rep(self) -> int:
        """Max rep an enumerated permutation can score.

        Equal to `total_quest_rep` minus rep from quests whose turnin coord
        could not be resolved (no QT stop emitted by `build_stop_list`).
        """
        return sum(s.quest.get('rep', 0) for s in self.stops if s.type == 'QT')


def _quests_for_faction(expansion: str, faction_id: int) -> list[dict]:
    """Run the same filter+bridge+coords+drop chain the addon generator uses."""
    quests, _ = load_and_filter_quests(expansion, faction_id)
    npc_db, object_db, item_db = load_world_dbs(expansion)
    attach_coords(quests, npc_db, object_db, item_db)
    kept, _complex = drop_unreachable_bridge_chains(quests)
    return kept


def list_subguides(
    faction_id: int, faction_name: str, expansion: str,
) -> list[SubGuide]:
    """Build SubGuide handles for every zone+tier bucket of a faction."""
    quests = _quests_for_faction(expansion, faction_id)
    buckets = group_by_zone_and_tier(quests)

    subguides: list[SubGuide] = []
    for (zone_id, tier), qs in sorted(buckets.items()):
        subguides.append(_build_subguide(
            faction_id, faction_name, expansion, zone_id, tier, qs,
        ))
    return subguides


def load_subguide(
    faction_id: int, faction_name: str, expansion: str,
    zone_id: int, tier: str,
) -> SubGuide:
    """Load and return a single sub-guide; raises if (zone, tier) is empty."""
    quests = _quests_for_faction(expansion, faction_id)
    buckets = group_by_zone_and_tier(quests)
    qs = buckets.get((zone_id, tier))
    if not qs:
        raise ValueError(
            f'no sub-guide for faction {faction_id} '
            f'in zone {zone_id} ({ZONE_MAP.get(zone_id, "?")}) tier "{tier}"'
        )
    return _build_subguide(faction_id, faction_name, expansion, zone_id, tier, qs)


def build_distance_matrix(sg: SubGuide) -> list[list[float]]:
    """Pairwise stop-to-stop distance, zone-aware (cross-zone = 0)."""
    n = len(sg.stops)
    coords = [s.coord for s in sg.stops]
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        zi, xi, yi = coords[i]
        for j in range(n):
            if i == j:
                continue
            zj, xj, yj = coords[j]
            if zi != zj:
                mat[i][j] = 0.0
            else:
                mat[i][j] = math.hypot(xi - xj, yi - yj)
    return mat


def distances_from_start(sg: SubGuide) -> list[float]:
    """Distance from `sg.start_pos` to each stop (zone-aware, cross-zone = 0)."""
    n = len(sg.stops)
    if sg.start_pos is None:
        return [0.0] * n
    sz, sx, sy = sg.start_pos
    out: list[float] = []
    for s in sg.stops:
        zi, xi, yi = s.coord
        if zi != sz:
            out.append(0.0)
        else:
            out.append(math.hypot(sx - xi, sy - yi))
    return out


def build_stop_predecessor_masks(sg: SubGuide) -> list[int]:
    """Per stop, the bitmask of stop indices that must be visited first.

    Translates routing.feasibility precedence (which is per quest_id and
    by stop type) into a stop-index bitmask:
        QA: every QT stop of every quest in `predecessors[qid]`
        QC: the QA stop of the same quest, if a QA stop exists
        QT: the QA stop and (if present) QC stop of the same quest

    Item-drop bridge quests have no QA stop — their dependents pick up the
    predecessor's QT directly through the QT chain (a QT stop only depends
    on the same quest's QA/QC, never on another quest's QT).
    """
    n = len(sg.stops)
    qa_idx_for: dict[int, int] = {}
    qc_idx_for: dict[int, int] = {}
    qt_idx_for: dict[int, int] = {}
    for i, s in enumerate(sg.stops):
        if s.type == 'QA':
            qa_idx_for[s.quest_id] = i
        elif s.type == 'QC':
            qc_idx_for[s.quest_id] = i
        elif s.type == 'QT':
            qt_idx_for[s.quest_id] = i

    pred_mask: list[int] = [0] * n
    for i, s in enumerate(sg.stops):
        qid = s.quest_id
        if s.type == 'QA':
            for pid in sg.predecessors.get(qid, ()):
                qt = qt_idx_for.get(pid)
                if qt is not None:
                    pred_mask[i] |= 1 << qt
        elif s.type == 'QC':
            qa = qa_idx_for.get(qid)
            if qa is not None:
                pred_mask[i] |= 1 << qa
        elif s.type == 'QT':
            qa = qa_idx_for.get(qid)
            if qa is not None:
                pred_mask[i] |= 1 << qa
            qc = qc_idx_for.get(qid)
            if qc is not None:
                pred_mask[i] |= 1 << qc
    return pred_mask


def _build_subguide(
    faction_id: int, faction_name: str, expansion: str,
    zone_id: int, tier: str, quests: list[dict],
) -> SubGuide:
    stops = build_stop_list(quests)
    predecessors = build_predecessor_map(quests)
    start_pos = pick_start_position(quests)
    return SubGuide(
        faction_id=faction_id,
        faction_name=faction_name,
        expansion=expansion,
        zone_id=zone_id,
        zone_name=ZONE_MAP.get(zone_id, f'Zone-{zone_id}'),
        tier=tier,
        quests=quests,
        stops=stops,
        predecessors=predecessors,
        start_pos=start_pos,
    )
