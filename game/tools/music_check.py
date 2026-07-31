#!/usr/bin/env python3
"""Check the compiled THRENOS soundtrack by simulating the driver in Python.

pyntendo gives us no audio, so this is how the music is actually verified: the
same control flow as src/sound.s runs over the same compiled bytes, and we
report what comes out — rows, loop point, duration, note range and timer range
per channel — and assert the things that would be silent bugs on hardware:

  * no song is silent, and no channel is accidentally empty
  * every looping song is at least MIN_SECONDS long (VICTORY/FANFARE excepted)
  * every note every song plays, including arpeggio offsets and vibrato swing,
    lands on a legal 11-bit APU timer (8..2047)
  * every pattern's rows add up to exactly PAT_ROWS, which the driver assumes
  * SFX steps are well formed and their pulse timers are legal too

It also carries a cycle model of the driver (costs counted by hand off the
assembly, see CYC below) so the worst-case NMI cost is measured over the real
data instead of guessed at.

Run: python3 tools/music_check.py
"""
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import music                                                   # noqa: E402
import songs                                                   # noqa: E402

MIN_SECONDS = 10.0
SHORT_OK = {"VICTORY", "FANFARE"}
TIMER_MIN, TIMER_MAX = 8, 2047

# --- cycle costs, counted instruction by instruction off src/sound.s ----------
# Each entry is one straight-line block of the driver; the simulator adds the
# ones it actually executes, exactly as the 6502 would.
CYC = dict(
    tick_base=36,       # request checks + jmp SfxFrame + idle SfxFrame
    row_no=9,           # dec snd_rowt / bne (no row this frame)
    row_yes=16,         # dec / bne not taken / reload the tempo
    call=8,             # ldx #n + jsr (the rts is inside each block below)
    ra_inactive=13,
    ra_hold=21,
    ra_enter=32,        # flag+dec+beq, load stream pointer, ldy #0
    ra_fetch=7,         # lda (ptr),y / iny
    ra_d_end=3, ra_d_note=7, ra_d_rest=9, ra_d_slur=13, ra_d_inst=15,
    ra_d_len=26,
    ra_note=38, ra_rest=17, ra_slur=22, ra_inst=15,
    ra_dur=37,          # set duration, write the pointer back, rts
    ra_take=107,        # next pattern out of the order row + its 2-byte header
    ra_wrap=28,         # extra when the order wraps to the loop point
    cf_inactive=13, cf_steady=17, cf_sfx=22,
    cf_head=24,
    cf_mute=68,
    cf_env_move=37, cf_env_sus=22,
    cf_modchk=14,
    cf_volonly=18,      # + the per-channel volume write below
    cf_vol_pulse=18, cf_vol_noise=17, cf_vol_tri=19,
    cf_arp_off=14, cf_arp_on=57,
    cf_pitch=23,
    cf_vib_off=11, cf_vib_on=77,
    cf_wr_pulse=26, cf_wr_tri=21,
    cf_wrpitch=33, cf_wrpitch_skip=28,
    cf_noise=50,
    cf_finish=24,
)

END, REST, SLUR, INST = 0x00, 0x61, 0x62, 0x63


class Chan:
    def __init__(self, ch):
        self.ch = ch
        self.pat = None         # (pattern index, byte offset)
        self.dur = 1
        self.len = 4
        self.inst = 0
        self.note = 0
        self.env = 0
        self.vibp = 0
        self.arpp = 0
        self.hi = 0
        self.ordi = 0
        self.cnt = 0
        self.active = True
        self.steady = False
        self.keyon = False


class Sim:
    """A transliteration of src/sound.s over the compiled data."""

    def __init__(self, d, song):
        self.d = d
        self.song = song
        self.pats = d["patterns"]
        self.tempo = song["tempo"]
        self.rowt = 1
        self.chans = [Chan(i) for i in range(4)]
        for c in self.chans:
            c.cnt = song["n_order"]
        self.cycles = []
        self.notes = [[] for _ in range(4)]     # (row, pitch) actually keyed
        self.timers = [[] for _ in range(4)]    # every timer value written
        self.row = 0
        self.frames = 0
        self.stopped = False

    # -- row parsing ----------------------------------------------------------
    def next_pattern(self, c):
        cost = 0
        if c.cnt == 0:
            if self.song["loop_n"] == 0:
                c.active = False
                return None, cost
            c.cnt = self.song["loop_n"]
            c.ordi = self.song["n_order"] - self.song["loop_n"]
            cost += CYC["ra_wrap"]
        c.cnt -= 1
        p = self.song["order"][c.ordi][c.ch]
        c.ordi += 1
        return p, cost + CYC["ra_take"]

    def row_advance(self, c):
        if not c.active:
            return CYC["ra_inactive"]
        c.dur -= 1
        if c.dur > 0:
            return CYC["ra_hold"]
        cost = CYC["ra_enter"]
        while True:
            if c.pat is None:
                p, extra = self.next_pattern(c)
                cost += CYC["ra_d_end"] + extra
                if p is None:
                    return cost
                c.inst = self.pats[p][0]        # pattern header
                c.len = self.pats[p][1]
                c.pat = (p, 2)
                continue
            pi, off = c.pat
            data = self.pats[pi]
            if off >= len(data):
                raise AssertionError(f"pattern {pi} ran off the end")
            b = data[off]
            off += 1
            cost += CYC["ra_fetch"]
            if b == END:
                c.pat = None
                continue
            c.pat = (pi, off)
            if b < REST:                                  # note
                cost += CYC["ra_d_note"] + CYC["ra_note"]
                c.note = b
                c.env = self.d["inst_env"][c.inst]
                c.vibp = 0
                c.arpp = 0
                c.keyon = True
                c.steady = False
                self.notes[c.ch].append((self.row, b, c.inst))
                break
            if b == REST:
                cost += CYC["ra_d_rest"] + CYC["ra_rest"]
                c.note = 0
                c.steady = False
                break
            if b == SLUR:
                c.note = data[off]
                c.pat = (pi, off + 1)
                cost += CYC["ra_d_slur"] + CYC["ra_slur"]
                c.steady = False
                break
            if b == INST:
                c.inst = data[off]
                c.pat = (pi, off + 1)
                cost += CYC["ra_d_inst"] + CYC["ra_inst"]
                continue
            c.len = b - 0x63
            cost += CYC["ra_d_len"]
        c.dur = c.len
        return cost + CYC["ra_dur"]

    # -- per-frame channel update --------------------------------------------
    def chan_frame(self, c):
        d = self.d
        if not c.active:
            return CYC["cf_inactive"]
        if c.steady:
            return CYC["cf_steady"]
        cost = CYC["cf_head"]
        if c.note == 0:
            c.steady = True
            c.keyon = False
            return CYC["cf_mute"]

        steady = True
        ev = d["env_data"][c.env]
        if ev & 0x80:
            vol = ev & 0x0F
            cost += CYC["cf_env_sus"]
        else:
            vol = ev
            c.env += 1
            steady = False
            cost += CYC["cf_env_move"]

        arp = d["inst_arp"][c.inst]
        vib = d["inst_vib"][c.inst]
        cost += CYC["cf_modchk"]
        if not arp and not vib and not c.keyon:
            cost += CYC["cf_volonly"]
            cost += CYC[("cf_vol_pulse", "cf_vol_pulse",
                         "cf_vol_tri", "cf_vol_noise")[c.ch]]
            c.keyon = False
            c.steady = steady
            return cost + CYC["cf_finish"]

        note = c.note
        if arp:
            steady = False
            c.arpp = (c.arpp + 1) % 3
            if c.arpp == 1:
                note += arp >> 4
            elif c.arpp == 2:
                note += arp & 0x0F
            cost += CYC["cf_arp_on"]
        else:
            cost += CYC["cf_arp_off"]

        if c.ch == 3:
            cost += CYC["cf_noise"]
            c.keyon = False
            c.steady = steady
            return cost + CYC["cf_finish"]

        if note >= music.N_PITCH:
            raise AssertionError(f"pitch index {note} past the pitch table")
        t = d["pitch"][note]
        cost += CYC["cf_pitch"]

        if vib:
            steady = False
            c.vibp = (c.vibp + vib) & 0xFF
            delta = VIB_TAB[d["inst_vibd"][c.inst] | (c.vibp >> 4)]
            t += delta
            cost += CYC["cf_vib_on"]
        else:
            cost += CYC["cf_vib_off"]

        self.timers[c.ch].append(t)
        cost += CYC["cf_wr_tri"] if c.ch == 2 else CYC["cf_wr_pulse"]
        hi = (t >> 8) & 0xFF
        if hi != c.hi or c.keyon:
            c.hi = hi
            cost += CYC["cf_wrpitch"]
        else:
            cost += CYC["cf_wrpitch_skip"]
        c.keyon = False
        c.steady = steady
        return cost + CYC["cf_finish"]

    # -- one frame ------------------------------------------------------------
    def frame(self):
        cost = CYC["tick_base"]
        self.rowt -= 1
        if self.rowt == 0:
            self.rowt = self.tempo
            cost += CYC["row_yes"]
            for c in self.chans:
                cost += CYC["call"] + self.row_advance(c)
            self.row += 1
        else:
            cost += CYC["row_no"]
        for c in self.chans:
            cost += CYC["call"] + self.chan_frame(c)
        self.frames += 1
        self.cycles.append(cost)
        if not any(c.active for c in self.chans):
            self.stopped = True
        return cost


def _signed(b):
    return b - 256 if b > 127 else b


# Same table as vib_tab in src/sound.s.
VIB_TAB = [_signed(b) for b in bytes([
    0, 1, 2, 3, 3, 3, 2, 1, 0, 0xFF, 0xFE, 0xFD, 0xFD, 0xFD, 0xFE, 0xFF,
    0, 2, 4, 6, 6, 6, 4, 2, 0, 0xFE, 0xFC, 0xFA, 0xFA, 0xFA, 0xFC, 0xFE,
    0, 3, 6, 9, 9, 9, 6, 3, 0, 0xFD, 0xFA, 0xF7, 0xF7, 0xF7, 0xFA, 0xFD,
    0, 5, 10, 15, 15, 15, 10, 5, 0, 0xFB, 0xF6, 0xF1, 0xF1, 0xF1, 0xF6, 0xFB])]


def note_name(idx):
    midi = music.BASE_MIDI + idx
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"


def check_patterns(d):
    """Every pattern must fill exactly PAT_ROWS rows; the driver assumes it."""
    bad = 0
    for i, p in enumerate(d["patterns"]):
        rows, cur, j = 0, p[1], 2
        while j < len(p):
            b = p[j]
            j += 1
            if b == END:
                break
            if b == INST or b == SLUR:
                if b == SLUR:
                    rows += cur
                j += 1
            elif b >= 0x64:
                cur = b - 0x63
            else:
                rows += cur
        if rows != music.PAT_ROWS:
            print(f"  !! pattern {i}: {rows} rows, expected {music.PAT_ROWS}")
            bad += 1
    return bad


def main():
    d = music.compile_all(songs.SONGS, songs.INSTRUMENTS,
                          songs.ENVELOPES, songs.SFX)
    fail = []

    print(f"patterns: {len(d['patterns'])} unique, "
          f"{sum(len(p) for p in d['patterns'])} bytes")
    if check_patterns(d):
        fail.append("pattern row counts")

    worst_frame = 0
    worst_song = ""
    chan_names = ("P1", "P2", "TRI", "NOI")

    for s in d["songs"]:
        sim = Sim(d, s)
        # one full pass through the order, plus a loop-around, plus slack
        target = s["rows"] + music.PAT_ROWS
        while sim.row < target and not sim.stopped:
            sim.frame()
        secs = s["seconds"]
        loop_secs = s["loop_idx"] * music.PAT_ROWS * s["tempo"] / 60.0
        mx = max(sim.cycles)
        avg = sum(sim.cycles) / len(sim.cycles)
        if mx > worst_frame:
            worst_frame, worst_song = mx, s["name"]

        print(f"\n{s['name']}  id {s['id']}  tempo {s['tempo']} "
              f"({60 / s['tempo']:.1f} rows/s)")
        print(f"  {s['rows']} rows / {s['n_order']} patterns, "
              f"{secs:.1f}s" +
              (f", loops to row {s['loop_idx'] * music.PAT_ROWS} "
               f"({loop_secs:.1f}s)" if s["loop_n"] else ", one-shot"))
        print(f"  frames simulated {sim.frames}, "
              f"cycles/frame avg {avg:.0f} max {mx}")
        for ci in range(4):
            notes = sim.notes[ci]
            if not notes:
                # a track with no percussion is a choice; a silent melodic
                # channel is a bug.
                print(f"  {chan_names[ci]:3s}: silent"
                      + ("  (no percussion in this track)" if ci == 3 else ""))
                if ci != 3:
                    fail.append(f"{s['name']} {chan_names[ci]} is silent")
                continue
            lo = min(n[1] for n in notes)
            hi = max(n[1] for n in notes)
            if ci == 3:
                print(f"  NOI: {len(notes):4d} hits, "
                      f"noise periods {lo - 1}..{hi - 1}")
                continue
            tmin = min(sim.timers[ci])
            tmax = max(sim.timers[ci])
            octave = " (an octave down on the triangle)" if ci == 2 else ""
            print(f"  {chan_names[ci]:3s}: {len(notes):4d} notes, "
                  f"{note_name(lo)}..{note_name(hi)}, "
                  f"timers {tmin}..{tmax}{octave}")
            if not (TIMER_MIN <= tmin and tmax <= TIMER_MAX):
                fail.append(f"{s['name']} {chan_names[ci]}: timer "
                            f"{tmin}..{tmax} outside {TIMER_MIN}..{TIMER_MAX}")
        if secs < MIN_SECONDS and s["name"] not in SHORT_OK:
            fail.append(f"{s['name']} is only {secs:.1f}s long")

    print("\nsfx:")
    for s in d["sfx"]:
        data = s["data"]
        steps = (len(data) - 2) // 4
        frames = sum(data[1 + 4 * i] for i in range(steps))
        print(f"  {s['name']:10s} ch {s['ch']}  {steps} steps, "
              f"{frames} frames ({frames / 60:.2f}s), {len(data)} bytes")
        if steps == 0 or frames == 0:
            fail.append(f"sfx {s['name']} is empty")
        for i in range(steps):
            lo = data[3 + 4 * i]
            hi = data[4 + 4 * i]
            if s["ch"] in (0, 1):
                t = ((hi & 0x07) << 8) | lo
                if not TIMER_MIN <= t <= TIMER_MAX:
                    fail.append(f"sfx {s['name']} step {i}: timer {t}")

    sz = d["sizes"]
    print("\nbytes: " + ", ".join(f"{k} {v}" for k, v in sz.items()))
    print(f"worst frame over all songs: {worst_frame} cycles ({worst_song}), "
          f"{worst_frame / 29780 * 100:.1f}% of an NTSC frame")

    if fail:
        print("\nFAILED:")
        for f in fail:
            print("  " + f)
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
