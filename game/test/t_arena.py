"""The battle screen survives being entered from a scrolled map.

The arena is drawn as one unsplit 32-tile row per line, which only works
because BattleEnter zeroes the camera first: every row write goes through
RowSegs, and RowSegs splits a row across the two nametables at the camera's
column. StField used to recompute the field camera *after* UpdateHero had
already started the battle, which put every later row write at the field's
column offset -- the window came out torn in half with its second copy starting
mid-screen, the HUD lost the party names off the left edge, and every button
press redrew more of the same. On a real emulator that reads as flicker.

The camera is only nonzero once the party has walked, so this walks first and
lets a random encounter start the fight, which is exactly how a player meets it.

Control: -D TEST_CAMERA_CLOBBER removes the guard. Every check below must fail
on that build, or this test is measuring nothing.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

from harness import Run, press, A, RIGHT, LEFT                    # noqa: E402
from play import start_game, arena_fraction                       # noqa: E402
import glyphs                                                     # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build(dst, defines=()):
    import re
    mk = (GAME / "Makefile").read_text()
    body = re.search(r"^SRCS\s*:=\s*((?:.*\\\n)*.*)$", mk, re.M).group(1)
    body = body.replace("\\\n", " ")
    srcs = [GAME / t.replace("$(SRCDIR)", "src").replace("$(GENDIR)", "src/gen")
            .replace("$(SOUND)", "src/sound.s") for t in body.split()]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="threnos-arena-"))
    try:
        objs = []
        for src in srcs:
            o = tmp / (str(src.relative_to(GAME)).replace("/", "_")[:-2] + ".o")
            subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + list(defines)
                           + ["-o", str(o), str(src)], check=True)
            objs.append(str(o))
        subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(dst)]
                       + objs, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dst


CLASSES = ("SOLDIER", "RANGER", "MEDIC", "PSION", "ENGINEER", "BRAWLER")


def to_battle(rom, limit=400):
    """Walk until an encounter starts, then step past the intro banner."""
    r = Run(rom=rom)
    start_game(r)
    for _ in range(limit):
        r.step(press(RIGHT), 8)
        r.step([0] * 8, 2)
        r.step(press(LEFT), 8)
        r.step([0] * 8, 2)
        if arena_fraction(r.frame) > 0.6:
            r.tap(A, 3, 50)
            return r
    return None


def inspect(r, tag):
    r.shot(tag)
    # rows 25-28 are the party HUD; 29 is overscan and never legible
    rows = {i: glyphs.line(r.frame, i) for i in range(18, 29)}
    for i, t in rows.items():
        if t.strip():
            print(f"    {i:2d} |{t.rstrip()}|")
    turn = rows[20].strip()
    hud = [rows[i] for i in (25, 26, 27, 28)]
    named = sum(1 for h in hud if any(c in h for c in CLASSES))
    return turn, named


ok_intact = []
print("the real ROM, entered from a scrolled map")
r = to_battle(GAME / "threnos.nes")
if r is None:
    print("no encounter in 400 steps"); sys.exit(1)
turn, named = inspect(r, "arena_1_real")
ok_intact.append(check(turn.startswith("TURN:"),
                       f"the turn line reads from the left ({turn!r})"))
ok_intact.append(check(named == 4,
                       f"all four HUD rows carry a party name ({named}/4)"))
ok_intact.append(check(glyphs.says(r.frame, "FIGHT")
                       and glyphs.says(r.frame, "GUARD"),
                       "the command menu is on screen"))

print("\nthe control (TEST_CAMERA_CLOBBER puts the bug back)")
ctl = build(GAME / "test" / "threnos_arena_bug.nes",
            ["-D", "TEST_CAMERA_CLOBBER=1"])
rc = to_battle(ctl)
if rc is None:
    print("  (no encounter on the control build; cannot compare)")
    check(False, "the control reached a battle")
else:
    c_turn, c_named = inspect(rc, "arena_2_control")
    check(not (c_turn.startswith("TURN:") and c_named == 4),
          f"the control's arena IS torn (turn={c_turn!r}, named={c_named}/4) "
          f"- so the checks above mean something")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_arena: PASS")
sys.exit(0)
