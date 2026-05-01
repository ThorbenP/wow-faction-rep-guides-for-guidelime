"""Race and class bitmasks — match the WoW client API and Questie."""

RACE_FLAGS = [
    (1, 'Human'), (2, 'Orc'), (4, 'Dwarf'), (8, 'NightElf'),
    (16, 'Undead'), (32, 'Tauren'), (64, 'Gnome'), (128, 'Troll'),
    (512, 'BloodElf'), (1024, 'Draenei'),
]
RACES_ALLIANCE = {'Human', 'Dwarf', 'NightElf', 'Gnome', 'Draenei'}
RACES_HORDE = {'Orc', 'Undead', 'Tauren', 'Troll', 'BloodElf'}
ALLIANCE_MASK = 1 + 4 + 8 + 64 + 1024
HORDE_MASK = 2 + 16 + 32 + 128 + 512
ALL_RACES_MASK = ALLIANCE_MASK | HORDE_MASK

CLASS_FLAGS = [
    (1, 'Warrior'), (2, 'Paladin'), (4, 'Hunter'), (8, 'Rogue'),
    (16, 'Priest'), (64, 'Shaman'), (128, 'Mage'), (256, 'Warlock'),
    (1024, 'Druid'),
]
ALL_CLASSES_MASK = sum(b for b, _ in CLASS_FLAGS)
