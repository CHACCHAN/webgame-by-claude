"""
Building blocks for the game's vegetation (trees, bushes): Blender 5 (bpy), run headless by the per-species scripts.

A species script describes a tree in numbers (a branching recipe, its twigs, its bark) and `run()` makes of it:
  1. the twig sprites: the script's modelled twigs (needles / leaves as geometry) rendered from above with Cycles
     into cells of the leaf texture: colour + cutout, normal, and a thickness mask (how much light passes);
  2. the bough sprites: one of the tree's own boughs with its twig cards, rendered from above and from the side
     into two more cells (what the reduced levels of detail are made of);
  3. the bark: a tiling band at the bottom of the same texture (numpy, periodic), so a whole tree is one material;
  4. per shape variant (a seed) the meshes lod0 (boughs as tubes, twig cards), lod1 (bough cards + thick boughs),
     lod2 (few big cards; also what throws the shadow), and an impostor: eight views around the tree in an atlas
     (colour + cutout, normals in the view's frame);
  5. the GLB (geometry only: `v<k>_lod<n>`, `v<k>_imp`) and the textures as PNG files next to it, which
     tools/blender-models.cjs puts into the GLB's materials (`foliage`, `impostor`) and compresses.

Frame: the game's (metres, +Y up); written to Blender as (x, -z, y) so the glTF exporter with export_yup gives the
game's axes back.
Vertex data of the meshes: normal = the crown's volume normal for foliage (so a crown shades as a volume, not as
cards), colour = (ambient occlusion, sway weight of the branch, flutter weight of the leaf, phase).
"""
import math
import os
import sys

import bpy
import numpy as np

TEX = 1024            # the leaf texture (sprites above, the bark band below)
BARK_H = 256          # rows of the bark band, PAD of them at each edge repeat the band's far side (mip bleeding)
PAD = 8
SPR_H = TEX - BARK_H


class Cell:
    """a rectangle of the leaf texture in pixels (y down)"""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def uv(self, s, t):
        """s across (0 left … 1 right), t from the bottom of the cell (0, the stem's base) to its top"""
        return ((self.x + s * self.w) / TEX, (self.y + (1 - t) * self.h) / TEX)


CELLS = {
    'twig0': Cell(0, 0, 256, 384),
    'twig1': Cell(0, 384, 256, 384),
    'top': Cell(256, 0, 448, 768),
    'side': Cell(704, 0, 320, 768),
}
BARK_V = ((SPR_H + PAD) / TEX, (TEX - PAD) / TEX)


class Rng:
    def __init__(self, seed):
        self.g = np.random.default_rng(seed)

    def u(self, a=0.0, b=1.0):
        return float(self.g.uniform(a, b))

    def n(self, s=1.0):
        return float(self.g.normal(0, s))

    def vec(self):
        v = self.g.normal(0, 1, 3)
        return v / np.linalg.norm(v)

    def child(self):
        return Rng(int(self.g.integers(1 << 31)))


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


UP = np.array([0.0, 1.0, 0.0])


def perp(t):
    """a unit vector across `t`, as level as it gets"""
    s = np.cross(UP, t)
    if np.linalg.norm(s) < 1e-4:
        s = np.cross(np.array([1.0, 0, 0]), t)
    return unit(s)


# ------------------------------------------------------------------------------------------------ geometry

class Geo:
    """triangles with per-vertex position, normal, uv (image coordinates, v down), colour and a leaf flag"""

    def __init__(self):
        self.P, self.N, self.UV, self.C, self.T, self.L = [], [], [], [], [], []
        self.n = 0

    def add(self, P, N, UV, C, T, leaf):
        P = np.asarray(P, float).reshape(-1, 3)
        self.P.append(P)
        self.N.append(np.asarray(N, float).reshape(-1, 3))
        self.UV.append(np.asarray(UV, float).reshape(-1, 2))
        self.C.append(np.asarray(C, float).reshape(-1, 4))
        self.T.append(np.asarray(T, int).reshape(-1, 3) + self.n)
        self.L.append(np.full(len(P), 1.0 if leaf else 0.0))
        self.n += len(P)

    def arrays(self):
        cat = lambda a, w: np.concatenate(a) if a else np.zeros((0, w))
        return cat(self.P, 3), cat(self.N, 3), cat(self.UV, 2), cat(self.C, 4), cat(self.T, 3).astype(int), (np.concatenate(self.L) if self.L else np.zeros(0))

    def tris(self):
        return sum(len(t) for t in self.T)


def tube(geo, pts, rad, sides, rep, ao, sway, phase):
    """
    A branch: rings of `sides` around the path. Bark: u runs along the branch and turns back every `rep` metres
    (mirrored repeat: the texture needs no wrap and the mesh no seam rings), v once around inside the bark band.
    """
    pts = np.asarray(pts, float)
    n = len(pts)
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-12
    side = perp(tang[0])
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    P, N, UV, C = [], [], [], []
    for i in range(n):
        # carry the frame along (no twist)
        side = unit(side - tang[i] * np.dot(side, tang[i]))
        bi = np.cross(tang[i], side)
        x = arc[i] / rep
        u = 1 - abs((x % 2) - 1)
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            d = math.cos(a) * side + math.sin(a) * bi
            P.append(pts[i] + d * rad[i])
            N.append(d)
            UV.append((u, BARK_V[0] + (BARK_V[1] - BARK_V[0]) * k / sides))
            C.append((ao[i], sway[i], 0.0, phase))
    T = []
    for i in range(n - 1):
        for k in range(sides):
            a, b = i * (sides + 1) + k, (i + 1) * (sides + 1) + k
            T += [(a, a + 1, b + 1), (a, b + 1, b)]
    geo.add(P, N, UV, C, T, False)


def card(geo, base, axis, side, nrm, length, width, cell, ao, sway, phase, bend=0.0, segs=2, flutter=(0.15, 1.0), mirror=False):
    """a twig card: a strip from `base` along `axis`, `width` across, sagging by `bend` × length at its tip"""
    P, N, UV, C, T = [], [], [], [], []
    for j in range(segs + 1):
        t = j / segs
        c = base + axis * (length * t) - nrm * (bend * length * t * t)
        for e in (0, 1):
            P.append(c + side * (width * (e - 0.5)))
            N.append(nrm)
            UV.append(cell.uv((1 - e) if mirror else e, t))
            C.append((ao, sway[0] + (sway[1] - sway[0]) * t, flutter[0] + (flutter[1] - flutter[0]) * t, phase))
    for j in range(segs):
        a = j * 2
        T += [(a, a + 1, a + 3), (a, a + 3, a + 2)]
    geo.add(P, N, UV, C, T, True)


def quad(geo, corners, cell, ao, sway, phase, flutter=0.5):
    """a flat card on four corners (bottom-left, bottom-right, top-right, top-left of the cell)"""
    P = np.asarray(corners, float)
    n = unit(np.cross(P[1] - P[0], P[3] - P[0]))
    UV = [cell.uv(0, 0), cell.uv(1, 0), cell.uv(1, 1), cell.uv(0, 1)]
    C = [(ao, sway[0], flutter * 0.3, phase), (ao, sway[0], flutter * 0.3, phase), (ao, sway[1], flutter, phase), (ao, sway[1], flutter, phase)]
    geo.add(P, [n] * 4, UV, C, [(0, 1, 2), (0, 2, 3)], True)


# ------------------------------------------------------------------------------------------------ the skeleton

class Branch:
    def __init__(self, level, pts, rad, plane, parent=None, sway0=0.0, flex=0.0):
        self.level, self.pts, self.rad, self.plane, self.parent = level, np.asarray(pts, float), np.asarray(rad, float), plane, parent
        self.children, self.sites = [], []
        self.arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(self.pts, axis=0), axis=1))])
        self.length = float(self.arc[-1])
        self.sway0, self.flex = sway0, flex
        self.phase = 0.0

    def at(self, t):
        """position, tangent, radius and sway weight at the fraction t of the length"""
        s = t * self.length
        i = int(np.clip(np.searchsorted(self.arc, s) - 1, 0, len(self.pts) - 2))
        f = (s - self.arc[i]) / max(self.arc[i + 1] - self.arc[i], 1e-9)
        p = self.pts[i] + (self.pts[i + 1] - self.pts[i]) * f
        return p, unit(self.pts[i + 1] - self.pts[i]), self.rad[i] + (self.rad[i + 1] - self.rad[i]) * f, min(1.0, self.sway0 + self.flex * t)

    def sway(self):
        return np.minimum(1.0, self.sway0 + self.flex * self.arc / max(self.length, 1e-9))

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def ancestor(self, level):
        b = self
        while b is not None and b.level > level:
            b = b.parent
        return b


class Site:
    """a twig card: where, which way, how big"""

    def __init__(self, base, axis, side, nrm, length, width, cell, sway, phase, branch, bend):
        self.base, self.axis, self.side, self.nrm, self.length, self.width = base, axis, side, nrm, length, width
        self.cell, self.sway, self.phase, self.branch, self.bend = cell, sway, phase, branch, bend

    def corners(self):
        tip = self.base + self.axis * self.length
        h = self.side * (self.width / 2)
        return np.array([self.base - h, self.base + h, tip + h, tip - h])


def path(rng, start, d, length, segs, droop=0.0, upturn=0.0, wiggle=0.0):
    """a branch's centreline: it starts along d, sags by `droop`, turns up at the tip by `upturn`, wanders by `wiggle`"""
    pts = [np.asarray(start, float)]
    d = unit(d)
    for k in range(segs):
        t = (k + 0.5) / segs
        d = d + UP * (-droop / segs) + rng.vec() * wiggle / segs
        if t > 0.6:
            d = d + UP * (upturn / segs / 0.4)
        d = unit(d)
        pts.append(pts[-1] + d * (length / segs))
    return np.array(pts)


def grow(spec, rng):
    """the trunk and its branches from the recipe (see a species script for the fields)"""
    tk = spec['trunk']
    H = tk['height'] * rng.u(1 - tk.get('vary', 0.08), 1 + tk.get('vary', 0.08))
    segs = tk['segs']
    lean = rng.vec() * tk.get('lean', 0.03)
    lean[1] = 0
    pts = [np.array([0.0, -0.6, 0.0])]
    d = unit(UP + lean)
    for k in range(segs):
        d = unit(d + rng.vec() * tk.get('wiggle', 0.02) + UP * tk.get('straighten', 0.02))
        pts.append(pts[-1] + d * ((H + 0.6) / segs))
    pts = np.array(pts)
    # the foot stands on the origin
    pts[:, 0] -= np.interp(0, pts[:, 1], pts[:, 0])
    pts[:, 2] -= np.interp(0, pts[:, 1], pts[:, 2])
    y = np.clip((pts[:, 1]) / H, 0, 1)
    rad = tk['radius'] * (1 - y) ** tk.get('taper', 0.9) + tk.get('tip', 0.012)
    rad *= 1 + tk.get('flare', 0.45) * np.exp(-np.maximum(pts[:, 1], 0) / tk.get('flare_h', 0.5))
    trunk = Branch(0, pts, rad, np.array([1.0, 0, 0]))
    trunk.height = H
    _spawn(spec, rng, trunk, H)
    return trunk


def _spawn(spec, rng, parent, H):
    lv = parent.level + 1
    if lv > len(spec['levels']):
        return
    L = spec['levels'][lv - 1]
    n = L['n'](parent, rng) if callable(L['n']) else L['n']
    t0, t1 = L.get('span', (0.2, 0.97))
    turn = rng.u(0, 2 * math.pi)
    for i in range(n):
        f = (i + rng.u(0.2, 0.8)) / n            # 0 … 1 along the span
        f = f ** L.get('bias', 1.0)
        t = t0 + (t1 - t0) * f
        p, tang, r, sw = parent.at(t)
        ang = math.radians(L['angle'](f, rng) if callable(L['angle']) else L['angle'])
        if L.get('planar'):
            sidev = np.cross(parent.plane, tang) * (1 if i % 2 else -1)
            d = math.cos(ang) * tang + math.sin(ang) * unit(sidev) + parent.plane * rng.n(L.get('lift', 0.06))
            plane = unit(parent.plane + rng.vec() * L.get('twist', 0.1))
        else:
            turn += math.radians(L.get('turn', 137.5)) + rng.n(0.25)
            a = perp(tang)
            b = np.cross(tang, a)
            radial = math.cos(turn) * a + math.sin(turn) * b
            d = math.cos(ang) * tang + math.sin(ang) * radial
            plane = None
        length = L['length'](f, parent, rng)
        env = spec.get('envelope')
        if env:
            length = env(p, unit(d), length, H)
        if length < L.get('min', 0.15):
            continue
        droop = L.get('droop', 0.0) * (L['droop_by'](f) if 'droop_by' in L else 1)
        pts = path(rng, p, d, length, L['segs'], droop, L.get('upturn', 0.0), L.get('wiggle', 0.0))
        if plane is None:
            # the fan plane of a bough: its own direction and the level line across it
            ch = unit(pts[-1] - pts[0])
            plane = unit(np.cross(ch, perp(ch)))
            if plane[1] < 0:
                plane = -plane
        r0 = min(r * 0.9, max(L.get('rmin', 0.004), r * L.get('radius', 0.4)))
        if 'radius_per_m' in L:
            r0 = min(r * 0.9, max(L.get('rmin', 0.004), L['radius_per_m'] * length))
        rad = r0 + (L.get('tip', 0.004) - r0) * (np.linspace(0, 1, len(pts)) ** 0.8)
        br = Branch(lv, pts, rad, plane, parent, sw, L.get('flex', 0.3))
        br.phase = rng.u()
        br.f = f
        parent.children.append(br)
        _spawn(spec, rng, br, H)


def foliage(spec, rng, trunk):
    """the twig cards (sites) on the branches of the recipe's leaf level"""
    lf = spec['leaf']
    for br in trunk.walk():
        tip_only = br.level in lf.get('tips', [])
        if br.level != lf['level'] and not tip_only:
            continue
        start = lf.get('start', 0.1)
        # (`tips`: branches of those levels carry one card at their end)
        n = 0 if tip_only else max(1, int(round(lf['per_m'] * br.length * (1 - start))))
        for i in range(n + 1):
            tip = i == n
            t = 1.0 if tip else start + (1 - start) * (i + rng.u(0.1, 0.9)) / n
            p, tang, r, sw = br.at(min(t, 0.999))
            length = lf['size'] * rng.u(0.75, 1.2) * (lf.get('tip_scale', 1.0) if tip else 1.0)
            width = length * lf.get('aspect', 0.66)
            if lf.get('mode', 'fan') == 'fan':
                plane = br.plane
                sidev = unit(np.cross(plane, tang)) * (1 if i % 2 else -1)
                ang = 0.0 if tip else math.radians(lf.get('angle', 50) + rng.n(10))
                axis = unit(math.cos(ang) * tang + math.sin(ang) * sidev + UP * lf.get('rise', 0.0))
                roll = rng.n(math.radians(lf.get('roll', 25)))
                nrm = unit(plane - axis * np.dot(plane, axis))
                s = np.cross(nrm, axis)
                nrm = unit(math.cos(roll) * nrm + math.sin(roll) * s)
                s = unit(np.cross(nrm, axis))
            else:
                # around the branch; the card's face turned up and outwards
                a = perp(tang)
                b = np.cross(tang, a)
                phi = rng.u(0, 2 * math.pi)
                radial = math.cos(phi) * a + math.sin(phi) * b
                ang = 0.0 if tip else math.radians(lf.get('angle', 55) + rng.n(12))
                axis = unit(math.cos(ang) * tang + math.sin(ang) * radial + UP * lf.get('rise', 0.0))
                want = unit(UP * lf.get('face_up', 1.0) + unit(p * np.array([1, 0, 1]) + 1e-6) * lf.get('face_out', 0.5) + rng.vec() * lf.get('face_rand', 0.5))
                nrm = unit(want - axis * np.dot(want, axis))
                s = unit(np.cross(nrm, axis))
            cell = lf['cells'][int(rng.u(0, len(lf['cells']) - 1e-6))]
            sway = (sw, min(1.0, sw + lf.get('flex', 0.25)))
            br.sites.append(Site(p - axis * (length * 0.06), axis, s, nrm, length, width, cell, sway, rng.u(), br, lf.get('bend', 0.12) * rng.u(0.4, 1.4)))


class Tree:
    """a grown tree: its skeleton, the height, the crown's radius by height (for normals and occlusion)"""

    def __init__(self, spec, seed):
        self.spec = spec
        rng = Rng(seed)
        self.trunk = grow(spec, rng.child())
        foliage(spec, rng.child(), self.trunk)
        self.H = self.trunk.height
        sites = [s for b in self.trunk.walk() for s in b.sites]
        self.sites = sites
        pts = np.concatenate([s.corners() for s in sites])
        self.y0, self.y1 = float(pts[:, 1].min()), float(pts[:, 1].max())
        # the crown's radius in bands of height, from the cards themselves
        bands = 12
        self.bands = np.zeros(bands)
        yb = np.clip(((pts[:, 1] - self.y0) / max(self.y1 - self.y0, 1e-6) * bands).astype(int), 0, bands - 1)
        rr = np.hypot(pts[:, 0] - self.axis_x(pts[:, 1]), pts[:, 2] - self.axis_z(pts[:, 1]))
        for b in range(bands):
            m = yb == b
            self.bands[b] = np.percentile(rr[m], 92) if m.any() else 0
        for b in range(bands):   # no empty bands
            if self.bands[b] == 0:
                self.bands[b] = max(self.bands[max(b - 1, 0)], self.bands[min(b + 1, bands - 1)], 0.3)
        self.radius = float(np.hypot(pts[:, 0], pts[:, 2]).max())
        self.top = float(max(pts[:, 1].max(), self.trunk.pts[-1, 1]))

    def axis_x(self, y):
        return np.interp(y, self.trunk.pts[:, 1], self.trunk.pts[:, 0])

    def axis_z(self, y):
        return np.interp(y, self.trunk.pts[:, 1], self.trunk.pts[:, 2])

    def crown_r(self, y):
        f = np.clip((y - self.y0) / max(self.y1 - self.y0, 1e-6), 0, 1) * (len(self.bands) - 1)
        return np.interp(f, np.arange(len(self.bands)), self.bands)

    def depth(self, P):
        """0 at the trunk … 1 at the crown's surface"""
        r = np.hypot(P[:, 0] - self.axis_x(P[:, 1]), P[:, 2] - self.axis_z(P[:, 1]))
        return np.clip(r / np.maximum(self.crown_r(P[:, 1]), 0.2), 0, 1.3)

    # ---------------------------------------------------------------- levels of detail

    def finish(self, geo):
        """volume normals and ambient occlusion from the place in the crown"""
        P, N, UV, C, T, L = geo.arrays()
        d = self.depth(P)
        hrel = np.clip((P[:, 1] - self.y0) / max(self.y1 - self.y0, 1e-6), 0, 1)
        dark = self.spec.get('inner_dark', 0.38)
        ao = dark + (1 - dark) * np.clip((d - 0.15) / 0.75, 0, 1) ** 1.2
        ao *= 0.8 + 0.2 * hrel
        leaf = L > 0.5
        # bark: darker inside the crown, lighter on the bare trunk below it
        ao_b = np.where(P[:, 1] < self.y0, 0.95, 0.55 + 0.45 * np.clip(d, 0, 1))
        C[:, 0] = np.where(leaf, C[:, 0] * ao, C[:, 0] * ao_b)
        # the volume normal: away from a point on the axis somewhat below
        cy = P[:, 1] - 0.35 * self.crown_r(P[:, 1])
        out = P - np.stack([self.axis_x(cy), cy, self.axis_z(cy)], axis=1)
        out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
        flip = np.sign(np.sum(N * out, axis=1, keepdims=True))
        flip[flip == 0] = 1
        k = self.spec.get('volume_normal', 0.72)
        Nv = N * flip * (1 - k) + out * k
        Nv /= np.linalg.norm(Nv, axis=1, keepdims=True) + 1e-9
        N = np.where(leaf[:, None], Nv, N)
        return P, N, UV, C, T

    def lod0(self):
        g = Geo()
        tk = self.spec['trunk']
        t = self.trunk
        tube(g, t.pts, t.rad, tk.get('sides', 12), tk.get('rep', 2.0), np.ones(len(t.pts)), np.zeros(len(t.pts)), 0.0)
        for b in t.walk():
            if b.level == 0:
                continue
            if b.rad[0] < self.spec.get('twig_r', 0.006):
                continue
            sides = 6 if b.rad[0] > 0.05 else 5 if b.rad[0] > 0.02 else 3
            tube(g, b.pts, b.rad, sides, 1.0 if b.rad[0] > 0.04 else 0.5, np.ones(len(b.pts)), b.sway(), b.phase)
        for s in self.sites:
            card(g, s.base, s.axis, s.side, s.nrm, s.length, s.width, CELLS[s.cell], 1.0, s.sway, s.phase, s.bend, 2, mirror=s.phase > 0.5)
        return self.finish(g)

    def clumps(self, level):
        """the branches of `level` with the cards they carry: (branch, sites)"""
        by = {}
        for s in self.sites:
            a = s.branch.ancestor(level)
            if a is not None and a.level == level:
                by.setdefault(id(a), (a, []))[1].append(s)
        return list(by.values())

    @staticmethod
    def box(branch, sites, grow_by=1.0):
        """the cards' box in the branch's frame: axes (along, across, normal) and the extents along them"""
        pts = np.concatenate([s.corners() for s in sites])
        a = unit(branch.pts[-1] - branch.pts[0])
        if len(sites) > 2:
            a = unit(a + unit(pts.mean(axis=0) - branch.pts[0]))
        n = unit(branch.plane - a * np.dot(branch.plane, a))
        s = np.cross(n, a)
        q = np.stack([pts @ a, pts @ s, pts @ n], axis=1)
        lo, hi = np.percentile(q, 2, axis=0), np.percentile(q, 98, axis=0)
        mid = (lo + hi) / 2
        half = np.maximum((hi - lo) / 2 * grow_by, [0.15, 0.15, 0.12])
        return a, s, n, mid - half, mid + half

    def clump_cards(self, g, branch, sites, grow_by=1.0, side_card=True):
        a, s, n, lo, hi = self.box(branch, sites, grow_by)
        P = lambda u, v, w: a * u + s * v + n * w
        sw = (min(1.0, branch.sway0 + 0.1), min(1.0, branch.sway0 + branch.flex))
        mid = (lo + hi) / 2
        # from above: the cell's bottom is the bough's base
        quad(g, [P(lo[0], lo[1], mid[2]), P(lo[0], hi[1], mid[2]), P(hi[0], hi[1], mid[2]), P(hi[0], lo[1], mid[2])], CELLS['top'], 1.0, sw, branch.phase)
        if side_card:
            quad(g, [P(lo[0], mid[1], lo[2]), P(lo[0], mid[1], hi[2]), P(hi[0], mid[1], hi[2]), P(hi[0], mid[1], lo[2])], CELLS['side'], 1.0, sw, branch.phase)

    def lod1(self):
        g = Geo()
        sp, t = self.spec, self.trunk
        tk = sp['trunk']
        idx = sorted(set(list(range(0, len(t.pts), 2)) + [len(t.pts) - 1]))
        tube(g, t.pts[idx], t.rad[idx], 7, tk.get('rep', 2.0), np.ones(len(idx)), np.zeros(len(idx)), 0.0)
        for b in t.walk():
            if b.level == 0 or b.rad[0] < sp.get('lod1_branch_r', 0.035):
                continue
            k = max(1, (len(b.pts) - 1) // 3)
            idx = sorted(set(list(range(0, len(b.pts), k)) + [len(b.pts) - 1]))
            tube(g, b.pts[idx], b.rad[idx], 4, 1.0, np.ones(len(idx)), b.sway()[idx], b.phase)
        for br, sites in self.clumps(sp['clump1']):
            self.clump_cards(g, br, sites)
        # a share of the twig cards stays: the outline keeps its ragged edge
        every = sp.get('lod1_twigs', 5)
        for i, s in enumerate(self.sites):
            if every and i % every == 0:
                card(g, s.base, s.axis, s.side, s.nrm, s.length * 1.25, s.width * 1.25, CELLS[s.cell], 1.0, s.sway, s.phase, s.bend, 1)
        return self.finish(g)

    def lod2(self):
        g = Geo()
        sp, t = self.spec, self.trunk
        idx = np.linspace(0, len(t.pts) - 1, 5).round().astype(int)
        tube(g, t.pts[idx], t.rad[idx] * 1.1, 5, sp['trunk'].get('rep', 2.0), np.ones(5), np.zeros(5), 0.0)
        cl = self.clumps(sp['clump2'])
        every = sp.get('lod2_every', 1)
        # by height, so that what is left out is spread over the crown
        cl.sort(key=lambda c: c[0].pts[0][1])
        for i, (br, sites) in enumerate(cl):
            if i % every == 0:
                self.clump_cards(g, br, sites, sp.get('lod2_grow', 1.3))
        return self.finish(g)


# ------------------------------------------------------------------------------------------------ Blender side

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def to_object(name, arrays, material=None, frame='game', normals=True):
    """a mesh object from (P, N, UV, C, T); `frame` 'game' turns the game's axes into Blender's, 'raw' keeps them"""
    P, N, UV, C, T = arrays
    if frame == 'game':
        P = np.stack([P[:, 0], -P[:, 2], P[:, 1]], axis=1)
        N = np.stack([N[:, 0], -N[:, 2], N[:, 1]], axis=1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(P.tolist(), [], T.tolist())
    me.update()
    loops = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', loops)
    uv = me.uv_layers.new(name='UVMap')
    uvl = np.stack([UV[loops, 0], 1 - UV[loops, 1]], axis=1).astype(np.float32)
    uv.data.foreach_set('uv', uvl.ravel())
    col = me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
    col.data.foreach_set('color', C.astype(np.float32).ravel())
    me.color_attributes.active_color = col
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
    if normals:
        me.normals_split_custom_set_from_vertices(N.tolist())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material:
        me.materials.append(material)
    ob['tris'] = len(T)
    return ob


def save_png(path, img):
    """float RGBA (rows top to bottom) → 8-bit PNG, values as they are"""
    h, w = img.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = 'Non-Color'
    im.alpha_mode = 'STRAIGHT'
    im.pixels.foreach_set(np.clip(img[::-1], 0, 1).astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    return path


def load_png(path):
    im = bpy.data.images.load(path)
    im.colorspace_settings.name = 'Non-Color'
    im.alpha_mode = 'STRAIGHT'
    w, h = im.size
    a = np.zeros(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()


def bleed(img, steps=24):
    """spread the colour of covered texels into the empty ones around (rgb only): no dark fringe in the mips"""
    rgb, a = img[..., :3].copy(), img[..., 3]
    known = a > 0.02
    for _ in range(steps):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(a.shape)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            k = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]
            cnt += k
        new = (~known) & (cnt > 0)
        rgb[new] = acc[new] / cnt[new][:, None]
        known = known | new
    if not known.all() and known.any():
        rgb[~known] = rgb[known].mean(axis=0)
    out = img.copy()
    out[..., :3] = rgb
    return out


def _nodes(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt, nt.nodes.new('ShaderNodeOutputMaterial')


def bake_material(kind, image=None, frame='top', ao_dist=0.0, alpha_image=None):
    """
    Emission-only materials for the bakes. kind: 'albedo' (the colour attribute, or `image` × the attribute's
    occlusion), 'normal' (the shading normal in the picture's frame: 'top' = camera looking down −Z and normals
    turned to face it, 'front' = camera looking along +Y, normals as they are), 'mask' (thickness: the attribute's
    alpha, or the image's). `alpha_image` (default `image`) cuts the cards out.
    """
    m, nt, out = _nodes(f'bake_{kind}')
    N, Lk = nt.nodes.new, nt.links.new
    em = N('ShaderNodeEmission')
    tex = None
    if image is not None:
        tex = N('ShaderNodeTexImage')
        tex.image = image
    attr = N('ShaderNodeAttribute')
    attr.attribute_name = 'Color'
    if kind == 'albedo':
        if tex is not None:
            sep = N('ShaderNodeSeparateColor')
            Lk(attr.outputs['Color'], sep.inputs['Color'])
            mul = N('ShaderNodeVectorMath')
            mul.operation = 'SCALE'
            Lk(tex.outputs['Color'], mul.inputs[0])
            Lk(sep.outputs['Red'], mul.inputs['Scale'])
            Lk(mul.outputs['Vector'], em.inputs['Color'])
        elif ao_dist > 0:
            ao = N('ShaderNodeAmbientOcclusion')
            ao.inputs['Distance'].default_value = ao_dist
            ao.samples = 8
            Lk(attr.outputs['Color'], ao.inputs['Color'])
            Lk(ao.outputs['Color'], em.inputs['Color'])
        else:
            Lk(attr.outputs['Color'], em.inputs['Color'])
    elif kind == 'normal':
        geo = N('ShaderNodeNewGeometry')
        sep = N('ShaderNodeSeparateXYZ')
        Lk(geo.outputs['Normal'], sep.inputs[0])
        comb = N('ShaderNodeCombineXYZ')
        if frame == 'top':
            # (Cycles hands out the normal already turned towards the viewer on a back face: what a sprite wants)
            Lk(sep.outputs['X'], comb.inputs['X'])
            Lk(sep.outputs['Y'], comb.inputs['Y'])
            Lk(sep.outputs['Z'], comb.inputs['Z'])
            vec = comb.outputs[0]
        else:
            neg = N('ShaderNodeMath')
            neg.operation = 'MULTIPLY'
            Lk(sep.outputs['Y'], neg.inputs[0])
            neg.inputs[1].default_value = -1.0
            Lk(sep.outputs['X'], comb.inputs['X'])
            Lk(sep.outputs['Z'], comb.inputs['Y'])
            Lk(neg.outputs[0], comb.inputs['Z'])
            # the crown's volume normal as it is, also where a card is seen from behind: undo Cycles' turn
            flip = N('ShaderNodeMath')
            flip.operation = 'MULTIPLY_ADD'
            Lk(geo.outputs['Backfacing'], flip.inputs[0])
            flip.inputs[1].default_value = -2.0
            flip.inputs[2].default_value = 1.0
            sc = N('ShaderNodeVectorMath')
            sc.operation = 'SCALE'
            Lk(comb.outputs[0], sc.inputs[0])
            Lk(flip.outputs[0], sc.inputs['Scale'])
            vec = sc.outputs['Vector']
        enc = N('ShaderNodeVectorMath')
        enc.operation = 'MULTIPLY_ADD'
        Lk(vec, enc.inputs[0])
        enc.inputs[1].default_value = (0.5, 0.5, 0.5)
        enc.inputs[2].default_value = (0.5, 0.5, 0.5)
        Lk(enc.outputs['Vector'], em.inputs['Color'])
    else:
        if tex is not None:
            Lk(tex.outputs['Alpha'], em.inputs['Color'])
        else:
            Lk(attr.outputs['Alpha'], em.inputs['Color'])
    cut = alpha_image or image
    if cut is not None:
        ctex = tex
        if cut is not image:
            ctex = N('ShaderNodeTexImage')
            ctex.image = cut
        gt = N('ShaderNodeMath')
        gt.operation = 'GREATER_THAN'
        Lk(ctex.outputs['Alpha'], gt.inputs[0])
        gt.inputs[1].default_value = 0.5
        mix = N('ShaderNodeMixShader')
        tr = N('ShaderNodeBsdfTransparent')
        Lk(gt.outputs[0], mix.inputs['Fac'])
        Lk(tr.outputs[0], mix.inputs[1])
        Lk(em.outputs[0], mix.inputs[2])
        Lk(mix.outputs[0], out.inputs['Surface'])
    else:
        Lk(em.outputs[0], out.inputs['Surface'])
    return m


def setup_cycles(w, h, samples=16, raw=False):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.cycles.use_adaptive_sampling = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 64
    sc.cycles.seed = 1
    sc.cycles.filter_width = 1.2
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 8
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.view_settings.view_transform = 'Raw' if raw else 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0
    sc.view_settings.gamma = 1
    try:
        sc.render.image_settings.media_type = 'IMAGE'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    sc.render.dither_intensity = 0
    if sc.world is None:
        sc.world = bpy.data.worlds.new('w')
    return sc


def ortho_camera(loc, look, up_axis, scale):
    """an orthographic camera at `loc` looking along `look` (Blender axes), `scale` = the frame's larger side"""
    from mathutils import Vector
    cd = bpy.data.cameras.new('cam')
    cd.type = 'ORTHO'
    cd.ortho_scale = scale
    cd.clip_start, cd.clip_end = 0.01, 500
    cam = bpy.data.objects.new('cam', cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = Vector(look).to_track_quat('-Z', up_axis).to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_passes(objs, kinds, mats, prefix, w, h, samples=16):
    """render the scene once per pass with every object wearing that pass' material → {kind: float RGBA}"""
    out = {}
    for kind in kinds:
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mats[kind])
        sc = setup_cycles(w, h, samples, raw=kind != 'albedo')
        sc.render.filepath = f'{prefix}_{kind}.png'
        bpy.ops.render.render(write_still=True)
        out[kind] = load_png(f'{prefix}_{kind}.png')
    return out


PX = 0.01   # bake scene: world units per pixel


def place_in_cell(ob, cell, width, length):
    """scale and move an object lying in the XY plane (base at the origin, growing along +Y) into its cell"""
    k = min(cell.w * PX * 0.94 / width, cell.h * PX * 0.96 / length)
    ob.scale = (k, k, k)
    cx = (cell.x + cell.w / 2) * PX
    by = (SPR_H - (cell.y + cell.h)) * PX + (cell.h * PX - length * k) / 2
    ob.location = (cx, by, 0)
    return k


def sprite_camera():
    return ortho_camera((TEX * PX / 2, SPR_H * PX / 2, 50), (0, 0, -1), 'Y', TEX * PX)


def compose(passes, alpha_gain=1.0):
    """the sprite region's colour (+ cutout) and normal (+ thickness) pictures from the passes"""
    alb, nrm, msk = passes['albedo'], passes['normal'], passes['mask']
    a = np.clip(alb[..., 3] * alpha_gain, 0, 1)
    col = bleed(np.dstack([alb[..., :3], a]))
    n = bleed(np.dstack([nrm[..., :3], a]))
    # where nothing is: a flat normal further out than the bleed reached
    empty = (a <= 0.02) & (np.abs(n[..., :3] - 0.5).sum(axis=2) < 1e-3)
    n[empty, :3] = (0.5, 0.5, 1.0)
    n[..., 3] = msk[..., 0] * (a > 0.02)
    return col, n


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def fft_noise(shape, alpha, rng, stretch=(1.0, 1.0)):
    """periodic noise with a 1/f^alpha spectrum; `stretch` > 1 draws the features out along that axis (y, x)"""
    h, w = shape
    fy = np.fft.fftfreq(h)[:, None] * h / 256 * stretch[0]
    fx = np.fft.fftfreq(w)[None, :] * w / 256 * stretch[1]
    f = np.sqrt(fy * fy + fx * fx)
    f[0, 0] = 1
    a = np.fft.ifft2(np.fft.fft2(rng.standard_normal((h, w))) / f ** alpha).real
    a -= a.mean()
    return a / (a.std() + 1e-9)


def bark_band(height_fn, colour_fn, seed, strength=2.0):
    """
    The bark band: (colour RGBA, normal RGBA with thickness 0), BARK_H rows. `height_fn(rng, h, w)` gives a periodic
    height field (0…1) of the band's inner rows; x runs along the trunk, y around it; `colour_fn(rng, height)` its
    linear colour.
    """
    rng = np.random.default_rng(seed)
    hi = BARK_H - 2 * PAD
    hgt = height_fn(rng, hi, TEX)
    col = colour_fn(rng, hgt)
    dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * strength * 4
    dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * strength * 4
    n = np.dstack([-dx, dy, np.ones_like(dx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    nrm = np.dstack([n * 0.5 + 0.5, np.zeros_like(dx)])
    col = np.dstack([lin2srgb(col), np.ones_like(dx)])
    wrap = lambda a: np.concatenate([a[-PAD:], a, a[:PAD]], axis=0)
    return wrap(col), wrap(nrm)


# ------------------------------------------------------------------------------------------------ the pipeline

def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opt = {'out': None, 'render': None}
    i = 0
    while i < len(argv):
        if argv[i] in ('--out', '--render'):
            opt[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opt


def bake_twigs(species, tmp):
    """stage 1: the modelled twigs into their cells"""
    clear_scene()
    objs = []
    for name, twig in species['twigs'].items():
        arrays, width, length = twig(Rng(species['seed'] + len(objs)))
        ob = to_object(name, arrays, frame='raw')
        ob['k'] = place_in_cell(ob, CELLS[name], width, length)
        objs.append(ob)
    sprite_camera()
    k = objs[0]['k']
    mats = {'albedo': bake_material('albedo', ao_dist=species.get('twig_ao', 0.03) * k), 'normal': bake_material('normal'), 'mask': bake_material('mask')}
    return render_passes(objs, ['albedo', 'normal', 'mask'], mats, os.path.join(tmp, 's1'), TEX, SPR_H, 24)


def clump_local(tree, branch, sites):
    """a bough with its cards in its own box frame, laid out flat for the two sprite views"""
    a, s, n, lo, hi = tree.box(branch, sites)
    g = Geo()
    for b in branch.walk():
        if b.rad[0] >= tree.spec.get('twig_r', 0.006):
            tube(g, b.pts, b.rad, 5, 1.0, np.ones(len(b.pts)), b.sway(), b.phase)
    for st in sites:
        card(g, st.base, st.axis, st.side, st.nrm, st.length, st.width, CELLS[st.cell], 1.0, st.sway, st.phase, st.bend, 2)
    # (the cards' own normals, not the crown's volume normals: the sprite's normal map is relative to its card)
    N = g.arrays()[1]
    P, _, UV, C, T = tree.finish(g)
    mid = (lo + hi) / 2
    q = np.stack([P @ a, P @ s, P @ n], axis=1)
    # picture x = across (top view) or the normal (side view), picture y = along the bough from its base: as the
    # cards of clump_cards() are laid out (bottom-left corner at lo, u growing with the second axis)
    top = (np.stack([q[:, 1] - mid[1], q[:, 0] - lo[0], q[:, 2] - mid[2]], axis=1), np.stack([N @ s, N @ a, N @ n], axis=1), UV, C, T)
    side = (np.stack([q[:, 2] - mid[2], q[:, 0] - lo[0], -(q[:, 1] - mid[1])], axis=1), np.stack([N @ n, N @ a, -(N @ s)], axis=1), UV, C, T)
    return top, side, hi - lo


def bake_boughs(species, tree, leaf_png, leaf_n_png, tmp):
    """stage 2: one bough of the tree, with the twig sprites on its cards, into the two bough cells"""
    clear_scene()
    cl = tree.clumps(species['recipe']['clump1'])
    # a bough of middling size, well furnished
    cl.sort(key=lambda c: len(c[1]))
    br, sites = cl[int(len(cl) * 0.7)]
    top, side, ext = clump_local(tree, br, sites)
    o1 = to_object('top', top, frame='raw')
    o2 = to_object('side', side, frame='raw')
    # each view fills its cell (the cards that wear it are stretched the same way)
    for ob, cell, w in ((o1, CELLS['top'], ext[1]), (o2, CELLS['side'], ext[2])):
        kx, ky = cell.w * PX / w, cell.h * PX / ext[0]
        ob.scale = (kx, ky, min(kx, ky))
        ob.location = ((cell.x + cell.w / 2) * PX, (SPR_H - (cell.y + cell.h)) * PX, 0)
    sprite_camera()
    img = bpy.data.images.load(leaf_png)
    imgn = bpy.data.images.load(leaf_n_png)
    imgn.colorspace_settings.name = 'Non-Color'
    mats = {'albedo': bake_material('albedo', image=img), 'normal': bake_material('normal', image=img), 'mask': bake_material('mask', image=imgn, alpha_image=img)}
    return render_passes([o1, o2], ['albedo', 'normal', 'mask'], mats, os.path.join(tmp, 's2'), TEX, SPR_H, 16)


def bake_impostor(lod0, tree, cw, ch, leaf_png, tmp, tag):
    """eight views around the tree, side by side: colour + cutout and the normals in each view's frame"""
    clear_scene()
    R, top = tree.radius * 1.04, tree.top * 1.02 + 0.3
    half = max(R, (top + 0.3) / 2 * cw / ch)
    span_w, span_h = 2 * half, 2 * half * ch / cw
    objs = []
    base = to_object('t', lod0)
    for k in range(8):
        ob = base
        if k:
            ob = bpy.data.objects.new(f't{k}', base.data)
            bpy.context.scene.collection.objects.link(ob)
        # the view from the azimuth k × 45° (game: from +Z round to +X): the tree turned the other way
        ob.rotation_euler = (0, 0, -k * math.pi / 4)
        ob.location = (k * span_w, 0, 0)
        objs.append(ob)
    W = 8 * span_w
    # (Blender −Y is the game's +Z: the camera stands there and looks back)
    ortho_camera((W / 2 - span_w / 2, -100, -0.3 + span_h / 2), (0, 1, 0), 'Z', W)
    img = bpy.data.images.load(leaf_png)
    mats = {'albedo': bake_material('albedo', image=img), 'normal': bake_material('normal', image=img, frame='front')}
    p = render_passes([base], ['albedo', 'normal'], mats, os.path.join(tmp, f'imp{tag}'), 8 * cw, ch, 12)
    a = p['albedo'][..., 3]
    col = bleed(np.dstack([p['albedo'][..., :3], a]), 12)
    nrm = bleed(np.dstack([p['normal'][..., :3], a]), 12)
    return col, nrm, half, span_h


def quad_object(name, half, height, uv_rect):
    """the impostor's card: as wide and tall as a view's frame, uv = the first view's cell"""
    u0, v0, u1, v1 = uv_rect
    P = np.array([[-half, -0.3, 0], [half, -0.3, 0], [half, height - 0.3, 0], [-half, height - 0.3, 0]])
    N = np.tile([0, 0, 1.0], (4, 1))
    UV = np.array([[u0, v1], [u1, v1], [u1, v0], [u0, v0]])
    C = np.ones((4, 4))
    return to_object(name, (P, N, UV, C, np.array([[0, 1, 2], [0, 2, 3]])))


def export_glb(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
              export_materials='EXPORT', export_extras=False, export_cameras=False, export_lights=False,
              export_normals=True, export_texcoords=True, export_tangents=False)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    if 'export_vertex_color' in props:
        kw['export_vertex_color'] = 'ACTIVE'
        if 'export_active_vertex_color_when_no_material' in props:
            kw['export_active_vertex_color_when_no_material'] = True
    elif 'export_colors' in props:
        kw['export_colors'] = True
    bpy.ops.export_scene.gltf(**kw)


def named_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m


def run(species):
    """the whole build of a species (see the module's header)"""
    opt = parse_args()
    sid = species['id']
    out = opt['out']
    if not out:
        raise SystemExit('usage: blender --background --factory-startup --python <species>.py -- --out <file.glb> [--render <dir>]')
    tmp = os.path.dirname(os.path.abspath(out))
    stem = os.path.join(tmp, sid)
    trees = [Tree(species['recipe'], species['seed'] * 100 + k) for k in range(species['variants'])]

    # 1. twigs → the sprite region
    col, nrm = compose(bake_twigs(species, tmp), species.get('alpha_gain', 1.5))
    bark_c, bark_n = bark_band(species['bark_height'], species['bark_colour'], species['seed'], species.get('bark_relief', 2.0))
    full = lambda spr, bark: np.concatenate([spr, bark], axis=0)
    s1, s1n = save_png(stem + '_s1.png', full(col, bark_c)), save_png(stem + '_s1n.png', full(nrm, bark_n))

    # 2. a bough with those twigs → the bough cells
    col2, nrm2 = compose(bake_boughs(species, trees[0], s1, s1n, tmp), 1.0)
    for name in ('top', 'side'):
        c = CELLS[name]
        col[c.y:c.y + c.h, c.x:c.x + c.w] = col2[c.y:c.y + c.h, c.x:c.x + c.w]
        nrm[c.y:c.y + c.h, c.x:c.x + c.w] = nrm2[c.y:c.y + c.h, c.x:c.x + c.w]
    leaf_png, leaf_n_png = save_png(stem + '_leaf.png', full(col, bark_c)), save_png(stem + '_leaf_n.png', full(nrm, bark_n))

    # 3. the meshes and the impostors
    lods = [(t.lod0(), t.lod1(), t.lod2()) for t in trees]
    cw, ch = species['impostor']
    rows_c, rows_n, frames = [], [], []
    for k, t in enumerate(trees):
        c, n, half, span_h = bake_impostor(lods[k][0], t, cw, ch, leaf_png, tmp, k)
        rows_c.append(c), rows_n.append(n), frames.append((half, span_h))
    imp_png = save_png(stem + '_imp.png', np.concatenate(rows_c, axis=0))
    save_png(stem + '_imp_n.png', np.concatenate(rows_n, axis=0))

    # 4. the GLB
    clear_scene()
    fol, imp = named_material('foliage'), named_material('impostor')
    objs = []
    nv = len(trees)
    for k in range(nv):
        for l in range(3):
            ob = to_object(f'v{k}_lod{l}', lods[k][l], fol)
            objs.append(ob)
            print(f'TRIS {sid} v{k} lod{l}: {ob["tris"]}')
        half, span_h = frames[k]
        objs.append(quad_object(f'v{k}_imp', half, span_h, (0.0, k / nv, 1 / 8, (k + 1) / nv)))
        objs[-1].data.materials.append(imp)
    export_glb(out, objs)
    print(f'NATURE {sid}: {nv} variants, {os.path.getsize(out) / 1024:.0f} KiB raw')
    if opt['render']:
        render_sheet(species, opt['render'], trees, lods, leaf_png, imp_png, frames)


def render_sheet(species, out_dir, trees, lods, leaf_png, imp_png, frames):
    """the species' sheet: every variant's levels of detail side by side in daylight, with their triangle counts"""
    from mathutils import Vector
    os.makedirs(out_dir, exist_ok=True)
    sid = species['id']
    clear_scene()
    sc = bpy.context.scene

    def shown(name, png):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        p = nt.nodes['Principled BSDF']
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(png)
        attr = nt.nodes.new('ShaderNodeAttribute')
        attr.attribute_name = 'Color'
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(attr.outputs['Color'], sep.inputs['Color'])
        mul = nt.nodes.new('ShaderNodeVectorMath')
        mul.operation = 'SCALE'
        nt.links.new(tex.outputs['Color'], mul.inputs[0])
        nt.links.new(sep.outputs['Red'], mul.inputs['Scale'])
        nt.links.new(mul.outputs['Vector'], p.inputs['Base Color'])
        gt = nt.nodes.new('ShaderNodeMath')
        gt.operation = 'GREATER_THAN'
        nt.links.new(tex.outputs['Alpha'], gt.inputs[0])
        gt.inputs[1].default_value = 0.5
        p.inputs['Roughness'].default_value = 0.7
        # leaves let light through: without it every card seen from below is black in a path tracer
        out = nt.nodes['Material Output']
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
        nt.links.new(mul.outputs['Vector'], tr.inputs['Color'])
        cut = nt.nodes.new('ShaderNodeBsdfTransparent')
        lit = nt.nodes.new('ShaderNodeMixShader')
        lit.inputs['Fac'].default_value = 0.45
        nt.links.new(p.outputs[0], lit.inputs[1])
        nt.links.new(tr.outputs[0], lit.inputs[2])
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(gt.outputs[0], mix.inputs['Fac'])
        nt.links.new(cut.outputs[0], mix.inputs[1])
        nt.links.new(lit.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        return m

    fol, imp = shown('foliage', leaf_png), shown('impostor', imp_png)
    font = bpy.data.materials.new('label')
    font.use_nodes = True
    font.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
    x = 0.0
    nv = len(trees)
    for k, t in enumerate(trees):
        step = t.radius * 2 + 1.5
        for l in range(4):
            if l < 3:
                # (Cycles shades a card black where its volume normal looks away: the sheet shows the plain geometry)
                ob = to_object(f'v{k}_lod{l}', lods[k][l], fol, normals=False)
                label = f'v{k} lod{l}: {ob["tris"]} tris'
            else:
                half, span_h = frames[k]
                ob = quad_object(f'v{k}_imp', half, span_h, (0.0, k / nv, 1 / 8, (k + 1) / nv))
                ob.data.materials.append(imp)
                label = f'v{k} impostor'
            ob.location = (x + step / 2, 0, 0)
            cu = bpy.data.curves.new('txt', 'FONT')
            cu.body = label
            cu.size = max(0.4, t.radius * 0.2)
            cu.align_x = 'CENTER'
            tx = bpy.data.objects.new('txt', cu)
            tx.location = (x + step / 2, -t.radius - 1.4, 0.02)
            tx.data.materials.append(font)
            sc.collection.objects.link(tx)
            x += step
    width = x
    top = max(t.top for t in trees)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=width * 3)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.15, 0.13, 1)
    me.materials.append(gm)
    world = bpy.data.worlds.new('sky')
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.68, 0.9, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(55), 0, math.radians(35))
    sc.collection.objects.link(sun)
    W, Hh = 2400, 900
    lens, sensor = 60, 36
    half_w = math.atan(sensor / 2 / lens)
    dist = max(width * 0.54 / math.tan(half_w), (top * 0.75) / (math.tan(half_w) * Hh / W))
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = lens
    cam.data.clip_end = 4000
    eye = Vector((width / 2, -dist, top * 0.5))
    cam.location = eye
    cam.rotation_euler = (Vector((width / 2, 0, top * 0.4)) - eye).to_track_quat('-Z', 'Y').to_euler()
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 64
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 4
    sc.cycles.transparent_max_bounces = 48
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 8
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, Hh, 100
    try:
        sc.render.image_settings.media_type = 'IMAGE'
    except Exception:
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, f'{sid}_sheet.png')
    bpy.ops.render.render(write_still=True)
    # the textures next to it
    import shutil
    for f in (leaf_png, leaf_png.replace('_leaf', '_leaf_n'), imp_png, imp_png.replace('_imp', '_imp_n')):
        shutil.copy(f, os.path.join(out_dir, os.path.basename(f)))
    print('SHEET', sc.render.filepath)
