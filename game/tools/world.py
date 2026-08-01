"""The world of Threnos: the overworld map and every area map.

The overworld is painted programmatically (regions, ranges, coasts, roads) so
the geography is editable as design intent rather than 16,384 hand-typed cells;
landmarks are then placed by hand at exact coordinates.
"""
import art_tiles
from maps import GameMap, MF_DUNGEON, OB_NPC, OB_CHEST, OB_WARP, OB_SIGN, \
    OB_SHOP, OB_INN, OB_SAVE, OB_TRIG

W = H = 128

# --- map ids ------------------------------------------------------------------
MAP_NAMES = [
    "OVERWORLD",
    "LANDFALL", "EMBERREST", "KELPHOLD", "HIGHMESA", "DUSTGATE", "LASTPORT",
    "CINDER1", "CINDER2", "CINDER3",
    "TIDE1", "TIDE2", "TIDE3",
    "STORM1", "STORM2", "STORM3",
    "HOLLOW1", "HOLLOW2", "HOLLOW3",
    "CAUSEWAY", "RELAY1", "RELAY2", "OSSUARY1", "OSSUARY2",
    "EREBUS1", "EREBUS2", "EREBUS3", "EREBUS4",
]
MAP_ID = {n: i for i, n in enumerate(MAP_NAMES)}

# Landmark positions on the overworld (metatile coords).
SITES = {
    "LANDFALL":  (44, 66),
    "EMBERREST": (92, 30),
    "KELPHOLD":  (52, 104),
    "HIGHMESA":  (102, 78),
    "DUSTGATE":  (26, 26),
    "LASTPORT":  (60, 52),
    "CINDER":    (104, 20),
    "TIDE":      (40, 112),
    "STORM":     (114, 92),
    "HOLLOW":    (14, 14),
    "RELAY":     (24, 84),
    "OSSUARY":   (88, 108),
    "REEF":      (70, 96),      # causeway mouth
    "RIFT":      (64, 58),
}

START = (44, 68)     # just outside Landfall's gate


def _blank():
    return [["DEEP"] * W for _ in range(H)]


def _ell(grid, cx, cy, rx, ry, tile, only=None):
    for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
        for x in range(max(0, cx - rx), min(W, cx + rx + 1)):
            dx = (x - cx) / rx
            dy = (y - cy) / ry
            if dx * dx + dy * dy <= 1.0:
                if only is None or grid[y][x] in only:
                    grid[y][x] = tile


def _rect(grid, x0, y0, x1, y1, tile, only=None):
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            if only is None or grid[y][x] in only:
                grid[y][x] = tile


def _line(grid, x0, y0, x1, y1, tile, only=None):
    """Manhattan road: horizontal then vertical."""
    step = 1 if x1 >= x0 else -1
    for x in range(x0, x1 + step, step):
        if only is None or grid[y0][x] in only:
            grid[y0][x] = tile
    step = 1 if y1 >= y0 else -1
    for y in range(y0, y1 + step, step):
        if only is None or grid[y][x1] in only:
            grid[y][x1] = tile


class _Rand:
    """Deterministic LCG so the world is byte-identical on every build."""
    def __init__(self, seed):
        self.s = seed

    def next(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 16) % n


def _scatter(grid, rnd, base, tile, chance, region=None):
    for y in range(H):
        for x in range(W):
            if grid[y][x] != base:
                continue
            if region and not region(x, y):
                continue
            if rnd.next(100) < chance:
                grid[y][x] = tile


def build_overworld_grid():
    g = _blank()
    rnd = _Rand(0x5EED)

    # --- the landmass: five overlapping regions around a central plain -------
    _ell(g, 52, 62, 34, 28, "ASH")        # central plains
    _ell(g, 92, 32, 30, 24, "ASH")        # the Ashen Verge (north-east)
    _ell(g, 28, 28, 22, 20, "DUNE")       # the Hollow Waste (north-west)
    _ell(g, 100, 82, 24, 22, "ASH")       # the Screaming Reach (east)
    _ell(g, 54, 104, 38, 18, "MARSH")     # the Drowned Shelf (south)
    _ell(g, 26, 86, 16, 14, "SCRUB")      # the Fen (south-west)

    # --- regional character --------------------------------------------------
    _ell(g, 92, 30, 26, 20, "GLASS", only=["ASH"])
    _scatter(g, rnd, "GLASS", "ASH", 34)
    _ell(g, 26, 26, 20, 18, "DUNE", only=["ASH", "GLASS"])
    _scatter(g, rnd, "ASH", "SCRUB", 22,
             region=lambda x, y: 24 <= x <= 80 and 44 <= y <= 84)
    _scatter(g, rnd, "MARSH", "SEA", 26)
    _scatter(g, rnd, "SCRUB", "TREE", 9)
    _scatter(g, rnd, "DUNE", "CRAG", 5)

    # --- mountain ranges: the gates between regions --------------------------
    _rect(g, 66, 8, 74, 44, "RIDGE", only=["ASH", "GLASS", "SCRUB", "DUNE"])
    _rect(g, 46, 22, 70, 28, "RIDGE", only=["ASH", "GLASS", "SCRUB", "DUNE"])
    _rect(g, 84, 56, 90, 96, "RIDGE", only=["ASH", "SCRUB", "MARSH"])
    _rect(g, 12, 44, 44, 50, "RIDGE", only=["ASH", "DUNE", "SCRUB"])
    _rect(g, 4, 44, 14, 52, "RIDGE", only=["ASH", "DUNE", "SCRUB", "DEEP"])
    _scatter(g, rnd, "RIDGE", "CRAG", 18)

    # The Rift: a rampart of high ground around a dead centre, with Lastport
    # inside it. RIDGE, not CRAG -- CRAG is plain solid and nothing in the game
    # can ever cross it, which sealed the endgame dungeon and a whole town
    # behind terrain no vehicle opens. The grav-lift crosses RIDGE, so the last
    # act of the game is what unlocks the basin.
    _ell(g, 64, 58, 9, 8, "RIDGE", only=["ASH", "SCRUB", "CRAG", "GLASS"])
    _ell(g, 64, 58, 5, 4, "GLASS")

    # --- coastline: a shallow shelf everywhere land meets deep water ---------
    for _ in range(2):
        edge = []
        for y in range(1, H - 1):
            for x in range(1, W - 1):
                if g[y][x] != "DEEP":
                    continue
                if any(g[y + dy][x + dx] not in ("DEEP", "SEA")
                       for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    edge.append((x, y))
        for x, y in edge:
            g[y][x] = "SEA"

    # --- roads ---------------------------------------------------------------
    _line(g, *SITES["LANDFALL"], *SITES["LASTPORT"], "ROAD",
          only=["ASH", "SCRUB", "DUNE", "GLASS", "MARSH"])
    _line(g, *SITES["LANDFALL"], *SITES["KELPHOLD"], "ROAD",
          only=["ASH", "SCRUB", "MARSH"])
    _line(g, *SITES["EMBERREST"], *SITES["CINDER"], "ROAD",
          only=["ASH", "GLASS", "SCRUB"])
    _line(g, *SITES["DUSTGATE"], *SITES["HOLLOW"], "ROAD",
          only=["DUNE", "ASH", "SCRUB"])
    _line(g, *SITES["HIGHMESA"], *SITES["STORM"], "ROAD",
          only=["ASH", "SCRUB", "GLASS"])
    _line(g, *SITES["LANDFALL"], *SITES["RELAY"], "ROAD",
          only=["ASH", "SCRUB", "MARSH"])

    # --- ruins and wrecks: the ark came down in pieces ------------------------
    for (x, y) in [(38, 58), (58, 74), (74, 62), (30, 70), (96, 46),
                   (48, 92), (18, 36), (110, 66), (66, 34), (86, 20)]:
        g[y][x] = "WRECK"
    for (x, y) in [(40, 62), (62, 68), (34, 40), (98, 60), (50, 98), (20, 90)]:
        g[y][x] = "RUIN"
    for (x, y) in [(56, 44), (72, 76), (36, 30), (104, 40), (46, 108)]:
        g[y][x] = "PYLON"

    # --- landmarks -----------------------------------------------------------
    for key, tile in [("LANDFALL", "TOWN"), ("EMBERREST", "TOWN"),
                      ("KELPHOLD", "TOWN"), ("HIGHMESA", "TOWN"),
                      ("DUSTGATE", "TOWN"), ("LASTPORT", "TOWN"),
                      ("CINDER", "TOWER"), ("TIDE", "CAVE"),
                      ("STORM", "TOWER"), ("HOLLOW", "CAVE"),
                      ("RELAY", "TOWER"), ("OSSUARY", "CAVE"),
                      ("REEF", "CAVE"), ("RIFT", "CAVE")]:
        x, y = SITES[key]
        g[y][x] = tile
        # make sure each landmark is approachable from below
        if g[y + 1][x] in ("DEEP", "RIDGE", "CRAG", "TREE"):
            g[y + 1][x] = "ASH"

    # the start tile must be walkable
    g[START[1]][START[0]] = "ROAD"
    return g


# Encounter zones over the overworld (8x8 blocks of 16x16 metatiles).
OW_ZONES = [
    [7, 7, 5, 5, 1, 1, 1, 1],
    [7, 7, 5, 5, 1, 1, 1, 2],
    [6, 6, 0, 0, 0, 1, 2, 2],
    [6, 0, 0, 0, 0, 0, 2, 2],
    [6, 0, 0, 0, 0, 3, 3, 3],
    [4, 4, 0, 0, 0, 3, 3, 3],
    [4, 4, 8, 8, 8, 8, 3, 3],
    [4, 4, 8, 8, 8, 8, 8, 3],
]


def overworld_map(ts):
    grid = build_overworld_grid()
    legend = {c: c for c in set(t for row in grid for t in row)}
    rows = ["\x00".join(r) for r in grid]     # placeholder, replaced below
    m = GameMap.__new__(GameMap)
    m.name = "OVERWORLD"
    m.tileset = ts
    m.objects = []
    m.grid = [[ts.id(t) for t in row] for row in grid]
    m.w, m.h = W, H
    m.music = 3         # SONG_OVERWORLD
    m.enc_zone = 0
    m.enc_rate = 10
    m.flags = 0
    m.zones = OW_ZONES

    # warps: stepping on a TOWN/CAVE/TOWER tile enters that map
    entries = [("LANDFALL", "LANDFALL"), ("EMBERREST", "EMBERREST"),
               ("KELPHOLD", "KELPHOLD"), ("HIGHMESA", "HIGHMESA"),
               ("DUSTGATE", "DUSTGATE"), ("LASTPORT", "LASTPORT"),
               ("CINDER", "CINDER1"), ("TIDE", "TIDE1"),
               ("STORM", "STORM1"), ("HOLLOW", "HOLLOW1"),
               ("RELAY", "RELAY1"), ("OSSUARY", "OSSUARY1"),
               ("REEF", "CAUSEWAY"), ("RIFT", "EREBUS1")]
    for site, target in entries:
        x, y = SITES[site]
        m.obj(OB_WARP, x, y, MAP_ID[target], 12, 18, 0, 0)
    return m


def render_png(grid, path, scale=3):
    """Eyeball check: draw the overworld to a PNG."""
    from PIL import Image
    colours = {
        "DEEP": (10, 20, 60), "SEA": (40, 90, 170), "ASH": (120, 96, 72),
        "DUNE": (200, 178, 120), "SCRUB": (86, 130, 60), "MARSH": (70, 110, 96),
        "GLASS": (60, 55, 65), "ROAD": (170, 150, 120), "RIDGE": (110, 110, 118),
        "CRAG": (80, 80, 88), "TREE": (40, 90, 50), "RUIN": (150, 150, 160),
        "TOWN": (250, 230, 120), "CAVE": (230, 120, 60), "TOWER": (240, 90, 200),
        "WRECK": (190, 190, 200), "PYLON": (200, 200, 255), "BRIDGE": (160, 130, 90),
    }
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = colours[grid[y][x]]
    img = img.resize((W * scale, H * scale), Image.NEAREST)
    img.save(path)
    return path
