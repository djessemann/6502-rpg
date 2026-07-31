"""Compile THRENOS songs into the sound driver's binary format.

The binary format itself is documented at the top of src/sound.s; this module is
the only thing that emits it. Songs are authored in tools/songs.py.

Authoring model
---------------
A song is four channels (pulse1, pulse2, triangle, noise), each given as a list
of *bar* strings. A bar is always BAR_ROWS rows long and the compiler enforces
it, which catches almost every composing slip. Tokens inside a bar:

    @name       select instrument `name`
    c4          note, using the current length
    c#4:8       note, and set the current length to 8 rows
    eb3:2       flats are written with `b`, sharps with `#`
    r / r:4     rest
    ~ / ~:4     extend the previous note (tie; no retrigger)
    k s h b     noise-channel drums (kick, snare, hat, boom)

The compiler slices every channel into PAT_ROWS-row patterns, splitting notes
that straddle a boundary with a SLUR, dedups identical patterns across the whole
soundtrack, and emits an order table of pattern addresses.
"""

# --- constants shared with the driver ----------------------------------------
CPU_HZ = 1789773.0
BAR_ROWS = 16
PAT_ROWS = 32                  # rows per pattern; must be a multiple of BAR_ROWS
N_PITCH = 128                  # pitch table entries (arp offsets may run off 96)
BASE_MIDI = 32                 # pitch index i -> MIDI note BASE_MIDI + i
MAX_PITCH_IDX = 96             # highest index a song may actually name
TRI_SHIFT = 12                 # the triangle sounds an octave low for a timer

EV_END = 0x00
EV_REST = 0x61
EV_SLUR = 0x62
EV_INST = 0x63
EV_LEN = 0x63                  # + rows

SEMI = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

# noise "drums": token -> (instrument name, noise period 0..15)
DRUMS = {
    "k": ("kick", 12),
    "s": ("snare", 6),
    "h": ("hat", 2),
    "b": ("boom", 15),
    "t": ("hat", 0),
}


def note_to_midi(name):
    """'c#4' / 'eb3' / 'a2' -> MIDI note number (c4 = 60)."""
    s = name.lower()
    if s[0] not in SEMI:
        raise ValueError(f"bad note {name!r}")
    v = SEMI[s[0]]
    i = 1
    while i < len(s) and s[i] in "#b":
        v += 1 if s[i] == "#" else -1
        i += 1
    if not s[i:].lstrip("-").isdigit():
        raise ValueError(f"bad note {name!r}")
    return 12 * (int(s[i:]) + 1) + v


def timer_for(midi):
    """11-bit pulse timer for a MIDI note (the triangle is an octave lower)."""
    f = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    return int(round(CPU_HZ / (16.0 * f) - 1.0))


def pitch_table():
    out = []
    for i in range(N_PITCH):
        t = timer_for(BASE_MIDI + i)
        out.append(max(8, min(2047, t)))
    return out


# --- events -------------------------------------------------------------------
class Ev:
    __slots__ = ("kind", "pitch", "inst", "dur", "row")

    def __init__(self, kind, pitch, inst, dur, row):
        self.kind = kind                # 'note' | 'rest' | 'slur'
        self.pitch = pitch
        self.inst = inst
        self.dur = dur
        self.row = row

    def __repr__(self):
        return f"<{self.kind} {self.pitch} i{self.inst} d{self.dur} @{self.row}>"


def parse_channel(bars, chan, inst_ids, where):
    """bars: list of bar strings -> list of Ev. chan 0..3 (3 = noise)."""
    evs = []
    cur_inst = 0
    cur_dur = 4
    row = 0
    for bi, bar in enumerate(bars):
        start = row
        for tok in bar.split():
            if tok.startswith("@"):
                if tok[1:] not in inst_ids:
                    raise ValueError(f"{where} bar {bi}: unknown instrument {tok}")
                cur_inst = inst_ids[tok[1:]]
                continue
            name, _, d = tok.partition(":")
            if d:
                cur_dur = int(d)
                if not 1 <= cur_dur <= PAT_ROWS:
                    raise ValueError(f"{where} bar {bi}: bad length {tok}")
            if name == "r":
                evs.append(Ev("rest", 0, cur_inst, cur_dur, row))
            elif name == "~":
                if not evs or evs[-1].kind == "rest":
                    raise ValueError(f"{where} bar {bi}: '~' with nothing to tie")
                evs.append(Ev("slur", evs[-1].pitch, cur_inst, cur_dur, row))
            elif chan == 3 and name in DRUMS:
                iname, period = DRUMS[name]
                evs.append(Ev("note", period + 1, inst_ids[iname], cur_dur, row))
            else:
                midi = note_to_midi(name)
                if chan == 2:
                    midi += TRI_SHIFT
                idx = midi - BASE_MIDI
                if not 1 <= idx <= MAX_PITCH_IDX:
                    raise ValueError(
                        f"{where} bar {bi}: {name} is outside the NES range "
                        f"(pitch index {idx})")
                evs.append(Ev("note", idx, cur_inst, cur_dur, row))
            row += cur_dur
        if row - start != BAR_ROWS:
            raise ValueError(
                f"{where} bar {bi}: {row - start} rows, expected {BAR_ROWS}"
                f"  ({bar!r})")
    return evs


def slice_patterns(evs, total_rows):
    """Cut an event list into PAT_ROWS-row chunks, splitting straddling notes."""
    pats = [[] for _ in range(total_rows // PAT_ROWS)]
    for ev in evs:
        row, dur, kind, pitch = ev.row, ev.dur, ev.kind, ev.pitch
        while dur > 0:
            pat = row // PAT_ROWS
            room = PAT_ROWS - (row % PAT_ROWS)
            take = min(dur, room)
            pats[pat].append(Ev(kind, pitch, ev.inst, take, row))
            row += take
            dur -= take
            if kind == "note":
                kind = "slur"       # the tail must not retrigger
    return pats


def encode_pattern(evs):
    """Encode one pattern. Self-contained: it sets its own instrument/length."""
    out = bytearray()
    cur_len = None
    cur_inst = None
    for ev in evs:
        if ev.kind in ("note", "slur") and ev.inst != cur_inst:
            out += bytes((EV_INST, ev.inst))
            cur_inst = ev.inst
        if ev.dur != cur_len:
            out.append(EV_LEN + ev.dur)
            cur_len = ev.dur
        if ev.kind == "note":
            out.append(ev.pitch)
        elif ev.kind == "rest":
            out.append(EV_REST)
        else:
            out += bytes((EV_SLUR, ev.pitch))
    out.append(EV_END)
    return bytes(out)


# --- sfx ----------------------------------------------------------------------
def encode_sfx(sfx, pitch):
    """sfx: dict(name, ch, steps=[(frames, vol, duty, note_or_period), ...])."""
    ch = sfx["ch"]
    out = bytearray([ch * 4])
    for frames, vol, duty, note in sfx["steps"]:
        if not 1 <= frames <= 255:
            raise ValueError(f"sfx {sfx['name']}: bad step length {frames}")
        if ch == 3:
            volbyte = 0x30 | (vol & 0x0F)
            lo = (note & 0x0F) | (0x80 if duty else 0x00)
            hi = 0x08
        elif ch == 2:
            volbyte = 0xFF if vol else 0x80
            t = pitch[note_to_midi(note) + TRI_SHIFT - BASE_MIDI] if isinstance(note, str) else note
            lo, hi = t & 0xFF, (t >> 8) & 0x07
        else:
            volbyte = (duty << 6) | 0x30 | (vol & 0x0F)
            t = pitch[note_to_midi(note) - BASE_MIDI] if isinstance(note, str) else note
            lo, hi = t & 0xFF, ((t >> 8) & 0x07) | 0x08
        out += bytes((frames, volbyte, lo, hi))
    out.append(0x00)
    return bytes(out)


# --- top level ----------------------------------------------------------------
def compile_all(songs, instruments, envelopes, sfxs):
    """-> a dict with everything the emitter and tools/music_check.py need."""
    inst_ids = {ins["name"]: i for i, ins in enumerate(instruments)}
    if len(instruments) > 16:
        raise ValueError("at most 16 instruments")

    # envelopes are concatenated into one <=256 byte blob
    env_data = bytearray()
    env_at = {}
    for name, steps in envelopes.items():
        env_at[name] = len(env_data)
        for v in steps:
            if not (0 <= v <= 0x0F or 0x80 <= v <= 0x8F):
                raise ValueError(f"envelope {name}: bad step ${v:02X}")
            env_data.append(v)
        if not 0x80 <= env_data[-1] <= 0x8F:
            raise ValueError(f"envelope {name}: must end in a sustain step")
    if len(env_data) > 256:
        raise ValueError(f"envelope data is {len(env_data)} bytes (max 256)")

    inst_env = [env_at[i["env"]] for i in instruments]
    inst_duty = [i.get("duty", 0) for i in instruments]
    inst_arp = [i.get("arp", 0) for i in instruments]
    inst_vib, inst_vibd = [], []
    for i in instruments:                       # "vib": (speed 1..15, depth 0..3)
        speed, depth = i.get("vib", (0, 0))
        if not (0 <= speed <= 15 and 0 <= depth <= 3):
            raise ValueError(f"instrument {i['name']}: bad vibrato {i['vib']}")
        inst_vib.append(speed)
        inst_vibd.append(depth << 4)

    pitch = pitch_table()

    patterns = []               # list of bytes, deduped
    pat_index = {}

    def intern(b):
        if b not in pat_index:
            pat_index[b] = len(patterns)
            patterns.append(b)
        return pat_index[b]

    out_songs = []
    for sid, song in enumerate(songs, start=1):
        chans = [song["p1"], song["p2"], song["tri"], song["noise"]]
        nbars = len(chans[0])
        for c in chans:
            if len(c) != nbars:
                raise ValueError(f"{song['name']}: channels have different lengths")
        if nbars * BAR_ROWS % PAT_ROWS:
            raise ValueError(f"{song['name']}: {nbars} bars is not a whole "
                             f"number of {PAT_ROWS}-row patterns")
        total_rows = nbars * BAR_ROWS
        order = []
        ranges = []
        for ci, bars in enumerate(chans):
            evs = parse_channel(bars, ci, inst_ids, f"{song['name']} ch{ci}")
            notes = [e.pitch for e in evs if e.kind == "note"]
            ranges.append((min(notes), max(notes)) if notes else None)
            col = [intern(encode_pattern(p)) for p in slice_patterns(evs, total_rows)]
            order.append(col)
        n_order = total_rows // PAT_ROWS
        rows = [[order[c][i] for c in range(4)] for i in range(n_order)]

        loop_bar = song.get("loop_bar", 0)
        if loop_bar * BAR_ROWS % PAT_ROWS:
            raise ValueError(f"{song['name']}: loop_bar must be even")
        loop_idx = loop_bar * BAR_ROWS // PAT_ROWS
        one_shot = song.get("one_shot", False)
        out_songs.append({
            "name": song["name"],
            "id": sid,
            "tempo": song["tempo"],
            "order": rows,
            "n_order": n_order,
            "loop_idx": 0 if one_shot else loop_idx,
            "loop_n": 0 if one_shot else n_order - loop_idx,
            "rows": total_rows,
            "ranges": ranges,
            "seconds": total_rows * song["tempo"] / 60.0,
        })

    out_sfx = []
    for i, s in enumerate(sfxs, start=1):
        out_sfx.append({"name": s["name"], "id": i, "ch": s["ch"],
                        "data": encode_sfx(s, pitch)})

    data = {
        "songs": out_songs,
        "patterns": patterns,
        "sfx": out_sfx,
        "env_data": bytes(env_data),
        "inst_env": inst_env,
        "inst_duty": inst_duty,
        "inst_vib": inst_vib,
        "inst_vibd": inst_vibd,
        "inst_arp": inst_arp,
        "instruments": instruments,
        "pitch": pitch,
    }
    data["sizes"] = sizes(data)
    return data


def sizes(d):
    pat = sum(len(p) for p in d["patterns"])
    order = sum(5 + 8 * s["n_order"] for s in d["songs"])
    sfx = sum(len(s["data"]) for s in d["sfx"])
    tabs = 2 * (len(d["songs"]) + 1) + 2 * (len(d["sfx"]) + 1)
    inst = 5 * 16 + len(d["env_data"])
    pitch = 2 * N_PITCH
    return {"patterns": pat, "orders": order, "sfx": sfx, "tables": tabs,
            "instruments": inst, "pitch": pitch,
            "total": pat + order + sfx + tabs + inst + pitch}


# --- emitters -----------------------------------------------------------------
def _bytes_lines(f, data, indent="    "):
    for i in range(0, len(data), 16):
        f.write(indent + ".byte " +
                ",".join(f"${b:02X}" for b in data[i:i + 16]) + "\n")


def emit(f, d, bank):
    f.write('.include "banks.inc"\n')
    f.write(".export song_tab, sfx_tab\n")
    f.write(".export inst_env, inst_duty, inst_vib, inst_vibd, inst_arp\n")
    f.write(".export env_data, pitch_lo, pitch_hi\n")
    f.write(f'.segment "BANK{bank:02d}"\n\n')

    f.write("; pitch index -> 11-bit APU timer\n")
    f.write("pitch_lo:\n")
    _bytes_lines(f, [t & 0xFF for t in d["pitch"]])
    f.write("pitch_hi:\n")
    _bytes_lines(f, [(t >> 8) & 0x07 for t in d["pitch"]])

    f.write("\ninst_env:\n")
    _bytes_lines(f, d["inst_env"] + [0] * (16 - len(d["inst_env"])))
    f.write("inst_duty:\n")
    _bytes_lines(f, d["inst_duty"] + [0] * (16 - len(d["inst_duty"])))
    f.write("inst_vib:\n")
    _bytes_lines(f, d["inst_vib"] + [0] * (16 - len(d["inst_vib"])))
    f.write("inst_vibd:\n")
    _bytes_lines(f, d["inst_vibd"] + [0] * (16 - len(d["inst_vibd"])))
    f.write("inst_arp:\n")
    _bytes_lines(f, d["inst_arp"] + [0] * (16 - len(d["inst_arp"])))
    f.write("env_data:\n")
    _bytes_lines(f, d["env_data"])

    f.write("\nsong_tab:\n    .addr 0\n")
    for s in d["songs"]:
        f.write(f"    .addr song_{s['name']}\n")
    f.write("sfx_tab:\n    .addr 0\n")
    for s in d["sfx"]:
        f.write(f"    .addr sfx_{s['name']}\n")

    for s in d["songs"]:
        f.write(f"\nsong_{s['name']}:\n")
        f.write(f"    .byte {s['tempo']}, {s['n_order']}, {s['loop_n']}\n")
        if s["loop_n"]:
            f.write(f"    .addr song_{s['name']}_ord + {8 * s['loop_idx']}\n")
        else:
            f.write("    .addr 0\n")
        f.write(f"song_{s['name']}_ord:\n")
        for row in s["order"]:
            f.write("    .addr " + ",".join(f"pat_{p}" for p in row) + "\n")

    f.write("\n")
    for i, p in enumerate(d["patterns"]):
        f.write(f"pat_{i}:\n")
        _bytes_lines(f, p)

    for s in d["sfx"]:
        f.write(f"sfx_{s['name']}:\n")
        _bytes_lines(f, s["data"])


def emit_ids(f, d):
    for s in d["songs"]:
        f.write(f"SONG_{s['name']} = {s['id']}\n")
    f.write(f"N_SONGS = {len(d['songs'])}\n")
    for s in d["sfx"]:
        f.write(f"SFX_{s['name']} = {s['id']}\n")
    f.write(f"N_SFX = {len(d['sfx'])}\n")
    f.write("MUSIC_STOP = $FF\n")
