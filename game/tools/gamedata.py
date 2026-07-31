"""All of THRENOS's numeric design data: classes, the level curve, gear, techs,
monsters, encounter formations and shops. Compiled into the BANK_TABLES data
bank plus a constants include.

Everything here is authored against design/MECHANICS.md.
"""

# --- classes -----------------------------------------------------------------
# name, base (HP,TP,STR,AGI,VIT,SPI), growth per level (same order),
# school (0 none, 1 PSI, 2 BIO, 3 both), equip mask, veteran name
CLASSES = [
    ("SOLDIER",  (40, 0, 14, 8, 13, 5),  (8, 0, 3, 1, 3, 1), 0, 0b00111111, "VANGUARD"),
    ("RANGER",   (32, 0, 11, 14, 9, 7),  (6, 0, 2, 3, 2, 1), 0, 0b00011111, "MARKSMAN"),
    ("MEDIC",    (26, 8, 8, 9, 8, 14),   (5, 2, 1, 2, 2, 3), 2, 0b00000111, "SURGEON"),
    ("PSION",    (22, 10, 6, 10, 6, 16), (4, 3, 1, 2, 1, 3), 1, 0b00000011, "ORACLE"),
    ("ENGINEER", (30, 6, 10, 10, 10, 10), (5, 1, 2, 2, 2, 2), 3, 0b00001111, "ARTIFICER"),
    ("BRAWLER",  (36, 0, 15, 12, 11, 4), (7, 0, 3, 3, 2, 1), 0, 0b00000011, "MYRMIDON"),
]

# --- level curve: XP required to REACH each level (index 0 = level 1) ---------
def _xp_curve():
    out = [0]
    for lvl in range(2, 31):
        out.append(int(24 * (lvl ** 2.1)) * 4)
    return out

XP_TABLE = _xp_curve()

# --- items -------------------------------------------------------------------
IT_NONE, IT_WEAPON, IT_ARMOUR, IT_SHIELD, IT_HELM, IT_USE, IT_KEY = range(7)

# (name, kind, power, price, equip_mask, effect)
# effect for IT_USE: 1 heal HP, 2 cure status, 3 revive, 4 restore TP,
#                    5 damage all enemies, 6 warp to town, 7 leave dungeon
ITEMS = [
    ("-",          IT_NONE,   0,    0, 0b00000000, 0),
    # weapons
    ("KNIFE",      IT_WEAPON,  4,   30, 0b00111111, 0),
    ("BATON",      IT_WEAPON,  6,   70, 0b00111111, 0),
    ("MACHETE",    IT_WEAPON, 10,  180, 0b00110011, 0),
    ("RIVET GUN",  IT_WEAPON, 13,  320, 0b00010011, 0),
    ("ARC SPIKE",  IT_WEAPON, 17,  560, 0b00110011, 0),
    ("CARBINE",    IT_WEAPON, 20,  900, 0b00010010, 0),
    ("BREAKER",    IT_WEAPON, 24, 1500, 0b00100001, 0),
    ("PULSE LANCE",IT_WEAPON, 28, 2400, 0b00100001, 0),
    ("MONOEDGE",   IT_WEAPON, 33, 4000, 0b00000001, 0),
    ("RAILGUN",    IT_WEAPON, 36, 5200, 0b00000010, 0),
    ("STAFF",      IT_WEAPON,  7,  140, 0b00011100, 0),
    ("FOCUS ROD",  IT_WEAPON, 12,  620, 0b00011100, 0),
    ("PSI PRISM",  IT_WEAPON, 18, 1900, 0b00001100, 0),
    ("BONE FIST",  IT_WEAPON, 15,  400, 0b00100000, 0),
    ("STAR FIST",  IT_WEAPON, 26, 2600, 0b00100000, 0),
    ("ANCHOR EDGE",IT_WEAPON, 44,    0, 0b00000001, 0),
    # armour
    ("WORKSUIT",   IT_ARMOUR,  3,   40, 0b00111111, 0),
    ("PLATE VEST", IT_ARMOUR,  7,  140, 0b00110011, 0),
    ("CERAMWEAVE", IT_ARMOUR, 11,  380, 0b00110011, 0),
    ("FIELD COAT", IT_ARMOUR,  8,  260, 0b00011110, 0),
    ("EXO FRAME",  IT_ARMOUR, 16,  950, 0b00010001, 0),
    ("VOID MANTLE",IT_ARMOUR, 14, 1300, 0b00001100, 0),
    ("ANCHOR MAIL",IT_ARMOUR, 24, 3800, 0b00110001, 0),
    ("ARK SHELL",  IT_ARMOUR, 30,    0, 0b00110001, 0),
    # shields
    ("HAND PLATE", IT_SHIELD,  2,   60, 0b00110011, 0),
    ("BLAST WARD", IT_SHIELD,  5,  240, 0b00110011, 0),
    ("NULL FIELD", IT_SHIELD,  9, 1100, 0b00110001, 0),
    ("ARK AEGIS",  IT_SHIELD, 14,    0, 0b00000001, 0),
    # helms
    ("HARD HAT",   IT_HELM,    1,   40, 0b00111111, 0),
    ("VISOR RIG",  IT_HELM,    3,  160, 0b00111111, 0),
    ("SEALED HOOD",IT_HELM,    6,  700, 0b00111111, 0),
    ("ARK CROWN",  IT_HELM,   10,    0, 0b00111111, 0),
    # consumables
    ("MEDKIT",     IT_USE,    40,   30, 0b00111111, 1),
    ("MEDKIT-2",   IT_USE,   150,  180, 0b00111111, 1),
    ("MEDKIT-3",   IT_USE,   500,  700, 0b00111111, 1),
    ("ANTITOX",    IT_USE,     0,   50, 0b00111111, 2),
    ("STIMPACK",   IT_USE,    60,  260, 0b00111111, 3),
    ("TP-CELL",    IT_USE,    20,  200, 0b00111111, 4),
    ("GRENADE",    IT_USE,    35,  120, 0b00111111, 5),
    ("EMP CHARGE", IT_USE,    70,  400, 0b00111111, 5),
    ("BEACON",     IT_USE,     0,  150, 0b00111111, 6),
    ("EXIT CHIP",  IT_USE,     0,  100, 0b00111111, 7),
    # key items
    ("PASSKEY",    IT_KEY,     0,    0, 0, 0),
    ("LIFT CODE",  IT_KEY,     0,    0, 0, 0),
    ("RIFT KEY",   IT_KEY,     0,    0, 0, 0),
]

# --- techs -------------------------------------------------------------------
# name, school (1 PSI / 2 BIO), tier 1..8, power, element, target, status
#
# `status` is a mask of the ST_* bits in src/ram.inc and means two different
# things depending on which side of the target list the tech is on:
#   offensive (TG_ONE_ENEMY / TG_ALL_ENEMY) -> the status it tries to INFLICT
#                                              (ST_ODDS in battle.s: 25%, and
#                                              half of that again on a boss)
#   support   (TG_*_ALLY / TG_SELF)         -> the status it CURES
# ST_DOWN is never inflicted or cured by a mask; death and revival are separate.
ST_POISON, ST_STUN, ST_BLIND, ST_SILENCE = 0x01, 0x02, 0x04, 0x08
ST_ALL = ST_POISON | ST_STUN | ST_BLIND | ST_SILENCE

EL_NONE, EL_FIRE, EL_ICE, EL_SHOCK, EL_VOID = range(5)
TG_ONE_ENEMY, TG_ALL_ENEMY, TG_ONE_ALLY, TG_ALL_ALLY, TG_SELF = range(5)

# All-enemy techs are priced at roughly half their same-tier single-target
# counterpart. They used to be priced at ~90% of it - i.e. nearly four times the
# value - which is why one boss cast could wipe the party (tools/balance.py).
#
# STUN and SILENCE are single-target only. A four-member party leans on one
# healer, so an all-enemy tech that mass-stuns or mass-silences does not make a
# hard fight, it makes an unwinnable one: THE ARCHON's SHATTER went from a 95%
# clear to 31% (STUN) and 17% (SILENCE) on nothing but that change. All-target
# techs get POISON or BLIND, which cost the party throughput rather than turns.
TECHS = [
    ("SPARK",   1, 1, 14, EL_SHOCK, TG_ONE_ENEMY, 0),
    ("CHILL",   1, 1, 12, EL_ICE,   TG_ONE_ENEMY, ST_STUN),
    ("JOLT",    1, 2, 16, EL_SHOCK, TG_ALL_ENEMY, ST_BLIND),
    ("SCAN",    1, 2,  0, EL_NONE,  TG_ONE_ENEMY, 0),
    ("FLARE",   1, 3, 34, EL_FIRE,  TG_ONE_ENEMY, ST_BLIND),
    ("QUAKE",   1, 3, 20, EL_NONE,  TG_ALL_ENEMY, ST_POISON),
    ("HUSH",    1, 4,  0, EL_NONE,  TG_ONE_ENEMY, ST_SILENCE),
    ("HASTE",   1, 4,  0, EL_NONE,  TG_ONE_ALLY, 0),
    ("PLASMA",  1, 5, 56, EL_FIRE,  TG_ONE_ENEMY, 0),
    ("RIME",    1, 5, 30, EL_ICE,   TG_ALL_ENEMY, 0),
    ("GRAVITY", 1, 6, 60, EL_VOID,  TG_ONE_ENEMY, ST_STUN),
    ("BARRIER", 1, 6,  0, EL_NONE,  TG_ALL_ALLY, 0),
    ("NOVA",    1, 7, 50, EL_FIRE,  TG_ALL_ENEMY, ST_BLIND),
    ("VOID",    1, 7, 96, EL_VOID,  TG_ONE_ENEMY, ST_SILENCE),
    ("SHATTER", 1, 8, 80, EL_ICE,   TG_ALL_ENEMY, ST_BLIND),
    ("DOOM",    1, 8, 110, EL_VOID, TG_ONE_ENEMY, ST_SILENCE),
    ("MEND",    2, 1, 30, EL_NONE,  TG_ONE_ALLY, 0),
    ("CLEANSE", 2, 1,  0, EL_NONE,  TG_ONE_ALLY, ST_POISON),
    ("GUARD+",  2, 2,  0, EL_NONE,  TG_ONE_ALLY, 0),
    ("ROUSE",   2, 2,  0, EL_NONE,  TG_ONE_ALLY, ST_STUN | ST_BLIND),
    ("MEND-2",  2, 3, 90, EL_NONE,  TG_ONE_ALLY, 0),
    ("ANTIDOTE",2, 3,  0, EL_NONE,  TG_ALL_ALLY, ST_POISON | ST_BLIND),
    ("SHIELD",  2, 4,  0, EL_NONE,  TG_ONE_ALLY, 0),
    ("FOCUS",   2, 4,  0, EL_NONE,  TG_SELF, 0),
    ("MEND-3",  2, 5, 200, EL_NONE, TG_ONE_ALLY, 0),
    ("REVIVE",  2, 5,  0, EL_NONE,  TG_ONE_ALLY, 0),
    ("PURGE",   2, 6,  0, EL_NONE,  TG_ALL_ALLY, ST_ALL),
    ("RESIST",  2, 6,  0, EL_NONE,  TG_ALL_ALLY, 0),
    ("MEND-ALL",2, 7, 160, EL_NONE, TG_ALL_ALLY, 0),
    ("RENEW",   2, 7, 400, EL_NONE, TG_ONE_ALLY, 0),
    ("WARD",    2, 8,  0, EL_NONE,  TG_ALL_ALLY, 0),
    ("LAZARUS", 2, 8,  0, EL_NONE,  TG_ONE_ALLY, ST_ALL),
]

TECH_ID = {t[0]: i for i, t in enumerate(TECHS)}

# tech learn table: class index -> list of (level, tech index)
def _learn():
    psi = [i for i, t in enumerate(TECHS) if t[1] == 1]
    bio = [i for i, t in enumerate(TECHS) if t[1] == 2]
    tbl = {c: [] for c in range(len(CLASSES))}
    lv = [1, 1, 4, 6, 9, 12, 15, 18, 21, 23, 25, 26, 27, 28, 29, 30]
    for i, t in enumerate(bio):
        tbl[2].append((lv[i], t))                      # MEDIC: all BIO
    for i, t in enumerate(psi):
        tbl[3].append((lv[i], t))                      # PSION: all PSI
    for i, t in enumerate(psi[:8]):                    # ENGINEER: low tiers
        tbl[4].append((lv[i] + 2, t))
    for i, t in enumerate(bio[:8]):
        tbl[4].append((lv[i] + 3, t))
    return tbl

LEARN = _learn()

# --- monsters ----------------------------------------------------------------
# name, hp, atk, def, agi, spi, xp, credits, weakness element, immunity,
# ai, special tech, boss flag
#
# ai 0 = attacks only; the `special` column is ignored.
# ai 1 = attacks, but roughly one turn in three uses `special`.
# ai 2 = caster: uses `special` most turns, and falls back to attacking when it
#        cannot (silenced, or a healing special with nothing hurt to heal).
# `special` is a tech index; an offensive one is aimed at the party through the
# same damage path party techs use, a support one heals the monster's own side.
T = TECH_ID
MONSTERS = [
    ("CRAWLER",      12,   6,  2,  6,  2,    6,    5, EL_FIRE,  0, 0, 0, 0),
    ("ASH MOTH",      9,   5,  1, 12,  4,    7,    4, EL_ICE,   0, 0, 0, 0),
    ("GLASS TICK",   14,   7,  5,  7,  2,    9,    7, EL_SHOCK, 0, 0, 0, 0),
    ("SENTRY DRONE", 18,   9,  4, 11,  4,   14,   12, EL_SHOCK, 0, 1, T["SPARK"], 0),
    ("HUSK",         22,  10,  3,  5,  3,   16,   10, EL_FIRE,  0, 0, 0, 0),
    ("RIVET HOUND",  26,  13,  6, 13,  3,   22,   16, EL_ICE,   0, 0, 0, 0),
    ("ARC MITE",     16,   8,  3, 15,  8,   18,   14, EL_VOID,  EL_SHOCK, 1, T["SPARK"], 0),
    ("DUNE EEL",     34,  15,  5,  9,  4,   30,   20, EL_ICE,   0, 0, 0, 0),
    ("SPINE CRAB",   40,  16, 12,  6,  3,   34,   24, EL_SHOCK, 0, 0, 0, 0),
    ("WELDER",       38,  18,  9, 10,  5,   40,   30, EL_ICE,   EL_FIRE, 1, T["FLARE"], 0),
    ("VOID WISP",    24,  12,  4, 18, 14,   38,   26, EL_SHOCK, EL_VOID, 2, T["CHILL"], 0),
    ("REAVER",       52,  22,  8, 12,  5,   52,   40, EL_NONE,  0, 0, 0, 0),
    ("KELP HORROR",  60,  20, 10,  7,  8,   58,   44, EL_FIRE,  EL_ICE, 0, 0, 0),
    ("SILT LURKER",  48,  21,  9, 11,  6,   50,   38, EL_SHOCK, 0, 0, 0, 0),
    ("LOADER",       70,  25, 16,  6,  4,   72,   55, EL_SHOCK, 0, 0, 0, 0),
    ("ECHO",         44,  19,  6, 20, 16,   66,   48, EL_NONE,  EL_VOID, 2, T["FLARE"], 0),
    ("THRESHER",     78,  28, 11, 15,  6,   88,   64, EL_ICE,   0, 0, 0, 0),
    ("BONE STAG",    66,  26,  9, 17,  7,   80,   58, EL_FIRE,  0, 0, 0, 0),
    ("CULTIST",      54,  20,  7, 12, 18,   76,   60, EL_NONE,  0, 2, T["QUAKE"], 0),
    ("STATIC",       58,  24,  8, 19, 15,   84,   62, EL_ICE,   EL_SHOCK, 2, T["JOLT"], 0),
    ("CHASSIS",     100,  32, 20,  8,  6,  120,   90, EL_SHOCK, 0, 1, T["JOLT"], 0),
    ("PHASE HOUND",  84,  30, 12, 22,  9,  118,   86, EL_FIRE,  0, 0, 0, 0),
    ("ROC CHICK",    92,  33, 13, 20,  8,  130,   95, EL_SHOCK, 0, 0, 0, 0),
    ("SEEKER",       88,  31, 15, 18, 12,  126,   92, EL_VOID,  0, 1, T["FLARE"], 0),
    ("GRAV WELL",    76,  27, 10, 14, 24,  140,  110, EL_FIRE,  EL_VOID, 2, T["GRAVITY"], 0),
    ("ASCETIC",      82,  28,  9, 16, 26,  144,  115, EL_NONE,  0, 2, T["MEND-2"], 0),
    ("MAW",         150,  40, 18, 10,  8,  210,  160, EL_ICE,   0, 0, 0, 0),
    ("SCRAP TITAN", 180,  44, 26,  7,  6,  260,  200, EL_SHOCK, 0, 1, T["QUAKE"], 0),
    ("PROPHET",     120,  34, 12, 18, 30,  240,  190, EL_NONE,  0, 2, T["NOVA"], 0),
    ("WARDEN UNIT", 210,  48, 28, 14, 12,  340,  260, EL_VOID,  0, 1, T["RIME"], 0),
    # bosses: every one of them has a special worth fearing, and the two Archon
    # forms are casters so theirs is the shape of the fight, not a surprise.
    ("MAGMA HULK",  150,  24, 18, 10,  8,  600,  400, EL_ICE,   EL_FIRE, 1, T["FLARE"], 1),
    ("ABYSS WARDEN",420,  50, 22, 14, 16, 1000,  700, EL_SHOCK, EL_ICE, 1, T["RIME"], 1),
    ("SERAPH",620, 78, 26, 24, 22, 1600, 1100, EL_VOID, EL_SHOCK, 1, T["PLASMA"], 1),
    ("NULLCOLOSSUS",820, 92, 34, 16, 26, 2400, 1600, EL_FIRE,  EL_VOID, 1, T["GRAVITY"], 1),
    ("RIFT SENTINL",990, 102, 36, 22, 28, 3200, 2000, EL_NONE,  0, 1, T["NOVA"], 1),
    ("THE ARCHON",  1400, 92, 40, 26, 34, 5000, 3000, EL_NONE,  0, 2, T["SHATTER"], 1),
    ("ARCHON PRIME",1900,104, 46, 30, 40, 9999, 5000, EL_NONE,  0, 2, T["DOOM"], 1),
]
del T

MONSTER_ID = {m[0]: i for i, m in enumerate(MONSTERS)}

# --- formations: (type0, count0, type1, count1, flags) -----------------------
# flags bit0 = cannot flee (boss)
FORMATIONS = [
    ("CRAWLER", 2, None, 0, 0),
    ("CRAWLER", 4, None, 0, 0),
    ("ASH MOTH", 3, None, 0, 0),
    ("ASH MOTH", 2, "CRAWLER", 2, 0),
    ("GLASS TICK", 2, None, 0, 0),
    ("GLASS TICK", 3, "ASH MOTH", 1, 0),
    ("SENTRY DRONE", 2, None, 0, 0),
    ("HUSK", 2, "CRAWLER", 1, 0),
    ("RIVET HOUND", 2, None, 0, 0),
    ("RIVET HOUND", 1, "SENTRY DRONE", 2, 0),
    ("ARC MITE", 3, None, 0, 0),
    ("DUNE EEL", 2, None, 0, 0),
    ("SPINE CRAB", 2, None, 0, 0),
    ("WELDER", 2, "ARC MITE", 1, 0),
    ("VOID WISP", 3, None, 0, 0),
    ("REAVER", 2, None, 0, 0),
    ("KELP HORROR", 1, "SILT LURKER", 2, 0),
    ("SILT LURKER", 3, None, 0, 0),
    ("LOADER", 2, None, 0, 0),
    ("ECHO", 2, "VOID WISP", 2, 0),
    ("THRESHER", 2, None, 0, 0),
    ("BONE STAG", 2, "THRESHER", 1, 0),
    ("CULTIST", 3, None, 0, 0),
    ("STATIC", 2, "ECHO", 1, 0),
    ("CHASSIS", 2, None, 0, 0),
    ("PHASE HOUND", 3, None, 0, 0),
    ("ROC CHICK", 2, "PHASE HOUND", 1, 0),
    ("SEEKER", 2, "CHASSIS", 1, 0),
    ("GRAV WELL", 2, None, 0, 0),
    ("ASCETIC", 2, "CULTIST", 2, 0),
    ("MAW", 1, None, 0, 0),
    ("SCRAP TITAN", 1, "LOADER", 2, 0),
    ("PROPHET", 1, "ASCETIC", 2, 0),
    ("WARDEN UNIT", 1, "SEEKER", 1, 0),
    # bosses
    ("MAGMA HULK", 1, None, 0, 1),
    ("ABYSS WARDEN", 1, None, 0, 1),
    ("SERAPH", 1, None, 0, 1),
    ("NULLCOLOSSUS", 1, None, 0, 1),
    ("RIFT SENTINL", 1, None, 0, 1),
    ("THE ARCHON", 1, None, 0, 1),
    ("ARCHON PRIME", 1, None, 0, 1),
]

# --- encounter zones: 8 formation indices each (rolled uniformly) ------------
ZONES = [
    [0, 1, 2, 3, 4, 5, 2, 0],        # 0 central plains
    [6, 7, 8, 9, 10, 6, 8, 7],       # 1 ashen verge
    [11, 12, 13, 10, 11, 13, 12, 9], # 2 the glass
    [20, 21, 22, 23, 20, 22, 21, 24],# 3 screaming reach
    [14, 15, 16, 17, 15, 17, 14, 16],# 4 the fen
    [11, 12, 18, 19, 12, 18, 11, 19],# 5 hollow waste
    [25, 26, 27, 28, 26, 28, 25, 27],# 6 deep waste
    [8, 9, 10, 11, 12, 13, 10, 8],   # 7 north coast
    [16, 17, 14, 15, 19, 16, 17, 15],# 8 drowned shelf
    # dungeon zones
    [0, 2, 4, 6, 7, 5, 3, 1],        # 9  Cinder
    [12, 13, 14, 15, 13, 16, 12, 14],# 10 Tide
    [20, 21, 22, 23, 24, 20, 22, 21],# 11 Storm
    [25, 26, 27, 28, 29, 25, 27, 26],# 12 Hollow
    [30, 31, 32, 33, 30, 32, 31, 33],# 13 Erebus
    [18, 19, 20, 21, 22, 19, 18, 20],# 14 Relay / Ossuary
]

# --- shops: list of item names -----------------------------------------------
SHOPS = [
    ["KNIFE", "BATON", "WORKSUIT", "HARD HAT", "MEDKIT", "ANTITOX"],
    ["MACHETE", "PLATE VEST", "HAND PLATE", "MEDKIT", "ANTITOX", "GRENADE"],
    ["RIVET GUN", "STAFF", "FIELD COAT", "VISOR RIG", "MEDKIT-2", "TP-CELL"],
    ["ARC SPIKE", "CERAMWEAVE", "BLAST WARD", "MEDKIT-2", "STIMPACK", "BEACON"],
    ["CARBINE", "FOCUS ROD", "EXO FRAME", "SEALED HOOD", "MEDKIT-2", "EXIT CHIP"],
    ["BREAKER", "PSI PRISM", "VOID MANTLE", "NULL FIELD", "MEDKIT-3", "EMP CHARGE"],
    ["PULSE LANCE", "STAR FIST", "ANCHOR MAIL", "MEDKIT-3", "STIMPACK", "TP-CELL"],
    ["MONOEDGE", "RAILGUN", "ARK SHELL", "ARK CROWN", "MEDKIT-3", "EMP CHARGE"],
]

INN_PRICES = [10, 30, 80, 200, 400, 800]


def sanity():
    for f in FORMATIONS:
        assert f[0] in MONSTER_ID, f
        assert f[2] is None or f[2] in MONSTER_ID, f
        assert 1 <= f[1] <= 4 and 0 <= f[3] <= 4 and f[1] + f[3] <= 4, f
    for z in ZONES:
        assert len(z) == 8
        for i in z:
            assert 0 <= i < len(FORMATIONS), i
    for s in SHOPS:
        for n in s:
            assert n in [i[0] for i in ITEMS], n
    assert len(ITEMS) <= 128, len(ITEMS)
    assert len(MONSTERS) <= 64, len(MONSTERS)
    assert len(TECHS) == 32
    for t in TECHS:
        assert 0 <= t[6] <= ST_ALL, t          # status masks never carry ST_DOWN
    for m in MONSTERS:
        ai, spec = m[10], m[11]
        assert ai in (0, 1, 2), m
        assert 0 <= spec < len(TECHS), m
        if ai:                                  # a caster must have a real tech
            assert TECHS[spec][3] or TECHS[spec][6], m
    for name, *_ in ITEMS + MONSTERS:
        assert len(name) <= 12, name
    return True


# --- monster art assignment ---------------------------------------------------
# Bosses stand in on existing large designs with their own palette, the way
# FF1 reuses monster art. Keys are entries in tools/monster_art.MONSTERS.
ART_OVERRIDE = {
    "MAGMA HULK":   "SCRAP_TITAN",
    "ABYSS WARDEN": "MAW",
    "RIFT SENTINL": "WARDEN_UNIT",
    # The Archon's two forms share one design because they are one being; the
    # design itself is its own (monster_art.ARCHON, the only 64x64 in the game).
    "THE ARCHON":   "ARCHON",
    "ARCHON PRIME": "ARCHON",
}


def art_key(name):
    if name in ART_OVERRIDE:
        return ART_OVERRIDE[name]
    return name.replace(" ", "_").replace("-", "_")
