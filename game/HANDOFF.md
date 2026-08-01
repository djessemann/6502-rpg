# THRENOS — handoff

State of the build, the invariants that are easy to violate, and the next work
in the order it should be done. Read `design/BIBLE.md` first for what the game
*is*, then this for where the code is.

-----

## Build and verify

```
cd game
python3 tools/build.py     # art + world + script + data + music + title -> src/gen/*
make                       # -> threnos.nes   (MMC3, 256KB PRG / 128KB CHR)

# static checks over the content, before you run anything
python3 tools/check_areas.py     # 27 area maps: reachability, objects, ids
python3 tools/check_world.py     # the overworld: every site reachable, in order
python3 tools/check_progress.py  # solve the gate graph: is the game finishable
python3 tools/music_check.py     # song data vs the bytes in the built ROM

# the emulator tests
python3 test/t_step0.py      # boots and renders
python3 test/t_field.py      # scrolling, movement
python3 test/t_text.py       # window open/close over the map
python3 test/t_town.py       # overworld -> Landfall warp
python3 test/t_seam.py       # colours stay in palette across the nametable seam
python3 test/t_sound.py      # driver liveness + negative control
python3 test/t_chest.py      # opening a chest, and its flag sticking
python3 test/t_inn.py        # resting, and being refused when broke
python3 test/t_story.py      # a trigger plays, arms its boss, and never replays
python3 test/t_gate.py       # the Anchor gates, and the grav-lift
python3 test/t_battle.py     # an encounter resolves
python3 test/t_battle2.py    # a longer fight, mashing FIGHT
python3 test/t_battleai.py   # enemy casters, status effects, and their control
python3 test/t_titlescreen.py # the title module against stubs, with save tests
python3 test/t_title.py      # the title in the real ROM, through to the field
python3 test/t_ending.py     # THE ARCHON -> ARCHON PRIME -> the ending
python3 test/t_menu.py       # START: item, equip, tech, the character sheet
python3 test/t_shop.py       # buying, selling, and a save terminal
python3 test/t_item.py       # who a battle item is for, and revive
python3 test/t_journey.py    # the shipped ROM, played: title -> town -> menu
python3 test/t_apu.py        # the ROM actually plays notes (slow: ~3 min)
python3 test/t_arena.py      # the battle screen survives a scrolled camera
python3 test/t_hits.py       # kills clear the arena, hits flash (slow: ~10 min)
```

`make SOUND=src/sound_stub.s` links a silent ROM — useful when bisecting.

**Verification is not optional here.** Every subsystem in this repo was landed
by driving `test/harness.py` (pyntendo) and *looking at the frames*, and every
bug in the list at the bottom of this file was found that way, not by reading
the code. `harness.Run` gives you `step/tap/hold/idle`, `shot()` (PNG you can
open with the Read tool), `digest()` and `region()`. `test/play.py` adds
`start_game()` (drive the title into the field — the ROM no longer boots
straight onto the map, and a test that forgets this scripts a walk at a menu
and quietly measures nothing), a window-aware `Player.walk()`, and
`route_between()`. When a frame looks wrong, the fastest tool is a per-tile-row
dump:

```python
for row in range(30):
    band = np.asarray(r.frame)[row*8-8:row*8, :, :]      # frame row = NES y - 8
    print(row, int((band.sum(axis=2) > 40).sum()))
```

pyntendo crops to 240x224 (8px off each edge), so screen column 0/31 and rows
0/29 are not visible in captures. That is overscan, not a bug.

The other decisive tool is the **halt probe**: insert "disable rendering, set
the backdrop to a distinctive colour, `jmp *`" at a suspect point, rebuild, run
40 frames, and check whether the screen is that colour. Write probes into
`scratchpad`, not the repo. **One trap, learned the hard way:** a halt probe
that paints the palette a flat colour is indistinguishable from a palette-
corruption bug, which also paints the palette a flat colour. The discriminator
is a freeze test — step a few more frames and compare digests. A halt is
frozen; a bug keeps animating.

Every test must have a **negative control**: a build where the feature is
absent or disabled, on which the assertion must fail. A test that passes on a
ROM without the feature is measuring nothing, and several in this repo did
before they were fixed.

-----

## ROM map

| Bank | Contents |
|------|----------|
| 0-3 | script (193 messages; msg id -> bank `0 + id>>6`, entry `id & 63` in that bank's own address table at $8000) |
| 4-5 | 27 area maps (bank 4 is at 7971/8100 bytes — nearly full) |
| 8 | the 128x128 overworld |
| 9 | tilesets |
| 10 | numeric game data (monsters, items, techs, classes, XP, formations, zones, shops, the gate tables) |
| 11 | the title screen's nametable, attributes and palette |
| 24 | sound driver + all music (4571/8192 used) |
| 25 | battle |
| 27 | title, squad muster, save file |
| 26, 28, 29 | **free code banks** at $A000 — field menus and shops go here |
| 30 | fixed at $C000: field engine + text/window engine |
| 31 | fixed at $E000: kernel (reset, NMI, banking, VBUF, input, RNG, math) |

CHR: bank 0 font/window, 1 UI, 2-7 tilesets (2 per tileset), 32-68 monsters
(one 1KB bank each), 88-91 sprites, 92-93 the title screen.

Memory: `src/zp.inc` and `src/ram.inc` are the authoritative maps and use fixed
addresses rather than segments. **Add new variables there, never with `.res` in
a `BSS` segment** — the linker's BSS would land on top of the fixed addresses.
Zero page is allocated to `$E1`; `battle.s` also claims `$F0-$F5` locally.

-----

## Invariants you will break if you do not know them

1. **The NMI handler may never borrow `tmp0..tmp7`.** `FlushVBuf` used `tmp0`
   for a packet mode, and `VBufAlloc` keeps its packet size in `tmp0` across
   about fifty cycles — so an NMI landing in that window made the queue
   advance by 1 byte instead of 4+count, destroyed its framing, and eventually
   had `FlushVBuf` parse a packet's *data* as a header and write tile ids into
   palette RAM. That is the whole story of the "seam palette corruption" bug:
   shapes stayed legible, only colours broke, and the bad colours were dungeon
   tile ids masked to six bits. NMI now uses `vram_mode`/`vram_cnt`.
2. **`ScreenOff`/`ScreenOn`, never a raw PPUSTATUS vblank poll.** The NMI
   handler reads PPUSTATUS and clears the vblank flag, so a main-thread poll
   spins forever once NMI is on. `ScreenOff` hands the job to NMI when NMI is
   running and only polls when it is off; `ppu_ctrl` bit 7 must therefore
   always match the real register, or `ScreenOff` hangs.
3. **The vblank budget is ~1750 cycles after OAM DMA — about 100 bytes.** Two
   32-tile rows per frame is the working ceiling. Battle menus and the title's
   row queue both pace at two rows/frame for exactly this reason; four rows
   silently truncated and looked like a logic bug.
4. **The window only opens while the leader is grid-aligned.** That is what
   makes `cam_x`/`cam_y` multiples of 16 (hence `HERO_SX = 128`, not 120), so
   the window covers whole attribute quadrants and no palette bleeds.
5. **Scratch collisions are the dominant bug class in this codebase.**
   `BuildRowStrip` and `AttrRowCore` both own `tmpd`; `AttrRowForce`,
   `DecodeRow` and `PutNumber` all clobber X; `StoryFlagSet` ends in `TAX`;
   `HudLine` goes through `ptr`. Loops that call them must count in memory
   (`box_row_i`/`box_cnt`, `loop_i`, `hit_i`, `ti_flush`) and reload X from a
   variable afterwards. `SetPrgData`, `SetPrgCode` and `Random` were made
   register-safe *because* callers assumed it — keep them so.
6. **Maps do not wrap.** The camera clamps; every map is >= 16x16 metatiles.
   Metatile ids must stay <= 127 (the RLE uses bit 7 as the run flag).
7. **Data reads must set their own bank every time.** Any routine reading
   through $8000 sets `SetPrgData` first — the map, text and table banks all
   compete for that window.
8. **A flag-setting instruction between a load and its branch.** This project
   has now shipped this bug twice. `INY` between `LDA (ptr),y` and `BMI` broke
   the map RLE decoder; `INY` between `LDA (ptr),y` and `BEQ` broke the music
   pattern parser, which then walked off the end of every pattern and played
   whatever followed as if it were note data -- no music, a constant buzz, and
   the whole test suite green. `INX`/`INY`/`DEX`/`DEY` set N and Z from the
   register. Put an explicit `CMP` back in, or branch before you increment.
9. **A state that owns the whole screen owns the camera too.** `BattleEnter`
   zeroes `cam_tx`/`scroll_x` so `RowSegs` addresses the arena as one unsplit
   32-tile row. `StField` used to recompute the field camera *after*
   `UpdateHero` had already started the battle, which put every later row write
   at the field's column offset: the window came out torn in half, the HUD lost
   the party names off the left edge, and every button press redrew more of the
   same — which reads as flicker on hardware. Anything at `GS_BATTLE` or above
   is off limits to `UpdateCamera`.
10. **The NMI writes at most `VBUF_BUDGET` bytes of PPUDATA.** Vblank is ~2273
   cycles and OAM DMA takes 513; the flush loop costs about 16 cycles a byte.
   `FlushVBuf` drains the queue front to back across frames through `vbuf_rp`
   and the main thread only rewinds it once NMI has emptied it, so a producer
   that queues six rows at once no longer spills PPU writes into active
   rendering — it just takes three frames to appear.
11. **What is on screen is derived from state, never pushed to it.** The
   battle arena and the party HUD both work this way, and both were rewritten
   into it after the same class of bug. `EraseEnemy` used to work out an
   enemy's screen position itself instead of sharing `EnemySlotPos` with the
   painter; when the layout table grew a row per group size only the painter
   was updated, so a corpse was blanked at coordinates nothing had been drawn
   at and stayed on screen for the rest of the fight. The HUD was refreshed one
   row per message, so an attack that hit the whole party updated one member's
   HP and left three reading stale numbers. Now a kill or a hit only sets a bit
   in `btl_dirty`, and `ArenaTick` repaints that slot from `b_alive`/`btl_blink`
   a frame later; `HudTick` compares each row's live stats against `hud_shadow`
   and redraws whatever drifted. Neither can be left showing the wrong thing,
   and no future edit to the two dozen places that move a stat has to remember
   to announce it.
12. **A refused `VBufAlloc` must not be recorded as drawn.** The queue fills,
   and a producer that shrugs off the refusal loses that row permanently — half
   an erased corpse, a HUD line frozen at the wrong HP. `WriteRowSegs` returns
   carry set when it could not queue the whole row; `EraseEnemy`/`RedrawEnemy`
   do the same; every caller leaves its dirty bit set and comes back next frame.
13. **`LoadObjects` fills entity slots 1..`MAX_ENT`-1 and silently drops the
   rest.** The overworld had 14 warps against a cap of 11 and lost the
   Ossuary, the Causeway and Erebus — the endgame dungeon had no entrance at
   all, and nothing said so. `MAX_ENT` is 16 now and `check_world.py` asserts
   the count.

-----

## What works today

Boots to a **title screen**: NEW GAME or CONTINUE, then a squad muster where
all four party members are picked from the six classes with that class's
opening stats under the cursor. From there you can walk the 2048x2048 world
with real two-axis scrolling, enter all six towns and all 21 dungeon floors
through their warps, talk to NPCs, open chests, rest at inns, trigger
zone-weighted random encounters and fight them — enemy casters use their techs,
status effects land and are cured, bosses use their specials — level up,
relight the four Anchors in the order the script was written for, and finish
the game. Music changes per map and per battle; SFX fire on hits, criticals,
menus and saves.

Progression is gated: the Tide Anchor will not open until Cinder is lit, Storm
until Tide, Hollow and Relay Nine until Storm, Erebus until Hollow. Relighting
Tide hands over the skiff and Storm the grav-lift, and the grav-lift is what
opens the ridge around the Rift basin — which is where Lastport's endgame shops
and Erebus itself are. `tools/check_progress.py` solves that graph forward from
an empty save every build.

START opens a **field menu** (bank 26): ITEM, EQUIP, TECH and a full character
sheet. Items heal, cure, revive and restore TP on a member you choose; EQUIP
swaps gear against the class mask and re-derives the stats through `Rederive`
in the battle bank; TECH spends TP on support techs and refuses the ones that
only work in a fight. **Shops** (bank 29) buy and sell at half price, and save
terminals write the file.

The save file lives at $6200 behind a magic word and a checksum; the live game
state is $6006-$61FF and a save is a copy of it. `SaveGame`, `LoadGame` and
`SaveValid` are in `src/title.s`, `StampPosition` in `field.s` writes the
party's position into the block, and the save terminals in `shop.s` call both.
`t_titlescreen.py` proves the round trip and that a file whose checksum no
longer matches is refused. What no test here can prove is that the battery
survives a power cycle: pyntendo has no cartridge-battery file. The iNES header
sets the battery bit (flags6 = $43), which is what makes FCEUX and Mesen write
a `.sav`, but confirming that end needs one of those emulators.

-----

## Next work, in order

**1. A scripted playthrough that reaches the ending.** `t_journey.py` plays the
shipped ROM through the title, the muster, a warp, the menu and a walk, but it
walks two cells, not eighty. A long scripted walk does not reliably arrive: one
blocked step -- a mountain the route thought was open, a battle that ends on a
different frame parity -- desynchronises the rest of the path, and nothing in a
frame tells the walker where the party actually is. The fix is a test-only
build define that draws `ent_gx`/`ent_gy` somewhere on screen, so the walker can
read its own position and correct. Everything else needed is already in
`test/play.py`.

**2. Art.** The four Anchor core floors share one plan varied only by material,
and it shows on `test/shots/areas.png`.

**3. The early game is still soft.** After the encounter pass, levels 10-24 are
3-5 round fights costing 10-30% HP, but levels 2-8 still resolve in one or two
rounds. Four characters against three low-tier monsters is four attacks against
three targets, and no amount of HP fixes that shape -- it needs either smaller
early parties or bigger early groups, and both are design decisions rather than
tuning.

-----

## How a scene works now

`CheckTrigger` fires when the party *lands* on an `OB_TRIG` cell whose story
flag is clear. If `boss_by_map[map_id]` names a boss, the trigger arms it in
`pend_form`, remembers the flag in `pend_flag`, and — for an Anchor core
(script id 2) — remembers its message in `pend_msg`. The scene's message plays,
and `StBoxClose` starts the fight when the window finishes closing. The flag is
set only when the battle is *won*, so losing, fleeing or reloading leaves the
trigger armed and the boss can be retried.

Victory sets the flag through `MarkStory`, which also grants whatever
`boon_tab` says that flag hands over (the skiff, the grav-lift). Then, if
`pend_msg` names an Anchor core, the three messages that follow it play as one
chained scene: the relight, the spark, and the key item. The script authors
them consecutively for exactly this — `MSG_STORY_CINDER_CORE`, `_RELIGHT`,
`_SPARK`, `_PASSKEY` — so the whole post-victory scene is one call.

`ShowMessageChain(A = first id, X = extra count)` shows consecutive ids as one
scene. The count lives in `chain_n`, **not** `tmpa`: `SetMessage` uses `tmpa`
as scratch, and stashing it there made the chain length come back as the
message id and walk off the end of the table into garbage.

## Where the difficulty lives

`tools/balance.py` simulates every formation at the level the player actually
reaches it and prints win rate, rounds and HP lost. Run it after touching any
number in `gamedata.py`. It found 55 of 62 random encounters ending in one or
two rounds for under 5% of the party's health -- a game the player holds A
through -- and three things came out of fixing that:

* `ENC_HP_GAIN` / `ENC_ATK_GAIN` / `ENC_DEF_GAIN` scale the rank-and-file with
  tier. The hand-written numbers in `MONSTERS` are a shape, not a scale; party
  ATK had outrun them. Bosses are excluded and keep their authored values.
* `ZONES` is authored against the level each zone is reached at, not by theme
  alone. It used to put the same tier-3 monsters in a level-4 zone and a
  level-8 one, and the three endgame zones all drew from the same five
  formations.
* `FORMATIONS` gives early encounters one body per party member. Two monsters
  against four characters cannot survive a round however much HP they have.

The target is 3-4 rounds and 10-25% HP for an ordinary encounter, and no random
encounter that can wipe a party at the level it appears. ARCHON PRIME sits at
about 75%, which is where a final boss should be.

## Gating, and where it is authored

`tools/gating.py` holds the whole progression as data: which map needs which
story flag, what message refuses you, and which flag grants which vehicle. It
asserts that the flag numbers still belong to the maps it thinks they do, so
moving a trigger cannot silently re-point a gate at the wrong Anchor. The
tables land in the engine bank as `gate_flag`, `gate_msg` and `boon_tab`;
`CheckWarp` reads the first two and `MarkStory` the third.

Terrain gating is in `TryStep`. RIDGE is `PROP_SOLID | PROP_HIGH`, so the
grav-lift has to be consulted **before** the solid test or high ground is
rejected before it is asked about.

## Known rough edges

- The inn rests the party the moment you talk to it, with no yes/no prompt —
  a confirm step wants a small menu state the field engine does not have yet.
  Add it with the field menus.
- Chest loot lives in `CHEST_LOOT` in `tools/areas.py`, keyed by chest flag id
  (chests are numbered in build order). 24 of the 65 chests carry gear.
- The battle HUD's `PutNumber` output is misplaced on the HP line, and the
  status tag (`P`/`T`/`B`/`S`) at column 8 reads cramped against a 7-letter
  name. Both cosmetic.
- `VBufAlloc` still has a narrow race of the same shape as invariant 1: it
  overwrites the old terminator with the mode byte and writes the new
  terminator afterwards. Writing the terminator first and the mode byte **last**
  (mode = "this packet is valid") closes it for free.
- `nmi_ready` ($1B) is documented as the NMI/main handshake and is referenced
  by nothing. There is no handshake.
- `design/BIBLE.md` says `XP(n) = 24 * n^2.1` capped near 330,000;
  `gamedata.py` emits `* 4` and caps at 121,400. The curve's shape is right —
  it puts the party at 25 of 30 for the final boss — but the doc and the code
  disagree and one of them should move.
- `design/MECHANICS.md` lists the five status effects but not what they do. The
  semantics now implemented in `battle.s` should be written down there.
- The four Anchor core floors share one plan varied by material; visible as
  repetition on `test/shots/areas.png`.
- Bank 4 has 129 bytes of slack. New maps will spill into banks 6-7, which the
  packer handles, but do not grow the existing ones.
- `PROP_COUNTER` exists but nothing implements talking across a shop counter,
  so shop and inn objects sit on walkable cells rather than behind one.
