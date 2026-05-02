"""Write quality-report files.

Two files are emitted:

- `<addon_dir>/QUALITY_REPORT.md` — one per addon, written next to the
  addon's `.lua` and `CHANGELOG.md`. Self-contained: glossary, this
  faction's snapshot, sub-guide detail, input data.
- `<repo_root>/_quality_report.md` — slim global summary across every
  faction. Snapshot + faction comparison + top/bottom sub-guides.
  Per-faction detail intentionally lives in the addon files, not here.

Both reports are derived from the same `(fname, fid, addon_path,
n_total, stats)` tuples emitted by the bulk and single pipelines.

The root file is the maintainer's quick-look summary; if a player
copies `addons/*` into `Interface/AddOns/`, it stays in the repo.
"""
from __future__ import annotations

import os

from .aggregate import aggregate_pathing
from .sections import (
    render_addon_header, render_addon_input, render_addon_snapshot,
    render_addon_subguides, render_global_faction_comparison,
    render_global_header, render_global_snapshot, render_global_top_bottom,
    render_glossary,
)

ADDON_REPORT_FILENAME = 'QUALITY_REPORT.md'
GLOBAL_REPORT_FILENAME = '_quality_report.md'


def write_addon_report(
    stats: dict, addon_dir: str, faction_name: str, faction_id: int,
    version: str, expansion: str,
) -> str:
    """Write `<addon_dir>/QUALITY_REPORT.md` and return the path.

    Called from both the bulk and single pipelines, so a single-faction
    run leaves the same artefact in the addon directory as a full bulk
    run would.
    """
    lines: list[str] = []
    render_addon_header(lines, faction_name, faction_id, version, expansion)
    render_glossary(lines)
    render_addon_snapshot(lines, faction_name, stats)
    render_addon_subguides(lines, stats)
    render_addon_input(lines, stats)

    path = os.path.join(addon_dir, ADDON_REPORT_FILENAME)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path


def write_global_report(
    results: list, addons_root: str, version: str, expansion: str,
) -> str:
    """Write the slim `_quality_report.md` next to the addons directory.

    Skipped silently when `results` contains no faction with stats —
    e.g. when single-faction runs call this for symmetry but the run
    failed before producing stats.
    """
    valid = [r for r in results if r[4]]
    if not valid:
        return ''

    grand, totals, total_subs, global_avg_score = _summarise(valid)

    lines: list[str] = []
    render_global_header(lines, version, expansion)
    render_global_snapshot(
        lines, grand, totals, total_subs, global_avg_score, len(valid),
    )
    render_global_faction_comparison(lines, valid)
    render_global_top_bottom(lines, valid)

    path = os.path.join(
        os.path.dirname(os.path.abspath(addons_root)), GLOBAL_REPORT_FILENAME,
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path


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
