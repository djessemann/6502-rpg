"""Enemy AI and status effects, read off the screen.

Every claim here is checked by OCRing the battle message window out of the
frame — the font is generated from tools/font.py, so the same glyph bitmaps the
ROM draws with are the templates we match against, and a message either says
what we claim or it does not.

Four ROMs, all pinned to one formation with -D TEST_FORCE_FORM and built with
-D TEST_TANK_PARTY, which makes the party unkillable so one fight runs long
enough to watch (a level-1 party dies in two rounds, which is not a sample):
    caster  CULTIST x3   ai 2, special QUAKE (whole party, inflicts POISON)
    mixed   CHASSIS x2   ai 1, special JOLT - fires about one turn in three
    boss    THE ARCHON   ai 2, special SHATTER
    control the caster formation again, built -D TEST_AI_OFF so EnemyAction
            always falls through to a plain attack

The control is the point: it runs the identical script against the identical
formation, and it must NOT produce the lines the others do. Without it, "the
word USES appeared on screen" would only prove that something drew text.
"""
import sys, pathlib, subprocess, re
HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))
import numpy as np
from harness import Run, press, A, DOWN
import font, gamedata, areas, art_tiles, world
from maps import OB_TRIG

# --- OCR ---------------------------------------------------------------------
TEMPLATES = {}
for _ch, _bits in font.GLYPHS.items():
    _m = np.zeros((7, 5), bool)
    for _y in range(7):
        for _x in range(5):
            _m[_y, _x] = bool(_bits[_y] & (0x10 >> _x))
    TEMPLATES[_ch] = _m

WINDOW_LINES = (21, 22, 23, 24)         # screen tile rows of the window interior


def read_row(frame, row):
    """OCR one screen tile row. pyntendo crops 8px, so tile (r,c) starts at
    (r*8-8, c*8-8); glyphs sit at x+1..x+5, y+0..y+6 inside their tile."""
    ink = np.asarray(frame).sum(axis=2) > 400      # glyphs are colour 3 (white)
    out = []
    for c in range(1, 31):
        y0, x0 = row * 8 - 8, c * 8 - 8
        cell = ink[y0:y0 + 7, x0 + 1:x0 + 6]
        if cell.shape != (7, 5) or not cell.any():
            out.append(" ")
            continue
        hit = [ch for ch, t in TEMPLATES.items() if np.array_equal(t, cell)]
        out.append(hit[0] if hit else "?")
    return " ".join("".join(out).split())          # collapse the column padding


# --- ROM building ------------------------------------------------------------
def sources():
    """The Makefile's own source list, so a test ROM is the real ROM."""
    mk = (GAME / "Makefile").read_text()
    body = re.search(r"SRCS\s*:=(.*?)\n\n", mk, re.S).group(1)
    body = (body.replace("\\\n", " ").replace("$(SRCDIR)", "src")
                .replace("$(GENDIR)", "src/gen").replace("$(SOUND)", "src/sound.s"))
    return body.split()


def build(tag, defs):
    rom = GAME / "test" / f"threnos_{tag}.nes"
    objs = []
    for name in sources():
        src = GAME / name
        obj = GAME / "test" / f"{tag}_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] +
                       [d for k in defs for d in ("-D", k)] +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)
    return rom


# The Archon's trigger drops us into a fight without a long walk; the formation
# it starts is overridden by TEST_FORCE_FORM anyway.
MAP = "EREBUS4"
_m = areas.build_all(art_tiles.town(), art_tiles.dungeon())[
    world.MAP_NAMES[1:].index(MAP)]
_trg = next(o for o in _m.objects if o[0] == OB_TRIG)
BASE = [f"TEST_START_DUNGEON={world.MAP_ID[MAP]}", f"TEST_START_X={_trg[1]}",
        f"TEST_START_Y={_trg[2] - 1}", "TEST_NO_ENCOUNTERS=1",
        "TEST_TANK_PARTY=1"]

FORM = {f[0]: i for i, f in enumerate(gamedata.FORMATIONS)}


def transcript(rom, rounds=260):
    """Fight, collecting every distinct state of the message window."""
    r = Run(rom=rom)
    r.idle(20)
    r.step(press(DOWN), 8)          # step onto the trigger
    r.step([0] * 8, 2)
    r.idle(40)
    for _ in range(6):              # page the scene, which starts the fight
        r.tap(A, 3, 30)
    r.idle(40)
    lines, last = [], None
    for _ in range(rounds):
        r.tap(A, 2, 5)
        w = [read_row(r.frame, row) for row in WINDOW_LINES]
        if w != last:
            lines += [x for x in w if x]
            last = w
    return r, lines


ok = True


def check(cond, good, bad):
    global ok
    print(("ok   " if cond else "FAIL: ") + (good if cond else bad))
    if not cond:
        ok = False


def has(lines, *needles):
    return [l for l in lines if all(n in l for n in needles)]


# --- 1. a caster enemy uses its special, and the status it carries lands ------
caster = build("ai_caster", BASE + [f"TEST_FORCE_FORM={FORM['CULTIST']}"])
r, live = transcript(caster)
r.shot("battleai_1_caster")
print("--- caster transcript")
for l in live[:24]:
    print("   ", l)

check(bool(has(live, "CULTIST", "USES")),
      "a caster enemy uses its special", "no enemy ever used a special")
check(bool(has(live, "QUAKE")),
      "the special is named on screen", "the special was never named")
check(bool(has(live, "IS POISONED!")),
      "the special's status lands", "no status was ever inflicted")
check(bool(has(live, "TAKES POISON")),
      "poison costs HP at the start of the sufferer's turn",
      "poison never did anything after it landed")

# --- 2. the control: the same fight with the AI switched off ------------------
ctl = build("ai_none", BASE + [f"TEST_FORCE_FORM={FORM['CULTIST']}",
                               "TEST_AI_OFF=1"])
rc, dead = transcript(ctl)
rc.shot("battleai_2_control")
check(bool(has(dead, "CULTIST", "ATTACKS!")),
      "control: the same formation still fights", "control: nothing happened at "
      "all, so its silence proves nothing")
for needle in ("USES", "QUAKE", "POISONED", "TAKES POISON"):
    check(not has(dead, needle),
          f"control: never says {needle!r}",
          f"control: said {needle!r} with the AI off - the check above is "
          f"measuring something other than the AI")

# --- 3. AI mode 1 mixes its special into ordinary attacks ---------------------
mixed = build("ai_mixed", BASE + [f"TEST_FORCE_FORM={FORM['CHASSIS']}"])
rm, mix = transcript(mixed)
rm.shot("battleai_3_mixed")
atk = has(mix, "CHASSIS", "ATTACKS!")
spc = has(mix, "CHASSIS", "USES")
print(f"     CHASSIS: {len(atk)} attacks, {len(spc)} specials")
check(bool(spc), "an ai-1 enemy uses its special", "an ai-1 enemy never cast")
check(bool(atk), "an ai-1 enemy still mostly attacks",
      "an ai-1 enemy never made a plain attack")
check(len(spc) < len(atk), "and attacks more often than it casts",
      "an ai-1 enemy cast more often than it attacked")

# --- 4. the boss the whole game ends on uses its own special ------------------
boss = build("ai_boss", BASE + [f"TEST_FORCE_FORM={FORM['THE ARCHON']}"])
rb, arc = transcript(boss, rounds=120)
rb.shot("battleai_4_archon")
print("--- Archon transcript")
for l in arc[:16]:
    print("   ", l)
check(bool(has(arc, "THE ARCHON", "USES")) and bool(has(arc, "SHATTER")),
      "THE ARCHON uses SHATTER", "THE ARCHON just punched the party")

print("PASS" if ok else "FAILED")
sys.exit(0 if ok else 1)
