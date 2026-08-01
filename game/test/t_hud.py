"""The party HUD keeps up with the party's HP.

The HUD used to be refreshed one row per battle message, picking the row of
whoever was hit last.  An enemy tech that hit the whole party therefore
updated one member's HP and left the other three reading whatever they had
before, often for the rest of the round -- three quarters of the damage the
player took never appeared on screen at the moment it happened.

HudTick now compares each row's live stats against hud_shadow and redraws
whatever drifted, one row per frame.  So the claim to test is not "a redraw
happened" but "what the HUD says and what RAM says do not stay apart", and
that is what this measures: it reads the four HUD rows straight out of the
nametable, reads b_hp straight out of the cartridge's battery RAM, and tracks
the longest stretch of frames any row spent disagreeing.

Some lag is by design -- one row per frame, then a frame for NMI to flush it
-- so this asserts a bound, not equality.

Control: -D TEST_HUD_FROZEN makes HudTick return immediately.  Its rows then
freeze at whatever they said when the arena was painted, and the stretch runs
to the length of the fight.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))

import apu_trace as T                                          # noqa: E402

A, LEFT, RIGHT = 0, 6, 7
GS_BATTLE = 6                   # field.s
GAMESTATE = 0x20                # zp.inc
B_HP = 0x6C10                   # ram.inc, 2 x 8 (low bytes then high bytes)
PARTY_N = 0x60D3

# How far apart the HUD and RAM may drift before it counts as stale. HudTick
# does one row a frame and NMI flushes a frame later, so four rows changing at
# once take about ten frames to all land; this is that with room to spare.
STALE_FRAMES = 30

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build(dst, defines=()):
    mk = (GAME / "Makefile").read_text()
    body = re.search(r"^SRCS\s*:=\s*((?:.*\\\n)*.*)$", mk, re.M).group(1)
    body = body.replace("\\\n", " ")
    srcs = [GAME / t.replace("$(SRCDIR)", "src").replace("$(GENDIR)", "src/gen")
            .replace("$(SOUND)", "src/sound.s") for t in body.split()]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="threnos-hud-"))
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


def charmap():
    """tile index -> character, from the table the assembler itself uses."""
    out = {}
    for ln in (GAME / "src" / "gen" / "charmap.inc").read_text().splitlines():
        g = re.match(r"\.charmap \$([0-9A-Fa-f]+), \$([0-9A-Fa-f]+)", ln.strip())
        if g:
            out.setdefault(int(g.group(2), 16), chr(int(g.group(1), 16)))
    return out


CHARS = charmap()
HUD_ROW = int(re.search(r"^HUD_ROW\s*=\s*(\d+)",
                        (GAME / "src" / "battle.s").read_text(),
                        re.M).group(1))


def row_text(nes, r):
    v = nes.ppu.vram
    return "".join(CHARS.get(v.read(0x2000 + r * 32 + c), "?")
                   for c in range(32))


def hud_hp(nes):
    """The HP each HUD row is showing, as HudLine wrote it: `<hp>/<max>`."""
    out = []
    for i in range(4):
        t = row_text(nes, HUD_ROW + i)
        g = re.search(r"(\d+)/(\d+)", t)
        out.append(int(g.group(1)) if g else None)
    return out


def ram_hp(nes):
    """The HP the engine believes, out of the battery RAM behind $6000."""
    c = nes.cart.ram
    return [c[B_HP - 0x6000 + i] | (c[B_HP - 0x6000 + 8 + i] << 8)
            for i in range(4)]


def in_battle(nes):
    return nes.memory.ram[GAMESTATE] == GS_BATTLE


def to_battle(rom, walk_steps=60):
    nes, t = T.build(rom)
    seq, f = [], 40
    seq.append((f, A)); f += 20
    for _ in range(4):
        seq.append((f, A)); f += 14
    seq.append((f, A)); f += 60
    T.run_frames(nes, t, f - t.frame, keys=seq)
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
    T.run_frames(nes, t, 40, keys=[(t.frame, A)])
    return nes, t


def measure(rom, label, limit=140):
    """Longest run of frames any HUD row disagreed with RAM, over one fight."""
    nes, t = to_battle(rom)
    if nes is None:
        print(f"  ({label}: no encounter)")
        return None
    worst, run, samples, seen_damage = 0, 0, 0, False
    step = 2
    while samples < limit:
        T.run_frames(nes, t, step, keys=[(t.frame, A)])
        if not in_battle(nes):
            break
        samples += 1
        shown, real = hud_hp(nes), ram_hp(nes)
        n = nes.cart.ram[PARTY_N - 0x6000]
        if any(r != real[0] for r in real[:n]) or real[0] == 0:
            seen_damage = True          # the party's HP has moved at all
        bad = any(shown[i] != real[i] for i in range(min(n, 4)))
        run = run + step if bad else 0
        worst = max(worst, run)
    print(f"  {label}: {samples} samples, worst stale run {worst} frames, "
          f"last row/RAM = {hud_hp(nes)} / {ram_hp(nes)}")
    return worst, seen_damage


print("the real ROM")
got = measure(GAME / "threnos.nes", "HUD vs RAM")
if got is None:
    print("no encounter; cannot measure"); sys.exit(1)
worst, damaged = got
check(damaged, "the party actually took damage in this fight "
                "(otherwise nothing was being tested)")
check(worst <= STALE_FRAMES,
      f"no HUD row disagreed with RAM for more than {STALE_FRAMES} frames "
      f"(worst {worst})")

print("\nthe control (TEST_HUD_FROZEN stops HudTick)")
ctl = build(GAME / "test" / "threnos_hud_frozen.nes",
            ["-D", "TEST_HUD_FROZEN=1"])
cgot = measure(ctl, "HUD vs RAM")
if cgot is None:
    check(False, "the control reached a battle")
else:
    check(cgot[0] > STALE_FRAMES,
          f"the control's HUD does go stale and stay stale "
          f"({cgot[0]} frames) - so the bound above means something")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_hud: PASS")
sys.exit(0)
