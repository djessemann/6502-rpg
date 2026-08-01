"""Battle items: who they are for, and the two effects that did nothing.

Before this, every item in a fight was applied to whoever used it -- a medkit
handed to the front-liner healed the front-liner -- and effects 3 (revive) and
4 (restore TP) fell straight through to "no effect" while still being consumed.
A stimpack, the one item that matters in a losing fight, was a way to throw 600
credits away.

The ROM starts slot 1 fallen and the pack stocked (-D TEST_DOWN_ONE), so both
halves of each effect are reachable: it works on the member who needs it, and
it refuses -- without spending the item -- on one who does not.
"""
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

from harness import Run, press, A, B, UP, DOWN, LEFT, RIGHT     # noqa: E402
from play import arena_fraction, start_game                     # noqa: E402
import glyphs                                                   # noqa: E402

ROM = GAME / "test" / "threnos_item.nes"
CMD_ROWS = (22, 23)
LIST_ROWS = (21, 22, 23, 24)

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build():
    defs = ["-D", "TEST_DOWN_ONE=1"]
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"item_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(ROM)] + objs,
                   check=True)


def cursor_row(r, rows):
    for i in rows:
        if ">" in glyphs.line(r.frame, i):
            return i
    return None


def move_to(r, rows, label, axis=DOWN, back=UP):
    for _ in range(len(rows) + 3):
        tgt = next((i for i in rows if label in glyphs.line(r.frame, i)), None)
        if tgt is None:
            return False
        cur = cursor_row(r, rows)
        if cur == tgt:
            return True
        r.tap(axis if cur is None or cur < tgt else back, 3, 20)
    return False


def to_battle(r, limit=400):
    for _ in range(limit):
        r.step(press(RIGHT), 8)
        r.step([0] * 8, 2)
        r.step(press(LEFT), 8)
        r.step([0] * 8, 2)
        if arena_fraction(r.frame) > 0.6:
            r.tap(A, 3, 40)             # past "<monster> APPEARS!"
            return True
    return False


MSG_ROWS = (21, 22)


def watch(r, until=None, limit=60):
    """Let the round resolve, collecting every message line that goes past.

    Commands are queued for all four members and only resolve once everyone has
    chosen, so the screen right after a pick still shows the command menu. The
    message this test is looking for appears, and is replaced, during the
    resolve -- so it has to be caught frame by frame rather than read once.

    It deliberately does not stop when a command menu comes back: the menu is
    up again the instant the pick is taken, one member later, so stopping there
    caught nothing at all. Rows 21-22 are where results are written -- row 19
    keeps the "<monster> APPEARS!" banner for the whole fight, which is what an
    earlier version of this test was reading and reporting as "no message".
    """
    seen = []
    for _ in range(limit):
        for i in MSG_ROWS:
            t = glyphs.line(r.frame, i).strip()
            if t and t not in seen:
                seen.append(t)
        if until and any(until in t for t in seen):
            break                       # stop before the fight runs on without us
        if any("VICTORIOUS" in t or "FALLEN." in t for t in seen):
            break
        r.tap(A, 2, 7)
    return " | ".join(seen)


def wait_for_cmd(r, limit=60):
    """Advance until a party member's command menu is up.

    watch() stops mid-round on purpose, so the screen afterwards can be a
    resolving message, an enemy picker, or someone else's turn. Opening the
    pack from whatever happens to be showing is how this test ended up
    asserting against a list of GLASS TICKs.
    """
    for _ in range(limit):
        if "FIGHT" in glyphs.line(r.frame, 22) and \
                ">" in glyphs.line(r.frame, 22) + glyphs.line(r.frame, 23):
            return True
        r.tap(A, 2, 8)
    return False


def open_items(r):
    """From the command menu: put the cursor on ITEM and open the pack."""
    for _ in range(4):
        if ">" in glyphs.line(r.frame, 22) and \
                glyphs.line(r.frame, 22).index(">") > 12:
            break
        r.tap(RIGHT, 3, 20)
    r.tap(A, 3, 40)


build()
r = Run(rom=ROM)
start_game(r)
if not to_battle(r):
    print("no encounter in 400 steps"); sys.exit(1)

print("\nan item asks who it is for")
open_items(r)
check(glyphs.line(r.frame, 21).strip().endswith("MEDKIT"),
      f"the pack opens on MEDKIT ({glyphs.line(r.frame, 21).strip()!r})")
r.tap(A, 3, 40)
rows = [glyphs.line(r.frame, i).strip() for i in LIST_ROWS]
check(sum(1 for t in rows if t) >= 4,
      f"choosing it lists the party to pick from ({rows})")
check(any("FALLEN" in t for t in rows),
      f"and the fallen member is shown as fallen ({rows})")

print("\na stimpack brings back the member who is down")
r.tap(B, 3, 40)                          # back to the pack
check(move_to(r, LIST_ROWS, "STIMPACK"), "STIMPACK is in the pack")
r.tap(A, 3, 40)
check(move_to(r, LIST_ROWS, "FALLEN"), "the fallen member can be picked")
r.tap(A, 3, 60)
seen = watch(r, until="IS BACK UP")
r.shot("item_1_revived")
check("IS BACK UP" in seen, f"and it says so ({seen!r})")

# The proof they are actually up: the picker no longer offers a fallen member.
# The party HUD shows a corpse as "0/40" rather than any word, so searching the
# HUD for "FALLEN" -- which an earlier version of this test did -- matched
# nothing and passed whatever the game did.
check(wait_for_cmd(r), "the fight comes back to a command menu")
open_items(r)
r.tap(A, 3, 40)
rows = [glyphs.line(r.frame, i).strip() for i in LIST_ROWS]
check(any("SOLDIER" in t for t in rows) and not any("FALLEN" in t for t in rows),
      f"and nobody is listed as fallen any more ({rows})")
r.tap(B, 3, 40)

print("\n...and refuses on someone already standing")
check(move_to(r, LIST_ROWS, "STIMPACK"), "STIMPACK is still in the pack")
r.tap(A, 3, 40)
if move_to(r, LIST_ROWS, "SOLDIER"):
    r.tap(A, 3, 60)
    seen = watch(r, until="NO EFFECT")
    r.shot("item_2_refused")
    check("NO EFFECT" in seen,
          f"a stimpack on someone standing says NO EFFECT ({seen!r})")
else:
    check(False, "could not pick a standing member")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_item: PASS")
sys.exit(0)
