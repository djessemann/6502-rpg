# SLICE.md — Vertical Slice Spec

> **Status: COMPLETE and verified.** All six build steps below shipped and were
> verified headless. Beyond this spec we then built — by explicit direction — a
> 2×2 scrolling overworld (row streaming) and in-place text/menu/dialogue boxes
> drawn over the map; those are documented in ARCHITECTURE.md. **Next phase:
> Engine** (format-first; MMC3 + battery), starting with the map data format —
> see CLAUDE.md → Order of operations. This file is kept as the slice record /
> reference; the engine phase will get its own scope doc.

> **Scope rule for the agent:** this file is the entire job right now. Build the
> MVP interactions below **in the numbered order, one at a time**, stopping after
> each for verification. Do **not** suggest, offer, or begin anything outside
> this file — no streaming, no real battle system, no extra features, no “while
> I’m here.” Out-of-scope ideas go in a one-line `## Parking lot` note at the end
> and nowhere else. When in doubt, stop and ask instead of expanding scope.

## Why this exists

This slice tests **two separate things**:

1. **Game feel** — does grid movement, text pacing, and the encounter transition
   feel right?
1. **Buildability** — can we produce a clean, testable `.nes` on this toolchain,
   following the CLAUDE.md structural rules?

(2) is the bigger unknown and the bigger reason to do this. A working slice also
becomes a **reference implementation** the real engine extends, plus a known-good
ROM to bisect against later.

**What this slice does NOT prove:** the actual pitch — visual variety — because
that lives entirely in CHR-RAM streaming and many tilesets, which we are
deliberately faking here. A great-feeling slice proves the spine and proves
buildability. It does not validate the concept. Keep those judgments separate.

-----

## Scope (exactly this — nothing more)

- **One screen** field (single nametable, no scrolling).
- **~12 background tiles**, **2 palettes**.
- **Hero**: a metasprite, grid-locked 16px movement in 4 directions.
- **One stationary NPC**: drawn as **background tiles**. Pressing the action
  button while adjacent and facing it opens a text window with **one hardcoded
  line**; press again to close.
- **One encounter**: triggered by a step counter (or a debug button). Fades/cuts
  to a **stub battle**: one enemy, press button to attack → enemy “dies” →
  return to the field at the same spot.

-----

## The boundary that makes this a foundation, not a detour

|Keep REAL (structural — must be correct now)|Fake FOR NOW (additive — bolt on later)               |
|--------------------------------------------|------------------------------------------------------|
|Split game loop (logic main / PPU in NMI)   |CHR-RAM streaming (use one fixed CHR-ROM tileset)     |
|PPU writes only via VRAM buffer in NMI      |Compression / dictionary tokens (raw bytes ok)        |
|Struct-of-arrays entities                   |The §4 data formats (hardcode the NPC line, the enemy)|
|Grid-locked 16px movement                   |Real battle system (stub: attack → win → return)      |
|Stationary NPC as background tiles          |Encounter tables / zones (single hardcoded enemy)     |
|Hero as the only OAM actor                  |Save system, menus, inventory, audio (stub the tick)  |

If it’s in the left column and it’s wrong, the slice has failed even if it looks
fine. If it’s in the right column, do the cheapest thing that works.

-----

## Build order (each step ends in a runnable .nes)

Do these **strictly in order, one at a time.** Each step ends in a ROM I test
before you start the next. Do not begin a later step early, do not pull any
“fake for now” item forward, and do not combine steps.

1. **Boot** — correct init sequence; solid-color screen, no glitches.
1. **Field background** — ~12-tile screen drawn from a small map, 2 palettes.
1. **Hero movement** — grid-locked walk, 4 directions, collision against a couple
   of solid tiles.
1. **NPC + text** — stationary NPC as BG tiles; adjacent + facing + button opens
   a window with one hardcoded line via the VRAM buffer; button closes it.
1. **Encounter trigger** — step counter (or debug button) fires the transition.
1. **Stub battle + return** — show one enemy, button to attack, enemy gone,
   return to field at the prior position.

-----

## Success criterion (observable in emulator)

> Boot the ROM in FCEUX/Mesen. The hero walks the field on a 16px grid and
> stops at solid tiles. Walking into the NPC and pressing the button opens a
> clean text window with one line; pressing again closes it with the field
> intact. After enough steps (or the debug button), the screen transitions to a
> single enemy; pressing the button defeats it and returns to the field at the
> same spot. No visual glitches at any transition.

And, structurally: PPU is only touched in NMI, entities are struct-of-arrays,
and no shortcut in the “Keep REAL” column was taken.

-----

## Toolchain / how I’ll test

- Build: ca65/ld65 via Makefile → `[game].nes`.
- I run it in FCEUX (and Mesen) and report concrete results. For glitches I’ll
  share the nametable viewer / PPU log, not a description.