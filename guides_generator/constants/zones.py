"""Zone metadata: id -> name, level tier, city/hub set, per-zone routing radius."""

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
