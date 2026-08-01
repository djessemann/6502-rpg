"""The title screen and the squad muster.

Boots the real ROM (no test defines) and checks the three screens a new player
actually walks through: the logo, the muster, and the field they land on.

The negative control is a ROM built with -D TEST_SKIP_TITLE=1, which boots
straight into the overworld the way the game did before the title existed. The
logo check must FAIL on that ROM; a check that passes on both is measuring
nothing. This file asserts that too, so the control cannot silently rot.
"""
import sys
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np                                                # noqa: E402
from harness import Run, press, A, DOWN                           # noqa: E402

ROM = GAME / "test" / "threnos_title.nes"
SKIP = GAME / "test" / "threnos_notitle.nes"


def build(rom, extra=()):
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"ti_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + list(extra) +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)


def rows(frame, r0, r1):
    """Frame pixels for screen tile rows r0..r1 (pyntendo crops 8px off the top)."""
    return np.asarray(frame)[max(0, r0 * 8 - 8):r1 * 8 - 8, :, :]


def lit(frame, r0, r1):
    """How many pixels in those rows are not the backdrop."""
    band = rows(frame, r0, r1)
    return int((band.sum(axis=2) > 40).sum())


def looks_like_title(frame):
    """The logo band is busy, the sky above it has stars, the menu row has text.

    Deliberately three separate conditions: any one of them alone is something
    an ordinary map screen can produce.
    """
    logo = lit(frame, 15, 20)
    sky = lit(frame, 2, 12)
    menu = lit(frame, 22, 23)
    return logo > 1200 and 30 < sky < 4000 and menu > 60


ok = True


def check(cond, good, bad):
    global ok
    if cond:
        print("ok   " + good)
    else:
        print("FAIL: " + bad)
        ok = False


# --- 1. the title screen -----------------------------------------------------
build(ROM)
r = Run(rom=ROM)
r.idle(40)
r.shot("title_1_logo")
check(looks_like_title(r.frame), "the title screen comes up on boot",
      f"no title screen on boot (logo={lit(r.frame,15,20)} "
      f"sky={lit(r.frame,2,12)} menu={lit(r.frame,22,23)})")

# --- 2. the negative control -------------------------------------------------
# Without the title, the same three measurements must not add up.
build(SKIP, ["-D", "TEST_SKIP_TITLE=1"])
r2 = Run(rom=SKIP)
r2.idle(40)
r2.shot("title_2_control")
check(not looks_like_title(r2.frame),
      "the control ROM (TEST_SKIP_TITLE) is not mistaken for the title",
      "the title check passes on a ROM with no title screen - it measures "
      "nothing")

# --- 3. NEW GAME opens the muster -------------------------------------------
r.tap(A, 3, 40)
r.shot("title_3_muster")
muster = r.frame
check(not looks_like_title(muster), "NEW GAME leaves the title screen",
      "NEW GAME did not change the screen")
# six class rows, each with a name: rows 9..14 must all carry text
empty = [row for row in range(9, 15) if lit(muster, row, row + 1) < 40]
check(not empty, "the muster lists all six classes",
      f"muster rows with no text: {empty}")
check(lit(muster, 16, 19) > 100, "the muster previews the class's stats",
      "no stat panel under the class list")

# --- 4. picking four members lands in the field ------------------------------
for i in range(4):
    for _ in range(i):                  # a different class in each slot
        r.tap(DOWN, 3, 8)
    r.tap(A, 3, 20)
r.idle(30)
r.shot("title_4_ready")
ready = r.frame
r.tap(A, 3, 90)                          # MAKE PLANETFALL
r.idle(30)
r.shot("title_5_field")
field = r.frame
check(lit(field, 2, 28) > 20000,
      "MAKE PLANETFALL drops the party onto the map",
      f"the field did not appear after MAKE PLANETFALL "
      f"(lit={lit(field, 2, 28)})")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
