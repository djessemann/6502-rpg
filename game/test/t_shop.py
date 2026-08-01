"""Shops and save terminals.

Two test-only ROMs: one standing at Landfall's general store, one at its save
terminal. The stock, the prices and the equip masks are read out of
tools/gamedata.py, so the assertions check the ROM against the design data
rather than against themselves; the screen is read character by character with
test/glyphs.py.

Negative control: the same sources linked with -D TEST_NO_MENU, which takes the
OB_SHOP and OB_SAVE cases back out of TalkOrAct so both objects fall through
the way they did before this work. Every "the shop appeared" check is repeated
there and must fail.
"""
import sys
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

from harness import Run, press, A, B, START, UP, DOWN            # noqa: E402
import glyphs                                                    # noqa: E402
import areas, art_tiles, world                                   # noqa: E402
import gamedata                                                  # noqa: E402
from maps import OB_SHOP, OB_SAVE                                # noqa: E402

LANDFALL = areas.build_all(art_tiles.town(), art_tiles.dungeon())[0]
SHOP = next(o for o in LANDFALL.objects if o[0] == OB_SHOP)
SAVE = next(o for o in LANDFALL.objects if o[0] == OB_SAVE)
SHOP_ID = SHOP[3]
STOCK = gamedata.SHOPS[SHOP_ID]
PRICE = {i[0]: i[3] for i in gamedata.ITEMS}
KIND = {i[0]: i[1] for i in gamedata.ITEMS}
MASK = {i[0]: i[4] for i in gamedata.ITEMS}
START_CREDITS = 200
PARTY_CLASSES = (0, 1, 2, 3)        # InitParty gives class = slot

FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build(rom, gx, gy, extra=()):
    defs = ["-D", f"TEST_START_DUNGEON={world.MAP_ID['LANDFALL']}",
            "-D", f"TEST_START_X={gx}", "-D", f"TEST_START_Y={gy}",
            "-D", "TEST_NO_ENCOUNTERS=1"] + list(extra)
    tag = rom.stem
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


def talk(r):
    """Face the object one cell north without leaving the cell, then press A."""
    r.step(press(UP), 4)
    r.step([0] * 8, 4)
    r.tap(A, 3, 45)


def credits_on(frame):
    """The number on the shop's CREDITS line, or None."""
    for row in range(1, 6):
        s = glyphs.line(frame, row).strip()
        if s.startswith("CREDITS"):
            tail = s[len("CREDITS"):].strip()
            return int(tail) if tail.isdigit() else None
    return None


SHOP_ROM = build(GAME / "test" / "threnos_shop.nes", SHOP[1], SHOP[2] + 1)
SAVE_ROM = build(GAME / "test" / "threnos_save.nes", SAVE[1], SAVE[2] + 1)
CTL_SHOP = build(GAME / "test" / "threnos_shopctl.nes", SHOP[1], SHOP[2] + 1,
                 ["-D", "TEST_NO_MENU=1"])
CTL_SAVE = build(GAME / "test" / "threnos_savectl.nes", SAVE[1], SAVE[2] + 1,
                 ["-D", "TEST_NO_MENU=1"])

print(f"Landfall store: shop id {SHOP_ID} at ({SHOP[1]},{SHOP[2]}), "
      f"stock {STOCK}")
print(f"Landfall save terminal at ({SAVE[1]},{SAVE[2]})")

# =============================================================================
print("\ntalking to a shop opens it")
r = Run(rom=SHOP_ROM)
r.idle(30)
field = r.digest()
talk(r)
root = r.frame
r.shot("shop_1_root")
check(r.digest() != field, "the picture changed")
check(glyphs.line(root, 1).strip() == "SHOP", "the page is headed SHOP")
check(credits_on(root) == START_CREDITS,
      f"it shows the purse, {START_CREDITS} ({credits_on(root)})")
check(glyphs.read(root, 1, 6, 6) == "> BUY ", "BUY is the first option")
check(glyphs.line(root, 7).strip() == "SELL", "then SELL")
check(glyphs.line(root, 8).strip() == "LEAVE", "then LEAVE")

c = Run(rom=CTL_SHOP)
c.idle(30)
talk(c)
c.shot("shop_1_control")
check(glyphs.read(c.frame, 1, 6, 6) != "> BUY " and credits_on(c.frame) is None
      and c.nonblack() > 20000,
      "CONTROL: with the OB_SHOP case compiled out, the map stays up and no "
      "BUY / SELL / purse appears")

# =============================================================================
print("\nBUY lists this shop's real stock, at its real prices")
r.tap(A, 3, 45)
buy = r.frame
r.shot("shop_2_buy")
for i, name in enumerate(STOCK):
    row = glyphs.line(buy, 5 + i)
    check(name in row, f"row {5 + i} stocks {name} ({row.strip()!r})")
    check(f"{PRICE[name]:>6}" in row or str(PRICE[name]) in row.split(),
          f"...at {PRICE[name]} credits")

print("\n...and says which of the four can carry a piece of gear")
for i, name in enumerate(STOCK):
    row = glyphs.line(buy, 5 + i)
    digits = "".join(sorted(ch for ch in row[22:] if ch.isdigit()))
    if 1 <= KIND[name] <= 4:
        want = "".join(str(s + 1) for s, cls in enumerate(PARTY_CLASSES)
                       if MASK[name] & (1 << cls))
        check(digits == want, f"{name}: {digits!r} matches its equip mask "
                              f"{MASK[name]:#08b} -> {want!r}")
    else:
        check(digits == "", f"{name} is not gear, so no member digits ({digits!r})")

# =============================================================================
print("\nbuying takes the credits and hands over the goods")
r.tap(DOWN, 3, 15)                       # BATON, 70
r.tap(A, 3, 45)
r.shot("shop_3_bought")
check(glyphs.says(r.frame, "BOUGHT"), "the shop says BOUGHT")
check(credits_on(r.frame) == START_CREDITS - PRICE["BATON"],
      f"the purse went {START_CREDITS} -> {START_CREDITS - PRICE['BATON']} "
      f"({credits_on(r.frame)})")
r.tap(A, 3, 45)                          # a second one
check(credits_on(r.frame) == START_CREDITS - 2 * PRICE["BATON"],
      f"and again ({credits_on(r.frame)})")

print("\n...and refuses when the purse is short")
r.tap(A, 3, 45)                          # 60 credits left, a BATON is 70
short = r.frame
r.shot("shop_4_short")
check(glyphs.says(short, "NOT ENOUGH CREDITS"),
      "a purchase that cannot be afforded is refused")
check(credits_on(short) == START_CREDITS - 2 * PRICE["BATON"],
      "and nothing was deducted")

# =============================================================================
print("\nSELL offers the pack at half price, and pays out")
r.tap(B, 3, 45)                          # back to the root
r.tap(DOWN, 3, 15)
r.tap(A, 3, 45)                          # SELL
sell = r.frame
r.shot("shop_5_sell")
check(glyphs.line(sell, 1).strip() == "SELL", "the page is headed SELL")
rows = [glyphs.line(sell, x) for x in (5, 6, 7)]
check(any("MEDKIT" in x for x in rows), "the pack's MEDKITs are listed")
baton_row = next((x for x in rows if "BATON" in x), "")
check(baton_row != "", "so are the batons just bought")
check(str(PRICE["BATON"] // 2) in baton_row.split(),
      f"at half price, {PRICE['BATON'] // 2} ({baton_row.strip()!r})")
check("2" in baton_row.split(), f"and both of them ({baton_row.strip()!r})")

purse = credits_on(sell)
i = next(n for n, x in enumerate(rows) if "BATON" in x)
for _ in range(i):
    r.tap(DOWN, 3, 15)
r.tap(A, 3, 50)
sold = r.frame
r.shot("shop_6_sold")
check(glyphs.says(sold, "SOLD"), "the shop says SOLD")
check(credits_on(sold) == purse + PRICE["BATON"] // 2,
      f"the purse went {purse} -> {purse + PRICE['BATON'] // 2} "
      f"({credits_on(sold)})")
after = [glyphs.line(sold, x) for x in (5, 6, 7)]
brow = next((x for x in after if "BATON" in x), "")
check("1" in brow.split(), f"one baton is left ({brow.strip()!r})")

# =============================================================================
print("\nLEAVE puts the field back")
r.tap(B, 3, 45)                          # root, cursor restored to SELL
r.tap(DOWN, 3, 15)                       # LEAVE
r.tap(A, 3, 50)
r.shot("shop_7_field")
check(r.nonblack() > 20000, f"the map is painted again ({r.nonblack()})")
check(credits_on(r.frame) is None, "and the shop is gone")
r.step(press(DOWN), 8)
r.step([0] * 8, 4)
check(r.nonblack() > 20000, "and the party can walk away")

# =============================================================================
print("\nthe save terminal asks before it writes")
s = Run(rom=SAVE_ROM)
s.idle(30)
sfield = s.digest()
talk(s)
term = s.frame
s.shot("save_1_confirm")
check(s.digest() != sfield, "the picture changed")
check(glyphs.line(term, 1).strip() == "SAVE TERMINAL", "it names itself")
check(glyphs.says(term, "RECORD YOUR PROGRESS"), "and asks")
check(glyphs.read(term, 1, 6, 6) == "> YES ", "YES is the first option")
check(glyphs.line(term, 7).strip() == "NO", "NO is the second")

cs = Run(rom=CTL_SAVE)
cs.idle(30)
talk(cs)
cs.shot("save_1_control")
# (the terminal's *script* line also contains the words "SAVE TERMINAL", so the
# control has to key on the new screen, not on the text)
check(glyphs.read(cs.frame, 1, 6, 6) != "> YES "
      and glyphs.line(cs.frame, 7).strip() != "NO"
      and cs.nonblack() > 20000,
      "CONTROL: with the OB_SAVE case compiled out, the map stays up and there "
      "is no YES / NO to answer")

s.tap(A, 3, 50)
s.shot("save_2_done")
check(glyphs.says(s.frame, "PROGRESS SAVED"), "answering YES confirms the save")
s.tap(B, 3, 50)
s.shot("save_3_field")
check(s.nonblack() > 20000, f"and B goes back to the field ({s.nonblack()})")

print("\n...and NO just walks away")
s2 = Run(rom=SAVE_ROM)
s2.idle(30)
talk(s2)
s2.tap(DOWN, 3, 15)
s2.tap(A, 3, 50)
s2.shot("save_4_declined")
check(s2.nonblack() > 20000, "NO returns to the field")
check(not glyphs.says(s2.frame, "PROGRESS SAVED"), "without saving")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_shop: PASS")
sys.exit(0)
