"""Command-line interface for the brute-force enumerator."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from ..constants import FACTION_NAMES, ZONE_MAP
from .dataset import SubGuide, list_subguides, load_subguide
from .dfs import EnumResult, enumerate_subguide

DEFAULT_OUT_DIR = 'enumerations'
TIERS = ('natural', 'cleanup')
DEFAULT_TOP_K = 100


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='enumerate_pathing',
        description=(
            'Brute-force enumeration of all feasible stop orderings of one '
            'sub-guide. Default output is compact: <bucket>_best.json (winner), '
            '<bucket>_top.jsonl (top-K), <bucket>_stats.json (aggregates). The '
            'full per-permutation JSONL is opt-in via --full-output. '
            'Runtime is exponential — use --list first to find a small bucket.'
        ),
    )
    parser.add_argument('--faction', required=True, help='faction id or name (e.g. "lower city" or 1011)')
    parser.add_argument('--expansion', default='tbc', choices=('tbc', 'classic'))
    parser.add_argument('--zone', help='zone id or name (e.g. "Shattrath City" or 3703)')
    parser.add_argument('--tier', choices=TIERS, default='natural')
    parser.add_argument('--list', action='store_true',
                        help='list available sub-guides for the faction and exit')
    parser.add_argument('--max-combinations', type=int, default=None,
                        help='cut-off after N completed permutations (default: no cap)')
    parser.add_argument('--progress-every', type=int, default=100_000,
                        help='print a progress line every N completed permutations (default 100_000)')
    parser.add_argument('--top-k', type=int, default=DEFAULT_TOP_K,
                        help=f'how many top permutations to keep in _top.jsonl (default {DEFAULT_TOP_K})')
    parser.add_argument('--full-output', action='store_true',
                        help='also write _full.jsonl.gz with every permutation (very large, opt-in)')
    parser.add_argument('--out', default=DEFAULT_OUT_DIR,
                        help=f'output root directory (default {DEFAULT_OUT_DIR})')
    args = parser.parse_args(argv)

    faction_id, faction_name = _resolve_faction(args.faction)

    if args.list:
        return _cmd_list(faction_id, faction_name, args.expansion)

    if not args.zone:
        parser.error('--zone is required (use --list to see options)')

    zone_id = _resolve_zone(args.zone)
    print(f'\n=== brute-force pathing: {faction_name} '
          f'/ {ZONE_MAP.get(zone_id, zone_id)} / {args.tier} '
          f'({args.expansion.upper()}) ===\n')

    sg = load_subguide(faction_id, faction_name, args.expansion, zone_id, args.tier)
    _print_subguide_summary(sg)

    out_paths = _output_paths(args.out, sg, write_full=args.full_output)
    os.makedirs(os.path.dirname(out_paths['best']), exist_ok=True)
    print(f'\nenumerating; outputs -> {os.path.dirname(out_paths["best"])}/')
    if args.max_combinations:
        print(f'  (cut-off: {args.max_combinations:,d} permutations)')
    if args.full_output:
        print(f'  (full JSONL -> {out_paths["full"]})')

    result = enumerate_subguide(
        sg,
        out_paths=out_paths,
        top_k=args.top_k,
        max_permutations=args.max_combinations,
        progress_every=args.progress_every,
        write_full=args.full_output,
    )

    _print_result(result, out_paths)
    return 0


def _cmd_list(faction_id: int, faction_name: str, expansion: str) -> int:
    print(f'\n=== sub-guides for {faction_name} ({expansion.upper()}) ===\n')
    subguides = list_subguides(faction_id, faction_name, expansion)
    if not subguides:
        print('  (no sub-guides — faction has no in-zone rep quests)')
        return 0
    print(f'  {"zone":<26}{"tier":<10}{"quests":>7}{"stops":>7}')
    print(f'  {"-" * 50}')
    for sg in sorted(subguides, key=lambda s: (len(s.stops), s.zone_name)):
        print(f'  {sg.zone_name:<26}{sg.tier:<10}'
              f'{len(sg.quests):>7}{len(sg.stops):>7}')
    print(f'\n  ({len(subguides)} sub-guides total — start with the smallest)')
    return 0


def _resolve_faction(value: str) -> tuple[int, str]:
    if value.isdigit():
        fid = int(value)
        if fid not in FACTION_NAMES:
            raise SystemExit(f'unknown faction id: {fid}')
        return fid, FACTION_NAMES[fid]
    needle = value.strip().lower()
    matches = [
        (fid, name) for fid, name in FACTION_NAMES.items()
        if name.lower() == needle
    ]
    if not matches:
        matches = [
            (fid, name) for fid, name in FACTION_NAMES.items()
            if needle in name.lower()
        ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f'no faction matches "{value}"')
    raise SystemExit(
        f'ambiguous faction "{value}": '
        + ', '.join(f'{f[1]} ({f[0]})' for f in matches)
    )


def _resolve_zone(value: str) -> int:
    if value.isdigit():
        zid = int(value)
        if zid not in ZONE_MAP:
            raise SystemExit(f'unknown zone id: {zid}')
        return zid
    needle = value.strip().lower()
    matches = [zid for zid, name in ZONE_MAP.items() if name.lower() == needle]
    if not matches:
        matches = [zid for zid, name in ZONE_MAP.items() if needle in name.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f'no zone matches "{value}"')
    raise SystemExit(
        f'ambiguous zone "{value}": '
        + ', '.join(f'{ZONE_MAP[z]} ({z})' for z in matches)
    )


def _output_paths(out_root: str, sg: SubGuide, *, write_full: bool) -> dict:
    safe_zone = sg.zone_name.replace(' ', '').replace("'", '')
    out_dir = os.path.join(out_root, sg.expansion, sg.faction_name.replace(' ', ''))
    base = os.path.join(out_dir, f'{safe_zone}_{sg.tier}')
    paths = {
        'best': f'{base}_best.json',
        'top': f'{base}_top.jsonl',
        'stats': f'{base}_stats.json',
    }
    if write_full:
        paths['full'] = f'{base}_full.jsonl.gz'
    return paths


def _print_subguide_summary(sg: SubGuide) -> None:
    print(f'  quests:          {len(sg.quests)}')
    print(f'  stops (QA/QC/QT):{len(sg.stops):>4}')
    print(f'  total quest rep: {sg.total_quest_rep}')
    if sg.reachable_rep != sg.total_quest_rep:
        print(f'  reachable rep:   {sg.reachable_rep}  '
              f'({sg.total_quest_rep - sg.reachable_rep} unreachable: '
              f'quests w/o resolved turnin)')
    print(f'  start position:  {sg.start_pos}')


def _print_result(result: EnumResult, out_paths: dict) -> None:
    print(f'\n=== done ===')
    print(f'  permutations: {result.total_permutations:,d}'
          f'{"  (truncated by --max-combinations)" if result.truncated else ""}')
    print(f'  elapsed:      {result.elapsed_sec:.2f}s')
    if result.total_permutations:
        print(f'  best rep:     {result.best_rep}')
        print(f'  best dist:    {result.best_distance:.2f}')
        rd_str = ('inf' if result.best_distance == 0
                  else f'{result.best_rep_per_dist:.4f}')
        print(f'  best rep/dist:{rd_str}')
    print(f'  best:   {out_paths["best"]}')
    print(f'  top-K:  {out_paths["top"]}')
    print(f'  stats:  {out_paths["stats"]}')
    if 'full' in out_paths:
        print(f'  full:   {out_paths["full"]}')


if __name__ == '__main__':
    sys.exit(main())
