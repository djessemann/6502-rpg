"""The title screen: a painted 32x30 screen compiled to CHR + a nametable.

The screen is authored here as pixels, not as tiles. `build()` paints a
256x240 canvas of colour indices 0..3, cuts it into 8x8 tiles, deduplicates
them and returns both the tile set (which becomes two 1KB CHR banks at BG
$80-$FF) and the nametable that references them.

Deduplication is what makes this affordable: the sky is mostly one blank tile,
so the 960-tile screen collapses to well under the 128 the two banks hold. The
build asserts that, so an over-ambitious edit fails at build time rather than
silently painting garbage.

Three sub-palettes, assigned per 16x16 attribute quadrant:
    0  space      backdrop, dim star, bright star, white star
    1  the logo   backdrop, shadow, body, highlight
    2  the planet backdrop, deep ember, ember, pale rim
    3  the UI palette the font shares (set by the engine, not here)
"""
import font
from chrlib import tile_from_rows

W, H = 256, 240                 # pixels
TW, TH = W // 8, H // 8         # 32 x 30 tiles

BASE_TILE = 0x80                # BG $80-$FF: the two title CHR banks

PAL_SPACE, PAL_LOGO, PAL_PLANET, PAL_UI = 0, 1, 2, 3

# NES colours. Sub-palette entry 0 is the shared backdrop and must be equal in
# all four (see the palette-mirror trap in framework/HARDWARE.md).
PALETTES = [
    [0x0F, 0x01, 0x21, 0x30],   # space: navy, sky blue, white stars
    [0x0F, 0x06, 0x27, 0x37],   # logo: maroon shadow, amber body, pale rim
    [0x0F, 0x07, 0x17, 0x28],   # planet: burnt orange through to sand
    [0x0F, 0x00, 0x10, 0x30],   # UI (matches every tileset's sub-palette 3)
]


class Canvas:
    def __init__(self):
        self.px = [[0] * W for _ in range(H)]
        self.attr = [[PAL_SPACE] * (TW // 2) for _ in range(TH // 2)]

    def put(self, x, y, v):
        if 0 <= x < W and 0 <= y < H:
            self.px[y][x] = v

    def quad(self, tx0, ty0, tx1, ty1, pal):
        """Assign a sub-palette over a range of *tiles*, rounded to quadrants."""
        for qy in range(ty0 // 2, ty1 // 2 + 1):
            for qx in range(tx0 // 2, tx1 // 2 + 1):
                if 0 <= qy < TH // 2 and 0 <= qx < TW // 2:
                    self.attr[qy][qx] = pal


# --- a deterministic starfield -----------------------------------------------
def _lcg(seed):
    v = seed
    while True:
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        yield v >> 16


# Stars are placed on a fixed set of in-tile positions rather than anywhere,
# so the whole sky collapses to a handful of unique tiles. Scattering them
# freely looks no better and costs about a hundred tiles the logo needs.
STAR_SPOTS = [(2, 3), (5, 1), (1, 6), (6, 5), (3, 2), (4, 6), (0, 4), (7, 2)]


def starfield(c, rows, density=5, seed=7):
    """One star per lit tile, on one of eight fixed in-tile positions."""
    r = _lcg(seed)
    for ty in range(rows // 8):
        for tx in range(TW):
            if next(r) % 16 >= density:
                continue
            sx, sy = STAR_SPOTS[next(r) % len(STAR_SPOTS)]
            roll = next(r) % 10
            c.put(tx * 8 + sx, ty * 8 + sy, 1 if roll < 6 else
                  (2 if roll < 9 else 3))


def planet(c, cx, cy, radius):
    """A gas giant's limb: banded, lit from the upper left, cut off by the sky.

    Only the part of the disc that lands inside the canvas is drawn, so placing
    the centre off the right edge gives a crescent of a very large world.
    """
    r2 = radius * radius
    for y in range(max(0, cy - radius), min(H, cy + radius + 1)):
        dy = y - cy
        for x in range(max(0, cx - radius), min(W, cx + radius + 1)):
            dx = x - cx
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            band = ((y + (dx * dx) // (radius * 2)) // 7) % 3
            v = (3, 2, 1)[band]
            if d2 > r2 - radius * 6:            # the rim catches the light
                v = 3
            if dx > radius // 3 and dy > 0:     # the far side falls into night
                v = 1 if v > 1 else 0
            c.put(x, y, v)


# --- the logo -----------------------------------------------------------------
def _glyph_bits(ch):
    rows = font.GLYPHS[ch]
    return [[(r >> (4 - i)) & 1 for i in range(5)] for r in rows]


def big_letter(c, ch, x0, y0, scale):
    """One glyph at `scale`, with a 2px drop shadow and a 1px outline.

    Drawn in three passes so the passes cannot fight: shadow, then outline,
    then body. Each pass only writes where it is allowed to, which is what
    keeps neighbouring letters from eating each other's outlines.
    """
    bits = _glyph_bits(ch)
    solid = set()
    for gy, row in enumerate(bits):
        for gx, on in enumerate(row):
            if not on:
                continue
            for sy in range(scale):
                for sx in range(scale):
                    solid.add((x0 + gx * scale + sx, y0 + gy * scale + sy))
    for (x, y) in solid:                                     # shadow
        c.put(x + 2, y + 3, 1)
    for (x, y) in solid:                                     # outline
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (-1, -1), (1, -1), (-1, 1)):
            if (x + dx, y + dy) not in solid:
                c.put(x + dx, y + dy, 2)
    for (x, y) in solid:                                     # body
        c.put(x, y, 3)


def logo(c, word, cy, scale=4, gap=4):
    cell = 5 * scale + gap
    total = cell * len(word) - gap
    x = (W - total) // 2
    for ch in word:
        big_letter(c, ch, x, cy, scale)
        x += cell


# --- compile ------------------------------------------------------------------
def _tile_rows(c, tx, ty):
    return ["".join(str(c.px[ty * 8 + y][tx * 8 + x]) for x in range(8))
            for y in range(8)]


def build(word="THRENOS"):
    """-> (tiles, nametable[960], attributes[64]).

    The nametable holds absolute BG tile indices, so the engine can push it
    straight to $2000 with no fix-up.
    """
    c = Canvas()
    starfield(c, 96)            # stop the sky where the logo band begins
    planet(c, 250, 26, 38)      # a crescent off the top-right corner
    logo(c, word, 120)

    c.quad(0, 0, TW - 1, 13, PAL_SPACE)
    c.quad(0, 12, TW - 1, 19, PAL_LOGO)
    c.quad(26, 0, TW - 1, 9, PAL_PLANET)
    c.quad(0, 20, TW - 1, TH - 1, PAL_UI)

    tiles, index, nt = [], {}, []
    for ty in range(TH):
        for tx in range(TW):
            rows = _tile_rows(c, tx, ty)
            key = "\n".join(rows)
            if key not in index:
                index[key] = len(tiles)
                tiles.append(tile_from_rows(rows))
            nt.append(BASE_TILE + index[key])
    if len(tiles) > 128:
        raise ValueError(f"title screen needs {len(tiles)} unique tiles > 128; "
                         f"simplify the art or reuse more of it")

    attr = []
    for qy in range(0, TH // 2, 2):
        for qx in range(0, TW // 2, 2):
            def q(dx, dy):
                yy, xx = qy + dy, qx + dx
                if yy >= TH // 2 or xx >= TW // 2:
                    return 0
                return c.attr[yy][xx]
            attr.append(q(0, 0) | (q(1, 0) << 2) | (q(0, 1) << 4) | (q(1, 1) << 6))
    return tiles, nt, attr


def palette_bytes():
    out = []
    for p in PALETTES:
        out += p
    return out


def emit(f, tiles, nt, attr, bank):
    """Write the nametable and palette as ca65 source in a data bank."""
    f.write(f'\n.segment "BANK{bank:02d}"\n')
    f.write(".export title_nt, title_attr, title_pal\n")
    f.write("title_nt:\n")
    for i in range(0, len(nt), 16):
        f.write("    .byte " + ",".join(f"${v:02X}" for v in nt[i:i + 16]) + "\n")
    f.write("title_attr:\n")
    for i in range(0, len(attr), 16):
        f.write("    .byte " + ",".join(f"${v:02X}" for v in attr[i:i + 16]) + "\n")
    # 32 bytes: 16 BG + 16 sprite (the sprite half is never shown here, but
    # LoadPalette always writes all 32).
    pal = palette_bytes()
    f.write("title_pal:\n")
    f.write("    .byte " + ",".join(f"${v:02X}" for v in pal) + "\n")
    f.write("    .byte " + ",".join(f"${v:02X}" for v in pal) + "\n")
