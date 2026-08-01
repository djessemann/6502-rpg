"""The arena reacts to what happens in it: hits flash, the dead go away.

Reported symptom: "when you defeat a single enemy it doesn't disappear from the
screen, they just all stay on until the battle is over."  Two separate faults
sat behind it.

  * EraseEnemy worked its own screen position out instead of sharing
    EnemySlotPos with the painter.  When the layout table grew a row per group
    size only the painter was updated, so a corpse was blanked at coordinates
    nothing had ever been drawn at.
  * Nothing at all marked a *surviving* enemy, so a hit that did not kill
    changed no pixel anywhere -- the fight was a menu with a story attached.

Both are now driven off btl_dirty: a kill or a hit sets the slot's bit and
ArenaTick repaints that slot from the live state on a later frame.  A kill
blanks its tiles; a hit only rewrites the attribute bytes over that monster,
turning it white for a few frames without moving a single tile.  So this
watches two different things: the arena's tile count must end at zero (every
corpse was erased) and some attribute byte must go to the flash palette and
come back (a hit that did not kill lit its target up).

It has to use pyntendo's pure-Python core: the fast core renders frames but
exposes no VRAM, and "is that enemy still drawn" is a nametable question.  That
makes it slow, so it drives exactly one fight.

Control: -D TEST_STATIC_ARENA makes MarkSlot a no-op, which is precisely the
reported bug.  The two checks below must both fail on that build.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))

import apu_trace as T                                          # noqa: E402

A, LEFT, RIGHT = 0, 6, 7
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
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="threnos-hits-"))
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


GS_BATTLE = 6                   # field.s
GAMESTATE = 0x20                # zp.inc


def in_battle(nes):
    """The 2KB of work RAM is directly readable on the pure-Python core.

    Reading `gamestate` is the only reliable way to ask this: an earlier
    version of the test asked "are there any non-blank tiles in the arena
    rows", which is trivially true of the field map too, so it decided the
    party was fighting the moment it took its first step.
    """
    return nes.memory.ram[GAMESTATE] == GS_BATTLE


FLASH_ATTR = 0xAA               # sub-palette 2 in all four quadrants


def flash_cells(nes):
    """Attribute bytes currently set to the hit-flash palette."""
    v = nes.ppu.vram
    return sum(1 for i in range(64) if v.read(0x23C0 + i) == FLASH_ATTR)


def arena_tiles(nes):
    """Non-blank background tiles in the arena rows.

    Rows 2..17 are the arena proper: row 0-1 is overscan and the window, HUD
    and message rows all start at 19.  Only the enemies are ever drawn up here,
    so this count is a direct read of how much monster is on screen.
    """
    v = nes.ppu.vram
    return sum(1 for r in range(2, 18) for c in range(32)
               if v.read(0x2000 + r * 32 + c) != 0)


def to_battle(rom, walk_steps=60):
    """Boot, take the default squad, walk until an encounter, clear the banner."""
    nes, t = T.build(rom)
    seq, f = [], 40
    seq.append((f, A)); f += 20            # title -> NEW GAME
    for _ in range(4):                     # accept each of the four classes
        seq.append((f, A)); f += 14
    seq.append((f, A)); f += 60            # confirm the squad
    T.run_frames(nes, t, f - t.frame, keys=seq)

    # One lap at a time, checking after each: the pure-Python core runs at a
    # few frames a second, so walking a fixed 1200 frames and only then looking
    # cost twenty minutes for an encounter that usually lands in the first two.
    for _ in range(walk_steps):
        walk, g = [], t.frame
        for _ in range(8):
            walk.append((g, RIGHT)); g += 1
        g += 2
        for _ in range(8):
            walk.append((g, LEFT)); g += 1
        g += 2
        T.run_frames(nes, t, g - t.frame, keys=walk)
        if in_battle(nes):
            break
    else:
        return None, None
    T.run_frames(nes, t, 40, keys=[(t.frame, A)])   # past "<monster> APPEARS!"
    return nes, t


def fight(nes, t, limit=120):
    """Mash A through the fight, sampling the arena every other frame."""
    counts, lit = [], []
    for _ in range(limit):
        T.run_frames(nes, t, 2, keys=[(t.frame, A)])
        if not in_battle(nes):
            break               # the field is back; those tiles are the map
        counts.append(arena_tiles(nes))
        lit.append(flash_cells(nes))
        if counts[-1] == 0:
            break
    return counts, lit


def runs(counts):
    out = []
    for v in counts:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def flashes(lit):
    """Times the flash palette appeared over a monster and then went away.

    Counted over runs, not samples: FLASH_FRAMES is several frames long and
    this samples every other frame, so one flash is a run of nonzero cells
    between two runs of zero.
    """
    rs = runs(lit)
    return sum(1 for i in range(1, len(rs) - 1)
               if rs[i][0] > 0 and rs[i - 1][0] == 0 and rs[i + 1][0] == 0)


def measure(rom, label):
    nes, t = to_battle(rom)
    if nes is None:
        print(f"  ({label}: no encounter)")
        return None
    counts, lit = fight(nes, t)
    print(f"  {label} tiles: " + " ".join(f"{v}x{n}" for v, n in runs(counts)))
    print(f"  {label} flash: " + " ".join(f"{v}x{n}" for v, n in runs(lit)))
    return counts, lit


print("the real ROM")
got = measure(GAME / "threnos.nes", "arena")
if got is None:
    print("no encounter; cannot measure"); sys.exit(1)
c, lit = got
check(c[0] > 0 and c[-1] == 0,
      f"the arena starts full and is empty by the end of the fight "
      f"({c[0]} -> {c[-1]} tiles)")
check(flashes(lit) >= 1,
      f"and a hit that does not kill lights its target up "
      f"({flashes(lit)} flashes, peak {max(lit)} cells)")

print("\nthe control (TEST_STATIC_ARENA stops anything marking a slot)")
ctl = build(GAME / "test" / "threnos_static_arena.nes",
            ["-D", "TEST_STATIC_ARENA=1"])
cgot = measure(ctl, "arena")
if cgot is None:
    check(False, "the control reached a battle")
else:
    cc, clit = cgot
    check(cc[-1] != 0 and flashes(clit) == 0,
          f"the control's arena never changes ({cc[0]} -> {cc[-1]} tiles, "
          f"{flashes(clit)} flashes) - so the checks above mean something")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_hits: PASS")
sys.exit(0)
