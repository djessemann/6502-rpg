#!/usr/bin/env python3
"""Dev-time asset generator for the vertical slice.

Source-of-truth for the CHR tiles, the one-screen field map, and the text
window tilemap. NOT part of the `make` build: it emits committed .s files
(src/chr.s, src/field.s) that ca65 assembles. Re-run by hand after editing art,
then commit the generated .s.

Tiles are 8x8, pixel values 0-3 selecting a color within the active palette.
The attribute table is palette-aware: water -> palette 1, NPC -> palette 2,
everything else -> palette 0. The text window region is switched to palette 3
at runtime.
"""

import os

# ---------------------------------------------------------------------------
# Background tile indices (pattern table 0)
# ---------------------------------------------------------------------------
T_BLANK, T_GRASS, T_FLOWER, T_PATH, T_TREE, T_WALL, T_BUSH, T_WATER = range(8)
T_NPC0 = 0x08          # NPC metasprite-as-background, tiles $08-$0B
W_TL, W_T, W_TR, W_L, W_FILL, W_R, W_BL, W_B, W_BR = range(0x0C, 0x15)
F_BASE = 0x15          # font glyph tiles start here

WATER = T_WATER

# ---------------------------------------------------------------------------
# Field tile art. '0'-'3' = color index within the tile's palette.
# ---------------------------------------------------------------------------
TILES = {
    T_BLANK: ["00000000"] * 8,
    T_GRASS: [
        "11112111", "11111111", "21111121", "11111111",
        "11211111", "11111111", "11111121", "21111111",
    ],
    T_FLOWER: [
        "11111111", "11122111", "11233211", "11232311",
        "11233211", "11122111", "11111111", "11111111",
    ],
    T_PATH: [
        "33333333", "33133333", "33333313", "33333333",
        "31333333", "33333133", "33333333", "33313333",
    ],
    T_TREE: [
        "12222221", "22222222", "22322322", "22222222",
        "22322322", "22222222", "12333321", "11333311",
    ],
    T_WALL: [
        "33333333", "33333333", "13131313", "33333333",
        "33333333", "31313131", "33333333", "33333333",
    ],
    T_BUSH: [
        "11111111", "11222211", "12222221", "12222221",
        "12222221", "11222211", "11111111", "11111111",
    ],
    T_WATER: [
        "11111111", "12211221", "11111111", "21122112",
        "11111111", "12211221", "11111111", "21122112",
    ],
}

# ---------------------------------------------------------------------------
# Hero metasprite: 16x16, drawn as a 2x2 block of tiles in pattern table 1.
# Pixel value 0 = transparent. Sprite palette 0: 1=red, 2=tan, 3=white.
# ---------------------------------------------------------------------------
HERO16 = [
    "0000011111100000",
    "0000122222210000",
    "0001222222221000",
    "0001223223221000",
    "0001222222221000",
    "0001222222221000",
    "0000122222210000",
    "0000011111100000",
    "0001111111111000",
    "0011111111111100",
    "0011111111111100",
    "0011111111111100",
    "0001111111111000",
    "0001100000011000",
    "0001100000011000",
    "0001100000011000",
]

# ---------------------------------------------------------------------------
# NPC: 16x16 drawn as BACKGROUND tiles (palette 2). Value 0 renders as the
# universal backdrop ($0F black) so it reads as an outline; the figure fills
# the cell. 1=robe, 2=skin, 3=eyes/white.
# ---------------------------------------------------------------------------
NPC16 = [
    "0000111111100000",
    "0001122222110000",
    "0011222222211000",
    "0011233223211000",
    "0011222222211000",
    "0011222222211000",
    "0001122222110000",
    "0011111111110000",
    "0111111111111000",
    "0111111111111000",
    "0111111111111000",
    "0111111111111000",
    "0111111111111000",
    "0111111111111000",
    "0011111111110000",
    "0001111111100000",
]

# ---------------------------------------------------------------------------
# Text window: white box, black border + text (palette 3: 1=white, 2=black).
# Font glyphs are '#'=ink (value 2) on '.'=paper (value 1).
# ---------------------------------------------------------------------------
FONT = {
    "H": ["........", ".#...#..", ".#...#..", ".#####..",
          ".#...#..", ".#...#..", ".#...#..", "........"],
    "E": ["........", ".#####..", ".#......", ".####...",
          ".#......", ".#......", ".#####..", "........"],
    "L": ["........", ".#......", ".#......", ".#......",
          ".#......", ".#......", ".#####..", "........"],
    "O": ["........", "..###...", ".#...#..", ".#...#..",
          ".#...#..", ".#...#..", "..###...", "........"],
    "T": ["........", ".#####..", "...#....", "...#....",
          "...#....", "...#....", "...#....", "........"],
    "R": ["........", ".####...", ".#...#..", ".####...",
          ".#.#....", ".#..#...", ".#...#..", "........"],
    "!": ["...#....", "...#....", "...#....", "...#....",
          "...#....", "........", "...#....", "........"],
}
MESSAGE = "HELLO THERE!"   # one hardcoded line (<= 14 chars to fit the window)

# Where the NPC stands, in 16px grid cells (must match NPC_GX/GY in main.s).
NPC_GX, NPC_GY = 6, 6


def to_chr(rows):
    """Encode one 8x8 tile (rows of digit chars) to 16 planar bytes."""
    p0, p1 = [], []
    for row in rows:
        b0 = b1 = 0
        for px in row:
            v = int(px)
            b0 = (b0 << 1) | (v & 1)
            b1 = (b1 << 1) | ((v >> 1) & 1)
        p0.append(b0)
        p1.append(b1)
    return p0 + p1


def split16(block):
    """Split a 16x16 art block into 4 8x8 tiles ordered TL, TR, BL, BR."""
    return [
        [r[0:8] for r in block[0:8]],
        [r[8:16] for r in block[0:8]],
        [r[0:8] for r in block[8:16]],
        [r[8:16] for r in block[8:16]],
    ]


def wintile(top=False, bottom=False, left=False, right=False):
    """Window frame tile: white (1) fill with black (2) on the named edges."""
    g = [[1] * 8 for _ in range(8)]
    for i in range(8):
        if top:
            g[0][i] = 2
        if bottom:
            g[7][i] = 2
        if left:
            g[i][0] = 2
        if right:
            g[i][7] = 2
    return ["".join(str(v) for v in row) for row in g]


def glyph(ch):
    """Font tile: '#'=ink(2) on '.'=paper(1)."""
    return ["".join("2" if c == "#" else "1" for c in row) for row in FONT[ch]]


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, "src")

    # --- assemble the ordered background tile table ($00-$1B) ---
    font_chars = sorted(FONT.keys())
    font_id = {ch: F_BASE + i for i, ch in enumerate(font_chars)}

    bg = {}
    bg.update(TILES)
    for tid, tile in zip(range(T_NPC0, T_NPC0 + 4), split16(NPC16)):
        bg[tid] = tile
    bg[W_TL] = wintile(top=True, left=True)
    bg[W_T] = wintile(top=True)
    bg[W_TR] = wintile(top=True, right=True)
    bg[W_L] = wintile(left=True)
    bg[W_FILL] = wintile()
    bg[W_R] = wintile(right=True)
    bg[W_BL] = wintile(bottom=True, left=True)
    bg[W_B] = wintile(bottom=True)
    bg[W_BR] = wintile(bottom=True, right=True)
    for ch in font_chars:
        bg[font_id[ch]] = glyph(ch)

    last_bg = max(bg)
    bg_bytes = []
    for tid in range(last_bg + 1):
        bg_bytes += to_chr(bg.get(tid, ["00000000"] * 8))

    hero_bytes = []
    for tile in split16(HERO16):
        hero_bytes += to_chr(tile)

    with open(os.path.join(src, "chr.s"), "w") as f:
        f.write("; chr.s - GENERATED by tools/gen_assets.py. Do not edit by hand.\n")
        f.write("; Pattern table 0: field tiles, NPC, window frame, font ($00-$%02X).\n" % last_bg)
        f.write("; Pattern table 1 ($1000): hero metasprite tiles ($00-$03).\n")
        f.write("; The CHR region fills the remaining 8KB with zero (see nes.cfg).\n\n")
        f.write('.segment "CHARS"\n')
        f.write("    ; --- pattern table 0: background ---\n")
        for i in range(0, len(bg_bytes), 16):
            row = ", ".join(f"${b:02X}" for b in bg_bytes[i:i + 16])
            f.write(f"    .byte {row}   ; bg tile ${i // 16:02X}\n")
        pad = 0x1000 - len(bg_bytes)
        f.write(f"\n    .res ${pad:04X}, $00   ; pad to pattern table 1 ($1000)\n\n")
        f.write("    ; --- pattern table 1: sprites ---\n")
        for i in range(0, len(hero_bytes), 16):
            row = ", ".join(f"${b:02X}" for b in hero_bytes[i:i + 16])
            f.write(f"    .byte {row}   ; hero tile ${i // 16:02X}\n")

    # --- build the field map ---
    W, H = 32, 30
    m = [[T_GRASS] * W for _ in range(H)]
    for x in range(W):
        m[0][x] = T_TREE
        m[H - 1][x] = T_TREE
    for y in range(H):
        m[y][0] = T_TREE
        m[y][W - 1] = T_TREE
    for y in range(3, 8):
        for x in range(3, 9):
            m[y][x] = T_WATER
    for y in range(1, H - 1):
        m[y][16] = T_PATH
    for x in range(1, W - 1):
        m[22][x] = T_PATH
    for x in range(20, 26):
        m[3][x] = T_WALL
        m[7][x] = T_WALL
    for y in range(3, 8):
        m[y][20] = T_WALL
        m[y][25] = T_WALL
    for (x, y) in [(5, 12), (9, 18), (13, 25), (27, 10), (29, 19), (23, 24), (6, 26)]:
        m[y][x] = T_FLOWER
    for (x, y) in [(11, 11), (28, 6), (4, 20), (19, 27), (26, 14), (8, 9)]:
        m[y][x] = T_BUSH

    # stamp the NPC (2x2 background tiles) at its grid cell
    bx, by = NPC_GX * 2, NPC_GY * 2
    m[by][bx], m[by][bx + 1] = T_NPC0 + 0, T_NPC0 + 1
    m[by + 1][bx], m[by + 1][bx + 1] = T_NPC0 + 2, T_NPC0 + 3

    def palette_of(tile):
        if tile == T_WATER:
            return 1
        if T_NPC0 <= tile <= T_NPC0 + 3:
            return 2
        return 0

    def attr_table(grid):
        attr = [0] * 64
        for ay in range(8):
            for ax in range(8):
                byte = 0
                for q in range(4):
                    qx, qy = q & 1, q >> 1
                    pal = 0
                    for ty in range(2):
                        for tx in range(2):
                            x = ax * 4 + qx * 2 + tx
                            y = ay * 4 + qy * 2 + ty
                            if 0 <= y < H and 0 <= x < W:
                                pal = max(pal, palette_of(grid[y][x]))
                    byte |= pal << (q * 2)
                attr[ay * 8 + ax] = byte
        return attr

    flat = [m[y][x] for y in range(H) for x in range(W)]
    attr = attr_table(m)

    # --- build the 16x4 window tilemap (text embedded), rows top-to-bottom ---
    interior = " " + MESSAGE + " "
    interior = interior + " " * (14 - len(interior))   # pad to 14 wide
    assert len(interior) == 14, "MESSAGE too long for the window"
    text_row = [W_L] + [W_FILL if c == " " else font_id[c] for c in interior] + [W_R]
    winmap = (
        [W_TL] + [W_T] * 14 + [W_TR] +
        text_row +
        [W_L] + [W_FILL] * 14 + [W_R] +
        [W_BL] + [W_B] * 14 + [W_BR]
    )

    with open(os.path.join(src, "field.s"), "w") as f:
        f.write("; field.s - GENERATED by tools/gen_assets.py. Do not edit by hand.\n")
        f.write("; One-screen field map + attribute table, and the text window tilemap.\n\n")
        f.write(".export fieldmap, fieldattr, winmap\n\n")
        f.write('.segment "RODATA"\n')
        f.write(fmt_bytes("fieldmap", flat, 32) + "\n\n")
        f.write(fmt_bytes("fieldattr", attr, 16) + "\n\n")
        f.write(fmt_bytes("winmap", winmap, 16) + "\n")

    # console preview
    glyphs = {T_GRASS: ".", T_FLOWER: ",", T_PATH: ":", T_TREE: "T",
              T_WALL: "#", T_BUSH: "o", T_WATER: "~"}
    print("Field map preview (N = NPC):")
    for y in range(H):
        line = ""
        for x in range(W):
            t = m[y][x]
            line += "N" if T_NPC0 <= t <= T_NPC0 + 3 else glyphs.get(t, "?")
        print(line)


def fmt_bytes(label, data, per_line):
    out = [f"{label}:"]
    for i in range(0, len(data), per_line):
        chunk = ", ".join(f"${b:02X}" for b in data[i:i + per_line])
        out.append(f"    .byte {chunk}")
    return "\n".join(out)


if __name__ == "__main__":
    main()
