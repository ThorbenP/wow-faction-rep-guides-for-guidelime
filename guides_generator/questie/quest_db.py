"""Parser for Questie's quest database.

Quest table indices (1-based, see Questie's `questKeys.lua`):
    1=name, 2=startedBy {creatures, objects, items}, 3=finishedBy,
    4=requiredLevel, 5=questLevel, 6=requiredRaces, 7=requiredClasses,
    10=objectives {creatures, objects, items},
    12=preQuestGroup, 13=preQuestSingle, 17=zoneOrSort, 22=nextQuestInChain,
    26=reputationReward {{factionID, value}, ...}
"""
from __future__ import annotations

import os

from .lua import iter_entries, read_questie_table


def parse_quest_db(filepath: str) -> dict[int, dict]:
    print(f'  parse Questie quest DB ({os.path.getsize(filepath)//1024} KB)...')
    body = read_questie_table(filepath, 'QuestieDB.questData = [[')
    quests = dict(iter_entries(body))
    print(f'  ✓ {len(quests)} quests loaded')
    return quests
