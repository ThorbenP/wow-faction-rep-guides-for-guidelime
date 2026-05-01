"""Dungeon-entrance fallback for NPCs/items that resolve to instance bosses."""

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
