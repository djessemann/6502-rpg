# MECHANICS — the closed list (frozen)

Everything the engine's data formats freeze against. Anything not here is not
in the game.

## Party & battle
- **Party size:** exactly 4, chosen at New Game from 6 classes.
- **Battle shape:** turn-based; up to 4 party members vs up to 4 enemies of at
  most 2 distinct types. Enemies are background-drawn; party members are
  sprites with a HUD row.
- **Battle commands:** FIGHT / TECH / ITEM / GUARD / RUN.
- **Turn order:** per round, each combatant's initiative = `AGI + rand(0..15)`;
  descending. Ties broken by party-before-enemy.
- **Melee damage:** `d = max(1, ATK - DEF/2)`; hits = `1 + AGI/32`; per-hit
  spread `d * (112..88)/100`; critical ×2 at 1/32; miss if
  `rand(0..99) >= hit%` (hit% = `168 - target_evade`, clamped 40..99).
- **Tech damage:** `d = power + SPI/2`, minus `target_SPI/4`, element multiplier
  ×2 weak / ×1 normal / ×0 immune, spread ±12%.
- **GUARD:** halves damage taken until that character's next turn.
- **RUN:** succeeds if `rand(0..255) < 96 + partyAGI - enemyAGI`; bosses block.
- **Status effects:** POISON, STUN, BLIND, SILENCE, DOWN.

## Stats
- **Per character:** LVL, XP(3 bytes), HP(2), HPMAX(2), TP, TPMAX, STR, AGI,
  VIT, SPI, ATK, DEF, EVA, HITPCT, STATUS, CLASS, and 4 equipment slots.
- **Derived on equip/level:** `ATK = STR/2 + weapon.atk`,
  `DEF = VIT/4 + sum(armour.def)`, `EVA = AGI/2 + armour.eva`.
- **Leveling:** XP table of 30 entries; per-class growth table adds
  (HP, TP, STR, AGI, VIT, SPI) per level; **level cap 30**.
- **Max HP 999, max TP 99.**

## Techs
- 32 techs, 2 schools (PSI/BIO) × 8 tiers × 2. Learned automatically at fixed
  levels per class. TP cost = tier. No tech shops.

## Items & equipment
- **Slots:** WEAPON, ARMOUR, SHIELD, HELM.
- **Inventory:** 32 slots, stack to 99, shared.
- **Key items** are flags, not inventory slots.

## World interaction
- **Encounters:** random, step-based, per-zone tables (8 entries per zone,
  weighted); rate is per-zone. Boss encounters are map triggers.
- **Doors & keys:** locked doors open with story flags (PASSKEY / RIFT KEY).
- **Vehicles:** SKIFF (shallow sea), GRAV-LIFT (ridge/chasm). No airship.
- **Treasure chests:** map objects; one flag bit each (256 chest flags).
- **Darkness:** cut.

## Economy & failure
- **Money:** CREDITS from battle; shops buy at list price, sell at half.
- **Death:** party wipe = GAME OVER, reload last save.

## Saving
- **Medium:** battery SRAM at $6000. **Slots:** 1. Checksummed.
- **Where:** save terminals (towns + dungeon entrances).
