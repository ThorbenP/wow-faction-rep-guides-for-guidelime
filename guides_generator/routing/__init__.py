"""Greedy-nearest-feasible tour routing for sub-guides, with 2-opt refinement.

A sub-guide is a set of Stops (QA, QC, QT for each quest). The tour builder
emits an ordered sequence of Cluster entries (multiple stops at the same
location) and Travel entries (single stops reached by travel). On every
travel leg, additional stops are absorbed if they sit on the way with a
small detour. Finally a 2-opt post-pass reorders entries when that shortens
the total tour cost without violating precedence.

Public API:
    route_subguide       build the tour for one sub-guide
    compute_tour_stats   pathing metrics for the quality report
    Stop, TourEntry      data carriers (also used by the output emitter)
"""
from .start import pick_start_position
from .stats import compute_tour_stats
from .tour import CLUSTER_RADIUS, DETOUR_THRESHOLD, route_subguide
from .types import Stop, TourEntry

__all__ = [
    'CLUSTER_RADIUS', 'DETOUR_THRESHOLD', 'Stop', 'TourEntry',
    'compute_tour_stats', 'pick_start_position', 'route_subguide',
]
