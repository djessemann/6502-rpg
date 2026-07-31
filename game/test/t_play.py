"""Self-check for the scripted-play detectors in test/play.py.

If window_open() or in_battle() were wrong, every playthrough result built on
them would be meaningless, so prove both against frames we can construct.
"""
import sys, pathlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, DOWN
from play import window_open, arena_fraction, Player, route_between
import areas, art_tiles, world
from maps import OB_TRIG, OB_WARP

ROM = GAME / "test" / "threnos_play.nes"
MAP = "CINDER1"
ts_d = art_tiles.dungeon()
m = areas.build_all(art_tiles.town(), ts_d)[world.MAP_NAMES[1:].index(MAP)]
prop = ts_d.compile()["prop"]

defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID[MAP]}", "-D", "TEST_NO_ENCOUNTERS=1"]
objs = []
for src in sorted((GAME / "src").glob("*.s")) + sorted((GAME / "src" / "gen").glob("*.s")):
    if src.name == "sound_stub.s":
        continue
    o = GAME / "test" / f"play_{src.parent.name}_{src.stem}.o"
    subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs + ["-o", str(o), str(src)], check=True)
    objs.append(str(o))
subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(ROM)] + objs, check=True)

ok = True
r = Run(rom=ROM); r.idle(20)

# no window on a plain field frame
if window_open(r.frame):
    print("FAIL: window_open() is true on a plain field frame"); ok = False
else:
    print("ok   window_open() is false with no window")
if arena_fraction(r.frame) > 0.6:
    print("FAIL: in_battle() is true on the field"); ok = False
else:
    print("ok   in_battle() is false on the field")

# open one by talking to the sign next to the entrance
r.step(press(DOWN), 4); r.step([0] * 8, 4)
r.tap(A, 3, 50)
if not window_open(r.frame):
    print("FAIL: window_open() missed an open window"); ok = False
else:
    print("ok   window_open() sees an open window")
r.shot("play_window")

# the walker must cross the trigger at (12,17) and still arrive
warps = {(o[1], o[2]) for o in m.objects if o[0] == OB_WARP}
trigs = [(o[1], o[2]) for o in m.objects if o[0] == OB_TRIG]
goal = (17, 4)                              # a chest across the trigger
route = route_between(m, prop, (12, 18), goal, avoid=warps)
p = Player(ROM)
p.walk(route)
p.shot("play_walked")
if p.windows == 0:
    print("FAIL: the route did not cross the trigger, so this proves nothing")
    ok = False
else:
    print(f"ok   the walker crossed {p.windows} window(s) and kept going")
p.tap(A, 3, 50)
if not window_open(p.frame):
    print("FAIL: did not arrive at the chest"); ok = False
else:
    print("ok   arrived: the chest at the end of the route responds")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
