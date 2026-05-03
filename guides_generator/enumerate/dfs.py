"""Brute-force enumeration of every feasible stop ordering of a sub-guide.

The DFS walks the stop set, picking at each level any not-yet-visited stop
whose predecessors are satisfied (`routing.feasibility.is_feasible`). When
all stops are placed, the resulting permutation is one full path through
the sub-guide; we update aggregate statistics and a Top-K heap.

Cumulative numbers (rep, distance) are maintained incrementally so the
per-permutation cost is O(1) — the constant factor matters at this scale.

Output (token-efficient layout):
- `<bucket>_best.json`  — winner only, ~3 KB.
- `<bucket>_top.jsonl`  — Top-K by rep/dist, ~tens of KB.
- `<bucket>_stats.json` — aggregates + rep/dist histogram, ~few KB.
- `<bucket>_full.jsonl.gz` (only with `--full-output`) — every permutation,
  gzipped. Optional audit trail; not needed to find the winner.
"""
from __future__ import annotations

import gzip
import heapq
import json
import math
import time
from dataclasses import dataclass
from typing import Optional, TextIO

from ..routing.feasibility import is_feasible, mark_done
from ..routing.types import Stop
from .dataset import SubGuide

HISTOGRAM_BUCKETS = 50  # rep/dist histogram resolution in stats output


@dataclass
class EnumResult:
    total_permutations: int
    truncated: bool
    elapsed_sec: float
    best_seq: list[int]
    best_rep: int
    best_distance: float
    best_rep_per_dist: float
    top_entries: list[dict]   # top-K, descending by rep/dist
    stats: dict               # aggregates + histogram


def _dist(a: Optional[tuple[int, float, float]],
          b: tuple[int, float, float]) -> float:
    """Euclidean distance within a zone; 0 across zones (treated as
    flightpath/portal travel, matching `compute_tour_stats`)."""
    if a is None or a[0] != b[0]:
        return 0.0
    return math.hypot(a[1] - b[1], a[2] - b[2])


def _meta(sg: SubGuide) -> dict:
    """Header metadata reused across all output files."""
    return {
        'faction_id': sg.faction_id,
        'faction_name': sg.faction_name,
        'expansion': sg.expansion,
        'zone_id': sg.zone_id,
        'zone_name': sg.zone_name,
        'tier': sg.tier,
        'n_stops': len(sg.stops),
        'n_quests': len(sg.quests),
        'total_quest_rep': sg.total_quest_rep,
        'reachable_rep': sg.reachable_rep,
        'start_pos': list(sg.start_pos) if sg.start_pos else None,
        'stops': [
            {
                'i': i, 'type': s.type, 'qid': s.quest_id,
                'coord': list(s.coord),
                'rep': s.quest.get('rep', 0) if s.type == 'QT' else 0,
                'name': s.quest.get('name'),
            }
            for i, s in enumerate(sg.stops)
        ],
    }


def enumerate_subguide(
    sg: SubGuide, *,
    out_paths: dict,                  # 'best' / 'top' / 'stats' / 'full' (optional)
    top_k: int = 100,
    max_permutations: Optional[int] = None,
    progress_every: int = 100_000,
    write_full: bool = False,
) -> EnumResult:
    """Enumerate every feasible permutation. Streams the winner, top-K and
    aggregates to disk; only writes the (potentially huge) full JSONL if
    `write_full=True`.
    """
    stops = sg.stops
    n = len(stops)
    predecessors = sg.predecessors
    start_pos = sg.start_pos

    visited = [False] * n
    completed: dict[int, set[str]] = {}
    sequence: list[int] = []
    counter = {'count': 0, 'truncated': False}

    # Aggregates (maintained incrementally).
    agg = {
        'rep_min': math.inf, 'rep_max': -math.inf, 'rep_sum': 0,
        'dist_min': math.inf, 'dist_max': -math.inf, 'dist_sum': 0.0,
        'rd_min': math.inf, 'rd_max': -math.inf, 'rd_sum': 0.0,
        'rd_inf_count': 0,  # permutations with dist == 0
    }

    # Top-K min-heap on (rd, -rep, dist, tiebreak, seq). The heap holds the
    # *worst* of the top-K at index 0 so we can drop it when something better
    # comes in.
    top_heap: list[tuple] = []
    tiebreak = 0

    # Histogram of rep/dist (excluding rd==inf entries).
    hist_min: float = math.inf
    hist_max: float = -math.inf
    hist_samples: list[float] = []  # we'll compute the histogram at the end

    full_fh: Optional[TextIO] = None
    if write_full:
        full_fh = gzip.open(out_paths['full'], 'wt', encoding='utf-8')
        full_fh.write(json.dumps({'meta': _meta(sg)}) + '\n')

    started = time.monotonic()

    def record(rep: int, dist: float) -> bool:
        """Record one completed permutation. Returns False to abort the DFS."""
        nonlocal tiebreak, hist_min, hist_max
        if dist > 0:
            rd = rep / dist
            agg['rd_min'] = min(agg['rd_min'], rd)
            agg['rd_max'] = max(agg['rd_max'], rd)
            agg['rd_sum'] += rd
            hist_samples.append(rd)
            if rd < hist_min:
                hist_min = rd
            if rd > hist_max:
                hist_max = rd
        else:
            rd = math.inf
            agg['rd_inf_count'] += 1

        agg['rep_min'] = min(agg['rep_min'], rep)
        agg['rep_max'] = max(agg['rep_max'], rep)
        agg['rep_sum'] += rep
        agg['dist_min'] = min(agg['dist_min'], dist)
        agg['dist_max'] = max(agg['dist_max'], dist)
        agg['dist_sum'] += dist

        # Top-K: rank by rd descending, then by smaller dist as tiebreak.
        # Push tuples whose natural sort puts the *worst* of the top-K at
        # heap[0]. We use (rd, -dist, tiebreak, seq_snapshot).
        key = (rd if rd != math.inf else 1e18, -dist, tiebreak)
        tiebreak += 1
        if len(top_heap) < top_k:
            heapq.heappush(top_heap, (key, list(sequence), rep, dist))
        elif key > top_heap[0][0]:
            heapq.heapreplace(top_heap, (key, list(sequence), rep, dist))

        if full_fh is not None:
            full_fh.write(json.dumps({
                'seq': list(sequence),
                'rep': rep,
                'dist': round(dist, 4),
                'rd': round(rd, 6) if rd != math.inf else None,
            }) + '\n')

        counter['count'] += 1
        if progress_every and counter['count'] % progress_every == 0:
            elapsed = time.monotonic() - started
            rate = counter['count'] / elapsed if elapsed else 0.0
            best_rd = top_heap[-1][0][0] if top_heap else 0.0  # worst-of-top
            top_best = max(top_heap, key=lambda x: x[0]) if top_heap else None
            shown_rd = top_best[0][0] if top_best else 0.0
            print(
                f'  [{counter["count"]:>12,d} perms] '
                f'best rep/dist={shown_rd:.4f}  '
                f'{rate:,.0f} perms/s'
            )
        if max_permutations is not None and counter['count'] >= max_permutations:
            counter['truncated'] = True
            return False
        return True

    def recurse(cur_pos: Optional[tuple[int, float, float]],
                cur_dist: float, cur_rep: int) -> bool:
        if len(sequence) == n:
            return record(cur_rep, cur_dist)
        for i in range(n):
            if visited[i]:
                continue
            stop = stops[i]
            if not is_feasible(stop, completed, predecessors):
                continue
            visited[i] = True
            sequence.append(i)
            mark_done(completed, stop)
            step_dist = _dist(cur_pos, stop.coord)
            added_rep = stop.quest.get('rep', 0) if stop.type == 'QT' else 0
            try:
                if not recurse(stop.coord, cur_dist + step_dist, cur_rep + added_rep):
                    return False
            finally:
                visited[i] = False
                sequence.pop()
                completed[stop.quest_id].discard(stop.type)
                if not completed[stop.quest_id]:
                    del completed[stop.quest_id]
        return True

    recurse(start_pos, 0.0, 0)

    if full_fh is not None:
        full_fh.close()

    elapsed = time.monotonic() - started
    return _finalize(sg, out_paths, top_heap, agg, hist_samples,
                     hist_min, hist_max, counter, elapsed)


def _finalize(
    sg: SubGuide, out_paths: dict, top_heap: list,
    agg: dict, hist_samples: list[float],
    hist_min: float, hist_max: float,
    counter: dict, elapsed: float,
) -> EnumResult:
    n_completed = counter['count']

    # Sort top-K descending by rd, breaking ties by smaller distance.
    top_sorted = sorted(top_heap, key=lambda x: x[0], reverse=True)
    top_entries = [
        {
            'rank': rank + 1,
            'seq': seq,
            'rep': rep,
            'dist': round(dist, 4),
            'rd': (round(key[0], 6) if key[0] < 1e17 else None),
        }
        for rank, (key, seq, rep, dist) in enumerate(top_sorted)
    ]

    # Histogram of rep/dist.
    histogram: list[dict] = []
    if hist_samples and hist_max > hist_min:
        bucket_count = min(HISTOGRAM_BUCKETS, len(hist_samples))
        bucket_count = max(bucket_count, 1)
        bucket_width = (hist_max - hist_min) / bucket_count
        if bucket_width == 0:
            histogram = [{'lo': hist_min, 'hi': hist_max, 'n': len(hist_samples)}]
        else:
            counts = [0] * bucket_count
            for s in hist_samples:
                idx = int((s - hist_min) / bucket_width)
                if idx >= bucket_count:
                    idx = bucket_count - 1
                counts[idx] += 1
            histogram = [
                {
                    'lo': round(hist_min + i * bucket_width, 6),
                    'hi': round(hist_min + (i + 1) * bucket_width, 6),
                    'n': c,
                }
                for i, c in enumerate(counts)
            ]
    elif hist_samples:
        histogram = [{'lo': hist_min, 'hi': hist_max, 'n': len(hist_samples)}]

    stats = {
        'meta': _meta(sg),
        'permutations': n_completed,
        'truncated': counter['truncated'],
        'elapsed_sec': round(elapsed, 3),
        'rep': {
            'min': agg['rep_min'] if n_completed else None,
            'max': agg['rep_max'] if n_completed else None,
            'mean': round(agg['rep_sum'] / n_completed, 4) if n_completed else None,
        },
        'distance': {
            'min': round(agg['dist_min'], 4) if n_completed else None,
            'max': round(agg['dist_max'], 4) if n_completed else None,
            'mean': round(agg['dist_sum'] / n_completed, 4) if n_completed else None,
        },
        'rep_per_dist': {
            'min': round(agg['rd_min'], 6) if agg['rd_min'] != math.inf else None,
            'max': round(agg['rd_max'], 6) if agg['rd_max'] != -math.inf else None,
            'mean': (round(agg['rd_sum'] / (n_completed - agg['rd_inf_count']), 6)
                     if (n_completed - agg['rd_inf_count']) > 0 else None),
            'inf_count': agg['rd_inf_count'],
        },
        'histogram': histogram,
    }

    # _stats.json (small)
    with open(out_paths['stats'], 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)

    # _top.jsonl (one entry per line). Header line carries meta so the file
    # is self-contained — readers can pick a rank without needing _stats.json.
    with open(out_paths['top'], 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'meta': _meta(sg)}, ensure_ascii=False) + '\n')
        for entry in top_entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # _best.json (winner with resolved stop info — primary read target)
    best = top_entries[0] if top_entries else None
    if best:
        best_payload = {
            'meta': _meta(sg),
            'permutations': n_completed,
            'truncated': counter['truncated'],
            'elapsed_sec': round(elapsed, 3),
            'rep': best['rep'],
            'distance': best['dist'],
            'rep_per_dist': best['rd'],
            'sequence': [
                {
                    'idx': i,
                    'type': sg.stops[i].type,
                    'quest_id': sg.stops[i].quest_id,
                    'quest_name': sg.stops[i].quest.get('name'),
                    'coord': list(sg.stops[i].coord),
                }
                for i in best['seq']
            ],
        }
    else:
        best_payload = {'meta': _meta(sg), 'permutations': 0}
    with open(out_paths['best'], 'w', encoding='utf-8') as fh:
        json.dump(best_payload, fh, indent=2, ensure_ascii=False)

    return EnumResult(
        total_permutations=n_completed,
        truncated=counter['truncated'],
        elapsed_sec=elapsed,
        best_seq=best['seq'] if best else [],
        best_rep=best['rep'] if best else 0,
        best_distance=best['dist'] if best else 0.0,
        best_rep_per_dist=(best['rd'] if best and best['rd'] is not None else 0.0),
        top_entries=top_entries,
        stats=stats,
    )
