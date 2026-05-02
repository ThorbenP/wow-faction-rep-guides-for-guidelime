"""Multistart-driven tour routing for sub-guides.

A sub-guide is a set of Stops (QA, QC, QT for each quest). The tour
builder emits an ordered sequence of Cluster entries (multiple stops at
the same location) and Travel entries (single stops reached by travel).

Every `route_subguide` call runs the full v1.5.0 pipeline:

    1. Greedy build with cluster discovery + on-the-way absorption.
    2. K=64 randomized rebuilds (multistart) with cost-aligned
       acceptance and ILS escape (segment-reverse + double-bridge).
    3. Deep refinement on the winner: alternating 2-opt + or-opt,
       3-opt for ≤50 entries, defrag, Held-Karp DP for ≤12 entries,
       stop-level 2-opt + or-opt finishers.

There are no method flags; the chain above is always on. See
`tour.py` and `multistart.py` for the per-step rationale, and
`_experiments_history.md` for the experiment trail that picked it.

Public API:
    route_subguide       build a tour for one sub-guide
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
