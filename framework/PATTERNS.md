# Engine patterns

Reusable recipes. Each: **what it's for → the approach → the invariant to keep.**
Described portably here; a concrete implementation lives in the project's
`ARCHITECTURE.md` and source.

## Split loop
Main thread: read input → clear VRAM buffer → update game → build OAM → wait for
NMI. NMI: OAM DMA → flush VRAM buffer → set scroll → sound tick → bump a frame
counter. Main spins on the counter. *Invariant: game logic never writes the PPU.*

## Asset pipeline
A generator (Python) owns all art/data and emits committed `.s`/`.inc`: CHR
tiles, maps, palettes, attribute data, and text as a byte stream. The build only
assembles. *Invariant: one source of truth; never hand-edit generated files.*

## Scrolling overworld
Use **metatiles** (e.g. 16×16 = 2×2 hardware tiles) so a screen is few enough
cells to redraw cheaply. Camera centers on the hero (hero fixed on screen, world
scrolls). With vertical mirroring the two nametables sit side-by-side, so
horizontal scroll is free and the **vertical** axis is row-streamed: each time
the camera crosses a tile-row, write the incoming row into the nametable slot the
outgoing row vacated (`slot = worldRow mod screenRows`). *Invariants: stream at
8px tile granularity (seam stays in overscan); store camera/world position at the
width the world needs (16-bit once it exceeds 255px).*

## Entities
Struct-of-arrays indexed by X: grid cell + pixel position + dir + state + a slide
timer. Idle: pick a target cell (wrap or block on collision), start a slide,
**committing the cell at slide start** — and treat a slider's origin cell as
occupied until it lands — so two walkers can never stack or pass through each
other. Slide: move N px/frame; re-derive the cell on arrival. *Invariants: only
moving actors are sprites; stationary NPCs are background tiles. Shared movement
code carries no player-only side effects — gate encounter counting and
interaction triggers on the player's entity index, or a wandering NPC triggers
random battles by itself.*

## Text engine
Author messages as plain strings; the generator word-wraps + paginates and emits
a byte stream of tile ids + control codes (newline / page-break / end). Runtime
renders one line per frame into the box. Dynamic text (numbers, names) is composed
into a RAM buffer from `$FF`-terminated fragments and rendered the same way.

## Menus
A menu *is* a composed message: option lines with a cursor glyph built into the
text buffer, rendered through the text path. A small cursor-input state handles
up/down/confirm/cancel. *Reuse this one primitive for commands, items, shops.*

## In-place UI boxes (menus / dialogue over a scrolling map)
The technique real NES RPGs use. Draw the box **directly into the scrolled
nametables, over the map**, and restore the map underneath on close — no layout
swap, no rendering-off, no flash.
- Open a box only when the hero is **grid-aligned**, so the camera is on a tile
  boundary and the box aligns to tiles/metatiles.
- The box spans the screen width, so each row straddles both nametables: split
  each row write at the seam into 1–2 contiguous runs.
- Animate with the **black-intermediate** (clear region to `$00` → set attribute
  → draw content) so no tile flashes under the wrong palette.
- Set the box's attributes **per metatile-row nibble** via a RAM attribute
  shadow, so neighboring map rows in the same attribute byte keep their color.
- On close, redraw the map tiles under the box from world data. Freeze
  scrolling/streaming while a box is open.
*Invariant: never blank the screen to show a box.*

## Battle / scene change
A full-screen scene (battle) is the exception to "draw in place": swap it in with
rendering and NMI disabled, hold scroll at (0,0) while it's up, and on exit
repaint the field for the current camera before re-enabling. A brief cut-to-black
on a scene change is acceptable; a black flash on a *menu* is not.

## Data formats (engine phase)
Past the slice, content must be *data the ROM reads*, not hand-written code. For
each kind of content — map, tileset/CHR bank, entity/NPC, encounter, text, stats
— define a compact binary format, write the generator **emitter** (authoring →
bytes) and the runtime **reader** (bytes → behavior), prove it on the smallest
real example, then **freeze it** before authoring at volume. *Invariant: decide
the format first; changing it after content exists is rework across all content.*
Banking note: with CHR-ROM bank-switching, "show a new tileset" = point at a
different bank (no copy); with CHR-RAM, stream tiles in within the vblank budget.

## Save model
Decide before the engine phase: password vs battery SRAM. Battery ⇒ a mapper with
battery-backed RAM (MMC1/MMC3) and a "battery" flag in the ROM header; emulators
persist it as a save file. This drives mapper choice. (MMC3 = mapper 4: fast CHR
bank-switching + a scanline IRQ for a fixed HUD; MMC1 = simpler, classic, pairs
with editable CHR-RAM.)
