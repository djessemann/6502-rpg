#!/usr/bin/env python3
"""Watch what the ROM actually writes to the APU, frame by frame.

pyntendo's fast Cython core produces no audio and exposes no APU state, which
is why every sound "test" in this repo could only prove the driver did not
crash. Its pure-Python core is slow but fully inspectable: this loads the ROM
there, hooks the memory write path, and records every write to $4000-$4017 with
the frame it happened on. RAM is readable too, so driver state can be dumped
alongside.

That turns "the sound is a constant buzz" into something with an address on it.

Run:  python3 tools/apu_trace.py [frames] [--rom PATH] [--keys A,A,A]
"""
import contextlib
import io
import os
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

# pycore.system imports pygame only for its interactive loop.
for name in ("pygame", "pygame.locals"):
    if name not in sys.modules:
        m = types.ModuleType(name)
        sys.modules[name] = m
sys.modules["pygame"].locals = sys.modules["pygame.locals"]
# peripherals.py builds a keyboard map out of pygame key constants at import
# time; any integers will do, nothing here presses a key.
for _i, _k in enumerate(("K_w K_s K_a K_d K_g K_h K_k K_l K_p K_o K_i K_u "
                         "K_ESCAPE K_SPACE K_RETURN").split()):
    setattr(sys.modules["pygame"], _k, 1000 + _i)


class _Surface:
    """Enough of a pygame surface for the screen object to construct.

    Nothing here draws: this trace only wants the CPU's APU writes, so the
    display side is stubbed out entirely rather than pulled in.
    """

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


sys.modules["pygame"].Surface = _Surface
sys.modules["pygame"].surfarray = types.SimpleNamespace(
    pixels2d=lambda *a: None, blit_array=lambda *a: None)
sys.modules["pygame"].display = types.SimpleNamespace(
    set_mode=lambda *a, **k: _Surface(), flip=lambda: None,
    set_caption=lambda *a: None)
sys.modules["pygame"].font = types.SimpleNamespace(
    init=lambda: None, SysFont=lambda *a, **k: _Surface())
sys.modules["pygame"].transform = types.SimpleNamespace(
    scale=lambda *a: _Surface())
sys.modules["pygame"].freetype = types.SimpleNamespace(
    init=lambda: None, SysFont=lambda *a, **k: _Surface(),
    Font=lambda *a, **k: _Surface())

from nes.pycore.system import NES                              # noqa: E402
from nes.pycore.memory import NESMappedRAM                     # noqa: E402
from nes.rom import ROM                                        # noqa: E402
from nes.pycore.carts import CartBase                          # noqa: E402
import nes.pycore.system as _sys                               # noqa: E402

REG = {
    0x4000: "P1 vol/duty", 0x4001: "P1 sweep", 0x4002: "P1 lo", 0x4003: "P1 hi",
    0x4004: "P2 vol/duty", 0x4005: "P2 sweep", 0x4006: "P2 lo", 0x4007: "P2 hi",
    0x4008: "TRI linear", 0x400A: "TRI lo", 0x400B: "TRI hi",
    0x400C: "NOI vol", 0x400E: "NOI period", 0x400F: "NOI len",
    0x4010: "DMC freq", 0x4011: "DMC raw", 0x4012: "DMC addr",
    0x4013: "DMC len", 0x4015: "enable", 0x4017: "frame ctr",
}


class _NullScreen:
    """The video side, stubbed. This trace only reads the CPU's APU writes."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


class MMC3(CartBase):
    """MMC3 (mapper 4) for the pure-Python core, which only ships mapper 0.

    Only what the CPU needs is real: the two switchable 8K PRG windows at
    $8000/$A000, the two fixed ones, and the battery RAM at $6000. CHR reads
    return the right bytes but nothing here cares what the screen looks like --
    this exists to watch APU writes, and the CPU is what makes them.
    """

    def __init__(self, prg, chr_data, mirror):
        super().__init__()
        self.prg = bytearray(prg)
        self.chr = bytearray(chr_data) if chr_data else bytearray(8 * 1024)
        # the Python VRAM reads cart.chr_mem directly rather than via
        # read_ppu, so expose the first 8K under that name too
        self.chr_mem = self.chr
        self.ram = bytearray(8 * 1024)
        self.nametable_mirror_pattern = list(mirror)
        self.n_prg = len(self.prg) // 0x2000
        self.regs = [0] * 8
        self.select = 0
        self.prg_mode = 0
        self.chr_inv = 0

    def _prg_bank(self, slot):
        """slot 0 = $8000, 1 = $A000, 2 = $C000, 3 = $E000."""
        last, last1 = self.n_prg - 1, self.n_prg - 2
        if self.prg_mode == 0:
            return (self.regs[6], self.regs[7], last1, last)[slot]
        return (last1, self.regs[7], self.regs[6], last)[slot]

    def read(self, address):
        if address < 0x8000:
            return self.ram[address - 0x6000] if address >= 0x6000 else 0
        slot = (address - 0x8000) >> 13
        bank = self._prg_bank(slot) % self.n_prg
        return self.prg[bank * 0x2000 + (address & 0x1FFF)]

    def write(self, address, value):
        if 0x6000 <= address < 0x8000:
            self.ram[address - 0x6000] = value
            return
        even = (address & 1) == 0
        if address < 0xA000:
            if even:
                self.select = value
                self.prg_mode = (value >> 6) & 1
                self.chr_inv = (value >> 7) & 1
            else:
                self.regs[self.select & 7] = value
        elif address < 0xC000:
            if even:
                self.nametable_mirror_pattern = ([0, 0, 1, 1] if value & 1
                                                 else [0, 1, 0, 1])
        # IRQ registers ($C000-$FFFF) are ignored: the engine disables them.

    def read_ppu(self, address):
        return self.chr[address % len(self.chr)]

    def write_ppu(self, address, value):
        pass



class Trace:
    def __init__(self):
        self.writes = []          # (frame, addr, value)
        self.frame = 0


def build(rom):
    t = Trace()
    orig = NESMappedRAM.write

    def write(self, address, value):
        if 0x4000 <= address <= 0x4017 and address != 0x4014 \
                and address != 0x4016:
            t.writes.append((t.frame, address, value & 0xFF))
        return orig(self, address, value)

    NESMappedRAM.write = write
    _sys.Screen = _NullScreen
    ROM.get_cart = lambda self, prg=None: MMC3(
        self.prg_rom_data, self.chr_rom_data, self.mirror_pattern)
    with contextlib.redirect_stdout(io.StringIO()):
        nes = NES(str(rom))
    return nes, t


def run_frames(nes, t, n, keys=()):
    """Run n frames. `keys` is a list of (frame, button) presses to inject."""
    from nes.pycore.system import NES as _N            # noqa: F401
    pressed = {}
    for f, b in keys:
        pressed.setdefault(f, []).append(b)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for _ in range(n):
            held = pressed.get(t.frame, [])
            for b in held:
                nes.controller1.is_pressed[b] = 1
            done = False
            while not done:
                done = nes.step()
            for b in held:
                nes.controller1.is_pressed[b] = 0
            t.frame += 1
    return t


def report(t, first=0, last=None):
    last = t.frame if last is None else last
    ws = [w for w in t.writes if first <= w[0] < last]
    print(f"{len(ws)} APU writes over frames {first}..{last}")
    by_reg = {}
    for f, a, v in ws:
        by_reg.setdefault(a, []).append((f, v))
    print(f"\n{'reg':<6} {'name':<12} {'writes':>7}  {'distinct values':>15}  last")
    for a in sorted(by_reg):
        vals = [v for _, v in by_reg[a]]
        print(f"${a:04X} {REG.get(a, '?'):<12} {len(vals):>7}  "
              f"{len(set(vals)):>15}  ${vals[-1]:02X}")
    return by_reg


def main():
    args = sys.argv[1:]
    rom = ROOT / "threnos.nes"
    if "--rom" in args:
        i = args.index("--rom")
        rom = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    frames = int(args[0]) if args else 150
    print(f"tracing {rom.name} for {frames} frames (pure-Python core, slow)")
    nes, t = build(rom)
    run_frames(nes, t, frames)
    by_reg = report(t)

    print("\nthe first 40 writes:")
    for f, a, v in t.writes[:40]:
        print(f"  f{f:<4} ${a:04X} {REG.get(a, '?'):<12} ${v:02X}")

    # a channel that never changes its period after the music starts is a buzz
    print("\nper-channel movement after frame 30:")
    for base, name in ((0x4000, "PULSE1"), (0x4004, "PULSE2"),
                       (0x4008, "TRI"), (0x400C, "NOISE")):
        lo = [v for f, v in by_reg.get(base + 2, []) if f > 30]
        vol = [v for f, v in by_reg.get(base, []) if f > 30]
        print(f"  {name:<7} vol writes {len(vol):>4} ({len(set(vol))} distinct)"
              f"   period writes {len(lo):>4} ({len(set(lo))} distinct)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
