"""
The F-15's surface: one atlas for the whole aircraft, painted texel by texel from where the texel lies on the airframe
(jet_atlas.py). Camouflage as soft-edged fields in space, panel lines and markings drawn into sheets (side, top,
underside, fin: plain numpy, no font file, no image) and read by projection, bare metal, tyres, cockpit, the steady
lamps' glow. Numbers and codes are invented; no unit's emblem is copied (the tail band and the fin badge are the game's).
"""
import math
import os

import numpy as np

import jet_atlas as JA
import jet_kit as K
import f15_shape as S


def lin(h):
    return np.array(K.srgb(h)[:3], np.float32)


# ---------------------------------------------------------------- lettering: block capitals on a 4 x 6 grid

_O = [(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]
_P = [(0, 0), (0, 6), (3, 6), (4, 5), (4, 3.8), (3, 2.8), (0, 2.8)]
GLYPHS = {
    '0': [_O], 'O': [_O],
    '1': [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    '2': [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    '3': [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)], [(2, 3), (3, 3)]],
    '4': [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    '5': [[(4, 6), (0, 6), (0, 3.4), (3, 3.4), (4, 2.4), (4, 1), (3, 0), (1, 0), (0, 1)]],
    '6': [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2.4), (3, 3.4), (0, 3.4)]],
    '7': [[(0, 6), (4, 6), (1.5, 0)]],
    '8': [[(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3)]],
    '9': [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3.6), (1, 2.6), (4, 2.6)]],
    'A': [[(0, 0), (0, 4.5), (1.5, 6), (2.5, 6), (4, 4.5), (4, 0)], [(0, 2.4), (4, 2.4)]],
    'B': [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    'C': [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1)]],
    'D': [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 1), (3, 0), (0, 0)]],
    'E': [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    'F': [[(4, 6), (0, 6), (0, 0)], [(0, 3), (3, 3)]],
    'G': [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2.8), (2.2, 2.8)]],
    'H': [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    'I': [[(2, 0), (2, 6)]],
    'J': [[(4, 6), (4, 1), (3, 0), (1, 0), (0, 1), (0, 2)]],
    'K': [[(0, 0), (0, 6)], [(4, 6), (0, 2.6)], [(1.4, 3.6), (4, 0)]],
    'L': [[(0, 6), (0, 0), (4, 0)]],
    'M': [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    'N': [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    'P': [_P],
    'R': [_P, [(2, 2.8), (4, 0)]],
    'S': [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    'T': [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    'U': [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    'V': [[(0, 6), (2, 0), (4, 6)]],
    'W': [[(0, 6), (1, 0), (2, 3.5), (3, 0), (4, 6)]],
    'X': [[(0, 0), (4, 6)], [(0, 6), (4, 0)]],
    'Y': [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    'Z': [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    '-': [[(0.8, 3), (3.2, 3)]],
    ' ': [],
}


# ---------------------------------------------------------------- a sheet: lines and marks over one projection

class Sheet:
    """a picture over a plane of the aircraft (u, v in metres): `line` (grooves), marks (`rgb` over `a`), `emit`"""

    def __init__(self, u0, u1, v0, v1, ppm=160.0):
        self.u0, self.v0, self.ppm = u0, v0, ppm
        self.w, self.h = int(math.ceil((u1 - u0) * ppm)), int(math.ceil((v1 - v0) * ppm))
        self.line = np.zeros((self.h, self.w), np.float32)
        self.rgb = np.zeros((self.h, self.w, 3), np.float32)
        self.a = np.zeros((self.h, self.w), np.float32)
        self.emit = None

    def _box(self, pts, pad):
        p = np.array(pts, float)
        x0 = max(0, int(math.floor((p[:, 0].min() - pad - self.u0) * self.ppm)))
        x1 = min(self.w, int(math.ceil((p[:, 0].max() + pad - self.u0) * self.ppm)) + 1)
        y0 = max(0, int(math.floor((p[:, 1].min() - pad - self.v0) * self.ppm)))
        y1 = min(self.h, int(math.ceil((p[:, 1].max() + pad - self.v0) * self.ppm)) + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        U, V = np.meshgrid(self.u0 + (np.arange(x0, x1) + 0.5) / self.ppm, self.v0 + (np.arange(y0, y1) + 0.5) / self.ppm)
        return (slice(y0, y1), slice(x0, x1)), U.astype(np.float32), V.astype(np.float32)

    @staticmethod
    def _dist(U, V, pts, closed=False):
        d = np.full(U.shape, 1e9, np.float32)
        n = len(pts)
        for i in range(n if closed else n - 1):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            L2 = ex * ex + ey * ey
            if L2 < 1e-12:
                t = np.zeros_like(U)
            else:
                t = np.clip(((U - ax) * ex + (V - ay) * ey) / L2, 0, 1)
            d = np.minimum(d, np.hypot(U - (ax + t * ex), V - (ay + t * ey)))
        return d

    def _over(self, sl, cov, colour, emit=None):
        if colour is not None:
            c = np.asarray(colour, np.float32)
            self.rgb[sl] = self.rgb[sl] * (1 - cov[..., None]) + c * cov[..., None]
            self.a[sl] = self.a[sl] + cov * (1 - self.a[sl])
        if emit is not None:
            if self.emit is None:
                self.emit = np.zeros((self.h, self.w, 3), np.float32)
            self.emit[sl] = np.maximum(self.emit[sl], np.asarray(emit, np.float32) * cov[..., None])

    def groove(self, pts, width=0.012, depth=1.0, closed=False):
        b = self._box(pts, width)
        if b is None:
            return
        sl, U, V = b
        cov = np.clip((width / 2 - self._dist(U, V, pts, closed)) * self.ppm + 0.5, 0, 1) * depth
        self.line[sl] = np.maximum(self.line[sl], cov)

    def rect(self, u0, v0, u1, v1, r=0.03, **kw):
        pts = []
        for cx, cy, a0 in ((u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180), (u1 - r, v0 + r, 270)):
            for k in range(4):
                a = math.radians(a0 + 30 * k)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.groove(pts, closed=True, **kw)

    def stroke(self, pts, width, colour, alpha=1.0, emit=None, closed=False):
        b = self._box(pts, width)
        if b is None:
            return
        sl, U, V = b
        cov = np.clip((width / 2 - self._dist(U, V, pts, closed)) * self.ppm + 0.5, 0, 1) * alpha
        self._over(sl, cov, colour, emit)

    def fill(self, pts, colour, alpha=1.0, emit=None):
        b = self._box(pts, 2 / self.ppm)
        if b is None:
            return
        sl, U, V = b
        inside = np.zeros(U.shape, bool)
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if abs(by - ay) < 1e-12:
                continue
            cond = (ay > V) != (by > V)
            inside ^= cond & (U < ax + (V - ay) * (bx - ax) / (by - ay))
        d = self._dist(U, V, pts, True)
        cov = np.clip(np.where(inside, d, -d) * self.ppm + 0.5, 0, 1) * alpha
        self._over(sl, cov, colour, emit)

    def disc(self, c, r, colour, alpha=1.0, emit=None, inner=0.0):
        b = self._box([(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)], 2 / self.ppm)
        if b is None:
            return
        sl, U, V = b
        d = np.hypot(U - c[0], V - c[1])
        cov = np.clip((r - d) * self.ppm + 0.5, 0, 1) * np.clip((d - inner) * self.ppm + 0.5, 0, 1) * alpha
        self._over(sl, cov, colour, emit)

    def text(self, s, centre, height, colour, direction=1, weight=0.15, alpha=1.0, track=1.3, up=(0.0, 1.0)):
        """block capitals centred on `centre`; `direction`: +1 = written towards +u, -1 = towards -u"""
        unit = height / 6
        adv = 4 + track
        total = (len(s) * adv - track) * unit
        rx, ry = direction * up[1], -direction * up[0]            # the writing direction, at right angles to `up`
        for i, ch in enumerate(s):
            ox = -total / 2 + i * adv * unit
            for poly in GLYPHS[ch]:
                pts = [(centre[0] + rx * (ox + px * unit) + up[0] * (py - 3) * unit, centre[1] + ry * (ox + px * unit) + up[1] * (py - 3) * unit)
                       for px, py in poly]
                self.stroke(pts, weight * height, colour, alpha)

    def sample(self, u, v):
        x = (u - self.u0) * self.ppm - 0.5
        y = (v - self.v0) * self.ppm - 0.5
        ok = (x >= 0) & (x <= self.w - 1) & (y >= 0) & (y <= self.h - 1)
        x0 = np.clip(np.floor(x), 0, self.w - 2).astype(np.int32)
        y0 = np.clip(np.floor(y), 0, self.h - 2).astype(np.int32)
        fx = np.clip(x - x0, 0, 1).astype(np.float32)
        fy = np.clip(y - y0, 0, 1).astype(np.float32)

        def bil(a):
            if a.ndim == 3:
                gx, gy = fx[:, None], fy[:, None]
            else:
                gx, gy = fx, fy
            return ((a[y0, x0] * (1 - gx) + a[y0, x0 + 1] * gx) * (1 - gy) + (a[y0 + 1, x0] * (1 - gx) + a[y0 + 1, x0 + 1] * gx) * gy) * (ok[:, None] if a.ndim == 3 else ok)

        return bil(self.line), bil(self.rgb), bil(self.a), (bil(self.emit) if self.emit is not None else None)


# ---------------------------------------------------------------- noise

def _hash(i, j, k, seed):
    h = i.astype(np.uint32) * np.uint32(374761393) + j.astype(np.uint32) * np.uint32(668265263) + k.astype(np.uint32) * np.uint32(2246822519)
    h = h + np.uint32((seed * 3266489917) & 0xFFFFFFFF)
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h = h ^ (h >> np.uint32(16))
    return (h & np.uint32(0xFFFFFF)).astype(np.float32) / np.float32(0xFFFFFF)


def noise(x, y, z, seed=1):
    """value noise 0…1 over space (trilinear, smooth)"""
    with np.errstate(over='ignore'):
        xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
        fx, fy, fz = x - xi, y - yi, z - zi
        fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
        i, j, k = xi.astype(np.int64), yi.astype(np.int64), zi.astype(np.int64)
        out = np.zeros(x.shape, np.float32)
        for di in (0, 1):
            for dj in (0, 1):
                for dk in (0, 1):
                    w = (fx if di else 1 - fx) * (fy if dj else 1 - fy) * (fz if dk else 1 - fz)
                    out += w.astype(np.float32) * _hash(i + di, j + dj, k + dk, seed)
    return out


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- the two aircraft

SCHEMES = {
    # the F-15C: two medium greys in large soft fields, markings in dark grey only
    'c': {
        'light': '#8d969d', 'dark': '#6d7781', 'radome': '#7c858c', 'mark': '#4a5259', 'stencil': '#555d64', 'warn': '#555d64',
        'suit': '#5e6650', 'helmet': '#c5c8c6', 'glove': '#3d3e33',
        'blobs': [((0, 3.0, 4.6), (1.25, 0.95, 2.3)), ((0, 2.9, 10.4), (2.7, 0.8, 2.3)), ((4.9, 2.3, 13.2), (1.7, 0.5, 1.5)), ((0, 2.7, 15.0), (1.5, 0.5, 1.2)),
                  ((3.4, 2.1, 18.3), (1.2, 0.4, 1.0)), ((1.72, 4.3, 17.25), (0.45, 1.25, 1.5)), ((1.4, 2.3, 6.5), (0.6, 0.55, 1.0))],
    },
    # the F-15J: two light greys, the darker one on the upper surfaces; markings in full colour
    'j': {
        'light': '#a1abb4', 'dark': '#84919c', 'radome': '#8f979d', 'mark': '#1d2126', 'stencil': '#2a2f35', 'warn': '#a8252c',
        'suit': '#4f5a44', 'helmet': '#e2e4e2', 'glove': '#d8d8d2',
        'blobs': [((0, 3.1, 3.9), (1.1, 0.8, 2.6)), ((0, 2.95, 10.0), (1.6, 0.8, 3.4)), ((3.0, 2.35, 12.3), (1.9, 0.5, 2.1)), ((0, 2.7, 15.4), (1.9, 0.5, 1.6)),
                  ((2.9, 2.1, 17.8), (1.1, 0.4, 1.1)), ((1.72, 3.6, 17.0), (0.45, 1.0, 1.4))],
    },
}
NUMBERS = {
    # invented: no aircraft carries these
    ('f15c', ''): {'code': 'TG', 'fy': '96', 'serial': '500'},
    ('f15c', 'd'): {'code': 'TG', 'fy': '96', 'serial': '510'},
    ('f15j', ''): {'serial': '62-8999', 'nose': '999'},
    ('f15j', 'dj'): {'serial': '62-8100', 'nose': '100'},
}
RED, WHITE, YELLOW, BLACK = '#b3202a', '#e8e8e4', '#d8b21c', '#15171a'
STRIP = (0.16, 0.20, 0.11)                     # the formation strips' glow (pale yellow-green), as a share of full
BAND = '#1c2550'                               # the game's tail band


def star_bar(sh, c, r, colour, up=(0.0, 1.0)):
    """the star with its two bars, as a stencil in one colour"""
    ux, uy = up
    rx, ry = uy, -ux
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        q = r if k % 2 == 0 else r * 0.382
        px, py = q * math.cos(a), q * math.sin(a)
        pts.append((c[0] + rx * px + ux * py, c[1] + ry * px + uy * py))
    sh.fill(pts, colour)
    sh.disc(c, r * 1.12, colour, inner=r * 1.05)
    for s in (1, -1):
        q = [(s * r * 1.22, -0.26 * r), (s * r * 2.5, -0.26 * r), (s * r * 2.5, 0.3 * r), (s * r * 1.22, 0.3 * r)]
        sh.fill([(c[0] + rx * px + ux * py, c[1] + ry * px + uy * py) for px, py in q], colour)


def roundel(sh, c, r):
    sh.disc(c, r * 1.07, lin(WHITE))
    sh.disc(c, r, lin(RED))


def badge(sh, c, r):
    """the game's own fin badge: a pale moon over a mountain pass"""
    sh.disc(c, r, lin('#1c2550'))
    sh.disc((c[0], c[1] + 0.18 * r), r * 0.62, lin('#e8dfb8'))
    sh.disc((c[0] + 0.22 * r, c[1] + 0.3 * r), r * 0.52, lin('#1c2550'))
    zig = [(-0.8, -0.55), (-0.3, -0.2), (0.05, -0.5), (0.4, -0.1), (0.8, -0.45)]
    sh.stroke([(c[0] + px * r, c[1] + py * r) for px, py in zig], 0.11 * r, lin('#e8e8e4'))
    sh.disc(c, r * 1.06, lin('#e8e8e4'), inner=r * 0.98)


def strip(sh, u0, v0, u1, v1):
    """a formation light strip: a pale panel that glows at night"""
    sh.fill([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], lin('#c9cfa4'), emit=STRIP)
    sh.rect(u0 - 0.012, v0 - 0.012, u1 + 0.012, v1 + 0.012, r=0.01, width=0.008, depth=0.7)


def fus_sheet(side, sc, num, aircraft):
    """the forward fuselage and the spine, seen from the left (side = 1) or the right (-1): (d, y)"""
    sh = Sheet(-0.1, 14.4, 1.3, 3.6)
    for d, y0, y1 in ((2.6, 1.6, 2.9), (3.05, 1.62, 3.0), (3.56, 1.62, 3.13), (4.56, 1.62, 3.12), (5.6, 1.62, 3.12), (6.6, 1.62, 3.1), (7.52, 1.55, 3.45),
                      (8.3, 2.7, 3.36), (9.3, 2.7, 3.16), (10.4, 2.7, 3.06), (11.6, 2.7, 2.95), (12.8, 2.6, 2.8)):
        sh.groove([(d, y0), (d, y1)])
    sh.groove([(2.6, 2.62), (7.5, 2.62)])
    sh.groove([(2.6, 1.93), (7.9, 1.93)])
    for d0, d1 in ((2.74, 3.46), (3.66, 4.46), (4.66, 5.5), (5.7, 6.5)):
        sh.rect(d0, 2.0, d1, 2.55, r=0.05)
    sh.rect(3.2, 1.74, 3.42, 1.86, r=0.02, width=0.008)
    sh.rect(6.75, 2.0, 7.4, 2.5, r=0.04)
    sh.groove([(8.3, 3.0), (12.0, 2.84)])
    strip(sh, 3.9, 2.0, 4.85, 2.06)
    # the ejection seat's warning triangle and the rescue arrow under the canopy
    warn = lin(sc['warn'])
    sh.stroke([(4.72, 2.9), (4.96, 2.9), (4.84, 2.7)], 0.02, warn, closed=True)
    if aircraft == 'f15j':
        sh.fill([(5.87, 2.74), (5.37, 2.74), (5.37, 2.69), (5.25, 2.79), (5.37, 2.89), (5.37, 2.84), (5.87, 2.84)], lin(YELLOW))
        sh.text('RESCUE', (5.56, 2.79), 0.055, lin(BLACK), direction=side, weight=0.18)
        sh.text(num['nose'], (3.28, 2.3), 0.3, lin(sc['mark']), direction=side, weight=0.17)
    else:
        sh.stroke([(5.25, 2.74), (5.87, 2.74), (5.87, 2.84), (5.25, 2.84)], 0.012, lin(sc['stencil']), closed=True)
        sh.text('RESCUE', (5.56, 2.79), 0.055, lin(sc['stencil']), direction=side, weight=0.18)
    return sh


def nac_sheet(side, sc, num, aircraft):
    """intake cowl, nacelle, shoulder and shelf of one side, seen from outside: (d, y)"""
    sh = Sheet(5.0, 18.2, 1.3, 2.9)
    # cowl: the line under its roof, the joint to the nacelle, the ramp's pivot
    tip, top = S.IN_TIP, S.IN_TOP
    k = (top[1] - tip[1]) / (top[0] - tip[0])
    sh.groove([(tip[0] + 0.5, tip[1] + 0.5 * k - 0.11), (top[0], top[1] - 0.11)])
    sh.groove([(7.95, 1.42), (7.95, 2.78)])
    sh.groove([(7.0, 1.9), (7.0, 2.62)])
    for d in (9.0, 10.2, 11.4, 12.6, 13.8, 14.95, 16.05):
        sh.groove([(d, 1.42), (d, 2.76)])
    sh.groove([(8.0, 2.25), (16.9, 2.25)])
    sh.groove([(8.0, 1.8), (16.9, 1.8)])
    for d0, d1, y0, y1 in ((8.25, 8.85, 1.86, 2.19), (9.15, 10.05, 1.5, 1.74), (10.35, 11.25, 1.86, 2.19), (12.75, 13.65, 1.5, 1.74), (13.95, 14.8, 1.86, 2.19)):
        sh.rect(d0, y0, d1, y1, r=0.04)
    strip(sh, 12.75, 2.0, 13.65, 2.06)
    warn = lin(sc['warn'])
    # the intake's danger mark: a slanted bar and the word
    sh.stroke([(6.2, 2.32), (6.62, 2.44)], 0.035, warn)
    sh.text('DANGER', (6.45, 2.28), 0.06, warn, direction=side, weight=0.18)
    if aircraft == 'f15j':
        roundel(sh, (7.2, 2.24), 0.27)
    else:
        star_bar(sh, (9.6, 2.02), 0.14, lin(sc['mark']))
    return sh


def wing_lines(sh):
    for s in (1, -1):
        le = lambda u: 6.85 + u
        sh.groove([(s * 2.05, 13.85), (s * 4.0, 13.85)], width=0.016)
        sh.groove([(s * 4.0, 13.85), (s * 4.0, 14.62)], width=0.016)
        sh.groove([(s * 2.07, 13.85), (s * 2.07, 14.62)], width=0.016)
        sh.groove([(s * 4.0, 14.2), (s * 5.9, 14.66)], width=0.016)
        sh.groove([(s * 5.9, 14.66), (s * 5.9, 15.12)], width=0.016)
        sh.groove([(s * 2.05, le(2.05) + 0.62), (s * 6.25, le(6.25) + 0.62)])
        sh.groove([(s * 2.05, le(2.05) + 2.3), (s * 4.75, le(4.75) + 2.3)])
        for u, d1 in ((2.05, 13.85), (2.95, 13.85), (4.0, 13.85), (5.05, 14.45)):
            sh.groove([(s * u, le(u)), (s * u, d1)])
        sh.groove([(s * 5.95, le(5.95)), (s * 5.95, 14.7)], width=0.01)
        # tailplane: a line behind the leading edge, the pivot's plate
        sh.groove([(s * 2.0, 16.45), (s * 2.72, 17.27)])
        sh.groove([(s * 2.76, 16.98), (s * 4.25, 18.6)])
        sh.groove([(s * 2.74, 16.92), (s * 2.9, 18.9)], width=0.01)
        b = []
        for k in range(16):
            a = 2 * math.pi * k / 16
            b.append((s * 2.25 + 0.2 * math.cos(a), 17.55 + 0.2 * math.sin(a)))
        sh.groove(b, closed=True, width=0.01)


def top_sheet(top, sc, num, aircraft):
    """seen from above (or from below): (x, d)"""
    sh = Sheet(-6.7, 6.7, -0.1, 19.6, ppm=128.0)
    for d, w in ((2.6, 0.62), (3.05, 0.66), (3.56, 0.7), (4.56, 0.74), (5.6, 0.76), (6.6, 0.76), (7.52, 0.76)):
        sh.groove([(-w, d), (w, d)])
    wing_lines(sh)
    if top:
        # the speed brake on the spine
        sh.groove([(-0.42, 8.25), (0.42, 8.25), (0.5, 11.0), (0.2, 11.85), (-0.2, 11.85), (-0.5, 11.0)], closed=True, width=0.016)
        for d in (9.5, 10.6, 11.7, 12.8, 13.9, 14.95, 16.05):
            for s in (1, -1):
                sh.groove([(s * 0.6, d), (s * 2.02, d)])
        for s in (1, -1):
            sh.groove([(s * 1.35, 8.0), (s * 1.35, 16.9)])
            sh.rect(min(s * 0.85, s * 1.25), 12.95, max(s * 0.85, s * 1.25), 13.75, r=0.04)
            # louvres on the cowl's roof
            for k in range(5):
                sh.groove([(s * 0.95, 6.5 + 0.12 * k), (s * 1.3, 6.5 + 0.12 * k)], width=0.02)
            sh.rect(min(s * 0.85, s * 1.42), 6.42, max(s * 0.85, s * 1.42), 7.08, r=0.03, width=0.008)
            for x, d in ((3.0, 14.3), (5.0, 14.75), (2.5, 18.75)):
                sh.text('NO STEP', (s * x, d), 0.06, lin(sc['stencil']), direction=1, weight=0.17, up=(0.0, -1.0))
            strip(sh, min(s * 5.5, s * 6.05), 13.96, max(s * 5.5, s * 6.05), 14.02)
    else:
        sh.groove([(0, 8.0), (0, 16.5)])
        sh.rect(-0.28, 5.85, 0.28, 7.1, r=0.04, width=0.016)
        sh.groove([(0, 5.85), (0, 7.1)], width=0.016)
        for s in (1, -1):
            sh.rect(min(s * 0.78, s * 1.5), 10.8, max(s * 0.78, s * 1.5), 12.4, r=0.05, width=0.016)
            sh.rect(min(s * 0.3, s * 1.15), 12.75, max(s * 0.3, s * 1.15), 16.5, r=0.06)
            sh.groove([(s * 0.3, 14.6), (s * 1.15, 14.6)])
        for d in (8.5, 9.6, 10.7, 12.55):
            sh.groove([(-1.9, d), (1.9, d)])
        for s in (1, -1):
            strip(sh, min(s * 5.5, s * 6.05), 13.96, max(s * 5.5, s * 6.05), 14.02)
    if aircraft == 'f15j':
        for s in (1, -1):
            roundel(sh, (s * 4.35, 12.95), 0.42)
    else:
        star_bar(sh, ((4.4 if top else -4.4), 12.95), 0.3, lin(sc['mark']), up=(0.0, -1.0))
    return sh


def fin_sheet(side, sc, num, aircraft):
    """a fin's outer face, seen from the left (1) or the right (-1): (d, y); `marks` are for the outer faces only"""
    sh = Sheet(15.0, 18.7, 2.2, 5.8)
    le, te = S.fin_le, S.fin_te
    hinge = lambda y: 17.32 + (y - 2.62) * 0.2
    sh.groove([(hinge(2.62), 2.62), (hinge(4.62), 4.62)], width=0.016)
    sh.groove([(hinge(4.62), 4.62), (te(4.62), 4.62)], width=0.016)
    sh.groove([(hinge(2.62), 2.62), (te(2.62), 2.62)], width=0.016)
    sh.groove([(le(2.5) + 0.3, 2.5), (le(5.3) + 0.3, 5.3)])
    sh.groove([(le(5.27), 5.27), (te(5.27), 5.27)])
    sh.groove([(le(3.9) + 0.3, 3.9), (hinge(3.9), 3.9)])
    sh.groove([(le(3.2) + 0.3, 3.2), (hinge(3.2), 3.2)])
    strip(sh, 17.0, 4.8, 17.55, 4.86)
    mark = lin(sc['mark'])
    if aircraft == 'f15j':
        badge(sh, (17.05, 4.25), 0.3)
        sh.text(num['serial'], (16.75, 3.0), 0.15, mark, direction=side, weight=0.16)
    else:
        # the game's band under the tip, the invented code and number
        y0, y1 = 5.03, 5.21
        sh.fill([(le(y0), y0), (te(y0), y0), (te(y1), y1), (le(y1), y1)], lin(BAND))
        sh.stroke([(le(y0), y0), (te(y0), y0)], 0.012, lin('#35c8d8'))
        sh.stroke([(le(y1), y1), (te(y1), y1)], 0.012, lin('#35c8d8'))
        sh.text('NOCTURNE', ((le(5.12) + te(5.12)) / 2, 5.12), 0.085, lin(WHITE), direction=side, weight=0.17)
        sh.text(num['code'], (17.0, 4.08), 0.6, mark, direction=side, weight=0.17)
        sh.text(num['serial'], (16.98, 3.12), 0.3, mark, direction=side, weight=0.17)
        sh.text('AF', (16.98 - side * 0.62, 3.2), 0.1, mark, direction=side, weight=0.17)
        sh.text(num['fy'], (16.98 - side * 0.62, 3.04), 0.1, mark, direction=side, weight=0.17)
    return sh


def panel_sheet():
    """the instrument panel's face: (x, y), 0 at the panel's middle and the tub's floor"""
    sh = Sheet(-0.4, 0.4, 0.0, 0.7, ppm=600.0)
    grey, glass = lin('#3b3f43'), lin('#0c0f10')
    for cx, cy, w, h in ((0.0, 0.43, 0.13, 0.12), (-0.17, 0.4, 0.1, 0.1), (0.17, 0.4, 0.1, 0.1)):
        sh.fill([(cx - w / 2 - 0.008, cy - h / 2 - 0.008), (cx + w / 2 + 0.008, cy - h / 2 - 0.008), (cx + w / 2 + 0.008, cy + h / 2 + 0.008), (cx - w / 2 - 0.008, cy + h / 2 + 0.008)], grey)
        sh.fill([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)], lin('#10301c'), emit=(0.05, 0.22, 0.09))
    for k in range(10):
        cx, cy = -0.27 + 0.06 * (k % 5) * 2.25, 0.27 - 0.075 * (k // 5)
        sh.disc((cx, cy), 0.03, grey)
        sh.disc((cx, cy), 0.025, glass)
        a = 0.7 + 1.9 * k
        sh.stroke([(cx, cy), (cx + 0.02 * math.cos(a), cy + 0.02 * math.sin(a))], 0.003, lin('#d8d8d0'))
    for k in range(8):
        sh.fill([(-0.3 + 0.08 * k, 0.5), (-0.26 + 0.08 * k, 0.5), (-0.26 + 0.08 * k, 0.52), (-0.3 + 0.08 * k, 0.52)], lin('#8a8d86'))
    return sh


DENSITY = {'duct': 0.6, 'ductend': 0.5, 'tub': 0.6, 'nozzle_in': 0.6, 'glass': 0.04, 'beacon': 0.15, 'taxilight': 0.15, 'tyre': 0.7, 'strut': 0.75,
           'hub': 0.8, 'brake': 0.5, 'door': 0.8, 'steel': 0.6, 'chrome': 0.5, 'seat': 0.7, 'cushion': 0.7, 'suit': 0.8, 'harness': 0.6, 'glove': 0.6,
           'mask': 0.7, 'handle': 0.7, 'coaming': 0.6, 'lip': 0.8, 'frame': 0.8, 'panel': 1.2}

# zone → (colour, roughness, metalness) for what is not camouflage
PLAIN = {
    'lip': ('#5d666e', 0.5, 0.0), 'frame': ('#4a5158', 0.5, 0.0), 'duct': ('#d6d9d6', 0.45, 0.0), 'ductend': ('#1a1c1e', 0.6, 0.3),
    'tub': ('#3b3e41', 0.8, 0.0), 'coaming': ('#141618', 0.9, 0.0), 'panel': ('#1b1d20', 0.7, 0.0), 'seat': ('#2b2e30', 0.7, 0.0),
    'cushion': ('#4f5744', 0.9, 0.0), 'handle': ('#d8b21c', 0.6, 0.0), 'harness': ('#8c8d84', 0.85, 0.0), 'visor': ('#111315', 0.1, 0.4),
    'mask': ('#383b38', 0.7, 0.0), 'steel': ('#9a9c9c', 0.35, 0.8), 'strut': ('#dfe1de', 0.4, 0.0), 'chrome': ('#c8cacb', 0.15, 1.0),
    'tyre': ('#1a1b1c', 0.88, 0.0), 'hub': ('#d9dbd8', 0.45, 0.0), 'brake': ('#46484a', 0.55, 0.6), 'nozzle': ('#6a625a', 0.45, 0.8),
    'nozzle_in': ('#9a958c', 0.6, 0.2), 'metal': ('#8a837a', 0.42, 0.75),
}
CAMO = ('fus', 'nac', 'deck', 'cowl', 'wing', 'stab', 'fin', 'door')
METAL_FROM = 14.95                 # aft of this the engine bays' skin is bare titanium


def paint(objs, mats, aircraft, variant, seats, cfg, size=2048, keep=(), workdir='.'):
    sc = SCHEMES[cfg['scheme']]
    num = NUMBERS[(aircraft, variant)]
    os.makedirs(workdir, exist_ok=True)
    ppm = JA.unwrap(objs, density=lambda ob, name: DENSITY.get(name, 1.0), angle=50.0)
    tris = JA.triangles(objs, skip=keep)
    R = JA.raster(tris, size)
    # the sky each texel sees, at a quarter of the size
    Rl = JA.raster(tris, size // 4, pad=4)
    ao = JA.occlusion(JA.triangles(objs, skip=('glass',)), Rl, reach=1.5, rays=18, floor=None)
    ao = JA.blur(JA.resize(ao, size), 1)

    fill = R['fill']
    iy, ix = np.nonzero(fill)
    pos, nrm = R['pos'][iy, ix], R['nrm'][iy, ix]
    X, Y, D = pos[:, 0], pos[:, 1], S.ZN - pos[:, 2]
    NX, NY, NZ = nrm[:, 0], nrm[:, 1], nrm[:, 2]
    zid = R['zone'][iy, ix]
    zones = R['zones']
    oid = R['obj'][iy, ix]
    onames = [o.name for o in objs]
    n = len(X)

    def Z(*names):
        m = np.zeros(n, bool)
        for nm in names:
            if nm in zones:
                m |= zid == zones.index(nm)
        return m

    base = np.zeros((n, 3), np.float32)
    rough = np.full(n, 0.6, np.float32)
    metal = np.zeros(n, np.float32)
    height = np.zeros(n, np.float32)
    emit = np.zeros((n, 3), np.float32)
    for name, (c, r, m) in PLAIN.items():
        k = Z(name)
        base[k] = lin(c)
        rough[k] = r
        metal[k] = m
    for name, key in (('suit', 'suit'), ('helmet', 'helmet'), ('glove', 'glove')):
        k = Z(name)
        base[k] = lin(sc[key])
        rough[k] = 0.4 if name == 'helmet' else 0.9

    # ---- camouflage: soft fields in space, none on the undersides
    camo = Z(*CAMO)
    f = np.full(n, -1.0, np.float32)
    for (cx, cy, cd), (rx, ry, rd) in sc['blobs']:
        f = np.maximum(f, 1 - ((np.abs(X) - cx) / rx) ** 2 - ((Y - cy) / ry) ** 2 - ((D - cd) / rd) ** 2)
    f += 0.5 * (noise(X * 1.3, Y * 1.3, D * 1.3, 7) - 0.5) + 0.12 * (noise(X * 6, Y * 6, D * 6, 8) - 0.5)
    dark = sstep(-0.06, 0.06, f) * sstep(-0.45, -0.15, NY)
    light, darkc = lin(sc['light']), lin(sc['dark'])
    base[camo] = light + (darkc - light) * dark[camo, None]
    rough[camo] = 0.56
    k = Z('radome')
    base[k] = lin(sc['radome'])
    rough[k] = 0.48
    # gear doors: the inside is white
    k = Z('door')
    inner = k & (((np.abs(X) > 0.5) & (NX * np.sign(X) < 0.3)) | ((np.abs(X) <= 0.5) & (NZ < 0.3) & (np.abs(NX) < 0.8)))
    base[inner] = lin('#dfe1de')

    # ---- sheets: lines and marks by projection
    line = np.zeros(n, np.float32)
    body_f = Z('fus', 'radome', 'frame')
    body_n = Z('nac', 'deck', 'cowl', 'lip', 'metal')
    body = body_f | body_n
    flat = np.abs(NY) >= np.abs(NX)
    lift = Z('wing', 'stab')
    fin = Z('fin')
    jobs = []
    for top in (True, False):
        m = ((body & flat) | lift) & ((NY >= 0) == top) & (np.abs(NZ) < 0.75)
        jobs.append((lambda t=top: top_sheet(t, sc, num, aircraft), m, 'x', 'top' if top else 'bot', None))
    for side in (1, -1):
        sm = (NX >= 0) == (side > 0)
        jobs.append((lambda s=side: fus_sheet(s, sc, num, aircraft), body_f & ~flat & sm & (np.abs(NZ) < 0.75), 'd', 'fus' + 'LR'[side < 0], None))
        jobs.append((lambda s=side: nac_sheet(s, sc, num, aircraft), body_n & ~flat & sm & (np.abs(NZ) < 0.75) & (np.abs(X) > 1.2), 'd', 'nac' + 'LR'[side < 0], None))
        outer = (NX * (np.abs(X) - S.FIN_X)) > 0
        jobs.append((lambda s=side: fin_sheet(s, sc, num, aircraft), fin & sm & (np.abs(NX) > 0.5), 'd', 'fin' + 'LR'[side < 0], outer))
    for make, m, kind, name, marks in jobs:
        if not m.any():
            continue
        sh = make()
        u, v = (X[m], D[m]) if kind == 'x' else (D[m], Y[m])
        ln, rgb, a, em = sh.sample(u, v)
        if marks is not None:
            a = a * marks[m]
            rgb = rgb * marks[m][:, None]
            if em is not None:
                em = em * marks[m][:, None]
        line[m] = np.maximum(line[m], ln)
        base[m] = base[m] * (1 - a[:, None]) + rgb
        if em is not None:
            emit[m] = np.maximum(emit[m], em)
        dbg = np.zeros((sh.h, sh.w, 3), np.float32) + 0.35
        dbg = dbg * (1 - sh.a[..., None]) + sh.rgb
        dbg *= (1 - 0.8 * sh.line[..., None])
        JA.save(dbg, os.path.join(workdir, f'sheet_{name}.png'), True)
        del sh

    # ---- bare metal aft: the engine bays' skin, panel by panel in its own tint
    bare = Z('metal') | (Z('nac', 'deck') & (D > METAL_FROM))
    th = np.arctan2(Y - S.ENG_Y, np.abs(X) - S.ENG_X)
    cell = _hash(np.floor(D / 0.55).astype(np.int64), np.floor(th / 0.5).astype(np.int64), (X > 0).astype(np.int64), 5)
    tint = np.stack([0.60 + 0.06 * cell, 0.59 + 0.05 * cell, 0.575 + 0.04 * (1 - cell)], 1).astype(np.float32)
    streak = noise(X * 14, Y * 14, D * 0.7, 21)
    tint = tint * (0.9 + 0.16 * streak[:, None]) * (0.6 + 0.4 * sstep(18.0, 15.2, D))[:, None]
    base[bare] = (tint ** 2.2)[bare] * 1.15
    rough[bare] = 0.36 + 0.14 * streak[bare]
    metal[bare] = 0.78

    # ---- weathering of the paint: a little cloud, streaks along the airflow, dirt in the lines
    painted = (camo | Z('radome')) & ~bare
    w = 1 - 0.07 * (noise(X * 2.2, Y * 2.2, D * 2.2, 11) - 0.5) - 0.10 * (noise(X * 16, Y * 16, D * 1.1, 12) - 0.5)
    w -= 0.05 * sstep(0.2, -0.6, NY) * noise(X * 5, Y * 5, D * 0.6, 13)
    base[painted] *= w[painted, None]
    rough[painted] += 0.06 * (noise(X * 9, Y * 9, D * 9, 14)[painted] - 0.5)
    grime = JA.blur(_scatter(line, iy, ix, size), 2)[iy, ix]
    base *= (1 - 0.18 * np.clip(grime * 3, 0, 1) * (painted | bare))[:, None]
    base *= (1 - 0.55 * line)[:, None]
    height -= 0.003 * line

    # ---- nozzles: the flaps' seams, heat colours, the light lining inside
    k = Z('nozzle')
    seam = np.abs(((th / (2 * math.pi) * 15) % 1.0) - 0.5) * 2          # 1 on a seam
    t = np.clip((D - S.NOZ_D0) / (S.NOZ_D1 - S.NOZ_D0), 0, 1)
    c = lin('#6f665d')[None, :] * (1 - 0.35 * t[:, None]) * (0.85 + 0.3 * noise(th * 6, D * 9, X * 0 + 3, 41)[:, None])
    c = c * (1 - 0.6 * sstep(0.86, 0.97, seam)[:, None]) * (1 - 0.35 * sstep(0.04, 0.0, np.abs(t - 0.45))[:, None])
    base[k] = c[k]
    height[k] -= 0.004 * sstep(0.86, 0.97, seam)[k]
    k = Z('nozzle_in')
    soot = noise(th * 9, D * 1.5, X * 0 + 9, 42)
    c = lin('#a39e94')[None, :] * (0.55 + 0.5 * soot[:, None]) * (0.25 + 0.75 * sstep(S.NOZ_D0 - 0.3, S.NOZ_D1, D))[:, None]
    c = c * (1 - 0.5 * sstep(0.9, 0.98, seam)[:, None])
    base[k] = c[k]

    # ---- intake: the white duct greying towards the engine's face (a ring of blades)
    k = Z('duct')
    base[k] *= (0.45 + 0.55 * sstep(9.0, 6.8, D))[k, None]
    k = Z('ductend')
    cx, cy = (S.IN_XO + S.IN_XI) / 2, 1.865
    rr = np.hypot(np.abs(X) - cx, Y - cy)
    ang = np.arctan2(Y - cy, np.abs(X) - cx)
    blades = 0.5 + 0.5 * np.sin(ang * 26 + rr * 9)
    c = (0.03 + 0.09 * blades) * (rr > 0.1) + 0.12 * (rr <= 0.1)
    base[k] = np.repeat(c[:, None], 3, 1)[k]
    metal[k] = 0.6

    # ---- wheels: tread grooves, the wheel's holes
    for names, (yc, zc, r, hole) in ((('spin_l_m', 'spin_r_m'), (S.R_MAIN, -S.WB / 2, S.R_MAIN, 0.036)), (('steer_nose_m',), (S.R_NOSE, S.WB / 2, S.R_NOSE, 0.02))):
        ob = np.zeros(n, bool)
        for nm in names:
            ob |= oid == onames.index(nm)
        rr = np.hypot(Y - yc, pos[:, 2] - zc)
        ang = np.arctan2(Y - yc, pos[:, 2] - zc)
        k = ob & Z('tyre')
        xw = np.abs(np.abs(X) - (S.TRACK / 2 if len(names) == 2 else 0.0))
        groove = (rr > r - 0.03) * (sstep(0.006, 0.002, np.abs(xw - 0.035)) + sstep(0.006, 0.002, np.abs(xw - 0.075)) + (sstep(0.006, 0.002, xw) if len(names) == 1 else 0))
        base[k] *= (1 - 0.5 * groove[k, None]) * (0.9 + 0.2 * noise(ang * 20, rr * 40, X * 30, 51)[k, None])
        height[k] -= 0.003 * groove[k]
        base[k & (rr < r - 0.03) & (rr > r - 0.05)] *= 1.25
        k = ob & Z('hub')
        r_rim = 0.235 if len(names) == 2 else 0.14
        hr = 0.6 * r_rim
        a8 = (ang / (2 * math.pi) * 8) % 1.0 - 0.5
        hd = np.hypot(rr - hr, a8 * 2 * math.pi / 8 * hr)
        holes = sstep(hole + 0.004, hole - 0.004, hd)
        base[k] *= (1 - 0.85 * holes[k, None])
        base[k & (rr < 0.05)] = lin('#8a8d8e')
        metal[k & (rr < 0.05)] = 0.8
    k = Z('strut', 'door') & ~camo
    base[k] *= (0.93 + 0.1 * noise(X * 30, Y * 30, D * 30, 52)[k, None])

    # ---- cockpit: the panel's face, the handles' stripes, the helmet
    k = Z('panel') & (NZ < -0.7) & (np.abs(D - (S.tub_range(seats)[0] + 0.09)) < 0.02)
    if k.any():
        sh = panel_sheet()
        ln, rgb, a, em = sh.sample(X[k], Y[k] - S.TUB_FLOOR)
        base[k] = base[k] * (1 - a[:, None]) + rgb
        if em is not None:
            emit[k] = np.maximum(emit[k], em)
    k = Z('handle')
    stripe = ((pos[:, 2] * 38 + Y * 38) % 1.0) < 0.5
    base[k & stripe] = lin(BLACK)
    k = Z('helmet')
    if aircraft == 'f15j':
        base[k & (np.abs(X) < 0.022) & (NY > 0.1)] = lin('#1c2550')
    k = Z('cushion', 'suit')
    base[k] *= (0.85 + 0.3 * noise(X * 60, Y * 60, D * 60, 61)[k, None])

    # ---- lamps: position lights on the wing tips, the tail light, in their lenses
    tipl = Z('wing') & (np.abs(X) > 6.4) & (D < 13.66)
    for sgn, col, e in ((1, '#c8242c', (1.0, 0.08, 0.05)), (-1, '#1fae5c', (0.05, 1.0, 0.3))):
        k = tipl & (np.sign(X) == sgn)
        base[k] = lin(col)
        emit[k] = e
        rough[k] = 0.2
    k = Z('fin') & (D > 18.36) & (Y > 5.4) & (X > 0)
    base[k] = lin('#e6e6e0')
    emit[k] = (0.9, 0.9, 0.85)
    rough[k] = 0.2

    # ---- into the atlas
    aof = ao[iy, ix]
    base *= (0.72 + 0.28 * aof)[:, None]

    def full(a, fillv):
        out = np.full((size, size) + a.shape[1:], fillv, np.float32)
        out[iy, ix] = a
        return out

    files = {}
    files['base'] = JA.save(full(np.clip(base, 0, 1), 0.3), os.path.join(workdir, 'base.png'), True)
    orm = np.stack([aof, np.clip(rough, 0.05, 1), np.clip(metal, 0, 1)], 1)
    files['orm'] = JA.save(full(orm, 1.0), os.path.join(workdir, 'orm.png'), False)
    hmap = full(height, 0.0)
    nmap = JA.normal_from_height(JA.blur(hmap, 1), 1.0 / (ppm * size), strength=2.5)
    nmap[~fill] = (0.5, 0.5, 1.0)
    files['normal'] = JA.save(nmap, os.path.join(workdir, 'normal.png'), False)
    files['emit'] = JA.save(full(emit, 0.0), os.path.join(workdir, 'emit.png'), True)
    mat = JA.material('airframe', files, emission=1.0)
    JA.apply(objs, mat, keep=keep)
    print(f'PAINT {aircraft}{"-" + variant if variant else ""}: {n} texels, {ppm * size:.0f} px/m')
    return mat


def _scatter(values, iy, ix, size):
    out = np.zeros((size, size), np.float32)
    out[iy, ix] = values
    return out
