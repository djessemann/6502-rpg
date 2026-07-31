"""Story triggers: a trigger plays its scene, arms its boss, and never re-fires.

Boots standing one cell from Cinder Anchor 3's core trigger, so the check
exercises the trigger rather than a long walk.
"""
import sys, pathlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, DOWN, UP
import areas, art_tiles, world
from maps import OB_TRIG

MAP = "CINDER3"
ROM = GAME / "test" / "threnos_story.nes"
m = areas.build_all(art_tiles.town(), art_tiles.dungeon())[
    world.MAP_NAMES[1:].index(MAP)]
trg = next(o for o in m.objects if o[0] == OB_TRIG)
tx, ty, flag = trg[1], trg[2], trg[3]
print(f"{MAP} core trigger at ({tx},{ty}), story flag {flag}")


def build_at(rom, mapname, sx, sy):
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID[mapname]}",
            "-D", f"TEST_START_X={sx}", "-D", f"TEST_START_Y={sy}",
            "-D", "TEST_NO_ENCOUNTERS=1"]
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"story_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)


def arena_black(f):
    """The battle arena is a mostly-black upper screen."""
    a = np.asarray(f)[8:120, :, :]
    return float((a.sum(axis=2) == 0).mean())


build_at(ROM, MAP, tx, ty - 1)
ok = True

r = Run(rom=ROM)
r.idle(20)
r.shot("story_0_before")
r.step(press(DOWN), 8)          # step onto the trigger
r.step([0] * 8, 2)
r.idle(40)
r.shot("story_1_scene")
scene = np.asarray(r.frame)[168:184, 8:200, :].copy()
if not scene.any():
    print("FAIL: stepping on the trigger played no scene"); ok = False
else:
    print("ok   the trigger plays its scene")

for _ in range(6):              # page through and close the window
    r.tap(A, 3, 30)
r.idle(60)
r.shot("story_2_boss")
if arena_black(r.frame) < 0.6:
    print("FAIL: closing the scene did not start the boss fight"); ok = False
else:
    print("ok   closing the scene starts the boss fight")

# --- a scene with no boss sets its flag at once and must not replay ----------
MAP2 = "CINDER1"
m2 = areas.build_all(art_tiles.town(), art_tiles.dungeon())[
    world.MAP_NAMES[1:].index(MAP2)]
t2 = next(o for o in m2.objects if o[0] == OB_TRIG)
ROM2 = GAME / "test" / "threnos_story2.nes"
build_at(ROM2, MAP2, t2[1], t2[2] + 1)
r2 = Run(rom=ROM2)
r2.idle(20)
r2.step(press(UP), 8)
r2.step([0] * 8, 2)
r2.idle(40)
first = np.asarray(r2.frame)[168:184, 8:200, :].copy()
r2.shot("story_3_first")
for _ in range(6):
    r2.tap(A, 3, 30)
r2.idle(40)
r2.step(press(DOWN), 8)         # step off and back on
r2.step([0] * 8, 2)
r2.step(press(UP), 8)
r2.step([0] * 8, 2)
r2.idle(40)
again = np.asarray(r2.frame)[168:184, 8:200, :].copy()
r2.shot("story_4_again")
if not first.any():
    print("FAIL: the no-boss trigger played nothing"); ok = False
elif bool((first == again).all()):
    print("FAIL: the trigger replayed - its story flag is not sticking")
    ok = False
else:
    print("ok   a played scene does not replay")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
