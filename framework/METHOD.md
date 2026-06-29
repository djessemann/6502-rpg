# Method — how to work

## Build order (don't skip ahead)
1. **Slice.** Simplest mapper (NROM). One screen, one hero, one NPC, one stub
   encounter. Prove the bones feel right and a clean `.nes` builds on the
   toolchain. This is throwaway-grade, but it must obey `HARDWARE.md`.
2. **Engine.** Migrate to the target mapper (PRG banking + CHR streaming if
   needed); add the real data-format interpreters. Decide the save model first.
3. **Content.** Pour in tilesets, monsters, maps, and text through the formats.

Do not start a later phase — not even scaffolding — until the current one is
verified.

## Scope discipline
- Build only what the current phase calls for, in order, **one step at a time**.
- One step → one runnable `.nes` → verify → next. **Never bundle steps.**
- Out-of-scope ideas: one line under a `## Parking lot` heading. No action.
- If a request seems to need out-of-scope work, **stop and ask** rather than
  expanding scope yourself.

## Verify every step before moving on
- Build with `make` → one `.nes` per milestone. Commit per verified milestone.
- Eyeball in an accurate emulator (FCEUX for debugging, Mesen for accuracy).
- **Headless self-check.** Drive a scriptable emulator (e.g. `pyntendo`):
  script the controller, capture frames, diff them. Confirm the step
  pixel-for-pixel before handing the ROM over — e.g. "field after closing the
  menu == the frame before opening it." This catches glitches a glance misses.

## Toolchain
- Assembler/linker: **ca65 / ld65** (cc65 suite), Makefile-driven. The build is
  pure assembler — no other tools in the `make` path.
- **Assets: a dev-time generator (Python) owns all art/data** and emits
  *committed* source (`.s`/`.inc`): CHR tiles, maps, palettes, attribute data,
  text byte-streams. Edit art there, re-run, commit the generated files.
- Build artifacts (`*.nes`/`*.o`/`*.dbg`) are git-ignored. **Commit source only.
  Never hand-edit a generated file.**

## Doc discipline
- rule → `HARDWARE.md`; mechanism → `PATTERNS.md`/`ARCHITECTURE.md`; scope →
  `PROJECT.md`.
- State the current truth, not "we tried X then Y."
- Name the function; don't paste its code into the doc.
- Update the doc in the same commit as the behavior it describes.
