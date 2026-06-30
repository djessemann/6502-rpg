# Project: [Game Title] — NES RPG (6502 assembly)

A short, simple-mechanics NES RPG whose hook is **visual variety and
personality** — many characters, tilesets, and background-rendered enemies. The
art ambition is the spec; the mechanics are deliberately minimal.

This file is the binding contract. Follow it in every session and every file.
The active phase and its scope live in the **Current phase** section below.

## Documentation map
- **CLAUDE.md** (this file) — binding contract for *this* project: scope
  discipline, the active phase + scope, this game's choices, the hardware rules.
- **framework/** — the portable, project-agnostic distillation (method,
  hardware contract, engine patterns, a `PROJECT` template). Canonical and
  shareable; copy it to bootstrap a new NES RPG. The rules here mirror
  `framework/HARDWARE.md`.
- **ARCHITECTURE.md** — how *this* engine works now (code map) + how to add
  content. Read before changing a subsystem.

(The slice phase is complete; its old `SLICE.md` spec is retired — its current
truth lives in ARCHITECTURE.md. Each new phase states its scope under **Current
phase**, or in its own phase doc when one is warranted.)

Doc rule: state the current truth (not history); one fact in one place; name
the function instead of duplicating its code; update docs in the commit that
changes the behavior.

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

The scope of the **active phase** (see **Current phase**) is the entire job.
Finishing it cleanly is success; anything beyond it is scope creep, even if easy.
When no phase is active (between phases), do nothing in-engine without a scope.

-----

## Order of operations

**Macro (phases — do not skip ahead):**

1. **Slice (DONE)** — NROM. Proved the bones feel right and a clean `.nes`
   builds. Complete and verified (see **Current phase** / ARCHITECTURE.md).
1. **Engine (NOW / next)** — migrate to MMC3 + battery; add PRG banking, CHR
   bank-switching, and the real data-format interpreters. **Format-first:** define
   and freeze each on-ROM data format (map, tileset, entity, encounter, text,
   stats) — with its generator emitter and its runtime reader — before pouring
   content. (Save model decided: battery.)
1. **Content (later)** — pour in tilesets, monsters, maps, and text via the
   frozen formats.

Do not pull a later phase's work forward — not even scaffolding — until I say
the current phase is verified and we're moving on.

**Micro (within a phase):** follow that phase's numbered build order exactly,
one step → one runnable `.nes` → I verify → next.

-----

## Current phase

**Slice: complete and verified.** Beyond the original slice we also built — at my
direction — a 2×2 scrolling overworld with row streaming and in-place
text/menu/dialogue boxes drawn over the map. See ARCHITECTURE.md.

**Next: Engine phase** (format-first; target MMC3 + battery), starting with the
map data format. Not started yet — the world bible and reference assets are being
authored first.

-----

## Mapper

- **Slice phase: NROM (mapper 0)** — 32KB PRG, 8KB CHR-ROM. Simplest path.
- **Save model: battery SRAM** (decided).
- **Target (engine phase): MMC3 / mapper 4** (decided) — battery save, PRG
  banking, and fine/fast CHR-ROM bank-switching for the visual-variety hook, plus
  a scanline IRQ available for a fixed HUD over the scrolling field. Implemented
  at the engine phase, not now (only the features we use; the IRQ split is opt-in).
- **Output is a `.nes` ROM run in emulators** (FCEUX/Mesen/web) — no physical
  cartridge. MMC3 and battery save (persisted as a `.sav` file) are fully
  emulated; our headless test emulator supports mapper 4, so the verify loop
  carries into the engine phase unchanged.
- The structural rules below are **mapper-independent** and hold on NROM and MMC3
  alike. Banking and CHR bank-switching are added at the engine phase, not now.

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