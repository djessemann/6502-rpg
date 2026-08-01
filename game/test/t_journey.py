"""A player's first minutes, on the real ROM, with no test defines at all.

Every other test in this repo builds its own ROM and drops the party next to
the thing it wants to check. This one runs the shipped threnos.nes and plays
it: the title, the muster, a walk, the overworld-to-town warp, the field menu,
the walk back out, and a loop on the overworld. If one of those is broken in
the ROM that ships rather than in a test build, this is what notices.

What it deliberately does NOT do is claim a playthrough. A scripted walk of
eighty cells does not reliably arrive: one blocked step desynchronises the rest
of the route, and nothing in a frame tells the walker where the party actually
is. Reaching the ending unattended needs a position readout the engine does not
have -- see HANDOFF.md.
"""
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

import numpy as np                                                # noqa: E402
from harness import Run, press, A, B, START                       # noqa: E402
from play import start_game, arena_fraction, window_open          # noqa: E402
import glyphs                                                     # noqa: E402
import art_tiles, world                                           # noqa: E402
from tileset import PROP_SOLID, PROP_WATER, PROP_HIGH             # noqa: E402
from harness import UP, DOWN, LEFT, RIGHT                         # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


# --- routing over the real overworld -----------------------------------------
TS = art_tiles.overworld()
PROP = TS.compile()["prop"]
OW = world.overworld_map(TS)
DIRS = {(0, -1): UP, (0, 1): DOWN, (-1, 0): LEFT, (1, 0): RIGHT}


def walkable(x, y):
    p = PROP[OW.grid[y][x]]
    return not (p & (PROP_SOLID | PROP_WATER | PROP_HIGH))


# Every landmark is a warp: step on one and you are inside it. A route that
# happens to cross Landfall's gate on the way north does not pass through it,
# it ends there -- which is how the first version of this test spent its whole
# walk inside the wrong town and still reported a lit screen.
LANDMARKS = {c for c in world.SITES.values()}


def route(start, goal):
    """Shortest on-foot route that touches no landmark but the destination."""
    import collections
    prev = {start: None}
    q = collections.deque([start])
    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break
        for (dx, dy), d in DIRS.items():
            n = (x + dx, y + dy)
            if not (0 <= n[0] < OW.w and 0 <= n[1] < OW.h) or n in prev:
                continue
            if n != goal and (not walkable(*n) or n in LANDMARKS):
                continue
            prev[n] = ((x, y), d)
            q.append(n)
    if goal not in prev:
        return None
    out, cur = [], goal
    while prev[cur]:
        cur, d = prev[cur]
        out.append(d)
    out.reverse()
    return out


class Trip:
    """A walker that copes with what the world throws at it."""

    def __init__(self, r):
        self.r = r
        self.battles = 0
        self.scenes = 0

    def settle(self):
        if arena_fraction(self.r.frame) > 0.6:
            self.battles += 1
            for _ in range(400):
                self.r.tap(A, 2, 5)
                if arena_fraction(self.r.frame) <= 0.6:
                    break
            self.r.idle(20)
        self.r.idle(8)
        n = 0
        while window_open(self.r.frame) and n < 60:
            self.r.tap(A, 3, 14)
            n += 1
        if n:
            self.scenes += 1

    def step(self, d):
        self.r.step(press(d), 8)
        self.r.step([0] * 8, 2)
        self.settle()

    def walk(self, path, stop=None):
        for i, d in enumerate(path):
            self.step(d)
            if stop and stop(self.r):
                return i + 1
        return len(path)


def field_lit(r):
    a = np.asarray(r.frame)
    return int((a.sum(axis=2) > 40).sum())


def differs(a, b, thresh=0.35):
    """How much of the screen changed -- a warp repaints nearly all of it."""
    x, y = np.asarray(a, dtype=int), np.asarray(b, dtype=int)
    return float((np.abs(x - y).sum(axis=2) > 30).mean()) > thresh


# --- the run ------------------------------------------------------------------
# Landfall, not somewhere far: a scripted walk of eighty-odd cells does not
# reliably arrive. One blocked step -- a mountain the route thought was open, a
# battle that ends on a different frame parity -- desynchronises the rest of the
# path, and with no way to read the party's coordinates from a frame the walker
# cannot notice or correct. That is a limitation of this harness, not of the
# game, and it is why this test walks a distance it can verify instead of
# claiming a playthrough it cannot.
to_town = route(world.START, world.SITES["LANDFALL"])
print(f"start -> Landfall: {len(to_town)} steps")

r = Run()
start_game(r)
t = Trip(r)
r.shot("journey_0_field")
check(field_lit(r) > 20000, f"the muster lands on the map ({field_lit(r)} lit)")

print("\ninto Landfall")
t.walk(to_town[:-1])
r.idle(20)
outside = r.frame.copy()
t.step(to_town[-1])
r.idle(40)
r.shot("journey_1_town")
check(differs(outside, r.frame),
      "stepping onto the town repainted the screen, so the warp fired")
check(field_lit(r) > 15000, f"and the town is drawn ({field_lit(r)} lit)")

print("\nthe menu opens on the real ROM")
r.tap(START, 3, 60)
r.shot("journey_2_menu")
menu = r.frame
check(glyphs.says(menu, "ITEM") and glyphs.says(menu, "EQUIP"),
      "START opens the field menu")
check(glyphs.says(menu, "CREDITS"), "and it shows the purse")
r.tap(B, 3, 50)
check(field_lit(r) > 15000, "B puts the party back on the map")

print("\nback out to the overworld")
town = r.frame.copy()
t.step(DOWN)
t.step(UP)
r.idle(30)
r.shot("journey_3_backout")
check(differs(town, r.frame),
      "stepping off the gate and back on leaves the town")

print("\nand the world still scrolls")
before = r.frame.copy()
for d in (RIGHT, RIGHT, RIGHT, DOWN, DOWN, LEFT, LEFT, UP):
    t.step(d)
r.shot("journey_4_walk")
check(field_lit(r) > 20000, "the party is still on a drawn map after a loop")
check(not differs(before, r.frame, thresh=0.98),
      "and the loop did not leave the screen blank")

print(f"\n{r.n} frames, {t.battles} battles, {t.scenes} scenes")
if FAIL:
    print(f"\n{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_journey: PASS")
sys.exit(0)
