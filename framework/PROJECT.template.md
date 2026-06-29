# Project: [TITLE]

The hook: [one line — what makes this game distinct, e.g. "visual variety and
personality: many characters, tilesets, background-rendered enemies"].

This file holds the per-game choices and the current scope. The binding rules
live in `framework/HARDWARE.md`; how to work in `framework/METHOD.md`; engine
recipes in `framework/PATTERNS.md`; the realized code map in `ARCHITECTURE.md`.

## Choices
- **Mapper.** Slice: NROM (mapper 0). Target: [UxROM+CHR-RAM / MMC1 / MMC3 …]
  and why (PRG banking? CHR streaming for visual variety? battery save?).
- **Save model.** [password | battery SRAM]. (Battery ⇒ MMC1/MMC3.)
- **Mechanics.** [deliberately minimal — list them; everything else is content].

## Current phase
[Slice | Engine | Content]

## Current scope — the entire job right now
[The numbered build steps for this phase, in order. One step → one runnable
`.nes` → verify → next. Finishing these cleanly is success; anything beyond is
scope creep.]

1. …
2. …

## Parking lot
[one-line out-of-scope ideas; recorded, not acted on]
