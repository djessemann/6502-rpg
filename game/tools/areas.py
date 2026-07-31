"""Area maps: the six towns and the twenty-one dungeon floors.

Every map is hand-laid on a character canvas and then handed to GameMap, which
turns it into the on-ROM RLE format. `build_all` returns them in exactly
world.MAP_NAMES[1:] order, so map ids never move.

Two hard interface facts the layouts are built around:

  * the overworld warps every area entrance to cell (12,18) (see world.py), so
    every map here puts its entrance -- and the OB_WARP that leads back out --
    on that exact cell;
  * warps fire when the leader *lands* on their cell, not on arrival, so an
    entrance tile doubles as the exit: step off it and back on to leave.

Objects must sit on walkable cells (the engine finds them by grid coordinate
and the flood-fill check in tools/check_areas.py enforces reachability), so
shop/inn objects live on their building's DOOR metatile and a save object on
the walkable cell in front of its TERMINAL.
"""
import script_text
import world
from maps import GameMap, MF_DUNGEON, MF_SAVE, OB_NPC, OB_CHEST, OB_WARP, \
    OB_SIGN, OB_SHOP, OB_INN, OB_SAVE, OB_TRIG

MSG = {name: i for i, (name, _) in enumerate(script_text.MESSAGES)}

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

# Music track ids (see design/BIBLE.md section 10).
MUS_TOWN = 1
MUS_DUNGEON = 3

# Encounter table ids. 0-8 belong to the overworld (world.OW_ZONES).
ENC = {"CINDER": 9, "TIDE": 10, "STORM": 11, "HOLLOW": 12, "CAUSEWAY": 13,
       "RELAY": 14, "OSSUARY": 15, "EREBUS": 16}

ENTRY = (12, 18)        # every area map is entered here

_chest_flag = 0
_shop_id = 0
_story_flag = 0


# --- the drawing surface ------------------------------------------------------
class Canvas:
    """A grid of legend characters with the few painting verbs a map needs."""

    def __init__(self, w, h, fill):
        self.w, self.h = w, h
        self.g = [[fill] * w for _ in range(h)]

    def put(self, x, y, ch):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.g[y][x] = ch

    def at(self, x, y):
        return self.g[y][x]

    def rect(self, x0, y0, x1, y1, ch):
        """Filled rectangle, inclusive."""
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.g[y][x] = ch
        return self

    def frame(self, x0, y0, x1, y1, ch):
        """Rectangle outline, inclusive."""
        for x in range(max(0, x0), min(self.w, x1 + 1)):
            self.put(x, y0, ch)
            self.put(x, y1, ch)
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.put(x0, y, ch)
            self.put(x1, y, ch)
        return self

    def hall(self, x0, y0, x1, y1, ch, wide=1):
        """L-shaped corridor: along x at y0, then along y at x1."""
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self.rect(x, y0, x, y0 + wide - 1, ch)
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self.rect(x1, y, x1 + wide - 1, y, ch)
        return self

    def vhall(self, x0, y0, x1, y1, ch, wide=1):
        """L-shaped corridor: along y at x0, then along x at y1."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self.rect(x0, y, x0 + wide - 1, y, ch)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self.rect(x, y1, x, y1 + wide - 1, ch)
        return self

    def scatter(self, cells, ch):
        for x, y in cells:
            self.put(x, y, ch)
        return self

    def rows(self):
        return ["".join(r) for r in self.g]


def building(c, x0, y0, x1, y1, doorx, windows=()):
    """A town building: roof block, front wall along its bottom row, one door."""
    c.rect(x0, y0, x1, y1 - 1, '^')
    c.rect(x0, y1, x1, y1, '#')
    for wx in windows:
        c.put(wx, y1, 'W')
    c.put(doorx, y1, 'D')
    return (doorx, y1)


# --- object helpers -----------------------------------------------------------
def _msg(m):
    i = MSG[m]
    return i & 0xFF, i >> 8


def npc(mp, gx, gy, msg, tile=0, facing=1):
    lo, hi = _msg(msg)
    mp.obj(OB_NPC, gx, gy, tile, facing, lo, hi, 0)


def sign(mp, gx, gy, msg):
    lo, hi = _msg(msg)
    mp.obj(OB_SIGN, gx, gy, 0, 0, lo, hi, 0)


def shop(mp, gx, gy, msg):
    global _shop_id
    lo, hi = _msg(msg)
    mp.obj(OB_SHOP, gx, gy, _shop_id, 0, lo, hi, 0)
    _shop_id += 1


def inn(mp, gx, gy, price, msg):
    lo, hi = _msg(msg)
    mp.obj(OB_INN, gx, gy, price & 0xFF, price >> 8, lo, hi, 0)


def save(mp, gx, gy, msg):
    lo, hi = _msg(msg)
    mp.obj(OB_SAVE, gx, gy, 0, 0, lo, hi, 0)


def chest(mp, gx, gy, item=0, count=1, credits=0):
    global _chest_flag
    mp.obj(OB_CHEST, gx, gy, _chest_flag, item, count,
           credits & 0xFF, credits >> 8)
    _chest_flag += 1


def trig(mp, gx, gy, script, msg):
    global _story_flag
    lo, hi = _msg(msg)
    mp.obj(OB_TRIG, gx, gy, _story_flag, script, lo, hi, 0)
    _story_flag += 1


def exit_warp(mp, site):
    """The way back to the overworld, on the entrance cell."""
    x, y = world.SITES[site]
    mp.obj(OB_WARP, ENTRY[0], ENTRY[1], world.MAP_ID["OVERWORLD"], x, y + 1, 1, 0)


def stair(mp, gx, gy, dest, dx, dy):
    mp.obj(OB_WARP, gx, gy, world.MAP_ID[dest], dx, dy, 0, 0)


def _town(name, ts, c):
    """Wrap a finished town canvas: no encounters, a save terminal on board."""
    return GameMap(name, ts, TOWN_LEGEND, c.rows(), music=MUS_TOWN,
                   enc_zone=0xFF, enc_rate=0, flags=MF_DUNGEON | MF_SAVE)


# =============================================================================
# Towns.  All 32x24; the gate is the entry cell (12,18) in the south perimeter
# and rows 19-23 are the approach outside it.
# =============================================================================
def landfall(ts):
    """The ark's nose section, standing on its face. Deck plate underfoot."""
    c = Canvas(32, 24, '=')
    c.rect(0, 19, 31, 23, '.')                     # the ash outside the hull
    c.rect(12, 19, 12, 23, '=')                    # the road in
    c.scatter([(6, 20), (7, 22), (23, 20), (25, 22), (18, 21)], 'X')
    c.frame(0, 0, 31, 18, '#')                     # the hull
    c.put(12, 18, '=')                             # the gate

    building(c, 2, 1, 9, 5, 5, windows=(3, 8))     # medical bay
    building(c, 12, 1, 17, 4, 14, windows=(16,))
    building(c, 21, 1, 28, 5, 24, windows=(22, 27))    # inn
    building(c, 2, 8, 8, 11, 5, windows=(3, 7))        # supplies
    building(c, 11, 8, 17, 11, 14, windows=(12, 16))
    building(c, 22, 8, 28, 11, 25, windows=(23, 27))   # arms
    building(c, 2, 14, 7, 16, 4, windows=(6,))
    building(c, 24, 14, 29, 16, 26, windows=(25,))

    c.put(5, 6, 'S')                               # the stair up from the cells
    c.rect(10, 13, 20, 16, '"')                    # hydroponics
    c.scatter([(11, 14), (13, 14), (15, 14), (17, 14), (19, 14)], 'P')
    c.put(10, 17, 'T')
    c.scatter([(20, 6), (21, 7), (9, 12), (19, 12)], 'X')

    m = _town("LANDFALL", ts, c)
    exit_warp(m, "LANDFALL")
    inn(m, 24, 5, 20, "MSG_LANDFALL_INN")
    shop(m, 5, 11, "MSG_LANDFALL_SHOP")
    shop(m, 25, 11, "MSG_LANDFALL_ARMS")
    save(m, 10, 16, "MSG_LANDFALL_SAVE")
    npc(m, 6, 6, "MSG_LANDFALL_NPC1")
    npc(m, 19, 6, "MSG_LANDFALL_NPC2")
    npc(m, 15, 17, "MSG_LANDFALL_NPC3")
    npc(m, 7, 12, "MSG_LANDFALL_NPC4")
    npc(m, 9, 17, "MSG_LANDFALL_NPC5")
    npc(m, 24, 7, "MSG_LANDFALL_NPC7")
    return m


def ember_rest(ts):
    """Three ash-block terraces cut into the black glass, stairs between."""
    c = Canvas(32, 24, '.')
    c.rect(0, 19, 31, 23, '.')
    c.rect(12, 19, 12, 23, ',')
    c.scatter([(5, 20), (9, 22), (20, 20), (26, 21), (16, 22)], 'F')
    c.frame(0, 0, 31, 18, '#')
    c.put(12, 18, ',')

    c.rect(1, 6, 30, 6, '#')                       # terrace face
    c.rect(1, 12, 30, 12, '#')
    c.put(10, 6, 'S')
    c.put(19, 6, 'S')
    c.put(9, 12, 'S')
    c.put(20, 12, 'S')

    building(c, 2, 1, 9, 4, 5, windows=(3, 8))     # inn
    building(c, 13, 1, 18, 4, 15, windows=(17,))
    building(c, 23, 1, 29, 4, 26, windows=(24, 28))    # arms
    building(c, 2, 7, 8, 10, 5, windows=(3, 7))        # supplies
    building(c, 12, 7, 17, 10, 14, windows=(16,))
    building(c, 21, 7, 27, 10, 24, windows=(22, 26))
    building(c, 2, 13, 6, 16, 4, windows=(5,))
    building(c, 25, 13, 29, 16, 27, windows=(26,))

    c.rect(1, 5, 30, 5, ',')                       # terrace walkways
    c.rect(1, 11, 30, 11, ',')
    c.rect(1, 17, 30, 17, ',')
    c.put(15, 15, 'T')
    c.scatter([(11, 3), (20, 2), (10, 9), (19, 8), (12, 14), (22, 15)], 'X')

    m = _town("EMBERREST", ts, c)
    exit_warp(m, "EMBERREST")
    inn(m, 5, 4, 18, "MSG_EMBER_INN")
    shop(m, 5, 10, "MSG_EMBER_SHOP")
    shop(m, 26, 4, "MSG_EMBER_ARMS")
    save(m, 15, 16, "MSG_EMBER_SAVE")
    npc(m, 7, 5, "MSG_EMBER_NPC1")
    npc(m, 20, 5, "MSG_EMBER_NPC2")
    npc(m, 10, 11, "MSG_EMBER_NPC3")
    npc(m, 19, 11, "MSG_EMBER_NPC4")
    npc(m, 8, 17, "MSG_EMBER_NPC6")
    npc(m, 22, 17, "MSG_EMBER_NPC8")
    return m


def kelphold(ts):
    """Platforms and boardwalks on stilts; everything else is open water."""
    c = Canvas(32, 24, '~')
    c.rect(11, 5, 13, 20, '=')                     # the long pier
    c.rect(19, 5, 20, 17, '=')                     # the second pier
    c.rect(3, 5, 28, 6, '=')                       # upper quay
    c.rect(3, 10, 28, 11, '=')                     # middle quay
    c.rect(3, 16, 28, 17, '=')                     # lower quay

    building(c, 2, 1, 9, 4, 5, windows=(3, 8))     # inn, top floor, dry for now
    building(c, 14, 1, 18, 4, 16, windows=(17,))
    building(c, 22, 1, 29, 4, 25, windows=(23, 28))    # arms
    building(c, 2, 7, 8, 9, 5, windows=(7,))           # sealed goods
    building(c, 14, 7, 18, 9, 16, windows=(17,))
    building(c, 24, 7, 29, 9, 26, windows=(25,))
    building(c, 2, 12, 8, 15, 5, windows=(3, 7))
    building(c, 24, 12, 29, 15, 26, windows=(25,))

    c.put(15, 17, 'T')
    c.scatter([(4, 6), (27, 5), (10, 11), (21, 10), (5, 17), (27, 16)], 'X')
    kelp = [(1, 8), (1, 14), (9, 18), (16, 12), (17, 14), (22, 18), (30, 7),
            (30, 13), (6, 21), (17, 21), (25, 20), (2, 19), (29, 19)]
    c.scatter(kelp, 'P')

    m = _town("KELPHOLD", ts, c)
    exit_warp(m, "KELPHOLD")
    inn(m, 5, 4, 24, "MSG_KELPHOLD_INN")
    shop(m, 5, 9, "MSG_KELPHOLD_SHOP")
    shop(m, 25, 4, "MSG_KELPHOLD_ARMS")
    save(m, 15, 16, "MSG_KELPHOLD_SAVE")
    npc(m, 8, 5, "MSG_KELPHOLD_NPC1")
    npc(m, 22, 6, "MSG_KELPHOLD_NPC2")
    npc(m, 9, 11, "MSG_KELPHOLD_NPC3")
    npc(m, 23, 10, "MSG_KELPHOLD_NPC5")
    npc(m, 8, 17, "MSG_KELPHOLD_NPC6")
    npc(m, 24, 17, "MSG_KELPHOLD_NPC9")
    return m


def high_mesa(ts):
    """Two shelves of a cliff, stitched by two stairs. Everything strapped down."""
    c = Canvas(32, 24, ',')
    c.rect(0, 19, 31, 23, ',')
    c.rect(12, 19, 12, 23, '.')
    c.scatter([(4, 20), (8, 22), (21, 20), (27, 21), (17, 22)], 'X')
    c.frame(0, 0, 31, 18, '#')
    c.put(12, 18, ',')

    c.rect(1, 10, 30, 11, '#')                     # the cliff face
    c.rect(8, 10, 8, 11, 'S')
    c.rect(23, 10, 23, 11, 'S')

    building(c, 3, 1, 10, 4, 6, windows=(4, 9))        # inn
    building(c, 13, 1, 18, 4, 15, windows=(17,))
    building(c, 21, 1, 28, 4, 24, windows=(22, 27))    # grounded plate
    building(c, 3, 6, 8, 8, 5, windows=(7,))
    building(c, 23, 6, 28, 8, 25, windows=(24,))
    building(c, 2, 13, 7, 16, 5, windows=(3, 6))       # cells, kits and rope
    building(c, 24, 13, 29, 16, 26, windows=(25, 28))

    c.scatter([(11, 12), (13, 12), (15, 12), (17, 12), (19, 12), (21, 12)], 'F')
    c.put(10, 16, 'T')
    c.scatter([(12, 7), (20, 6), (14, 14), (18, 15), (27, 17), (2, 17)], 'X')

    m = _town("HIGHMESA", ts, c)
    exit_warp(m, "HIGHMESA")
    inn(m, 6, 4, 30, "MSG_MESA_INN")
    shop(m, 5, 16, "MSG_MESA_SHOP")
    shop(m, 24, 4, "MSG_MESA_ARMS")
    save(m, 10, 17, "MSG_MESA_SAVE")
    npc(m, 12, 5, "MSG_MESA_NPC1")
    npc(m, 19, 7, "MSG_MESA_NPC2")
    npc(m, 8, 16, "MSG_MESA_NPC3")
    npc(m, 14, 17, "MSG_MESA_NPC4")
    npc(m, 20, 16, "MSG_MESA_NPC5")
    npc(m, 26, 17, "MSG_MESA_NPC9")
    return m


def dustgate(ts):
    """A buried town: only the roofs show. The streets are dug trenches."""
    c = Canvas(32, 24, '^')
    c.rect(0, 19, 31, 23, ',')
    c.scatter([(4, 20), (9, 21), (17, 20), (23, 22), (28, 20)], '^')
    c.rect(12, 19, 12, 23, ',')
    c.frame(0, 0, 31, 18, '#')
    c.put(12, 18, ',')

    c.rect(11, 13, 13, 17, ',')                    # the way up from the gate
    c.rect(3, 13, 28, 14, ',')                     # lower street
    c.rect(3, 8, 28, 9, ',')                       # middle street
    c.rect(3, 3, 28, 4, ',')                       # upper street
    c.rect(6, 4, 7, 13, ',')                       # west cut
    c.rect(11, 4, 13, 13, ',')                     # centre cut
    c.rect(17, 4, 18, 13, ',')                     # east cut
    c.rect(24, 4, 25, 13, ',')                     # far cut

    c.rect(8, 7, 10, 7, '#')                       # frontages dug clear
    c.put(9, 7, 'D')                               # the inn
    c.rect(20, 10, 22, 10, '#')
    c.put(21, 10, 'D')                             # dig stock
    c.rect(8, 15, 10, 15, '#')
    c.put(9, 15, 'D')                              # weighted gear
    c.put(15, 14, 'T')
    c.scatter([(4, 3), (27, 4), (14, 8), (23, 9), (26, 13), (5, 14)], 'X')

    m = _town("DUSTGATE", ts, c)
    exit_warp(m, "DUSTGATE")
    inn(m, 9, 7, 35, "MSG_DUSTGATE_INN")
    shop(m, 21, 10, "MSG_DUSTGATE_SHOP")
    shop(m, 9, 15, "MSG_DUSTGATE_ARMS")
    save(m, 15, 13, "MSG_DUSTGATE_SAVE")
    npc(m, 5, 3, "MSG_DUSTGATE_NPC1")
    npc(m, 20, 4, "MSG_DUSTGATE_NPC2")
    npc(m, 5, 9, "MSG_DUSTGATE_NPC3")
    npc(m, 26, 8, "MSG_DUSTGATE_NPC5")
    npc(m, 8, 13, "MSG_DUSTGATE_NPC7")
    npc(m, 22, 14, "MSG_DUSTGATE_NPC9")
    return m


def last_port(ts):
    """A staging camp behind a rampart, a hundred paces from the Rift rail."""
    c = Canvas(32, 24, '.')
    c.rect(0, 19, 31, 23, '.')
    c.rect(12, 19, 12, 22, '=')
    c.rect(1, 22, 30, 22, 'F')                     # the rail on the rim
    c.put(12, 22, '=')
    c.frame(0, 0, 31, 18, '#')
    c.put(12, 18, '=')

    c.rect(11, 1, 13, 17, '=')                     # the muster road
    c.rect(1, 9, 30, 10, '=')

    building(c, 3, 2, 9, 5, 6, windows=(4, 8))         # inn
    building(c, 16, 2, 22, 5, 19, windows=(17, 21))    # buy heavy
    building(c, 24, 2, 29, 5, 26, windows=(25,))       # best plate
    building(c, 3, 12, 9, 15, 6, windows=(4, 8))
    building(c, 16, 12, 22, 15, 19, windows=(17, 21))
    building(c, 24, 12, 29, 15, 26, windows=(25,))

    c.put(16, 17, 'T')
    c.scatter([(5, 7), (7, 7), (25, 7), (27, 7), (5, 17), (7, 17),
               (25, 17), (27, 17), (2, 11), (29, 11)], 'X')

    m = _town("LASTPORT", ts, c)
    exit_warp(m, "LASTPORT")
    inn(m, 6, 5, 40, "MSG_PORT_INN")
    shop(m, 19, 5, "MSG_PORT_SHOP")
    shop(m, 26, 5, "MSG_PORT_ARMS")
    save(m, 16, 16, "MSG_PORT_SAVE")
    npc(m, 6, 7, "MSG_PORT_NPC2")
    npc(m, 20, 7, "MSG_PORT_NPC3")
    npc(m, 8, 9, "MSG_PORT_NPC4")
    npc(m, 24, 10, "MSG_PORT_NPC5")
    npc(m, 8, 16, "MSG_PORT_NPC6")
    npc(m, 21, 17, "MSG_PORT_NPC8")
    return m


# =============================================================================
# Dungeons.  Anchor floors are 40x32; the rock is WALL and the plan is carved
# out of it.  Floor 1 of every dungeon is entered at (12,18) through a DOOR.
# =============================================================================
def carve(w, h, rooms, floor):
    """Cut a list of (x0,y0,x1,y1) rooms and corridors out of solid rock."""
    c = Canvas(w, h, '#')
    for x0, y0, x1, y1 in rooms:
        c.rect(x0, y0, x1, y1, floor)
    return c


def _dmap(name, ts, c, zone, rate=14, flags=MF_DUNGEON, mirror=False):
    rows = c.rows()
    if mirror:
        rows = [r[::-1] for r in rows]
    return GameMap(name, ts, DUN_LEGEND, rows, music=MUS_DUNGEON,
                   enc_zone=zone, enc_rate=rate, flags=flags)


# --- CINDER: a radial plant around one great vent gallery ---------------------
def cinder1(ts):
    c = carve(40, 32, [
        (9, 19, 15, 24),          # the porch, out on the vent field
        (7, 12, 18, 17),          # entry hall
        (2, 20, 6, 26),           # west cistern
        (7, 22, 8, 22),           # cistern link
        (12, 8, 13, 11),          # north corridor
        (5, 3, 19, 7),            # pump room
        (19, 14, 29, 15),         # east corridor
        (26, 9, 35, 20),          # vent gallery
        (32, 8, 33, 8),           # gallery link
        (30, 4, 36, 7),           # upper cell
    ], '%')
    c.put(12, 18, 'D')
    c.rect(8, 4, 11, 5, '~')
    c.rect(29, 12, 32, 13, '~')
    c.scatter([(14, 4), (16, 4), (14, 6), (16, 6),
               (28, 17), (31, 17), (34, 17), (34, 11)], 'I')
    c.scatter([(3, 25), (6, 20), (35, 6)], 'R')
    c.put(33, 19, '>')

    m = _dmap("CINDER1", ts, c, ENC["CINDER"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "CINDER")
    sign(m, 12, 19, "MSG_STORY_CINDER_ARRIVE")
    trig(m, 12, 17, 1, "MSG_STORY_CINDER_DOOR")
    save(m, 14, 22, "MSG_SYS_SAVED")
    chest(m, 4, 24, credits=120)
    chest(m, 33, 5, credits=200)
    chest(m, 17, 4, credits=90)
    stair(m, 33, 19, "CINDER2", 33, 20)
    return m


def cinder2(ts):
    c = carve(40, 32, [
        (28, 16, 36, 23),         # arrival
        (18, 19, 27, 20),         # west corridor
        (8, 14, 19, 24),          # great vent hall
        (12, 13, 13, 13),         # hall link
        (10, 4, 16, 12),          # upper chamber
        (17, 7, 30, 8),           # north corridor
        (31, 3, 37, 10),          # north-east chamber
        (10, 25, 11, 25),         # south link
        (4, 26, 20, 27),          # south corridor
        (2, 22, 5, 29),           # sump
        (21, 27, 23, 27),         # sump link east
        (24, 26, 33, 30),         # south-east cell
    ], '%')
    c.rect(33, 5, 35, 8, '~')
    c.rect(12, 17, 15, 19, '~')
    c.scatter([(10, 15), (17, 15), (10, 23), (17, 23), (13, 22),
               (30, 18), (34, 18), (30, 22), (26, 28), (30, 28)], 'I')
    c.scatter([(5, 27), (19, 26), (11, 6)], 'R')
    c.put(33, 20, '<')
    c.put(33, 27, '>')

    m = _dmap("CINDER2", ts, c, ENC["CINDER"])
    stair(m, 33, 20, "CINDER1", 33, 19)
    stair(m, 33, 27, "CINDER3", 5, 17)
    sign(m, 18, 20, "MSG_SYS_TERMINAL_LOG")
    chest(m, 3, 28, credits=160)
    chest(m, 34, 4, credits=240)
    chest(m, 12, 6, credits=110)
    chest(m, 27, 29, credits=300)
    return m


# --- the shared Anchor core floor --------------------------------------------
# All four Anchors were cut from the same drive core and built to one plan:
# an approach, a ringed core chamber, three service cells hung off it.
def anchor_core(name, ts, zone, floor, hazard, up_dest, up_cell, msg_core,
                chest_credits, mirror=False, decor=()):
    c = carve(40, 32, [
        (2, 14, 9, 21),           # arrival
        (10, 17, 19, 18),         # approach
        (20, 10, 33, 25),         # core chamber
        (11, 4, 18, 9),           # west gallery
        (14, 10, 15, 16),         # gallery link
        (6, 22, 6, 23),           # sump link
        (4, 24, 12, 29),          # sump
        (32, 8, 35, 9),           # north link
        (34, 3, 38, 10),          # north cell
    ], floor)
    c.rect(23, 13, 30, 13, hazard)
    c.rect(23, 20, 30, 20, hazard)
    c.rect(25, 15, 28, 18, 'O')                # the drive ring
    c.scatter([(21, 11), (32, 11), (21, 24), (32, 24),
               (21, 17), (32, 17)], 'I')
    c.scatter(decor, 'R')
    c.put(5, 17, '<')

    fx = (lambda x: 39 - x) if mirror else (lambda x: x)
    m = _dmap(name, ts, c, zone, mirror=mirror)
    stair(m, fx(5), 17, up_dest, up_cell[0], up_cell[1])
    trig(m, fx(24), 17, 2, msg_core)
    sign(m, fx(12), 18, "MSG_SYS_TERMINAL_LOG")
    chest(m, fx(15), 6, credits=chest_credits[0])
    chest(m, fx(8), 27, credits=chest_credits[1])
    chest(m, fx(36), 5, credits=chest_credits[2])
    return m


# --- TIDE: flooded terraces, kelp streets ------------------------------------
def tide1(ts):
    c = carve(40, 32, [
        (9, 19, 15, 24),          # the stair head
        (6, 12, 19, 17),          # dry hall
        (2, 4, 10, 11),           # west terrace
        (20, 14, 30, 15),         # east corridor
        (28, 8, 37, 22),          # flooded gallery
        (32, 3, 37, 7),           # upper cell
        (16, 22, 26, 23),         # south corridor
        (22, 24, 28, 29),         # south cell
    ], ',')
    c.put(12, 18, 'D')
    c.rect(30, 10, 35, 13, 'c')
    c.rect(3, 6, 8, 9, 'c')
    c.rect(23, 26, 27, 28, 'c')
    c.scatter([(30, 17), (33, 17), (36, 17), (30, 20), (33, 20),
               (8, 14), (12, 14), (16, 14)], 'I')
    c.scatter([(19, 22), (5, 11)], 'R')
    c.put(33, 21, '>')

    m = _dmap("TIDE1", ts, c, ENC["TIDE"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "TIDE")
    sign(m, 12, 19, "MSG_STORY_TIDE_ARRIVE")
    trig(m, 12, 17, 1, "MSG_STORY_TIDE_DOOR")
    save(m, 13, 21, "MSG_SYS_SAVED")
    chest(m, 4, 10, credits=180)
    chest(m, 34, 5, credits=260)
    chest(m, 25, 28, credits=140)
    stair(m, 33, 21, "TIDE2", 33, 20)
    return m


def tide2(ts):
    c = carve(40, 32, [
        (30, 17, 37, 24),         # arrival
        (18, 20, 29, 21),         # east street
        (8, 16, 19, 26),          # the kelp city square
        (2, 18, 7, 23),           # a drowned house
        (10, 6, 17, 15),          # north hall
        (18, 8, 29, 9),           # north street
        (30, 4, 37, 12),          # north-east hall
        (4, 4, 9, 12),            # north-west cell
        (12, 27, 24, 28),         # south street
        (25, 26, 32, 31),         # south cell
    ], ',')
    c.rect(10, 18, 14, 20, 'c')
    c.rect(32, 6, 35, 10, 'c')
    c.rect(26, 28, 30, 30, 'c')
    c.rect(3, 20, 6, 22, 'c')
    c.scatter([(16, 18), (16, 22), (10, 24), (16, 24),
               (32, 19), (35, 19), (32, 23), (12, 8), (15, 12)], 'I')
    c.scatter([(20, 28), (8, 6)], 'R')
    c.put(33, 20, '<')
    c.put(29, 29, '>')

    m = _dmap("TIDE2", ts, c, ENC["TIDE"])
    stair(m, 33, 20, "TIDE1", 33, 21)
    stair(m, 29, 29, "TIDE3", 5, 17)
    sign(m, 12, 16, "MSG_SYS_TERMINAL_LOG")
    chest(m, 5, 5, credits=220)
    chest(m, 36, 5, credits=340)
    chest(m, 3, 23, credits=150)
    chest(m, 14, 25, credits=200)
    return m


# --- STORM: a tower, climbed by gantries around an open shaft -----------------
def storm1(ts):
    c = carve(40, 32, [
        (9, 19, 15, 24),          # the mast foot
        (10, 10, 16, 17),         # lower gantry
        (17, 12, 28, 13),         # east gantry
        (26, 4, 33, 20),          # the shaft
        (3, 6, 9, 14),            # generator room
        (3, 20, 8, 27),           # cable vault
        (14, 25, 14, 27),         # vault stair
        (14, 26, 30, 27),         # south gantry
        (31, 24, 37, 30),         # south-east cell
    ], '.')
    c.put(12, 18, 'D')
    c.scatter([(28, 7), (31, 7), (28, 11), (31, 11), (28, 15), (31, 15),
               (28, 19), (31, 19), (5, 8), (7, 12), (12, 12), (15, 16)], 'I')
    c.rect(3, 6, 9, 6, '=')
    c.rect(3, 27, 8, 27, '=')
    c.rect(17, 12, 28, 12, '=')
    c.scatter([(35, 29), (19, 27)], 'R')
    c.put(30, 5, '>')

    m = _dmap("STORM1", ts, c, ENC["STORM"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "STORM")
    sign(m, 12, 19, "MSG_STORY_STORM_ARRIVE")
    trig(m, 12, 17, 1, "MSG_STORY_STORM_DOOR")
    save(m, 13, 21, "MSG_SYS_SAVED")
    chest(m, 5, 13, credits=280)
    chest(m, 5, 25, credits=210)
    chest(m, 34, 28, credits=360)
    stair(m, 30, 5, "STORM2", 30, 6)
    return m


def storm2(ts):
    c = carve(40, 32, [
        (28, 4, 35, 11),          # arrival
        (16, 7, 27, 8),           # high gantry
        (6, 4, 15, 14),           # west platform
        (10, 15, 11, 17),         # platform stair
        (4, 18, 15, 25),          # lower platform
        (16, 24, 29, 25),         # south gantry
        (30, 16, 37, 27),         # east platform
        (20, 12, 27, 17),         # coil cell
        (23, 9, 24, 11),          # coil stair
        (30, 12, 33, 15),         # east link
    ], '.')
    c.scatter([(8, 6), (13, 6), (8, 12), (13, 12), (6, 20), (13, 20),
               (6, 24), (13, 24), (32, 18), (35, 18), (32, 25), (35, 25),
               (22, 14), (25, 14)], 'I')
    c.rect(16, 7, 27, 7, '=')
    c.rect(16, 25, 29, 25, '=')
    c.scatter([(9, 22), (26, 24)], 'R')
    c.put(30, 6, '<')
    c.put(34, 26, '>')

    m = _dmap("STORM2", ts, c, ENC["STORM"])
    stair(m, 30, 6, "STORM1", 30, 5)
    stair(m, 34, 26, "STORM3", 34, 17)
    sign(m, 18, 8, "MSG_SYS_TERMINAL_LOG")
    chest(m, 7, 5, credits=300)
    chest(m, 5, 24, credits=250)
    chest(m, 26, 16, credits=420)
    chest(m, 36, 20, credits=380)
    return m


# --- HOLLOW: the buried city, streets in a grid -------------------------------
def hollow1(ts):
    c = carve(40, 32, [
        (9, 19, 15, 24),          # the shaft foot
        (4, 16, 35, 17),          # main street
        (4, 6, 35, 7),            # north street
        (4, 26, 35, 27),          # south street
        (6, 6, 7, 27),            # west avenue
        (18, 6, 19, 27),          # centre avenue
        (30, 6, 31, 27),          # east avenue
        (12, 8, 12, 8),           # doorways
        (24, 8, 24, 8),
        (24, 18, 24, 18),
        (32, 12, 32, 12),
        (8, 9, 17, 14),           # block interiors
        (21, 9, 28, 14),
        (20, 19, 28, 24),
        (33, 10, 37, 14),
        (2, 10, 5, 14),
    ], '.')
    c.put(12, 18, 'D')
    c.scatter([(10, 11), (15, 11), (10, 13), (15, 13),
               (23, 11), (26, 11), (22, 21), (26, 21)], 'I')
    c.rect(34, 11, 36, 13, ' ')
    c.rect(3, 11, 4, 13, ' ')
    c.scatter([(9, 6), (27, 27), (33, 17)], 'R')
    c.put(34, 26, '>')

    m = _dmap("HOLLOW1", ts, c, ENC["HOLLOW"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "HOLLOW")
    sign(m, 12, 19, "MSG_STORY_HOLLOW_ARRIVE")
    trig(m, 12, 17, 1, "MSG_STORY_HOLLOW_DOOR")
    save(m, 13, 21, "MSG_SYS_SAVED")
    chest(m, 12, 12, credits=340)
    chest(m, 24, 22, credits=400)
    chest(m, 2, 10, credits=260)
    stair(m, 34, 26, "HOLLOW2", 33, 27)
    return m


def hollow2(ts):
    c = carve(40, 32, [
        (30, 24, 37, 30),         # arrival
        (18, 26, 29, 27),         # low street
        (6, 20, 17, 29),          # the sunken plaza
        (2, 14, 7, 19),           # west cell
        (10, 10, 17, 19),         # north-west hall
        (18, 12, 29, 13),         # upper street
        (30, 6, 37, 16),          # east hall
        (20, 3, 27, 10),          # north cell
        (24, 11, 24, 11),         # north doorway
        (9, 10, 9, 10),           # west doorway
        (4, 4, 9, 9),             # far cell
    ], '.')
    c.scatter([(8, 22), (15, 22), (8, 27), (15, 27),
               (12, 12), (15, 16), (32, 8), (35, 8), (32, 14), (35, 14)], 'I')
    c.rect(11, 23, 13, 26, ' ')
    c.rect(21, 5, 26, 8, ' ')
    c.scatter([(19, 27), (5, 19), (33, 16)], 'R')
    c.put(33, 27, '<')
    c.put(34, 10, '>')

    m = _dmap("HOLLOW2", ts, c, ENC["HOLLOW"])
    stair(m, 33, 27, "HOLLOW1", 34, 26)
    stair(m, 34, 10, "HOLLOW3", 34, 17)
    sign(m, 12, 19, "MSG_SYS_TERMINAL_LOG")
    chest(m, 5, 5, credits=380)
    chest(m, 3, 17, credits=300)
    chest(m, 20, 4, credits=460)
    chest(m, 9, 28, credits=340)
    return m


# --- the Sunken Causeway: one long road under the shelf -----------------------
def causeway(ts):
    c = carve(48, 24, [
        (9, 19, 15, 22),          # the mouth
        (8, 12, 17, 17),          # west pump hall
        (18, 14, 27, 15),         # first span
        (26, 10, 35, 19),         # mid pump hall
        (36, 14, 43, 15),         # second span
        (40, 4, 46, 13),          # far hall
        (4, 12, 8, 13),           # west link
        (2, 4, 7, 11),            # west cell
        (22, 10, 22, 13),         # north stair
        (18, 4, 25, 9),           # north cell
        (30, 20, 38, 22),         # south cell
    ], ',')
    c.put(12, 18, 'D')
    c.rect(28, 12, 33, 13, 'c')
    c.rect(3, 6, 6, 9, 'c')
    c.rect(42, 6, 45, 9, 'c')
    c.scatter([(28, 16), (31, 16), (34, 16), (10, 14), (15, 14),
               (20, 5), (23, 8), (33, 21)], 'I')
    c.scatter([(17, 12), (37, 19)], 'R')

    m = _dmap("CAUSEWAY", ts, c, ENC["CAUSEWAY"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "REEF")
    tx, ty = world.SITES["TIDE"]
    m.obj(OB_WARP, 44, 6, world.MAP_ID["OVERWORLD"], tx, ty + 1, 1, 0)
    sign(m, 12, 19, "MSG_STORY_CAUSEWAY_1")
    trig(m, 30, 14, 1, "MSG_STORY_CAUSEWAY_2")
    save(m, 13, 20, "MSG_SYS_SAVED")
    chest(m, 4, 5, credits=160)
    chest(m, 21, 5, credits=200)
    chest(m, 36, 21, credits=240)
    return m


# --- Relay Nine: a comms tower with nothing left to talk to -------------------
def relay1(ts):
    c = carve(32, 24, [
        (9, 19, 15, 22),          # the tower porch
        (8, 12, 17, 17),          # lobby
        (7, 12, 7, 12),           # west doorway
        (3, 5, 10, 11),           # transformer room
        (18, 14, 27, 15),         # spine
        (21, 5, 29, 13),          # dish room
    ], '.')
    c.put(12, 18, 'D')
    c.rect(3, 5, 10, 5, '=')
    c.rect(21, 5, 29, 5, '=')
    c.scatter([(23, 8), (27, 8), (23, 11), (27, 11), (10, 14), (15, 14)], 'I')
    c.scatter([(9, 17), (19, 15)], 'R')
    c.put(26, 7, '>')

    m = _dmap("RELAY1", ts, c, ENC["RELAY"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "RELAY")
    sign(m, 12, 19, "MSG_STORY_RELAY_1")
    trig(m, 12, 17, 1, "MSG_STORY_RELAY_2")
    save(m, 13, 20, "MSG_SYS_SAVED")
    chest(m, 5, 7, credits=300)
    chest(m, 28, 6, credits=450)
    stair(m, 26, 7, "RELAY2", 5, 17)
    return m


def relay2(ts):
    c = carve(32, 24, [
        (2, 14, 9, 21),           # arrival
        (10, 17, 19, 18),         # approach
        (14, 6, 27, 16),          # the dish hall
        (24, 3, 30, 8),           # upper cell
        (11, 7, 13, 7),           # west doorway
        (3, 4, 10, 11),           # west cell
    ], '.')
    c.rect(19, 10, 22, 13, 'O')                # the array
    c.scatter([(16, 8), (25, 8), (16, 15), (25, 15), (4, 6), (9, 6)], 'I')
    c.rect(3, 11, 10, 11, '=')
    c.put(5, 17, '<')

    m = _dmap("RELAY2", ts, c, ENC["RELAY"])
    stair(m, 5, 17, "RELAY1", 26, 7)
    trig(m, 18, 12, 3, "MSG_STORY_RELAY_3")
    sign(m, 12, 18, "MSG_STORY_RELAY_4")
    sign(m, 23, 15, "MSG_STORY_RELAY_6")
    chest(m, 5, 6, credits=500)
    chest(m, 28, 5, credits=650)
    return m


# --- the Ossuary: two levels of teeth, sorted by size -------------------------
def ossuary1(ts):
    c = carve(32, 24, [
        (9, 19, 15, 22),          # the mouth
        (7, 13, 17, 18),          # first lobe
        (18, 15, 25, 16),         # the gullet
        (20, 6, 29, 14),          # second lobe
        (2, 6, 10, 12),           # west lobe
        (3, 16, 6, 21),           # side pocket
    ], '%')
    c.put(12, 18, 'D')
    c.scatter([(4, 8), (8, 8), (4, 11), (22, 8), (26, 8), (22, 12), (26, 12),
               (9, 15), (14, 15), (5, 19)], 'R')
    c.put(27, 8, '>')

    m = _dmap("OSSUARY1", ts, c, ENC["OSSUARY"], rate=18)
    exit_warp(m, "OSSUARY")
    sign(m, 12, 19, "MSG_STORY_OSSUARY_1")
    trig(m, 12, 17, 1, "MSG_STORY_OSSUARY_2")
    chest(m, 4, 20, credits=400)
    chest(m, 24, 13, credits=520)
    chest(m, 3, 7, credits=360)
    stair(m, 27, 8, "OSSUARY2", 5, 17)
    return m


def ossuary2(ts):
    c = carve(32, 24, [
        (2, 14, 9, 21),           # arrival
        (10, 17, 19, 18),         # throat
        (16, 16, 16, 16),         # the gullet
        (13, 4, 28, 15),          # the nest
        (12, 7, 12, 7),           # west gap
        (3, 4, 11, 10),           # bone pocket
        (26, 16, 26, 16),         # south gap
        (22, 17, 29, 22),         # deep pocket
    ], '%')
    c.scatter([(15, 6), (19, 6), (23, 6), (15, 13), (19, 13), (23, 13),
               (5, 6), (9, 8), (24, 19), (28, 19)], 'R')
    c.put(5, 17, '<')

    m = _dmap("OSSUARY2", ts, c, ENC["OSSUARY"], rate=20)
    stair(m, 5, 17, "OSSUARY1", 27, 8)
    trig(m, 21, 10, 4, "MSG_STORY_OSSUARY_3")
    sign(m, 12, 18, "MSG_SYS_TERMINAL_LOG")
    chest(m, 5, 5, credits=600)
    chest(m, 25, 21, credits=800)
    chest(m, 17, 5, credits=700)
    return m


# --- the Erebus hull: ark corridors nobody in the colony has ever seen --------
def erebus1(ts):
    c = carve(40, 32, [
        (9, 19, 15, 24),          # the airlock
        (8, 12, 17, 17),          # deck one lobby
        (18, 15, 34, 16),         # the spine
        (23, 14, 23, 14),         # bay doors
        (20, 6, 27, 13),
        (32, 13, 32, 14),
        (29, 4, 37, 12),
        (30, 17, 30, 17),
        (28, 18, 36, 25),
        (2, 10, 7, 20),           # port bay
    ], '.')
    c.put(12, 18, 'D')
    c.scatter([(22, 8), (25, 8), (22, 11), (25, 11), (31, 6), (35, 6),
               (31, 10), (35, 10), (30, 20), (34, 20), (30, 24), (34, 24),
               (4, 13), (4, 17)], 'I')
    for a, b in ((18, 22), (24, 29), (34, 34)):
        c.rect(a, 15, b, 15, '=')
    c.put(34, 23, '>')

    m = _dmap("EREBUS1", ts, c, ENC["EREBUS"], flags=MF_DUNGEON | MF_SAVE)
    exit_warp(m, "RIFT")
    sign(m, 12, 19, "MSG_STORY_RIFT_1")
    trig(m, 12, 17, 1, "MSG_STORY_HULL_1")
    save(m, 13, 21, "MSG_SYS_SAVED")
    chest(m, 4, 12, credits=500)
    chest(m, 24, 7, credits=560)
    chest(m, 34, 5, credits=620)
    stair(m, 34, 23, "EREBUS2", 5, 17)
    return m


def erebus2(ts):
    c = carve(40, 32, [
        (2, 14, 9, 21),           # arrival
        (10, 17, 19, 18),         # approach
        (20, 17, 36, 18),         # the spine
        (15, 15, 15, 16),
        (12, 4, 19, 14),          # cold cells
        (25, 16, 25, 16),
        (22, 6, 29, 15),
        (34, 16, 34, 16),
        (31, 6, 37, 15),
        (25, 19, 25, 19),
        (22, 20, 30, 27),
        (34, 19, 34, 19),
        (32, 20, 37, 28),
    ], '.')
    c.scatter([(14, 6), (17, 6), (14, 9), (17, 9), (14, 12), (17, 12),
               (24, 8), (27, 8), (24, 12), (27, 12), (33, 8), (36, 8),
               (24, 22), (28, 22), (24, 26), (28, 26), (34, 22), (36, 26)], 'I')
    for a, b in ((20, 24), (26, 33), (35, 36)):
        c.rect(a, 17, b, 17, '=')
    c.put(5, 17, '<')
    c.put(35, 27, '>')

    m = _dmap("EREBUS2", ts, c, ENC["EREBUS"])
    stair(m, 5, 17, "EREBUS1", 34, 23)
    stair(m, 35, 27, "EREBUS3", 33, 27)
    sign(m, 12, 18, "MSG_STORY_HULL_2")
    trig(m, 15, 5, 5, "MSG_STORY_HULL_3")
    chest(m, 13, 13, credits=680)
    chest(m, 26, 7, credits=720)
    chest(m, 33, 14, credits=760)
    chest(m, 23, 26, credits=800)
    return m


def erebus3(ts):
    c = carve(40, 32, [
        (30, 24, 37, 30),         # arrival
        (18, 26, 29, 27),         # lower corridor
        (6, 20, 17, 29),          # the hangar
        (10, 10, 17, 19),         # the shaft
        (18, 12, 29, 13),         # upper corridor
        (30, 6, 37, 16),          # sentinel hall
        (24, 11, 24, 11),
        (20, 3, 27, 10),          # magazine
        (8, 17, 9, 17),
        (2, 14, 7, 21),           # port bay
    ], '.')
    c.scatter([(8, 22), (15, 22), (8, 27), (15, 27), (12, 12), (15, 16),
               (32, 8), (35, 8), (32, 14), (35, 14), (22, 5), (25, 5),
               (4, 16), (4, 20)], 'I')
    c.rect(18, 26, 29, 26, '=')
    for a, b in ((18, 23), (25, 29)):
        c.rect(a, 12, b, 12, '=')
    c.put(33, 27, '<')
    c.put(34, 10, '>')

    m = _dmap("EREBUS3", ts, c, ENC["EREBUS"])
    stair(m, 33, 27, "EREBUS2", 35, 27)
    stair(m, 34, 10, "EREBUS4", 5, 17)
    sign(m, 12, 20, "MSG_STORY_HULL_4")
    trig(m, 33, 15, 6, "MSG_BOSS_RIFT_SENTINEL")
    chest(m, 4, 18, credits=850)
    chest(m, 23, 4, credits=900)
    chest(m, 12, 26, credits=950)
    return m


def erebus4(ts):
    c = carve(40, 32, [
        (2, 14, 9, 21),           # arrival
        (10, 17, 19, 18),         # the approach
        (20, 8, 35, 26),          # the bridge
    ], '.')
    c.rect(25, 14, 30, 19, 'O')                # the navigator array
    c.scatter([(22, 10), (24, 10), (31, 10), (33, 10),
               (22, 24), (24, 24), (31, 24), (33, 24),
               (22, 17), (33, 17)], 'I')
    c.rect(20, 8, 35, 8, '=')
    c.rect(20, 26, 35, 26, '=')
    c.put(5, 17, '<')

    m = _dmap("EREBUS4", ts, c, ENC["EREBUS"], rate=0, flags=MF_DUNGEON)
    stair(m, 5, 17, "EREBUS3", 34, 10)
    sign(m, 12, 18, "MSG_SYS_TERMINAL_LOG")
    trig(m, 23, 17, 7, "MSG_STORY_ARCHON_1")
    chest(m, 21, 12, credits=1000)
    chest(m, 34, 22, credits=1200)
    return m


# =============================================================================
def build_all(ts_town, ts_dun):
    """Return every area map in world.MAP_NAMES[1:] order."""
    global _chest_flag, _shop_id, _story_flag
    _chest_flag = _shop_id = _story_flag = 0

    maps = {
        "LANDFALL": landfall(ts_town),
        "EMBERREST": ember_rest(ts_town),
        "KELPHOLD": kelphold(ts_town),
        "HIGHMESA": high_mesa(ts_town),
        "DUSTGATE": dustgate(ts_town),
        "LASTPORT": last_port(ts_town),

        "CINDER1": cinder1(ts_dun),
        "CINDER2": cinder2(ts_dun),
        "CINDER3": anchor_core(
            "CINDER3", ts_dun, ENC["CINDER"], '%', '~', "CINDER2", (33, 27),
            "MSG_STORY_CINDER_CORE", (300, 260, 420),
            decor=((7, 26), (16, 8), (37, 9))),

        "TIDE1": tide1(ts_dun),
        "TIDE2": tide2(ts_dun),
        "TIDE3": anchor_core(
            "TIDE3", ts_dun, ENC["TIDE"], ',', 'c', "TIDE2", (29, 29),
            "MSG_STORY_TIDE_CORE", (360, 320, 480),
            decor=((6, 28), (17, 5), (35, 10))),

        "STORM1": storm1(ts_dun),
        "STORM2": storm2(ts_dun),
        "STORM3": anchor_core(
            "STORM3", ts_dun, ENC["STORM"], '.', '=', "STORM2", (34, 26),
            "MSG_STORY_STORM_CORE", (440, 400, 560), mirror=True,
            decor=((5, 25), (12, 5), (38, 4))),

        "HOLLOW1": hollow1(ts_dun),
        "HOLLOW2": hollow2(ts_dun),
        "HOLLOW3": anchor_core(
            "HOLLOW3", ts_dun, ENC["HOLLOW"], '.', ' ', "HOLLOW2", (34, 10),
            "MSG_STORY_HOLLOW_CORE", (520, 480, 640), mirror=True,
            decor=((8, 24), (13, 8), (36, 8))),

        "CAUSEWAY": causeway(ts_dun),
        "RELAY1": relay1(ts_dun),
        "RELAY2": relay2(ts_dun),
        "OSSUARY1": ossuary1(ts_dun),
        "OSSUARY2": ossuary2(ts_dun),
        "EREBUS1": erebus1(ts_dun),
        "EREBUS2": erebus2(ts_dun),
        "EREBUS3": erebus3(ts_dun),
        "EREBUS4": erebus4(ts_dun),
    }
    return [maps[n] for n in world.MAP_NAMES[1:]]
