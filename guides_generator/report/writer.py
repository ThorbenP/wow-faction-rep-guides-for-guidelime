"""Write `_quality_report.md` next to the addons directory.

The report is intended for the maintainer, not the player. It lives in the
repo root so a player who copies `addons/*` into `Interface/AddOns/` does
not accidentally take it along.
"""
from __future__ import annotations

import os

from .aggregate import aggregate_pathing
from .sections import (
    render_faction_comparison, render_faction_ranking, render_glossary,
    render_header, render_input_data, render_per_faction_detail,
    render_snapshot, render_top_bottom_subguides,
)


def write_quality_report(
    results: list, addons_root: str, version: str, expansion: str,
) -> None:
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(addons_root)), '_quality_report.md',
    )

    valid = [r for r in results if r[4]]
    grand, totals, total_subs, global_avg_score = _summarise(valid)

    lines: list[str] = []
    render_header(lines, version, expansion)
    render_glossary(lines)
    render_snapshot(lines, grand, totals, total_subs, global_avg_score)
    render_faction_comparison(lines, valid)
    render_per_faction_detail(lines, valid)
    render_faction_ranking(lines, valid)
    render_top_bottom_subguides(lines, valid)
    render_input_data(lines, valid, totals, grand)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'quality report: {report_path}')


def _summarise(valid: list) -> tuple[dict, dict, int, float]:
    aggs = [aggregate_pathing(r[4]) for r in valid]
    grand = {
        'n_dist':      sum(a['normal_distance'] for a in aggs),
        'n_rep':       sum(a['normal_rep'] for a in aggs),
        'n_jumps':     sum(a['normal_jumps'] for a in aggs),
        'n_stops':     sum(a['normal_stops'] for a in aggs),
        'n_clustered': sum(a['normal_clustered'] for a in aggs),
        'c_dist':      sum(a['complex_distance'] for a in aggs),
        'c_rep':       sum(a['complex_rep'] for a in aggs),
        'c_jumps':     sum(a['complex_jumps'] for a in aggs),
    }
    totals = {
        'input':   sum(r[4]['totals']['total_input'] for r in valid),
        'kept':    sum(r[4]['totals']['in_kept'] for r in valid),
        'complex': sum(r[4]['totals']['in_complex'] for r in valid),
        'dropped': sum(r[4]['totals']['dropped_no_zone'] for r in valid),
    }
    total_subs = sum(len(r[4]['sub_guides']) for r in valid)

    # Global ø score, weighted by normal rep across all sub-guides.
    all_scored: list[tuple[int, int]] = []
    for r in valid:
        for sg in r[4]['sub_guides']:
            if sg['normal_quests'] > 0:
                all_scored.append((sg['efficiency_score'], sg.get('normal_rep', 0)))
    if all_scored:
        sw = sum(w for _, w in all_scored)
        global_avg_score = (
            sum(s * w for s, w in all_scored) / sw if sw > 0
            else sum(s for s, _ in all_scored) / len(all_scored)
        )
    else:
        global_avg_score = 0.0

    return grand, totals, total_subs, global_avg_score
