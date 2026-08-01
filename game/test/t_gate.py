"""Progression gates: the doors that stay shut, and the ground that opens.

Two mechanisms, each tested in both directions, because a gate that never opens
and a gate that never closes look identical from one side.

  the door    the Tide Anchor refuses you until the Cinder Anchor is lit. The
              control is the same ROM with every story flag set.
  the ground  the ridge around the Rift basin -- and so Lastport and Erebus --
              is impassable until the grav-lift. The control is the same ROM
              built with the lift already granted.
"""
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np                                                # noqa: E402
from harness import Run, press, UP, LEFT                          # noqa: E402
import world                                                      # noqa: E402

OUT = HERE / "build"
TIDE = world.SITES["TIDE"]


def build(rom, defs):
    OUT.mkdir(exist_ok=True)
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        o = OUT / f"gate_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(o), str(src)], check=True)
        objs.append(str(o))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)


def at(x, y, *extra):
    return ["-D", "TEST_SKIP_TITLE=1", "-D", f"TEST_START_X={x}",
            "-D", f"TEST_START_Y={y}"] + list(extra)


def step(r, d, n=1):
    for _ in range(n):
        r.step(press(d), 8)
        r.step([0] * 8, 2)
    r.idle(6)


def window_open(frame):
    """A message window: both borders drawn, dark between them."""
    from play import window_open as w
    return w(frame)


def moved(before, after):
    return not np.array_equal(np.asarray(before), np.asarray(after))


def same_map(a, b):
    """Equal everywhere except the band the party sprite occupies.

    The party is drawn at a fixed screen position, and its walk animation is on
    a different phase after a warp than after a boot, so a whole-frame compare
    reports a difference that has nothing to do with which map is on screen.
    """
    a, b = np.asarray(a), np.asarray(b)
    return (np.array_equal(a[:96], b[:96])
            and np.array_equal(a[136:], b[136:]))


ok = True


def check(cond, good, bad):
    global ok
    if cond:
        print("ok   " + good)
    else:
        print("FAIL: " + bad)
        ok = False


# --- the Tide door -----------------------------------------------------------
# Stand one cell south of the Tide entrance and walk into it.
SHUT = OUT / "gate_shut.nes"
build(SHUT, at(TIDE[0], TIDE[1] + 1))
r = Run(rom=SHUT)
r.idle(30)
before = r.frame.copy()
step(r, UP)
r.idle(20)
r.shot("gate_1_refused")
check(window_open(r.frame),
      "the Tide Anchor is sealed until Cinder is lit",
      "walking into the Tide entrance with no Anchors lit did not refuse")

OPEN = OUT / "gate_open.nes"
build(OPEN, at(TIDE[0], TIDE[1] + 1, "-D", "TEST_GRANT_ALL=1"))
r2 = Run(rom=OPEN)
r2.idle(30)
ow = r2.frame.copy()
step(r2, UP)
r2.idle(30)
r2.shot("gate_2_entered")
# ...and it must be TIDE1 specifically, not "some other screen". A ROM booted
# straight into TIDE1 at the same arrival cell is the reference. Comparing
# against it is what caught CheckWarp reloading the destination through a
# clobbered X and warping the party to the wrong map entirely.
REF = OUT / "gate_ref.nes"
build(REF, ["-D", f"TEST_START_DUNGEON={world.MAP_ID['TIDE1']}"])
rref = Run(rom=REF)
rref.idle(30)
rref.shot("gate_2b_reference")
check(not window_open(r2.frame) and moved(ow, r2.frame),
      "with the Anchors lit the same step enters a dungeon",
      "the Tide door stayed shut even with every story flag set - the gate "
      "never opens, so the check above was measuring nothing")
check(same_map(rref.frame, r2.frame),
      "the Tide entrance lands in TIDE1, pixel for pixel",
      "the Tide entrance warped somewhere that is not TIDE1 - compare "
      "shots/gate_2_entered.png with shots/gate_2b_reference.png")

# --- the ridge around the Rift basin ----------------------------------------
# Lastport sits inside a ring of RIDGE. Walk west into it from just outside.
RX, RY = 74, 58                 # east of the basin, on open ground
WALL = OUT / "gate_wall.nes"
build(WALL, at(RX, RY))
r3 = Run(rom=WALL)
r3.idle(30)
r3.shot("gate_3_before_ridge")
b3 = r3.frame.copy()
step(r3, LEFT, 6)
r3.shot("gate_4_stopped")
stopped = r3.frame.copy()

LIFT = OUT / "gate_lift.nes"
build(LIFT, at(RX, RY, "-D", "TEST_VEHICLES=3"))
r4 = Run(rom=LIFT)
r4.idle(30)
step(r4, LEFT, 6)
r4.shot("gate_5_crossed")

check(moved(stopped, r4.frame),
      "the grav-lift crosses ridges that stop you on foot",
      "six steps west ended on the same frame with and without the grav-lift "
      "- either the ridge is not blocking on foot, or the lift does not open "
      "it")
check(moved(b3, stopped),
      "walking west on foot still moves before the ridge stops it",
      "the party did not move at all on foot, so the comparison above proves "
      "nothing about the ridge")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
