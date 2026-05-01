"""Console output helpers — non-essential progress + summary printing."""
from __future__ import annotations

import os


def print_coverage(quests: list[dict]) -> None:
    n = len(quests)
    p = sum(1 for q in quests if 'pickup_coords' in q)
    t = sum(1 for q in quests if 'turnin_coords' in q)
    o = sum(1 for q in quests if 'objective_coords' in q)
    print(f'  ✓ pickup: {p}/{n}, turnin: {t}/{n}, objective: {o}/{n}')


def print_bucket_stats(buckets: dict) -> None:
    natural = sum(1 for (_, b) in buckets if b == 'natural')
    cleanup = sum(1 for (_, b) in buckets if b == 'cleanup')
    print(f'  -> {len(buckets)} sub-guides ({natural} natural-tier, {cleanup} cleanup)')


def print_quest_stats(stats: dict) -> None:
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


def print_summary(
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


def print_bulk_summary(results: list, addons_root: str, version: str) -> None:
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
