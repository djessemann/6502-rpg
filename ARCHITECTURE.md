# ARCHITECTURE.md — implemented vertical slice (reference)

Code map for the working slice. This is the reference implementation the engine
phase extends; it intentionally follows every structural rule in CLAUDE.md.
For hardware gotchas hit while building it, see CLAUDE.md → **Known traps**.

Build: `make` → `6502rpg.nes` (NROM, 32KB PRG + 8KB CHR). Art: regenerate with
`python3 tools/gen_assets.py`, then `make`.

-----

## Files

| File                  | Role                                                          |
|-----------------------|---------------------------------------------------------------|
| `src/header.s`        | iNES header (mapper 0, 32KB PRG, 8KB CHR, horizontal mirror). |
| `src/nes.inc`         | Hardware register constants.                                  |
| `src/main.s`          | Everything: boot, main loop, NMI, state machine, routines, palettes, tables. |
| `src/chr.s`           | **Generated.** CHR-ROM tile data (BG table 0, hero table 1). |
| `src/field.s`         | **Generated.** 2×2 world: `worldtiles` (whole world as 8px tiles, 60×64), `attr_pair_l`/`_r` (attribute palette-pairs per metatile-row), `worldsolid` (per-metatile collision, 32×30), `winmap`. |
| `src/tiles.inc`       | **Generated.** Tile/geometry constants and message ids (`HERO_*_TILE`, `ENEMY_TILE_BASE`, `WIN_STEPS`, `MSG_*`). |
| `src/messages.s`      | **Generated.** `msg_table` + wrapped/paginated message byte streams. |
| `tools/gen_assets.py` | Dev-time art source-of-truth → emits `chr.s` + `field.s`. Not in the `make` path. |
| `nes.cfg`             | ld65 config (RAM/PRG/CHR layout, segments).                   |

-----

## RAM map (`nes.cfg`)

```
$0000-$00FF  zeropage (vars below)
$0100-$01FF  stack
$0200-$02FF  shadow OAM   -> DMA'd to PPU every NMI
$0300-$03FF  VRAM buffer  (VBUF; one packet/frame, see below)
$0400-$07FF  general game RAM (BSS: entity arrays)
```

Key zeropage: `frame_count`($00), `ptr`($01-02, general 16-bit pointer),
`pad1/_prev/_new`, movement scratch (`newgx/gy`, `tpx/tpy`, `cs_*`, `mt_*`),
`gamestate`($0E), `step_count`, `battle_timer`, `job_step`, `vpkt_*`.

-----

## CHR / tile index map

Pattern table 0 (background, `$0000`) — ids are assigned by the generator, in
order: blank `$00`; then **terrain metatiles** (grass, flower, path, tree, wall,
bush, water — each 4 subtiles, pixel-doubled from 8px art); the **NPC** metatile
(4 subtiles, its authored facing); the window frame (9 tiles); the font glyphs;
the enemy (4×4). `main.s` hardcodes no terrain ids — the nametables reference
them directly and collision uses `worldsolid` — so only `ENEMY_TILE_BASE`,
`WIN_BOTTOM_TILE`, `ARROW_TILE`, `DIGIT_TILE`, `CURSOR_TILE` are emitted to
`tiles.inc` for the (gated) text/battle code.

Pattern table 1 (sprites, `$1000`): hero, 3 facings x 2x2 — down `$00`, up `$04`,
side `$08` (left = side flipped at draw time). `PPUCTRL` selects BG table 0 /
sprite table 1 (`%10001000`).

These ranges are emitted to **`src/tiles.inc`** by `gen_assets.py`
(`HERO_*_TILE`, `TILE_NPC_LO/HI`, `ENEMY_TILE_BASE`); `main.s` includes it, so
no tile numbers are hardcoded in the assembly.

-----

## Directional characters (the convention for all actors)

Every character (player and NPC) tracks an `ent_dir` and is drawn facing it,
from **three authored 16x16 views**: **down** (front), **up** (back), **side**
(right-facing). The fourth facing (left) is a horizontal mirror of the side:

- **Sprites** (hero, future moving NPCs): `BuildOAM` is table-driven by
  `ent_dir` (`dir_tiles`, `dir_attr`, `slot_dx/dy`). Left reuses the side tiles
  with the OAM **H-flip bit** ($40) set and the two tile **columns swapped**.
  Adding a character = add its 3 views to pattern table 1 + a `dir_tiles` row.
- **Background NPCs** (can't hardware-flip): `gen_assets.py` mirrors the side
  art to make a 4th tile set, so the NPC has all four facings as BG tiles. A
  stationary NPC's facing is the authored `NPC_FACING` in `gen_assets.py`.

-----

## Split game loop

`MAIN` (logic, no PPU access):
```
ReadInput → VBufClear → UpdateGame → (BuildOAM | HideHero) → WaitFrame → loop
```
`NMI` (the only per-frame PPU writer): OAM DMA → flush VBUF → reset scroll →
`SoundTick` (stub) → `inc frame_count`. `WaitFrame` spins on `frame_count`.

-----

## VRAM buffer (`VBUF` = $0300)

One packet per frame: `[hi, lo, count, data...]`. `hi == $00` ⇒ empty (NMI skips).
`VBufClear` zeros it each frame; dialog/enemy code fills at most one small packet
(≤ ~8 bytes) so the flush fits in vblank. Larger updates are drawn as a sequence
of packets across frames (see job stepping below).

Full-screen redraws (field↔battle) do **not** use VBUF — they run with rendering
and NMI disabled (`EnterBattle`/`ExitBattle`/boot).

-----

## Game state machine (`gamestate`, driven in `UpdateGame`)

```
GS_FIELD(0)      walk; A+facing NPC → OPENING (field msg); Select/steps → EnterBattle
GS_OPENING(1)    open the box (DrawStep, mode=open, 9 chunks)            → GS_TEXT
GS_DIALOG(2)     field message fully shown; A → CLOSING
GS_CLOSING(3)    restore field under the box (DrawStep, mode=close)      → FIELD
GS_ENEMYDIE(5)   EraseEnemyRow, one tile-row/frame (4 frames)           → BATTLEWAIT
GS_BATTLEWAIT(6) battle_timer countdown → ExitBattle                    → FIELD
GS_TEXT(7)       render message lines (RenderLine); ends per msg_context
GS_TEXTWAIT(8)   page full ("▼" prompt), A → next page
GS_BWAIT(9)      battle message shown; A advances combat (battle_phase)
GS_MENU(10)      command/equip menu shown; cursor input (up/down/A/B)
```

`msg_context` (FIELD/BATTLE/MENU) decides where `GS_TEXT` goes when a message
ends: FIELD→`GS_DIALOG`, BATTLE→`GS_BWAIT`, MENU→`GS_MENU`. The hero is hidden
whenever `in_battle` is set (the whole battle screen), drawn otherwise.

### Menus & equipment

Field A opens the command menu (`OpenMenuBox`). A menu is just a composed
message (`ComposeMenu` builds option lines with a `CURSOR_TILE` on `menu_cursor`
into `msg_buf`) rendered through `GS_TEXT`; `GS_MENU` handles up/down (move
cursor → `RenderMenu`), A (confirm), B (cancel/back). Menus: `MENU_CMD`
(Talk→dialogue if `FacingNPC` else `MSG_NOBODY`; Equip→`MENU_EQUIP`) and
`MENU_EQUIP` (pick a weapon → sets `equipped`/`player_atk` from `weapon_atk[]`,
shows a live "Power"). `DoAttack` deals `player_atk`, so the equipped weapon's
stat drives battle damage. This menu/cursor code is the reusable UI primitive
for battle commands, items, etc.

### Battle flow

`EnterBattle` cuts to the black arena (`DrawBattle` draws the enemy), sets
`enemy_hp`, then opens the box and shows `MSG_SLIME_APPEARS`. `GS_BWAIT` drives
combat by `battle_phase`: each A runs `DoAttack` (damage 4-7 capped to HP,
`ComposeDamage` builds "The Slime takes N damage!" in `msg_buf`) and re-renders;
at 0 HP it shows `MSG_SLIME_DEFEATED`, then erases the enemy and `ExitBattle`
returns to the field at the prior spot.

-----

## Text engine

Messages are authored as plain strings in `gen_assets.py`; the tool word-wraps
to the 30-col interior and paginates to 4 lines, emitting a byte stream into
`messages.s`: tile bytes (glyph, or `$00` for space) plus control codes
`$FE` newline, `$FD` page break, `$FF` end. `msg_table` indexes them by `MSG_*`.

Runtime: `SetMessage(id)` points `msg_ptr` at a stream; the box opens (shell =
frame + blank interior), then `GS_TEXT` calls `RenderLine` once per frame —
each builds a 30-tile VRAM packet for interior line `cur_line` (nametable row
`22+L`) and reads `term_action` from the ending control. On a page break it
shows the `▼` prompt (`DrawPrompt`) and waits for A in `GS_TEXTWAIT`; on end it
waits for A then closes. Dynamic text (e.g. damage) is composed into `msg_buf`
in RAM (`CopyFrag` + `AppendNumber` → `DIGIT_TILE`) and rendered the same way.

-----

## Entities (struct-of-arrays, `BSS`, indexed by X)

`ent_gx, ent_gy` (16px grid cell) · `ent_px, ent_py` (sprite pixel pos) ·
`ent_dir` · `ent_state` (IDLE/MOVE) · `ent_timer` (pixels left in a slide).
Index 0 = hero (only one used so far; arrays sized `MAX_ENT`=8). Hero entity data
is preserved across battle, so `ExitBattle` returns it to the prior position.

## World, camera & scrolling (2×2 four-screen world)

The world is **16px metatiles**, `WORLD_W`×`WORLD_H` = 32×30 = **2×2 screens**
(512×480 px), wrapping on both axes (a torus). Each metatile is four 8px CHR
tiles (TL,TR,BL,BR); terrain is the old 8px art **pixel-doubled** by the
generator. The iNES header uses **vertical mirroring**, so the two physical
nametables sit side-by-side (512×240 resident): **horizontal scroll is free**
(both screens always present), but the world's lower half doesn't fit, so the
**vertical axis is row-streamed**.

**Camera** (`UpdateCamera`, every frame) keeps the hero at a fixed screen
position (128,112); the world scrolls beneath it (Dragon-Quest style):
- `camX = heroWorldX − 128 (mod 512)` → `camX_lo` (PPUSCROLL X) + `camX_hi`
  (PPUCTRL base-nametable bit 0).
- `camY = heroWorldY − 112 (mod 480)` → `scrollY = camY mod 240` (PPUSCROLL Y) +
  `cam_my = camY/16` (the camera's metatile row, for the streamer).
NMI writes the scroll after the VBUF flush and row-stream writes.

**Row streaming** (`StreamRows` → `BuildStream`, flushed in NMI) is done at **8px
tile-row granularity**, not 16px. The nametable is exactly 30 tile-rows = the
screen height, so world tile-row T lives in slot `T % 30` and the only wrap-seam
is a ≤7px sliver that stays inside the top/bottom overscan. (Streaming whole
16px metatile-rows instead pushed that seam to ~14px, which flashed on-screen
while scrolling up — the tile-granularity update fixes it.) On each 8px crossing
(`cam_ty = camY/8` changes) the incoming tile-row is written as four strips: the
LEFT and RIGHT 32-tile strips (straight from `worldtiles`) and the two attribute
byte-rows. All four fit easily in one vblank, ready the frame they appear.
Attributes use RAM **shadows** (`attr_shadow_l/_r`): one metatile == one attr
quadrant, so an attr byte mixes two metatile rows (even row → low nibble, odd →
high), read-modify-written from `attr_pair_l/_r` (`MergeAttrRow`). `DrawField`
(boot, rendering off) paints world rows 0–29 into both nametables and seeds the
shadows; the hero starts so `cam_ty = 0` to match.

## Movement & collision

Grid is 16px cells = one metatile each (32×30). `TryStep` picks the target cell,
**wrapping at the edges** (`WORLD_W`/`WORLD_H`), and slides if it isn't solid.
Collision is a single lookup: `CellSolid` reads `worldsolid[gy*WORLD_W + gx]`
(1 = solid: wall/water/tree/NPC).

`StepMove` is **direction-based**, `MOVE_SPEED`(2) px/frame in `ent_dir`. World X
is 16-bit (`ent_px`/`ent_pxh`), wrapping mod 512; world Y is 16-bit
(`ent_py`/`ent_pyh`), wrapping mod 480. After 16px it snaps the grid cell from the
world position (`gx = (pxh<<4)|(px>>4)`, `gy = (pyh<<4)|(py>>4)`).

### Text boxes drawn in place over the scrolling map (Dragon-Quest style)

The text box / command menu / NPC dialogue are drawn **directly into the
scrolled nametables, in place over the map, and the map is restored underneath
on close** — no layout swap, no rendering-off, **no flash**. This is the
window technique real NES RPGs (Dragon Warrior / Final Fantasy) use, and it's
the convention for every box in the full game. The box is a full-width, 8-row
window at screen rows 20-27.

- **Geometry** (`ComputeBoxGeom`, on open): the hero is grid-aligned when a box
  opens, so the camera is on a 16px boundary (the view is metatile-aligned —
  this is what keeps attributes clean). Field box top = nametable row
  `(cam_ty+20) mod 30`, left edge = `camX/8`. Battle box = fixed row 20, col 0
  (the battle screen is held at scroll 0,0).
- **Seam split** (`SplitRange`): the box spans the full screen width, so each row
  straddles the two side-by-side nametables. Every row write is split into 1-2
  contiguous segments (`PutSeg` → the NMI stream descriptors). For the battle box
  (`box_cstart = 0`) the split collapses to a single NT0 write at `$22xx`, so the
  same code serves both.
- **Animation** (`DrawStep`, 9 steps, black-intermediate): 4 steps clear the box
  rows to tile $00, 1 step sets attributes, 4 steps draw content — so no tile is
  ever shown under a mismatched palette. `draw_mode` 0 = open (window shell from
  `winmap`), 1 = close (restore the map from `worldtiles`). `QueueBoxTileRow`
  picks the per-row source by `bx_phase`.
- **Attributes** (`DrawBoxAttr` + `MergeAttrRow` with `attr_force`): the box's 4
  metatile-rows are folded into the attribute shadow **per metatile-row nibble**
  (palette 3 on open, the map's palette on close), then the affected attribute
  rows are written from the shadow. Because each metatile-row is a separate
  nibble, neighbouring map rows in the same attribute byte keep their colour —
  **no palette bleed at the box edges**, at any scroll position.
- Text/prompt updates (`RenderLine`, `DrawPrompt`) render into `linebuf` and use
  the same seam split, so they also land at the correct scrolled addresses.

`box_open` freezes `StreamRows` while a field box is up (battle uses `in_battle`),
and both opens clear `stream_req`, so a queued field row-stream can never bleed
onto the box.

**Battle** is still a full-screen scene: `EnterBattle` sets `in_battle` (NMI
holds scroll 0,0), and `ExitBattle` repaints the field at the hero's position
(camera-aware `DrawField`) and restores the field scroll.

-----

## Palettes (`pal_field`, `pal_battle`)

4 BG + 4 sprite sub-palettes each. Field: 0 ground, 1 water, 2 NPC, 3 window.
Battle: backdrop blue ($11), 1 = enemy. **Every sub-palette's color-0 entry must
equal the backdrop** because of the $3F1x→$3F0x mirror (see CLAUDE.md trap).

-----

## Asset pipeline (`tools/gen_assets.py`)

Hand-authored art (digit grids for tiles, `'#'/'.'` for glyphs, 16x16 blocks
doubled to 32x32 for the enemy) → encodes 2bpp planar CHR + the world tilemaps,
attribute tables, collision map, window shell, and text byte-streams → writes
`src/chr.s`, `src/field.s`, `src/tiles.inc`, `src/messages.s`. Edit art there,
re-run, commit the generated files. The `make` build stays pure ca65/ld65.

### Adding content (the only entry points)
All content flows through `tools/gen_assets.py`; never hand-edit `src/*.s` /
`src/tiles.inc`. After any change: `python3 tools/gen_assets.py && make`.

| To… | Edit in `gen_assets.py` |
|------|--------------------------|
| add / change a terrain tile | `TILES{}` (8×8 digit art; doubled into a 16×16 metatile) |
| recolor                      | the palette tables (`pal_field` / `pal_battle` in `main.s`) + `cell_pal` |
| change the map               | the `world[][]` build (terrain + `SOLID` set) |
| place / face the NPC         | `NPC_GX`, `NPC_GY`, `NPC_FACING` |
| add a character facing set   | `HERO_VIEWS` / `NPC_VIEWS` (down/up/side; left is mirrored) |
| add / change a monster       | `ENEMY16` (16×16, doubled to 32×32) |
| edit / add dialogue          | `MESSAGES[]` (auto word-wrapped; `\f` = page break) |
| add a composed-text fragment | `FRAGMENTS[]` (for runtime numbers/labels) |

-----

## Where the engine phase plugs in (not built yet — see CLAUDE.md order)

- CHR-RAM streaming replaces the fixed CHR-ROM (`chr.s`); tile indices become
  per-tileset, font/UI stay resident.
- UxROM banking: PRG split; the split loop, VBUF, and state machine are unchanged.
- Real data formats replace the hardcoded NPC line, `winmap`, and enemy.
- A real battle system replaces `GS_BATTLE`/`ENEMYDIE`/`BATTLEWAIT`.
- Save model (password vs battery) — decide before the engine phase.
