"""The field menu: START opens it, and every page does its job.

Boots a test-only ROM standing next to Landfall's general store, so the run can
buy a spare weapon (the only way to reach a non-empty EQUIP list this early)
and then wear it. Every assertion reads the CHARACTERS off the frame through
test/glyphs.py — not pixel counts — so "the screen says X" means it says X.

Negative control: the same sources are linked a second time with
-D TEST_NO_MENU, which removes the START hook and the shop/save dispatch from
field.s. Every check that proves a menu appeared is repeated against that ROM
and must fail there.
"""
import sys
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

from harness import Run, press, A, B, START, UP, DOWN          # noqa: E402
import glyphs                                                   # noqa: E402
import areas, art_tiles, world                                  # noqa: E402
from maps import OB_SHOP                                        # noqa: E402

LANDFALL = areas.build_all(art_tiles.town(), art_tiles.dungeon())[0]
SHOP = next(o for o in LANDFALL.objects if o[0] == OB_SHOP)
SX, SY = SHOP[1], SHOP[2]

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build(rom, extra=()):
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID['LANDFALL']}",
            "-D", f"TEST_START_X={SX}", "-D", f"TEST_START_Y={SY + 1}",
            "-D", "TEST_NO_ENCOUNTERS=1", "-D", "TEST_LIST_N=3",
            "-D", "TEST_HURT_PARTY=1"] + list(extra)
    tag = "menuctl" if extra else "menu"
    objs = []
    for src in sorted((GAME / "src").glob("*.s")) + \
            sorted((GAME / "src" / "gen").glob("*.s")):
        if src.name == "sound_stub.s":
            continue
        obj = GAME / "test" / f"{tag}_{src.parent.name}_{src.stem}.o"
        subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + defs +
                       ["-o", str(obj), str(src)], check=True)
        objs.append(str(obj))
    subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(rom)] + objs,
                   check=True)
    return rom


# --- navigating by what is on screen -----------------------------------------
# Counting taps is how this test drifted: one page behaved differently from the
# guess baked into the tap count and every assertion after it was reading the
# wrong screen. These move the cursor to a named row and check they got there.
TOP_ROWS = (16, 17, 18, 19)
WHO_ROWS = (3, 6, 9, 12)
LIST_ROWS = (3, 4, 5)


def cursor_row(r, rows):
    for i in rows:
        if glyphs.line(r.frame, i).lstrip().startswith(">"):
            return i
    return None


def move_to(r, rows, label):
    """Put the cursor on the row containing `label`. True if it got there."""
    for _ in range(len(rows) + 3):
        tgt = next((i for i in rows if label in glyphs.line(r.frame, i)), None)
        if tgt is None:
            return False
        cur = cursor_row(r, rows)
        if cur == tgt:
            return True
        r.tap(DOWN if cur is None or cur < tgt else UP, 3, 20)
    return False


def pick(r, rows, label, settle=45):
    if not move_to(r, rows, label):
        return False
    r.tap(A, 3, settle)
    return True


def to_roster(r, limit=6):
    """Back out until the top page is showing again."""
    for _ in range(limit):
        if glyphs.line(r.frame, 1).strip().startswith("CREDITS"):
            return True
        r.tap(B, 3, 35)
    return glyphs.line(r.frame, 1).strip().startswith("CREDITS")


def face_and_talk(r):
    """Face the shop counter without leaving the cell, then press A."""
    r.step(press(UP), 4)
    r.step([0] * 8, 4)
    r.tap(A, 3, 40)


def buy(r, n):
    """From the field: into the shop, buy stock line n, back out to the field."""
    face_and_talk(r)
    r.tap(A, 3, 40)                     # BUY
    for _ in range(n):
        r.tap(DOWN, 3, 12)
    r.tap(A, 3, 40)
    r.tap(B, 3, 40)                     # back to the shop root (cursor on BUY)
    r.tap(DOWN, 3, 12)
    r.tap(DOWN, 3, 12)                  # LEAVE
    r.tap(A, 3, 40)


ROM = build(GAME / "test" / "threnos_menu.nes")
CTL = build(GAME / "test" / "threnos_menu_nomenu.nes", ["-D", "TEST_NO_MENU=1"])

print(f"Landfall general store at ({SX},{SY})")

# =============================================================================
print("\nthe menu opens")
r = Run(rom=ROM)
r.idle(30)
field = r.digest()
r.tap(START, 3, 30)
opened = r.frame
r.shot("menu_1_top")
check(r.digest() != field, "START changes the picture")
check(glyphs.says(opened, "CREDITS"), "the roster page shows CREDITS")
check(glyphs.read(opened, 1, 16, 8) == "> ITEM  ", "row 16 is '> ITEM'")
check(glyphs.line(opened, 17).strip() == "EQUIP", "row 17 is EQUIP")
check(glyphs.line(opened, 18).strip() == "TECH", "row 18 is TECH")
check(glyphs.line(opened, 19).strip() == "STATUS", "row 19 is STATUS")
check("SOLDIER" in glyphs.line(opened, 3) and "LV 1" in glyphs.line(opened, 3),
      "row 3 is the SOLDIER's class and level")
check(glyphs.line(opened, 4).strip() == "HP   40/  40  TP   0/  0",
      f"row 4 is the SOLDIER's HP and TP ({glyphs.line(opened, 4).strip()!r})")
check("PSION" in glyphs.line(opened, 12), "row 12 is the fourth member")

# --- negative control ---------------------------------------------------------
c = Run(rom=CTL)
c.idle(30)
cfield = c.digest()
c.tap(START, 3, 30)
c.shot("menu_1_control")
check(c.digest() == cfield and not glyphs.says(c.frame, "STATUS"),
      "CONTROL: with the START hook compiled out, START does nothing")

# =============================================================================
print("\nthe cursor moves, and only the two rows it touched are redrawn")
before = [glyphs.line(r.frame, x) for x in range(1, 20)]
r.tap(DOWN, 3, 20)
after = [glyphs.line(r.frame, x) for x in range(1, 20)]
changed = [1 + i for i, (a, b) in enumerate(zip(before, after)) if a != b]
check(changed == [16, 17], f"exactly rows 16 and 17 changed ({changed})")
check(glyphs.read(r.frame, 1, 17, 8) == "> EQUIP ", "the cursor is on EQUIP")
r.tap(UP, 3, 20)
check(glyphs.read(r.frame, 1, 16, 8) == "> ITEM  ", "and back on ITEM")

# =============================================================================
print("\nITEM lists the pack")
r.tap(A, 3, 40)
item = r.frame
r.shot("menu_2_item")
check(glyphs.line(item, 1).strip() == "ITEM", "the page is headed ITEM")
check(glyphs.read(item, 1, 3, 12) == "> MEDKIT    ", "MEDKIT is the first entry")
check(glyphs.line(item, 3).strip().endswith("5"), "and it shows a count of 5")
check("ANTITOX" in glyphs.line(item, 4), "ANTITOX is the second entry")

print("\n...and refuses what it cannot use here")
r.tap(A, 3, 30)                          # use it on whom
check(glyphs.line(r.frame, 1).strip() == "USE ON WHOM", "it asks for a member")
r.tap(A, 3, 40)                          # on a SOLDIER at full HP
check(glyphs.says(r.frame, "NO EFFECT"),
      "a medkit on a member at full HP says NO EFFECT")
r.tap(B, 3, 40)
check(glyphs.line(r.frame, 3).strip().endswith("5"),
      "and the medkit was NOT consumed")
r.tap(B, 3, 40)

# =============================================================================
print("\nthe list scrolls (this build shows three rows at a time)")
r.tap(B, 3, 40)                          # out of the menu, into the shop
for line in (1, 2, 3):                   # BATON, WORKSUIT, HARD HAT
    buy(r, line)
r.tap(START, 3, 40)
r.tap(A, 3, 40)                          # ITEM
first = [glyphs.line(r.frame, x) for x in (3, 4, 5)]
check(len([x for x in first if x.strip()]) == 3, "three entries are visible")
for _ in range(4):
    r.tap(DOWN, 3, 20)
scrolled = [glyphs.line(r.frame, x) for x in (3, 4, 5)]
r.shot("menu_3_scrolled")
check(scrolled != first, f"walking past the window scrolled it\n"
                         f"         {first}\n      -> {scrolled}")
check(all(x.strip() for x in scrolled), "and every visible row is filled in")
r.tap(B, 3, 40)

# =============================================================================
print("\nEQUIP puts the new weapon on, and re-derives the stats")
r.tap(DOWN, 3, 20)
r.tap(A, 3, 40)                          # EQUIP -> whose
check(glyphs.line(r.frame, 1).strip() == "EQUIP", "it asks whose gear")
r.tap(A, 3, 40)                          # the SOLDIER's slots
slots = r.frame
r.shot("menu_4_slots")
check("SOLDIER" in glyphs.line(slots, 1), "the slot page names the member")
check(glyphs.read(slots, 1, 6, 18) == "> WEAPON   KNIFE  ",
      f"WEAPON reads KNIFE ({glyphs.read(slots, 1, 6, 18)!r})")
check("WORKSUIT" in glyphs.line(slots, 7), "ARMOUR reads WORKSUIT")
atk_before = glyphs.line(slots, 3).strip()
check(atk_before.startswith("ATK   11"), f"ATK is 11 ({atk_before!r})")

r.tap(A, 3, 40)                          # what fits the weapon slot
choices = glyphs.line(r.frame, 3)
check("BATON" in choices, f"the BATON we bought is offered ({choices.strip()!r})")
r.tap(A, 3, 50)                          # wear it
worn = r.frame
r.shot("menu_5_equipped")
check(glyphs.says(worn, "EQUIPPED"), "the menu confirms EQUIPPED")
check("BATON" in glyphs.line(worn, 6), "the WEAPON slot now reads BATON")
atk_after = glyphs.line(worn, 3).strip()
check(atk_after.startswith("ATK   13"),
      f"ATK went 11 -> 13, so Rederive ran in the battle bank ({atk_after!r})")

r.tap(B, 3, 40)                          # back to the member list
r.tap(B, 3, 40)                          # back to the roster (cursor on EQUIP)
r.tap(UP, 3, 20)                         # ...move it to ITEM
r.tap(A, 3, 40)                          # the knife should have come off into it
seen = set()
for _ in range(6):                       # the window is three rows: walk the list
    seen.update(glyphs.line(r.frame, x).strip() for x in (3, 4, 5))
    r.tap(DOWN, 3, 20)
check(any(s.startswith("KNIFE") or s.startswith("> KNIFE") for s in seen),
      f"the displaced KNIFE went back into the pack ({sorted(seen)})")
r.tap(B, 3, 40)

# =============================================================================
print("\nTECH spends TP, and knows what will not work out of a fight")
check(pick(r, TOP_ROWS, "TECH"), "TECH opens")
check(pick(r, WHO_ROWS, "MEDIC"), "the MEDIC can be selected")
techs = r.frame
r.shot("menu_6_tech")
check("MEDIC" in glyphs.line(techs, 1), "the tech page names the caster")
check(glyphs.read(techs, 1, 3, 8) == "> MEND  ", "MEND is listed")
check("TP" in glyphs.line(techs, 3) and glyphs.line(techs, 3).strip().endswith("1"),
      "with its TP cost")
check("CLEANSE" in glyphs.line(techs, 4), "CLEANSE is listed")

# CLEANSE is a cure, and cures ARE usable out of a fight -- so it asks for a
# target. The pair worth watching is: it works on the member who is afflicted,
# and it refuses, without charging TP, on one who is not. This build starts the
# RANGER poisoned and on 1 HP so both halves are reachable.
check(pick(r, LIST_ROWS, "CLEANSE"), "CLEANSE can be selected")
check(glyphs.line(r.frame, 1).strip() == "ON WHOM", "CLEANSE asks for a target")
check(pick(r, WHO_ROWS, "RANGER"), "the RANGER can be selected")
check(glyphs.says(r.frame, "DONE"), "and it cures them")
check(to_roster(r), "and comes back to the roster")
check(glyphs.line(r.frame, 10).strip().endswith("TP   7/  8"),
      f"the MEDIC's TP went 8 -> 7 ({glyphs.line(r.frame, 10).strip()!r})")

check(pick(r, TOP_ROWS, "TECH") and pick(r, WHO_ROWS, "MEDIC")
      and pick(r, LIST_ROWS, "CLEANSE") and pick(r, WHO_ROWS, "RANGER"),
      "CLEANSE can be cast a second time on the same member")
check(glyphs.says(r.frame, "NO EFFECT"),
      "a cure with nothing left to cure says NO EFFECT")
check(to_roster(r), "and comes back to the roster")
check(glyphs.line(r.frame, 10).strip().endswith("TP   7/  8"),
      f"and was not charged for it ({glyphs.line(r.frame, 10).strip()!r})")

check(pick(r, TOP_ROWS, "TECH") and pick(r, WHO_ROWS, "MEDIC")
      and pick(r, LIST_ROWS, "MEND"), "MEND can be selected")
check(glyphs.line(r.frame, 1).strip() == "ON WHOM", "MEND asks for a target")
check(pick(r, WHO_ROWS, "RANGER"), "the RANGER can be selected")
check(glyphs.says(r.frame, "DONE"), "and it casts")
check(to_roster(r), "and comes back to the roster")
check(not glyphs.line(r.frame, 7).strip().startswith("HP    1/"),
      f"the RANGER is off 1 HP ({glyphs.line(r.frame, 7).strip()!r})")

# =============================================================================
print("\nSTATUS is a full character sheet")
check(pick(r, TOP_ROWS, "STATUS"), "STATUS opens")
check(pick(r, WHO_ROWS, "SOLDIER"), "the SOLDIER can be selected")
st = r.frame
r.shot("menu_7_status")
check("SOLDIER" in glyphs.line(st, 3), "the class is named")
check(glyphs.line(st, 4).strip() == "VANGUARD", "so is the veteran title")
check(glyphs.line(st, 6).strip().startswith("XP"), "XP is shown")
check(glyphs.line(st, 7).strip().startswith("NEXT LEVEL"),
      "and the XP needed for the next level")
check(glyphs.line(st, 7).strip().endswith("408"),
      f"which is the level-2 entry of xp_tab, 408 "
      f"({glyphs.line(st, 7).strip()!r})")
check("STR    14" in glyphs.line(st, 11) and "AGI     8" in glyphs.line(st, 11),
      f"STR and AGI ({glyphs.line(st, 11).strip()!r})")
check("VIT    13" in glyphs.line(st, 12) and "SPI     5" in glyphs.line(st, 12),
      "VIT and SPI")
check("ATK    13" in glyphs.line(st, 13) and "DEF     6" in glyphs.line(st, 13),
      f"ATK and DEF, with the new weapon counted "
      f"({glyphs.line(st, 13).strip()!r})")
check("EVA" in glyphs.line(st, 14) and "HIT" in glyphs.line(st, 14), "EVA and HIT")
check("BATON" in glyphs.line(st, 17), "the equipped weapon")
check("WORKSUIT" in glyphs.line(st, 18), "the equipped armour")

# =============================================================================
print("\nB comes back out to the field")
r.tap(B, 3, 40)
r.tap(B, 3, 40)
r.tap(B, 3, 50)
r.shot("menu_8_field")
check(r.nonblack() > 20000, f"the map is painted again ({r.nonblack()} subpixels)")
check(not glyphs.says(r.frame, "STATUS"), "and the menu is gone")
r.step(press(DOWN), 8)
r.step([0] * 8, 4)
check(r.nonblack() > 20000, "and the party can walk")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_menu: PASS")
sys.exit(0)
