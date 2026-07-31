#!/usr/bin/env python3
"""Verify the overworld: every site reachable, and reachable in the right order.

This exists because the overworld silently sealed two landmarks behind terrain.
The Rift basin was ringed with CRAG, which is plain PROP_SOLID -- no vehicle in
the game crosses it -- so the endgame dungeon and the town beside it could not
be walked to at all. `check_areas.py` never looked, because it only checks the
27 area maps.

The rule this enforces: a site is either reachable on foot, or reachable with a
vehicle the player is *given* before they need it. Nothing may be unreachable
with everything.

Run from anywhere:  python3 tools/check_world.py
"""
import collections
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import art_tiles                                                  # noqa: E402
import world                                                      # noqa: E402
from tileset import PROP_SOLID, PROP_WATER, PROP_HIGH             # noqa: E402

SKIFF, LIFT = 1, 2

# What each site needs. This is the intended shape of the game: the four
# Anchors on foot in flag order, then the grav-lift opens the Rift basin --
# Lastport's endgame shops and Erebus itself.
EXPECTED = {
    "LANDFALL": 0, "EMBERREST": 0, "KELPHOLD": 0, "HIGHMESA": 0,
    "DUSTGATE": 0, "CINDER": 0, "TIDE": 0, "STORM": 0, "HOLLOW": 0,
    "RELAY": 0, "OSSUARY": 0, "REEF": 0,
    "LASTPORT": LIFT, "RIFT": LIFT,
}


def flood(m, prop, start, vehicles):
    seen = {start}
    q = collections.deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < m.w and 0 <= ny < m.h) or (nx, ny) in seen:
                continue
            p = prop[m.grid[ny][nx]]
            if p & PROP_HIGH:
                if not vehicles & LIFT:
                    continue
            elif p & PROP_SOLID:
                continue
            if p & PROP_WATER and not vehicles & SKIFF:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def main():
    ts = art_tiles.overworld()
    prop = ts.compile()["prop"]
    m = world.overworld_map(ts)
    errors = []

    levels = {v: flood(m, prop, world.START, v)
              for v in (0, SKIFF, LIFT, SKIFF | LIFT)}

    print(f"{'site':<10} {'cell':>10}  needs")
    for site, (x, y) in world.SITES.items():
        # a landmark is entered by stepping on its own tile, which is always
        # approached from the cell below it
        need = None
        for v in (0, SKIFF, LIFT, SKIFF | LIFT):
            if (x, y) in levels[v] or (x, y + 1) in levels[v]:
                need = v
                break
        got = {None: "UNREACHABLE", 0: "on foot", SKIFF: "skiff",
               LIFT: "grav-lift", SKIFF | LIFT: "both"}[need]
        print(f"{site:<10} {str((x, y)):>10}  {got}")
        want = EXPECTED[site]
        if need is None:
            errors.append(f"{site} at {(x, y)} cannot be reached with anything")
        elif need & ~want:
            errors.append(f"{site} needs {got}, but the design says "
                          f"{'on foot' if not want else 'grav-lift'}")

    # LoadObjects fills entity slots 1..MAX_ENT-1, so anything past that is
    # silently dropped. The overworld had 14 warps against a cap of 11 and lost
    # the Ossuary, the Causeway and Erebus -- the endgame dungeon had no
    # entrance at all.
    MAX_OBJECTS = 15            # MAX_ENT in src/ram.inc, minus the party leader
    if len(m.objects) > MAX_OBJECTS:
        errors.append(f"the overworld has {len(m.objects)} objects but only "
                      f"{MAX_OBJECTS} entity slots: "
                      f"{[world.MAP_NAMES[o[3]] for o in m.objects[MAX_OBJECTS:]]} "
                      f"would be dropped at load")

    walk = len(levels[0])
    print(f"\nwalkable on foot: {walk} cells of {m.w * m.h}")
    if walk < 4000:
        errors.append(f"only {walk} cells are walkable on foot - the early "
                      f"game has nowhere to go")

    if errors:
        print(f"\n{len(errors)} PROBLEM(S):")
        for e in errors:
            print("  " + e)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
