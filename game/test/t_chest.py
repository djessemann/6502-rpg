"""Treasure chests: open one, get its contents, and find it empty next time.

Boots a test-only ROM straight into Cinder Anchor 1 with encounters off, then
walks a path computed by BFS over the real map data.
"""
import sys, pathlib, subprocess, collections
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, UP, DOWN, LEFT, RIGHT
import areas, art_tiles, world
from maps import OB_CHEST, OB_WARP

MAP = "CINDER1"
ROM = GAME / "test" / "threnos_chest.nes"


def _map():
    ts_d = art_tiles.dungeon()
    m = areas.build_all(art_tiles.town(), ts_d)[world.MAP_NAMES[1:].index(MAP)]
    return m, ts_d.compile()["prop"]


def route_between(start, goal):
    """A walkable route that never steps on a warp: stairs fire on landing, so
    a naive shortest path happily walks the party onto the next floor."""
    m, prop = _map()
    blocked = {(o[1], o[2]) for o in m.objects if o[0] == OB_WARP} - {goal}
    prev = {start: None}
    q = collections.deque([start])
    dirs = {(0, -1): UP, (0, 1): DOWN, (-1, 0): LEFT, (1, 0): RIGHT}
    while q:
        x, y = q.popleft()
        for (dx, dy), d in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < m.w and 0 <= ny < m.h and (nx, ny) not in prev \
                    and (nx, ny) not in blocked \
                    and not prop[m.grid[ny][nx]] & 1:
                prev[(nx, ny)] = ((x, y), d)
                q.append((nx, ny))
    route, cur = [], goal
    while prev[cur]:
        cur, d = prev[cur][0], prev[cur][1]
        route.append(d)
    route.reverse()
    return route


def chests():
    m, _ = _map()
    return [(o[1], o[2], o[3], o[4]) for o in m.objects if o[0] == OB_CHEST]


def path_to_nearest_chest():
    ts_d = art_tiles.dungeon()
    m = areas.build_all(art_tiles.town(), ts_d)[world.MAP_NAMES[1:].index(MAP)]
    prop = ts_d.compile()["prop"]
    start = (12, 18)
    prev = {start: None}
    q = collections.deque([start])
    dirs = {(0, -1): UP, (0, 1): DOWN, (-1, 0): LEFT, (1, 0): RIGHT}
    while q:
        x, y = q.popleft()
        for (dx, dy), d in dirs.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < m.w and 0 <= ny < m.h and (nx, ny) not in prev \
                    and not prop[m.grid[ny][nx]] & 1:
                prev[(nx, ny)] = ((x, y), d)
                q.append((nx, ny))
    best = None
    for o in m.objects:
        if o[0] != OB_CHEST or (o[1], o[2]) not in prev:
            continue
        route, cur = [], (o[1], o[2])
        while prev[cur]:
            cur, d = prev[cur][0], prev[cur][1]
            route.append(d)
        route.reverse()
        if best is None or len(route) < len(best[0]):
            best = (route, o[1], o[2])
    return best


def build():
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID[MAP]}",
            "-D", "TEST_NO_ENCOUNTERS=1"]
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"{src.parent.name}_{src.stem}_t.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(ROM)] + objs,
                   check=True)


def text_region(f):
    """The window's interior, as a coarse fingerprint."""
    return np.asarray(f)[152:200, :, :].sum()


build()

# The item chest is reached by a long route that crosses a story trigger. With
# the window-aware walker that is no longer a problem, so this is asserted now.
from play import Player, route_between as _rb


def open_chest_run(gx, gy, tag):
    """A fresh boot per chest: some chests sit in a wing whose only link to the
    rest of the floor is the entrance tile, which warps the party out."""
    m, prop = _map()
    warps = {(o[1], o[2]) for o in m.objects if o[0] == OB_WARP}
    p = Player(ROM)
    p.walk(_rb(m, prop, (12, 18), (gx, gy), avoid=warps))
    p.tap(A, 3, 50)
    p.shot(f"chest_{tag}")
    return p, text_region(p.frame)


ok = True
cx, cy = [c for c in chests() if not c[3]][0][:2]
print(f"credits chest at ({cx},{cy})")
r, first = open_chest_run(cx, cy, "1_credits")
if first == 0:
    print("FAIL: no window appeared when the chest was opened"); ok = False

r.tap(A, 3, 60)
r.idle(20)
r.tap(A, 3, 50)
second = text_region(r.frame)
r.shot("chest_2_reopened")
if first == second:
    print("FAIL: re-opening shows the same text - the chest flag is not sticking")
    ok = False
else:
    print("ok   re-opening the same chest shows different text")

ix, iy, _f, item_id = next(c for c in chests() if c[3])
print(f"item chest at ({ix},{iy}), item id {item_id}")
p3, third = open_chest_run(ix, iy, "3_item")
# Control: the SAME cell, once the chest has been emptied. Standing one cell
# short does not work - pressing A there talks to the chest anyway, because the
# engine checks the cell the party faces.
p3.tap(A, 3, 60)
p3.idle(20)
p3.tap(A, 3, 50)
emptied = text_region(p3.frame)
p3.shot("chest_4_emptied")
if third == 0:
    print("FAIL: the item chest showed nothing"); ok = False
elif third == emptied:
    print("FAIL: the item chest reads the same once emptied"); ok = False
else:
    print("ok   the item chest pays out its item, then reads as taken")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
