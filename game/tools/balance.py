"""A pure-Python model of src/battle.s, for checking that the numbers in
gamedata.py produce fights a party can actually win.

This is a *mirror*, not a second design: every formula below is the one the 6502
code uses, down to the `rand(0..255) % 100` bias in the hit roll and the
`(28..35)/32` damage spread. If battle.s changes, change this with it — a
simulator that has drifted from the engine is worse than none.

    python3 tools/balance.py                  # every zone and every boss
    python3 tools/balance.py --trials 2000    # tighter numbers
    python3 tools/balance.py --zone 9         # one zone
    python3 tools/balance.py --bosses

Reported per encounter: win rate, mean rounds, and mean party HP lost as a
percentage of the party's maximum (a fight the party wins with 5% of its HP
gone is not really a fight; one that costs 70% is a wall).
"""
import argparse
import random
import statistics

import gamedata as G

ST_POISON, ST_STUN, ST_BLIND, ST_SILENCE = 1, 2, 4, 8

AI_MELEE, AI_MIXED, AI_CASTER = 0, 1, 2
AI_MIXED_ODDS, AI_CASTER_ODDS = 85, 160      # out of 256, as in battle.s

K_SCHOOL, K_COST, K_POWER, K_ELEM, K_TARGET, K_STATUS = range(6)
TG_ONE_ENEMY, TG_ALL_ENEMY = 0, 1


def rnd():
    """The engine's Random: one byte."""
    return random.randrange(256)


# --- the party ---------------------------------------------------------------
# Gear the party plausibly owns at a given level. The engine has no economy
# model, so this stands in for one: an item is assumed affordable once the
# party is about this deep, derived from its list price.
def unlock_level(price):
    if price <= 0:
        return 99                              # quest-only gear, never bought
    return 1 + int(price ** 0.5 / 4)


def best_item(kind, level, cls):
    best = 0
    for i, (nm, k, power, price, mask, eff) in enumerate(G.ITEMS):
        if k != kind or not (mask >> cls) & 1:
            continue
        if unlock_level(price) > level:
            continue
        if power > G.ITEMS[best][2] or best == 0:
            best = i
    return G.ITEMS[best][2] if best else 0


class Fighter:
    def __init__(self, name):
        self.name = name
        self.status = 0
        self.guard = False
        self.alive = True

    @property
    def hurt(self):
        return self.hpmax - self.hp


def make_party(classes, level):
    out = []
    for cls in classes:
        nm, base, grow, school, mask, vet = G.CLASSES[cls]
        f = Fighter(nm)
        f.cls, f.level, f.is_party = cls, level, True
        hp, tp, st, ag, vi, sp = [b + g * (level - 1) for b, g in zip(base, grow)]
        f.hpmax = f.hp = min(hp, 999)
        f.tpmax = f.tp = min(tp, 99)
        f.spi, f.agi = sp, ag
        f.atk = st // 2 + best_item(G.IT_WEAPON, level, cls)
        f.dfn = (vi // 4 + best_item(G.IT_ARMOUR, level, cls)
                 + best_item(G.IT_SHIELD, level, cls)
                 + best_item(G.IT_HELM, level, cls))
        f.evade = ag // 2
        f.elem, f.imm, f.boss = 0, 0, 0
        f.techs = sorted(t for lv, t in G.LEARN.get(cls, []) if lv <= level)
        out.append(f)
    return out


def make_enemies(form):
    t0, c0, t1, c1, flags = G.FORMATIONS[form]
    out = []
    for name, n in ((t0, c0), (t1, c1)):
        if not name:
            continue
        for _ in range(n):
            m = G.MONSTERS[G.MONSTER_ID[name]]
            f = Fighter(m[0])
            f.is_party = False
            f.hpmax = f.hp = m[1]
            f.atk, f.dfn, f.agi, f.spi = m[2], m[3], m[4], m[5]
            f.xp, f.gold = m[6], m[7]
            f.elem, f.imm, f.ai, f.spec, f.boss = m[8], m[9], m[10], m[11], m[12]
            f.evade = 4
            f.techs = []
            out.append(f)
    return out[:4]


# --- the engine's arithmetic --------------------------------------------------
def physical(src, tgt):
    """PhysicalAttack."""
    chance = max(40, min(99, 168 - tgt.evade))
    if src.status & ST_BLIND:
        chance >>= 1
    if rnd() % 100 >= chance:
        return 0
    base = max(1, src.atk - tgt.dfn // 2)
    dmg = max(1, base * ((rnd() & 7) - 4 + 32) // 32)
    if rnd() & 31 == 0:
        dmg *= 2
    if tgt.guard:
        dmg //= 2
    return dmg


def tech_damage(src, tgt, tech):
    """CastTech / EnemyTech + TechDamageOne."""
    dmg = max(1, tech[K_POWER] + src.spi // 2 - tgt.spi // 4)
    el = tech[K_ELEM]
    if el:
        if el == tgt.elem:
            dmg *= 2
        elif el == tgt.imm:
            dmg = 0
    return dmg


def try_inflict(tgt, tech):
    """TryInflict: about half, halved again on a boss."""
    mask = tech[K_STATUS]
    if not mask or not tgt.alive or rnd() >= 128:
        return
    if tgt.boss and rnd() >= 128:
        return
    tgt.status |= mask


def hurt(tgt, dmg):
    tgt.hp = max(0, tgt.hp - dmg)
    if tgt.hp == 0:
        tgt.alive = False


def heal(tgt, amount):
    tgt.hp = min(tgt.hpmax, tgt.hp + amount)


def tech_of(i):
    nm, sch, tier, pw, el, tg, st = G.TECHS[i]
    return (sch, tier, min(pw, 255), el, tg, st)


# --- turns --------------------------------------------------------------------
def enemy_turn(src, party, enemies, log):
    live = [p for p in party if p.alive]
    if not live:
        return
    if src.ai and not src.status & ST_SILENCE:
        odds = AI_CASTER_ODDS if src.ai == AI_CASTER else AI_MIXED_ODDS
        if rnd() < odds:
            tech = tech_of(src.spec)
            if tech[K_TARGET] >= 2:                     # a support special
                if any(e.alive and e.hurt for e in enemies):
                    for e in enemies:
                        if e.alive:
                            heal(e, tech[K_POWER])
                    log.append(f"{src.name} mends")
                    return
            else:
                targets = live if tech[K_TARGET] == TG_ALL_ENEMY \
                    else [random.choice(live)]
                for t in targets:
                    hurt(t, tech_damage(src, t, tech))
                    try_inflict(t, tech)
                log.append(f"{src.name} casts {G.TECHS[src.spec][0]}")
                return
    tgt = random.choice(live)
    hurt(tgt, physical(src, tgt))


def party_turn(src, party, enemies, log):
    """The simulator's own policy, not the engine's: the engine asks a human.
    A reasonable-but-not-perfect player - heal when someone is badly hurt, cure
    what is worth curing, blast with the biggest tech that is affordable."""
    live = [e for e in enemies if e.alive]
    if not live:
        return
    known = [tech_of(t) for t in src.techs]
    afford = [(t, tech_of(t)) for t in src.techs if tech_of(t)[K_COST] <= src.tp]

    hurtest = min((p for p in party if p.alive), key=lambda p: p.hp / p.hpmax,
                  default=None)
    if not src.status & ST_SILENCE:
        # heal first
        if hurtest and hurtest.hp * 2 < hurtest.hpmax:
            heals = [(t, k) for t, k in afford if k[K_TARGET] >= 2 and k[K_POWER]]
            if heals:
                t, k = max(heals, key=lambda tk: tk[1][K_POWER])
                src.tp -= k[K_COST]
                for p in party:
                    if p.alive:
                        heal(p, k[K_POWER])
                log.append(f"{src.name} heals")
                return
        # then cure, if anyone is carrying something worth clearing
        bad = [p for p in party if p.alive and p.status & (ST_POISON | ST_BLIND)]
        if bad:
            cures = [(t, k) for t, k in afford
                     if k[K_TARGET] >= 2 and not k[K_POWER] and k[K_STATUS]]
            if cures:
                t, k = max(cures, key=lambda tk: bin(tk[1][K_STATUS]).count("1"))
                src.tp -= k[K_COST]
                for p in party:
                    if p.alive:
                        p.status &= ~k[K_STATUS]
                log.append(f"{src.name} cures")
                return
        # then the biggest blast that is worth the TP
        blasts = [(t, k) for t, k in afford if k[K_TARGET] < 2 and k[K_POWER]]
        if blasts:
            def value(tk):
                k = tk[1]
                return k[K_POWER] * (len(live) if k[K_TARGET] == TG_ALL_ENEMY else 1)
            t, k = max(blasts, key=value)
            if k[K_POWER] + src.spi // 2 > src.atk:
                src.tp -= k[K_COST]
                targets = live if k[K_TARGET] == TG_ALL_ENEMY else [live[0]]
                for e in targets:
                    hurt(e, tech_damage(src, e, k))
                    try_inflict(e, k)
                log.append(f"{src.name} casts {G.TECHS[t][0]}")
                return
    tgt = live[0]
    hurt(tgt, physical(src, tgt))


def fight(party, enemies, max_rounds=60, log=None):
    log = log if log is not None else []
    for rounds in range(1, max_rounds + 1):
        order = sorted(range(len(party) + len(enemies)),
                       key=lambda i: -((party + enemies)[i].agi + (rnd() & 15)))
        all_ = party + enemies
        poisoned = set()
        for i in order:
            f = all_[i]
            if not f.alive:
                continue
            if f.status & ST_POISON and i not in poisoned:
                poisoned.add(i)
                hurt(f, max(1, f.hpmax // 8))
                if not f.alive:
                    continue
            if f.status & ST_STUN:
                f.status &= ~ST_STUN
                continue
            if f.is_party:
                party_turn(f, party, enemies, log)
            else:
                enemy_turn(f, party, enemies, log)
            if not any(e.alive for e in enemies):
                return True, rounds
            if not any(p.alive for p in party):
                return False, rounds
        for f in all_:
            f.guard = False
    return False, max_rounds


# --- runs ---------------------------------------------------------------------
DEFAULT_CLASSES = [0, 1, 2, 3]          # SOLDIER RANGER MEDIC PSION

# --- what level the progression actually implies ------------------------------
# Not a guess: the route below is walked, the XP each zone's formations pay out
# is accumulated, and XP_TABLE decides the level. FIGHTS_PER_ZONE is the one
# assumption - roughly how many random encounters a zone or dungeon arc costs
# at the engine's encounter rate.
FIGHTS_PER_ZONE = 30

ROUTE = [           # (zone, boss fought at the end of it, if any)
    (0, None), (9, "MAGMA HULK"), (1, None), (7, None),
    (10, "ABYSS WARDEN"), (2, None), (5, None),
    (11, "SERAPH"), (4, None), (8, None),
    (12, "NULLCOLOSSUS"), (3, None), (14, "RIFT SENTINL"),
    (6, None), (13, "THE ARCHON"),
]


def _form_xp(form):
    t0, c0, t1, c1, _ = G.FORMATIONS[form]
    xp = c0 * G.MONSTERS[G.MONSTER_ID[t0]][6]
    if t1:
        xp += c1 * G.MONSTERS[G.MONSTER_ID[t1]][6]
    return xp


def _level_for(xp):
    lvl = 1
    while lvl < 30 and xp >= G.XP_TABLE[lvl]:
        lvl += 1
    return lvl


def progression(fights=FIGHTS_PER_ZONE):
    """-> ({zone: level on arrival}, {boss name: level when fought})."""
    zone_level, boss_level, xp = {}, {}, 0
    for zone, boss in ROUTE:
        zone_level.setdefault(zone, _level_for(xp))
        xp += fights * statistics.mean(_form_xp(f) for f in set(G.ZONES[zone]))
        if boss:
            boss_level[boss] = _level_for(xp)
            xp += G.MONSTERS[G.MONSTER_ID[boss]][6]
    boss_level["ARCHON PRIME"] = boss_level.get("THE ARCHON", 1)
    return zone_level, boss_level


ZONE_LEVEL, BOSS_LEVEL = progression()


def run(form, level, trials, classes=DEFAULT_CLASSES):
    wins, rounds, lost = 0, [], []
    for _ in range(trials):
        party = make_party(classes, level)
        total = sum(p.hpmax for p in party)
        won, n = fight(party, make_enemies(form))
        wins += won
        rounds.append(n)
        lost.append(100.0 * sum(p.hpmax - p.hp for p in party) / total)
    return (100.0 * wins / trials, statistics.mean(rounds),
            statistics.mean(lost))


def label(form):
    t0, c0, t1, c1, _ = G.FORMATIONS[form]
    s = f"{c0}x{t0}"
    if t1:
        s += f" + {c1}x{t1}"
    return s


def report(rows, trials):
    print(f"{'encounter':34} {'lvl':>3} {'win%':>6} {'rounds':>7} {'hp lost%':>9}")
    print("-" * 63)
    for tag, form, level in rows:
        w, r, l = run(form, level, trials)
        flag = ""
        if w < 90:
            flag = "  <-- losable"
        if w < 60:
            flag = "  <-- WALL"
        if w > 99.5 and l < 8:
            flag = "  <-- trivial"
        print(f"{tag:34} {level:3} {w:6.1f} {r:7.1f} {l:9.1f}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=400)
    ap.add_argument("--zone", type=int)
    ap.add_argument("--form", type=int)
    ap.add_argument("--level", type=int)
    ap.add_argument("--bosses", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    random.seed(a.seed)
    G.sanity()

    if a.form is not None:
        report([(label(a.form), a.form, a.level or 10)], a.trials)
        return

    rows = []
    if a.zone is not None:
        zones = [a.zone]
    elif a.bosses:
        zones = []
    else:
        zones = range(len(G.ZONES))
    for z in zones:
        lvl = a.level or ZONE_LEVEL[z]
        for form in sorted(set(G.ZONES[z])):
            rows.append((f"z{z}: {label(form)}", form, lvl))
    if not a.zone and (a.bosses or not rows):
        for i, f in enumerate(G.FORMATIONS):
            if f[4] & 1:
                rows.append((f"BOSS {f[0]}", i, a.level or BOSS_LEVEL[f[0]]))
    elif not a.zone and a.form is None and not a.bosses:
        for i, f in enumerate(G.FORMATIONS):
            if f[4] & 1:
                rows.append((f"BOSS {f[0]}", i, a.level or BOSS_LEVEL[f[0]]))
    report(rows, a.trials)


if __name__ == "__main__":
    main()
