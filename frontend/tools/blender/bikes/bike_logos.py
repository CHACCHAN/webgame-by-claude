"""
Our own simple lettering and badges for the bike models: block letters drawn as strokes (no fonts, no copied logos),
laid onto the bodywork as decals by ray casts. Screen coordinates (s, t) are as seen from the side the decal is on:
right side (seen from -x): s = z, t = y; left side (seen from +x): s = -z, t = y, so text reads left to right on both.
"""
import math

import numpy as np

import bike_kit as K


def _arc(cx, cy, rx, ry, a0, a1, n=10):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


# glyph: (advance width, [polyline, ...]) in units of the cap height
GLYPHS = {
    'A': (0.78, [[(0.0, 0.0), (0.36, 1.0), (0.42, 1.0), (0.78, 0.0)], [(0.17, 0.36), (0.61, 0.36)]]),
    'B': (0.66, [[(0.0, 0.0), (0.0, 1.0), (0.42, 1.0)] + _arc(0.42, 0.76, 0.22, 0.24, 90, -90, 8) + [(0.0, 0.52)],
                 [(0.0, 0.52), (0.44, 0.52)] + _arc(0.44, 0.26, 0.22, 0.26, 90, -90, 8) + [(0.0, 0.0)]]),
    'D': (0.72, [[(0.0, 0.0), (0.0, 1.0), (0.30, 1.0)] + _arc(0.30, 0.5, 0.42, 0.5, 90, -90, 14) + [(0.0, 0.0)]]),
    'E': (0.58, [[(0.58, 1.0), (0.0, 1.0), (0.0, 0.0), (0.58, 0.0)], [(0.0, 0.5), (0.48, 0.5)]]),
    'H': (0.70, [[(0.0, 0.0), (0.0, 1.0)], [(0.70, 0.0), (0.70, 1.0)], [(0.0, 0.5), (0.70, 0.5)]]),
    'I': (0.0, [[(0.0, 0.0), (0.0, 1.0)]]),
    'K': (0.66, [[(0.0, 0.0), (0.0, 1.0)], [(0.66, 1.0), (0.0, 0.38)], [(0.22, 0.58), (0.66, 0.0)]]),
    'N': (0.70, [[(0.0, 0.0), (0.0, 1.0), (0.70, 0.0), (0.70, 1.0)]]),
    'O': (0.80, [_arc(0.40, 0.5, 0.40, 0.5, 0, 360, 24)]),
    'R': (0.66, [[(0.0, 0.0), (0.0, 1.0), (0.40, 1.0)] + _arc(0.40, 0.75, 0.24, 0.25, 90, -90, 8) + [(0.0, 0.5)],
                 [(0.30, 0.5), (0.66, 0.0)]]),
    'S': (0.64, [_arc(0.32, 0.75, 0.30, 0.25, 15, 270, 10) + _arc(0.32, 0.25, 0.32, 0.25, 90, -165, 10)]),
    'U': (0.68, [[(0.0, 1.0), (0.0, 0.32)] + _arc(0.34, 0.32, 0.34, 0.32, 180, 360, 10) + [(0.68, 1.0)]]),
    'W': (1.0, [[(0.0, 1.0), (0.22, 0.0), (0.5, 0.78), (0.78, 0.0), (1.0, 1.0)]]),
    'Z': (0.62, [[(0.0, 1.0), (0.62, 1.0), (0.0, 0.0), (0.62, 0.0)]]),
    'G': (0.76, [_arc(0.40, 0.5, 0.38, 0.5, 40, 340, 18) + [(0.76, 0.42), (0.46, 0.42)]]),
    'Y': (0.70, [[(0.0, 1.0), (0.35, 0.5), (0.70, 1.0)], [(0.35, 0.5), (0.35, 0.0)]]),
    'X': (0.68, [[(0.0, 0.0), (0.68, 1.0)], [(0.0, 1.0), (0.68, 0.0)]]),
    '0': (0.62, [_arc(0.31, 0.5, 0.31, 0.5, 0, 360, 20)]),
    '1': (0.30, [[(0.0, 0.78), (0.30, 1.0), (0.30, 0.0)]]),
    '3': (0.60, [_arc(0.30, 0.75, 0.28, 0.25, 160, -90, 9) + _arc(0.30, 0.26, 0.30, 0.26, 90, -160, 9)]),
    # 隼 (hayabusa, falcon): our own plain block drawing of the character, not the maker's brush logo
    '隼': (1.0, [[(0.32, 1.0), (0.06, 0.60)], [(0.20, 0.78), (0.20, 0.40)], [(0.50, 1.0), (0.58, 0.91)],
                [(0.44, 0.88), (0.44, 0.42)], [(0.44, 0.88), (0.94, 0.88)], [(0.44, 0.74), (0.86, 0.74)],
                [(0.44, 0.60), (0.86, 0.60)], [(0.44, 0.44), (0.96, 0.44)], [(0.02, 0.25), (0.98, 0.25)],
                [(0.52, 0.42), (0.52, 0.0)]]),
    ' ': (0.45, []),
}


def _thin(line, min_seg):
    """drop polyline points closer than min_seg to the last kept one (keeps the ends): fewer quads for small text"""
    if min_seg <= 0 or len(line) < 3:
        return line
    out = [line[0]]
    for p in line[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= min_seg:
            out.append(p)
    out.append(line[-1])
    return out


def stroke_quads(text, height, stroke=0.16, gap=0.28, shear=0.0, condense=1.0, min_seg=0.0):
    """the text's strokes as quads in text space (x along the baseline, y up; centred on the text's middle);
    min_seg (in cap heights) thins the curves' points"""
    quads = []
    x = 0.0
    for ch in text:
        w, lines = GLYPHS[ch]
        for line in lines:
            line = _thin(line, min_seg)
            for (x0, y0), (x1, y1) in zip(line, line[1:]):
                a = np.array([x + x0 * condense, y0])
                b = np.array([x + x1 * condense, y1])
                d = b - a
                L = float(np.linalg.norm(d))
                if L < 1e-6:
                    continue
                d = d / L
                n = np.array([-d[1], d[0]]) * stroke / 2
                e = d * stroke / 2
                q = [a - e - n, b + e - n, b + e + n, a - e + n]
                quads.append([(px + shear * py, py) for px, py in q])
        x += w * condense + gap + stroke
    width = x - gap - stroke
    return [[((px - width / 2) * height, (py - 0.5) * height) for px, py in q] for q in quads], width * height


def place(quads, centre, direction):
    """text-space quads → screen (s, t) at a centre with a reading direction"""
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    n = np.array([-d[1], d[0]])
    c = np.array(centre, float)
    return [[tuple(c + d * px + n * py) for px, py in q] for q in quads]


def to_side(poly, side):
    """screen (s, t) → side projection (z, y); side = -1 right (seen from -x), +1 left"""
    return [(s if side < 0 else -s, t) for s, t in poly]


def _dense_diagonal(q, step=0.012):
    """a slanted stroke (its bounding box much wider than the stroke): extra points along its long edges, so the decal's
    triangles follow a curved surface instead of cutting under it (a straight stroke gets interior points anyway)"""
    if len(q) != 4:
        return q
    a = np.array(q, float)
    sides = [float(np.linalg.norm(a[(i + 1) % 4] - a[i])) for i in range(4)]
    ext = a.max(axis=0) - a.min(axis=0)
    if min(ext) < 1.5 * min(sides) or max(sides) < 2 * step:
        return q
    out = []
    for i in range(4):
        p0, p1 = a[i], a[(i + 1) % 4]
        k = max(1, int(math.ceil(sides[i] / step)))
        out += [tuple(p0 + (p1 - p0) * j / k) for j in range(k)]
    return out


def decal_polys(part, surf, polys, side, mat, lift=0.0012):
    """lay screen-space polygons on the side `side` of a surface"""
    direction = (1.0, 0.0, 0.0) if side < 0 else (-1.0, 0.0, 0.0)
    for q in polys:
        K.decal(part, surf, to_side(_dense_diagonal(q), side), 'side', mat, lift=lift, direction=direction)


def text(part, surf, s, centre, direction, height, mat, side, stroke=0.16, gap=0.28, shear=0.0, condense=1.0, lift=0.0012,
         min_seg=0.0):
    """block letters on one side; centre and direction in that side's screen coordinates"""
    quads, width = stroke_quads(s, height, stroke, gap, shear, condense, min_seg)
    decal_polys(part, surf, place(quads, centre, direction), side, mat, lift)
    return width
