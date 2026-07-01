# design/ — the game's creative source material

Everything the designer authors lives here. This directory is the **design
truth**; the engine never reads these files directly — content is compiled into
ROM data (in the engine/content phases) *from* what's captured here.

## What goes where

| File / folder      | Holds | Format |
|--------------------|-------|--------|
| `game-bible.xlsx`  | All structured design data: story beats, triggers/events, cast, hero progression, spells, bestiary, gear, items, locations, shops, encounter notes, art sets, music cues. Start at its **Start Here** tab. | Excel workbook |
| `MECHANICS.md`     | The **closed list** of mechanics decisions. Engine data formats freeze against this file — fill it in before the engine phase. | Markdown, fill-in-the-blanks |
| `script/`          | Long-form dialogue and narrative, when it outgrows the workbook's key-line columns. Who says what, when; keep lines short (boxes are ~30 chars × 4 lines). | Plain text / Markdown |
| `art/`             | Reference art: tiles, characters, monsters. Any pixel editor; obey **3 colors + transparent** per 16×16 block (see `framework/ASSETS.md`). | PNG (or text grids) |
| `music/`           | Compositions and SFX sketches. | FamiStudio project files (`.fms`) |

(`script/`, `art/`, `music/` are created when the first file needs them.)

## The rules that matter here

- **Reference slice first.** Before mass-producing anything, finish a *small
  real sample*: one region's tileset, a few characters, a couple of monsters, a
  short script, a small stats table. The engine phase locks its data formats
  against these real examples — then you scale with confidence.
- **Use the workbook's Status column** (Placeholder → Draft → Review → Locked).
  Formats and ROM data are only ever built from **Locked** rows.
- **Design within the canvas.** `framework/ASSETS.md` is the one-page guide to
  the NES's limits (tiles, colors, sprites, text, sound). Read it before
  authoring; it prevents the art that has to be redrawn later.
- One home for everything: if it isn't in `design/` (or the workbook), it isn't
  part of the game yet.
