# THRENOS — handoff

State of the build, the invariants that are easy to violate, and the next work
in the order it should be done. Read `design/BIBLE.md` first for what the game
*is*, then this for where the code is.

-----

## Build and verify

```
cd game
python3 tools/build.py     # art + world + script + data + music -> src/gen/*
make                       # -> threnos.nes   (MMC3, 256KB PRG / 128KB CHR)
python3 test/t_field.py    # scrolling, movement
python3 test/t_text.py     # window open/close over the map
python3 test/t_town.py     # overworld -> Landfall warp
python3 test/t_sound.py    # driver liveness + negative control
python3 test/t_chest.py    # opening a chest, and its flag sticking
python3 test/t_inn.py      # resting, and being refused when broke
python3 tools/check_areas.py    # every area map: reachability, objects, ids
python3 tools/music_check.py    # song data vs the bytes in the built ROM
```

`make SOUND=src/sound_stub.s` links a silent ROM — useful when bisecting.

**Verification is not optional here.** Every subsystem in this repo was landed
by driving `test/harness.py` (pyntendo) and *looking at the frames*, and every
one of the eleven bugs listed at the bottom of this file was found that way,
not by reading the code. `harness.Run` gives you `step/tap/hold/idle`, `shot()`
(PNG you can open with the Read tool), `digest()` and `region()`. When a frame
looks wrong, the fastest tool is a per-tile-row dump:

```python
for row in range(30):
    band = np.asarray(r.frame)[row*8-8:row*8, :, :]      # frame row = NES y - 8
    print(row, int((band.sum(axis=2) > 40).sum()))
```

pyntendo crops to 240x224 (8px off each edge), so screen column 0/31 and rows
0/29 are not visible in captures. That is overscan, not a bug.

The other decisive tool is the **halt probe**: insert "disable rendering, set
the backdrop to a distinctive colour, `jmp *`" at a suspect point, rebuild, run
40 frames, and check whether the screen is that colour. That is how the boot
hang and the battle stall were located. Examples are in the git history of this
file's neighbours; write them into `scratchpad`, not the repo.

-----

## ROM map

| Bank | Contents |
|------|----------|
| 0-3 | script (193 messages; msg id -> bank `0 + id>>6`, entry `id & 63` in that bank's own address table at $8000) |
| 4-5 | 27 area maps (bank 4 is at 7963/8100 bytes — nearly full) |
| 8 | the 128x128 overworld |
| 9 | tilesets |
| 10 | numeric game data (monsters, items, techs, classes, XP, formations, zones, shops) |
| 24 | sound driver + all music |
| 25 | battle |
| 26, 27, 28, 29 | **free code banks** at $A000 — menus, title, save go here |
| 30 | fixed at $C000: field engine + text/window engine |
| 31 | fixed at $E000: kernel (reset, NMI, banking, VBUF, input, RNG, math) |

CHR: bank 0 font/window, 1 UI, 2-7 tilesets (2 per tileset), 32-68 monsters
(one 1KB bank each), 88-91 sprites. 44 of 128 banks used.

Memory: `src/zp.inc` and `src/ram.inc` are the authoritative maps and use fixed
addresses rather than segments. **Add new variables there, never with `.res` in
a `BSS` segment** — the linker's BSS would land on top of the fixed addresses.

-----

## Invariants you will break if you do not know them

1. **`ScreenOff`/`ScreenOn`, never a raw PPUSTATUS vblank poll.** The NMI
   handler reads PPUSTATUS and clears the vblank flag, so a main-thread poll
   spins forever once NMI is on. `ScreenOff` hands the job to NMI when NMI is
   running and only polls when it is off; `ppu_ctrl` bit 7 must therefore
   always match the real register.
2. **The vblank budget is ~1750 cycles after OAM DMA — about 100 bytes.** Two
   32-tile rows per frame is the working ceiling. Battle menus go through the
   pacer (`UiFlush`, at most two rows/frame) for exactly this reason; four rows
   silently truncated and looked like a logic bug. Anything bigger must be
   drawn with rendering off.
3. **The window only opens while the leader is grid-aligned.** That is what
   makes `cam_x`/`cam_y` multiples of 16 (hence `HERO_SX = 128`, not 120), so
   the window covers whole attribute quadrants and no palette bleeds.
4. **Scratch collisions are the dominant bug class in this codebase.**
   `BuildRowStrip` and `AttrRowCore` both own `tmpd`; `AttrRowForce`,
   `DecodeRow` and `PutNumber` all clobber X. Loops that call them must count
   in memory (`box_row_i`/`box_cnt`, `loop_i`). `SetPrgData`, `SetPrgCode` and
   `Random` were made register-safe *because* callers assumed it — keep them so.
5. **Maps do not wrap.** The camera clamps; every map is >= 16x16 metatiles.
   Metatile ids must stay <= 127 (the RLE uses bit 7 as the run flag).
6. **Data reads must set their own bank every time.** Any routine reading
   through $8000 sets `SetPrgData` first — the map, text and table banks all
   compete for that window.

-----

## What works today

Boots to the overworld with a fixed party of SOLDIER/RANGER/MEDIC/PSION at
level 1. You can walk the 2048x2048 world with real two-axis scrolling, enter
all six towns and all 21 dungeon floors through their warps, talk to NPCs,
trigger zone-weighted random encounters, and fight them to victory (XP,
credits, level-ups that re-derive stats and grant techs) or a party wipe. Music
changes per map and per battle; SFX fire on hits, criticals and menus.

-----

## Next work, in order

**1. Save/load (SRAM) + title + party creation.** New code bank 26.
`ram.inc` already defines the whole save layout at $6000 (`sav_magic`,
`sav_sum`, the four 32-byte character records, inventory, credits, story and
chest flags) and step 0 proved the battery RAM works. Needed: a checksum over
$6006-$61FF, a title screen with NEW GAME / CONTINUE, class picking for four
slots (`InitParty` in `battle.s` is the template — it currently hardcodes
classes 0-3), and `OB_SAVE` handling in the field. Make `GameInit` boot to the
title instead of straight into the overworld.

**2. Field menus.** New code bank 27. START opens status / item / equip / tech.
Inns are **done** (`UseInn` in `field.s`); shops and save terminals are not.
The shop and save objects already exist on all six town maps
(`OB_SHOP` carries a shop id into `shop_tab`) and
`FindObject`/`TalkOrAct` in `field.s` already locates them — they currently
fall through to "nothing happens". `battle.s` has working list-selection code
to copy (`BuildTechList`, `StartItemSel`, and the `UiFlush` pacer).

**3. Progression.** Chests are **done** (see below). Story flags for the four Anchor Sparks,
PASSKEY / SKIFF / LIFT CODE / RIFT KEY gating, and `PROP_WATER` / `PROP_HIGH`
checks in `TryStep` against the `vehicles` byte.

**4. Bosses and the ending.** `OB_TRIG` objects already sit in front of each
Anchor core. Wire them to `BattleEnter` with the boss formations (`FORM_*`
constants exist), set the arc's story flag on victory, then the Rift, the two
ARCHON stages and the ending text (all seven boss messages and the six ending
pages are already written in `tools/script_text.py`).

**5. QA.** A scripted headless playthrough that reaches the ending, plus review
agents on balance and on the engine's remaining scratch-register discipline.

-----

## Open threads left by the chest work

- **A long scripted walk does not land where the pathfinder says it should.**
  `test/t_chest.py` verifies the credits chest (14 steps) but the item chest at
  Cinder 1 (33,5) is reached by a much longer route and the party ends up short
  of it. Same engine code either way, so suspect either the test's stepping
  (8 frames held + 2 released is exactly one 16px cell — confirmed for short
  routes) or a disagreement between `TryStep`'s collision and the tileset
  `prop` table the BFS reads. The test reports this as `info` rather than
  asserting it; make it an assertion once it is understood. This is the first
  thing to look at, because a scripted playthrough (task 10) needs long walks
  to be reliable. `t_inn.py` sidesteps it with `-D TEST_START_X/Y`, which drops
  the party on a chosen cell; use that for object tests, not for pathing ones.
- **Cinder 1's south-west wing is a cul-de-sac through the exit.** From the
  entrance you can reach 371 of 372 walkable cells, but from the chest at
  (4,24) only 77 — the wing's only link to the rest of the floor is the
  entrance tile (12,18), which is the warp back to the overworld. Walking back
  costs a trip out and in. `tools/check_areas.py` does not catch this because
  it floods *over* warps; teach it to treat warp cells as one-way and re-check
  all 27 maps.

## Known rough edges

- The inn rests the party the moment you talk to it, with no yes/no prompt --
  a confirm step wants a small menu state, which the field engine does not have
  yet. Add it with the field menus.
- Chest loot lives in `CHEST_LOOT` in `tools/areas.py`, keyed by chest flag id
  (chests are numbered in build order). 24 of the 65 chests carry gear; the
  rest carry credits.
- The battle HUD's `PutNumber` output is misplaced on the HP line (cosmetic;
  the numbers themselves are right).
- Enemy AI only ever attacks — `mon_tab` carries `ai` and `special` fields that
  nothing reads yet, so casters and boss specials are inert.
- The four Anchor core floors share one plan varied by material; visible as
  repetition on `test/shots/areas.png`.
- Bank 4 has 137 bytes of slack. New maps will spill into banks 6-7, which the
  packer handles, but do not grow the existing ones.
- Shop/inn/save objects sit on walkable cells rather than behind a counter,
  because the reachability check requires it. `PROP_COUNTER` exists but nothing
  implements talking across it.
