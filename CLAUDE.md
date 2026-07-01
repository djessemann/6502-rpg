# Project: [Game Title] — NES RPG (6502 assembly)

A short, simple-mechanics NES RPG whose hook is **visual variety and
personality** — many characters, tilesets, and background-rendered enemies. The
art ambition is the spec; the mechanics are deliberately minimal.

This file is the binding contract. Follow it in every session and every file.
The active phase and its scope live in the **Current phase** section below.

## Documentation map
- **CLAUDE.md** (this file) — binding contract for *this* project: scope
  discipline, the active phase + scope, this game's choices. The hardware rules
  are **imported** from `framework/HARDWARE.md` below (one copy, no mirror).
- **framework/** — the portable, project-agnostic distillation (method,
  hardware contract, engine patterns, a `PROJECT` template). Canonical and
  shareable; copy it to bootstrap a new NES RPG.
- **ARCHITECTURE.md** — how *this* engine works now (code map) + how to add
  content. Read before changing a subsystem.
- **design/** — this game's creative source material, authored by the designer:
  the game-bible workbook (story, cast, stats, gear, locations, music, art
  sets), `design/MECHANICS.md` (the closed mechanics list the engine's data
  formats freeze against), and script/art/music references. `design/README.md`
  says what goes where. Design truth lives here; the engine only ever reads
  data generated from it.

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
   stats, music/SFX) — with its generator emitter and its runtime reader — before
   pouring content. (Save model decided: battery.) Also in this phase, as their
   own steps: prove the headless emulator on a minimal MMC3 ROM (and `.sav`
   persistence) *before* building on it; fix the **ROM/content budget** (PRG/CHR
   sizes → how many tilesets, monsters, maps, and pages of text fit) *before*
   content is mass-authored; and integrate the **sound driver** (see **Audio**).
1. **Content (later)** — pour in tilesets, monsters, maps, text, and music via
   the frozen formats.

Do not pull a later phase's work forward — not even scaffolding — until I say
the current phase is verified and we're moving on.

**Micro (within a phase):** follow that phase's numbered build order exactly,
one step → one runnable `.nes` → I verify → next.

-----

## Current phase

**Slice: complete and verified.** Beyond the original slice we also built — at my
direction — a 2×2 scrolling overworld with row streaming and in-place
text/menu/dialogue boxes drawn over the map. See ARCHITECTURE.md.

**Now: design authoring (between phases — no engine work).** The game bible,
mechanics decisions, script, and reference assets are being authored into
`design/` (see `design/README.md`). The gate to the engine phase is a **small
reference slice of real content** (one region's tileset, a few characters, a
couple of monsters, a short script, a small stats table) plus a filled-in
`design/MECHANICS.md` — formats are frozen against real examples, never guesses.

**Next: Engine phase** (format-first; target MMC3 + battery). Its numbered step
list is written when the phase starts. Already fixed: step 0 proves the headless
emulator on a minimal MMC3 ROM + `.sav` persistence; an early step sets the
ROM/content budget; the first data format is the **map format**; and no format
freezes until `design/MECHANICS.md` covers the decisions it encodes.

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
  emulated. The headless test emulator reportedly supports mapper 4 — engine
  phase **step 0 proves it** (minimal MMC3 ROM + `.sav` persistence through
  the headless loop) before anything is built on top of that assumption.
- The structural rules below are **mapper-independent** and hold on NROM and MMC3
  alike. Banking and CHR bank-switching are added at the engine phase, not now.

-----

## Audio (decided at doc level; built in the engine phase)

- **Driver: integrate a proven sound engine, don't write one.** Default choice:
  the **FamiStudio Sound Engine** (ca65-compatible; its music is authored in the
  free FamiStudio desktop app, which is designer-friendly). famitone2 is the
  lighter fallback. Confirm the pick when the engine-phase audio step starts.
- **Authoring:** music and SFX are composed in FamiStudio and exported as data
  the build assembles — same rule as art: generated source is committed, never
  hand-edited.
- The per-frame tick call site already exists (`SoundTick`, currently a stub,
  called from NMI every frame including lag frames).
- **Lands in the engine phase** as its own step: driver + one test song + one
  test SFX. The real soundtrack is content-phase material.

-----

## Structural rules & known traps (NON-NEGOTIABLE, active now)

The full hardware contract — structural rules and known traps — is imported
from the framework so it exists in exactly one place:

@framework/HARDWARE.md

This game's concrete parameters for those rules (RAM map, VRAM buffer at
$0300–$03FF with a ≈160 bytes/frame budget, shadow OAM at $0200, the 16px
grid) live in **ARCHITECTURE.md** with the code that implements them.

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
- **Claude verifies first, with evidence.** Before handing over a ROM, and on
  any reported failure, Claude drives the headless emulator itself — script the
  inputs, capture and diff frames — and shows me the screenshots. I eyeball
  results; I am not the debugger. Only when automation can't see the problem do
  I open FCEUX, and then Claude tells me exactly what to capture (which viewer,
  which moment).
- Do not advance past an unverified ROM. Do not bundle multiple subsystems into
  one step.
- Stay inside the current scope (see **Scope discipline** above). Out-of-scope
  ideas go in a one-line `## Parking lot` note at the end, never into the build.