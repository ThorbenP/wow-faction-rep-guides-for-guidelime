"""Chain index for the sub-guide header + inline chain markers per stop.

Singletons are not included in the chain index — they get no chain marker
either. The disambiguator suffixes duplicate quest names with `(Pt. N)` so
multi-part chains like "The Tower of Althalaxx" stay readable.
"""
from __future__ import annotations

from collections import Counter

from ..chains import find_chains


def build_chain_index(
    quests: list[dict],
) -> tuple[list[tuple[str, list[str]]], dict[int, tuple[str, int, int]]]:
    """Returns:
      - chain_list: `[(label, [quest_names])]` for the index block at the
        top of the sub-guide.
      - quest_pos:  `{quest_id: (label, position, total)}` for the inline
        `*Chain N x/y*` annotation on each step.
    """
    chains, _ = find_chains(quests)
    chain_list: list[tuple[str, list[str]]] = []
    quest_pos: dict[int, tuple[str, int, int]] = {}

    for idx, chain in enumerate(chains, 1):
        names = []
        seen: set[str] = set()
        for q in chain:
            if q['name'] not in seen:
                names.append(q['name'])
                seen.add(q['name'])
        label = f"Chain {idx}"
        chain_list.append((label, names))
        for pos, q in enumerate(chain, 1):
            quest_pos[q['id']] = (label, pos, len(chain))

    return chain_list, quest_pos


def disambiguate_duplicate_names(quests: list[dict]) -> dict[int, str]:
    """When several quests in the list share the same name, suffix them with
    `(Pt. N)` in order of appearance. Returns `{quest_id: display_name}`.
    """
    name_counts = Counter(q['name'] for q in quests)
    seen: dict[str, int] = {}
    result: dict[int, str] = {}
    for q in quests:
        if name_counts[q['name']] > 1:
            seen[q['name']] = seen.get(q['name'], 0) + 1
            result[q['id']] = f"{q['name']} (Pt. {seen[q['name']]})"
        else:
            result[q['id']] = q['name']
    return result
