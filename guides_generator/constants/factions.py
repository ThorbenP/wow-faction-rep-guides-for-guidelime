"""Faction registry: id -> name, side membership, and grouped display order."""

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
