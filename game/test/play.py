"""Scripted play: walk a route the way a person would.

A naive "press the d-pad N times" walker desyncs the moment anything interrupts
it — a story trigger opens a window and eats every following step, a random
encounter drops you into a battle. Player.walk() notices both and deals with
them, so a route computed over the map data actually arrives.

Detection is by frame, since we cannot read emulator RAM:
  * a battle repaints the top of the screen to a mostly-black arena;
  * an open window draws a full-width border line across screen row 20.
Both detectors are self-checked by test/t_play.py against known frames.
"""
import collections
import numpy as np

from harness import Run, press, A, UP, DOWN, LEFT, RIGHT

# The window frame is drawn in the UI palette's colour 1, NES $00.
FRAME_RGB = (82, 82, 82)
WINDOW_ROW = 20                 # screen tile row of the window's top border


def _rows(frame, r0, r1):
    """Frame rows for screen tile rows r0..r1 (pyntendo crops 8px off the top)."""
    return np.asarray(frame)[max(0, r0 * 8 - 8):r1 * 8 - 8, :, :]


def arena_fraction(frame):
    """How much of the upper screen is pure black — high during a battle."""
    a = np.asarray(frame)[8:120, :, :]
    return float((a.sum(axis=2) == 0).mean())


def _border_line(frame, row):
    """Longest run-length of frame-colour pixels in any scanline of `row`."""
    band = _rows(frame, row, row + 1)
    if band.size == 0:
        return 0
    hit = np.all(band == np.array(FRAME_RGB), axis=2)
    return int(hit.sum(axis=1).max())


def window_open(frame):
    """True if the message window is on screen.

    Deliberately strict. An earlier version keyed on a single full-width line
    of the frame colour in row 20, which ordinary map terrain can produce - so
    the walker thought a window was open on open ground and mashed A at it.
    A window is: BOTH borders drawn, AND a mostly-black interior between them.
    """
    if _border_line(frame, WINDOW_ROW) < 200:
        return False
    if _border_line(frame, WINDOW_ROW + 5) < 200:
        return False
    inner = _rows(frame, WINDOW_ROW + 2, WINDOW_ROW + 4)
    if inner.size == 0:
        return False
    return bool((inner.sum(axis=2) == 0).mean() > 0.80)


def start_game(r, settle=40):
    """Drive the title screen into the field, the way a player would.

    The ROM boots to the title now, so any test that runs the real
    threnos.nes has to get through it first -- otherwise it scripts a walk at
    a menu and quietly measures nothing. Six A presses: NEW GAME, four class
    picks (whatever the cursor is already on), MAKE PLANETFALL.
    """
    r.idle(settle)
    r.tap(A, 3, 40)                 # NEW GAME
    for _ in range(4):              # four slots, taking the default class
        r.tap(A, 3, 24)
    r.tap(A, 3, 60)                 # MAKE PLANETFALL
    r.idle(settle)
    return r


class Player:
    def __init__(self, rom, settle=20, title=False):
        self.r = Run(rom=rom)
        if title:
            start_game(self.r)
        self.r.idle(settle)
        self.battles = 0
        self.windows = 0

    # --- state ------------------------------------------------------------
    @property
    def frame(self):
        return self.r.frame

    def in_battle(self):
        return arena_fraction(self.r.frame) > 0.6

    def window(self):
        return window_open(self.r.frame)

    # --- actions ----------------------------------------------------------
    def dismiss(self, limit=40, settle=10):
        """Page through any open window until it closes.

        A window opened by stepping onto a trigger takes a few frames to draw
        its border, so wait for it before deciding there is nothing to dismiss.
        """
        self.r.idle(settle)
        n = 0
        while self.window() and n < limit:
            self.r.tap(A, 3, 14)
            n += 1
        if n:
            self.windows += 1
        return n

    def fight(self, limit=400):
        """Mash through a battle by taking the default command on everyone."""
        if not self.in_battle():
            return 0
        self.battles += 1
        n = 0
        while self.in_battle() and n < limit:
            self.r.tap(A, 2, 5)
            n += 1
        self.r.idle(20)
        return n

    def step(self, d):
        """One 16px cell: 8 frames held, 2 released. Handles interruptions."""
        self.r.step(press(d), 8)
        self.r.step([0] * 8, 2)
        if self.in_battle():
            self.fight()
        self.dismiss()

    def walk(self, route):
        for d in route:
            self.step(d)
        return self

    def tap(self, *a, **k):
        return self.r.tap(*a, **k)

    def idle(self, *a, **k):
        return self.r.idle(*a, **k)

    def shot(self, name):
        return self.r.shot(name)

    def digest(self):
        return self.r.digest()


# --- routing ------------------------------------------------------------------
DIRS = {(0, -1): UP, (0, 1): DOWN, (-1, 0): LEFT, (1, 0): RIGHT}


def route_between(gmap, prop, start, goal, avoid=()):
    """Shortest walkable route, avoiding the given cells (warps, usually).

    Triggers are NOT avoided by default: on some maps every route out of the
    entrance crosses one. Player.walk() dismisses the window it opens.
    """
    block = set(avoid) - {goal}
    prev = {start: None}
    q = collections.deque([start])
    while q:
        x, y = q.popleft()
        for (dx, dy), d in DIRS.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < gmap.w and 0 <= ny < gmap.h and (nx, ny) not in prev \
                    and (nx, ny) not in block and not prop[gmap.grid[ny][nx]] & 1:
                prev[(nx, ny)] = ((x, y), d)
                q.append((nx, ny))
    if goal not in prev:
        return None
    route, cur = [], goal
    while prev[cur]:
        cur, d = prev[cur][0], prev[cur][1]
        route.append(d)
    route.reverse()
    return route
