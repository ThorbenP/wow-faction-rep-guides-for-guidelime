"""Composite efficiency score 0..100 for one sub-guide.

Components and weights:
  - Rep / distance       (50%): logarithmic, rpd=1 -> 15p, 10 -> 52p,
                                50 -> 85p, 100+ -> 100p
  - Total rep            (25%): sqrt-scaled, 5000 -> 71p, 10000+ -> 100p
  - Absorption rate      (15%): linear 0..100% -> 0..100p
  - Cross-zone-jump      (10%): penalty, 0 jumps -> 100p, 10+ -> 0p

The complex section does NOT contribute (same rationale as for
rep/distance). The score is a heuristic, not an absolute measure: 80+ is
excellent, 60-79 solid, 40-59 mediocre, <20 poor.
"""
from __future__ import annotations

import math


def compute_efficiency_score(
    normal_rep: int,
    normal_distance: float,
    normal_jumps: int,
    absorption_rate: float,
    has_normal_quests: bool,
) -> int:
    if not has_normal_quests:
        return 0

    # 1) rep / distance (50%)
    if normal_distance > 0:
        rpd = normal_rep / normal_distance
        rpd_score = min(100.0, max(0.0, math.log10(rpd + 1) * 50))
    else:
        # No distance = perfect pathing (everything at the same NPC).
        rpd_score = 100.0 if normal_rep > 0 else 0.0

    # 2) total rep (25%) — sqrt-scaled
    rep_score = min(100.0, math.sqrt(max(0, normal_rep) / 10000) * 100)

    # 3) absorption rate (15%) — linear
    absorption_score = max(0.0, min(100.0, absorption_rate * 100))

    # 4) jump penalty (10%) — every cross-zone jump costs 10 points
    jump_score = max(0.0, 100.0 - normal_jumps * 10)

    score = (
        rpd_score * 0.50
        + rep_score * 0.25
        + absorption_score * 0.15
        + jump_score * 0.10
    )
    return round(score)
