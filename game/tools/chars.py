"""Character sprite art: 16x16 party/NPC sprites, three authored facings.

Down (front), up (back) and side (facing RIGHT). Left is the side art drawn
with the OAM horizontal-flip bit and the two tile columns swapped, so it costs
no extra CHR. Each facing has two frames for the walk cycle.

Sprite tile numbering (pattern table $1000, MMC3 R0):
    $00 down f0   $04 down f1   $08 up f0   $0C up f1   $10 side f0  $14 side f1
"""
from chrlib import grid_to_tiles

# colour 1 = dark (suit/shadow), 2 = mid (armour), 3 = light (visor/skin)

WARDEN_DOWN_0 = [
    "....111111......",
    "...12222221.....",
    "..1233333321....",
    "..1233333321....",
    "..1231331321....",
    "..1233333321....",
    "..1122222211....",
    "...1122221......",
    "..112222221.....",
    ".11222222221....",
    "1122122212211...",
    "1121122211211...",
    "1111222221111...",
    "...1222221......",
    "...12....21.....",
    "..122....221....",
]

WARDEN_DOWN_1 = [
    "....111111......",
    "...12222221.....",
    "..1233333321....",
    "..1233333321....",
    "..1231331321....",
    "..1233333321....",
    "..1122222211....",
    "...1122221......",
    "..112222221.....",
    ".11222222221....",
    "1122122212211...",
    "1121122211211...",
    "1111222221111...",
    "...1222221......",
    "...122..221.....",
    "...12....21.....",
]

WARDEN_UP_0 = [
    "....111111......",
    "...12222221.....",
    "..1222222221....",
    "..1222222221....",
    "..1221221221....",
    "..1222222221....",
    "..1122222211....",
    "...1122221......",
    "..112222221.....",
    ".11222222221....",
    "1122222222211...",
    "1121222221211...",
    "1111222221111...",
    "...1222221......",
    "...12....21.....",
    "..122....221....",
]

WARDEN_UP_1 = [
    "....111111......",
    "...12222221.....",
    "..1222222221....",
    "..1222222221....",
    "..1221221221....",
    "..1222222221....",
    "..1122222211....",
    "...1122221......",
    "..112222221.....",
    ".11222222221....",
    "1122222222211...",
    "1121222221211...",
    "1111222221111...",
    "...1222221......",
    "...122..221.....",
    "...12....21.....",
]

WARDEN_SIDE_0 = [
    "...1111111......",
    "..122222221.....",
    "..122223331.....",
    "..122223331.....",
    "..122222221.....",
    "..122222221.....",
    "..112222211.....",
    "...11222211.....",
    "..1122222111....",
    "..1222222211....",
    "..1222222212....",
    "..1122222111....",
    "...122222 1.....".replace(" ", "1"),
    "...1222221......",
    "...122..21......",
    "..122....21.....",
]

WARDEN_SIDE_1 = [
    "...1111111......",
    "..122222221.....",
    "..122223331.....",
    "..122223331.....",
    "..122222221.....",
    "..122222221.....",
    "..112222211.....",
    "...11222211.....",
    "..1122222111....",
    "..1222222211....",
    "..1222222212....",
    "..1122222111....",
    "...1222221......",
    "..1122221.......",
    ".112...1221.....",
    ".12.....121.....",
]


def build_sprite_bank():
    """Return the 128-tile sprite bank (MMC3 R0, sprite tiles $00-$7F)."""
    tiles = []
    for art in (WARDEN_DOWN_0, WARDEN_DOWN_1, WARDEN_UP_0, WARDEN_UP_1,
                WARDEN_SIDE_0, WARDEN_SIDE_1):
        tiles += grid_to_tiles(art, 2, 2)
    while len(tiles) < 128:
        tiles.append(bytes(16))
    return tiles


# Colour 1 is BLACK in every party sub-palette, and the art uses colour 1 as its
# outline: a hard black edge is the only thing that keeps a 16x16 figure legible
# over ash, dirt, road, grass, slag and deck plate alike. The old palette drew
# the hero in the same browns as the ground he walks on and he disappeared.
# Entry 0 must equal the backdrop ($0F) or it overwrites it -- see the
# palette-mirror trap in framework/HARDWARE.md.
SPRITE_PALETTE = [
    0x0F, 0x0F, 0x11, 0x30,     # 0 blue  - cool against a warm dead world
    0x0F, 0x0F, 0x16, 0x30,     # 1 red
    0x0F, 0x0F, 0x1A, 0x30,     # 2 green
    0x0F, 0x0F, 0x28, 0x30,     # 3 gold
]
