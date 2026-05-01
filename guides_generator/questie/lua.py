"""Lua-side parsing helpers — slpp wrapper, table iteration, value flatteners.

Questie stores its DBs as `QuestieDB.<name> = [[ return { [id] = {...}, ... } ]]`
inside Lua source files. We extract the long-string body, split it line by
line, and decode each `[id] = {...}` entry as an array literal. Keys inside
the entry array are 1-based (match Lua's positional convention).
"""
from __future__ import annotations

import re
from typing import Any

try:
    from slpp import slpp as lua
except ImportError:
    print("ERROR: 'slpp' is not installed. Run: pip install slpp")
    raise

# Matches one entry of the form `[<id>] = { ... },` inside Questie's
# `[[return { ... }]]` long-string blocks.
ENTRY_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*=\s*(\{.*\})\s*,?\s*$')


def read_questie_table(filepath: str, marker: str) -> str:
    """Extract the body of a Questie table written as `<marker>return {...}]]`
    and return the inner Lua source string.
    """
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    start = content.find(marker)
    if start < 0:
        raise ValueError(f'marker {marker!r} not found in {filepath}')
    end = content.find(']]', start)
    body = content[start + len(marker):end]
    if body.lstrip().startswith('return'):
        body = body.lstrip()[len('return'):]
    return body


def arr_get(arr: Any, idx: int) -> Any:
    """Read index `idx` (1-based) from a positional Lua array (slpp produces
    either a dict with int keys or a list)."""
    if isinstance(arr, dict):
        return arr.get(idx)
    if isinstance(arr, list) and 0 < idx <= len(arr):
        return arr[idx - 1]
    return None


def flatten_ids(value: Any) -> list[int]:
    """Flatten a Lua array (dict with int keys, list, or scalar) into a flat
    list of ints — discarding the keys."""
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, dict):
        value = [value[k] for k in sorted(value.keys())]
    if isinstance(value, list):
        out: list[int] = []
        for v in value:
            out.extend(flatten_ids(v))
        return out
    return []


def flatten_objective_ids(value: Any) -> list[int]:
    """Questie objectives are nested like `{{creatureId, text?, icon?}, ...}`.
    Return only the IDs (the first element of each sub-list/dict)."""
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, dict):
        value = [value[k] for k in sorted(value.keys())]
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for entry in value:
        if isinstance(entry, int):
            out.append(entry)
        elif isinstance(entry, dict):
            cid = entry.get(1)
            if isinstance(cid, int):
                out.append(cid)
        elif isinstance(entry, list) and entry:
            cid = entry[0]
            if isinstance(cid, int):
                out.append(cid)
    return out


def _decode_entry_array(text: str) -> dict | None:
    """Parse one Lua array literal; normalise to a 1-based dict for indexing."""
    try:
        arr = lua.decode(text)
    except Exception:
        return None
    if isinstance(arr, list):
        return {i + 1: v for i, v in enumerate(arr)}
    if isinstance(arr, dict):
        return arr
    return None


def iter_entries(body: str):
    """Yield (id, dict) for every `[id] = {...},` line in the table body."""
    for line in body.splitlines():
        m = ENTRY_LINE_RE.match(line)
        if not m:
            continue
        entry_id = int(m.group(1))
        arr = _decode_entry_array(m.group(2))
        if arr is None:
            continue
        yield entry_id, arr
