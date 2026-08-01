"""Verify the sound driver in the running ROM.

pyntendo produces no audio, so this test proves the two things that CAN be
observed from outside: that the driver runs without disturbing the game, and
that it costs no visible time.

It builds a second ROM from the same sources with -D SOUND_SELFTEST, which makes
SoundTick poke its own music_req/sfx_req bytes (the same interface the engine
will use) so that music and sfx are actually playing. Then:

  (a) boot + render: both ROMs draw a real picture, and the frame digest with
      music playing is identical to the digest before the music started and to
      the silent ROM's — the driver must not touch the PPU, the VBUF or timing.
  (b) no slowdown, no hang: 600 frames of scripted input reach the same frames
      on both ROMs, in comparable wall-clock time.
  (c) the check in (a) cannot pass vacuously: the self-test build also asserts
      its own liveness from inside the ROM (it counts the frames in which some
      channel is sounding and blanks the screen if a whole 256-frame window
      goes by near-silent). A third ROM, built with SOUND_SELFTEST_DEAD so the
      driver is never given a song, is run as a negative control and must go
      black.

The musical content itself is checked by tools/music_check.py, which simulates
the driver over the compiled data; this test runs it too.
"""
import re
import subprocess
import sys
import pathlib
import shutil
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harness import Run, press, NONE, DOWN, RIGHT, UP, LEFT      # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def makefile_sources():
    """The SRCS list out of the Makefile, so this can't drift from the build."""
    mk = (ROOT / "Makefile").read_text()
    body = re.search(r"^SRCS\s*:=\s*((?:.*\\\n)*.*)$", mk, re.M).group(1)
    body = body.replace("\\\n", " ")
    out = []
    for tok in body.split():
        tok = (tok.replace("$(SRCDIR)", "src").replace("$(GENDIR)", "src/gen")
                  .replace("$(SOUND)", "src/sound.s"))
        out.append(ROOT / tok)
    return out


def build_selftest(dst, dead=False, selftest=True):
    """Assemble every source and link a test ROM.

    Every ROM here is built with TEST_SKIP_TITLE: the real game boots to the
    title screen, which is a still picture, and this test needs the field --
    it measures "renders a real picture" and "is still animating", neither of
    which a menu does.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="threnos-snd-"))
    defines = ["-D", "TEST_SKIP_TITLE=1"]
    if selftest:
        defines += ["-D", "SOUND_SELFTEST"]
    if dead:
        defines += ["-D", "SOUND_SELFTEST_DEAD"]
    objs = []
    try:
        for src in makefile_sources():
            # flatten the path into the name: src/text.s and src/gen/text.s
            # must not land on the same object file
            obj = tmp / (str(src.relative_to(ROOT)).replace("/", "_")[:-2] + ".o")
            subprocess.run(["ca65", "-g", "-I", str(ROOT / "src")] + defines
                           + ["-o", str(obj), str(src)], check=True)
            objs.append(str(obj))
        subprocess.run(["ld65", "-C", str(ROOT / "nes.cfg"), "-o", str(dst)]
                       + objs, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dst


# The same scripted input on both ROMs.
SCRIPT = [(NONE, 90), (press(DOWN), 40), (NONE, 20), (press(RIGHT), 40),
          (NONE, 60), (press(UP), 40), (press(LEFT), 40), (NONE, 270)]
PROBE = (100, 200, 300, 400, 500, 599)      # frames to fingerprint


def run_script(rom):
    r = Run(rom=rom)
    marks = {}
    frame = 0
    t0 = time.time()
    for state, n in SCRIPT:
        for _ in range(n):
            r.step(state)
            frame += 1
            if frame in PROBE:
                marks[frame] = (r.digest(), r.nonblack())
    return r, marks, time.time() - t0, frame


def main():
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    print("building the SOUND_SELFTEST ROM...")
    snd_rom = build_selftest(ROOT / "test" / "threnos_snd.nes")

    silent_rom = build_selftest(ROOT / "test" / "threnos_snd_silent.nes",
                                selftest=False)
    print("\nsilent ROM (test/threnos_snd_silent.nes):")
    r0, m0, t0, n0 = run_script(silent_rom)
    print(f"  {n0} frames in {t0:.1f}s")
    print("music ROM (test/threnos_snd.nes): song changes every 256 frames, "
          "sfx every 64")
    r1, m1, t1, n1 = run_script(snd_rom)
    print(f"  {n1} frames in {t1:.1f}s")

    r1.shot("sound_music_playing")

    # (a) it still boots and renders
    check(m1[100][1] > 20000, f"music ROM renders a real picture "
                              f"({m1[100][1]} non-black subpixels)")
    check(m0[100][1] > 20000, f"silent ROM renders a real picture "
                              f"({m0[100][1]} non-black subpixels)")

    # music starts at frame 256; frame 100 is before it, 400/500 well after.
    # Nothing on screen may change because of it.
    for f in PROBE:
        check(m0[f][0] == m1[f][0],
              f"frame {f}: music ROM digest {m1[f][0]} == silent {m0[f][0]}"
              + ("  (music playing)" if f > 256 else "  (before music)"))

    # (c) negative control: the same ROM with the driver never given a song
    dead_rom = build_selftest(ROOT / "test" / "threnos_snd_dead.nes", dead=True)
    rd = Run(rom=dead_rom)
    rd.step(NONE, 600)
    check(rd.nonblack() == 0,
          f"negative control: a driver with no song blanks the screen "
          f"({rd.nonblack()} non-black subpixels) - so the checks above are "
          f"proof the driver really is playing")

    # (b) no hang, no slowdown
    check(n1 == 600, "the music ROM ran all 600 frames without hanging")
    slow = t1 / max(t0, 1e-6)
    check(slow < 1.25, f"no slowdown: {t1:.1f}s vs {t0:.1f}s silent "
                       f"({slow:.2f}x)")
    # the game is still alive at the end: walking changed the picture
    check(m1[100][0] != m1[300][0], "the game is still animating with music on")

    print("\nrunning tools/music_check.py (simulates the driver over the "
          "compiled data)...")
    rc = subprocess.run([sys.executable, str(ROOT / "tools" / "music_check.py")],
                        cwd=ROOT, **quiet).returncode
    check(rc == 0, "music_check.py passes (run it directly for the report)")

    print()
    if FAIL:
        print(f"{len(FAIL)} FAILURES")
        for f in FAIL:
            print("  " + f)
        return 1
    print("t_sound: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
