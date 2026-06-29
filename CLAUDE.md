# Project: [Game Title] — NES RPG (6502 assembly)

A short, simple-mechanics NES RPG whose hook is **visual variety and
personality** — many characters, tilesets, and background-rendered enemies. The
art ambition is the spec; the mechanics are deliberately minimal.

This file is the binding contract. Follow it in every session and every file.
For the current task scope, see **SLICE.md**.

-----

## Scope discipline (READ FIRST — applies to every response)

Build **only** what the current phase calls for, **in the defined order, one
step at a time**, and stop for me to verify before the next step.

- **Do not suggest, offer, recommend, or begin anything outside the current
  scope.** No “while I’m here,” no “I also went ahead and…”, no starting the
  next phase or pulling a later feature forward.
- **Do not bundle steps.** One step → one runnable `.nes` → I verify → next step.
- **Default to silence on out-of-scope ideas.** The only permitted channel is a
  single-line note under a `## Parking lot` heading at the very end of a
  response — record it in one line, take no action, do not elaborate or pitch.
  If you have nothing to park, omit the heading.
- If a request seems to need out-of-scope work, **stop and ask** rather than
  expanding scope on your own.

The MVP interactions in SLICE.md are the entire job right now. Finishing them
cleanly is success. Anything beyond them is scope creep, even if it’s easy.

-----

## Order of operations

**Macro (phases — do not skip ahead):**

1. **Slice (NOW)** — NROM. Prove the bones feel right and a clean `.nes` builds.
   Scope = SLICE.md.
1. **Engine (later)** — migrate to UxROM + CHR-RAM; add banking, CHR-RAM
   streaming, and the real data-format interpreters. Decide the save model first.
1. **Content (later)** — pour in tilesets, monsters, and text via the formats.

Do not touch phase 2 or 3 work — not even scaffolding for it — until I say the
slice is verified and we’re moving on.

**Micro (within the slice):** follow the numbered build order in SLICE.md
exactly, pausing after each for verification.

-----

## Current phase

**Vertical slice** (see SLICE.md). Building one screen + hero + one NPC + one
stub encounter to prove the bones feel right and that a clean `.nes` builds on
this toolchain. Not the real engine yet.

-----

## Mapper

- **Slice phase: NROM (mapper 0)** — 32KB PRG, 8KB CHR-ROM. Simplest path.
- **Target (later): UxROM + CHR-RAM** — PRG banking + tiles streamed from PRG
  into CHR-RAM for visual variety.
- The structural rules below are **mapper-independent** and must hold on both.
  Banking and CHR-RAM streaming are added at the engine phase, not now.
- Save model (decide before the engine phase): [ password | battery SRAM ].
  Battery ⇒ migrate to MMC1/MMC3.

-----

## Structural rules (NON-NEGOTIABLE, active now)

These are cheap to honor now and agony to retrofit. They hold even in throwaway
prototypes.

1. **Split game loop.** Game logic runs in the main thread. All PPU updates
   happen in the **NMI handler**. A sound/music tick is called every frame,
   including lag frames (may be a stub for the slice, but the call site exists).
1. **PPU discipline.** NEVER write $2005/$2006/$2007 outside vblank. All
   nametable/palette changes go into a **RAM VRAM buffer** ($0300–$03FF) and are
   flushed in NMI only. Budget ≈160 bytes/frame. Always reset scroll after any
   $2006 write.
1. **OAM.** Shadow OAM at $0200; OAM DMA every frame in NMI.
1. **Entities are struct-of-arrays.** Parallel arrays indexed by X
   (`x[], y[], dir[], state[], …`). Never array-of-structs.
1. **Grid-locked movement.** 16px steps. No sub-tile scrolling. Redraw a
   row/column per camera step.
1. **Sprites are scarce.** 8-per-scanline hardware limit. Stationary NPCs are
   **background tiles**, not sprites. Only moving actors (the hero, and later a
   wandering NPC) consume OAM.
1. **Resident core tiles.** Font, window borders, hero, UI icons stay resident
   and are never swapped. (Slice has one fixed tileset, so this is automatic
   now; the rule matters once streaming exists.)
1. **Stack discipline.** 256-byte stack. No deep call chains. Use jump tables /
   the RTS trick for state dispatch.

### Known traps (avoid by construction)

- PPU writes during rendering → glitches. (Buffer + NMI flush.)
- Too many hardware sprites on one line → flicker. (NPCs as BG.)
- Forgetting to restore scroll after a $2006 write.
- Exceeding the vblank byte budget in one frame.
- **Palette mirror.** $3F10/$3F14/$3F18/$3F1C mirror $3F00/$3F04/$3F08/$3F0C.
  When you write all 32 palette bytes, the sprite-palette "color 0" entries land
  on the BG backdrop slots — so they must hold the *same* value as the backdrop,
  or they silently overwrite it. (This caused a black battle screen: the backdrop
  was set to blue but a sprite-palette[0] of $0F clobbered it back to black.)
- **Vblank budget.** NTSC vblank ≈ **2273 CPU cycles** (20 scanlines). OAM DMA
  burns ~513, leaving ~1700; a naive `lda buf,y / sta $2007 / iny / dex / bne`
  flush is ~15 cyc/byte → **~100+ tiles/frame** are safe, so the "≈160
  bytes/frame" figure is realistic. (Don't confuse vblank length with the ~757
  figure — that's wrong.) Still spread *very* large updates across frames, but
  64 tiles/frame is comfortable.
- **Palette change during a multi-frame nametable update flashes.** If you
  redraw a region's tiles over several frames AND change its attribute (palette)
  separately, there's a window where tiles render under the wrong palette (the
  text box flashed green opening / white closing). Fix: route the transition
  through **all-black** — clear the region to tile $00 (value 0 is
  palette-independent), THEN switch the attribute, THEN draw the real content.
  No tile is ever shown under a mismatched palette.
- **Full-screen redraws** (field↔battle): you cannot do these in one vblank, so
  do them with rendering AND NMI disabled (the same safe window as boot): blank
  PPUMASK/PPUCTRL, write VRAM freely, reset scroll, re-enable. Push hidden/updated
  OAM via a manual DMA before re-enabling so stale sprites don't flash.

-----

## Toolchain

- Assembler/linker: **ca65 / ld65** (cc65 suite). Makefile-driven.
  Install on a fresh box with `apt-get install cc65`. Build with `make`
  (output `6502rpg.nes`); art is regenerated with `python3 tools/gen_assets.py`.
- Test in **FCEUX** (debugger, nametable/PPU viewers) and **Mesen** (accuracy).
- **Headless self-check:** `pip install pyntendo` gives an emulator you can drive
  from Python — `NES('6502rpg.nes').run_frame_headless(controller1_state=[...])`
  returns the frame as a numpy array. Script the controller, save PNGs, and diff
  frames to verify a step before handing the ROM over (e.g. confirm "return to
  field" is pixel-identical to the pre-encounter frame). Button order:
  `[A, B, Select, Start, Up, Down, Left, Right]`.
- One runnable `.nes` per milestone. Commit per verified milestone.
- Build artifacts (`*.nes`, `*.o`, `*.dbg`) are git-ignored; commit source only.

See **ARCHITECTURE.md** for the implemented slice's code map (memory layout,
state machine, VRAM-buffer format, asset pipeline).

-----

## How we work

- One milestone/subsystem per session. State the success criterion in the prompt.
- On failure, I provide concrete debugger output (nametable viewer, CPU/PPU log,
  screenshot) — not symptom descriptions.
- Do not advance past an unverified ROM. Do not bundle multiple subsystems into
  one step.
- Stay inside the current scope (see **Scope discipline** above). Out-of-scope
  ideas go in a one-line `## Parking lot` note at the end, never into the build.