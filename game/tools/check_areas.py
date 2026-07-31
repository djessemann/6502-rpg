#!/usr/bin/env python3
"""Verify every area map: size, object budget, reachability, message ids.

Run from anywhere:  python3 tools/check_areas.py
Also writes a contact sheet of all 27 maps to test/shots/areas.png.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import art_tiles                                                  # noqa: E402
import areas                                                      # noqa: E402
import script_text                                                # noqa: E402
import world                                                      # noqa: E402
from maps import OB_NPC, OB_CHEST, OB_WARP, OB_SIGN, OB_SHOP, \
    OB_INN, OB_SAVE, OB_TRIG                                      # noqa: E402
from tileset import PROP_SOLID                                    # noqa: E402

MAX_OBJECTS = 11
MSG_KINDS = (OB_NPC, OB_SIGN, OB_SHOP, OB_INN, OB_SAVE, OB_TRIG)
KIND_NAME = {OB_NPC: "NPC", OB_CHEST: "CHEST", OB_WARP: "WARP", OB_SIGN: "SIGN",
             OB_SHOP: "SHOP", OB_INN: "INN", OB_SAVE: "SAVE", OB_TRIG: "TRIG"}

# Colours for the contact sheet, by metatile name.
COLOURS = {
    # town
    "DIRT": (122, 98, 74), "SAND": (206, 184, 130), "GRASS": (78, 132, 62),
    "WATER": (38, 84, 160), "PLAZA": (176, 158, 128), "WALL": (96, 96, 104),
    "ROOF": (140, 74, 62), "DOOR": (250, 216, 96), "WINDOW": (92, 132, 180),
    "COUNTER": (150, 120, 80), "TERMINAL": (120, 220, 230),
    "CRATE": (150, 118, 70), "PLANT": (56, 150, 70), "FENCE": (110, 92, 72),
    "STAIRS": (232, 232, 232),
    # dungeon
    "FLOOR": (104, 104, 112), "GRATE": (86, 116, 122), "SLAG": (128, 78, 58),
    "VOID": (12, 12, 18), "LAVA": (224, 92, 40), "COOL": (58, 128, 148),
    "PILLAR": (60, 60, 70), "PIPE": (72, 84, 96), "CORE": (204, 96, 232),
    "STAIRD": (250, 250, 250), "STAIRU": (200, 200, 250),
    "CHEST": (240, 200, 80), "RUBBLE": (74, 68, 62),
}
OBJ_COLOUR = {OB_NPC: (255, 80, 80), OB_CHEST: (255, 230, 60),
              OB_WARP: (80, 255, 120), OB_SIGN: (255, 160, 60),
              OB_SHOP: (120, 180, 255), OB_INN: (255, 120, 255),
              OB_SAVE: (120, 255, 255), OB_TRIG: (255, 60, 200)}


def build():
    ts_town = art_tiles.town()
    ts_dun = art_tiles.dungeon()
    return areas.build_all(ts_town, ts_dun), {"town": ts_town.compile(),
                                              "dungeon": ts_dun.compile()}


def flood(m, prop, start):
    """Reachable cells from `start` over metatiles without PROP_SOLID."""
    w, h = m.w, m.h
    if prop[m.grid[start[1]][start[0]]] & PROP_SOLID:
        return set()
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen:
                continue
            if prop[m.grid[ny][nx]] & PROP_SOLID:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return seen


def check_map(m, compiled, msg_names, errors):
    prop = compiled[m.tileset.name]["prop"]
    names = [n for n, _, _, _ in m.tileset.metas]
    town = m.tileset.name == "town"

    def bad(s):
        errors.append(f"{m.name}: {s}")

    lo, hi = (32, 24) if town else (32, 24)
    max_w, max_h = (40, 32) if town else (48, 40)
    if not (lo <= m.w <= max_w and hi <= m.h <= max_h):
        bad(f"size {m.w}x{m.h} outside the allowed range "
            f"({lo}x{hi}..{max_w}x{max_h})")
    if m.w < 16 or m.h < 16 or m.w > 128 or m.h > 128:
        bad(f"size {m.w}x{m.h} breaks the engine limits")
    if len(m.objects) > MAX_OBJECTS:
        bad(f"{len(m.objects)} objects > {MAX_OBJECTS}")
    if max(max(r) for r in m.grid) > 127:
        bad("metatile id > 127")

    warps = [o for o in m.objects if o[0] == OB_WARP]
    if not warps:
        bad("no warp out")
        return
    entry = (warps[0][1], warps[0][2])
    reach = flood(m, prop, entry)
    if not reach:
        bad(f"entry cell {entry} is solid ({names[m.grid[entry[1]][entry[0]]]})")
        return

    for kind, gx, gy, a0, a1, a2, a3, a4 in m.objects:
        cell = names[m.grid[gy][gx]]
        if (gx, gy) not in reach:
            bad(f"{KIND_NAME[kind]} at {gx},{gy} on {cell} is unreachable")
        if kind in MSG_KINDS:
            mid = a2 | (a3 << 8)
            if mid >= len(script_text.MESSAGES):
                bad(f"{KIND_NAME[kind]} at {gx},{gy}: message id {mid} does "
                    f"not exist")
        if kind == OB_WARP and a0 != 0:
            if cell not in ("STAIRD", "STAIRU"):
                bad(f"inter-floor warp at {gx},{gy} is on {cell}, "
                    f"not STAIRD/STAIRU")
        if kind == OB_WARP and a0 >= len(world.MAP_NAMES):
            bad(f"warp at {gx},{gy} targets map {a0}, which does not exist")

    # every object must sit on its own cell (FindObject returns the first hit)
    cells = [(o[1], o[2]) for o in m.objects]
    if len(set(cells)) != len(cells):
        bad("two objects share a cell")


def check_links(maps, errors):
    """Every stair must land on the matching stair of the destination map."""
    by_name = {m.name: m for m in maps}
    for m in maps:
        for kind, gx, gy, a0, a1, a2, a3, a4 in m.objects:
            if kind != OB_WARP or a0 == 0:
                continue
            dest = world.MAP_NAMES[a0]
            d = by_name[dest]
            if not (0 <= a1 < d.w and 0 <= a2 < d.h):
                errors.append(f"{m.name}: stair to {dest} lands off the map")
                continue
            name = [n for n, _, _, _ in d.tileset.metas][d.grid[a2][a1]]
            if name not in ("STAIRD", "STAIRU", "DOOR"):
                errors.append(f"{m.name}: stair to {dest} lands on {name} "
                              f"at {a1},{a2}")


def render(maps, path, scale=3):
    from PIL import Image, ImageDraw
    cols = 6
    cw, ch = 48 * scale + 10, 40 * scale + 16
    rows = (len(maps) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * ch), (24, 24, 28))
    d = ImageDraw.Draw(img)
    for i, m in enumerate(maps):
        names = [n for n, _, _, _ in m.tileset.metas]
        ox = (i % cols) * cw + 5
        oy = (i // cols) * ch + 12
        tile = Image.new("RGB", (m.w, m.h))
        px = tile.load()
        for y in range(m.h):
            for x in range(m.w):
                px[x, y] = COLOURS.get(names[m.grid[y][x]], (255, 0, 255))
        for kind, gx, gy, *_ in m.objects:
            px[gx, gy] = OBJ_COLOUR[kind]
        img.paste(tile.resize((m.w * scale, m.h * scale), Image.NEAREST),
                  (ox, oy))
        d.text((ox, oy - 11), f"{m.name} {m.w}x{m.h}", fill=(210, 210, 220))
    img.save(path)
    return path


def main():
    maps, compiled = build()
    msg_names = {n for n, _ in script_text.MESSAGES}
    errors = []
    order = world.MAP_NAMES[1:]
    if [m.name for m in maps] != order:
        errors.append(f"build_all order is wrong: {[m.name for m in maps]}")
    total = 0
    print(f"{'map':<10} {'size':>7} {'objs':>5} {'bytes':>6}")
    for m in maps:
        check_map(m, compiled, msg_names, errors)
        sz = m.size_estimate()
        total += sz
        print(f"{m.name:<10} {m.w:>3}x{m.h:<3} {len(m.objects):>5} {sz:>6}")
    check_links(maps, errors)
    print(f"{'TOTAL':<10} {len(maps):>7} maps {total:>10} bytes")

    shots = ROOT / "test" / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    print("contact sheet:", render(maps, shots / "areas.png"))

    if errors:
        print(f"\n{len(errors)} PROBLEM(S):")
        for e in errors:
            print("  " + e)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
