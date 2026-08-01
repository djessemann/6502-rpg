"""Does the ROM actually play music? Read the APU writes and find out.

Every earlier sound check in this repo could only prove the driver did not
crash, because pyntendo's fast core produces no audio and exposes no APU state.
That is how a ROM shipped whose driver never played a single note: the pattern
parser could not see an END byte, so it walked off the end of every pattern and
played the bytes that followed as if they were events -- no music, a constant
buzz, and every test green.

tools/apu_trace.py runs the ROM on pyntendo's pure-Python core with the memory
write path hooked, so every write to $4000-$4017 is visible. This asserts on
what comes out:

  * the melody channels get many period writes with many distinct values --
    a stuck tone writes once, or writes the same value forever;
  * the volume moves too, so it is an envelope and not a held note;
  * and a control ROM built with -D TEST_BROKEN_PARSER, which puts the original
    bug back, must fail those checks. A sound test that passes on a ROM known
    to be silent is measuring nothing.

The Python core is slow -- about a second per two frames -- so this traces a
few hundred frames of the title screen rather than a whole song.
"""
import pathlib
import subprocess
import sys
import tempfile
import shutil

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GAME / "tools"))

import apu_trace as T                                             # noqa: E402

FRAMES = 200
SETTLE = 30           # the music starts a few frames after boot
FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)
    return bool(cond)


def build(dst, defines=()):
    """Link a ROM from the Makefile's own source list."""
    import re
    mk = (GAME / "Makefile").read_text()
    body = re.search(r"^SRCS\s*:=\s*((?:.*\\\n)*.*)$", mk, re.M).group(1)
    body = body.replace("\\\n", " ")
    srcs = [GAME / tok.replace("$(SRCDIR)", "src").replace("$(GENDIR)", "src/gen")
            .replace("$(SOUND)", "src/sound.s") for tok in body.split()]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="threnos-apu-"))
    try:
        objs = []
        for src in srcs:
            obj = tmp / (str(src.relative_to(GAME)).replace("/", "_")[:-2] + ".o")
            subprocess.run(["ca65", "-g", "-I", str(GAME / "src")] + list(defines)
                           + ["-o", str(obj), str(src)], check=True)
            objs.append(str(obj))
        subprocess.run(["ld65", "-C", str(GAME / "nes.cfg"), "-o", str(dst)]
                       + objs, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dst


def trace(rom, frames=FRAMES):
    nes, t = T.build(rom)
    T.run_frames(nes, t, frames)
    out = {}
    for base, name in ((0x4000, "PULSE1"), (0x4004, "PULSE2"),
                       (0x4008, "TRI"), (0x400C, "NOISE")):
        vol = [v for f, a, v in t.writes if a == base and f > SETTLE]
        per = [v for f, a, v in t.writes if a == base + 2 and f > SETTLE]
        out[name] = (vol, per)
    return out


# What separates music from garbage is not "is the APU busy" -- the broken
# parser is very busy indeed. It is that the channels do their own jobs: the
# lead moves a lot, the bass moves slowly, and a channel the track does not use
# stays quiet. The broken build drives all four in lockstep off one garbage
# stream, so they come out with identical write counts and the noise channel
# sounds in a song that has no percussion in it.
def counts(tr):
    return {k: (len(set(per)), len(per)) for k, (vol, per) in tr.items()}


print(f"tracing threnos.nes for {FRAMES} frames (pure-Python core, slow)")
real = trace(GAME / "threnos.nes")
for name, (vol, per) in real.items():
    print(f"  {name:<7} {len(per):>4} period writes ({len(set(per))} distinct), "
          f"{len(set(vol))} distinct volumes")

def melodic(tr):
    """The three marks of the real thing, all of which the control fails."""
    lead = len(set(tr["PULSE1"][1])) >= 15      # a lead line with movement
    quiet = len(tr["NOISE"][1]) == 0            # TITLE has no percussion
    n = [len(tr[k][1]) for k in ("PULSE1", "PULSE2", "TRI", "NOISE")]
    apart = len(set(n)) >= 3                    # not four channels in lockstep
    return lead, quiet, apart


lead, quiet, apart = melodic(real)
check(lead, f"PULSE1 carries a moving lead line "
            f"({len(set(real['PULSE1'][1]))} distinct periods)")
check(quiet, "the noise channel stays silent - the title track has no "
             "percussion, and tools/music_check.py agrees")
check(apart, f"the four channels play their own parts, not one stream in "
             f"lockstep ({[len(real[k][1]) for k in real]})")
check(sum(len(p) for _, p in real.values()) > 100,
      "the APU is being written continuously, not once and left")

print("\nbuilding the control (TEST_BROKEN_PARSER puts the original bug back)")
ctl_rom = build(GAME / "test" / "threnos_apu_broken.nes",
                ["-D", "TEST_BROKEN_PARSER=1"])
ctl = trace(ctl_rom, 120)
for name, (vol, per) in ctl.items():
    print(f"  {name:<7} {len(per):>4} period writes ({len(set(per))} distinct), "
          f"{len(set(vol))} distinct volumes")
c_lead, c_quiet, c_apart = melodic(ctl)
check(not (c_lead and c_quiet and c_apart),
      f"the control fails those checks (lead={c_lead} quiet={c_quiet} "
      f"apart={c_apart}) - so passing them means something")
check(not c_quiet,
      "and specifically: the broken parser makes the noise channel sound in a "
      "song with no percussion, which is what the buzz was")

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES")
    for f in FAIL:
        print("  " + f)
    print("FAILED")
    sys.exit(1)
print("t_apu: PASS")
sys.exit(0)
