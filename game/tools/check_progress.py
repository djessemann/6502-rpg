#!/usr/bin/env python3
"""Prove the game is finishable: solve the gate graph from an empty save.

Gates and boons (tools/gating.py) can deadlock in a way no single check sees:
a door that wants a flag you can only earn behind that door, or a vehicle whose
grant sits on the far side of the terrain it opens. This walks the whole thing
forward from nothing -- no flags, no vehicles, standing outside Landfall -- and
reports the order a player is actually forced into, or the exact step where the
game stops being finishable.

Run from anywhere:  python3 tools/check_progress.py
"""
import collections
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import areas                                                      # noqa: E402
import art_tiles                                                  # noqa: E402
import gating                                                     # noqa: E402
import world                                                      # noqa: E402
from maps import OB_TRIG, OB_WARP                                 # noqa: E402
from tileset import PROP_SOLID, PROP_WATER, PROP_HIGH             # noqa: E402
from check_areas import wings                                     # noqa: E402

# The overworld tile each area is entered from.
SITE_OF = {"LANDFALL": "LANDFALL", "EMBERREST": "EMBERREST",
           "KELPHOLD": "KELPHOLD", "HIGHMESA": "HIGHMESA",
           "DUSTGATE": "DUSTGATE", "LASTPORT": "LASTPORT",
           "CINDER1": "CINDER", "TIDE1": "TIDE", "STORM1": "STORM",
           "HOLLOW1": "HOLLOW", "RELAY1": "RELAY", "OSSUARY1": "OSSUARY",
           "CAUSEWAY": "REEF", "EREBUS1": "RIFT"}

FINAL_FLAG = 16         # EREBUS4's trigger: THE ARCHON, and the ending


def ow_reachable(vehicles):
    ts = art_tiles.overworld()
    prop = ts.compile()["prop"]
    m = world.overworld_map(ts)
    seen = {world.START}
    q = collections.deque([world.START])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < m.w and 0 <= ny < m.h) or (nx, ny) in seen:
                continue
            p = prop[m.grid[ny][nx]]
            if p & PROP_HIGH:
                if not vehicles & 2:
                    continue
            elif p & PROP_SOLID:
                continue
            if p & PROP_WATER and not vehicles & 1:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def floor_links(maps):
    """map name -> the map names its stairs lead to."""
    out = {}
    for m in maps:
        out[m.name] = [world.MAP_NAMES[o[3]] for o in m.objects
                       if o[0] == OB_WARP and o[3] != 0]
    return out


def main():
    maps = areas.build_all(art_tiles.town(), art_tiles.dungeon())
    by_name = {m.name: m for m in maps}
    links = floor_links(maps)
    trigs = {m.name: [o[3] for o in m.objects if o[0] == OB_TRIG] for m in maps}
    gating.check(world.MAP_NAMES, trigs)

    flags, vehicles, visited = set(), 0, set()
    order = []
    errors = []

    for step in range(40):
        ow = ow_reachable(vehicles)
        frontier = []
        for name, site in SITE_OF.items():
            if name in visited:
                continue
            x, y = world.SITES[site]
            if (x, y) not in ow and (x, y + 1) not in ow:
                continue
            need = gating.GATES.get(name, (0xFF, None))[0]
            if need != 0xFF and need not in flags:
                continue
            frontier.append(name)
        if not frontier:
            break
        # entering a floor gives you its own triggers and everything its stairs
        # reach, since nothing gates a staircase
        gained = set()
        for name in sorted(frontier):
            stack, seen = [name], set()
            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)
                gained |= set(trigs.get(n, []))
                stack += links.get(n, [])
            visited |= seen
        new = gained - flags
        if not new and not frontier:
            break
        flags |= gained
        for f in sorted(new):
            vehicles |= gating.BOONS.get(f, 0)
        order.append((sorted(frontier), sorted(new), vehicles))
        if FINAL_FLAG in flags:
            break

    print(f"{'step':<5} {'opens':<44} {'flags gained':<24} vehicles")
    for i, (front, new, veh) in enumerate(order):
        v = {0: "-", 1: "skiff", 2: "lift", 3: "skiff+lift"}[veh]
        print(f"{i:<5} {','.join(front):<44} {str(new):<24} {v}")

    if FINAL_FLAG not in flags:
        missing = [n for n in SITE_OF if n not in visited]
        errors.append(f"the game cannot be finished: flag {FINAL_FLAG} "
                      f"(the Archon) is unreachable. Never opened: {missing}")
    if len(order) < 2:
        errors.append("every area opens at once - the gates in tools/gating.py "
                      "impose no order at all")

    # a gate that wants a flag only earned behind itself is a deadlock even if
    # the game happens to be finishable another way
    for name, (need, _) in gating.GATES.items():
        if need == 0xFF:
            continue
        owner = [n for n, fs in trigs.items() if need in fs]
        if owner and owner[0] == name:
            errors.append(f"{name} is gated on flag {need}, which is set by "
                          f"{name} itself - the door locks its own key inside")

    if errors:
        print(f"\n{len(errors)} PROBLEM(S):")
        for e in errors:
            print("  " + e)
        return 1
    print(f"\nfinishable in {len(order)} gated steps; all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
