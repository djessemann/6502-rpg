# Authoring content & assets

For whoever creates the concept, art, maps, script, and stats. The NES has hard
limits; designing within them from the start avoids redrawing everything later.
None of this depends on the mapper or the engine internals.

## Design within the NES canvas
- **Everything is a grid of 8×8 tiles.** Worlds are built from reusable tiles;
  this engine groups them into 16×16 **metatiles**. Think in tiles/blocks, not
  freeform pixels.
- **Color is very limited.** Any one 16×16 block of background can use only
  **3 colors + a shared backdrop color**, and colors come in fixed groups of 4.
  Design tiles and characters as **"3 colors + transparent."** This is the
  constraint that bites hardest if ignored.
- **Moving things are scarce.** Only a few hardware sprites fit on one screen
  row before they flicker. The player (and a wandering NPC) are sprites;
  **anyone who just stands there should be drawn as background tiles**, not a
  sprite.
- **Variety comes from themed *sets*.** The cartridge swaps in a town set, a
  cave set, a battle set, etc., each a small limited palette. Design in
  **themed tile/character sets**, not unlimited unique art everywhere.
- **Text is small.** Dialogue boxes are roughly **30 characters wide × 4 lines**.
  Write short.
- **Sound is 5 voices.** Two melody/harmony voices, a bass voice, a noise
  channel for percussion, and a sample channel. Think melody + counter-melody +
  bass + drums; short loops. Distinct themes per place (town, field, dungeon,
  battle) carry as much personality as the art does.

## What to make, and in what order
1. **World/concept bible first.** The places, the kinds of characters, the tone,
   the rough story/progression. If "visual variety" is the hook, this is what
   tells the engine how much variety to support.
2. **A small reference slice, not the whole game.** One region's tile set, a few
   characters, a couple of monsters, a short script, a small stats table. This
   lets the formats get locked against *real* examples and the full pipeline get
   proven end-to-end — *then* you scale with confidence.

## Tools (use what you like; export format is settled per-subsystem)
- **Art:** any pixel editor, working in a fixed palette and the 3-colors rule.
- **Maps:** a grid/tile map editor (e.g. Tiled) or even gridded spreadsheets.
- **Script:** a plain doc — who says what, when; keep lines short.
- **Stats:** spreadsheets with clean columns (e.g. monster: HP/ATK/DEF/XP/gold;
  item: name/effect/cost).
- **Music:** **FamiStudio** (free, visual) — compose inside the NES's real
  limits; the engine plays its exported data directly.

## Where it lives
Give the source material **one agreed home in the repo** (this project:
`design/` — the game-bible workbook, mechanics decisions, script, reference
art, FamiStudio files) so the authored truth and the formats that consume it
stay next to each other and nothing lives only on someone's laptop.

The exact file an importer consumes is defined **together, per subsystem, in the
engine phase** (see `METHOD.md` → format-first). Don't mass-produce final assets
against a guessed format; make the small reference slice, lock the format, then
scale.
