"""Fallback area maps: one plain room per map id.

Used only when tools/areas.py does not (yet) provide build_all, so that the
content build always produces a complete, linkable set of 28 maps.

Original note:

Every map id in world.MAP_NAMES exists from the first build so map ids never
move; maps that are not designed yet are generated as a plain room with an exit
back to the overworld.
"""
import art_tiles
from maps import GameMap, MF_DUNGEON, OB_NPC, OB_CHEST, OB_WARP, OB_SIGN, \
    OB_SHOP, OB_INN, OB_SAVE, OB_TRIG
import world

TOWN_LEGEND = {
    '.': 'DIRT', ',': 'SAND', '"': 'GRASS', '~': 'WATER', '=': 'PLAZA',
    '#': 'WALL', '^': 'ROOF', 'D': 'DOOR', 'W': 'WINDOW', 'C': 'COUNTER',
    'T': 'TERMINAL', 'X': 'CRATE', 'P': 'PLANT', 'F': 'FENCE', 'S': 'STAIRS',
}

DUN_LEGEND = {
    '.': 'FLOOR', ',': 'GRATE', '%': 'SLAG', ' ': 'VOID', '~': 'LAVA',
    'c': 'COOL', '#': 'WALL', 'I': 'PILLAR', '=': 'PIPE', 'O': 'CORE',
    'D': 'DOOR', '>': 'STAIRD', '<': 'STAIRU', 'H': 'CHEST', 'R': 'RUBBLE',
}


def _room(name, ts, legend, floor, wall, w=24, h=20, music=3, enc=0xFF,
          rate=0, flags=MF_DUNGEON):
    rows = []
    for y in range(h):
        if y == 0 or y == h - 1:
            rows.append(wall * w)
        else:
            rows.append(wall + floor * (w - 2) + wall)
    return GameMap(name, ts, legend, rows, music=music, enc_zone=enc,
                   enc_rate=rate, flags=flags)


def placeholder(name, ts, legend, floor, wall, site, music=3):
    m = _room(name, ts, legend, floor, wall, music=music)
    # exit back to the overworld, one tile below the landmark
    ex, ey = 12, 18
    m.obj(OB_WARP, ex, ey, world.MAP_ID["OVERWORLD"], site[0], site[1] + 1, 1, 0)
    m.obj(OB_WARP, ex, ey - 1, world.MAP_ID["OVERWORLD"], site[0], site[1] + 1, 1, 0)
    return m


SITE_OF = {
    "LANDFALL": "LANDFALL", "EMBERREST": "EMBERREST", "KELPHOLD": "KELPHOLD",
    "HIGHMESA": "HIGHMESA", "DUSTGATE": "DUSTGATE", "LASTPORT": "LASTPORT",
    "CINDER1": "CINDER", "CINDER2": "CINDER", "CINDER3": "CINDER",
    "TIDE1": "TIDE", "TIDE2": "TIDE", "TIDE3": "TIDE",
    "STORM1": "STORM", "STORM2": "STORM", "STORM3": "STORM",
    "HOLLOW1": "HOLLOW", "HOLLOW2": "HOLLOW", "HOLLOW3": "HOLLOW",
    "CAUSEWAY": "REEF", "RELAY1": "RELAY", "RELAY2": "RELAY",
    "OSSUARY1": "OSSUARY", "OSSUARY2": "OSSUARY",
    "EREBUS1": "RIFT", "EREBUS2": "RIFT", "EREBUS3": "RIFT", "EREBUS4": "RIFT",
}

TOWN_MAPS = {"LANDFALL", "EMBERREST", "KELPHOLD", "HIGHMESA", "DUSTGATE",
             "LASTPORT"}


def build_all(ts_town, ts_dun):
    """Return area maps in MAP_NAMES order (excluding the overworld)."""
    out = []
    for name in world.MAP_NAMES[1:]:
        site = world.SITES[SITE_OF[name]]
        if name in TOWN_MAPS:
            m = placeholder(name, ts_town, TOWN_LEGEND, '.', '#', site, music=1)
        else:
            m = placeholder(name, ts_dun, DUN_LEGEND, '.', '#', site, music=3)
        out.append(m)
    return out
