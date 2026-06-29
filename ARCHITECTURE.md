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
| `src/field.s`         | **Generated.** `fieldmap`, `fieldattr`, `winmap` (exported).  |
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

Pattern table 0 (background, `$0000`):

```
$00         blank
$01-$07     grass, flower, path, tree, wall, bush, water
$08-$17     NPC, 4 facings x 2x2 (down,up,left,right; palette 2)
$18-$20     window frame (TL,T,TR,L,FILL,R,BL,B,BR)
$21-$27     font glyphs (! E H L O R T — only what "HELLO THERE!" needs)
$28-$37     enemy (4x4 = 32x32, palette 1 in battle)
```

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
```

`msg_context` (FIELD/BATTLE) decides where `GS_TEXT` goes when a message ends:
FIELD→`GS_DIALOG`, BATTLE→`GS_BWAIT`. The hero is hidden whenever `in_battle` is
set (the whole battle screen), drawn otherwise (field, including dialogue).

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

## Movement & collision

Grid is 16px cells; the map is 8px tiles. A move commits the target cell, then
`StepMove` slides the sprite `MOVE_SPEED`(2)px/frame for 8 frames. A cell is
solid if **any** of its four underlying 8px tiles is solid (tree/wall/water/NPC)
— so 1-tile-thick borders block correctly. `CellSolid`→`CheckTile`→`MapTile`.

-----

## Palettes (`pal_field`, `pal_battle`)

4 BG + 4 sprite sub-palettes each. Field: 0 ground, 1 water, 2 NPC, 3 window.
Battle: backdrop blue ($11), 1 = enemy. **Every sub-palette's color-0 entry must
equal the backdrop** because of the $3F1x→$3F0x mirror (see CLAUDE.md trap).

-----

## Asset pipeline (`tools/gen_assets.py`)

Hand-authored art (digit grids for tiles, `'#'/'.'` for glyphs, 16x16 blocks
doubled to 32x32 for the enemy) → encodes 2bpp planar CHR + the field/window
tilemaps and a palette-aware attribute table → writes `src/chr.s` and
`src/field.s`. Edit art there, re-run, commit the generated `.s`. The `make`
build stays pure ca65/ld65 (no Python dependency).

-----

## Where the engine phase plugs in (not built yet — see CLAUDE.md order)

- CHR-RAM streaming replaces the fixed CHR-ROM (`chr.s`); tile indices become
  per-tileset, font/UI stay resident.
- UxROM banking: PRG split; the split loop, VBUF, and state machine are unchanged.
- Real data formats replace the hardcoded NPC line, `winmap`, and enemy.
- A real battle system replaces `GS_BATTLE`/`ENEMYDIE`/`BATTLEWAIT`.
- Save model (password vs battery) — decide before the engine phase.
