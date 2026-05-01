"""Coord type and geometric helpers shared across the coord-resolution code."""
from __future__ import annotations

import math
from collections import defaultdict


Coord = tuple[int, float, float]  # (zone_id, x, y)
SPAWN_CLUSTER_THRESHOLD = 12.0    # map units, single-link clustering radius


def cluster_spawns(spawns: list[Coord], threshold: float) -> list[list[Coord]]:
    """Greedy single-link clustering by map distance. Points in the same
    zone are clustered if their distance is below the threshold; points in
    different zones are never merged.

    Each new point is attached to the **earliest-created** cluster that has
    any member within `threshold` (mirrors the original single-pass greedy
    semantics — order matters for `compute_objective_centroid` because the
    largest cluster wins and ties depend on creation order).

    Implementation: a spatial grid with cell size = threshold ensures that
    any two points within `threshold` share at least one of the 3×3 cells
    around either one. So each point only checks members of nine cells
    instead of every existing cluster, turning the worst-case O(n²) of the
    naive single-link sweep into O(n) for typical spawn distributions.
    """
    clusters: list[list[Coord]] = []
    # Grid keyed by (zone_id, cell_x, cell_y) → list of (cluster_index, coord).
    # Including the zone in the key avoids cross-zone _close calls entirely.
    cells: dict[tuple[int, int, int], list[tuple[int, Coord]]] = defaultdict(list)

    for p in spawns:
        zone, x, y = p
        cx, cy = int(x / threshold), int(y / threshold)
        # Collect every cluster index whose members reach into the 3×3
        # neighbourhood of (cx, cy) within `threshold`. Take the smallest —
        # that is the earliest-created cluster, matching the naive sweep.
        candidates: set[int] = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bucket = cells.get((zone, cx + dx, cy + dy))
                if not bucket:
                    continue
                for cidx, q in bucket:
                    if math.hypot(x - q[1], y - q[2]) < threshold:
                        candidates.add(cidx)
        if candidates:
            target = min(candidates)
        else:
            target = len(clusters)
            clusters.append([])
        clusters[target].append(p)
        cells[(zone, cx, cy)].append((target, p))
    return clusters


def centroid(spawns: list[Coord]) -> Coord:
    cz = spawns[0][0]
    cx = sum(s[1] for s in spawns) / len(spawns)
    cy = sum(s[2] for s in spawns) / len(spawns)
    return (cz, cx, cy)


def _close(a: Coord, b: Coord, threshold: float) -> bool:
    if a[0] != b[0]:
        return False
    return math.hypot(a[1] - b[1], a[2] - b[2]) < threshold
