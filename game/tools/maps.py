"""Map authoring and the on-ROM map format.

A map is authored as a grid of characters plus a legend mapping each character
to a metatile name in the map's tileset. Objects (NPCs, chests, warps, signs)
are attached by grid coordinate.

ROM format (all pointers absolute, inside the map's own $8000 data bank):

    map:
        .byte width, height          ; in metatiles (>= 16 each)
        .byte tileset_id
        .byte music_id
        .byte enc_zone               ; $FF = no random encounters
        .byte enc_rate               ; encounter chance per step, out of 256
        .byte flags                  ; MF_*
        .byte n_objects
        .addr rowtab
        .addr objects
        .addr zonetab                ; 0 = none; else an 8x8 grid of zone ids
    rowtab:  .addr row0 .. row(h-1)
    rowN:    RLE stream:
                 b < $80          -> one cell of metatile b
                 b >= $80         -> ((b & $7F) + 2) cells of the next byte
    objects: 8 bytes each: kind, gx, gy, a0, a1, a2, a3, a4
"""

MF_DUNGEON = 0x01      # "inside": the overworld return position is remembered
MF_SAVE    = 0x02      # a save terminal exists here (unused by the engine)
MF_NOFLEE  = 0x04

# object kinds
OB_END   = 0
OB_NPC   = 1           # a0=metatile id, a1=facing, a2/a3=message id, a4=flags
OB_CHEST = 2           # a0=chest flag, a1=item id, a2=count, a3/a4=credits
OB_WARP  = 3           # a0=dest map, a1=dest gx, a2=dest gy, a3=dir, a4=flags
OB_SIGN  = 4           # a2/a3 = message id
OB_SHOP  = 5           # a0 = shop id
OB_INN   = 6           # a0/a1 = price
OB_SAVE  = 7
OB_TRIG  = 8           # a0 = story flag, a1 = script id


class GameMap:
    def __init__(self, name, tileset, legend, rows, music=0, enc_zone=0xFF,
                 enc_rate=12, flags=0, scale=1, zones=None):
        self.name = name
        self.tileset = tileset
        self.objects = []
        grid = []
        for r in rows:
            line = []
            for ch in r:
                if ch not in legend:
                    raise ValueError(f"{name}: character {ch!r} not in legend")
                line.append(tileset.id(legend[ch]))
            if scale > 1:
                line = [c for c in line for _ in range(scale)]
            for _ in range(scale):
                grid.append(list(line))
        self.grid = grid
        self.h = len(grid)
        self.w = len(grid[0])
        if any(len(r) != self.w for r in grid):
            raise ValueError(f"{name}: ragged map rows")
        if self.w < 16 or self.h < 16:
            raise ValueError(f"{name}: maps must be at least 16x16 metatiles")
        if self.w > 128 or self.h > 128:
            raise ValueError(f"{name}: maps must be at most 128x128 metatiles")
        self.music = music
        self.enc_zone = enc_zone
        self.enc_rate = enc_rate
        self.flags = flags
        # zones: optional 8x8 grid of encounter-table ids laid over the map
        # (cell = 1/8 of the map in each axis). Gives one map several regional
        # monster tables, the way an overworld needs.
        self.zones = zones
        if zones is not None:
            if len(zones) != 8 or any(len(r) != 8 for r in zones):
                raise ValueError(f"{name}: zones must be an 8x8 grid")

    def put(self, gx, gy, meta):
        self.grid[gy][gx] = self.tileset.id(meta)

    def obj(self, kind, gx, gy, a0=0, a1=0, a2=0, a3=0, a4=0):
        if not (0 <= gx < self.w and 0 <= gy < self.h):
            raise ValueError(f"{self.name}: object out of bounds at {gx},{gy}")
        self.objects.append((kind, gx, gy, a0, a1, a2, a3, a4))
        return len(self.objects) - 1

    # --- compilation ---------------------------------------------------------
    @staticmethod
    def rle_row(cells):
        out = bytearray()
        i = 0
        n = len(cells)
        while i < n:
            v = cells[i]
            if v > 0x7F:
                raise ValueError(f"metatile id {v} exceeds 127")
            run = 1
            while i + run < n and cells[i + run] == v and run < 0x81:
                run += 1
            if run >= 2:
                out.append(0x80 | (run - 2))
                out.append(v)
                i += run
            else:
                out.append(v)
                i += 1
        return bytes(out)

    def compile(self):
        rows = [self.rle_row(r) for r in self.grid]
        objs = bytearray()
        for o in self.objects:
            objs += bytes(o)
        return rows, bytes(objs)

    def size_estimate(self):
        rows, objs = self.compile()
        return 12 + 2 * self.h + sum(len(r) for r in rows) + len(objs)


def emit_maps(f, maps, label_prefix="map"):
    """Emit a list of GameMap into the currently-selected segment."""
    total = 0
    for i, m in enumerate(maps):
        rows, objs = m.compile()
        lab = f"{label_prefix}_{m.name}"
        f.write(f"\n; ---- {m.name}: {m.w}x{m.h}, {len(m.objects)} objects ----\n")
        f.write(f"{lab}:\n")
        f.write(f"    .byte {m.w}, {m.h}, TS_{m.tileset.name.upper()}, {m.music}\n")
        f.write(f"    .byte {m.enc_zone}, {m.enc_rate}, {m.flags}, {len(m.objects)}\n")
        f.write(f"    .addr {lab}_rows\n")
        f.write(f"    .addr {lab}_objs\n")
        f.write(f"    .addr {lab}_zones\n" if m.zones else "    .addr 0\n")
        if m.zones:
            f.write(f"{lab}_zones:\n")
            for zr in m.zones:
                f.write("    .byte " + ",".join(str(z) for z in zr) + "\n")
        f.write(f"{lab}_rows:\n")
        for y in range(m.h):
            f.write(f"    .addr {lab}_r{y}\n")
        for y, r in enumerate(rows):
            f.write(f"{lab}_r{y}: .byte " + ",".join(f"${b:02X}" for b in r) + "\n")
        f.write(f"{lab}_objs:\n")
        if objs:
            for i2 in range(0, len(objs), 8):
                f.write("    .byte " + ",".join(str(b) for b in objs[i2:i2 + 8]) + "\n")
        else:
            f.write("    .byte 0\n")
        total += m.size_estimate()
    return total
