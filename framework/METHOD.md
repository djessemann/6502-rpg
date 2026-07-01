# Method — how to work

## Build order (don't skip ahead)
1. **Slice.** Simplest mapper (NROM). One screen, one hero, one NPC, one stub
   encounter. Prove the bones feel right and a clean `.nes` builds on the
   toolchain. This is throwaway-grade, but it must obey `HARDWARE.md`.
2. **Engine.** Decide the save model (it gates the mapper), then migrate to the
   target mapper (PRG banking + CHR bank-switching/streaming). **Step 0: prove
   the verify loop on the target mapper** — a minimal ROM through the headless
   emulator, plus save persistence if battery — before building on it. **Early:
   fix the ROM/content budget** (PRG/CHR sizes → how many tilesets, monsters,
   maps, and pages of text fit) so content is authored to guardrails, not hopes.
   Then **format-first:** define and *freeze* each on-ROM data format — map,
   tileset, entity, encounter, text, stats, music/SFX — with its generator
   emitter and its runtime reader, proven on the smallest real content, before
   any of it is mass-authored. Changing a format after content exists is the
   expensive mistake this order avoids. Integrate the sound driver here as its
   own step (an existing engine — see `PATTERNS.md` → Audio; the per-frame tick
   call site exists from the slice).
3. **Content.** Pour in tilesets, monsters, maps, text, and music through the
   frozen formats. (Authoring assets can start during phase 2 — see `ASSETS.md`.)

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
  (Check the headless emulator supports your target mapper before relying on it.)
- **The builder gathers the evidence.** On a reported failure, whoever builds
  (person or agent) reproduces it in the headless emulator first — scripted
  input, captured frames — rather than asking the verifier for debugger output.
  Manual debugger captures (nametable viewer, CPU/PPU log) are the fallback,
  with precise instructions on what to capture.
- **Grow a regression suite.** As features/content accumulate, promote those
  one-off headless checks into a committed `tests/` of scripted scenarios +
  golden frames, run each milestone. It's the cheapest insurance against a
  growing ROM silently regressing.

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
