"""
Twigs modelled for the sprite bakes (nature_kit.bake_twigs): needles and leaves as real geometry, lying flat.
Frame: x across, y along the twig (its base at the origin), z towards the camera. Colours are linear; a vertex'
alpha is its thickness mask (1 = a thin blade that lets light through, ~0 = wood).
"""
import math

import numpy as np


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) + 1e-12)


def srgb(hex_colour):
    h = hex_colour.lstrip('#')
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


class Twig:
    def __init__(self):
        self.P, self.N, self.C, self.T = [], [], [], []
        self.n = 0

    def _add(self, P, N, C, T):
        P = np.asarray(P, float).reshape(-1, 3)
        self.P.append(P)
        self.N.append(np.asarray(N, float).reshape(-1, 3))
        self.C.append(np.asarray(C, float).reshape(-1, 4))
        self.T.append(np.asarray(T, int).reshape(-1, 3) + self.n)
        self.n += len(P)

    def stem(self, pts, r0, r1, colour, sides=5):
        """a woody axis along the points"""
        pts = np.asarray(pts, float)
        n = len(pts)
        tang = np.gradient(pts, axis=0)
        tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-12
        P, N, C, T = [], [], [], []
        for i in range(n):
            a = unit(np.cross(tang[i], [0, 0, 1.0]))
            b = np.cross(tang[i], a)
            r = r0 + (r1 - r0) * i / max(n - 1, 1)
            for k in range(sides):
                ang = 2 * math.pi * k / sides
                d = math.cos(ang) * a + math.sin(ang) * b
                P.append(pts[i] + d * r)
                N.append(d)
                C.append((*colour, 0.05))
        for i in range(n - 1):
            for k in range(sides):
                p, q = i * sides + k, i * sides + (k + 1) % sides
                T += [(p, q, q + sides), (p, q + sides, p + sides)]
        self._add(P, N, C, T)

    def blade(self, base, direction, normal, length, width, colour, tip=None, shape='needle', fold=0.0, curl=0.0, segs=3, thickness=1.0):
        """
        A leaf blade from `base` along `direction`, its face towards `normal`: two half strips either side of the
        midrib, each tilted up by `fold` (rad), the tip curling down by `curl` × length. shape: 'needle' (even,
        pointed), 'ovate' (a beech leaf), 'lance' (bamboo, willow), 'scale' (short and blunt).
        """
        d = unit(direction)
        nrm = unit(np.asarray(normal, float) - d * np.dot(normal, d))
        side = np.cross(d, nrm)
        tip = colour if tip is None else tip
        prof = {
            'needle': lambda t: (1 - t ** 3) * 0.5 + 0.5 * (1 - t),
            'ovate': lambda t: math.sin(math.pi * min(1, t ** 0.75 * 1.02)) ** 0.8 if t < 1 else 0.0,
            'lance': lambda t: math.sin(math.pi * t ** 0.6) ** 0.9 if t < 1 else 0.0,
            'scale': lambda t: (1 - t ** 2) ** 0.5,
        }[shape]
        for sgn in (-1, 1):
            hn = unit(nrm * math.cos(fold) - side * sgn * math.sin(fold))    # this half's normal
            hs = unit(side * sgn * math.cos(fold) + nrm * math.sin(fold))    # … and its outward direction
            P, N, C, T = [], [], [], []
            for j in range(segs + 1):
                t = j / segs
                c = np.asarray(base, float) + d * (length * t) - nrm * (curl * length * t * t)
                w = width / 2 * max(prof(min(t, 0.999)) if j < segs else 0.0, 0.0)
                col = np.asarray(colour) + (np.asarray(tip) - np.asarray(colour)) * t
                P += [c, c + hs * w]
                N += [hn, hn]
                C += [(*col, thickness), (*col, thickness)]
            for j in range(segs):
                a = j * 2
                T += [(a, a + 1, a + 3), (a, a + 3, a + 2)] if sgn > 0 else [(a, a + 3, a + 1), (a, a + 2, a + 3)]
            self._add(P, N, C, T)

    def needles(self, rng, pts, length, width, colour, tip, spacing=0.004, lean=40.0, spread=1.0, flat=0.0, thickness=0.8, vary=0.2, shape='needle'):
        """
        Needles all along an axis, set spirally: each leans `lean` degrees off the axis; `flat` (0…1) presses the
        spiral into the picture's plane (the two-ranked look of fir and spruce twigs), `spread` < 1 thins them out.
        """
        pts = np.asarray(pts, float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        arc = np.concatenate([[0], np.cumsum(seg)])
        phi = rng.u(0, 6.28)
        s = spacing * 0.5
        while s < arc[-1]:
            i = min(int(np.searchsorted(arc, s)) - 1, len(pts) - 2)
            i = max(i, 0)
            f = (s - arc[i]) / max(seg[i], 1e-9)
            p = pts[i] + (pts[i + 1] - pts[i]) * f
            t = unit(pts[i + 1] - pts[i])
            a = unit(np.cross(t, [0, 0, 1.0]))
            b = np.cross(t, a)
            phi += 2.39996
            radial = unit(math.cos(phi) * a + math.sin(phi) * b * (1 - flat))
            ln = math.radians(lean + rng.n(8))
            d = unit(t * math.cos(ln) + radial * math.sin(ln))
            # the blade's face: across its own direction, as much towards the camera as it can
            nrm = unit(np.array([0, 0, 1.0]) - d * d[2] + radial * 0.15)
            k = 1 + rng.n(vary)
            col = np.asarray(colour) * max(0.5, k)
            if rng.u() < spread:
                self.blade(p, d, nrm, length * rng.u(0.75, 1.2), width, col, np.asarray(tip) * max(0.5, k), shape, fold=0.25, curl=rng.u(-0.15, 0.2), segs=2, thickness=thickness)
            s += spacing * rng.u(0.7, 1.3)

    def result(self):
        """(arrays for nature_kit.to_object, width, length): the twig centred across, its lowest point on y = 0"""
        P, N, C, T = np.concatenate(self.P), np.concatenate(self.N), np.concatenate(self.C), np.concatenate(self.T)
        P = P.copy()
        P[:, 0] -= (P[:, 0].min() + P[:, 0].max()) / 2
        P[:, 1] -= P[:, 1].min()
        width, length = P[:, 0].max() - P[:, 0].min(), P[:, 1].max()
        return (P, N, np.zeros((len(P), 2)), C, T), float(width), float(length)


def curve(rng, start, d, length, segs, bend=None, wiggle=0.0):
    """points of an axis: from `start` along `d`, turning towards `bend` (a vector added over the length)"""
    pts = [np.asarray(start, float)]
    d = unit(d)
    for _ in range(segs):
        if bend is not None:
            d = d + np.asarray(bend, float) / segs
        if wiggle:
            d = d + rng.vec() * wiggle / segs
        d = unit(d)
        pts.append(pts[-1] + d * (length / segs))
    return np.array(pts)


def along(pts, t):
    """the point and direction at the fraction t of a polyline"""
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    arc = np.concatenate([[0], np.cumsum(seg)])
    s = t * arc[-1]
    i = int(np.clip(np.searchsorted(arc, s) - 1, 0, len(pts) - 2))
    f = (s - arc[i]) / max(seg[i], 1e-9)
    return pts[i] + (pts[i + 1] - pts[i]) * f, unit(pts[i + 1] - pts[i])
