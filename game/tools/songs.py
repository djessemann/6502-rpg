"""THRENOS soundtrack — instruments, songs and sfx.

Authoring notes are at the top of tools/music.py. Everything here is source: the
binary the driver reads is generated from it by tools/build.py.
Render and audit it with tools/music_render.py (WAVs + piano rolls + note lists).

Register: bleak, but written as songs, not as ambience. Every track has a tune
you could hum, laid out as four-bar phrases with an A section, a contrasting B
section and a return; the harmony moves at least once a bar; and the last bar of
every loop leads back into the first, so the seam is a cadence and not a hole.
Pulse 1 carries the melody, pulse 2 comps or answers it (never just a held pad),
the triangle walks the bass, and the noise channel builds and fills.

Sixteen rows to a bar; a row is a sixteenth, so 4 = a quarter, 6 = a dotted
quarter, 2 = an eighth. `tempo` is frames-per-row: 13 is a slow 4/4, 7 is a
hard-driving one.
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


# --- accompaniment figures ---------------------------------------------------
def stab4(a, b, c, d):
    """Pulse-2 offbeat stab through four chord tones (the battle/boss comp)."""
    return f"@stab r:2 {a}:2 r:2 {b}:2 r:2 {c}:2 r:2 {d}:2"


def comp(a, b):
    """Pulse-2 offbeat two-note chord, twice a bar (the town comp)."""
    return f"@pluck r:4 {a}:2 {b}:2 r:4 {a}:2 {b}:2"


def roll(a, b, c):
    """Pulse-2 rolling eighth arpeggio a-c-b-c, twice a bar (the road comp)."""
    return f"@pluck {a}:2 {c}:2 {b}:2 {c}:2 {a}:2 {c}:2 {b}:2 {c}:2"


def walk(root, fifth, oct_, top=None):
    """Triangle stride: root, fifth, octave, and a fourth note."""
    return f"@bass {root}:4 {fifth}:4 {oct_}:4 {top or fifth}:4"


def drive(root, low="1", high="2"):
    """Triangle octave-pumping ostinato — one bar of eighths."""
    return (f"@bass {root}{low}:2 {root}{high}:2 {root}{low}:2 {root}{high}:2 "
            f"{root}{low}:2 {root}{high}:2 {root}{low}:2 {root}{low}:2")


def chrom(a, b):
    """Triangle ostinato that leans on a chromatic neighbour (BOSS)."""
    return (f"@bass {a}1:2 {a}1:2 {a}2:2 {a}1:2 "
            f"{b}1:2 {b}1:2 {a}2:2 {a}1:2")


# =============================================================================
# TITLE — the dead colony seen from orbit. A minor, 12 bars: A A' B, one chord
# per bar. The hook is bar 0-1: a stepwise climb that reaches for a minor sixth
# (A4 -> F5) and falls back. Bar 11 lands on E4, a rising fourth below the A4
# that opens bar 0, so the loop closes on a cadence.
# =============================================================================
TITLE = {
    "name": "TITLE", "tempo": 13, "loop_bar": 0,
    "p1": [
        "@lead a4:6 b4:2 c5:4 e5:4",       # A   Am
        "f5:8 e5:4 c5:4",                  #     F   <- the reach
        "d5:6 c5:2 b4:4 g4:4",             #     C
        "a4:12 r:4",                       #     G   half cadence, then breath
        "a4:6 b4:2 c5:4 e5:4",             # A'  Am
        "f5:8 e5:8",                       #     F
        "d5:4 c5:4 a4:4 b4:4",             #     Dm
        "e5:8 g#4:8",                      #     E   the cry: a minor sixth down
        "a4:16",                           # B   Am  arrival, held
        "c5:6 d5:2 e5:8",                  #     C
        "f5:4 e5:4 d5:4 c5:4",             #     F   the descent
        "b4:8 g#4:4 e4:4",                 #     E   -> A4
    ],
    "p2": [
        "@arpm a3:16", "@arpM f3:16", "@arpM c4:16", "@arpM g3:16",
        "@arpm a3:16", "@arpM f3:16", "@arpm d3:16", "@arpM e3:16",
        "@soft e4:4 d4:4 c4:4 b3:4",       # answers the held A4
        "@arpM c4:16", "@arpM f3:16", "@arpM e3:16",
    ],
    "tri": [
        "@bass a2:8 e2:8", "f2:8 c3:8", "c2:8 g2:8", "g2:8 d3:8",
        "a2:8 e2:8", "f2:8 c3:8", "d2:8 a2:8", "e2:8 b2:8",
        "a2:12 g2:4", "c2:8 g2:8", "f2:8 c3:8", "e2:8 g#2:4 b2:4",
    ],
    "noise": rep("r:16", 12),
}

# =============================================================================
# LANDFALL — the town theme. D dorian, 12 bars, three four-bar phrases with the
# opening figure returning at bar 6. The melody works, so it is left alone except
# for the last bar, which used to be a rest: it is now an A7 arpeggio walking up
# into the loop. Pulse 2 comps on the offbeats instead of holding a pad, and a
# soft hat enters at bar 4 so the arrangement grows across the loop.
# =============================================================================
TOWN = {
    "name": "TOWN", "tempo": 11, "loop_bar": 0,
    "p1": [
        "@pluck d4:2 f4:2 a4:4 g4:4 f4:4",  # Dm
        "e4:4 d4:4 f4:8",                   # Dm
        "bb3:2 d4:2 f4:4 d4:8",             # Bb
        "c4:4 bb3:4 d4:8",                  # Bb
        "a3:2 c4:2 f4:4 e4:4 c4:4",         # F
        "g3:4 e4:4 c4:8",                   # C
        "d4:2 e4:2 f4:4 a4:4 g4:4",         # Dm  the opening figure returns
        "a4:8 e4:8",                        # Am
        "f4:4 d4:4 bb3:8",                  # Bb
        "c4:4 a3:4 f4:8",                   # F
        "bb3:2 d4:2 g4:4 f4:4 d4:4",        # G   the dorian major IV
        "c#4:4 e4:4 g4:4 a4:4",             # A7  -> D4
    ],
    "p2": [
        comp("f3", "a3"), comp("f3", "a3"),
        comp("d3", "f3"), comp("d3", "bb3"),
        comp("a3", "c4"), comp("e3", "g3"),
        comp("f3", "a3"), comp("c4", "e4"),
        comp("d3", "f3"), comp("a3", "c4"),
        comp("b3", "d4"), comp("c#4", "e4"),
    ],
    "tri": [
        "@bass d2:8 a2:8", "d2:8 f2:8",
        "bb1:8 f2:8", "bb1:8 d2:8",
        "f2:8 c3:8", "c2:8 g2:8",
        "d2:8 a2:8", "a1:8 e2:8",
        "bb1:8 f2:8", "f2:8 c3:8",
        "g1:8 d2:8", "a1:8 e2:8",
    ],
    "noise": rep("r:16", 4) + rep("r:2 h:2 r:2 h:2 r:2 h:2 r:2 h:2", 7)
             + ["r:2 h:2 r:2 h:2 r:2 h:2 h:2 h:2"],
}

# =============================================================================
# OVERWORLD — walking a poisoned continent. E minor, 16 bars: A (0-3), A' (4-7),
# B (8-11, which lifts into D major and B7), A'' (12-15). The hook is the rising
# fourth B4->E5 on a dotted quarter that opens the tune and closes it, so the
# loop seam is that same fourth. Pulse 2 rolls eighths under the A sections and
# switches to sustained chords for B; the drums build in four stages and drop out
# at the loop, which is what makes a 43-second cycle feel like it has a shape.
# =============================================================================
OVERWORLD = {
    "name": "OVERWORLD", "tempo": 10, "loop_bar": 0,
    "p1": [
        "@lead b4:6 e5:2 d5:4 b4:4",       # A    Em   the hook
        "c5:6 b4:2 a4:4 g4:4",             #      C
        "b4:4 d5:4 g5:8",                  #      G    peak, held
        "f#5:6 e5:2 d5:8",                 #      D
        "b4:6 e5:2 d5:4 b4:4",             # A'   Em
        "c5:6 b4:2 a4:4 c5:4",             #      C
        "a4:4 c5:4 e5:6 d5:2",             #      Am
        "b4:8 a4:4 f#4:4",                 #      B    half cadence
        "g4:4 a4:2 b4:2 d5:4 b4:4",        # B    G    new rhythm: eighths
        "a4:4 b4:2 c#5:2 d5:8",            #      D    C# lifts out of E minor
        "e5:4 d5:4 b4:4 g4:4",             #      Em
        "f#4:4 a4:4 b4:4 d#5:4",           #      B7   D#5 leans on the return
        "e5:6 d5:2 b4:4 g4:4",             # A''  Em
        "c5:4 b4:4 a4:8",                  #      C
        "a4:4 b4:4 c5:4 d5:4",             #      Am
        "e5:4 d5:4 b4:4 f#4:4",            #      B7   -> B4
    ],
    "p2": [
        roll("e3", "g3", "b3"), roll("c3", "e3", "g3"),
        roll("g3", "b3", "d4"), roll("d3", "f#3", "a3"),
        roll("e3", "g3", "b3"), roll("c3", "e3", "g3"),
        roll("a3", "c4", "e4"), roll("b2", "d#3", "f#3"),
        "@arpM g3:16", "@arpM d3:16", "@arpm e3:16", "@arpM b2:16",
        roll("e3", "g3", "b3"), roll("c3", "e3", "g3"),
        roll("a3", "c4", "e4"),
        "@pluck b2:2 f#3:2 d#3:2 f#3:2 b2:2 d#3:2 f#3:2 a3:2",
    ],
    "tri": [
        walk("e2", "b2", "e3"), walk("c2", "g2", "c3"),
        walk("g1", "d2", "g2"), walk("d2", "a2", "d3"),
        walk("e2", "b2", "e3"), walk("c2", "g2", "c3"),
        walk("a1", "e2", "a2"), walk("b1", "f#2", "b2"),
        walk("g1", "d2", "g2", "b2"), walk("d2", "a2", "d3", "f#2"),
        walk("e2", "b2", "e3", "g2"), walk("b1", "f#2", "a2", "d#2"),
        walk("e2", "b2", "e3"), walk("c2", "g2", "c3"),
        walk("a1", "e2", "a2", "c3"), walk("b1", "d#2", "f#2", "a2"),
    ],
    "noise": (rep("r:16", 4)                         # bare
              + rep("r:4 h:4 r:4 h:4", 4)            # hats
              + rep("k:4 h:4 k:4 h:4", 4)            # + kick
              + rep("k:4 h:4 s:4 h:4", 3)            # + backbeat
              + ["k:4 h:4 s:4 s:2 s:2"]),            # fill into the loop
}

# =============================================================================
# THE DEEP — the dungeon theme. C minor pulled sideways by a G-flat: the tritone
# is the tune, not just the drone. 12 bars, and unlike the old drone-only version
# it has an actual line — a three-note motif (C5 B4 / G-flat4) that is answered a
# step higher, then a single climb at bar 8 that is the only time the track lifts
# its head. Bar 11 hangs on B4, unresolved, straight back into the C drone.
# =============================================================================
DUNGEON = {
    "name": "DUNGEON", "tempo": 14, "loop_bar": 0,
    "p1": [
        "@soft r:16",                      # Cm   the drone alone
        "r:4 c5:8 b4:4",                   # Cm   the motif: semitone fall
        "gb4:12 r:4",                      # Ab   the tritone
        "r:4 ab4:4 g4:8",                  # Ab
        "r:4 db5:8 c5:4",                  # Gb   the motif, a step up
        "gb4:8 f4:8",                      # Gb
        "r:4 eb5:6 d5:6",                  # G
        "c5:12 r:4",                       # Cm   arrival
        "@bell c5:2 eb5:2 g5:4 ab5:8",     # Cm   the one climb, struck
        "@soft g5:8 gb5:8",                # Ab   ...and then held: the bell
        "f5:4 eb5:4 c5:4 b4:4",            # Gb   envelope dies in 19 frames,
        "b4:12 r:4",                       # G    so the peak has to sustain
    ],
    "p2": [
        "@arpm c3:16", "@arp5 c3:16",
        "@arpM ab2:16", "@arpM ab2:16",
        "@arpM gb2:16", "@arp5 gb2:16",
        "@arpM g2:16", "@arpm c3:16",
        "@arpm c3:16", "@arpM ab2:16",
        "@arpM gb2:16", "@arpM g2:16",
    ],
    "tri": [
        "@bass c2:16", "c2:12 eb2:4",
        "ab1:16", "ab1:12 c2:4",
        "gb1:16", "gb1:12 ab1:4",
        "g1:16", "c2:12 g1:4",
        "c2:8 g2:8", "ab1:8 eb2:8",
        "gb1:8 db2:8", "g1:8 d2:8",
    ],
    "noise": [
        "b:16", "r:16",
        "b:16", "r:16",
        "b:16", "r:8 h:4 r:4",
        "b:16", "r:16",
        "b:8 h:4 h:4", "r:4 h:4 b:8",
        "b:8 h:4 h:4", "b:8 r:4 h:4",
    ],
}

# =============================================================================
# BATTLE — the most-heard 34 seconds in the game, so it is built like a song.
# A minor, 16 bars, one chord a bar. A (0-7) is a stabbing repeated-note figure
# that snaps up to a held E5 and then runs back down; B (8-15) goes to C major,
# climbs to A5 at bar 12 and falls. Bars 7 and 15 share a descending tag on
# purpose — it is the refrain that ends both halves, and at bar 15 it walks down
# to B4 and drops a fourth into the A4 that starts the loop.
# =============================================================================
BATTLE = {
    "name": "BATTLE", "tempo": 8, "loop_bar": 0,
    "p1": [
        "@lead2 a4:2 a4:2 c5:2 a4:2 e5:8",  # A   Am  the hook
        "e5:2 d5:2 c5:2 b4:2 a4:4 e4:4",    #     Am  the run back down
        "f4:2 f4:2 a4:2 f4:2 c5:8",         #     F
        "c5:2 b4:2 a4:2 g#4:2 e4:8",        #     E
        "a4:2 a4:2 c5:2 a4:2 e5:8",         #     Am  restated
        "e5:2 f5:2 e5:2 d5:2 c5:4 b4:4",    #     Am  varied, higher
        "d5:4 a4:4 f5:4 d5:4",              #     Dm  leaps
        "e5:4 d5:4 c5:4 b4:4",              #     E   the tag
        "c5:6 e5:2 g5:8",                   # B   C   lyrical, long notes
        "d5:6 b4:2 d5:8",                   #     G
        "e5:4 c5:4 a4:8",                   #     Am
        "b4:4 g#4:4 e4:8",                  #     E
        "f5:2 e5:2 f5:2 g5:2 a5:8",         #     F   climax
        "g5:4 f5:4 d5:4 b4:4",              #     G
        "a4:2 c5:2 e5:2 a5:2 g5:4 e5:4",    #     Am
        "e5:4 d5:4 c5:4 b4:4",              #     E   the tag -> A4
    ],
    "p2": [
        stab4("a3", "e4", "a3", "c4"), stab4("a3", "e4", "a3", "c4"),
        stab4("f3", "c4", "f3", "a3"), stab4("e3", "b3", "e3", "g#3"),
        stab4("a3", "e4", "a3", "c4"), stab4("a3", "e4", "c4", "e4"),
        stab4("d3", "a3", "d3", "f3"), stab4("e3", "b3", "g#3", "b3"),
        stab4("c4", "g3", "e4", "g3"), stab4("b3", "d4", "g3", "d4"),
        stab4("a3", "e4", "c4", "e4"), stab4("e3", "b3", "g#3", "b3"),
        stab4("f3", "c4", "a3", "c4"), stab4("g3", "d4", "b3", "d4"),
        stab4("a3", "e4", "c4", "e4"), stab4("e3", "b3", "g#3", "d4"),
    ],
    "tri": [
        drive("a"), drive("a"), drive("f"), drive("e"),
        drive("a"), drive("a"), drive("d"), drive("e"),
        drive("c"), drive("g"), drive("a"), drive("e"),
        drive("f"), drive("g"), drive("a"), drive("e"),
    ],
    "noise": [
        "k:4 h:4 s:4 h:4", "k:4 h:2 k:2 s:4 h:4",
        "k:4 h:4 s:4 h:4", "k:4 h:4 s:4 s:2 s:2",
        "k:4 h:4 s:4 h:4", "k:4 h:2 k:2 s:4 h:4",
        "k:4 h:4 s:4 h:4", "k:4 h:4 s:4 s:2 s:2",
        "k:4 h:4 s:4 h:4", "k:4 h:2 k:2 s:4 h:4",
        "k:4 h:4 s:4 h:4", "k:4 h:4 s:4 s:2 s:2",
        "k:4 h:4 s:4 h:4", "k:4 h:2 k:2 s:4 h:4",
        "k:4 h:4 s:4 h:4", "s:2 s:2 s:2 s:2 s:2 s:2 b:2 b:2",
    ],
}

# =============================================================================
# BOSS — D phrygian, faster and lower than BATTLE so the two never blur. The riff
# is the flat second hammered against the tonic with a rest punched out of it
# (D5 . D5 Eb5 D5 A4) — the rest is what makes it a riff instead of a scale. The
# old version was a stepwise chromatic wander whose second half was the first
# half an octave up; this one answers the riff with a real B section (bars 8-11
# in G minor, the widest leaps in the score) and a stepwise fall back to A4.
# =============================================================================
BOSS = {
    "name": "BOSS", "tempo": 7, "loop_bar": 0,
    "p1": [
        "@lead2 d5:2 r:2 d5:2 eb5:2 d5:4 a4:4",  # A   Dm  the riff
        "bb4:4 a4:2 g4:2 f4:4 d4:4",             #     Dm
        "eb5:2 r:2 eb5:2 f5:2 eb5:4 bb4:4",      #     Eb  the riff on the bII
        "c5:4 bb4:2 a4:2 g4:4 e4:4",             #     A
        "d5:2 r:2 d5:2 eb5:2 d5:4 a4:4",         # A'  Dm
        "bb4:4 a4:2 g4:2 f4:8",                  #     Dm
        "bb4:4 d5:4 f5:6 eb5:2",                 #     Bb
        "d5:4 c5:4 bb4:4 a4:4",                  #     A
        "g5:2 f5:2 eb5:2 d5:2 g5:8",             # B   Gm  the wide answer
        "a5:2 g5:2 f5:2 eb5:2 d5:8",             #     Dm
        "eb5:4 g5:4 bb5:8",                      #     Eb  top of the score
        "a5:4 g5:4 f5:4 eb5:4",                  #     A
        "d5:2 eb5:2 d5:2 c5:2 bb4:4 a4:4",       # A'' Dm
        "bb4:2 c5:2 d5:2 eb5:2 f5:8",            #     Bb
        "g5:4 f5:4 eb5:4 d5:4",                  #     Gm
        "eb5:2 d5:2 c5:2 bb4:2 a4:8",            #     A   -> D5
    ],
    "p2": [
        stab4("d3", "d3", "eb3", "d3"), stab4("d3", "a3", "f3", "a3"),
        stab4("eb3", "bb3", "eb3", "g3"), stab4("a2", "e3", "a2", "c3"),
        stab4("d3", "d3", "eb3", "d3"), stab4("d3", "a3", "f3", "a3"),
        stab4("bb2", "f3", "bb2", "d3"), stab4("a2", "e3", "c3", "e3"),
        stab4("g2", "d3", "g2", "bb2"), stab4("d3", "a3", "d3", "f3"),
        stab4("eb3", "bb3", "eb3", "g3"), stab4("a2", "e3", "c3", "e3"),
        stab4("d3", "d3", "eb3", "d3"), stab4("bb2", "f3", "d3", "f3"),
        stab4("g2", "d3", "bb2", "d3"), stab4("a2", "e3", "c3", "e3"),
    ],
    "tri": [
        chrom("d", "eb"), chrom("d", "eb"), chrom("eb", "d"), drive("a"),
        chrom("d", "eb"), chrom("d", "eb"), chrom("bb", "a"), drive("a"),
        drive("g"), chrom("d", "eb"), chrom("eb", "d"), drive("a"),
        chrom("d", "eb"), chrom("bb", "a"), drive("g"),
        "@bass a1:4 a2:4 e2:4 a1:4",
    ],
    "noise": [
        "k:4 k:2 h:2 s:4 h:4", "k:4 k:2 h:2 s:4 h:4",
        "k:4 k:2 h:2 s:4 h:4", "k:4 h:2 h:2 s:2 s:2 s:2 s:2",
        "k:4 k:2 h:2 s:4 h:4", "k:4 k:2 h:2 s:4 s:2 h:2",
        "k:4 k:2 h:2 s:4 h:4", "k:4 h:2 h:2 s:2 s:2 s:2 s:2",
        "k:4 k:2 h:2 s:4 h:4", "k:4 k:2 h:2 s:4 h:4",
        "k:4 k:2 h:2 s:4 s:2 h:2", "k:4 h:2 h:2 s:2 s:2 s:2 s:2",
        "k:4 k:2 h:2 s:4 h:4", "k:4 k:2 h:2 s:4 s:2 h:2",
        "k:4 k:2 h:2 s:4 h:4", "s:2 s:2 s:2 s:2 b:4 b:4",
    ],
}

# =============================================================================
# VICTORY — brief relief, loops while the spoils are counted. C major, 4 bars.
# The triple-G pickup into a held C5 is the hook and it already worked; what is
# new is that pulse 2 answers in real two-part writing instead of holding one
# chord, and the last bar resolves to C and then plays the G pickup itself, so
# the loop hands off cleanly instead of sitting on a whole note.
# =============================================================================
VICTORY = {
    "name": "VICTORY", "tempo": 9, "loop_bar": 0,
    "p1": [
        "@lead2 g4:2 g4:2 g4:2 c5:10",     # C
        "e5:4 d5:4 e5:8",                  # C
        "f5:2 e5:2 d5:4 g5:4 e5:4",        # F/G
        "c5:12 g4:4",                      # C   -> the pickup, into the loop
    ],
    "p2": [
        "@arpM c4:16",
        "@pluck c5:4 b4:4 c5:8",
        "@pluck a4:2 g4:2 f4:4 b4:4 g4:4",
        "@arpM g3:12 c4:4",
    ],
    "tri": [
        "@bass c2:8 g2:8", "c3:4 g2:4 e2:4 g2:4",
        "f2:4 c3:4 g1:4 d2:4", "c2:12 g1:4",
    ],
    "noise": [
        "k:4 h:4 k:4 s:4", "k:4 h:4 k:4 s:4",
        "k:4 h:4 k:4 s:4", "k:4 s:2 s:2 s:2 s:2 b:4",
    ],
}

# =============================================================================
# FANFARE — item found / secret opened. One-shot, and now short: at tempo 7 the
# two-bar minimum is 3.7 seconds instead of 4.8. The old version was a bare
# ascending C major triad; this one runs G-C-E-G up to C6 and answers with
# B5-D6-C6, so it has a shape rather than just an arrival.
# =============================================================================
FANFARE = {
    "name": "FANFARE", "tempo": 7, "loop_bar": 0, "one_shot": True,
    "p1": [
        "@lead2 g4:2 c5:2 e5:2 g5:2 c6:8",
        "b5:2 d6:2 c6:12",
    ],
    "p2": ["@arpM c4:16", "@arpM g3:8 c4:8"],
    "tri": ["@bass c2:8 g2:8", "g1:8 c2:8"],
    "noise": ["k:4 h:4 k:4 s:4", "s:2 s:2 s:2 s:2 b:8"],
}

# =============================================================================
# ENDING — the long exhale, and the payoff for TITLE. Same tempo, same tune, but
# in C major: TITLE's reach for a minor sixth (A4 -> F5) becomes a major sixth
# (C5 -> A5) in bar 2, and TITLE's phrase comes back note for note at bar 5, in
# its own minor, before the major has the last word. Noise stays silent; nothing
# should hit anything here.
# =============================================================================
ENDING = {
    "name": "ENDING", "tempo": 13, "loop_bar": 0,
    "p1": [
        "@soft e4:8 g4:8",                 # C
        "@lead c5:6 d5:2 e5:4 c5:4",       # Am  the TITLE hook, transposed
        "a5:8 g5:4 e5:4",                  # F   the reach, now a major sixth
        "d5:6 c5:2 b4:4 g4:4",             # G
        "c5:12 e5:4",                      # C
        "a4:6 b4:2 c5:4 e5:4",             # Am  TITLE, note for note
        "f5:8 e5:4 d5:4",                  # Dm
        "d5:4 c5:4 b4:8",                  # G
        "c5:16",                           # C   arrival
        "a5:6 g5:2 f5:4 e5:4",             # F
        "d5:8 g4:4 b4:4",                  # G
        "c5:16",                           # C
    ],
    "p2": [
        "@arpM c4:16", "@arpm a3:16", "@arpM f3:16", "@arpM g3:16",
        "@arpM c4:16", "@arpm a3:16", "@arpm d3:16", "@arpM g3:16",
        "@soft e4:4 d4:4 c4:4 g3:4",
        "@arpM f3:16", "@arpM g3:16", "@soft g4:8 e4:8",
    ],
    "tri": [
        "@bass c2:8 g2:8", "a1:8 e2:8", "f1:8 c2:8", "g1:8 d2:8",
        "c2:8 g2:8", "a1:8 e2:8", "d2:8 a2:8", "g1:8 d2:8",
        "c2:12 e2:4", "f1:8 c2:8", "g1:8 d2:8", "c2:12 g1:4",
    ],
    "noise": rep("r:16", 12),
}

# Song ids are assigned in this order, starting at 1 ($00 = "no request").
SONGS = [TITLE, TOWN, OVERWORLD, DUNGEON, BATTLE, BOSS, VICTORY, FANFARE, ENDING]


# =============================================================================
# SFX — steps are (frames, volume 0-15, duty 0-3 / noise mode, pitch)
# Pitch is a note name on the pulse channels and a noise period 0-15 on ch 3.
#
# Menu and status cues live on pulse 2, so an sfx never eats the melody; impacts
# live on noise, so combat never eats the melody either. Each cue is shaped to be
# unmistakable from the others: rising = good, falling = cancelled, arpeggiated
# major = reward, tritone = magic, noise = physical.
# =============================================================================
SFX = [
    # Menu: three gestures that cannot be confused — a two-note blip up, a
    # three-note rise, a two-note fall. CURSOR must stay under ~6 frames or
    # holding a direction on a menu turns into a machine gun.
    {"name": "CURSOR", "ch": 1, "steps": [
        (2, 9, 2, "e6"), (3, 5, 2, "a6")]},
    {"name": "CONFIRM", "ch": 1, "steps": [
        (3, 10, 2, "c6"), (3, 10, 2, "e6"), (7, 8, 2, "a6")]},
    {"name": "CANCEL", "ch": 1, "steps": [
        (3, 9, 1, "a5"), (6, 6, 1, "e5")]},

    # Impacts: noise only. HIT is a short mid crack. CRIT must not be a slow
    # downward sweep, because that is exactly what ENCOUNTER is — it is a snap
    # (two bright frames) that drops straight onto a low body and rings out.
    {"name": "HIT", "ch": 3, "steps": [
        (2, 12, 0, 10), (3, 8, 0, 12), (4, 4, 0, 13)]},
    {"name": "CRIT", "ch": 3, "steps": [
        (2, 15, 0, 2), (2, 15, 0, 6), (3, 12, 0, 11),
        (5, 8, 0, 14), (7, 4, 0, 15)]},

    # Restoration vs magic vs advancement. These used to be three versions of
    # the same rising major arpeggio; they are now three different intervals:
    # HEAL rises and then settles back a step, TECH is a stack of tritones,
    # LEVELUP is the only major triad and the only one over half a second.
    {"name": "HEAL", "ch": 1, "steps": [
        (3, 8, 1, "c5"), (3, 9, 1, "g5"), (3, 10, 1, "c6"),
        (5, 9, 1, "e6"), (4, 7, 1, "d6"), (7, 4, 1, "c6")]},
    {"name": "TECH", "ch": 1, "steps": [
        (2, 10, 0, "d5"), (2, 11, 0, "g#5"), (2, 11, 0, "d6"),
        (3, 10, 0, "g#6"), (3, 8, 0, "d6"), (6, 5, 0, "g#6")]},
    {"name": "LEVELUP", "ch": 1, "steps": [
        (4, 10, 2, "c5"), (4, 10, 2, "e5"), (4, 10, 2, "g5"),
        (4, 11, 2, "c6"), (10, 9, 2, "e6"), (12, 5, 2, "e6")]},

    # World cues.
    {"name": "DOOR", "ch": 3, "steps": [
        (4, 8, 0, 14), (4, 6, 0, 15), (7, 4, 0, 15), (9, 2, 0, 15)]},
    # SAVE was a third rising major triad, which put it in LEVELUP's family. It
    # is now a bare fifth held long: no third, so it reads as a system chime and
    # not as a reward, and it is far too slow to be mistaken for CONFIRM.
    {"name": "SAVE", "ch": 1, "steps": [
        (6, 8, 2, "a5"), (6, 9, 2, "e6"), (11, 8, 2, "e6"), (7, 4, 2, "e6")]},
    {"name": "ENCOUNTER", "ch": 3, "steps": [
        (2, 14, 0, 4), (2, 12, 0, 5), (2, 11, 0, 6), (2, 10, 0, 7),
        (2, 9, 0, 8), (3, 8, 0, 9), (3, 6, 0, 10), (4, 4, 0, 11),
        (6, 2, 0, 12)]},
]
