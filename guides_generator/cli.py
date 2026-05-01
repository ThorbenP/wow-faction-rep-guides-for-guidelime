"""Command-line entry point: parse args and dispatch to the right pipeline."""
from __future__ import annotations

import argparse
import sys

from .constants import DEFAULT_EXPANSION_FOR_ALL, FACTION_NAMES
from .pipeline import run_all, run_single


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.all:
        run_all(DEFAULT_EXPANSION_FOR_ALL)
    elif args.faction is not None:
        faction_id = _resolve_faction_arg(args.faction)
        run_single(faction_id=faction_id, expansion=DEFAULT_EXPANSION_FOR_ALL)
    else:
        run_single()


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


if __name__ == '__main__':
    main()
