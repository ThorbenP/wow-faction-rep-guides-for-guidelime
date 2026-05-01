"""Quest-level processing: filter, prereq bridges, cross-zone classification.

Pipeline:
    filter_quests_by_faction         keep rep-granting quests for one faction
    expand_with_prereq_bridges       pull in pre/preg prerequisite chains
    drop_unreachable_bridge_chains   split into (kept, complex) post-coord
    attribute_complex_to_zones       map complex components to their entry zone

Auxiliaries:
    decode_races / decode_classes    bitmask -> name list
    SKILL_NAMES                      profession-skill annotation table
"""
from .bridges import expand_with_prereq_bridges
from .builder import (
    DEPRECATED_PREFIXES, REP_TIER_THRESHOLDS, SKILL_NAMES,
    build_quest_dict, filter_quests_by_faction,
)
from .classify import attribute_complex_to_zones, drop_unreachable_bridge_chains
from .decode import decode_classes, decode_races

__all__ = [
    'DEPRECATED_PREFIXES', 'REP_TIER_THRESHOLDS', 'SKILL_NAMES',
    'attribute_complex_to_zones', 'build_quest_dict', 'decode_classes',
    'decode_races', 'drop_unreachable_bridge_chains',
    'expand_with_prereq_bridges', 'filter_quests_by_faction',
]
