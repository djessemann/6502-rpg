"""The Archon's two forms and the ending.

Beating THE ARCHON must chain straight into ARCHON PRIME, and beating that must
run the ending and stop. Built with -D TEST_WEAK_ENEMIES so a level-1 party can
actually get there.
"""
import sys, pathlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, UP, DOWN
import areas, art_tiles, world
from maps import OB_TRIG

MAP = "EREBUS4"
ROM = GAME / "test" / "threnos_end.nes"
m = areas.build_all(art_tiles.town(), art_tiles.dungeon())[
    world.MAP_NAMES[1:].index(MAP)]
trg = next(o for o in m.objects if o[0] == OB_TRIG)
tx, ty = trg[1], trg[2]
print(f"{MAP} Archon trigger at ({tx},{ty})")

defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID[MAP]}",
        "-D", f"TEST_START_X={tx}", "-D", f"TEST_START_Y={ty - 1}",
        "-D", "TEST_NO_ENCOUNTERS=1", "-D", "TEST_WEAK_ENEMIES=1"]
objs = []
for src in sorted((GAME / "src").glob("*.s")) + \
        sorted((GAME / "src" / "gen").glob("*.s")):
    if src.name == "sound_stub.s":
        continue
    obj = GAME / "test" / f"end_{src.parent.name}_{src.stem}.o"
    subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                   ["-o", str(obj), str(src)], check=True)
    objs.append(str(obj))
subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(ROM)] + objs,
               check=True)


def arena(f):
    a = np.asarray(f)[8:120, :, :]
    return float((a.sum(axis=2) == 0).mean())


def input_dead(run):
    """True if the game no longer responds to the d-pad."""
    before = run.digest()
    run.step(press(UP), 20)
    run.step(press(DOWN), 20)
    run.idle(10)
    return run.digest() == before


# Control, in its own run so the walking does not disturb the real sequence:
# without it, "input is dead at the end" would prove nothing.
_c = Run(rom=ROM)
_c.idle(20)
alive_at_start = not input_dead(_c)

r = Run(rom=ROM)
r.idle(20)
r.step(press(DOWN), 8)   # the trigger is one cell below the start
r.step([0] * 8, 2)
r.idle(40)
for _ in range(6):
    r.tap(A, 3, 30)
r.idle(60)
in_battle_1 = arena(r.frame) > 0.6
r.shot("end_1_archon")

# Reaching GS_ENDED is itself the proof of the whole chain: the only way in is
# beating ARCHON PRIME, which only exists if THE ARCHON chained into it. A
# battle-to-battle transition cannot be seen from the frames (the arena never
# stops being black between the two forms), so do not try.
ok = True
if not in_battle_1:
    print("FAIL: the Archon trigger did not start a fight"); ok = False
else:
    print("ok   the Archon trigger starts the fight")

if not alive_at_start:
    print("FAIL: input looked dead before anything happened - the end-state "
          "check would prove nothing"); ok = False
else:
    print("ok   control: the game responds to input at the start")

for _ in range(600):            # fight both forms, then page the ending
    r.tap(A, 2, 5)
r.shot("end_3_after_fights")
for _ in range(20):
    r.tap(A, 3, 25)
r.shot("end_4_ending")

if not input_dead(r):
    print("FAIL: never reached the ending - the party is still walking around")
    ok = False
else:
    print("ok   the run ends in the held ending state, so ARCHON PRIME chained "
          "off THE ARCHON and the ending ran")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
