"""Headless verification harness for THRENOS.

Drives the ROM through pyntendo, scripts the controller, captures frames as
PNGs and lets tests assert on what is actually on screen.

Button order for controller1_state: [A, B, Select, Start, Up, Down, Left, Right]
"""
import os
import sys
import pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROM = ROOT / "threnos.nes"
SHOTS = ROOT / "test" / "shots"

A, B, SELECT, START, UP, DOWN, LEFT, RIGHT = range(8)
NONE = [0] * 8


def press(*buttons):
    s = [0] * 8
    for b in buttons:
        s[b] = 1
    return s


class Run:
    def __init__(self, rom=None, quiet=True):
        if quiet:
            self._devnull = open(os.devnull, "w")
            old = sys.stdout
            sys.stdout = self._devnull
        from nes import NES
        self.nes = NES(str(rom or ROM))
        if quiet:
            sys.stdout = old
        self.frame = None
        self.n = 0
        SHOTS.mkdir(parents=True, exist_ok=True)

    def step(self, state=NONE, n=1):
        for _ in range(n):
            self.frame = self.nes.run_frame_headless(controller1_state=state)
            self.n += 1
        return self.frame

    def tap(self, button, hold=3, gap=6):
        """Press a button for `hold` frames then release for `gap` frames."""
        self.step(press(button), hold)
        self.step(NONE, gap)
        return self.frame

    def hold(self, button, n):
        return self.step(press(button), n)

    def idle(self, n=1):
        return self.step(NONE, n)

    def shot(self, name):
        path = SHOTS / f"{name}.png"
        img = Image.fromarray(np.asarray(self.frame, dtype=np.uint8), "RGB")
        img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
        img.save(path)
        return path

    def nonblack(self):
        return int(np.count_nonzero(np.asarray(self.frame).sum(axis=2)))

    def digest(self):
        """A stable fingerprint of the current frame."""
        import hashlib
        return hashlib.sha1(np.asarray(self.frame, dtype=np.uint8).tobytes()).hexdigest()[:12]

    def region(self, x, y, w, h):
        return np.asarray(self.frame)[y:y + h, x:x + w]
