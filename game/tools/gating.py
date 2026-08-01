"""Progression: which door opens when, and what relighting an Anchor gives you.

The script in `script_text.py` was written for a gated world -- Crew Chief Vask
hands you the PASSKEY "for the Sunken Causeway south", Dockmaster Ila hands you
the SKIFF, Tower Chief Ren hands you the LIFT CODE so "ridges and chasms stop
being walls" -- but nothing read the flags, so every dungeon stood open from the
first step and the four arcs had no order. This file is that order, as data the
engine reads.

Two mechanisms, both driven from the same story flags the boss triggers set:

  gates   a map you cannot enter until a flag is set. The overworld warp
          refuses and says why.
  boons   a vehicle granted the moment a flag is set. The grav-lift is the one
          that matters: the Rift basin is ringed with RIDGE, so Lastport's
          endgame shops and Erebus itself are behind it.

Story-flag numbering comes from `areas.trig()` call order and is asserted here,
so moving a trigger cannot silently re-point a gate at the wrong Anchor.
"""

# The four Anchor cores, in the order the script sends the player through them.
# Each is the story flag that its boss victory sets.
CINDER_CORE = 1
TIDE_CORE = 3
STORM_CORE = 5
HOLLOW_CORE = 7

# The flag a trigger sets must belong to the map named here, or the gates below
# are pointing at the wrong thing. `check_gating` enforces it.
CORE_MAP = {CINDER_CORE: "CINDER3", TIDE_CORE: "TIDE3",
            STORM_CORE: "STORM3", HOLLOW_CORE: "HOLLOW3"}

# map name -> (story flag required to enter, message shown when refused)
GATES = {
    "CAUSEWAY": (CINDER_CORE, "MSG_SYS_DOOR_PASSKEY"),
    "TIDE1":    (CINDER_CORE, "MSG_SYS_DOOR_SEALED"),
    "STORM1":   (TIDE_CORE,   "MSG_SYS_DOOR_SEALED"),
    "RELAY1":   (STORM_CORE,  "MSG_SYS_DOOR_SEALED"),
    # optional side dungeons, but not at level 1: the Ossuary sat open from the
    # first step, which put a mid-game encounter zone one walk from the start
    "OSSUARY1": (CINDER_CORE, "MSG_SYS_DOOR_SEALED"),
    "HOLLOW1":  (STORM_CORE,  "MSG_SYS_DOOR_SEALED"),
    "EREBUS1":  (HOLLOW_CORE, "MSG_SYS_DOOR_RIFTKEY"),
}

# story flag -> the `vehicles` bits it grants (bit 0 skiff, bit 1 grav-lift)
BOONS = {
    TIDE_CORE:  0b01,       # Dockmaster Ila's skiff: shallow water
    STORM_CORE: 0b10,       # Tower Chief Ren's lift code: ridges and chasms
}

N_FLAGS = 32


def emit(f, map_names, msg_ids, trig_flags):
    """Write gate_flag / gate_msg / boon_tab into the engine's read-only bank."""
    check(map_names, trig_flags)
    f.write(".export gate_flag, gate_msg, boon_tab\n")

    flags, msgs = [], []
    for n in map_names:
        flag, msg = GATES.get(n, (0xFF, "MSG_SYS_DOOR_SEALED"))
        flags.append(flag)
        msgs.append(msg_ids[msg])
    f.write("gate_flag:\n    .byte " + ",".join(f"${v:02X}" for v in flags) + "\n")
    f.write("gate_msg:\n    .byte " + ",".join(f"${v & 255:02X}" for v in msgs) + "\n")

    boons = [BOONS.get(i, 0) for i in range(N_FLAGS)]
    f.write("boon_tab:\n    .byte " + ",".join(f"${v:02X}" for v in boons) + "\n")


def check(map_names, trig_flags):
    """trig_flags: {map name: [story flags its triggers own]}."""
    for flag, want in CORE_MAP.items():
        owner = [n for n, fs in trig_flags.items() if flag in fs]
        if owner != [want]:
            raise ValueError(
                f"story flag {flag} should belong to {want}'s Anchor core but "
                f"belongs to {owner or 'nothing'} -- a trigger moved, and the "
                f"gates in tools/gating.py now point at the wrong Anchor")
    for n in GATES:
        if n not in map_names:
            raise ValueError(f"gating.py gates {n}, which is not a map")
