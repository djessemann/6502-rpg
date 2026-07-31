#!/usr/bin/env python3
"""Render the compiled THRENOS soundtrack to WAV, piano rolls and note lists.

music_check.py proves the data is *legal*; this proves it is *music*. It runs
the same frame-accurate model of src/sound.s (row tick, envelope, vibrato,
arpeggio, duty, triangle on/off, noise LFSR), then:

  * synthesises a 2A03 approximation to test/shots/<SONG>.wav
  * draws a piano roll to test/shots/roll_<SONG>.png
  * prints the melody (pulse 1) as note names with durations, plus the
    structural measurements a composer would actually check: how many distinct
    pitches the tune uses, its range, whether bar N is a copy of an earlier bar,
    where the bass sits, how loud the loop seam clunks.

Run: python3 tools/music_render.py [SONGNAME ...]
"""
import math
import pathlib
import struct
import sys
import wave

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import music                                                    # noqa: E402
import songs                                                    # noqa: E402

OUT = HERE.parent / "test" / "shots"
SR = 44100
FRAME_SAMPLES = SR / 60.0988

# NTSC noise period table, index 0..15
NOISE_PERIOD = [4, 8, 16, 32, 64, 96, 128, 160,
                202, 254, 380, 508, 762, 1016, 2034, 4068]

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

VIB_TAB = [
    0, 1, 2, 3, 3, 3, 2, 1, 0, -1, -2, -3, -3, -3, -2, -1,
    0, 2, 4, 6, 6, 6, 4, 2, 0, -2, -4, -6, -6, -6, -4, -2,
    0, 3, 6, 9, 9, 9, 6, 3, 0, -3, -6, -9, -9, -9, -6, -3,
    0, 5, 10, 15, 15, 15, 10, 5, 0, -5, -10, -15, -15, -15, -10, -5,
]

END, REST, SLUR, INST = 0x00, 0x61, 0x62, 0x63


def midi_name(m):
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def idx_name(idx, chan):
    """Pitch index -> sounding note name (the triangle sounds an octave down)."""
    m = music.BASE_MIDI + idx
    if chan == 2:
        m -= music.TRI_SHIFT
    return midi_name(m)


# =============================================================================
# Driver model
# =============================================================================
class Chan:
    def __init__(self, ch):
        self.ch = ch
        self.pat = None
        self.off = 0
        self.dur = 1
        self.len = 4
        self.inst = 0
        self.note = 0
        self.env = 0
        self.vibp = 0
        self.arpp = 0
        self.active = True
        self.keyon = False
        self.ordi = 0
        self.cnt = 0


class Sim:
    """Frame-accurate model of src/sound.s for one song."""

    def __init__(self, d, song):
        self.d = d
        self.song = song
        self.order = song["order"]
        self.pats = d["patterns"]
        self.tempo = song["tempo"]
        self.rowt = 1
        self.row = -1
        self.chans = [Chan(c) for c in range(4)]
        for c in self.chans:
            c.cnt = song["n_order"]
            c.ordi = 0
        self.events = [[] for _ in range(4)]     # (row, dur, pitch_idx, inst)
        self.rests = [[] for _ in range(4)]      # (row, dur)

    def _pull(self, c):
        if c.cnt == 0:
            if not self.song["loop_n"]:
                c.active = False
                c.note = 0
                return False
            c.cnt = self.song["loop_n"]
            c.ordi = self.song["loop_idx"]
        c.cnt -= 1
        p = self.order[c.ordi][c.ch]
        c.ordi += 1
        c.pat = self.pats[p]
        c.inst = c.pat[0]
        c.len = c.pat[1]
        c.off = 2
        return True

    def row_advance(self, c):
        if not c.active:
            return
        c.dur -= 1
        if c.dur:
            return
        while True:
            if c.pat is None or c.off >= len(c.pat):
                if not self._pull(c):
                    return
                continue
            b = c.pat[c.off]
            c.off += 1
            if b == END:
                c.pat = None
                if not self._pull(c):
                    return
                continue
            if b < REST:                                  # note
                c.note = b
                c.env = self.d["inst_env"][c.inst]
                c.vibp = 0
                c.keyon = True
                self.events[c.ch].append((self.row, c.len, b, c.inst))
                break
            if b == REST:
                c.note = 0
                self.rests[c.ch].append((self.row, c.len))
                break
            if b == SLUR:
                c.note = c.pat[c.off]
                c.off += 1
                break
            if b == INST:
                c.inst = c.pat[c.off]
                c.off += 1
                continue
            c.len = b - 0x63                              # LEN
        c.dur = c.len

    def chan_frame(self, c):
        """-> (vol 0..15, duty 0..3, timer/period, keyon) or None when silent."""
        if not c.active or c.note == 0:
            c.keyon = False
            return None
        d = self.d
        e = d["env_data"][c.env]
        if e & 0x80:
            vol = e & 0x0F
        else:
            vol = e & 0x0F
            c.env += 1
        inst = c.inst
        note = c.note
        arp = d["inst_arp"][inst]
        if arp:
            c.arpp = (c.arpp + 1) % 3
            if c.arpp == 1:
                note += arp >> 4
            elif c.arpp == 2:
                note += arp & 0x0F
        keyon = c.keyon
        c.keyon = False
        if c.ch == 3:
            return (vol, d["inst_duty"][inst] >> 7, (note - 1) & 0x0F, keyon)
        t = d["pitch"][note]
        vs = d["inst_vib"][inst]
        if vs:
            c.vibp = (c.vibp + vs) & 0xFF
            t += VIB_TAB[(d["inst_vibd"][inst] >> 4) * 16 + ((c.vibp >> 4) & 0x0F)]
            t = max(8, min(2047, t))
        return (vol, d["inst_duty"][inst] >> 6, t, keyon)

    def frames(self, n):
        """Yield n frames of [(vol,duty,timer,keyon)|None] * 4."""
        for _ in range(n):
            self.rowt -= 1
            if self.rowt == 0:
                self.rowt = self.tempo
                self.row += 1
                for c in self.chans:
                    self.row_advance(c)
                yield [None] * 4          # the driver writes no APU register
            else:
                yield [self.chan_frame(c) for c in self.chans]


# =============================================================================
# Synthesis
# =============================================================================
DUTY_FRAC = [0.125, 0.25, 0.5, 0.75]


def synth(d, song, seconds):
    n = int(seconds * 60)
    sim = Sim(d, song)
    nsamp = int(seconds * SR)
    buf = [0.0] * (nsamp + 2048)

    phase = [0.0, 0.0, 0.0]
    lfsr = 1
    ntimer = 0.0
    last = [None] * 4
    pos = 0.0
    for st in sim.frames(n):
        for ci in range(4):
            if st[ci] is not None:
                last[ci] = st[ci]
        start = int(pos)
        pos += FRAME_SAMPLES
        end = int(pos)
        cnt = end - start
        for ci in range(3):
            s = last[ci]
            if s is None or s[0] == 0:
                continue
            vol, duty, timer, keyon = s
            if ci == 2:
                f = music.CPU_HZ / (32.0 * (timer + 1))
                amp = 0.30
            else:
                f = music.CPU_HZ / (16.0 * (timer + 1))
                amp = 0.22 * (vol / 15.0)
                if keyon:
                    phase[ci] = 0.0
            step = f / SR
            ph = phase[ci]
            if ci == 2:
                for i in range(cnt):
                    ph += step
                    if ph >= 1.0:
                        ph -= 1.0
                    # 16-step quantised triangle, as the 2A03 makes it
                    q = int(ph * 32) & 31
                    v = (q if q < 16 else 31 - q) / 15.0 * 2.0 - 1.0
                    buf[start + i] += amp * v
            else:
                df = DUTY_FRAC[duty]
                for i in range(cnt):
                    ph += step
                    if ph >= 1.0:
                        ph -= 1.0
                    buf[start + i] += amp if ph < df else -amp
            phase[ci] = ph
        s = last[3]
        if s is not None and s[0]:
            vol, mode, period, keyon = s
            p = NOISE_PERIOD[period]
            amp = 0.17 * (vol / 15.0)
            for i in range(cnt):
                ntimer -= music.CPU_HZ / SR
                while ntimer <= 0:
                    ntimer += p
                    bit = 6 if mode else 1
                    fb = (lfsr ^ (lfsr >> bit)) & 1
                    lfsr = (lfsr >> 1) | (fb << 14)
                buf[start + i] += amp if (lfsr & 1) == 0 else -amp
    return buf[:nsamp]


def write_wav(path, buf):
    peak = max(1e-6, max(abs(v) for v in buf))
    g = min(1.0, 0.92 / peak)
    frames = b"".join(struct.pack("<h", int(max(-1, min(1, v * g)) * 32000))
                      for v in buf)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames)


# =============================================================================
# Piano roll
# =============================================================================
COL = [(255, 210, 60), (110, 190, 255), (120, 245, 150), (255, 120, 120)]


def piano_roll(path, song, evs, title):
    from PIL import Image, ImageDraw
    rows = song["rows"]
    pitched = [(c, e) for c in range(3) for e in evs[c]]
    if not pitched:
        return
    mids = []
    for c, e in pitched:
        m = music.BASE_MIDI + e[2] - (music.TRI_SHIFT if c == 2 else 0)
        mids.append(m)
    lo, hi = min(mids) - 2, max(mids) + 2
    span = hi - lo + 1
    px = max(2, min(8, 1600 // rows))
    ph = max(4, min(10, 520 // span))
    W, H = rows * px + 70, span * ph + 60
    img = Image.new("RGB", (W, H), (18, 18, 24))
    dr = ImageDraw.Draw(img)
    # staff lines: C octaves light, other semitones dark
    for m in range(lo, hi + 1):
        y = 40 + (hi - m) * ph
        if m % 12 == 0:
            dr.rectangle([60, y, W - 4, y + ph - 1], fill=(46, 46, 60))
            dr.text((4, y - 2), midi_name(m), fill=(150, 150, 170))
        elif m % 12 in (1, 3, 6, 8, 10):
            dr.rectangle([60, y, W - 4, y + ph - 1], fill=(28, 28, 36))
    for bar in range(0, rows // 16 + 1):          # bar lines
        x = 60 + bar * 16 * px
        c = (95, 95, 120) if bar % 4 == 0 else (52, 52, 66)
        dr.line([x, 38, x, H - 18], fill=c)
    for c, e in pitched:
        row, dur, idx, _ = e
        m = music.BASE_MIDI + idx - (music.TRI_SHIFT if c == 2 else 0)
        x0 = 60 + row * px
        y0 = 40 + (hi - m) * ph
        dr.rectangle([x0, y0, x0 + dur * px - 1, y0 + ph - 2], fill=COL[c])
    for e in evs[3]:                              # noise strip along the bottom
        row, dur, idx, _ = e
        x0 = 60 + row * px
        dr.rectangle([x0, H - 14, x0 + max(1, dur * px - 1), H - 8], fill=COL[3])
    dr.text((6, 10), title, fill=(235, 235, 245))
    dr.text((6, 24), "yellow=lead  blue=harmony  green=triangle bass  red=noise",
            fill=(140, 140, 160))
    img.save(path)


# =============================================================================
# Analysis
# =============================================================================
def bar_sig(evs, bar):
    """A bar's melodic content, transposition-sensitive, for repeat detection."""
    lo, hi = bar * 16, bar * 16 + 16
    return tuple((e[0] - lo, e[1], e[2]) for e in evs if lo <= e[0] < hi)


def melody_text(evs, rests, chan, rows):
    """Bar by bar, notes and rests interleaved so the rhythm is readable."""
    items = sorted([(e[0], e[1], idx_name(e[2], chan)) for e in evs] +
                   [(r[0], r[1], "--") for r in rests])
    out = []
    for bar in range(rows // 16):
        lo, hi = bar * 16, bar * 16 + 16
        toks = [f"{nm}:{d}" for row, d, nm in items if lo <= row < hi]
        out.append(f"  bar {bar:2d} | " + (" ".join(toks) if toks else "-"))
    return "\n".join(out)


def seam_gap(evs, rows):
    """Rows of lead silence spanning the loop point (last note off -> first on).

    A big number here is the clunk you hear every time the song comes round.
    """
    if not evs:
        return rows
    tail = rows - max(e[0] + e[1] for e in evs)
    head = min(e[0] for e in evs)
    return tail + head


def intervals(evs):
    return [evs[i + 1][2] - evs[i][2] for i in range(len(evs) - 1)]


def analyse(song, evs, rests):
    rows = song["rows"]
    nbars = rows // 16
    p1 = evs[0]
    print(f"\n{'=' * 74}\n{song['name']}  tempo {song['tempo']} "
          f"({60 / song['tempo']:.1f} rows/s)  {nbars} bars  "
          f"{song['seconds']:.1f}s  loop@bar {song['loop_idx'] * 2}")
    if not p1:
        print("  MELODY: none — pulse 1 is empty")
    else:
        pitches = sorted({e[2] for e in p1})
        iv = intervals(p1)
        big = sum(1 for i in iv if abs(i) >= 5)
        print(f"  lead: {len(p1)} notes, {len(pitches)} distinct pitches, "
              f"range {idx_name(pitches[0], 0)}..{idx_name(pitches[-1], 0)} "
              f"({pitches[-1] - pitches[0]} semitones), "
              f"{big}/{len(iv)} leaps >=4th, "
              f"mean |interval| {sum(abs(i) for i in iv) / max(1, len(iv)):.1f}")
        durs = {}
        for e in p1:
            durs[e[1]] = durs.get(e[1], 0) + 1
        print("  rhythm: " + ", ".join(f"{k}r x{v}" for k, v in
                                       sorted(durs.items())))
    # repeated bars
    sigs = [bar_sig(p1, b) for b in range(nbars)]
    dup = {}
    for b, s in enumerate(sigs):
        dup.setdefault(s, []).append(b)
    reps = {tuple(v): None for v in dup.values() if len(v) > 1}
    if reps:
        print("  repeated melody bars: " +
              "; ".join("=".join(str(b) for b in g) for g in reps))
    else:
        print("  repeated melody bars: none (every bar is different)")
    for ci, nm in ((1, "harm"), (2, "bass"), (3, "drum")):
        e = evs[ci]
        if not e:
            print(f"  {nm}: SILENT")
            continue
        ps = sorted({x[2] for x in e})
        if ci == 3:
            print(f"  {nm}: {len(e)} hits")
        else:
            print(f"  {nm}: {len(e)} notes, {len(ps)} distinct, "
                  f"{idx_name(ps[0], ci)}..{idx_name(ps[-1], ci)}")
    g = seam_gap(p1, rows)
    print(f"  loop seam: {g} rows ({g * song['tempo'] / 60:.1f}s) with no melody")
    print(melody_text(p1, rests[0], 0, rows))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = music.compile_all(songs.SONGS, songs.INSTRUMENTS,
                          songs.ENVELOPES, songs.SFX)
    want = [a.upper() for a in sys.argv[1:]]
    for s in d["songs"]:
        if want and s["name"] not in want:
            continue
        sim = Sim(d, s)
        for _ in sim.frames(s["rows"] * s["tempo"] + 4):
            pass
        # the tail frames wrap into the next pass; keep one loop's worth
        evs = [[e for e in ch if e[0] < s["rows"]] for ch in sim.events]
        rsts = [[r for r in ch if r[0] < s["rows"]] for ch in sim.rests]
        analyse(s, evs, rsts)
        sim.events = evs
        piano_roll(OUT / f"roll_{s['name']}.png", s, sim.events,
                   f"{s['name']}  tempo {s['tempo']}  "
                   f"{s['rows'] // 16} bars  {s['seconds']:.0f}s")
        secs = min(s["seconds"] * 1.15, 70.0)
        write_wav(OUT / f"{s['name']}.wav", synth(d, s, secs))
    if not want:
        sfx_report(d)
    print(f"\nwrote {OUT}")


# =============================================================================
# SFX
# =============================================================================
def sfx_steps(raw):
    """Decode a compiled sfx back into (frames, vol, duty/mode, timer|period)."""
    out = []
    i = 1
    while i < len(raw) and raw[i]:
        fr, v, lo, hi = raw[i:i + 4]
        out.append((fr, v, lo, hi))
        i += 4
    return out


def sfx_render(d, s):
    """Synthesise one sfx; also return its pitch/period contour for printing."""
    steps = sfx_steps(s["data"])
    total = sum(x[0] for x in steps)
    buf = [0.0] * (int((total + 12) * FRAME_SAMPLES) + 64)
    contour = []
    pos, ph, lfsr, ntim = 0.0, 0.0, 1, 0.0
    for fr, v, lo, hi in steps:
        start = int(pos)
        pos += fr * FRAME_SAMPLES
        cnt = int(pos) - start
        if s["ch"] == 3:
            vol, period = v & 0x0F, lo & 0x0F
            contour.append(f"n{period}")
            amp = 0.5 * vol / 15.0
            p = NOISE_PERIOD[period]
            for i in range(cnt):
                ntim -= music.CPU_HZ / SR
                while ntim <= 0:
                    ntim += p
                    fb = (lfsr ^ (lfsr >> 1)) & 1
                    lfsr = (lfsr >> 1) | (fb << 14)
                buf[start + i] += amp if (lfsr & 1) == 0 else -amp
        else:
            vol, duty = v & 0x0F, (v >> 6) & 3
            t = ((hi & 0x07) << 8) | lo
            f = music.CPU_HZ / (16.0 * (t + 1))
            m = int(round(69 + 12 * math.log2(f / 440.0)))
            contour.append(midi_name(m))
            amp, df, step = 0.5 * vol / 15.0, DUTY_FRAC[duty], f / SR
            for i in range(cnt):
                ph += step
                if ph >= 1.0:
                    ph -= 1.0
                buf[start + i] += amp if ph < df else -amp
    return buf, contour, total


def sfx_report(d):
    print("\nsfx  (ch1 = pulse 2, so no cue ever steals the melody; "
          "ch3 = noise)")
    for s in d["sfx"]:
        buf, contour, total = sfx_render(d, s)
        write_wav(OUT / f"sfx_{s['name']}.wav", buf)
        print(f"  {s['name']:10s} ch{s['ch']} {total:3d}f ({total / 60:.2f}s)  "
              + " ".join(contour))


if __name__ == "__main__":
    main()
