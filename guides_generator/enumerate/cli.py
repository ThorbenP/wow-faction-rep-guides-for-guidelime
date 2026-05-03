"""Command-line interface for the optimum-pathing solvers.

Three back-ends behind --mode:
- heldkarp (default): exact DP, fast for sub-guides up to ~30 stops.
- ortools:            CP-SAT circuit + rank precedence, scales beyond
                      Held-Karp's memory wall but may only return a
                      best-found-within-budget solution rather than a
                      proven optimum (status FEASIBLE vs OPTIMAL).
- brute:              full enumeration with B&B-free DFS. Exact, but
                      tractable only up to ~16 stops; kept as the
                      verification ground-truth for the other solvers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from ..constants import FACTION_NAMES, ZONE_MAP
from .dataset import SubGuide, list_subguides, load_subguide
from .dfs import enumerate_subguide
from .heldkarp import solve_heldkarp
from .ortools_solver import DEFAULT_TIME_LIMIT_SEC, solve_ortools

DEFAULT_OUT_DIR = 'enumerations'
TIERS = ('natural', 'cleanup')
DEFAULT_TOP_K = 100
MODES = ('heldkarp', 'ortools', 'brute')


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='enumerate_pathing',
        description=(
            'Find the optimum stop ordering for one sub-guide. '
            'Three back-ends via --mode: heldkarp (exact DP, default, ~30 stops), '
            'ortools (CP-SAT, larger sub-guides), brute (verification). '
            'Output is small and self-contained: <bucket>_best.json with the '
            'winner, sequence, and method metadata. Brute additionally writes '
            '_top.jsonl and _stats.json.'
        ),
    )
    parser.add_argument('--faction', required=True, help='faction id or name (e.g. "lower city" or 1011)')
    parser.add_argument('--expansion', default='tbc', choices=('tbc', 'classic'))
    parser.add_argument('--zone', help='zone id or name (e.g. "Shattrath City" or 3703)')
    parser.add_argument('--tier', choices=TIERS, default='natural')
    parser.add_argument('--mode', choices=MODES, default='heldkarp',
                        help=f'solver back-end (default heldkarp). One of {MODES}')
    parser.add_argument('--list', action='store_true',
                        help='list available sub-guides for the faction and exit')
    parser.add_argument('--out', default=DEFAULT_OUT_DIR,
                        help=f'output root directory (default {DEFAULT_OUT_DIR})')
    # ortools-specific
    parser.add_argument('--time-limit', type=float, default=DEFAULT_TIME_LIMIT_SEC,
                        help=f'OR-Tools time budget in seconds (default {DEFAULT_TIME_LIMIT_SEC})')
    parser.add_argument('--workers', type=int, default=None,
                        help='OR-Tools parallel search workers (default: solver picks)')
    parser.add_argument('--log-search', action='store_true',
                        help='print OR-Tools search log to stdout')
    # brute-specific
    parser.add_argument('--max-combinations', type=int, default=None,
                        help='[brute only] cut-off after N completed permutations')
    parser.add_argument('--progress-every', type=int, default=100_000,
                        help='[brute only] progress-line cadence (default 100_000)')
    parser.add_argument('--top-k', type=int, default=DEFAULT_TOP_K,
                        help=f'[brute only] how many top permutations to keep (default {DEFAULT_TOP_K})')
    parser.add_argument('--full-output', action='store_true',
                        help='[brute only] also write _full.jsonl.gz (very large, opt-in)')
    args = parser.parse_args(argv)

    faction_id, faction_name = _resolve_faction(args.faction)

    if args.list:
        return _cmd_list(faction_id, faction_name, args.expansion)

    if not args.zone:
        parser.error('--zone is required (use --list to see options)')

    zone_id = _resolve_zone(args.zone)
    print(f'\n=== optimum pathing ({args.mode}): {faction_name} '
          f'/ {ZONE_MAP.get(zone_id, zone_id)} / {args.tier} '
          f'({args.expansion.upper()}) ===\n')

    sg = load_subguide(faction_id, faction_name, args.expansion, zone_id, args.tier)
    _print_subguide_summary(sg)

    out_dir = _bucket_dir(args.out, sg)
    os.makedirs(out_dir, exist_ok=True)
    print(f'\noutputs -> {out_dir}/')

    if args.mode == 'brute':
        return _run_brute(sg, args, out_dir)
    if args.mode == 'heldkarp':
        return _run_heldkarp(sg, out_dir)
    if args.mode == 'ortools':
        return _run_ortools(sg, args, out_dir)
    parser.error(f'unknown mode: {args.mode}')
    return 1


# --- mode dispatch -------------------------------------------------------

def _run_brute(sg: SubGuide, args, out_dir: str) -> int:
    base = _base_path(out_dir, sg, 'brute')
    out_paths = {
        'best': f'{base}_best.json',
        'top': f'{base}_top.jsonl',
        'stats': f'{base}_stats.json',
    }
    if args.full_output:
        out_paths['full'] = f'{base}_full.jsonl.gz'
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
    print(f'\n=== done (brute) ===')
    print(f'  permutations: {result.total_permutations:,d}'
          f'{"  (truncated)" if result.truncated else ""}')
    print(f'  elapsed:      {result.elapsed_sec:.2f}s')
    if result.total_permutations:
        print(f'  best rep:     {result.best_rep}')
        print(f'  best dist:    {result.best_distance:.4f}')
        rd_str = ('inf' if result.best_distance == 0
                  else f'{result.best_rep_per_dist:.6f}')
        print(f'  best rep/dist:{rd_str}')
    print(f'  best:   {out_paths["best"]}')
    print(f'  top-K:  {out_paths["top"]}')
    print(f'  stats:  {out_paths["stats"]}')
    if 'full' in out_paths:
        print(f'  full:   {out_paths["full"]}')
    return 0


def _run_heldkarp(sg: SubGuide, out_dir: str) -> int:
    result = solve_heldkarp(sg)
    out_path = f'{_base_path(out_dir, sg, "heldkarp")}_best.json'
    _write_solver_best(out_path, sg, result)
    _print_solver_result(result)
    print(f'  best:   {out_path}')
    return 0


def _run_ortools(sg: SubGuide, args, out_dir: str) -> int:
    result = solve_ortools(
        sg,
        time_limit_sec=args.time_limit,
        workers=args.workers,
        log_search=args.log_search,
    )
    out_path = f'{_base_path(out_dir, sg, "ortools")}_best.json'
    _write_solver_best(out_path, sg, result)
    _print_solver_result(result)
    print(f'  best:   {out_path}')
    return 0


# --- listing -------------------------------------------------------------

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


# --- shared output helpers ----------------------------------------------

def _write_solver_best(path: str, sg: SubGuide, result: dict) -> None:
    sequence = [
        {
            'idx': i,
            'type': sg.stops[i].type,
            'quest_id': sg.stops[i].quest_id,
            'quest_name': sg.stops[i].quest.get('name'),
            'coord': list(sg.stops[i].coord),
        }
        for i in result.get('sequence', [])
    ]
    payload = {
        'meta': {
            'faction_id': sg.faction_id,
            'faction_name': sg.faction_name,
            'expansion': sg.expansion,
            'zone_id': sg.zone_id,
            'zone_name': sg.zone_name,
            'tier': sg.tier,
            'n_stops': len(sg.stops),
            'n_quests': len(sg.quests),
            'total_quest_rep': sg.total_quest_rep,
            'reachable_rep': sg.reachable_rep,
            'start_pos': list(sg.start_pos) if sg.start_pos else None,
        },
        'method': result.get('method'),
        'status': result.get('status', 'OPTIMAL'),
        'rep': result.get('rep', 0),
        'distance': round(result.get('distance', 0.0), 6),
        'rep_per_dist': (round(result['rep_per_dist'], 6)
                         if result.get('rep_per_dist') is not None else None),
        'elapsed_sec': round(result.get('elapsed_sec', 0.0), 4),
        'states_visited': result.get('states_visited'),
        'best_bound': (round(result['best_bound'], 6)
                       if result.get('best_bound') is not None else None),
        'sequence': sequence,
    }
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _print_solver_result(result: dict) -> None:
    print(f'\n=== done ({result.get("method")}) ===')
    if 'status' in result:
        print(f'  status:       {result["status"]}')
    print(f'  elapsed:      {result.get("elapsed_sec", 0.0):.3f}s')
    if result.get('states_visited') is not None:
        print(f'  states:       {result["states_visited"]:,d}')
    print(f'  rep:          {result.get("rep", 0)}')
    print(f'  distance:     {result.get("distance", 0.0):.4f}')
    rd = result.get('rep_per_dist')
    print(f'  rep/dist:     {rd:.6f}' if rd is not None else '  rep/dist:     n/a')
    if result.get('best_bound') is not None:
        print(f'  best_bound:   {result["best_bound"]:.4f}')


def _resolve_faction(value: str) -> tuple[int, str]:
    if value.isdigit():
        fid = int(value)
        if fid not in FACTION_NAMES:
            raise SystemExit(f'unknown faction id: {fid}')
        return fid, FACTION_NAMES[fid]
    needle = value.strip().lower()
    matches = [(fid, name) for fid, name in FACTION_NAMES.items() if name.lower() == needle]
    if not matches:
        matches = [(fid, name) for fid, name in FACTION_NAMES.items() if needle in name.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f'no faction matches "{value}"')
    raise SystemExit(f'ambiguous faction "{value}": '
                     + ', '.join(f'{f[1]} ({f[0]})' for f in matches))


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
    raise SystemExit(f'ambiguous zone "{value}": '
                     + ', '.join(f'{ZONE_MAP[z]} ({z})' for z in matches))


def _bucket_dir(out_root: str, sg: SubGuide) -> str:
    return os.path.join(out_root, sg.expansion, sg.faction_name.replace(' ', ''))


def _base_path(out_dir: str, sg: SubGuide, mode: str) -> str:
    safe_zone = sg.zone_name.replace(' ', '').replace("'", '')
    return os.path.join(out_dir, f'{safe_zone}_{sg.tier}_{mode}')


def _print_subguide_summary(sg: SubGuide) -> None:
    print(f'  quests:          {len(sg.quests)}')
    print(f'  stops (QA/QC/QT):{len(sg.stops):>4}')
    print(f'  total quest rep: {sg.total_quest_rep}')
    if sg.reachable_rep != sg.total_quest_rep:
        print(f'  reachable rep:   {sg.reachable_rep}  '
              f'({sg.total_quest_rep - sg.reachable_rep} unreachable: '
              f'quests w/o resolved turnin)')
    print(f'  start position:  {sg.start_pos}')


if __name__ == '__main__':
    sys.exit(main())
