#!/usr/bin/env python3
"""Dump every piece of THRENOS art to test/shots/ as PNGs, at NES colours.

This is an eyeball tool, not a build step. It renders what the hardware would
actually show: 2bpp art through a real NES palette, at 1x (to judge silhouette)
and at 3-4x (to judge detail).

    python3 tools/render_art.py
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from PIL import Image, ImageDraw                              # noqa: E402

import art_tiles                                              # noqa: E402
import areas                                                  # noqa: E402
import chars                                                  # noqa: E402
import font                                                   # noqa: E402
import gamedata                                               # noqa: E402
import monster_art                                            # noqa: E402
import title_art                                              # noqa: E402
import world                                                  # noqa: E402

SHOTS = ROOT / "test" / "shots"

# --- the NES master palette (2C02, Mesen-ish) ---------------------------------
NES = [
    (0x66, 0x66, 0x66), (0x00, 0x2A, 0x88), (0x14, 0x12, 0xA7), (0x3B, 0x00, 0xA4),
    (0x5C, 0x00, 0x7E), (0x6E, 0x00, 0x40), (0x6C, 0x06, 0x00), (0x56, 0x1D, 0x00),
    (0x33, 0x35, 0x00), (0x0B, 0x48, 0x00), (0x00, 0x52, 0x00), (0x00, 0x4F, 0x08),
    (0x00, 0x40, 0x4D), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xAD, 0xAD, 0xAD), (0x15, 0x5F, 0xD9), (0x42, 0x40, 0xFF), (0x75, 0x27, 0xFE),
    (0xA0, 0x1A, 0xCC), (0xB7, 0x1E, 0x7B), (0xB5, 0x31, 0x20), (0x99, 0x4E, 0x00),
    (0x6B, 0x6D, 0x00), (0x38, 0x87, 0x00), (0x0C, 0x93, 0x00), (0x00, 0x8F, 0x32),
    (0x00, 0x7C, 0x8D), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFF, 0xFE, 0xFF), (0x64, 0xB0, 0xFF), (0x92, 0x90, 0xFF), (0xC6, 0x76, 0xFF),
    (0xF3, 0x6A, 0xFF), (0xFE, 0x6E, 0xCC), (0xFE, 0x81, 0x70), (0xEA, 0x9E, 0x22),
    (0xBC, 0xBE, 0x00), (0x88, 0xD8, 0x00), (0x5C, 0xE4, 0x30), (0x45, 0xE0, 0x82),
    (0x48, 0xCD, 0xDE), (0x4F, 0x4F, 0x4F), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
    (0xFF, 0xFE, 0xFF), (0xC0, 0xDF, 0xFF), (0xD3, 0xD2, 0xFF), (0xE8, 0xC8, 0xFF),
    (0xFB, 0xC2, 0xFF), (0xFE, 0xC4, 0xEA), (0xFE, 0xCC, 0xC5), (0xF7, 0xD8, 0xA5),
    (0xE4, 0xE5, 0x94), (0xCF, 0xEF, 0x96), (0xBD, 0xF4, 0xAB), (0xB3, 0xF3, 0xCC),
    (0xB5, 0xEB, 0xF2), (0xB8, 0xB8, 0xB8), (0x00, 0x00, 0x00), (0x00, 0x00, 0x00),
]


def rgb(c):
    return NES[c & 0x3F]


UI_PAL = [0x0F, 0x00, 0x10, 0x30]

# The battle palettes, copied from batt_pal in src/battle.s.
BATT_PAL = [[0x0F, 0x16, 0x27, 0x30],
            [0x0F, 0x11, 0x21, 0x30],
            [0x0F, 0x09, 0x19, 0x29],
            [0x0F, 0x00, 0x10, 0x30]]


def draw_grid(img, rows, ox, oy, pal, scale, bg=None):
    """Paint a character grid ('.'/'1'/'2'/'3') at (ox,oy)."""
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            v = 0 if ch in ".0 " else int(ch)
            if v == 0:
                if bg is None:
                    continue
                col = bg
            else:
                col = rgb(pal[v])
            for sy in range(scale):
                for sx in range(scale):
                    px[ox + x * scale + sx, oy + y * scale + sy] = col


def tile_rows(tile):
    """16-byte planar CHR tile -> 8 strings of '0'..'3'."""
    out = []
    for y in range(8):
        lo, hi = tile[y], tile[y + 8]
        out.append("".join(str(((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1))
                           for x in range(8)))
    return out


def label(d, x, y, s, fill=(200, 200, 210)):
    d.text((x, y), s, fill=fill)


# --- 1. font + UI bank --------------------------------------------------------
def render_font(scale=4):
    tiles = font.build_font_bank()
    cols, rows = 16, 4
    cell = 8 * scale + 6
    img = Image.new("RGB", (cols * cell + 8, rows * cell + 24), (20, 20, 26))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, "font bank (CHR 0) at %dx, UI palette 0F/00/10/30" % scale)
    for i, t in enumerate(tiles):
        ox = 4 + (i % cols) * cell
        oy = 18 + (i // cols) * cell
        d.rectangle([ox - 1, oy - 1, ox + 8 * scale, oy + 8 * scale],
                    fill=rgb(UI_PAL[0]))
        draw_grid(img, tile_rows(t), ox, oy, UI_PAL, scale)
    p = SHOTS / "font.png"
    img.save(p)
    return p


def render_font_1x():
    """A sentence of real text at 1x, the way a player reads it."""
    lines = ["THE ARCHON SPEAKS: \"YOU CAME BACK.\"",
             "WARDEN  HP 112/112  MP 24/24  LV 12",
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789"]
    tiles = font.build_font_bank()
    w = max(len(s) for s in lines) * 8
    h = len(lines) * 8 + 2
    for scale in (1, 3):
        img = Image.new("RGB", (w * scale, h * scale), rgb(UI_PAL[0]))
        for r, s in enumerate(lines):
            for i, ch in enumerate(s):
                idx = font.CHARSET.index(ch) if ch in font.CHARSET else 0
                draw_grid(img, tile_rows(tiles[idx]), i * 8 * scale,
                          r * 8 * scale, UI_PAL, scale)
        img.save(SHOTS / f"font_text_{scale}x.png")
    return SHOTS / "font_text_1x.png"


# --- 2. sprite sheet ----------------------------------------------------------
def render_sprites(scale=4):
    tiles = chars.build_sprite_bank()
    names = ["down f0", "down f1", "up f0", "up f1", "side f0", "side f1"]
    pals = [chars.SPRITE_PALETTE[i * 4:i * 4 + 4] for i in range(4)]
    cell = 16 * scale + 10
    img = Image.new("RGB", (len(names) * cell + 60, len(pals) * cell + 30),
                    (18, 18, 24))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, "sprite bank, 4 sprite sub-palettes, %dx" % scale)
    for pi, pal in enumerate(pals):
        label(d, 4, 22 + pi * cell + 8 * scale,
              " ".join(f"{c:02X}" for c in pal), (160, 160, 170))
        for fi in range(len(names)):
            ox = 58 + fi * cell
            oy = 20 + pi * cell
            d.rectangle([ox - 2, oy - 2, ox + 16 * scale + 1, oy + 16 * scale + 1],
                        fill=(40, 40, 48))
            for q in range(4):
                t = tiles[fi * 4 + q]
                draw_grid(img, tile_rows(t), ox + (q % 2) * 8 * scale,
                          oy + (q // 2) * 8 * scale, pal, scale)
            if pi == 0:
                label(d, ox, 8, names[fi])
    p = SHOTS / "sprites.png"
    img.save(p)
    return p


def render_sprites_1x():
    """The hero at 1x on the three grounds he actually walks on."""
    tiles = chars.build_sprite_bank()
    pal = chars.SPRITE_PALETTE[0:4]
    grounds = [(art_tiles.overworld(), "ASH"), (art_tiles.town(), "PLAZA"),
               (art_tiles.dungeon(), "FLOOR")]
    scale = 4
    img = Image.new("RGB", (3 * (32 * scale + 8) + 8, 32 * scale + 24), (16, 16, 20))
    d = ImageDraw.Draw(img)
    label(d, 4, 4, "hero at %dx over real ground (silhouette check)" % scale)
    for i, (ts, gname) in enumerate(grounds):
        c = ts.compile()
        meta = ts.metas[ts.id(gname)]
        gpal = [0x0F] + list(ts.palettes[meta[2]]) if meta[2] < 3 else UI_PAL
        ox = 4 + i * (32 * scale + 8)
        oy = 18
        for my in range(2):
            for mx in range(2):
                draw_grid(img, meta[1], ox + mx * 16 * scale, oy + my * 16 * scale,
                          gpal, scale)
        for q in range(4):
            draw_grid(img, tile_rows(tiles[q]), ox + 8 * scale + (q % 2) * 8 * scale,
                      oy + 8 * scale + (q // 2) * 8 * scale, pal, scale)
    p = SHOTS / "sprites_over_ground.png"
    img.save(p)
    return p


# --- 3. tilesets --------------------------------------------------------------
def pal_for(ts, pi):
    return UI_PAL if pi == 3 else [0x0F] + list(ts.palettes[pi])


def render_tileset(ts, scale=3):
    c = ts.compile()
    cols = 8
    cell = 16 * scale + 16
    rows = (len(ts.metas) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + 8, rows * cell + 40), (18, 18, 22))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, f"tileset {ts.name}: {len(ts.metas)} metatiles, "
                   f"{c['ntiles']} unique 8x8 tiles, {scale}x")
    label(d, 6, 16, "palettes  " + "   ".join(
        f"{i}:" + " ".join(f"{v:02X}" for v in ts.palettes[i]) for i in range(3))
        + f"   3:UI {' '.join(f'{v:02X}' for v in UI_PAL[1:])}", (170, 170, 180))
    for i, (name, art, pi, prop) in enumerate(ts.metas):
        ox = 6 + (i % cols) * cell
        oy = 34 + (i // cols) * cell
        p = pal_for(ts, pi)
        d.rectangle([ox - 1, oy - 1, ox + 16 * scale, oy + 16 * scale],
                    fill=rgb(p[0]))
        draw_grid(img, art, ox, oy, p, scale)
        label(d, ox, oy + 16 * scale + 1, f"{name} p{pi}", (190, 190, 200))
    p = SHOTS / f"tileset_{ts.name}.png"
    img.save(p)
    return p


def render_tileset_field(ts, scale=2):
    """A 2x2 block of every metatile against its neighbours, to see tiling."""
    c = ts.compile()
    per = 4
    cell = 32 * scale + 14
    cols = 8
    rows = (len(ts.metas) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + 8, rows * cell + 24), (18, 18, 22))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, f"{ts.name}: each metatile tiled 2x2 ({scale}x) - seam check")
    for i, (name, art, pi, prop) in enumerate(ts.metas):
        ox = 6 + (i % cols) * cell
        oy = 20 + (i // cols) * cell
        p = pal_for(ts, pi)
        d.rectangle([ox - 1, oy - 1, ox + 32 * scale, oy + 32 * scale], fill=rgb(p[0]))
        for my in range(2):
            for mx in range(2):
                draw_grid(img, art, ox + mx * 16 * scale, oy + my * 16 * scale,
                          p, scale)
        label(d, ox, oy + 32 * scale + 1, name, (190, 190, 200))
    p = SHOTS / f"tilefield_{ts.name}.png"
    img.save(p)
    return p


# --- 4. monsters --------------------------------------------------------------
def monster_entries():
    """(display name, art key, art dict) for every monster in the game."""
    out = []
    for m in gamedata.MONSTERS:
        key = gamedata.art_key(m[0])
        out.append((m[0], key, monster_art.MONSTERS[key]))
    return out


def render_monsters_1x():
    """Every distinct design at 1x on the battle backdrop. Silhouette test."""
    keys = sorted(monster_art.MONSTERS)
    cols = 8
    cell = 72
    rows = (len(keys) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + 8, rows * cell + 24), rgb(0x0F))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, "every monster design at 1x, battle sub-palette 0 "
                   "(0F/16/27/30) - silhouette test")
    for i, k in enumerate(keys):
        a = monster_art.MONSTERS[k]
        ox = 6 + (i % cols) * cell + (64 - a["size"]) // 2
        oy = 22 + (i // cols) * cell
        draw_grid(img, a["art"], ox, oy, BATT_PAL[0], 1)
        label(d, 6 + (i % cols) * cell, oy + 66, k[:11], (150, 150, 160))
    p = SHOTS / "monsters_1x.png"
    img.save(p)
    return p


def render_monsters_pal1():
    keys = sorted(monster_art.MONSTERS)
    cols = 8
    cell = 72
    rows = (len(keys) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + 8, rows * cell + 24), rgb(0x0F))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, "same designs, battle sub-palette 1 (0F/11/21/30) - "
                   "slot 2 of a mixed formation")
    for i, k in enumerate(keys):
        a = monster_art.MONSTERS[k]
        ox = 6 + (i % cols) * cell + (64 - a["size"]) // 2
        oy = 22 + (i // cols) * cell
        draw_grid(img, a["art"], ox, oy, BATT_PAL[1], 1)
        label(d, 6 + (i % cols) * cell, oy + 66, k[:11], (150, 150, 160))
    p = SHOTS / "monsters_1x_pal1.png"
    img.save(p)
    return p


def render_monsters_big(scale=3, per_sheet=10):
    keys = sorted(monster_art.MONSTERS)
    out = []
    for s in range(0, len(keys), per_sheet):
        chunk = keys[s:s + per_sheet]
        cols = 5
        cell = 64 * scale + 20
        rows = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (cols * cell + 8, rows * cell + 22), rgb(0x0F))
        d = ImageDraw.Draw(img)
        label(d, 6, 4, f"monsters {s}-{s+len(chunk)-1} at {scale}x")
        for i, k in enumerate(chunk):
            a = monster_art.MONSTERS[k]
            ox = 6 + (i % cols) * cell + (64 - a["size"]) * scale // 2
            oy = 20 + (i // cols) * cell
            draw_grid(img, a["art"], ox, oy, BATT_PAL[0], scale)
            label(d, 6 + (i % cols) * cell, oy + 64 * scale + 2, k, (170, 170, 180))
        p = SHOTS / f"monsters_{scale}x_{s//per_sheet}.png"
        img.save(p)
        out.append(p)
    return out


def render_zone_sheets():
    """The monsters that actually share a screen, side by side at 1x."""
    zones = gamedata.ZONES
    forms = gamedata.FORMATIONS
    names = [m[0] for m in gamedata.MONSTERS]
    rowh = 76
    img = Image.new("RGB", (8 * 72 + 60, len(zones) * rowh + 24), rgb(0x0F))
    d = ImageDraw.Draw(img)
    label(d, 6, 4, "encounter zones: the designs a player sees together, 1x")
    for zi, z in enumerate(zones):
        oy = 22 + zi * rowh
        label(d, 4, oy + 24, f"z{zi}", (200, 200, 60))
        seen = []
        for f in z:
            t0 = forms[f][0]
            t1 = forms[f][2]
            for t in (t0, t1):
                if t and t not in seen:
                    seen.append(t)
        for i, t in enumerate(seen[:8]):
            a = monster_art.MONSTERS[gamedata.art_key(t)]
            ox = 34 + i * 72 + (64 - a["size"]) // 2
            draw_grid(img, a["art"], ox, oy, BATT_PAL[i % 2], 1)
            label(d, 34 + i * 72, oy + 66, t[:11], (150, 150, 160))
    p = SHOTS / "monsters_by_zone.png"
    img.save(p)
    return p


# --- 5. title screen ----------------------------------------------------------
def render_title(scale=3):
    tiles, nt, attr = title_art.build()
    pals = title_art.PALETTES
    img = Image.new("RGB", (256 * scale, 240 * scale), (0, 0, 0))
    for ty in range(30):
        for tx in range(32):
            t = tiles[nt[ty * 32 + tx] - title_art.BASE_TILE]
            qy, qx = ty // 2, tx // 2
            byte = attr[(qy // 2) * 8 + (qx // 2)]
            sh = ((qy & 1) << 2) | ((qx & 1) << 1)
            pi = (byte >> sh) & 3
            draw_grid(img, tile_rows(t), tx * 8 * scale, ty * 8 * scale,
                      pals[pi], scale, bg=rgb(pals[pi][0]))
    img.save(SHOTS / f"title_{scale}x.png")
    img.resize((256, 240), Image.NEAREST).save(SHOTS / "title_1x.png")
    return SHOTS / f"title_{scale}x.png", len(tiles)


# --- 6. maps, drawn with the real tile art ------------------------------------
def paint_map(m, scale=1):
    ts = m.tileset
    img = Image.new("RGB", (m.w * 16 * scale, m.h * 16 * scale), (0, 0, 0))
    for y in range(m.h):
        for x in range(m.w):
            name, art, pi, prop = ts.metas[m.grid[y][x]]
            p = pal_for(ts, pi)
            draw_grid(img, art, x * 16 * scale, y * 16 * scale, p, scale,
                      bg=rgb(p[0]))
    return img


def render_area_sheets():
    ts_town = art_tiles.town()
    ts_dun = art_tiles.dungeon()
    maps = areas.build_all(ts_town, ts_dun)
    groups = [("towns", maps[:6]), ("dun_a", maps[6:15]),
              ("dun_b", maps[15:21]), ("dun_c", maps[21:])]
    out = []
    for gname, ms in groups:
        cols = 3
        cw = 48 * 16 + 12
        chh = 40 * 16 + 22
        rows = (len(ms) + cols - 1) // cols
        img = Image.new("RGB", (cols * cw, rows * chh), (16, 16, 20))
        d = ImageDraw.Draw(img)
        for i, m in enumerate(ms):
            ox = (i % cols) * cw + 6
            oy = (i // cols) * chh + 16
            img.paste(paint_map(m), (ox, oy))
            label(d, ox, oy - 13, f"{m.name}  {m.w}x{m.h}  ({m.tileset.name})",
                  (230, 230, 120))
        img.save(SHOTS / f"maps_{gname}.png")
        # a half-size copy that is actually readable in one glance
        img.resize((img.width // 2, img.height // 2), Image.LANCZOS).save(
            SHOTS / f"maps_{gname}_half.png")
        out.append(SHOTS / f"maps_{gname}.png")
    return out


def render_overworld():
    ts = art_tiles.overworld()
    m = world.overworld_map(ts)
    img = paint_map(m)                       # 2048 x 2048
    img.save(SHOTS / "overworld_art_1x.png")
    img.resize((1024, 1024), Image.LANCZOS).save(SHOTS / "overworld_art_half.png")
    img.crop((0, 0, 512, 512)).save(SHOTS / "overworld_art_crop_nw.png")
    img.crop((768, 768, 1280, 1280)).save(SHOTS / "overworld_art_crop_mid.png")
    grid = world.build_overworld_grid()
    world.render_png(grid, SHOTS / "overworld_key.png", scale=4)
    return SHOTS / "overworld_art_half.png"


def render_screen(m, cx, cy, path, scale=3):
    """One 256x240 screenful of a map, the way the player sees it."""
    img = paint_map(m)
    x0 = max(0, min(m.w * 16 - 256, cx * 16 - 128))
    y0 = max(0, min(m.h * 16 - 240, cy * 16 - 120))
    view = img.crop((x0, y0, x0 + 256, y0 + 240))
    view.resize((256 * scale, 240 * scale), Image.NEAREST).save(path)
    return path


def render_screens():
    ts_town = art_tiles.town()
    ts_dun = art_tiles.dungeon()
    maps = {m.name: m for m in areas.build_all(ts_town, ts_dun)}
    ts_ow = art_tiles.overworld()
    ow = world.overworld_map(ts_ow)
    shots = []
    for name, cx, cy in [("LANDFALL", 16, 12), ("EMBERREST", 16, 12),
                         ("KELPHOLD", 16, 12), ("CINDER1", 16, 12),
                         ("TIDE2", 16, 12), ("EREBUS3", 16, 12)]:
        shots.append(render_screen(maps[name], cx, cy,
                                   SHOTS / f"screen_{name}.png"))
    shots.append(render_screen(ow, 44, 66, SHOTS / "screen_OVERWORLD.png"))
    shots.append(render_screen(ow, 92, 30, SHOTS / "screen_OVERWORLD_ne.png"))
    return shots


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    print(render_font())
    print(render_font_1x())
    print(render_sprites())
    print(render_sprites_1x())
    for f in art_tiles.ALL_TILESETS:
        ts = f()
        print(render_tileset(ts))
        print(render_tileset_field(ts))
    print(render_monsters_1x())
    print(render_monsters_pal1())
    for p in render_monsters_big():
        print(p)
    print(render_zone_sheets())
    t, n = render_title()
    print(t, f"({n} unique tiles)")
    for p in render_area_sheets():
        print(p)
    print(render_overworld())
    for p in render_screens():
        print(p)


if __name__ == "__main__":
    main()
