# archive/ — salvaged work from retired branches

Work rescued from old experiment branches before they were deleted (repo
cleanup, 2026-07-01). Each folder holds the branch's unique commits as git
patch files — full diffs, original commit messages, ready to re-apply.

**Nothing here is in the game.** Per the scope rules (CLAUDE.md), a patch is
only applied when a phase's scope calls for that feature — then it's a starting
point, not a decision. To restore one, ask Claude to apply it (`git am
archive/<folder>/<file>.patch`, then re-verify — the code has moved since).

## Inventory

### fable-test-features/ — from `claude/nes-rpg-fable-test-gcs76z` (head `417ac6c`)
Five working slice upgrades, built and verified on top of the completed slice
(base `5699ca3`), in apply order:
1. True 16×16 terrain metatile art, new field palettes, NPC/window redraw.
2. Hero sprite redraw + constant 2-frame walk-cycle animation.
3. Authored 32×32 shaded slime + hero HP status window in battle.
4. Fight/Run battle command menu, enemy counterattacks, player HP.
5. Water shimmer via palette cycling.

Likely future homes: 1–3 are content/art (content phase, or reference for the
game bible's art direction); 4 is superseded by the real battle system the
engine phase builds from `design/MECHANICS.md` (keep as UI/flow reference);
5 is a small engine trick (parking-lot material).

### space-theme-reskin/ — from `claude/space-theme-test-rom-p45hm8` (head `43c8646`)
A content-only reskin of the slice (astronaut hero, service-droid NPC, alien
enemy, metal-deck terrain) done purely through `tools/gen_assets.py`. Kept
only as a worked example that all art flows through the content entry points.
**This was a pipeline experiment, not a direction** — the game has one theme,
chosen by the designer in `design/`; theme-swapping is not a mechanic and the
final theme may or may not be fantasy, space, or anything else.

## Deleted without archiving (nothing unique worth keeping)
- `claude/game-bible-spreadsheet-dkca8t` (`4b4ada2`) — its workbook was
  salvaged, extended, and lives at `design/game-bible.xlsx`.
- `claude/nes-rpg-vertical-slice-fgvwjz` (`c4eead6`) — early boot diagnostics,
  superseded by the finished slice on main.
- `claude/vertical-slice-setup-em43j8` (`5699ca3`) — pointed at old main; no
  unique commits.
