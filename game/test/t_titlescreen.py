"""The title screen and squad muster, in isolation.

Links kernel + text + title against test/stub_title.s instead of the field
engine, so this runs whether or not the field is wired to boot into the title.
The stub's two exits halt on flat colours -- green for MAKE PLANETFALL, blue
for CONTINUE -- which is how "the player got out of the menu" becomes a
question about pixels rather than about a hang.

Negative control: the same three measurements are taken on the boot frame of a
ROM whose title module never runs (the stub is built with -D TEST_NO_TITLE=1,
which paints nothing). They must not pass there.
"""
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
import numpy as np                                                # noqa: E402
from harness import Run, A, DOWN                                  # noqa: E402

OUT = HERE / "build"
SRCS = ["src/kernel.s", "src/text.s", "src/title.s", "src/sound_stub.s",
        "src/header.s", "test/stub_title.s", "src/gen/chr.s",
        "src/gen/tables.s", "src/gen/tilesets.s", "src/gen/maps_world.s",
        "src/gen/maps_area.s", "src/gen/text.s", "src/gen/data.s",
        "src/gen/title.s"]


def build(rom, extra=()):
    OUT.mkdir(exist_ok=True)
    objs = []
    for f in SRCS:
        o = OUT / (f.replace("/", "_")[:-2] + ".o")
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + list(extra) +
                       ["-o", str(o), str(GAME / f)], check=True, cwd=GAME)
        objs.append(str(o))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True, cwd=GAME)


def lit(frame, r0, r1):
    band = np.asarray(frame)[max(0, r0 * 8 - 8):r1 * 8 - 8, :, :]
    return int((band.sum(axis=2) > 40).sum())


# The halt colours the stub uses, looked up in the emulator's own palette
# rather than written out as RGB triples -- pyntendo does not use the canonical
# NES palette, and hand-guessed constants made this test fail on a pass.
from nes.pycore.ppu import NESPPU                                 # noqa: E402
NES_RGB = NESPPU.DEFAULT_NES_PALETTE
GREEN, RED, AMBER, BLUE = (NES_RGB[0x2A], NES_RGB[0x16],
                           NES_RGB[0x28], NES_RGB[0x12])


def flat(frame):
    """The single colour of a uniform frame, or None."""
    u = np.unique(np.asarray(frame).reshape(-1, 3), axis=0)
    return tuple(u[0]) if len(u) == 1 else None


def looks_like_title(f):
    return lit(f, 15, 20) > 1200 and 30 < lit(f, 2, 12) < 4000 \
        and lit(f, 22, 23) > 60


ok = True


def check(cond, good, bad):
    global ok
    if cond:
        print("ok   " + good)
    else:
        print("FAIL: " + bad)
        ok = False


ROM = OUT / "title_only.nes"
build(ROM)
r = Run(rom=ROM)
r.idle(40)
r.shot("ts_1_title")
check(looks_like_title(r.frame), "the logo screen paints",
      f"no logo screen (logo={lit(r.frame,15,20)} sky={lit(r.frame,2,12)} "
      f"menu={lit(r.frame,22,23)})")

NOTITLE = OUT / "title_none.nes"
build(NOTITLE, ["-D", "TEST_NO_TITLE=1"])
r0 = Run(rom=NOTITLE)
r0.idle(40)
r0.shot("ts_2_control")
check(not looks_like_title(r0.frame),
      "the control ROM (TEST_NO_TITLE) is not mistaken for the title",
      "the title check passes with the title module disabled - it measures "
      "nothing")

# NEW GAME -> the muster
r.tap(A, 3, 60)
r.shot("ts_3_muster")
m = r.frame
check(not looks_like_title(m), "NEW GAME leaves the title",
      "NEW GAME did not change the screen")
blank = [row for row in range(9, 15) if lit(m, row, row + 1) < 40]
check(not blank, "all six classes are listed",
      f"class rows with no text: {blank}")
check(lit(m, 16, 19) > 150, "the stat panel is drawn",
      f"no stat panel (lit={lit(m,16,19)})")

# moving the cursor must change the stats, or the panel is decoration
before = np.asarray(r.frame)[16 * 8 - 8:19 * 8 - 8].copy()
r.tap(DOWN, 3, 30)
r.shot("ts_4_moved")
after = np.asarray(r.frame)[16 * 8 - 8:19 * 8 - 8]
check(not np.array_equal(before, after),
      "moving the cursor re-reads that class's stats",
      "the stat panel did not change when the cursor moved")

# four picks, then MAKE PLANETFALL
for i in range(4):
    for _ in range(i):
        r.tap(DOWN, 3, 10)
    r.tap(A, 3, 30)
r.idle(30)
r.shot("ts_5_ready")
r.tap(A, 3, 60)
r.idle(20)
r.shot("ts_6_planetfall")
check(flat(r.frame) == GREEN,
      "MAKE PLANETFALL hands off to the field entry point",
      f"the ready screen did not reach StartNewGame (frame is {flat(r.frame)}, "
      f"expected the stub's flat green)")


# --- the save file: write it, wreck the live state, read it back -------------
# The stub does the whole round trip in GameInit and halts on a colour.
# Also build a control whose checksum is deliberately wrong, so "the file
# loaded" cannot be a routine that always says yes.
RT = OUT / "title_roundtrip.nes"
build(RT, ["-D", "TEST_SAVE_ROUNDTRIP=1"])
rr = Run(rom=RT)
rr.idle(30)
rr.shot("ts_7_saveload")
colour = flat(rr.frame)
check(colour == GREEN,
      "the save file round-trips: 506 bytes out, wrecked, and back byte for byte",
      f"the save round trip halted on {colour} - {GREEN} green is a match, "
      f"{RED} red is a mismatch, {AMBER} amber means the file it had just "
      f"written would not checksum")

BAD = OUT / "title_badsum.nes"
build(BAD, ["-D", "TEST_SAVE_ROUNDTRIP=1", "-D", "TEST_CORRUPT_SAVE=1"])
rb = Run(rom=BAD)
rb.idle(30)
rb.shot("ts_8_badsum")
check(flat(rb.frame) == AMBER,
      "a save whose checksum no longer matches is refused",
      f"a corrupted save was accepted (halted on {flat(rb.frame)}, expected "
      f"{AMBER} amber) - the checksum is not being checked")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
