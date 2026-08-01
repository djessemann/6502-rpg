# THRENOS — design bible

**Title:** THRENOS
**Genre:** turn-based console RPG, science-fiction, single alien planet
**Platform:** NES, MMC3 (mapper 4), 256KB PRG / 128KB CHR, battery save
**Scope target:** Final Fantasy 1 — a full world, a four-member party, a level
curve, dozens of monsters, four "dungeon arcs" plus a final descent.

Everything below is the creative truth. The engine only reads data compiled
from this document by `game/tools/`.

-----

## 1. Premise

Two centuries ago the colony ark **EREBUS IX** fell out of the sky over the
planet **Threnos**. It did not crash by accident. Something in the deep crust
reached up and pulled it down.

The survivors lived. They built four **Anchor Stations** on the ark's four
broken drive cores, and those cores did more than make power — they held the
planet's berserk weather, its shifting ground, and its hungry machine-life in
check. Four Anchors, four regions, two hundred years of a small, stubborn
civilisation.

Now the Anchors are going dark, one after another. The sky is bleeding.
And in the sealed hull of the EREBUS IX, at the bottom of the Rift, something
that calls itself **THE ARCHON** is finishing a two-hundred-year calculation.

**The player's story:** four **Wardens** are woken from cold storage in
Landfall — the last crew the ark's medical bay kept in reserve "for an
emergency worth waking them for." They must relight the four Anchors and go
down into the Rift.

## 2. The four Anchors (the arc)

| # | Anchor | Region | Dungeon | Guardian boss |
|---|--------|--------|---------|---------------|
| 1 | **CINDER** (thermal) | The Ashen Verge — volcanic plains, black glass | Cinder Anchor, 3 floors | **MAGMA HULK** |
| 2 | **TIDE** (hydro) | The Drowned Shelf — flooded terraces, kelp cities | Tide Anchor, 3 floors | **ABYSSAL WARDEN** |
| 3 | **STORM** (aero) | The Screaming Reach — mesas, permanent lightning | Storm Anchor, 3 floors | **THUNDER SERAPH** |
| 4 | **HOLLOW** (grav) | The Hollow Waste — grey dunes over a buried city | Hollow Anchor, 3 floors | **NULL COLOSSUS** |
| — | — | The Rift | Erebus Hull, 4 floors | **THE ARCHON** (2 forms) |

Gating (classic FF1 shape — the world opens as you go):

1. **Landfall** (start town) → the **Cinder** arc. Reward: the **PASSKEY**.
2. Passkey opens the **Sunken Causeway**, reaching the Drowned Shelf →
   **Tide** arc. Reward: the **SKIFF** (crosses shallow water on the overworld).
3. Skiff reaches the Screaming Reach → **Storm** arc. Reward: the **LIFT CODE**,
   which powers the **GRAV-LIFT** (crosses mountains/chasms on the overworld).
4. Grav-lift reaches the Hollow Waste → **Hollow** arc. Reward: the **RIFT KEY**.
5. Rift Key opens the Rift → Erebus Hull → THE ARCHON.

Two optional side dungeons for gear: **Relay Nine** (a comms tower, mid-game)
and the **Ossuary** (a monster den, late-game, holds the best weapon).

## 3. Party

The player builds a party of **exactly 4** at the start, choosing each member's
class from six. Names are auto-assigned from a class name pool (no text entry —
saves an entire keyboard UI, and FF1's naming is not load-bearing).

| Class | Role | Grows | Techs | Notes |
|-------|------|-------|-------|-------|
| **SOLDIER** | front-line damage/tank | STR, VIT high | none | best weapons + armour |
| **RANGER** | fast, ranged | AGI high, STR med | none | strikes first, rifles |
| **MEDIC** | healer | SPI high, VIT med | BIO techs | heals, cures, revives |
| **PSION** | offense caster | SPI high, VIT low | PSI techs | elemental damage |
| **ENGINEER** | hybrid | balanced | BIO + PSI (low tier) | buffs, machines, repairs |
| **BRAWLER** | unarmed melee | STR, AGI high | none | damage scales with level, cheap gear |

**Class change** (FF1's "class upgrade"): after the Storm Anchor, the shrine at
**Relay Nine** promotes every class to its **veteran form** (SOLDIER→VANGUARD,
RANGER→MARKSMAN, MEDIC→SURGEON, PSION→ORACLE, ENGINEER→ARTIFICER,
BRAWLER→MYRMIDON). Promotion unlocks the top tech tiers and better gear.

## 4. Stats (frozen — these are the save-file bytes)

Per character: `LVL, XP(3), HP, HPMAX(2), TP, TPMAX, STR, AGI, VIT, SPI, ATK,
DEF, hit%, status, class, weapon, armour, shield, helm` — see
`design/MECHANICS.md` for the exact byte list.

- **HP** — hit points (max 999).
- **TP** — tech points, one shared pool per character (max 99). Techs cost TP.
- **STR** — melee damage. **AGI** — turn order + evasion + ranged damage.
- **VIT** — HP growth + defence. **SPI** — tech power + tech resistance.
- **ATK/DEF** derived from stats + equipment; recomputed on equip and level-up.

**Level cap 30.** XP curve is roughly `XP(n) = 24 * n^2.1`, table-authored,
capped ~330,000. Level-up grants class-specific stat gains from a growth table
and re-derives HPMAX/TPMAX.

## 5. Battle

- **Shape:** turn-based, side view. Party of 4 on the right (sprite portraits +
  HUD), enemy group of **up to 4** drawn as **background tiles** (the
  visual-variety hook: big, individually drawn monsters).
- **Encounter:** up to 2 distinct monster types per group (CHR budget), 1–4
  monsters total. Random by zone, step-triggered; fixed for bosses.
- **Commands:** FIGHT / TECH / ITEM / GUARD / RUN.
- **Turn order:** each combatant rolls `AGI + rand(0..15)` per round, highest
  first. RUN succeeds on `AGI` vs the group's average AGI.
- **Damage (melee):** `base = ATK - DEF/2`, clamped ≥1, times a hit count of 1
  (+1 per 32 points of AGI), spread `±12%`, critical (×2) on 1/32.
- **Damage (tech):** `base = power + SPI/2`, resisted by target `SPI/4`, element
  multipliers ×2 (weak) / ×0 (immune, "NO EFFECT").
- **Status:** POISON (HP drain per step/turn), STUN (lose turns), BLIND (hit%
  halved), SILENCE (no techs), DOWN (0 HP). All curable.
- **Rewards:** XP + CREDITS split across living members; occasional item drop.
- **Death:** if the whole party is DOWN → GAME OVER → reload from last save.

## 6. Techs (magic)

Two schools, 8 tiers of 2 techs each = **32 techs** total.

**PSI (offensive/utility):** SPARK, CHILL, JOLT, SCAN, FLARE, QUAKE, HUSH,
HASTE, PLASMA, RIME, GRAVITY, BARRIER, NOVA, VOID, SHATTER, DOOM.
**BIO (healing/support):** MEND, CLEANSE, GUARD+, ROUSE, MEND-2, ANTIDOTE,
SHIELD, FOCUS, MEND-3, REVIVE, PURGE, RESIST, MEND-ALL, RENEW, WARD, LAZARUS.

Techs are learned automatically at fixed levels per class (no shops for techs —
one less system). Field-usable techs: MEND family, REVIVE, LAZARUS, CLEANSE,
ANTIDOTE, plus **RECALL** (warp to last town) and **EXIT** (leave a dungeon),
which are items instead of techs to keep the tech tables uniform.

## 7. Items & equipment

- **Slots:** WEAPON, ARMOUR, SHIELD, HELM (4 slots × 4 characters).
- **Inventory:** 32 slots, stackable to 99, shared across the party.
- **Consumables:** MEDKIT / MEDKIT-2 / MEDKIT-3 (heal), ANTITOX, STIMPACK
  (revive), TP-CELL, BEACON (=RECALL), EXIT-CHIP, GRENADE, EMP-CHARGE, TORCH.
- **Key items:** PASSKEY, SKIFF, LIFT CODE, RIFT KEY, plus the four **ANCHOR
  SPARKS** returned from each dungeon.
- ~24 weapons, ~16 armours, ~10 shields, ~10 helms, with class restrictions.

## 8. World

**Overworld:** 128×128 metatiles (2048×2048 px), wrapping. Terrain: ash plain,
scrub, ridge, black glass, shallow sea, deep sea, dune, crag, canyon, road,
ruin, forest of bone-trees. Movement is blocked by deep sea (needs SKIFF), and
by ridges/chasms (needs GRAV-LIFT).

**Towns (6):** LANDFALL (start, hub), EMBER REST (Ashen Verge), KELPHOLD
(Drowned Shelf), HIGH MESA (Screaming Reach), DUSTGATE (Hollow Waste),
THE LAST PORT (pre-Rift). Each: inn, shop(s), save terminal, 4–8 NPCs.

**Dungeons (map count):** Cinder ×3, Tide ×3, Storm ×3, Hollow ×3, Erebus ×4,
Relay Nine ×2, Ossuary ×2, plus the Sunken Causeway ×1 = **21 dungeon maps**
+ 6 towns + 1 overworld = **28 maps**.

**Save:** at **save terminals** (towns + one per dungeon's entry floor). One
slot, battery-backed, checksummed.

## 9. Monsters

**48 unique designs**, most with a palette-swapped stronger variant (FF1's own
trick) for **~70 encounter entries**. Families:

*Machine-life:* CRAWLER, SENTRY DRONE, RIVET HOUND, SCRAP TITAN, WELDER,
ARC MITE, LOADER, CHASSIS, SEEKER, WARDEN UNIT.
*Xenofauna:* ASH MOTH, GLASS TICK, DUNE EEL, SPINE CRAB, KELP HORROR, THRESHER,
BONE STAG, SILT LURKER, ROC CHICK, MAW.
*Anomalies:* VOID WISP, ECHO, STATIC, PHASE HOUND, GRAV WELL, MIRROR, NULL.
*Colonists gone wrong:* HUSK, REAVER, CULTIST, ASCETIC, PROPHET.
*Bosses:* MAGMA HULK, ABYSSAL WARDEN, THUNDER SERAPH, NULL COLOSSUS,
RIFT SENTINEL, THE ARCHON, ARCHON PRIME.

## 10. Music

8 tracks: TITLE, LANDFALL (town), OVERWORLD, DUNGEON, BATTLE, BOSS, VICTORY,
ENDING; plus a short FANFARE and a set of SFX (cursor, confirm, cancel, hit,
crit, heal, tech, level-up, door, save, encounter).

## 11. Tone & script rules

Dry, plain, a little haunted. Colonists speak like people who have been fixing
the same machines for two centuries. The Archon speaks in second person.
No line exceeds 30 characters; boxes are 4 lines; keep speeches to 1–2 pages.
