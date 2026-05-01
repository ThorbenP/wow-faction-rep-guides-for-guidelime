"""Interactive prompts for selecting a faction and expansion."""
from __future__ import annotations

from .constants import FACTION_GROUPS, FACTION_NAMES


EXPANSION_OPTIONS = [
    ('tbc', 'TBC Anniversary / Burning Crusade Classic'),
    ('era', 'Classic Era / Anniversary'),
]


def prompt_faction() -> int:
    """Prompt the user with a grouped faction list and return the chosen ID."""
    flat: list[tuple[int, str]] = []
    print('\nSelect a faction:\n')
    for group_name, fids in FACTION_GROUPS:
        print(f'  {group_name}:')
        for fid in fids:
            name = FACTION_NAMES.get(fid, f'Faction-{fid}')
            flat.append((fid, name))
            print(f'    [{len(flat):2d}]  {name}')
        print()

    while True:
        raw = input('Enter number or name: ').strip()
        if not raw:
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(flat):
                fid, name = flat[idx - 1]
                print(f'  -> {name} (ID {fid})\n')
                return fid
            print(f'  ! enter a number between 1 and {len(flat)}.')
            continue
        needle = raw.lower()
        matches = [(fid, name) for fid, name in flat if needle in name.lower()]
        if len(matches) == 1:
            fid, name = matches[0]
            print(f'  -> {name} (ID {fid})\n')
            return fid
        if not matches:
            print(f'  ! no faction contains {raw!r}.')
            continue
        print('  ! ambiguous — be more specific:')
        for fid, name in matches:
            print(f'      {name}')


def prompt_expansion() -> str:
    """Prompt for an expansion. Empty input defaults to TBC."""
    print('\nSelect the expansion:\n')
    for i, (_, label) in enumerate(EXPANSION_OPTIONS, 1):
        print(f'  [{i}]  {label}')
    print()
    while True:
        raw = input('Enter number or name (default = 1): ').strip().lower()
        if not raw:
            return EXPANSION_OPTIONS[0][0]
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(EXPANSION_OPTIONS):
                return EXPANSION_OPTIONS[idx - 1][0]
        for key, label in EXPANSION_OPTIONS:
            if raw in key or raw in label.lower():
                return key
        print('  ! invalid input.')
