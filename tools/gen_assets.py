#!/usr/bin/env python3
"""Dev-time asset generator for the vertical slice.

Source-of-truth for the field CHR tiles and the one-screen map. NOT part of the
`make` build: it emits committed .s files (src/chr.s, src/field.s) that ca65
assembles. Re-run by hand after editing art, then commit the generated .s.

Tiles are 8x8, pixel values 0-3 selecting a color within the active palette.
Palette is chosen per-tile (water -> bg palette 1, everything else -> palette 0)
and baked into the attribute table.
"""

import os

# ---------------------------------------------------------------------------
# Tile art. '0'-'3' = pixel color index within the tile's palette.
# Tile $00 must stay all-zero (blank). No visible field tile uses value 0, so
# the backdrop color never bleeds through a seam.
# ---------------------------------------------------------------------------
TILES = {
    0x00: [  # blank
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
    ],
    0x01: [  # grass
        "11112111",
        "11111111",
        "21111121",
        "11111111",
        "11211111",
        "11111111",
        "11111121",
        "21111111",
    ],
    0x02: [  # flower
        "11111111",
        "11122111",
        "11233211",
        "11232311",
        "11233211",
        "11122111",
        "11111111",
        "11111111",
    ],
    0x03: [  # path / dirt
        "33333333",
        "33133333",
        "33333313",
        "33333333",
        "31333333",
        "33333133",
        "33333333",
        "33313333",
    ],
    0x04: [  # tree (solid)
        "12222221",
        "22222222",
        "22322322",
        "22222222",
        "22322322",
        "22222222",
        "12333321",
        "11333311",
    ],
    0x05: [  # brick wall (solid)
        "33333333",
        "33333333",
        "13131313",
        "33333333",
        "33333333",
        "31313131",
        "33333333",
        "33333333",
    ],
    0x06: [  # bush
        "11111111",
        "11222211",
        "12222221",
        "12222221",
        "12222221",
        "11222211",
        "11111111",
        "11111111",
    ],
    0x07: [  # water (solid, palette 1)
        "11111111",
        "12211221",
        "11111111",
        "21122112",
        "11111111",
        "12211221",
        "11111111",
        "21122112",
    ],
}

WATER = 0x07


def tile_to_chr(rows):
    """Encode one 8x8 tile to 16 planar bytes (8 plane0, then 8 plane1)."""
    plane0, plane1 = [], []
    for row in rows:
        b0 = b1 = 0
        for px in row:
            v = int(px)
            b0 = (b0 << 1) | (v & 1)
            b1 = (b1 << 1) | ((v >> 1) & 1)
        plane0.append(b0)
        plane1.append(b1)
    return plane0 + plane1


# ---------------------------------------------------------------------------
# Map: 32x30 tiles, one screen. Built programmatically for exact columns.
# ---------------------------------------------------------------------------
W, H = 32, 30
GRASS, FLOWER, PATH, TREE, WALL, BUSH = 0x01, 0x02, 0x03, 0x04, 0x05, 0x06

m = [[GRASS] * W for _ in range(H)]

# Tree border
for x in range(W):
    m[0][x] = TREE
    m[H - 1][x] = TREE
for y in range(H):
    m[y][0] = TREE
    m[y][W - 1] = TREE

# Water pond (top-left), uses palette 1
for y in range(3, 8):
    for x in range(3, 9):
        m[y][x] = WATER

# Vertical path at col 16, horizontal path at row 22
for y in range(1, H - 1):
    m[y][16] = PATH
for x in range(1, W - 1):
    m[x and 22 or 22][x] = PATH  # row 22

# Little brick hut (top-right): walls outline
for x in range(20, 26):
    m[3][x] = WALL
    m[7][x] = WALL
for y in range(3, 8):
    m[y][20] = WALL
    m[y][25] = WALL

# Scatter flowers and bushes at fixed spots (kept off the paths/structures)
for (x, y) in [(5, 12), (9, 18), (13, 25), (27, 10), (29, 19), (23, 24), (6, 26)]:
    m[y][x] = FLOWER
for (x, y) in [(11, 11), (28, 6), (4, 20), (19, 27), (26, 14), (8, 9)]:
    m[y][x] = BUSH


def attr_table(grid):
    """64-byte attribute table; palette 1 where a 16x16 quadrant holds water."""
    attr = [0] * 64
    for ay in range(8):
        for ax in range(8):
            byte = 0
            for q in range(4):  # quadrants: TL,TR,BL,BR
                qx, qy = q & 1, q >> 1
                pal = 0
                for ty in range(2):
                    for tx in range(2):
                        x = ax * 4 + qx * 2 + tx
                        y = ay * 4 + qy * 2 + ty
                        if 0 <= y < H and 0 <= x < W and grid[y][x] == WATER:
                            pal = 1
                byte |= pal << (q * 2)
            attr[ay * 8 + ax] = byte
    return attr


def fmt_bytes(label, data, per_line=16):
    out = [f"{label}:"]
    for i in range(0, len(data), per_line):
        chunk = ", ".join(f"${b:02X}" for b in data[i:i + per_line])
        out.append(f"    .byte {chunk}")
    return "\n".join(out)


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, "src")

    # CHR
    chr_bytes = []
    for tid in range(max(TILES) + 1):
        chr_bytes += tile_to_chr(TILES.get(tid, ["00000000"] * 8))
    with open(os.path.join(src, "chr.s"), "w") as f:
        f.write("; chr.s - GENERATED by tools/gen_assets.py. Do not edit by hand.\n")
        f.write("; Background field tiles for pattern table 0. CHR region fill\n")
        f.write("; pads the rest of the 8KB to zero (see nes.cfg).\n\n")
        f.write('.segment "CHARS"\n')
        f.write("    ; tiles $00-$%02X (16 bytes each)\n" % max(TILES))
        for i in range(0, len(chr_bytes), 16):
            row = ", ".join(f"${b:02X}" for b in chr_bytes[i:i + 16])
            f.write(f"    .byte {row}   ; tile ${i // 16:02X}\n")

    # Map + attributes
    flat = [m[y][x] for y in range(H) for x in range(W)]
    attr = attr_table(m)
    with open(os.path.join(src, "field.s"), "w") as f:
        f.write("; field.s - GENERATED by tools/gen_assets.py. Do not edit by hand.\n")
        f.write("; One-screen field: 32x30 nametable map + 64-byte attribute table.\n\n")
        f.write(".export fieldmap, fieldattr\n\n")
        f.write('.segment "RODATA"\n')
        f.write(fmt_bytes("fieldmap", flat, per_line=32) + "\n\n")
        f.write(fmt_bytes("fieldattr", attr, per_line=16) + "\n")

    # Console preview
    glyph = {GRASS: ".", FLOWER: ",", PATH: ":", TREE: "T",
             WALL: "#", BUSH: "o", WATER: "~"}
    print("Field map preview:")
    for y in range(H):
        print("".join(glyph.get(m[y][x], "?") for x in range(W)))


if __name__ == "__main__":
    main()
