"""Emit the numeric game data into the BANK_TABLES data bank + constants."""
import gamedata as G
import font

MON_REC = 16
ITEM_REC = 8
TECH_REC = 7
CLASS_REC = 16
NAME_LEN = 13          # 12 characters + $FF


def _name(s):
    b = font.encode(s)
    b += [0xFF]
    b += [0xFF] * (NAME_LEN - len(b))
    return b[:NAME_LEN]


def emit(f, base_bank, mon_sizes=None):
    G.sanity()
    f.write(f'.segment "BANK{base_bank:02d}"\n')
    exports = ["mon_tab", "mon_names", "item_tab", "item_names", "tech_tab",
               "tech_names", "class_tab", "class_names", "xp_tab", "form_tab",
               "zone_tab", "shop_tab", "shop_len", "inn_tab", "learn_tab",
               "class_vets",
               "learn_idx"]
    for e in exports:
        f.write(f".export {e}\n")

    def block(label, rows):
        f.write(f"{label}:\n")
        for r in rows:
            f.write("    .byte " + ",".join(f"${b:02X}" for b in r) + "\n")

    # --- monsters ------------------------------------------------------------
    mon = []
    for idx, (nm, hp, atk, dfn, agi, spi, xp, gold, weak, imm, ai, spec,
              boss) in enumerate(G.MONSTERS):
        size = mon_sizes[idx] if mon_sizes else 4
        mon.append([hp & 255, hp >> 8, atk, dfn, agi, spi,
                    xp & 255, xp >> 8, gold & 255, gold >> 8,
                    weak, imm, ai, spec, boss, size])
    block("mon_tab", mon)
    block("mon_names", [_name(m[0]) for m in G.MONSTERS])

    # --- items ---------------------------------------------------------------
    # byte 7 is the status mask an effect-2 (cure) item clears.
    items = []
    for (nm, kind, power, price, mask, eff) in G.ITEMS:
        items.append([kind, power & 255, power >> 8, price & 255, price >> 8,
                      mask, eff, G.ST_ALL if eff == 2 else 0])
    block("item_tab", items)
    block("item_names", [_name(i[0]) for i in G.ITEMS])

    # --- techs ---------------------------------------------------------------
    # byte 5 is the status mask: inflicted by an offensive tech, cured by a
    # support one (see the TECHS comment in gamedata.py).
    block("tech_tab", [[sch, tier, min(pw, 255), el, tg, st, rv]
                       for (nm, sch, tier, pw, el, tg, st, rv) in G.TECHS])
    block("tech_names", [_name(t[0]) for t in G.TECHS])

    # --- classes -------------------------------------------------------------
    cls = []
    for (nm, base, grow, school, mask, vet) in G.CLASSES:
        cls.append(list(base) + list(grow) + [school, mask, 0, 0])
    block("class_tab", cls)
    block("class_names", [_name(c[0]) for c in G.CLASSES])
    # the veteran title each class grows into; the muster screen shows it
    block("class_vets", [_name(c[5]) for c in G.CLASSES])

    # --- xp curve (3 bytes per level) ---------------------------------------
    block("xp_tab", [[x & 255, (x >> 8) & 255, (x >> 16) & 255]
                     for x in G.XP_TABLE])

    # --- formations ----------------------------------------------------------
    forms = []
    for (t0, c0, t1, c1, flags) in G.FORMATIONS:
        forms.append([G.MONSTER_ID[t0], c0,
                      G.MONSTER_ID[t1] if t1 else 0, c1, flags])
    block("form_tab", forms)
    block("zone_tab", G.ZONES)

    # --- shops ---------------------------------------------------------------
    item_id = {n[0]: i for i, n in enumerate(G.ITEMS)}
    shops = []
    for s in G.SHOPS:
        row = [item_id[n] for n in s]
        row += [0] * (8 - len(row))
        shops.append(row)
    block("shop_tab", shops)
    f.write("shop_len:\n    .byte " + ",".join(str(len(s)) for s in G.SHOPS) + "\n")
    f.write("inn_tab:\n    .word " + ",".join(str(p) for p in G.INN_PRICES) + "\n")

    # --- tech learn table: per class, pairs of (level, tech), $FF terminated --
    f.write("learn_idx:\n")
    for c in range(len(G.CLASSES)):
        f.write(f"    .addr learn_c{c}\n")
    f.write("learn_tab:\n")
    for c in range(len(G.CLASSES)):
        f.write(f"learn_c{c}:\n")
        entries = sorted(G.LEARN.get(c, []))
        if entries:
            f.write("    .byte " + ",".join(
                f"{lv},{t}" for lv, t in entries) + ",$FF\n")
        else:
            f.write("    .byte $FF\n")


def emit_consts(f):
    f.write(f"N_ITEMS = {len(G.ITEMS)}\n")
    f.write(f"N_MONSTERS = {len(G.MONSTERS)}\n")
    f.write(f"N_TECHS = {len(G.TECHS)}\n")
    f.write(f"N_CLASSES = {len(G.CLASSES)}\n")
    f.write(f"N_FORMS = {len(G.FORMATIONS)}\n")
    f.write(f"MON_REC = {MON_REC}\n")
    f.write(f"ITEM_REC = {ITEM_REC}\n")
    f.write(f"TECH_REC = {TECH_REC}\n")
    f.write(f"CLASS_REC = {CLASS_REC}\n")
    f.write(f"NAME_LEN = {NAME_LEN}\n")
    for i, (nm, *_rest) in enumerate(G.ITEMS):
        key = "IT_" + "".join(ch if ch.isalnum() else "_" for ch in nm.upper())
        f.write(f"{key} = {i}\n")
    for i, m in enumerate(G.MONSTERS):
        key = "MON_" + "".join(ch if ch.isalnum() else "_" for ch in m[0].upper())
        f.write(f"{key} = {i}\n")
    for i, (t0, c0, t1, c1, fl) in enumerate(G.FORMATIONS):
        if fl & 1:
            key = "FORM_" + "".join(ch if ch.isalnum() else "_" for ch in t0.upper())
            f.write(f"{key} = {i}\n")


def size_estimate():
    G.sanity()
    return (len(G.MONSTERS) * (MON_REC + NAME_LEN) +
            len(G.ITEMS) * (ITEM_REC + NAME_LEN) +
            len(G.TECHS) * (TECH_REC + NAME_LEN) +
            len(G.CLASSES) * (CLASS_REC + NAME_LEN) +
            len(G.XP_TABLE) * 3 + len(G.FORMATIONS) * 5 +
            len(G.ZONES) * 8 + len(G.SHOPS) * 8 + 64)
