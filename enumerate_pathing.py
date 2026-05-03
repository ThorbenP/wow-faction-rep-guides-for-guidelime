#!/usr/bin/env python3
"""Brute-force enumerator entry point.

Counterpart to `create.py` — same data pipeline up to `group_by_zone_and_tier`,
then enumerates every feasible stop ordering of one sub-guide instead of
running the heuristic router. See `guides_generator/enumerate/` for details.
"""
from __future__ import annotations

import sys

from guides_generator.enumerate.cli import main

if __name__ == '__main__':
    sys.exit(main())
