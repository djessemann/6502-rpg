# Mechanics — the closed list

**Status: DRAFT — nothing here is decided yet.** Replace each bracketed blank
with a decision. The engine phase freezes its data formats (stats, encounter,
save, battle) against this file, so it must be filled in **before** those
formats are designed. Anything not on this list is not in the game.

Suggested defaults in *(italics)* are Dragon Quest 1's answers — a proven,
deliberately minimal shape. Take them, change them, or cut them; just decide.

## Party & battle
- **Party size:** [ ... ] *(DQ1: exactly 1 hero — the simplest battle system
  there is, and the biggest single scope lever in the game)*
- **Battle shape:** [ ... ] *(DQ1: one enemy at a time, turn-based, first-person
  view — the enemy is a big background-drawn portrait, which fits our
  visual-variety hook perfectly)*
- **Battle commands:** [ ... ] *(DQ1: Fight / Spell / Item / Run)*
- **Damage math:** [rough feel now; exact formula decided with Claude in the
  engine phase] *(DQ1 feel: attack vs defense/2, small random spread; misses
  and criticals exist)*
- **Turn order:** [ ... ] *(DQ1: agility-based with randomness)*

## Stats
- **Stats that exist:** [ ... ] *(DQ1: HP, MP, Strength, Agility — attack/defense
  are derived from stat + gear. Every stat here becomes a column in the bible
  and a byte in the save file; fewer is better)*
- **Leveling:** [ ... ] *(DQ1: XP table → level ups; the curve lives in the
  bible's Hero Progression tab)*
- **Level cap:** [ ... ] *(DQ1: 30)*

## Magic
- **Does magic exist?** [ ... ]
- **If yes:** [spell list size; battle spells, field spells, or both; learned by
  level?] *(DQ1: 10 spells, learned at fixed levels, mix of battle and field —
  see the bible's Spells tab)*

## Items & equipment
- **Equipment slots:** [ ... ] *(DQ1: weapon, armor, shield — one each, no
  inventory juggling)*
- **Inventory:** [size? stacking?] *(DQ1: ~10 slots + herbs/keys stack)*
- **Consumables/tools:** [ ... ] *(DQ1: herb, torch, wing, fairy water, keys)*

## World interaction
- **Encounters:** [ ... ] *(DQ1: random, step-based, per-zone monster tables)*
- **Doors & keys:** [ ... ] *(DQ1: locked doors, consumable magic keys)*
- **Darkness/light in dungeons:** [ ... ] *(DQ1: dark dungeons, torch/spell
  radius — atmospheric but an extra system; cuttable)*
- **Vehicles/travel:** [ ... ] *(DQ1: none — walking + warp spell/item only)*

## Economy & failure
- **Money:** [ ... ] *(DQ1: gold from battles; shops, inns)*
- **Death penalty:** [ ... ] *(DQ1: revive at the throne room, keep XP/items,
  lose half your gold — famously forgiving, no game over)*

## Saving
- **Save medium:** battery SRAM (decided — see CLAUDE.md).
- **Where can you save?** [ ... ] *(DQ1: one place — the King. Save-anywhere is
  more code and more save-state to define)*
- **Save slots:** [ ... ] *(DQ1 remakes: 1–3; 1 is simplest)*
