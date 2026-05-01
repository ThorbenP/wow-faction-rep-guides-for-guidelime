"""Questie database I/O: download, cache, and parse the four DB files.

Public symbols:
    fetch_or_load      — cached HTTP fetch of one DB file
    parse_quest_db     — quest table parser
    parse_npc_db       — NPC table parser
    parse_object_db    — world-object table parser
    parse_item_db      — item table parser

Lua-side helpers (`arr_get`, `flatten_ids`, `flatten_objective_ids`) are
re-exported from the `questie.lua` submodule for use by quest builders.
"""
from .fetch import fetch_or_load
from .item_db import parse_item_db
from .lua import arr_get, flatten_ids, flatten_objective_ids
from .npc_db import parse_npc_db
from .object_db import parse_object_db
from .quest_db import parse_quest_db

__all__ = [
    'arr_get', 'fetch_or_load', 'flatten_ids', 'flatten_objective_ids',
    'parse_item_db', 'parse_npc_db', 'parse_object_db', 'parse_quest_db',
]
