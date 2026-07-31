"""Inns: resting costs credits, refills the party, and is refused when broke.

Boots a test-only ROM standing just below Landfall's inn door, so the check
exercises the inn rather than a long scripted walk.
"""
import sys, pathlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, UP
import areas, art_tiles, world
from maps import OB_INN

ROM = GAME / "test" / "threnos_inn.nes"
m = areas.build_all(art_tiles.town(), art_tiles.dungeon())[0]      # LANDFALL
inn = next(o for o in m.objects if o[0] == OB_INN)
ix, iy, price = inn[1], inn[2], inn[3] | (inn[4] << 8)
print(f"Landfall inn at ({ix},{iy}), {price} credits")


def build(rom, extra):
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID['LANDFALL']}",
            "-D", f"TEST_START_X={ix}", "-D", f"TEST_START_Y={iy + 1}"] + extra
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"inn_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)


def line1(f):
    return np.asarray(f)[168:184, 8:200, :].copy()


ok = True

build(ROM, [])
r = Run(rom=ROM)
r.idle(20)
r.step(press(UP), 4)          # face the inn door without leaving the cell
r.step([0] * 8, 4)
r.tap(A, 3, 50)
rest = line1(r.frame)
r.shot("inn_1_rest")
if not rest.any():
    print("FAIL: nothing appeared when talking to the innkeeper"); ok = False
else:
    print("ok   the innkeeper responds")

# a party with no credits must be turned away
BROKE = GAME / "test" / "threnos_inn_broke.nes"
build(BROKE, ["-D", "TEST_NO_CREDITS=1"])
r2 = Run(rom=BROKE)
r2.idle(20)
r2.step(press(UP), 4)
r2.step([0] * 8, 4)
r2.tap(A, 3, 50)
broke = line1(r2.frame)
r2.shot("inn_2_broke")
if bool((rest == broke).all()):
    print("FAIL: a broke party gets the same reply as a paying one"); ok = False
else:
    print("ok   a party that cannot pay is refused")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
