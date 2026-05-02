#!/usr/bin/env python3
"""Diff the snapshot KPIs between two quality reports.

Usage: python compare_reports.py REPORT_A REPORT_B
Prints a side-by-side delta line per metric so multistart vs greedy
runs can be eyeballed in a single line.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Order matches the snapshot section so output reads top-to-bottom.
METRICS = [
    ('Global ø Score',            r'\*\*Global ø Score\*\*: ([\d.]+)',         'higher'),
    ('Global Efficiency',         r'\*\*Global Efficiency\*\*: ([\d.]+)',      'higher'),
    ('Total Distance (Normal)',   r'\*\*Total Distance \(Normal\)\*\*: (\d+)', 'lower'),
    ('Total X-Jumps (Normal)',    r'\*\*Total X-Jumps \(Normal\)\*\*: (\d+)',  'lower'),
    ('Absorption Rate (Normal)',  r'\*\*Absorption Rate \(Normal\)\*\*: ([\d.]+)%', 'higher'),
]


def extract(path: Path) -> dict[str, float]:
    text = path.read_text(encoding='utf-8')
    out = {}
    for label, pattern, _ in METRICS:
        m = re.search(pattern, text)
        if m:
            out[label] = float(m.group(1))
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: compare_reports.py BASELINE NEW', file=sys.stderr)
        return 2
    a = extract(Path(sys.argv[1]))
    b = extract(Path(sys.argv[2]))
    print(f'{"metric":<28} {"baseline":>12} {"new":>12} {"delta":>10}  better?')
    print('-' * 75)
    for label, _, direction in METRICS:
        if label not in a or label not in b:
            continue
        delta = b[label] - a[label]
        if direction == 'higher':
            better = delta > 0.001
        else:
            better = delta < -0.001
        # Highlight regressions; near-zero deltas treated as neutral.
        flag = '✓' if better else ('=' if abs(delta) < 0.05 else '✗')
        print(f'{label:<28} {a[label]:>12.2f} {b[label]:>12.2f} {delta:>+10.2f}  {flag}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
