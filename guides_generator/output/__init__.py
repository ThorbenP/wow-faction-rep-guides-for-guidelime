"""Lua-side emission: turn routed quests into a GuideLime addon source file.

Architecture:
    sanitize          UTF-8 -> GuideLime-safe ASCII subset
    chain_index       chain detection + display-name disambiguation
    tags              [A race/class] tag construction
    emitter           GuideEmitter — stateful tag-line renderer
    header            file-top comment block (top zones table)
    sub_guide         one Guidelime.registerGuide(...) block per zone bucket
    guide             top-level orchestrator: header + sub-guides + complex
"""
from .emitter import GuideEmitter
from .guide import generate_guide

__all__ = ['GuideEmitter', 'generate_guide']
