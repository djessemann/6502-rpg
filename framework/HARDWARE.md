# Hardware contract (NES / 6502)

Binding on every change. **Mapper-independent** — holds on NROM and on a banked
target alike. Cheap to honor up front, agony to retrofit.

## Structural rules
1. **Split game loop.** Game logic in the main thread; **all** PPU updates in the
   NMI handler. A sound/music tick is called every frame, including lag frames.
2. **PPU discipline.** Touch `$2005/$2006/$2007` only during vblank (NMI) or with
   rendering disabled. Per-frame nametable/palette changes go through a RAM VRAM
   buffer flushed in NMI. **Always reset scroll after a `$2006` write.**
3. **OAM.** Shadow OAM in RAM; OAM DMA every frame in NMI.
4. **Entities are struct-of-arrays.** Parallel arrays indexed by entity number
   (`x[]`, `y[]`, `dir[]`, `state[]`…). Never array-of-structs.
5. **Grid-locked movement.** Whole-tile steps; redraw a row/column per camera
   step. Keep sub-tile bookkeeping out of game logic.
6. **Sprites are scarce.** 8-per-scanline hardware limit. Stationary actors are
   **background tiles**, not sprites. Only moving actors consume OAM.
7. **Resident core tiles.** Font, window borders, hero, UI icons stay resident
   and are never swapped (matters once CHR streaming exists).
8. **Stack discipline.** 256-byte stack. No deep call chains; use jump tables /
   the RTS trick for state dispatch.

## Known traps (avoid by construction)
- **PPU writes during rendering** → glitches. Buffer and flush in NMI.
- **Too many sprites on one line** → flicker. Keep NPCs as background tiles.
- **Forgetting to restore scroll** after a `$2006` write → the screen shifts.
- **Vblank budget** ≈ 2273 CPU cycles (NTSC, ~20 scanlines). OAM DMA burns ~513,
  leaving ~1700 → ~100 tiles/frame is safe. Spread very large updates over
  frames; do full-screen redraws with rendering OFF.
- **Palette mirror.** `$3F10/$14/$18/$1C` mirror `$3F00/$04/$08/$0C`. A
  sprite-palette color-0 entry must equal the backdrop or it overwrites it
  (classic cause of a screen going unexpectedly black).
- **Palette change during a multi-frame tile update flashes.** Route transitions
  through all-black: clear the region to tile `$00` (palette-independent), THEN
  change the attribute, THEN draw the real content.
- **Two nametables only.** A world larger than the resident area (512×240 with
  vertical mirroring, 256×480 with horizontal) needs **runtime row/column
  streaming** as the camera crosses tile boundaries; the wrap seam lives in the
  top/bottom (or left/right) overscan. Stream at 8px granularity so the seam
  stays ≤7px. Attributes are coarse (one byte per 32×32px / 2×2 metatiles) —
  update them **per metatile-row nibble** so neighbors don't bleed color.
- **Full-screen redraws** (e.g. field↔battle) can't fit one vblank: do them with
  rendering AND NMI disabled, reset scroll, push OAM, then re-enable.
- **Never blank the screen to show UI.** Draw menus/text boxes **in place** over
  the scene and restore underneath on close (see `PATTERNS.md`). A rendering-off
  repaint for a box is a visible black flash on every open/close.
- **Player-only side effects in shared entity code.** Movement/slide routines
  serve every walker; gate anything player-only (encounter step counting,
  interaction triggers) on the player's entity index — unguarded, the first
  wandering NPC triggers random battles by itself.
