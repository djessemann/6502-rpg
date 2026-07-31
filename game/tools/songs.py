"""THRENOS soundtrack — instruments, songs and sfx.

Authoring notes are at the top of tools/music.py. Everything here is source: the
binary the driver reads is generated from it by tools/build.py.

Register: bleak, spacious, slow-moving. Long triangle roots, sparse arpeggiated
pads, one melody line that carries the tune, percussion only where the scene
actually needs pressure (battle, boss, victory). Sixteen rows to a bar; a row is
a sixteenth note, so `tempo` frames-per-row sets the pulse: 13 is a slow 4/4,
7 is a hard-driving one.
"""

# --- envelopes (one byte per frame; $8v = hold at volume v) -------------------
ENVELOPES = {
    "lead":   [6, 10, 12, 13, 13, 0x8C],
    "pluck":  [15, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1, 0x80],
    "bell":   [15, 15, 13, 11, 10, 9, 8, 7, 6, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0x80],
    "soft":   [3, 6, 8, 9, 9, 0x88],
    "pad":    [2, 4, 6, 8, 9, 10, 10, 0x8A],
    "stab":   [15, 14, 12, 9, 6, 3, 0x80],
    "hold":   [0x8F],
    "tpluck": [15, 15, 15, 15, 12, 8, 4, 0x80],
    "kick":   [13, 11, 8, 5, 3, 1, 0x80],
    "snare":  [11, 9, 7, 6, 5, 4, 3, 2, 1, 0x80],
    "hat":    [7, 4, 2, 1, 0x80],
    "boom":   [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0x80],
}

D12, D25, D50, D75 = 0x00, 0x40, 0x80, 0xC0

# --- instruments (max 16; index = position) ----------------------------------
INSTRUMENTS = [
    {"name": "lead",   "env": "lead",   "duty": D25, "vib": (5, 1)},
    {"name": "lead2",  "env": "lead",   "duty": D50, "vib": (7, 0)},
    {"name": "pluck",  "env": "pluck",  "duty": D25},
    {"name": "bell",   "env": "bell",   "duty": D12, "vib": (3, 0)},
    {"name": "soft",   "env": "soft",   "duty": D12, "vib": (3, 1)},
    {"name": "pad",    "env": "pad",    "duty": D50},
    {"name": "arpm",   "env": "pad",    "duty": D25, "arp": 0x37},   # minor
    {"name": "arpM",   "env": "pad",    "duty": D25, "arp": 0x47},   # major
    {"name": "arp5",   "env": "pad",    "duty": D50, "arp": 0x57},   # sus/fifth
    {"name": "stab",   "env": "stab",   "duty": D50},
    {"name": "bass",   "env": "hold"},                               # triangle
    {"name": "bpluck", "env": "tpluck"},                             # triangle
    {"name": "kick",   "env": "kick",   "duty": 0x00},
    {"name": "snare",  "env": "snare",  "duty": 0x00},
    {"name": "hat",    "env": "hat",    "duty": 0x80},
    {"name": "boom",   "env": "boom",   "duty": 0x00},
]

SILENT = ["r:16"]


def rep(bar, n):
    return [bar] * n


# =============================================================================
# TITLE — the dead colony seen from orbit. Six two-bar chords, one long line.
# =============================================================================
TITLE = {
    "name": "TITLE", "tempo": 13, "loop_bar": 0,
    "p1": [
        "@lead r:16",
        "e4:8 a4:8",
        "c5:12 b4:4",
        "a4:16",
        "g4:8 e4:8",
        "c5:16",
        "b4:8 d5:8",
        "b4:16",
        "a4:12 c5:4",
        "f4:16",
        "e4:8 g#4:8",
        "b4:8 r:8",
    ],
    "p2": [
        "@arpm a3:16", "~:16",
        "@arpM f3:16", "~:16",
        "@arpM c4:16", "~:16",
        "@arpM g3:16", "~:16",
        "@arpM f3:16", "~:16",
        "@arpM e3:16", "~:16",
    ],
    "tri": [
        "@bass a2:12 e2:4", "a2:16",
        "f2:12 c3:4", "f2:16",
        "c3:12 g2:4", "c3:16",
        "g2:12 d3:4", "g2:16",
        "f2:12 c3:4", "f2:16",
        "e2:12 b2:4", "e2:16",
    ],
    "noise": rep("r:16", 12),
}

# =============================================================================
# LANDFALL — the town theme. Warmer, still tired. D dorian.
# =============================================================================
TOWN = {
    "name": "TOWN", "tempo": 12, "loop_bar": 0,
    "p1": [
        "@pluck d4:2 f4:2 a4:4 g4:4 f4:4",
        "e4:4 d4:4 f4:8",
        "bb3:2 d4:2 f4:4 d4:8",
        "c4:4 bb3:4 d4:8",
        "a3:2 c4:2 f4:4 e4:4 c4:4",
        "g3:4 e4:4 c4:8",
        "d4:2 e4:2 f4:4 a4:4 g4:4",
        "a4:8 e4:8",
        "f4:4 d4:4 bb3:8",
        "c4:4 a3:4 f4:8",
        "bb3:2 d4:2 g4:4 f4:4 d4:4",
        "e4:8 r:8",
    ],
    "p2": [
        "@soft f3:16", "a3:16",
        "d3:16", "f3:16",
        "c3:16", "e3:16",
        "f3:16", "c4:16",
        "d3:16", "c3:16",
        "bb3:16", "c#4:16",
    ],
    "tri": [
        "@bass d2:8 a2:8", "d2:8 f2:8",
        "bb1:8 f2:8", "bb1:8 d2:8",
        "f2:8 c3:8", "c2:8 g2:8",
        "d2:8 a2:8", "a1:8 e2:8",
        "bb1:8 f2:8", "f2:8 c3:8",
        "g1:8 d2:8", "a1:8 e2:8",
    ],
    "noise": rep("r:16", 12),
}

# =============================================================================
# OVERWORLD — walking a poisoned continent. Striding bass, wide melody.
# =============================================================================
OVERWORLD = {
    "name": "OVERWORLD", "tempo": 11, "loop_bar": 0,
    "p1": [
        "@lead e4:4 g4:4 b4:8",
        "a4:4 g4:4 e4:8",
        "c5:8 b4:8",
        "g4:4 e4:4 g4:8",
        "d5:4 b4:4 d5:8",
        "b4:8 g4:8",
        "a4:4 f#4:4 a4:8",
        "d5:16",
        "e5:4 d5:4 b4:8",
        "g4:4 a4:4 b4:8",
        "c5:8 a4:8",
        "e5:4 c5:4 a4:8",
        "b4:4 d#5:4 f#5:8",
        "d#5:8 b4:8",
        "e5:4 b4:4 g4:8",
        "e4:16",
    ],
    "p2": [
        "@arpm e3:16", "~:16",
        "@arpM c3:16", "~:16",
        "@arpM g3:16", "~:16",
        "@arpM d3:16", "~:16",
        "@arpm e3:16", "~:16",
        "@arpm a3:16", "~:16",
        "@arpM b2:16", "~:16",
        "@arpm e3:16", "~:16",
    ],
    "tri": [
        "@bass e2:4 e2:4 b2:4 e3:4", "e2:4 b2:4 g2:4 b2:4",
        "c2:4 c2:4 g2:4 c3:4", "c2:4 g2:4 e2:4 g2:4",
        "g2:4 g2:4 d3:4 g3:4", "g2:4 d3:4 b2:4 d3:4",
        "d2:4 d2:4 a2:4 d3:4", "d2:4 a2:4 f#2:4 a2:4",
        "e2:4 e2:4 b2:4 e3:4", "e2:4 b2:4 g2:4 b2:4",
        "a2:4 a2:4 e3:4 a3:4", "a2:4 e3:4 c3:4 e3:4",
        "b1:4 b1:4 f#2:4 b2:4", "b1:4 f#2:4 d#2:4 f#2:4",
        "e2:4 e2:4 b2:4 e3:4", "e2:8 b2:8",
    ],
    "noise": rep("r:16", 8) + rep("r:4 h:4 r:4 h:4", 8),
}

# =============================================================================
# DUNGEON — almost nothing. A drone, a tritone, something falling over.
# =============================================================================
DUNGEON = {
    "name": "DUNGEON", "tempo": 15, "loop_bar": 0,
    "p1": [
        "@bell r:16",
        "r:8 c5:8",
        "r:16",
        "r:8 gb4:8",
        "r:16",
        "r:8 ab4:8",
        "r:16",
        "r:4 g4:4 r:8",
    ],
    "p2": [
        "@pad c4:16", "~:16",
        "@pad ab3:16", "~:16",
        "@pad gb3:16", "~:16",
        "@pad g3:16", "~:16",
    ],
    "tri": [
        "@bass c2:16", "c2:12 eb2:4",
        "ab1:16", "ab1:12 c2:4",
        "gb1:16", "gb1:12 ab1:4",
        "g1:16", "g1:8 r:8",
    ],
    "noise": [
        "b:16", "r:16",
        "b:16", "r:16",
        "b:16", "r:16",
        "b:16", "r:8 h:4 r:4",
    ],
}

# =============================================================================
# BATTLE — pressure, not fun. Pumping root ostinato under a minor line.
# =============================================================================


def _drive(root, low="1", high="2"):
    return (f"@bass {root}{low}:2 {root}{high}:2 {root}{low}:2 {root}{high}:2 "
            f"{root}{low}:2 {root}{high}:2 {root}{low}:2 {root}{low}:2")


def _stab(note):
    return f"@stab r:2 {note}:2 r:2 {note}:2 r:2 {note}:2 r:2 {note}:2"


BATTLE = {
    "name": "BATTLE", "tempo": 8, "loop_bar": 0,
    "p1": [
        "@lead2 a4:4 e4:2 a4:2 c5:4 b4:4",
        "a4:4 g4:4 e4:8",
        "f4:4 c4:2 f4:2 a4:4 g4:4",
        "f4:8 e4:8",
        "g4:4 d4:2 g4:2 b4:4 a4:4",
        "g4:8 d4:8",
        "e4:4 g#4:4 b4:4 e5:4",
        "d5:8 b4:8",
        "a4:2 c5:2 e5:4 d5:4 c5:4",
        "b4:4 a4:4 e4:8",
        "f4:2 a4:2 c5:4 bb4:4 a4:4",
        "g4:8 e4:8",
        "d5:4 c5:4 b4:4 a4:4",
        "g#4:8 b4:8",
        "a4:4 e5:4 d5:4 c5:4",
        "b4:8 e4:8",
    ],
    "p2": [
        _stab("a3"), _stab("a3"),
        _stab("f3"), _stab("f3"),
        _stab("g3"), _stab("g3"),
        _stab("e3"), _stab("e3"),
        _stab("a3"), _stab("a3"),
        _stab("f3"), _stab("f3"),
        _stab("g3"), _stab("g3"),
        _stab("a3"), _stab("e3"),
    ],
    "tri": [
        _drive("a"), _drive("a"),
        _drive("f"), _drive("f"),
        _drive("g"), _drive("g"),
        _drive("e"), _drive("e"),
        _drive("a"), _drive("a"),
        _drive("f"), _drive("f"),
        _drive("g"), _drive("g"),
        _drive("a"), _drive("e"),
    ],
    "noise": rep("k:4 h:4 s:4 h:4", 15) + ["k:4 h:4 s:4 s:4"],
}

# =============================================================================
# BOSS — the same pressure, one step lower and chromatic. D phrygian.
# =============================================================================
BOSS = {
    "name": "BOSS", "tempo": 7, "loop_bar": 0,
    "p1": [
        "@lead2 d4:4 eb4:4 d4:4 a3:4",
        "bb3:8 a3:8",
        "d4:4 f4:4 gb4:4 f4:4",
        "e4:8 a4:8",
        "a4:4 bb4:4 a4:4 f4:4",
        "e4:8 d4:8",
        "f4:4 e4:4 eb4:4 d4:4",
        "d4:16",
        "d5:4 eb5:4 d5:4 a4:4",
        "bb4:8 a4:8",
        "d5:4 f5:4 gb5:4 f5:4",
        "e5:8 a5:8",
        "a5:4 g5:4 f5:4 e5:4",
        "d5:8 bb4:8",
        "a4:4 gb4:4 e4:4 eb4:4",
        "d4:16",
    ],
    "p2": [
        "@stab r:2 d3:2 r:2 d3:2 r:2 eb3:2 r:2 d3:2",
        "@stab r:2 d3:2 r:2 d3:2 r:2 eb3:2 r:2 d3:2",
        "@stab r:2 f3:2 r:2 f3:2 r:2 gb3:2 r:2 f3:2",
        "@stab r:2 f3:2 r:2 f3:2 r:2 e3:2 r:2 f3:2",
        _stab("a3"), _stab("a3"),
        "@stab r:2 d3:2 r:2 eb3:2 r:2 d3:2 r:2 a2:2",
        "@stab r:2 d3:2 r:2 d3:2 r:2 d3:2 r:2 d3:2",
        "@stab r:2 d3:2 r:2 d3:2 r:2 eb3:2 r:2 d3:2",
        "@stab r:2 d3:2 r:2 d3:2 r:2 eb3:2 r:2 d3:2",
        "@stab r:2 f3:2 r:2 f3:2 r:2 gb3:2 r:2 f3:2",
        "@stab r:2 f3:2 r:2 f3:2 r:2 e3:2 r:2 f3:2",
        _stab("a3"), _stab("a3"),
        "@stab r:2 d3:2 r:2 eb3:2 r:2 d3:2 r:2 a2:2",
        "@stab r:2 d3:2 r:2 d3:2 r:2 d3:2 r:2 d3:2",
    ],
    "tri": [
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:2 d1:2 d2:2 d1:2 f1:2 f1:2 d2:2 f1:2",
        "@bass e1:2 e1:2 e2:2 e1:2 f1:2 f1:2 e2:2 e1:2",
        _drive("a"), _drive("a"),
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:4 d2:4 a1:4 d1:4",
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:2 d1:2 d2:2 d1:2 f1:2 f1:2 d2:2 f1:2",
        "@bass e1:2 e1:2 e2:2 e1:2 f1:2 f1:2 e2:2 e1:2",
        _drive("a"), _drive("a"),
        "@bass d1:2 d1:2 d2:2 d1:2 eb1:2 eb1:2 d2:2 d1:2",
        "@bass d1:4 d2:4 a1:4 d1:4",
    ],
    "noise": rep("k:4 k:2 h:2 s:4 h:4", 15) + ["k:4 s:4 s:4 b:4"],
}

# =============================================================================
# VICTORY — brief relief, loops while the spoils are counted.
# =============================================================================
VICTORY = {
    "name": "VICTORY", "tempo": 10, "loop_bar": 0,
    "p1": [
        "@lead2 g4:2 g4:2 g4:2 c5:10",
        "e5:4 d5:4 e5:8",
        "f5:2 e5:2 d5:4 g4:8",
        "c5:16",
    ],
    "p2": [
        "@arpM c4:16", "~:16",
        "@arpM g3:16", "@arpM c4:16",
    ],
    "tri": [
        "@bass c2:8 g2:8", "c3:8 g2:8",
        "g1:8 d2:8", "c2:16",
    ],
    "noise": [
        "k:4 h:4 k:4 s:4", "k:4 h:4 k:4 s:4",
        "k:4 h:4 k:4 s:4", "k:4 s:4 s:4 b:4",
    ],
}

# =============================================================================
# FANFARE — very short, one-shot (item found, secret opened).
# =============================================================================
FANFARE = {
    "name": "FANFARE", "tempo": 9, "loop_bar": 0, "one_shot": True,
    "p1": [
        "@lead2 c5:2 e5:2 g5:2 c6:10",
        "b5:4 c6:12",
    ],
    "p2": ["@arpM c4:16", "~:16"],
    "tri": ["@bass c2:8 g2:8", "c2:16"],
    "noise": ["k:4 h:4 k:4 s:4", "s:2 s:2 s:2 s:2 b:8"],
}

# =============================================================================
# ENDING — the long exhale. Same harmonic world as TITLE, finally resolving.
# =============================================================================
ENDING = {
    "name": "ENDING", "tempo": 14, "loop_bar": 0,
    "p1": [
        "@soft r:8 e4:8",
        "g4:8 a4:8",
        "@lead c5:12 b4:4",
        "a4:16",
        "g4:8 e4:8",
        "f4:16",
        "e4:8 g4:8",
        "c5:16",
        "d5:8 c5:8",
        "b4:16",
        "a4:8 g4:8",
        "c5:16",
    ],
    "p2": [
        "@arpM c4:16", "~:16",
        "@arpm a3:16", "~:16",
        "@arpM f3:16", "~:16",
        "@arpM g3:16", "~:16",
        "@arpm a3:16", "~:16",
        "@arpM c4:16", "~:16",
    ],
    "tri": [
        "@bass c2:12 g2:4", "c2:16",
        "a1:12 e2:4", "a1:16",
        "f1:12 c2:4", "f1:16",
        "g1:12 d2:4", "g1:16",
        "a1:12 e2:4", "a1:16",
        "f1:12 g1:4", "c2:16",
    ],
    "noise": rep("r:16", 12),
}

# Song ids are assigned in this order, starting at 1 ($00 = "no request").
SONGS = [TITLE, TOWN, OVERWORLD, DUNGEON, BATTLE, BOSS, VICTORY, FANFARE, ENDING]


# =============================================================================
# SFX — steps are (frames, volume 0-15, duty 0-3 / noise mode, pitch)
# Pitch is a note name on the pulse channels and a noise period 0-15 on ch 3.
# =============================================================================
SFX = [
    {"name": "CURSOR", "ch": 1, "steps": [
        (2, 9, 2, "e6"), (3, 5, 2, "a6")]},
    {"name": "CONFIRM", "ch": 1, "steps": [
        (3, 10, 2, "c6"), (3, 10, 2, "e6"), (7, 8, 2, "a6")]},
    {"name": "CANCEL", "ch": 1, "steps": [
        (3, 9, 1, "a5"), (6, 6, 1, "e5")]},
    {"name": "HIT", "ch": 3, "steps": [
        (2, 12, 0, 10), (3, 8, 0, 12), (4, 4, 0, 13)]},
    {"name": "CRIT", "ch": 3, "steps": [
        (2, 15, 0, 6), (2, 13, 0, 8), (3, 10, 0, 10),
        (4, 7, 0, 12), (6, 3, 0, 14)]},
    {"name": "HEAL", "ch": 1, "steps": [
        (3, 8, 1, "c5"), (3, 9, 1, "g5"), (3, 10, 1, "c6"),
        (6, 8, 1, "e6"), (9, 4, 1, "g6")]},
    {"name": "TECH", "ch": 1, "steps": [
        (2, 10, 0, "g5"), (2, 10, 0, "b5"), (2, 10, 0, "d6"),
        (2, 10, 0, "g6"), (8, 7, 0, "b6")]},
    {"name": "LEVELUP", "ch": 1, "steps": [
        (4, 10, 2, "c5"), (4, 10, 2, "e5"), (4, 10, 2, "g5"),
        (4, 11, 2, "c6"), (10, 9, 2, "e6"), (12, 5, 2, "e6")]},
    {"name": "DOOR", "ch": 3, "steps": [
        (4, 8, 0, 14), (4, 6, 0, 15), (7, 4, 0, 15), (9, 2, 0, 15)]},
    {"name": "SAVE", "ch": 1, "steps": [
        (5, 8, 2, "a5"), (5, 8, 2, "c#6"), (10, 9, 2, "e6"), (10, 4, 2, "e6")]},
    {"name": "ENCOUNTER", "ch": 3, "steps": [
        (2, 14, 0, 4), (2, 12, 0, 5), (2, 11, 0, 6), (2, 10, 0, 7),
        (2, 9, 0, 8), (3, 8, 0, 9), (3, 6, 0, 10), (4, 4, 0, 11),
        (6, 2, 0, 12)]},
]
