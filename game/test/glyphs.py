"""Read the text off a captured frame.

The menu, shop and save screens draw their glyphs from the resident font bank
(tools/font.py) in sub-palette colour 3, on a black background, at a fixed 8x8
tile grid — so a test can recover the actual characters instead of guessing
from pixel counts. Every assertion in t_menu.py / t_shop.py that says "the
screen says X" goes through here.

pyntendo crops 8 pixels off each edge, so screen tile (col,row) lives at frame
pixel (col*8-8, row*8-8): columns 1..30 and rows 1..28 are readable, 0 and 31
(and rows 0/29) are in the overscan and are not.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import font  # noqa: E402

BRIGHT = 500          # colour 3 is white (~710); the frame colour is ~250


def _glyph_bitmaps():
    """char -> 8x8 bool array, exactly as tools/font.py lays a glyph out."""
    out = {}
    for ch in font.CHARSET:
        m = np.zeros((8, 8), dtype=bool)
        if ch != ' ':
            bits = font.GLYPHS[ch]
            for y in range(7):
                for x in range(5):
                    if bits[y] & (0x10 >> x):
                        m[y][1 + x] = True
        out[ch] = m
    out['>'] = np.zeros((8, 8), dtype=bool)     # the menu cursor tile
    for y, b in enumerate(font.CURSOR):
        for x in range(5):
            if b & (0x10 >> x):
                out['>'][y][1 + x] = True
    return out


GLYPHS = _glyph_bitmaps()


def tile(frame, col, row):
    """The 8x8 on/off bitmap of one screen tile, or None if it is off-screen."""
    a = np.asarray(frame)
    y, x = row * 8 - 8, col * 8 - 8
    if y < 0 or x < 0 or y + 8 > a.shape[0] or x + 8 > a.shape[1]:
        return None
    return a[y:y + 8, x:x + 8, :].sum(axis=2) > BRIGHT


def char_at(frame, col, row):
    """Best-matching character for one tile, or '?' if nothing matches well."""
    t = tile(frame, col, row)
    if t is None:
        return '?'
    if not t.any():
        return ' '
    best, score = '?', 0
    for ch, m in GLYPHS.items():
        hit = int((m == t).sum())
        if hit > score:
            best, score = ch, hit
    return best if score >= 62 else '?'


def read(frame, col, row, n):
    """n characters starting at screen tile (col,row)."""
    return "".join(char_at(frame, col + i, row) for i in range(n))


def line(frame, row):
    """The whole visible width of a screen row (columns 1..30)."""
    return read(frame, 1, row, 30)


def screen(frame, rows=range(1, 29)):
    return [line(frame, r) for r in rows]


def dump(frame, label=""):
    if label:
        print(f"--- {label}")
    for r in range(1, 29):
        s = line(frame, r)
        if s.strip():
            print(f"{r:2d} |{s}|")


def says(frame, text, rows=range(1, 29)):
    """True if `text` appears anywhere on the screen."""
    return any(text in line(frame, r) for r in rows)
