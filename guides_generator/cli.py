"""Pipeline orchestrator: parse args, load data, generate addons, write report."""
from __future__ import annotations

import argparse
import os
import sys

from .addon import (
    addon_name_for_faction, guide_title_for_faction, read_changelog, write_addon,
)
from .constants import (
    ADDONS_DIR, CACHE_DIR, CHANGELOG_DIR, DEFAULT_EXPANSION_FOR_ALL, FACTION_NAMES,
)
from .coords import attach_coords
from .fetch import fetch_or_load
from .output import generate_guide
from .parsers import (
    parse_item_db, parse_npc_db, parse_object_db, parse_quest_db,
)
from .prompts import prompt_expansion, prompt_faction
from .quests import (
    drop_unreachable_bridge_chains, expand_with_prereq_bridges,
    filter_quests_by_faction,
)
from .zones import group_by_zone_and_tier


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.all:
        _run_all(DEFAULT_EXPANSION_FOR_ALL)
    elif args.faction is not None:
        faction_id = _resolve_faction_arg(args.faction)
        _run_single(faction_id=faction_id, expansion=DEFAULT_EXPANSION_FOR_ALL)
    else:
        _run_single()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='WoW reputation guide generator for the GuideLime addon.',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help=f'Generate guides for all known factions (default expansion: '
             f'{DEFAULT_EXPANSION_FOR_ALL.upper()}). Non-interactive.',
    )
    parser.add_argument(
        '--faction',
        metavar='ID|NAME',
        help=f'Generate the guide for a single faction. Accepts a numeric ID '
             f'(e.g. 69) or a substring of the name (e.g. darnassus). Default '
             f'expansion: {DEFAULT_EXPANSION_FOR_ALL.upper()}. Non-interactive.',
    )
    args = parser.parse_args(argv)
    if args.all and args.faction is not None:
        parser.error('--all and --faction are mutually exclusive.')
    return args


def _resolve_faction_arg(raw: str) -> int:
    """Resolve the `--faction` argument (numeric id or name substring) to
    a faction id. Exits with an error if it is unknown or ambiguous."""
    raw = raw.strip()
    if raw.isdigit():
        fid = int(raw)
        if fid not in FACTION_NAMES:
            print(f'  ! faction id {fid} is not known.')
            sys.exit(1)
        return fid

    needle = raw.lower()
    matches = [(fid, name) for fid, name in FACTION_NAMES.items()
               if needle in name.lower()]
    if not matches:
        print(f'  ! no faction contains {raw!r}.')
        sys.exit(1)
    if len(matches) > 1:
        print(f'  ! ambiguous — {raw!r} matches several factions:')
        for fid, name in matches:
            print(f'      {name} (ID {fid})')
        sys.exit(1)
    return matches[0][0]


# ---------------------------------------------------------------------------
# Single-faction run (interactive or via --faction)
# ---------------------------------------------------------------------------

def _run_single(
    faction_id: int | None = None, expansion: str | None = None,
) -> None:
    """Generate the addon for one faction. Without arguments the user is
    prompted; with arguments (e.g. via `--faction`) it runs unattended."""
    if faction_id is None:
        faction_id = prompt_faction()
    if expansion is None:
        expansion = prompt_expansion()

    fname = FACTION_NAMES.get(faction_id, f'Faction-{faction_id}')

    print(f'\n=== {fname} rep generator ({expansion.upper()}) ===\n')

    quests, _ = _load_and_filter_quests(expansion, faction_id)
    if not quests:
        print('\n  ! no quests for this faction in this expansion.')
        sys.exit(1)

    npc_db, object_db, item_db = _load_world_dbs(expansion)
    attach_coords(quests, npc_db, object_db, item_db)
    quests, complex_quests = drop_unreachable_bridge_chains(quests)
    if complex_quests:
        print(f'  -> {len(complex_quests)} quests moved to complex section '
              f'(bridge chains crossing zones)')
    _print_coverage(quests)

    buckets = group_by_zone_and_tier(quests)
    _print_bucket_stats(buckets)

    version, changelog_text = read_changelog(CHANGELOG_DIR)
    print(f'  changelog: v{version}')

    print('\n[4/4] writing addon directory...')
    addon_path, stats = _build_and_write(
        quests, fname, expansion, faction_id, npc_db,
        version=version, changelog_text=changelog_text,
        complex_quests=complex_quests,
    )
    _print_summary(fname, faction_id, quests, buckets, addon_path, version)
    _print_quest_stats(stats)


# ---------------------------------------------------------------------------
# Bulk run (--all)
# ---------------------------------------------------------------------------

def _run_all(expansion: str) -> None:
    print(f'\n=== bulk generator: all factions ({expansion.upper()}) ===\n')

    print('[A/D] load quest DB...')
    qdb_file = fetch_or_load('questie', expansion, CACHE_DIR)
    quest_db = parse_quest_db(qdb_file)

    print('\n[B/D] load world DBs (NPC / object / item)...')
    npc_db, object_db, item_db = _load_world_dbs(expansion)

    version, changelog_text = read_changelog(CHANGELOG_DIR)
    print(f'\n[C/D] filter and write per faction (v{version})...')
    results: list[tuple[str, int, str | None, int, dict | None]] = []
    addons_top = os.path.abspath(ADDONS_DIR)            # parent dir, for report path
    addons_root = os.path.join(addons_top, expansion)   # actual write target
    os.makedirs(addons_root, exist_ok=True)

    faction_ids = sorted(FACTION_NAMES)
    total = len(faction_ids)
    for idx, faction_id in enumerate(faction_ids, start=1):
        fname = FACTION_NAMES[faction_id]
        rep_quests = filter_quests_by_faction(quest_db, faction_id)
        if not rep_quests:
            print(f'  [{idx}/{total}] · {fname} (ID {faction_id}) — no quests, skipped')
            results.append((fname, faction_id, None, 0, None))
            continue
        quests = expand_with_prereq_bridges(rep_quests, quest_db)
        attach_coords(quests, npc_db, object_db, item_db)
        quests, complex_quests = drop_unreachable_bridge_chains(quests)
        addon_path, stats = _build_and_write(
            quests, fname, expansion, faction_id, npc_db,
            version=version, changelog_text=changelog_text,
            complex_quests=complex_quests,
        )
        n_total = len(quests) + len(complex_quests)
        n_dropped = stats['totals']['dropped_no_zone']
        flag = f' (! {n_dropped} without zone)' if n_dropped else ''
        print(f'  [{idx}/{total}] ✓ {fname} (ID {faction_id}) — {n_total} quests{flag} -> {os.path.basename(addon_path)}')
        results.append((fname, faction_id, addon_path, n_total, stats))

    print('\n[D/D] bulk run finished.')
    _print_bulk_summary(results, addons_root, version)
    _write_quality_report(results, addons_top, version, expansion)


# ---------------------------------------------------------------------------
# Helpers (data loading + write)
# ---------------------------------------------------------------------------

def _load_and_filter_quests(
    expansion: str, faction_id: int,
) -> tuple[list[dict], dict]:
    print('[1/4] Questie quest database...')
    qdb_file = fetch_or_load('questie', expansion, CACHE_DIR)
    quest_db = parse_quest_db(qdb_file)

    print(f'\n[2/4] filter faction {faction_id}...')
    rep_quests = filter_quests_by_faction(quest_db, faction_id)
    print(f'  -> {len(rep_quests)} rep quests, {sum(q["rep"] for q in rep_quests)} rep total')

    quests = expand_with_prereq_bridges(rep_quests, quest_db)
    n_bridges = len(quests) - len(rep_quests)
    if n_bridges:
        print(f'  -> {n_bridges} prerequisite bridges added (rep=0, unblock rep quests)')
    return quests, quest_db


def _load_world_dbs(expansion: str) -> tuple[dict, dict, dict]:
    npc_file = fetch_or_load('questie_npcs', expansion, CACHE_DIR)
    npc_db = parse_npc_db(npc_file)
    obj_file = fetch_or_load('questie_objects', expansion, CACHE_DIR)
    object_db = parse_object_db(obj_file)
    itm_file = fetch_or_load('questie_items', expansion, CACHE_DIR)
    item_db = parse_item_db(itm_file)
    return npc_db, object_db, item_db


def _build_and_write(
    quests: list[dict], fname: str, expansion: str, faction_id: int, npc_db: dict,
    version: str, changelog_text: str,
    complex_quests: list[dict] | None = None,
) -> tuple[str, dict]:
    """Build the guide source and write the addon directory. Returns
    `(absolute_addon_path, stats_dict)`."""
    addon_name = addon_name_for_faction(fname)
    guide_title = guide_title_for_faction(fname)
    guide_text, stats = generate_guide(
        quests, fname, expansion, faction_id, npc_db=npc_db,
        complex_quests=complex_quests,
    )
    addon_dir = os.path.join(os.path.abspath(ADDONS_DIR), expansion, addon_name)
    write_addon(
        addon_dir, addon_name, guide_title, expansion, fname, guide_text,
        version=version, changelog_text=changelog_text,
    )
    return addon_dir, stats


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _print_coverage(quests: list[dict]) -> None:
    n = len(quests)
    p = sum(1 for q in quests if 'pickup_coords' in q)
    t = sum(1 for q in quests if 'turnin_coords' in q)
    o = sum(1 for q in quests if 'objective_coords' in q)
    print(f'  ✓ pickup: {p}/{n}, turnin: {t}/{n}, objective: {o}/{n}')


def _print_bucket_stats(buckets: dict) -> None:
    natural = sum(1 for (_, b) in buckets if b == 'natural')
    cleanup = sum(1 for (_, b) in buckets if b == 'cleanup')
    print(f'  -> {len(buckets)} sub-guides ({natural} natural-tier, {cleanup} cleanup)')


def _print_quest_stats(stats: dict) -> None:
    """Detailed coverage stats: how many quests went where."""
    t = stats['totals']
    print('\n=== quest coverage ===')
    print(f'  input total:      {t["total_input"]} ({t["rep_quests"]} rep + {t["bridge_quests"]} bridges)')
    print(f'  in kept:          {t["in_kept"]}')
    print(f'  in complex:       {t["in_complex"]}')
    print(f'  in sub-guides:    {t["in_buckets"]}')
    if t['dropped_no_zone']:
        print(f'  ! lost (no zone): {t["dropped_no_zone"]}')
        for qid, qname in t['dropped_quests'][:10]:
            print(f'      Q{qid:>5}: {qname}')
        if len(t['dropped_quests']) > 10:
            print(f'      ... + {len(t["dropped_quests"]) - 10} more')

    print('\n=== per sub-guide ===')
    print(f'  {"sub-guide":<35} {"quests":>8} {"steps":>7} {"orphan":>7}')
    for sg in stats['sub_guides']:
        nq = sg['normal_quests']
        cq = sg['complex_quests']
        nsteps = sg['normal_steps']['total_steps'] if sg['normal_steps'] else 0
        csteps = sg['complex_steps']['total_steps'] if sg['complex_steps'] else 0
        total_q = nq + cq
        total_steps = nsteps + csteps
        orphans = sg['orphans']
        flag = ''
        if orphans:
            flag = f' (! {orphans} orphan)'
        if total_q > 0 and total_steps == 0:
            flag = ' (EMPTY!)'
        print(f'  {sg["name"][:35]:<35} {total_q:>8} {total_steps:>7} {orphans:>7}{flag}')


def _print_summary(
    fname: str, faction_id: int, quests: list[dict], buckets: dict, addon_dir: str,
    version: str,
) -> None:
    addon_name = os.path.basename(addon_dir)
    print('\n' + '=' * 60)
    print(f'version:    v{version}')
    print(f'faction:    {fname} (ID {faction_id})')
    print(f'quests:     {len(quests)}')
    print(f'total rep:  {sum(q["rep"] for q in quests)}')
    print(f'sub-guides: {len(buckets)}')
    print(f'addon dir:  {addon_dir}')
    print(f'  ├─ {addon_name}.toc')
    print(f'  ├─ {addon_name}.lua')
    print(f'  └─ CHANGELOG.md')
    print('\nCopy the directory to:')
    print('  WoW/_classic_/Interface/AddOns/         (TBC)')
    print('  WoW/_classic_era_/Interface/AddOns/     (Era)')
    print('=' * 60)


def _print_bulk_summary(results: list, addons_root: str, version: str) -> None:
    print('\n' + '=' * 60)
    print(f'version: v{version}')
    print(f'generated in: {addons_root}\n')
    written = 0
    for fname, fid, addon_path, n_quests, _stats in results:
        if addon_path:
            written += 1
            print(f'  ✓ {fname:<30} ID {fid:<5}  {n_quests:>4} quests')
        else:
            print(f'  · {fname:<30} ID {fid:<5}  (no quests, skipped)')
    print(f'\n{written} addons generated.')
    print(f'Copy the contents of {addons_root} into Interface/AddOns/.')
    print('=' * 60)


# ---------------------------------------------------------------------------
# Quality report (Markdown, written next to the addons directory)
# ---------------------------------------------------------------------------

def _write_quality_report(
    results: list, addons_root: str, version: str, expansion: str,
) -> None:
    """Write `_quality_report.md` next to the addons directory.

    Contains:
      - faction overview (quest counts: total / kept / complex / lost)
      - per-faction detail with a per-sub-guide table including pathing
        metrics (distance, clusters, cross-zone jumps, rep/distance)
      - aggregate pathing block (totals, per-faction comparison)
      - top/bottom efficiency lists

    Intended for the maintainer, not the player. Lives in the repo root
    so a player who copies `addons/*` into `Interface/AddOns/` does not
    accidentally take it along.
    """
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(addons_root)), '_quality_report.md',
    )

    # Aggregated stats — used in several sections of the report.
    valid = [r for r in results if r[4]]
    aggs = [_aggregate_pathing(r[4]) for r in valid]
    grand_n_dist = sum(a['normal_distance'] for a in aggs)
    grand_n_rep = sum(a['normal_rep'] for a in aggs)
    grand_n_jumps = sum(a['normal_jumps'] for a in aggs)
    grand_n_stops = sum(a['normal_stops'] for a in aggs)
    grand_n_clustered = sum(a['normal_clustered'] for a in aggs)
    grand_c_dist = sum(a['complex_distance'] for a in aggs)
    grand_c_rep = sum(a['complex_rep'] for a in aggs)
    grand_c_jumps = sum(a['complex_jumps'] for a in aggs)
    total_input = sum(r[4]['totals']['total_input'] for r in valid)
    total_kept = sum(r[4]['totals']['in_kept'] for r in valid)
    total_complex = sum(r[4]['totals']['in_complex'] for r in valid)
    total_dropped = sum(r[4]['totals']['dropped_no_zone'] for r in valid)
    total_in_buckets = sum(r[4]['totals']['in_buckets'] for r in valid)
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

    lines: list[str] = []

    # ---- header ----
    lines += [
        f'# Quality Report v{version} ({expansion.upper()})',
        '',
        'Auto-generated by `create.py --all`. A snapshot of quest coverage and',
        'pathing efficiency for every faction. Useful as a baseline: tweak a',
        'constant or heuristic, regenerate, diff the new report.',
        '',
    ]

    # ---- glossary ----
    lines += [
        '## Glossary',
        '',
        '### Prefixes',
        '- **N-** = the normal section of a sub-guide (quests that stay inside the',
        '  zone). Feeds into every efficiency metric.',
        '- **C-** = the complex section (cross-zone chains). Reported **for info',
        '  only** — it does NOT feed into the score or rep-per-distance, because',
        '  the long cross-zone legs would distort the metric.',
        '',
        '### Quest counts',
        '- **Total**: quests pulled from the Questie DB that are either rep or',
        '  bridge quests for this faction (input).',
        '- **Rep**: quests that grant rep directly.',
        '- **Bridge**: prerequisite quests with no rep reward, kept so the chain',
        '  is acceptable in-game.',
        '- **Kept**: quests emitted into normal sub-guides.',
        '- **Complex**: cross-zone quests routed into the complex section.',
        '- **Buckets**: quests that actually ended up in some sub-guide.',
        '- **Lost**: quests for which no zone could be determined (e.g.',
        '  battleground zones missing from `ZONE_MAP`). They are dropped.',
        '',
        '### Pathing metrics (normal section)',
        '- **N-Dist**: sum of intra-zone euclidean map distance. Cross-zone hops',
        '  are flightpath/portal travel — not a meaningful running distance — so',
        '  they do not contribute to N-Dist.',
        '- **N-Jumps**: number of zone changes along the tour. For the normal',
        '  section this should be low; a non-zero value means a cross-zone',
        '  quest slipped through the complex extraction.',
        '- **N-Cluster**: number of cluster entries (groups of stops at the same',
        '  location, emitted together).',
        '- **N-Absorp** (absorption rate): fraction of stops sitting in clusters',
        '  with size >= 2. High is good (cluster discovery groups stops well).',
        '- **N-Rep**: total rep from the normal-section quests.',
        '- **N-Rep/Dist**: rep per map-unit walked. Higher is better.',
        '',
        '### Complex info',
        '- **C-Dist / C-Jumps / C-Rep**: same meaning as the N-* fields but for',
        '  the complex section. Reported for context only.',
        '',
        '### Efficiency score (0-100)',
        'A composite metric combining four pathing signals:',
        '- 50% rep / distance (logarithmic: rpd=10 -> 52p, 50 -> 85p, 100+ -> 100p)',
        '- 25% total rep (sqrt: 5000 -> 71p, 10000+ -> 100p) — rewards big sub-guides',
        '- 15% absorption rate (linear)',
        '- 10% cross-zone-jump penalty (0 jumps = 100p, 10+ = 0p)',
        '',
        'Visible in the sub-guide title as `(Eff. <score>, +<rep> rep)`.',
        '',
        '**Scale**: 80+ excellent, 60-79 solid, 40-59 mediocre, 20-39 weak, 0-19 poor.',
        '',
        '### ø Score (faction average)',
        'Weighted average of all sub-guide scores in a faction, weighted by',
        'normal rep so small no-rep sub-guides do not pull the average down.',
        '',
    ]

    # ---- section 1: snapshot headline ----
    abs_rate = (grand_n_clustered / grand_n_stops) if grand_n_stops else 0.0
    rpd_global = (grand_n_rep / grand_n_dist) if grand_n_dist > 0 else 0.0
    lines += [
        '## 1. Snapshot Headline',
        '',
        'The most important KPIs for diff comparisons. Routing/bucketing changes',
        'should improve these (score up, distance down, lost down).',
        '',
        f'- **Global ø Score**: {global_avg_score:.1f} / 100',
        f'- **Global Efficiency**: {rpd_global:.2f} rep / map unit',
        f'- **Total Distance (Normal)**: {grand_n_dist:.0f} map units',
        f'- **Total X-Jumps (Normal)**: {grand_n_jumps}',
        f'- **Absorption Rate (Normal)**: {abs_rate:.1%}',
        f'- **Lost Quests**: {total_dropped} (of {total_input})',
        f'- **Sub-Guides Total**: {total_subs}',
        '',
        '### Complex section (info only, not part of the efficiency)',
        f'- distance: {grand_c_dist:.0f} | x-jumps: {grand_c_jumps} | rep: {grand_c_rep}',
        '',
    ]

    # ---- section 2: faction comparison (diff-relevant columns) ----
    lines += [
        '## 2. Faction Comparison (diff-relevant)',
        '',
        'Limited to columns that move with code changes. Static quest counts',
        '(Total/Rep/Bridge/Kept/Complex) are in section 7.',
        '',
        '| Faction | Buckets | Lost | N-Dist | N-Jumps | N-Absorp | N-Rep/Dist | ø Score |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for entry in valid:
        fname, fid, _, _, stats = entry
        t = stats['totals']
        agg = _aggregate_pathing(stats)
        lost_flag = f'**{t["dropped_no_zone"]}**' if t['dropped_no_zone'] else '0'
        rep_per_dist = (
            f'**{agg["normal_rep"] / agg["normal_distance"]:.1f}**'
            if agg['normal_distance'] > 0 else '∞'
        )
        scored = [(sg['efficiency_score'], sg.get('normal_rep', 0))
                  for sg in stats['sub_guides'] if sg['normal_quests'] > 0]
        if scored:
            sw = sum(w for _, w in scored)
            avg_score = (
                sum(s * w for s, w in scored) / sw if sw > 0
                else sum(s for s, _ in scored) / len(scored)
            )
            avg_label = f'**{avg_score:.0f}**'
        else:
            avg_label = '—'
        n_absorp = (agg['normal_clustered'] / agg['normal_stops']) if agg['normal_stops'] else 0.0
        lines.append(
            f'| {fname} | {t["in_buckets"]} | {lost_flag} | '
            f'{agg["normal_distance"]:.0f} | {agg["normal_jumps"]} | {n_absorp:.0%} | '
            f'{rep_per_dist} | {avg_label} |'
        )
    lines.append('')

    # ---- section 3: per-faction detail with sub-guide table ----
    lines += [
        '## 3. Per-Faction Detail',
        '',
        'Each faction with its sub-guides sorted by score.',
        '',
    ]
    for entry in valid:
        fname, fid, _, _, stats = entry
        t = stats['totals']
        agg = _aggregate_pathing(stats)
        lines.append(f'### {fname} (ID {fid})')
        lines.append('')
        rep_per_dist = (
            f'{agg["normal_rep"] / agg["normal_distance"]:.2f}'
            if agg['normal_distance'] > 0 else '∞'
        )
        n_absorp = (agg['normal_clustered'] / agg['normal_stops']) if agg['normal_stops'] else 0.0
        lines.append(
            f'**Normal**: {agg["normal_distance"]:.0f} dist | {agg["normal_jumps"]} jumps | '
            f'{n_absorp:.1%} absorp | {agg["normal_rep"]} rep | **{rep_per_dist}** rep/dist'
        )
        if agg['complex_distance'] > 0 or agg['complex_rep'] > 0:
            lines.append(
                f'**Complex** (info): {agg["complex_distance"]:.0f} dist | '
                f'{agg["complex_jumps"]} jumps | {agg["complex_rep"]} rep'
            )
        if t['dropped_no_zone']:
            lines.append(f'**Lost**: {t["dropped_no_zone"]} quests:')
            for qid, qname in t['dropped_quests']:
                lines.append(f'  - Q{qid} `{qname}`')
        lines.append('')
        lines.append(
            '| Sub-Guide | Score | Quests | N-Dist | N-Jumps | N-Cluster | N-Absorp | N-Rep/Dist |'
        )
        lines.append('|---|---:|---:|---:|---:|---:|---:|---:|')
        sgs_sorted = sorted(
            stats['sub_guides'],
            key=lambda sg: (sg['efficiency_score'], sg.get('normal_rep', 0)),
            reverse=True,
        )
        for sg in sgs_sorted:
            nq = sg['normal_quests']
            cq = sg['complex_quests']
            quests_label = f'{nq + cq}' if cq == 0 else f'{nq + cq} ({nq}+{cq})'
            n_dist, n_jumps, n_clusters, n_absorp, n_rep = _sg_pathing_normal(sg)
            rep_per = f'{n_rep / n_dist:.2f}' if n_dist > 0 else '∞'
            score = sg['efficiency_score']
            lines.append(
                f'| {sg["name"]} | **{score}** | {quests_label} | '
                f'{n_dist:.0f} | {n_jumps} | {n_clusters} | {n_absorp:.0%} | {rep_per} |'
            )
        lines.append('')

    # ---- section 4: faction ranking by efficiency ----
    factions_with_rep = [
        (r[0], _aggregate_pathing(r[4])) for r in valid
        if _aggregate_pathing(r[4])['normal_distance'] > 0
    ]
    factions_with_rep.sort(
        key=lambda x: x[1]['normal_rep'] / x[1]['normal_distance'], reverse=True,
    )
    lines += [
        '## 4. Faction Ranking by Efficiency (N-Rep / N-Dist)',
        '',
        '| Rank | Faction | N-Rep | N-Dist | **N-Rep/Dist** |',
        '|---:|---|---:|---:|---:|',
    ]
    for i, (fname, agg) in enumerate(factions_with_rep, 1):
        rpd = agg['normal_rep'] / agg['normal_distance']
        lines.append(f'| {i} | {fname} | {agg["normal_rep"]} | {agg["normal_distance"]:.0f} | **{rpd:.2f}** |')
    lines.append('')

    # ---- sections 5/6: top + bottom sub-guides by score ----
    all_sgs: list[tuple[str, str, dict]] = []
    for r in valid:
        for sg in r[4]['sub_guides']:
            if sg['normal_quests'] > 0:
                all_sgs.append((r[0], sg['name'], sg))
    all_sgs.sort(key=lambda x: x[2]['efficiency_score'], reverse=True)

    lines += [
        '## 5. Top 20 Sub-Guides by Score',
        '',
        '| Rank | Faction | Sub-Guide | **Score** | N-Rep | N-Dist | N-Rep/Dist |',
        '|---:|---|---|---:|---:|---:|---:|',
    ]
    for i, (fname, sname, sg) in enumerate(all_sgs[:20], 1):
        n_dist, _, _, _, n_rep = _sg_pathing_normal(sg)
        rpd = f'{n_rep / n_dist:.2f}' if n_dist > 0 else '∞'
        lines.append(
            f'| {i} | {fname} | {sname} | **{sg["efficiency_score"]}** | '
            f'{n_rep} | {n_dist:.0f} | {rpd} |'
        )
    lines.append('')
    lines += [
        '## 6. Bottom 20 Sub-Guides by Score',
        '',
        'Optimisation candidates. Low score, lots of distance, or little rep.',
        '',
        '| Rank | Faction | Sub-Guide | **Score** | N-Rep | N-Dist | N-Rep/Dist |',
        '|---:|---|---|---:|---:|---:|---:|',
    ]
    for i, (fname, sname, sg) in enumerate(reversed(all_sgs[-20:]), 1):
        n_dist, _, _, _, n_rep = _sg_pathing_normal(sg)
        rpd = f'{n_rep / n_dist:.2f}' if n_dist > 0 else '∞'
        lines.append(
            f'| {i} | {fname} | {sname} | **{sg["efficiency_score"]}** | '
            f'{n_rep} | {n_dist:.0f} | {rpd} |'
        )
    lines.append('')

    # ---- section 7: input data (static reality check) ----
    lines += [
        '## 7. Input Data (static, reality-check)',
        '',
        'Quest counts per faction. These only change when the filter logic or',
        'the Questie DB changes — not relevant for routing diffs.',
        '',
        '| Faction | Total | Rep | Bridge | Kept | Complex | N-Rep | C-Rep |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for entry in valid:
        fname, _, _, _, stats = entry
        t = stats['totals']
        agg = _aggregate_pathing(stats)
        lines.append(
            f'| {fname} | {t["total_input"]} | {t["rep_quests"]} | {t["bridge_quests"]} | '
            f'{t["in_kept"]} | {t["in_complex"]} | {agg["normal_rep"]} | {agg["complex_rep"]} |'
        )
    lines += [
        '',
        f'**Aggregate**: {total_input} total | {total_kept} kept | {total_complex} complex | '
        f'{grand_n_rep} N-Rep | {grand_c_rep} C-Rep',
        '',
    ]

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'quality report: {report_path}')


def _aggregate_pathing(stats: dict) -> dict:
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


def _sg_pathing_normal(sg: dict) -> tuple[float, int, int, float, int]:
    """Normal-section pathing tuple (distance, cross_jumps, cluster_count,
    absorption_rate, rep) for table cells."""
    p = sg.get('normal_pathing')
    rep = sg.get('normal_rep', 0)
    if not p:
        return 0.0, 0, 0, 0.0, rep
    absorp = p['clustered_stops'] / p['total_stops'] if p['total_stops'] else 0.0
    return p['intra_zone_distance'], p['cross_zone_jumps'], p['cluster_count'], absorp, rep


def _sg_pathing_complex(sg: dict) -> tuple[float, int, int]:
    """Complex-section pathing tuple (distance, cross_jumps, rep) for info
    columns. Returns zeros when there is no complex section."""
    p = sg.get('complex_pathing')
    rep = sg.get('complex_rep', 0)
    if not p:
        return 0.0, 0, rep
    return p['intra_zone_distance'], p['cross_zone_jumps'], rep


if __name__ == '__main__':
    main()
