"""Crossing the nametable seam must not change the map's colours.

A mixed horizontal+vertical walk inside a dungeon streams both rows and
columns. Column streaming is the busiest frame the field engine has: one 34-byte
column packet plus eight 5-byte attribute packets, nine VBufAlloc calls in one
frame, so it is where an NMI is most likely to land inside the queue builder.
When it did, the queue's framing was destroyed and FlushVBuf walked into a
packet's *data*, read tile ids as a PPU address and eventually wrote them into
$3F00 - the background palette. The tell is exact: shapes and text stay right
while every background colour becomes a tile id masked to six bits.

So the assertion is on colour, not on layout: every pixel on screen, on every
step of a seam-crossing route, must be a colour the map's own palette can
produce. Anything else means something wrote to palette memory that should not
have.
"""
import sys, pathlib, subprocess, re
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run
from play import Player, route_between
import areas, art_tiles, world
from maps import OB_WARP, OB_CHEST

MAP = "CINDER1"
TILESET = "dungeon"
ROM = GAME / "test" / "threnos_seam.nes"

# pyntendo's RGB rendering of the NES palette (nes.pycore.ppu.DEFAULT_NES_PALETTE).
NES_RGB = [
    (82, 82, 82), (1, 26, 81), (15, 15, 101), (35, 6, 99),
    (54, 3, 75), (64, 4, 38), (63, 9, 4), (50, 19, 0),
    (31, 32, 0), (11, 42, 0), (0, 47, 0), (0, 46, 10),
    (0, 38, 45), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (160, 160, 160), (30, 74, 157), (56, 55, 188), (88, 40, 184),
    (117, 33, 148), (132, 35, 92), (130, 46, 36), (111, 63, 0),
    (81, 82, 0), (49, 99, 0), (26, 107, 5), (14, 105, 46),
    (16, 92, 104), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (254, 255, 255), (105, 158, 252), (137, 135, 255), (174, 118, 255),
    (206, 109, 241), (224, 112, 178), (222, 124, 112), (200, 145, 62),
    (166, 167, 37), (129, 186, 40), (99, 196, 70), (84, 193, 125),
    (86, 179, 192), (60, 60, 60), (0, 0, 0), (0, 0, 0),
    (254, 255, 255), (190, 214, 253), (204, 204, 255), (221, 196, 255),
    (234, 192, 249), (242, 193, 223), (241, 199, 194), (232, 208, 170),
    (217, 218, 157), (201, 226, 158), (188, 230, 174), (180, 229, 199),
    (181, 223, 228), (169, 169, 169), (0, 0, 0), (0, 0, 0),
]


def _bytes_after(path, label, count, skip=0):
    """The first `count` .byte values following `label:` in a generated file."""
    text = path.read_text()
    tail = text.split(label + ":", 1)[1]
    vals = []
    for line in tail.splitlines():
        line = line.strip()
        if not line.startswith(".byte"):
            if vals:
                break
            continue
        for tok in line[5:].split(","):
            tok = tok.strip()
            if tok.startswith("$"):
                vals.append(int(tok[1:], 16))
            elif tok.isdigit():
                vals.append(int(tok))
            else:
                vals.append(None)          # a symbol; not a palette byte
        if len(vals) >= skip + count:
            break
    return vals[skip:skip + count]


def allowed_colours():
    """Every RGB this map is allowed to put on screen.

    The tileset record is [chr4, chr5, nmeta, 16 background palette bytes, ...]
    (see LoadTileset); the sprite half of the palette is spr_palette.
    """
    bg = _bytes_after(GAME / "src" / "gen" / "tilesets.s", "ts_" + TILESET,
                      19)[3:19]
    spr = _bytes_after(GAME / "src" / "gen" / "tables.s", "spr_palette", 16)
    idxs = {v & 0x3F for v in bg + spr}
    idxs.add(bg[0] & 0x3F)                 # $3F00 shows through every mirror
    return {NES_RGB[i] for i in idxs}


def build():
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID[MAP]}",
            "-D", "TEST_NO_ENCOUNTERS=1"]
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"seam_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(ROM)] + objs,
                   check=True)


def seam_route():
    """A route out of the entrance that crosses camera tile column 32.

    The far item chest is used purely as a destination: reaching it needs a
    long mixed east/north walk, which is what puts the camera over the seam.
    """
    ts = art_tiles.dungeon()
    m = areas.build_all(art_tiles.town(), ts)[world.MAP_NAMES[1:].index(MAP)]
    prop = ts.compile()["prop"]
    warps = {(o[1], o[2]) for o in m.objects if o[0] == OB_WARP}
    goal = [(o[1], o[2]) for o in m.objects if o[0] == OB_CHEST and o[4]][0]
    route = route_between(m, prop, (12, 18), goal, avoid=warps)
    assert route, "no route to the far chest"
    return route


def stray(frame, allowed):
    """The off-palette colours on screen, worst first."""
    a = np.asarray(frame)
    cols, counts = np.unique(a.reshape(-1, 3), axis=0, return_counts=True)
    bad = [(tuple(c), int(n)) for c, n in zip(cols.tolist(), counts.tolist())
           if tuple(c) not in allowed]
    return sorted(bad, key=lambda z: -z[1])


if __name__ == "__main__":
    if "--no-build" not in sys.argv:
        build()
    rom = ROM
    for arg in sys.argv[1:]:
        if arg.endswith(".nes"):
            rom = pathlib.Path(arg)

    allowed = allowed_colours()
    route = seam_route()
    print(f"route {len(route)} cells, {len(allowed)} legal colours")

    p = Player(rom)
    ok = True
    bad0 = stray(p.frame, allowed)
    if bad0:
        print("FAIL: the map is off-palette before the walk even starts:", bad0[:3])
        ok = False

    for i, d in enumerate(route):
        p.step(d)
        bad = stray(p.frame, allowed)
        if bad:
            print(f"FAIL: step {i} put {bad[0][1]} px of {bad[0][0]} on screen, "
                  f"which is in none of the map's palettes")
            p.shot("seam_bad")
            ok = False
            break

    if ok:
        p.shot("seam_ok")
        print(f"ok   {len(route)} cells across the seam, colours stayed in palette")
    print("PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)
