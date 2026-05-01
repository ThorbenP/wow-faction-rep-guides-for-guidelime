"""Questie database file locations and target client interface versions."""

QUESTIE_RAW = 'https://raw.githubusercontent.com/Questie/Questie/master'

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
