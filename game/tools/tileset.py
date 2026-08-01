"""Tilesets: 16x16 metatile art -> deduplicated 8x8 CHR tiles + runtime tables.

A tileset is the art for one area (a region of the overworld, a town, a dungeon
style). It holds up to 128 metatiles, which compile down to at most 128 unique
8x8 tiles occupying BG tile indices $80-$FF (CHR banks R4 and R5).

Each metatile carries:
    art   16x16 characters, '.' / '1' / '2' / '3'  (colour index in its palette)
    pal   which BG sub-palette (0-2; 3 is reserved for the UI/window palette)
    prop  property bits (see PROP_*)

The runtime reads six parallel 128-byte tables (TL, TR, BL, BR, attr, prop),
copied into work RAM when a map loads.
"""
from chrlib import tile_from_rows

MAX_METATILES = 128
MAX_TILES = 128

# Property bits for a metatile.
PROP_SOLID   = 0x01     # blocks walking
PROP_WATER   = 0x02     # crossable only with the SKIFF
PROP_HIGH    = 0x04     # crossable only with the GRAV-LIFT
PROP_ENCTR   = 0x08     # random encounters happen here
PROP_DOOR    = 0x10     # stepping on it triggers the map's warp of that index
PROP_SLOW    = 0x20     # (marsh) doubles the encounter step cost
PROP_DAMAGE  = 0x40     # lava/rad: costs HP per step
PROP_COUNTER = 0x80     # shop counter: talk across it


class Tileset:
    def __init__(self, name, palettes):
        """palettes: 3 lists of 3 NES colour bytes (sub-palettes 0..2).
        Sub-palette 3 is always the UI palette, added by the builder."""
        self.name = name
        self.palettes = palettes
        assert len(palettes) == 3, name
        self.metas = []          # (name, art, pal, prop)
        self.index = {}

    def add(self, name, art, pal=0, prop=0):
        if name in self.index:
            raise ValueError(f"{self.name}: duplicate metatile {name}")
        if len(art) != 16 or any(len(r) != 16 for r in art):
            raise ValueError(f"{self.name}/{name}: art must be 16x16")
        self.index[name] = len(self.metas)
        self.metas.append((name, art, pal & 3, prop))
        return self.index[name]

    def id(self, name):
        return self.index[name]

    def compile(self):
        """-> dict with 'tiles' (list of 16-byte CHR tiles) and the six tables."""
        if len(self.metas) > MAX_METATILES:
            raise ValueError(f"{self.name}: {len(self.metas)} metatiles > {MAX_METATILES}")
        tiles = []
        lookup = {}
        tl, tr, bl, br, attr, prop = [], [], [], [], [], []

        def tile_id(rows):
            data = tile_from_rows(rows)
            if data not in lookup:
                lookup[data] = len(tiles)
                tiles.append(data)
            return lookup[data]

        for name, art, pal, pr in self.metas:
            quad = []
            for qy in (0, 8):
                for qx in (0, 8):
                    quad.append(tile_id([art[qy + y][qx:qx + 8] for y in range(8)]))
            tl.append(quad[0])
            tr.append(quad[1])
            bl.append(quad[2])
            br.append(quad[3])
            attr.append(pal)
            prop.append(pr)

        if len(tiles) > MAX_TILES:
            raise ValueError(
                f"{self.name}: {len(tiles)} unique 8x8 tiles > {MAX_TILES}")

        pad = lambda a, n=MAX_METATILES, v=0: a + [v] * (n - len(a))
        return {
            "name": self.name,
            "tiles": tiles,
            "tl": pad([0x80 + i for i in tl]),
            "tr": pad([0x80 + i for i in tr]),
            "bl": pad([0x80 + i for i in bl]),
            "br": pad([0x80 + i for i in br]),
            "attr": pad(attr),
            "prop": pad(prop, v=PROP_SOLID),
            "palettes": self.palettes,
            "n": len(self.metas),
            "ntiles": len(tiles),
        }
