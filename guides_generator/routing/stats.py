"""Aggregate pathing metrics over a finished tour — used by the quality report."""
from __future__ import annotations

import math
from typing import Optional

from .types import TourEntry


def compute_tour_stats(
    tour: list[TourEntry],
    start_pos: Optional[tuple[int, float, float]] = None,
) -> dict:
    """Returned dict:
      - intra_zone_distance: sum of euclidean distances within the same zone.
        Cross-zone hops do NOT contribute since they are flightpath/portal
        travel, not running distance.
      - cross_zone_jumps: number of zone changes along the tour.
      - cluster_count / cluster_sizes / avg_cluster_size / max_cluster_size
      - travel_count: number of single-stop travel entries.
      - total_stops, clustered_stops (members of clusters with size >= 2).
      - absorption_rate: clustered_stops / total_stops, higher is better.
    """
    total_dist = 0.0
    cross_zone_jumps = 0
    cluster_sizes: list[int] = []
    travel_count = 0
    cur_pos = start_pos

    for entry in tour:
        if entry.kind == 'cluster':
            cluster_sizes.append(len(entry.stops))
            for stop in entry.stops:
                if cur_pos is not None:
                    if cur_pos[0] != stop.coord[0]:
                        cross_zone_jumps += 1
                    else:
                        total_dist += math.hypot(
                            cur_pos[1] - stop.coord[1],
                            cur_pos[2] - stop.coord[2],
                        )
                cur_pos = stop.coord
        else:  # travel
            travel_count += 1
            stop = entry.stops[0]
            if cur_pos is not None:
                if cur_pos[0] != stop.coord[0]:
                    cross_zone_jumps += 1
                else:
                    total_dist += math.hypot(
                        cur_pos[1] - stop.coord[1],
                        cur_pos[2] - stop.coord[2],
                    )
            cur_pos = stop.coord

    total_stops = sum(cluster_sizes) + travel_count
    clustered_stops = sum(s for s in cluster_sizes if s > 1)
    return {
        'intra_zone_distance': round(total_dist, 1),
        'cross_zone_jumps': cross_zone_jumps,
        'cluster_count': len(cluster_sizes),
        'cluster_sizes': cluster_sizes,
        'avg_cluster_size': round(sum(cluster_sizes) / len(cluster_sizes), 2) if cluster_sizes else 0.0,
        'max_cluster_size': max(cluster_sizes) if cluster_sizes else 0,
        'travel_count': travel_count,
        'total_stops': total_stops,
        'clustered_stops': clustered_stops,
        'absorption_rate': round(clustered_stops / total_stops, 3) if total_stops else 0.0,
    }
