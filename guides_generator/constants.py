"""Static data: faction tables, race/class bitmasks, zones + tiers, DB paths."""

CACHE_DIR = './cache'          # downloaded DBs live in `<CACHE_DIR>/<expansion>/`
ADDONS_DIR = './addons'        # generated addons live in `<ADDONS_DIR>/<expansion>/`
CHANGELOG_DIR = './changelog'  # version files in the form `vX.Y.Z[_<slug>].md`
QUESTIE_RAW = 'https://raw.githubusercontent.com/Questie/Questie/master'

DEFAULT_EXPANSION_FOR_ALL = 'tbc'
FALLBACK_VERSION = '0.0.0'     # used when the changelog directory is empty

# Author tag — embedded in addon folder names, .toc Title, and Author field.
AUTHOR = 'ThPi'

# Public link shown in the per-addon README.md and the CurseForge project page.
REPO_URL = 'https://github.com/ThorbenP/wow-faction-rep-guides-for-guidelime'

# Per expansion: which database file to fetch from which Questie path.
DB_FILES = {
    'era': {
        'questie':         ('questie', 'Database/Classic/questDB.lua'),
        'questie_npcs':    ('questie', 'Database/Classic/classicNpcDB.lua'),
        'questie_objects': ('questie', 'Database/Classic/classicObjectDB.lua'),
        'questie_items':   ('questie', 'Database/Classic/classicItemDB.lua'),
    },
    'tbc': {
        'questie':         ('questie', 'Database/TBC/tbcQuestDB.lua'),
        'questie_npcs':    ('questie', 'Database/TBC/tbcNpcDB.lua'),
        'questie_objects': ('questie', 'Database/TBC/tbcObjectDB.lua'),
        'questie_items':   ('questie', 'Database/TBC/tbcItemDB.lua'),
    },
}

# WoW .toc Interface versions.
#   `era` -> Classic Era / Anniversary (currently 1.14.x, Interface 11403).
#   `tbc` -> Burning Crusade Classic / TBC Anniversary (2.5.4, Interface 20504).
# Bump these when WoW Classic patches the client.
INTERFACE_VERSION = {'era': '11403', 'tbc': '20504'}

# Race bitmasks (matches the WoW client API and Questie).
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

FACTION_NAMES = {
    47: 'Ironforge', 54: 'Gnomeregan', 69: 'Darnassus', 72: 'Stormwind',
    76: 'Orgrimmar', 81: 'Thunder Bluff', 68: 'Undercity', 530: 'Darkspear Trolls',
    911: 'Silvermoon City', 930: 'Exodar', 270: 'Argent Dawn', 576: 'Timbermaw Hold',
    609: 'Cenarion Circle', 910: 'Brood of Nozdormu', 470: 'Ravenholdt',
    942: 'Cenarion Expedition', 946: 'Honor Hold', 947: 'Thrallmar',
    933: 'The Consortium', 978: 'Kurenai', 941: "The Mag'har",
    967: 'The Violet Eye', 970: 'Sporeggar', 1011: 'Lower City',
    932: 'The Aldor', 934: 'The Scryers', 989: 'Keepers of Time',
    1015: 'Netherwing', 1031: "Sha'tari Skyguard", 1038: "Ogri'la",
}

ALLIANCE_FACTIONS = {47, 54, 69, 72, 930, 946, 978}
HORDE_FACTIONS = {76, 81, 68, 530, 911, 947, 941}

FACTION_GROUPS = [
    ('Alliance - Capitals',     [47, 54, 69, 72, 930]),
    ('Horde - Capitals',        [76, 81, 68, 530, 911]),
    ('TBC - Alliance',          [946, 978]),
    ('TBC - Horde',             [947, 941]),
    ('TBC - Both factions',     [932, 934, 933, 967, 970, 1011, 989, 1015, 1031, 1038]),
    ('Classic - Neutral',       [270, 576, 609, 910, 470]),
    ('TBC - Outland hub',       [942]),
]

# Zone tiers: the natural level range of a zone (as in a leveling guide).
# Used to bucket each quest as 'natural' (within tier ± tolerance) or
# 'cleanup' (off-tier rep-quests that still belong to that zone).
ZONE_LEVEL_TIER = {
    # Classic Alliance starter
    12:  (1, 10),    # Elwynn Forest
    1:   (1, 10),    # Dun Morogh
    141: (1, 10),    # Teldrassil
    38:  (10, 20),   # Loch Modan
    40:  (10, 20),   # Westfall
    148: (10, 20),   # Darkshore
    44:  (15, 25),   # Redridge Mountains
    10:  (18, 30),   # Duskwood
    11:  (20, 30),   # Wetlands
    33:  (30, 45),   # Stranglethorn Vale
    45:  (30, 40),   # Arathi Highlands
    36:  (30, 40),   # Alterac Mountains
    # Classic Horde starter
    85:  (1, 10),    # Tirisfal Glades
    14:  (1, 10),    # Durotar
    215: (1, 10),    # Mulgore
    130: (10, 20),   # Silverpine Forest
    17:  (10, 25),   # The Barrens
    267: (20, 30),   # Hillsbrad Foothills
    # Both factions
    331: (18, 30),   # Ashenvale
    406: (15, 27),   # Stonetalon Mountains
    405: (30, 40),   # Desolace
    400: (25, 35),   # Thousand Needles
    357: (35, 45),   # Feralas
    15:  (35, 45),   # Dustwallow Marsh
    47:  (40, 50),   # The Hinterlands
    440: (40, 50),   # Tanaris
    3:   (35, 45),   # Badlands
    51:  (43, 50),   # Searing Gorge
    46:  (50, 58),   # Burning Steppes
    28:  (51, 58),   # Western Plaguelands
    139: (53, 60),   # Eastern Plaguelands
    16:  (45, 55),   # Azshara
    361: (48, 55),   # Felwood
    490: (48, 55),   # Un'Goro Crater
    618: (55, 60),   # Winterspring
    1377: (55, 60),  # Silithus
    41:  (55, 65),   # Deadwind Pass
    # TBC Alliance starter
    3524: (1, 10),   # Azuremyst Isle
    3525: (10, 20),  # Bloodmyst Isle
    # TBC Horde starter
    3430: (1, 10),   # Eversong Woods
    3433: (10, 20),  # Ghostlands
    # TBC Outland
    3483: (58, 63),  # Hellfire Peninsula
    3521: (60, 64),  # Zangarmarsh
    3519: (62, 65),  # Terokkar Forest
    3518: (64, 67),  # Nagrand
    3522: (65, 68),  # Blade's Edge Mountains
    3523: (67, 70),  # Netherstorm
    3520: (67, 70),  # Shadowmoon Valley
}

# Capitals and hub zones — no tier constraint; everything bucketed as 'natural'.
CITY_ZONES = {
    1497, 1519, 1537, 1637, 1638, 1657, 3487, 3557, 3703,
    493,  # Moonglade
}

ZONE_MAP = {
    1: 'Dun Morogh', 3: 'Badlands', 10: 'Duskwood', 11: 'Wetlands',
    12: 'Elwynn Forest', 14: 'Durotar', 15: 'Dustwallow Marsh', 16: 'Azshara',
    17: 'The Barrens', 28: 'Western Plaguelands', 33: 'Stranglethorn Vale',
    36: 'Alterac Mountains', 38: 'Loch Modan', 40: 'Westfall', 41: 'Deadwind Pass',
    44: 'Redridge Mountains', 45: 'Arathi Highlands', 46: 'Burning Steppes',
    47: 'The Hinterlands', 51: 'Searing Gorge', 85: 'Tirisfal Glades',
    130: 'Silverpine Forest', 139: 'Eastern Plaguelands', 141: 'Teldrassil',
    148: 'Darkshore', 215: 'Mulgore', 267: 'Hillsbrad Foothills', 331: 'Ashenvale',
    357: 'Feralas', 361: 'Felwood', 400: 'Thousand Needles', 405: 'Desolace',
    406: 'Stonetalon Mountains', 440: 'Tanaris', 490: "Un'Goro Crater",
    493: 'Moonglade', 618: 'Winterspring', 1377: 'Silithus',
    1497: 'Undercity', 1519: 'Stormwind City', 1537: 'Ironforge',
    1637: 'Orgrimmar', 1638: 'Thunder Bluff', 1657: 'Darnassus',
    3430: 'Eversong Woods', 3433: 'Ghostlands', 3487: 'Silvermoon City',
    3524: 'Azuremyst Isle', 3525: 'Bloodmyst Isle', 3557: 'The Exodar',
    3483: 'Hellfire Peninsula', 3518: 'Nagrand', 3519: 'Terokkar Forest',
    3520: 'Shadowmoon Valley', 3521: 'Zangarmarsh', 3522: "Blade's Edge Mountains",
    3523: 'Netherstorm', 3703: 'Shattrath City',
}

# Tolerances
TIER_FIT_TOLERANCE = 5  # how far a quest level may sit off the tier range
LOC_TOL = 1.5           # max map distance to share an inline `[G ...]` hint


# Per-zone cluster radius overrides.
#
# WoW map coordinates are normalised to 0-100 per zone, but the actual zone
# size varies hugely (Tanaris is huge, Stormwind is small). A fixed radius
# is therefore too tight for sparse zones (where stops are spread out).
#
# Empirical tests (P75 of nearest-neighbour distances per zone, capped at
# 25): only sparse zones benefit from R > 12. City- and medium-density zones
# get worse with R < 12 (smaller clusters, more travel entries). So we keep
# 12 as the default and only raise the value for clearly sparse zones.
DEFAULT_CLUSTER_RADIUS = 12.0
ZONE_CLUSTER_RADIUS: dict[int, float] = {
    51:   25.0,   # Searing Gorge
    16:   25.0,   # Azshara
    139:  25.0,   # Eastern Plaguelands
    3557: 25.0,   # The Exodar
    28:   19.0,   # Western Plaguelands
    440:  18.0,   # Tanaris
    47:   17.0,   # The Hinterlands
    1537: 15.0,   # Ironforge
    3433: 13.5,   # Ghostlands
    # Every other zone uses DEFAULT_CLUSTER_RADIUS.
}


# Dungeon entrances as a fallback for NPCs without world coordinates.
# Format: instance-zone-id -> (parent-zone-id, x, y) of the dungeon entrance.
# Used when an item-drop bridge points the player at a dungeon boss — the
# guide then sends them to the entrance instead of (-1, -1).
DUNGEON_ENTRANCES: dict[int, tuple[int, float, float]] = {
    # Classic
    718:  (17,   42.4, 67.5),    # Wailing Caverns -> The Barrens
    719:  (331,  14.4, 14.0),    # Blackfathom Deeps -> Ashenvale
    721:  (51,   35.7, 88.7),    # Blackrock Depths -> Searing Gorge (BR Mtn)
    722:  (1519, 50.6, 64.7),    # The Stockade -> Stormwind City
    491:  (17,   41.0, 95.0),    # Razorfen Kraul -> The Barrens
    1477: (400,  49.1, 23.6),    # Razorfen Downs -> Thousand Needles
    209:  (130,  45.0, 67.6),    # Shadowfang Keep -> Silverpine Forest
    796:  (85,   84.7, 31.7),    # Scarlet Monastery -> Tirisfal Glades
    1583: (46,   28.4, 36.6),    # Lower/Upper Blackrock Spire -> Burning Steppes
    1337: (3,    42.4, 18.6),    # Uldaman -> Badlands
    1581: (40,   42.5, 71.6),    # Deadmines -> Westfall
    2017: (139,  27.8, 11.4),    # Stratholme -> Eastern Plaguelands
    2057: (28,   70.8, 72.6),    # Scholomance -> Western Plaguelands
    2100: (405,  29.0, 62.5),    # Maraudon -> Desolace
    2557: (357,  60.7, 30.8),    # Dire Maul -> Feralas
    1977: (33,   52.5, 18.5),    # Zul'Gurub -> Stranglethorn Vale
    3428: (1377, 30.1, 91.0),    # Ahn'Qiraj (40) -> Silithus
    3429: (1377, 30.1, 91.0),    # Ruins of Ahn'Qiraj (20) -> Silithus
    2677: (46,   27.0, 36.0),    # Blackwing Lair -> Burning Steppes
    2717: (51,   35.0, 86.0),    # Molten Core -> Searing Gorge (via BRD)
    533:  (139,  27.8, 11.4),    # Naxxramas (Classic) -> Eastern Plaguelands
    # TBC
    3562: (3483, 47.5, 51.8),    # Hellfire Ramparts -> Hellfire Peninsula
    3713: (3483, 46.4, 52.4),    # Blood Furnace -> Hellfire Peninsula
    3714: (3483, 47.7, 52.0),    # Shattered Halls -> Hellfire Peninsula
    3717: (3483, 47.4, 52.6),    # Magtheridon's Lair -> Hellfire Peninsula
    3711: (3521, 49.7, 39.6),    # Slave Pens -> Zangarmarsh
    3715: (3521, 49.7, 39.6),    # Underbog -> Zangarmarsh
    3716: (3521, 50.0, 39.4),    # Steamvault -> Zangarmarsh
    3607: (3521, 50.5, 39.4),    # Serpentshrine Cavern -> Zangarmarsh
    3789: (3519, 34.4, 64.4),    # Mana-Tombs -> Terokkar Forest
    3790: (3519, 34.0, 65.5),    # Auchenai Crypts -> Terokkar Forest
    3791: (3519, 34.4, 64.4),    # Sethekk Halls -> Terokkar Forest
    3792: (3519, 39.7, 73.4),    # Shadow Labyrinth -> Terokkar Forest
    3805: (3433, 78.0, 65.0),    # Zul'Aman -> Ghostlands
    3845: (3523, 70.4, 54.3),    # The Mechanar -> Netherstorm
    3847: (3523, 70.7, 53.6),    # The Botanica -> Netherstorm
    3849: (3523, 70.6, 51.9),    # The Arcatraz -> Netherstorm
    3848: (3523, 73.7, 51.6),    # Tempest Keep (The Eye) -> Netherstorm
    3457: (41,   47.4, 75.7),    # Karazhan -> Deadwind Pass
}

# Override map for NPCs that have `zone=0` in Questie but are known to live
# in a specific dungeon. Maps NPC-id -> instance-zone-id (referencing
# DUNGEON_ENTRANCES).
DUNGEON_BOSS_NPCS: dict[int, int] = {
    3654: 718,   # Mutanus the Devourer -> Wailing Caverns
}
