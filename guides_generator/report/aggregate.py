"""Aggregate per-faction pathing metrics for the quality report."""
from __future__ import annotations


def aggregate_pathing(stats: dict) -> dict:
    """Aggregate pathing metrics across all sub-guides of one faction.

    `normal_*` fields are the efficiency basis (in-zone quests).
    `complex_*` fields are reported for information only — complex
    sections have long cross-zone legs that would distort rep/dist.
    """
    n_dist = 0.0; n_jumps = 0; n_stops = 0; n_clustered = 0; n_rep = 0
    c_dist = 0.0; c_jumps = 0; c_stops = 0; c_clustered = 0; c_rep = 0
    for sg in stats['sub_guides']:
        n_rep += sg.get('normal_rep', 0)
        c_rep += sg.get('complex_rep', 0)
        np_ = sg.get('normal_pathing')
        if np_:
            n_dist += np_['intra_zone_distance']
            n_jumps += np_['cross_zone_jumps']
            n_stops += np_['total_stops']
            n_clustered += np_['clustered_stops']
        cp = sg.get('complex_pathing')
        if cp:
            c_dist += cp['intra_zone_distance']
            c_jumps += cp['cross_zone_jumps']
            c_stops += cp['total_stops']
            c_clustered += cp['clustered_stops']
    return {
        'normal_distance': n_dist,
        'normal_rep': n_rep,
        'normal_stops': n_stops,
        'normal_clustered': n_clustered,
        'normal_jumps': n_jumps,
        'normal_absorption': n_clustered / n_stops if n_stops else 0.0,
        'complex_distance': c_dist,
        'complex_rep': c_rep,
        'complex_stops': c_stops,
        'complex_jumps': c_jumps,
        'total_stops': n_stops + c_stops,
        'total_distance': n_dist + c_dist,
    }


def sg_pathing_normal(sg: dict) -> tuple[float, int, int, float, int]:
    """Normal-section pathing tuple (distance, cross_jumps, cluster_count,
    absorption_rate, rep) for table cells."""
    p = sg.get('normal_pathing')
    rep = sg.get('normal_rep', 0)
    if not p:
        return 0.0, 0, 0, 0.0, rep
    absorp = p['clustered_stops'] / p['total_stops'] if p['total_stops'] else 0.0
    return p['intra_zone_distance'], p['cross_zone_jumps'], p['cluster_count'], absorp, rep
