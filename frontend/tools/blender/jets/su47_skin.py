"""
Skins and the atlas of the Su-47 (tools/blender/jets/su47.py).

A `Skin` is a grid of surface points (game frame) that knows where each of its points lies on its own sheet of the
texture: (u, v) in metres on a rectangle of `size` metres. All skins are gathered first, `Atlas.pack()` then gives
every sheet its place in one square texture at one scale (pixels per metre, times the sheet's own `density`), and
only then are the faces made (`Skin.emit`: UVs known) and the sheets painted (su47_paint.py: a `Canvas` per sheet,
in metres). Small parts made from the kit's primitives take a plain swatch of the same texture (`swatch_part`).

The mirrored half of a symmetric skin shares its texels (`mirror=True`): what is painted there must read the same
from both sides (numerals go on patches with their own UVs).
"""
import math

import numpy as np

import jet_kit as K

AIRFRAME = 'airframe'


class Sheet:
    def __init__(self, name, size, density=1.0):
        self.name = name
        self.size = (float(size[0]), float(size[1]))        # metres (u, v)
        self.density = density
        self.px = None                                        # (x0, y0, w, h) in pixels, set by Atlas.pack
        self.scale = None                                     # pixels per metre

    def uv(self, u, v, n):
        """atlas UV (0..1, v up) of a point (u, v) in metres"""
        x0, y0, w, h = self.px
        return ((x0 + u * self.scale) / n, (y0 + v * self.scale) / n)


class Atlas:
    """one square texture: sheets packed on shelves (tallest first) at the largest scale that fits; swatch cells
    in a strip along the top"""

    def __init__(self, size=2048, pad=3, cell=12, swatch_rows=2):
        self.n = size
        self.pad = pad
        self.cell = cell
        self.swatch_h = cell * swatch_rows
        self.sheets = {}
        self.swatches = {}
        self.scale = None

    def sheet(self, name, size, density=1.0):
        if name in self.sheets:
            return self.sheets[name]
        s = self.sheets[name] = Sheet(name, size, density)
        return s

    def swatch(self, name, colour, rough=0.6, metal=0.0, material=AIRFRAME):
        """a plain cell: colour '#rrggbb'; `material`: the material its faces get (a lamp's)"""
        if name not in self.swatches:
            i = len(self.swatches)
            per = self.n // self.cell
            assert i < per * (self.swatch_h // self.cell), 'no room for another swatch'
            x0 = (i % per) * self.cell
            y0 = self.n - (i // per + 1) * self.cell
            self.swatches[name] = {'colour': colour, 'rough': rough, 'metal': metal, 'px': (x0, y0), 'material': material}
        return name

    def swatch_uv(self, name):
        x0, y0 = self.swatches[name]['px']
        return ((x0 + self.cell / 2) / self.n, (y0 + self.cell / 2) / self.n)

    def _try(self, scale):
        avail_h = self.n - self.swatch_h - self.pad
        order = sorted(self.sheets.values(), key=lambda s: (-s.size[1] * s.density, s.name))
        x = y = shelf = 0
        out = {}
        for s in order:
            k = scale * s.density
            w, h = int(math.ceil(s.size[0] * k)) + 2 * self.pad, int(math.ceil(s.size[1] * k)) + 2 * self.pad
            if w > self.n:
                return None
            if x + w > self.n:
                x, y, shelf = 0, y + shelf, 0
            if y + h > avail_h:
                return None
            out[s.name] = (x + self.pad, y + self.pad, w - 2 * self.pad, h - 2 * self.pad, k)
            x += w
            shelf = max(shelf, h)
        return out

    def pack(self):
        lo, hi = 5.0, 600.0
        best = None
        for _ in range(40):
            mid = (lo + hi) / 2
            r = self._try(mid)
            if r is None:
                hi = mid
            else:
                lo, best = mid, r
        assert best is not None, 'the sheets do not fit the atlas'
        self.scale = lo
        for name, (x0, y0, w, h, k) in best.items():
            s = self.sheets[name]
            s.px, s.scale = (x0, y0, w, h), k
        used = sum(s.px[2] * s.px[3] for s in self.sheets.values()) / (self.n * self.n)
        print(f'ATLAS {self.n} px: {len(self.sheets)} sheets at {lo:.1f} px/m, {used * 100:.0f} % used, {len(self.swatches)} swatches')
        return lo


class Skin:
    """
    rows[j][i]: points (x, y, z) in the game frame; uv[j][i]: (u, v) in metres on `sheet`. A closed ring repeats
    its first point at the end (the seam). `mats(i, j)` may name another material for a quad (the canopy's glass),
    `skip(i, j)` leaves a quad out (the cockpit's opening), `double(i, j)` gives a quad a second face looking the
    other way, 5 mm behind it (a canopy frame seen from inside: the game draws one side of a face).
    `out`: which way the faces look: None = away from each ring's own middle (a loft), 'up' / 'down' / a vector =
    towards it (a sheet), 'in' = towards the ring's middle (a duct).
    """

    def __init__(self, name, sheet, rows, uv, mirror=False, out=None, mat=AIRFRAME, mats=None, skip=None, smooth=True,
                 double=None):
        self.name, self.sheet = name, sheet
        self.double = double
        self.rows, self.uv = rows, uv
        self.mirror, self.out = mirror, out
        self.mat, self.mats, self.skip, self.smooth = mat, mats, skip, smooth

    def _flip(self):
        """do the quads as listed look the wrong way?"""
        R = np.array(self.rows, float)
        nj, ni = R.shape[:2]
        a = R[:-1, :-1]
        e_i = R[:-1, 1:] - a
        e_j = R[1:, :-1] - a
        n = np.cross(e_i, e_j)
        c = (a + R[:-1, 1:] + R[1:, :-1] + R[1:, 1:]) / 4
        if self.out is None or self.out == 'in':
            mid = R.mean(axis=1)                              # each ring's middle
            ref = (mid[:-1] + mid[1:])[:, None, :] / 2
            s = float((n * (c - ref)).sum())
            return s < 0 if self.out is None else s > 0
        v = {'up': (0, 1, 0), 'down': (0, -1, 0)}.get(self.out, self.out) if isinstance(self.out, str) else self.out
        return float((n @ np.array(v, float)).sum()) < 0

    def emit(self, part, atlas, sign=1):
        """faces into a kit Part (sign = -1: the mirrored half, x → -x)"""
        bm, layer = part.bm, part.uv
        nj, ni = len(self.rows), len(self.rows[0])
        vs = [[bm.verts.new(K.B(p[0] * sign, p[1], p[2])) for p in row] for row in self.rows]
        n = atlas.n
        uvs = [[self.sheet.uv(u, v, n) for (u, v) in row] for row in self.uv]
        flip = self._flip() != (sign < 0)
        for j in range(nj - 1):
            for i in range(ni - 1):
                if self.skip and self.skip(i, j):
                    continue
                idx = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
                if flip:
                    idx.reverse()
                # collapsed corners (a tip, a pole): a triangle, or nothing
                keep, seen = [], []
                for k, (a, b) in enumerate(idx):
                    co = vs[a][b].co
                    if any((co - s).length < 1e-6 for s in seen):
                        continue
                    seen.append(co)
                    keep.append(k)
                if len(keep) < 3:
                    continue
                try:
                    f = bm.faces.new([vs[idx[k][0]][idx[k][1]] for k in keep])
                except ValueError:
                    continue
                f.material_index = part.slot(self.mats(i, j) if self.mats else self.mat)
                f.smooth = self.smooth
                for loop, k in zip(f.loops, keep):
                    a, b = idx[k]
                    loop[layer].uv = uvs[a][b]
                if self.double and self.double(i, j):
                    f.normal_update()
                    back = [bm.verts.new(v.co - f.normal * 0.005) for v in f.verts]
                    g = bm.faces.new(back[::-1])
                    g.material_index, g.smooth = f.material_index, False
                    for loop, k in zip(g.loops, keep[::-1]):
                        a, b = idx[k]
                        loop[layer].uv = uvs[a][b]
        if self.mirror and sign > 0:
            self.emit(part, atlas, -1)


def swatch_part(part, atlas):
    """every face of a kit Part whose material is a swatch's name: that swatch's material (the airframe's unless it
    says otherwise), its UVs on the swatch"""
    bm, layer = part.bm, part.uv
    names = list(part.slots)
    for f in bm.faces:
        name = names[f.material_index] if f.material_index < len(names) else None
        sw = atlas.swatches.get(name)
        if sw is not None:
            uv = atlas.swatch_uv(name)
            for loop in f.loops:
                loop[layer].uv = uv
            f.material_index = part.slot(sw['material'])
    # drop the slots nobody uses any more (the kit appends a material per slot)
    used = sorted({f.material_index for f in bm.faces})
    remap = {old: new for new, old in enumerate(used)}
    for f in bm.faces:
        f.material_index = remap[f.material_index]
    part.slots = [part.slots[i] for i in used]


def plane_uv(part, faces, sheet, atlas, fn):
    """UVs for some faces of a Part: fn(game point) → (u, v) in metres on the sheet"""
    layer = part.uv
    idx = part.slot(AIRFRAME)
    for f in faces:
        f.material_index = idx
        for loop in f.loops:
            u, v = fn(K.G(loop.vert.co))
            loop[layer].uv = sheet.uv(u, v, atlas.n)


def arc_fractions(pts):
    """cumulative length along a polyline, 0..1"""
    P = np.array(pts, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    return s / s[-1] if s[-1] > 1e-9 else np.linspace(0, 1, len(P))


def loft_uv(rows, us, height):
    """UVs of a loft in metres: u per ring (given), v = the share of each ring's length × height"""
    return [[(u, f * height) for f in arc_fractions(row)] for row, u in zip(rows, us)]


def ring_length(pts):
    P = np.array(pts, float)
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
