"""Hand-authored tileset art for THRENOS.

Ground metatiles are built from a single 8x8 pattern tiled 4x (cheap: one unique
CHR tile each). Features are authored as full 16x16 art (four unique tiles).

Two rules the art here obeys, because the hardware punishes breaking them:

  * **No accidental colour 0.** Colour 0 of every sub-palette is the shared
    backdrop, $0F black. A '.' in a *background* tile is not transparency, it is
    a black hole punched in the ground. Features therefore carry their own
    ground: `on(GROUND, art)` lays 16x16 art over a tiled 8x8 ground pattern and
    only the pixels the art actually draws replace it. '.' is used only where
    black is the intended colour -- a doorway, a cave mouth, the void.
  * **Sub-palette 3 is the UI palette** ($0F/$00/$10/$30 -- black, mid grey,
    light grey, white) and cannot be changed per tileset: the text window is
    drawn in place over the map in it. Anything assigned to sub-palette 3 is
    therefore grey. That is a deliberate choice for stone and fused glass, and
    a mistake for anything that wants to be a colour.
"""
from tileset import (Tileset, PROP_SOLID, PROP_WATER, PROP_HIGH, PROP_ENCTR,
                     PROP_DOOR, PROP_SLOW, PROP_DAMAGE, PROP_COUNTER)

# --- helpers -----------------------------------------------------------------


def quad(t):
    """One 8x8 pattern -> a 16x16 metatile (the same tile four times)."""
    assert len(t) == 8 and all(len(r) == 8 for r in t), t
    return [r + r for r in t] + [r + r for r in t]


def quad2(top, bot):
    """Two 8x8 patterns -> 16x16 (top row of tiles / bottom row of tiles)."""
    return [r + r for r in top] + [r + r for r in bot]


def G(*rows):
    """A literal 16x16 metatile."""
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), rows
    return list(rows)


def peaks(*spec):
    """Build a 16x16 rock mass from triangular peaks.

    Each spec is (apex_x, apex_y, base_y, half_width). The left face of a peak
    takes the light tone, the right face the shade, and a one-pixel dark foot
    is laid under the whole mass. Peaks are drawn in order, so a later peak
    overlaps an earlier one -- which is how a range gets a skyline instead of
    a row of identical triangles.

    Doing this with geometry rather than by typing 16 strings is what makes a
    mountain that is actually symmetric about its ridgeline; hand-typed slopes
    drift by a pixel and read as a lump.
    """
    g = [["_"] * 16 for _ in range(16)]
    for cx, top, base, half in spec:
        span = max(1, base - top)
        for y in range(top, base + 1):
            w = round((y - top) * half / span)
            for x in range(cx - w, cx + w + 1):
                if 0 <= x < 16:
                    # only a narrow band along the ridgeline catches the light;
                    # a whole lit half reads as a wedge, not as rock
                    g[y][x] = "3" if cx - 2 <= x <= cx else "2"
    return ["".join(r) for r in g]


def scree(art, spots, ch="1"):
    """Punch a few dark pits into a rock face so it is not a flat wedge."""
    g = [list(r) for r in art]
    for x, y in spots:
        if g[y][x] in "23":
            g[y][x] = ch
    return ["".join(r) for r in g]


def on(ground, *rows):
    """A 16x16 feature standing on `ground` (an 8x8 pattern, tiled 2x2).

    In `rows`, '_' means "let the ground show through". '.' still means colour
    0, i.e. real black -- use it for openings, not for background.
    """
    assert len(rows) == 16 and all(len(r) == 16 for r in rows), rows
    g = quad(ground)
    return ["".join(b if a == '_' else a for a, b in zip(ar, br))
            for ar, br in zip(rows, g)]


# --- 8x8 ground patterns ------------------------------------------------------
# ASH: the dead plain that covers most of the continent. Kept calm on purpose --
# it is the background the whole game is read against.
ASH = ("11111111",
       "12111121",
       "11111111",
       "11211112",
       "11111111",
       "21111211",
       "11111111",
       "11112111")

# DUNE: wind ripples, so the dune sea is not just "brighter ash".
DUST = ("22222222",
        "23332222",
        "22111222",
        "22222222",
        "22222333",
        "22222111",
        "22222222",
        "32222222")

# SCRUB: dark ground with mid-tone tufts and the odd bright blade.
SCRUB = ("11111111",
         "11211211",
         "11121111",
         "11111131",
         "11111111",
         "21121121",
         "11112111",
         "31111111")

# ROAD: the one bright surface on the overworld, so a road reads as a road.
ROADP = ("33333333",
         "33323333",
         "33333333",
         "32333323",
         "33333333",
         "33333233",
         "33333333",
         "23333332")

SEA = ("11111111",
       "11221111",
       "12332111",
       "11221111",
       "11111111",
       "11112211",
       "11123321",
       "11112211")

DEEP = ("11111111",
        "11111111",
        "11211111",
        "11111112",
        "11111111",
        "12111111",
        "11111121",
        "11111111")

# GLASS: fused ground. Sub-palette 3, so it is the one grey region on the map.
GLASS = ("11111111",
         "12111211",
         "11311111",
         "11111121",
         "21111113",
         "11121111",
         "11111211",
         "13111111")

# MARSH: standing water in blots, so it never reads as SCRUB.
MARSHP = ("11111111",
          "12211221",
          "12211221",
          "11111111",
          "11122111",
          "11122111",
          "11111111",
          "21111112")

# Dungeon floor: mid grey, DARKER than the walls it is cut out of would be if
# they were grey too. Nothing on a dungeon screen should be brighter than lava.
FLOOR = ("11111111",
         "11111111",
         "11211121",
         "11111111",
         "11111111",
         "12111211",
         "11111111",
         "11111111")

# Dungeon wall body: the darkest surface in the tileset, with one mortar course
# for texture. Two rules learned the hard way -- no bright edge (an outline on a
# 16x16 metatile draws a grid across every wall on screen) and nothing near the
# brightness of a floor, or a room stops reading as a room.
WALLP = ("11111111",
         "11111111",
         "11111111",
         "12222221",
         "11111111",
         "11111111",
         "11111111",
         "11111111")

# Deck plate: a LIT floor. Bright enough that a room cut into the wall above
# reads at a glance, which the old dark grating did not.
GRATEP = ("22222222",
          "23222322",
          "22222222",
          "22322232",
          "22222222",
          "32223222",
          "22222222",
          "22232223")

# Coolant: also a lit floor, but flowing rather than riveted, so it is never
# mistaken for grating.
COOLP = ("22222222",
         "23332222",
         "22222222",
         "22223332",
         "22222222",
         "33222223",
         "22222222",
         "22233322")

# Molten: the brightest thing in any dungeon, because it costs HP to stand on.
LAVAP = ("33333333",
         "32233233",
         "33333333",
         "23332323",
         "33333333",
         "33233332",
         "32333333",
         "33332233")

# Slag: cold clinker, dark and grainy.
SLAGP = ("11111111",
         "12111121",
         "11111111",
         "11211112",
         "11121111",
         "21111211",
         "11111111",
         "11112111")

DARK = ("11111111",
        "11111111",
        "11111111",
        "11111111",
        "11111111",
        "11111111",
        "11111111",
        "11111111")

VOID = ("........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........")

GRASSP = ("11111111",
          "11311111",
          "11211113",
          "31111121",
          "11111311",
          "11211111",
          "13111131",
          "11111211")

# Corrugated roofing: courses of sheet with staggered joins and a lit ridge
# line. One unique CHR tile, and it tiles into a continuous roof at any size.
ROOFP = ("33333333",
         "22222222",
         "22122212",
         "22222222",
         "33333333",
         "22222222",
         "12221222",
         "22222222")

# Town dirt / plaza paving.
DIRTP = ASH
PLAZAP = ("22222222",
          "21222212",
          "22222222",
          "22122122",
          "22222222",
          "12222221",
          "22222222",
          "22212212")

# --- overworld ----------------------------------------------------------------
# Only GLASS is left on sub-palette 3. Everything built or piled -- ridges,
# crags, towns, towers, wrecks -- is on sub-palette 0, where it can be warm and
# where its own ground fill matches the ash it stands on.
OW_PAL = [[0x07, 0x17, 0x27],     # 0 ash / dune / road / rock / structures
          [0x01, 0x11, 0x21],     # 1 water
          [0x09, 0x1A, 0x2A]]     # 2 growth


def overworld():
    t = Tileset("overworld", OW_PAL)
    t.add("ASH",   quad(ASH),    0, PROP_ENCTR)
    t.add("DUNE",  quad(DUST),   0, PROP_ENCTR)
    t.add("SCRUB", quad(SCRUB),  2, PROP_ENCTR)
    t.add("ROAD",  quad(ROADP),  0, 0)
    t.add("GLASS", quad(GLASS),  3, PROP_ENCTR)
    t.add("MARSH", quad(MARSHP), 2, PROP_ENCTR | PROP_SLOW)
    t.add("SEA",   quad(SEA),    1, PROP_WATER | PROP_ENCTR)
    t.add("DEEP",  quad(DEEP),   1, PROP_SOLID)

    # A range: a low shoulder, a main summit and a second shoulder, so a run of
    # RIDGE metatiles reads as a skyline rather than a row of identical bumps.
    t.add("RIDGE", on(ASH, *scree(
        peaks((3, 6, 15, 5), (12, 7, 15, 4), (8, 2, 15, 8)),
        [(6, 8), (10, 10), (4, 12), (13, 12), (8, 6), (2, 13), (11, 14)])),
        0, PROP_SOLID | PROP_HIGH)

    # A crag is sharper and taller: two thin spires with a broken skirt. Never
    # crossable, so it must not be mistaken for the ridge the grav-lift clears.
    t.add("CRAG", on(ASH, *scree(
        peaks((4, 0, 15, 4), (11, 3, 15, 4)),
        [(4, 6), (3, 9), (5, 12), (11, 8), (12, 11), (10, 13), (4, 3)])),
        0, PROP_SOLID)

    # Forest: four crowns filling the metatile, so a wood reads as a mass and
    # not as a scatter of icons on holes.
    t.add("TREE", on(SCRUB,
        "___33______33___",
        "__3223____3223__",
        "_322223__322223_",
        "_322223__322223_",
        "_332233__332233_",
        "__3223____3223__",
        "___22______22___",
        "___22______22___",
        "________________",
        "_33______33_____",
        "3223____3223____",
        "22223__322223___",
        "22223__322223___",
        "32233__332233___",
        "_3223____3223___",
        "__22______22____"), 2, PROP_SOLID)

    # A shell of a building: three standing walls, the roof gone, black inside.
    t.add("RUIN", on(ASH,
        "________________",
        "__33________33__",
        "__32________23__",
        "__32_3333333_23_",
        "__32.3222223.23_",
        "__323.22222.323_",
        "__3223......3223",
        "__3222......2223",
        "__3222......2223",
        "__32233....33223",
        "__32233333332233",
        "__3222222222223_",
        "__33333333333___",
        "___111111111____",
        "________________",
        "________________"), 0, 0)

    # A settlement: three roofs behind a wall, a lit gate. The one landmark the
    # player looks for, so it is the brightest silhouette on the ground.
    t.add("TOWN", on(ASH,
        "________________",
        "___33______33___",
        "__3223____3223__",
        "_322223__322223_",
        "3322222332222223",
        "3222222322222223",
        "3222222322222223",
        "1333333333333331",
        "1322222222222231",
        "1322233222233231",
        "1322233222233231",
        "1322233222233231",
        "1322233...233231",
        "1333333...333331",
        "_111111...111111",
        "________________"), 0, PROP_DOOR)

    t.add("CAVE", on(ASH,
        "________________",
        "____33333333____",
        "___3322222233___",
        "__332222222233__",
        "_33222222222233_",
        "_32222222222223_",
        "_32222......2223",
        "_32222......2223",
        "_32222......2223",
        "_32222......2223",
        "_32222......2223",
        "_32222......2223",
        "_32222......2223",
        "_33333......3333",
        "__1111......1111",
        "________________"), 0, PROP_DOOR)

    t.add("TOWER", on(ASH,
        "________________",
        "______3333______",
        "_____332233_____",
        "_____322223_____",
        "_____322223_____",
        "____33222233____",
        "____32222223____",
        "____32.22.223___",
        "___33222222233__",
        "___32222222223__",
        "__3322222222233_",
        "__3222222222223_",
        "__3222...2222223",
        "__3333...3333333",
        "___111...1111111",
        "________________"), 0, PROP_DOOR)

    # A hull section, half buried, plates catching the light along the top.
    t.add("WRECK", on(ASH,
        "________________",
        "____3333333_____",
        "__333222222333__",
        "_33222222222233_",
        "_32222332222223_",
        "3322233223222233",
        "3222332222322223",
        "3223322222232223",
        "3222222222222223",
        "1322222222222231",
        "_1332222222331__",
        "___11322223311__",
        "_____1111111____",
        "________________",
        "________________",
        "________________"), 0, PROP_SOLID)

    t.add("PYLON", on(ASH,
        "________________",
        "_______33_______",
        "______3223______",
        "______3223______",
        "______3223______",
        "___3333223333___",
        "___3222222223___",
        "______3223______",
        "______3223______",
        "_____32.23______".replace(".", "2"),
        "_____322223_____",
        "_____322223_____",
        "____33222233____",
        "___3322222233___",
        "____11111111____",
        "________________"), 0, PROP_SOLID)

    # A plank deck with rails; drawn full-bleed so a bridge run has no gaps.
    t.add("BRIDGE", G(
        "3333333333333333",
        "2222222222222222",
        "3222232222322223",
        "2222222222222222",
        "2222222222222222",
        "3222232222322223",
        "2222222222222222",
        "3333333333333333",
        "3333333333333333",
        "2222222222222222",
        "3222232222322223",
        "2222222222222222",
        "2222222222222222",
        "3222232222322223",
        "2222222222222222",
        "3333333333333333"), 0, 0)

    return t


# --- town ---------------------------------------------------------------------
# Roofs are on sub-palette 0 so they can be warm rust rather than UI grey; walls
# and steps stay grey, which is what poured concrete looks like. Sub-palette 1
# is kept for water and lit glass -- the only cool colour in a town, so windows
# and pools read from across the screen.
TOWN_PAL = [[0x07, 0x17, 0x27],   # 0 ground, roofs, timber, crates
            [0x01, 0x11, 0x21],   # 1 water, lit glass
            [0x09, 0x1A, 0x2A]]   # 2 planting


def town():
    t = Tileset("town", TOWN_PAL)
    t.add("DIRT",  quad(DIRTP),  0, 0)
    t.add("PLAZA", quad(PLAZAP), 0, 0)
    t.add("GRASS", quad(GRASSP), 2, 0)
    t.add("SAND",  quad(DUST),   0, 0)
    t.add("WATER", quad(SEA),    1, PROP_SOLID)

    # Poured panels with a cast seam. The only white is the top light, so a
    # wall block reads as one surface instead of a grid of boxes.
    t.add("WALL", G(
        "3333333333333333",
        "1111111111111111",
        "1211111121111111",
        "1111111121111111",
        "1111111121111111",
        "2222222222222222",
        "1111121111111121",
        "1111121111111111",
        "1111121111111111",
        "1111121111111111",
        "2222222222222222",
        "1211111121111111",
        "1111111121111111",
        "1111111121111111",
        "1111111121111111",
        "1111111121111111"), 3, PROP_SOLID)

    # Corrugated roofing, warm rust. Tiles into one continuous roof.
    t.add("ROOF", quad(ROOFP), 0, PROP_SOLID)

    # A doorway is genuinely dark inside, so colour 0 is the right colour here.
    t.add("DOOR", G(
        "1111111111111111",
        "1222222222222221",
        "1211111111111121",
        "1213333333333121",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213......3...31",
        "1213......3...31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213..........31"), 3, PROP_DOOR)

    t.add("WINDOW", G(
        "1111111111111111",
        "1111111111111111",
        "1133333333333311",
        "1132222222222311",
        "1132333333332311",
        "1132322222232311",
        "1132322222232311",
        "1132333333332311",
        "1132222222222311",
        "1133333333333311",
        "1111111111111111",
        "1111111111111111",
        "1112111111121111",
        "1111111111111111",
        "1111111111111111",
        "1111111111111111"), 1, PROP_SOLID)

    t.add("COUNTER", G(
        "1111111111111111",
        "3333333333333333",
        "2222222222222222",
        "3333333333333333",
        "1111111111111111",
        "1211111211111121",
        "1111111111111111",
        "1112111111112111",
        "1111111111111111",
        "1211111211111121",
        "1111111111111111",
        "1112111111112111",
        "1111111111111111",
        "1211111211111121",
        "1111111111111111",
        "1112111111112111"), 3, PROP_SOLID | PROP_COUNTER)

    # A save terminal. Warm amber screen on its own ground, so it is a lit
    # object in the street rather than a blue hole in the dirt.
    t.add("TERMINAL", on(DIRTP,
        "____222222______",
        "___23333332_____",
        "___23333332_____",
        "___23333332_____",
        "___23333332_____",
        "___23333332_____",
        "___22222222_____",
        "____222222______",
        "_____2222_______",
        "_____2112_______",
        "_____2112_______",
        "_____2112_______",
        "____222222______",
        "___22222222_____",
        "____111111______",
        "________________"), 0, PROP_SOLID)

    # A crate is low, wide and banded -- the opposite silhouette to a terminal,
    # which is the only other loose object standing in a street.
    t.add("CRATE", on(DIRTP,
        "________________",
        "________________",
        "________________",
        "__222222222222__",
        "__233333333332__",
        "__232222222232__",
        "__233333333332__",
        "__232222222232__",
        "__233333333332__",
        "__232222222232__",
        "__222222222222__",
        "__111111111111__",
        "________________",
        "________________",
        "________________",
        "________________"), 0, PROP_SOLID)

    t.add("PLANT", on(GRASSP,
        "________________",
        "_______33_______",
        "______3223______",
        "_____32__223____",
        "____32____223___",
        "___332_____33___",
        "___3223___322___",
        "____32233223____",
        "_____322223_____",
        "______3223______",
        "______3223______",
        "_____322223_____",
        "____33222233____",
        "_____111111_____",
        "________________",
        "________________"), 2, PROP_SOLID)

    # Timber posts and two rails, standing on the ground they are planted in.
    t.add("FENCE", on(DIRTP,
        "________________",
        "__33__________33",
        "__32__________23",
        "__33333333333333",
        "__32222222222223",
        "__32__________23",
        "__33333333333333",
        "__32222222222223",
        "__32__________23",
        "__32__________23",
        "__11__________11",
        "________________",
        "________________",
        "________________",
        "________________",
        "________________"), 0, PROP_SOLID)

    t.add("STAIRS", G(
        "3333333333333333",
        "1111111111111111",
        "1222222222222221",
        "3333333333333333",
        "1111111111111111",
        "1222222222222221",
        "3333333333333333",
        "1111111111111111",
        "1222222222222221",
        "3333333333333333",
        "1111111111111111",
        "1222222222222221",
        "3333333333333333",
        "1111111111111111",
        "1222222222222221",
        "3333333333333333"), 3, PROP_DOOR)

    return t


# --- dungeon ------------------------------------------------------------------
DUN_PAL = [[0x06, 0x16, 0x27],    # 0 hot: cinder red through to molten amber
           [0x0C, 0x1C, 0x2C],    # 1 cold: teal machinery
           [0x03, 0x13, 0x23]]    # 2 anomaly: violet


def dungeon():
    t = Tileset("dungeon", DUN_PAL)
    t.add("FLOOR", quad(FLOOR),  3, PROP_ENCTR)
    t.add("GRATE", quad(GRATEP), 1, PROP_ENCTR)
    t.add("SLAG",  quad(SLAGP),  0, PROP_ENCTR)
    t.add("VOID",  quad(VOID),   3, PROP_SOLID)
    t.add("LAVA",  quad(LAVAP),  0, PROP_SOLID | PROP_DAMAGE)
    t.add("COOL",  quad(COOLP),  1, PROP_ENCTR)

    # The wall is the largest thing on a dungeon screen. It is a dark mass with
    # a mortar course; the bright edge it used to carry drew a cyan grid over
    # every room on the map.
    t.add("WALL", quad(WALLP), 1, PROP_SOLID)

    # Full-bleed on purpose. A prop that leaves a border shows its own
    # sub-palette's darkest colour there, which is a coloured hole in whatever
    # floor it stands on -- and dungeon floors here are red, grey and teal.
    t.add("PILLAR", G(
        "1111111111111111",
        "1333333333333331",
        "1322222222222231",
        "1321111111111231",
        "1321222222221231",
        "1321222222221231",
        "1321222222221231",
        "1321222222221231",
        "1321222222221231",
        "1321222222221231",
        "1321222222221231",
        "1321111111111231",
        "1322222222222231",
        "1333333333333331",
        "1111111111111111",
        "1111111111111111"), 1, PROP_SOLID)

    t.add("PIPE", G(
        "1111111111111111",
        "1111111111111111",
        "3333333333333333",
        "2222222222222222",
        "1111111111111111",
        "1133111133111133",
        "1111111111111111",
        "2222222222222222",
        "3333333333333333",
        "1111111111111111",
        "1111111111111111",
        "1111111111111111",
        "1122111111221111",
        "1111111111111111",
        "1111111111111111",
        "1111111111111111"), 1, PROP_SOLID)

    t.add("CORE", on(DARK,
        "______3333______",
        "____33222233____",
        "___3221111223___",
        "__321113311223__",
        "_3211133333123__",
        "_3211333333123__",
        "_3211333333123__",
        "_3211333333123__",
        "_3211133331123__",
        "__3211133311223_",
        "___322111112233_",
        "____332222233___",
        "______33333_____",
        "________________",
        "________________",
        "________________"), 2, PROP_SOLID)

    t.add("DOOR", G(
        "1111111111111111",
        "1222222222222221",
        "1211111111111121",
        "1213333333333121",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213......3...31",
        "1213......3...31",
        "1213..........31",
        "1213..........31",
        "1213..........31",
        "1213333333333121",
        "1211111111111121",
        "1111111111111111"), 1, PROP_DOOR)

    t.add("STAIRD", G(
        "1111111111111111",
        "1222222222222221",
        "1322222222222231",
        "1332222222222331",
        "1333222222223331",
        "1333322222233331",
        "1333332222333331",
        "1333333223333331",
        "1333333223333331",
        "1333332222333331",
        "1333322222233331",
        "1333222222223331",
        "1332222222222331",
        "1322222222222231",
        "1222222222222221",
        "1111111111111111"), 1, PROP_DOOR)

    t.add("STAIRU", G(
        "1111111111111111",
        "1333333333333331",
        "1322222222222231",
        "1322333333332231",
        "1323322222233231",
        "1323232222323231",
        "1323223223223231",
        "1323222332222231",
        "1323222332222231",
        "1323223223223231",
        "1323232222323231",
        "1323322222233231",
        "1322333333332231",
        "1322222222222231",
        "1333333333333331",
        "1111111111111111"), 1, PROP_DOOR)

    t.add("CHEST", on(DARK,
        "________________",
        "________________",
        "___3333333333___",
        "__322222222223__",
        "__321111111123__",
        "__333333333333__",
        "__322222222223__",
        "__321113311123__",
        "__321113311123__",
        "__321111111123__",
        "__322222222223__",
        "__333333333333__",
        "___1111111111___",
        "________________",
        "________________",
        "________________"), 0, PROP_SOLID)

    # A collapse: wall that has come down into the room. Full-bleed, and it
    # keeps the wall's own darkness so it reads as blocked, not as decoration.
    t.add("RUBBLE", G(
        "1111111111111111",
        "1111111111111111",
        "1111133111111111",
        "1113322331111111",
        "1132211122331111",
        "1322111112223311",
        "1321111111122231",
        "1321112211112231",
        "3211111111111223",
        "3211122111111123",
        "3221111111112223",
        "1332222222233231",
        "1133333333333311",
        "1111111111111111",
        "1111111111111111",
        "1111111111111111"), 1, PROP_SOLID)

    return t


ALL_TILESETS = [overworld, town, dungeon]
