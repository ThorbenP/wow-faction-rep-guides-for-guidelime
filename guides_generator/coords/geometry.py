"""Coord type and geometric helpers shared across the coord-resolution code."""
from __future__ import annotations

import math


Coord = tuple[int, float, float]  # (zone_id, x, y)
SPAWN_CLUSTER_THRESHOLD = 12.0    # map units, single-link clustering radius


def cluster_spawns(spawns: list[Coord], threshold: float) -> list[list[Coord]]:
    """Greedy single-link clustering by map distance. Points in the same zone
    are clustered if their distance is below the threshold; points in
    different zones are never merged."""
    clusters: list[list[Coord]] = []
    for p in spawns:
        attached = False
        for c in clusters:
            if any(_close(p, q, threshold) for q in c):
                c.append(p)
                attached = True
                break
        if not attached:
            clusters.append([p])
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
