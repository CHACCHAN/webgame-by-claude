"""
Details of the Supra laid on the finished shell: lamps (head, indicators, fog, side repeaters, the rear clusters in the
garnish, the high-mount stop lamp), plates, the hoop rear wing, door mirrors, wipers, door handles, the exhaust, shut
lines, and the interior seen through the glass. Left-hand parts are built once and mirrored.

Positions measured on the reference photos as noted in supra_parts; the interior is estimated (JDM, right-hand drive).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import supra_kit as K
import supra_body as BD
from supra_parts import (Frame, surface_patch, rings_of, headlamp_outline, headlamp_frame, HEAD_DEPTH, TAIL_C, TAIL_D, TAIL_E1,
                         OUTLINES)

# atlas cells of lamps.png (as supra_textures.CELLS)
CELLS = {
    'indicator_front': (0.0, 0.75, 0.5, 1.0),
    'amber': (0.5, 0.75, 1.0, 1.0),
    'reverse': (0.0, 0.5, 0.25, 0.75),
    'fog': (0.25, 0.5, 0.5, 0.75),
    'stop': (0.5, 0.5, 1.0, 0.75),
    'reflector': (0.0, 0.25, 0.5, 0.5),
    'amber_round': (0.5, 0.25, 0.75, 0.5),
}


def disc_lens(part, mat, c, n, r, dome=0.006, seg=18, uvbox=(0, 0, 1, 1), up=Vector((0, 1, 0))):
    """a round domed lens at c facing n"""
    n = Vector(n).normalized()
    a = up - n * up.dot(n)
    if a.length < 1e-4:
        a = Vector((1, 0, 0)) - n * n.x
    a.normalize()
    b = n.cross(a)
    u0, v0, u1, v1 = uvbox
    rings = [(1.0, 0.0), (0.7, dome * 0.6), (0.35, dome * 0.92)]
    rows = []
    for f, h in rings:
        rows.append([(Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r * f + n * h, (math.cos(t) * f, math.sin(t) * f))
                     for t in (2 * math.pi * k / seg for k in range(seg))])
    centre = (Vector(c) + n * dome, (0.0, 0.0))
    vs = [[part.vert(p) for p, _ in row] for row in rows]
    cv = part.vert(centre[0])
    idx = part.slot(mat)

    def uv(q):
        return (u0 + (u1 - u0) * (0.5 + 0.5 * q[1]), v0 + (v1 - v0) * (0.5 + 0.5 * q[0]))
    for k in range(len(rows)):
        for i in range(seg):
            j = (i + 1) % seg
            if k + 1 < len(rows):
                q = [vs[k][i], vs[k][j], vs[k + 1][j], vs[k + 1][i]]
                quv = [rows[k][i][1], rows[k][j][1], rows[k + 1][j][1], rows[k + 1][i][1]]
            else:
                q = [vs[k][i], vs[k][j], cv]
                quv = [rows[k][i][1], rows[k][j][1], centre[1]]
            f = part.bm.faces.new(q)
            f.material_index = idx
            f.smooth = True
            f.normal_update()
            if (K.G(f.normal)).dot(n) < 0:
                f.normal_flip()
            for loop, qq in zip(f.loops, quv if f.verts[0] == q[0] else list(reversed(quv))):
                loop[part.uv].uv = uv(qq)


def oriented_box(part, mat, c, n, along, size, bevel=0.0):
    """a box at c with its local z on n, local x along `along` (game vectors)"""
    n = Vector(n).normalized()
    ax = (Vector(along) - n * Vector(along).dot(n)).normalized()
    ay = n.cross(ax)
    rot = Matrix((ax, ay, n)).transposed()
    part.box(mat, c, size, bevel=bevel, rot=rot)


def plate(part, mats, c, n, w=0.33, h=0.165, up=Vector((0, 1, 0))):
    """a Japanese plate (330 × 165 mm): a thin slab, its face textured"""
    n = Vector(n).normalized()
    ax = up.cross(n).normalized()           # plate's right as seen from the front... (u axis)
    ay = n.cross(ax)
    t = 0.004
    pts = []
    for (u, v) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pts.append(Vector(c) + ax * u * w / 2 + ay * v * h / 2)
    front = [p + n * t for p in pts]
    part.face(front, mats['plate'], smooth=False, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], out=n)
    for i in range(4):
        j = (i + 1) % 4
        part.face([pts[i], pts[j], front[j], front[i]], mats['trim'], smooth=False,
                  out=((pts[i] + pts[j]) / 2 - Vector(c)))


# ------------------------------------------------------------------ lamps
# the unit's three lenses (u, v, radius in the lamp frame) and their circles in headlamp.png (x, y, r in pixels of
# 512 × 176): a big reflector inboard, two projectors outboard, all in the lower half of the unit
# (2026-11-10: ring centres and sizes traced on n07 and n14, carried back onto the body: lamps.py back)
HEAD_LENSES = [((-0.058, 0.002, 0.053), (117, 87, 64)), ((0.053, -0.007, 0.043), (270, 81, 52)),
               ((0.163, -0.012, 0.035), (403, 77, 43))]

LAMP_TOP = {}       # 3-D points along the head lamp's top edge (left), for the bonnet's shut line


def lamps(left, part_r, mats, bvh, bvh_cut):
    """left-hand lamps into `left` (mirrored later); the red lenses go to part_r too (left only)"""
    lm = mats['lamps']
    # head lamp: a teardrop recess in the wing top (cut in supra_parts: a dark grey housing) filled with three chrome
    # reflector bowls in thin bright bezels, a bulb shield in the inboard one, projector lenses in the others; the
    # shield and the lenses are `headlight` (they glow at night and the chrome bowls round them mirror the glow)
    fr = headlamp_frame(bvh)
    out = headlamp_outline()
    LAMP_TOP['pts'] = [fr.hit(bvh, u, v)[0] for u, v in out if v > 0.05]
    LAMP_TOP['frame'] = fr
    hl = mats['headlight']
    for k, ((u, v, r), (px, py, pr)) in enumerate(HEAD_LENSES):
        p, _n = fr.hit(bvh, u, v)
        n = fr.d
        floor = p - n * HEAD_DEPTH
        box = ((px - pr) / 512, 1 - (py + pr) / 176, (px + pr) / 512, 1 - (py - pr) / 176)
        OUTLINES[f'hl_e{k}'] = ('disc', floor + n * 0.026, n, r * 1.08)
        bowl(left, mats['chrome'], floor + n * 0.004, n, r, 0.022, box, seg=28)
        _tube(left, mats['housing'], floor + n * 0.026, n, r * 1.08, 0.09, seg=28)
        _ring(left, mats['chrome'], floor + n * 0.026, n, r * 1.08, r * 0.985, seg=28)
        if k == 0:
            disc_lens(left, hl, floor + n * 0.010, n, r * 0.40, dome=0.008, seg=20, uvbox=box)
        else:
            # projector: a clear lens in its chrome ring, a little proud of the bowl
            disc_lens(left, hl, floor + n * 0.012, n, r * 0.62, dome=0.008, seg=20, uvbox=box)
    # the black rubber seal round the unit
    rim = [(u * 1.012 + (0.003 if u > 0 else -0.003), v * 1.03 + (0.003 if v > 0 else -0.003)) for u, v in out]
    _ring_strip(left, bvh, rim, out, fr, mats['trim'], lift=0.0013)
    OUTLINES['hl'] = ('surf', fr, rim)
    # front indicator (late model): a capsule set in the top of the bumper's corner opening (supra_parts.CORNER_DUCT),
    # amber inboard, clear outboard, in a thin bright rim, a little behind the bumper face
    # (2026-11-10: the rim traced on n07 and n14, carried back onto the body: 0.19 x 0.064, 1.2 cm inboard)
    fr = Frame((0.585, 0.447, 2.0), (0.50, 0.0, 1.0), e1=(1.0, 0.0, -0.5))
    ind = K.resample(K.rounded_rect(-0.012, 0.002, 0.180, 0.054, 0.020, 6), 56, closed=True)
    ind_rim = K.resample(K.rounded_rect(-0.012, 0.002, 0.190, 0.064, 0.025, 6), 56, closed=True)
    surface_patch(left, bvh, ind, fr, lm, lift=-0.002, uvbox=CELLS['indicator_front'], n_rings=5)
    _ring_strip(left, bvh, ind_rim, ind, fr, mats['chrome'], lift=-0.0015)
    OUTLINES['ind'] = ('surf', fr, ind_rim)
    # amber side marker on the bumper's flank, side repeater on the front wing
    fr = Frame((0.86, 0.50, 1.72), (1.0, 0.0, 0.35), e1=(0.35, 0, -1))
    surface_patch(left, bvh, K.rounded_rect(0.0, 0.0, 0.085, 0.026, 0.013, 5), fr, lm, lift=0.003,
                  uvbox=CELLS['amber'])
    fr = Frame((0.88, 0.69, 0.98), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh, K.ellipse(0, 0, 0.034, 0.012, 16), fr, lm, lift=0.0025, uvbox=CELLS['amber'])
    # rear clusters: a pill-shaped unit laid flush on the tail, its clear smoked cover (the game's glass) over four round
    # lenses (inboard reverse, two red, outboard amber) in thin bright rings, a black seal round it, the outer end
    # wrapping round the corner (n05, n06, n15: the lenses nearly touch)
    # (2026-11-10: the seal and the lenses traced on n05, n06, n15 and carried back onto the body: the unit 0.126 tall,
    # lenses Ø 0.094 ~0.10 apart; n05 (square on) would have them 0.12 apart, n06 / n15 0.10: between, nearer these)
    us = (-0.172, -0.070, 0.036, 0.147)
    kinds = ('reverse', 'red', 'red', 'amber_round')
    R = 0.044
    fr = Frame(TAIL_C, TAIL_D, e1=TAIL_E1)
    house = K.resample(K.rounded_rect(-0.014, 0.0, 0.472, 0.112, 0.056, 10), 120, closed=True)
    surface_patch(left, bvh, house, fr, mats['glass'], lift=0.003, n_rings=10)
    ring = K.resample(K.rounded_rect(-0.014, 0.0, 0.486, 0.126, 0.063, 10), 120, closed=True)
    _ring_strip(left, bvh, ring, house, fr, mats['trim'], lift=0.0025)
    OUTLINES['tl'] = ('surf', fr, ring)
    for k, (u, kind) in enumerate(zip(us, kinds)):
        p, n = fr.hit(bvh, u, 0.0, strict=True)
        if p is None:
            continue
        OUTLINES[f'tl_{k}'] = ('disc', p + n * 0.004, n, R + 0.003)
        _ring(left, mats['chrome'], p + n * 0.0045, n, R + 0.003, R - 0.0005, seg=28)
        top = p + n * 0.004
        if kind == 'red':
            disc_lens(part_r, mats['taillight'], top, n, R - 0.001, dome=0.005, seg=28)
        else:
            disc_lens(left, lm, top, n, R - 0.001, dome=0.005, seg=28, uvbox=CELLS[kind])
    # the small round reflector at the inner end
    p, n = fr.hit(bvh, -0.238, -0.004, strict=True)
    if p is not None:
        disc_lens(left, mats['chrome'], p + n * 0.004, n, 0.011, dome=0.002, seg=12)
    # red reflector low on the bumper's flank
    fr = Frame((0.84, 0.50, -1.97), (1.0, 0, -0.35), e1=(0.3, 0, 1))
    surface_patch(left, bvh, K.rounded_rect(0, 0, 0.11, 0.028, 0.012, 4), fr, lm, lift=0.003, uvbox=CELLS['reflector'])


def bezel(part, mat, c, n, r, depth, seg=24):
    """a short black tube (open at the back) with a flat front ring: the raised bezel round a tail lens"""
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    ring = [(a * math.cos(t) + b * math.sin(t)) for t in (2 * math.pi * k / seg for k in range(seg))]
    back = [Vector(c) + d * r for d in ring]
    front = [Vector(c) + d * r + n * depth for d in ring]
    inner = [Vector(c) + d * (r - 0.006) + n * depth for d in ring]
    for k in range(seg):
        j = (k + 1) % seg
        part.face([back[k], back[j], front[j], front[k]], mat, smooth=True, out=ring[k])
        part.face([front[k], front[j], inner[j], inner[k]], mat, smooth=False, out=n)


def bowl(part, mat, c, n, r, depth, uvbox, seg=24):
    """a concave reflector bowl: its rim at c + n·depth (radius r), its bottom at c; faces look out along n"""
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    u0, v0, u1, v1 = uvbox
    rings = [(1.0, depth), (0.78, depth * 0.55), (0.52, depth * 0.24), (0.26, depth * 0.06)]
    rows = []
    for f, h in rings:
        rows.append([(Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r * f + n * h, (math.cos(t) * f, math.sin(t) * f))
                     for t in (2 * math.pi * k / seg for k in range(seg))])
    rows.append([(Vector(c), (0.0, 0.0))])

    def uv(q):
        return (u0 + (u1 - u0) * (0.5 + 0.5 * q[1]), v0 + (v1 - v0) * (0.5 + 0.5 * q[0]))
    for k in range(len(rows) - 1):
        for i in range(seg):
            j = (i + 1) % seg
            if len(rows[k + 1]) > 1:
                q = [rows[k][i], rows[k][j], rows[k + 1][j], rows[k + 1][i]]
            else:
                q = [rows[k][i], rows[k][j], rows[k + 1][0]]
            f = part.face([p for p, _ in q], mat, uvs=[uv(t) for _, t in q], out=n)


def _tube(part, mat, c, n, r, depth, seg=20):
    """an open tube from the circle (c, radius r, square to n) back along -n by depth, faces outwards"""
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    ring = [(a * math.cos(t) + b * math.sin(t)) for t in (2 * math.pi * k / seg for k in range(seg))]
    for k in range(seg):
        j = (k + 1) % seg
        q = [Vector(c) + ring[k] * r, Vector(c) + ring[j] * r, Vector(c) + ring[j] * r - n * depth,
             Vector(c) + ring[k] * r - n * depth]
        part.face(q, mat, smooth=True, out=ring[k])


def _disc(part, mat, c, n, r, seg=20):
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    pts = [Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r for t in (2 * math.pi * k / seg for k in range(seg))]
    part.face(pts, mat, smooth=False, out=n)


def _ring(part, mat, c, n, r0, r1, seg=20):
    n = Vector(n).normalized()
    a = Vector((0, 1, 0)) - n * n.y
    a.normalize()
    b = n.cross(a)
    for k in range(seg):
        t0, t1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        q = [Vector(c) + (a * math.cos(t) + b * math.sin(t)) * r for t, r in ((t0, r0), (t1, r0), (t1, r1), (t0, r1))]
        part.face(q, mat, smooth=False, out=n)


def _ring_strip(part, bvh, outer, inner, fr, mat, lift):
    """a band on the surface between two outlines with the same point count"""
    o = [fr.hit(bvh, u, v) for u, v in outer]
    i = [fr.hit(bvh, u, v) for u, v in inner]
    n = len(outer)
    for k in range(n):
        j = (k + 1) % n
        q = [o[k][0] + o[k][1] * lift, o[j][0] + o[j][1] * lift, i[j][0] + i[j][1] * lift, i[k][0] + i[k][1] * lift]
        part.face(q, mat, smooth=True, out=o[k][1])


def emblem(part, mats, bvh, fr, w):
    """an oval badge w wide: an outer oval ring, a wide flat oval in its upper half and a narrow upright oval across
    both (thin chrome rings laid on the surface)"""
    a = w / 2
    t = 0.085 * a
    for k, (cx, cy, ra, rb) in enumerate(((0.0, 0.0, a, 0.68 * a), (0.0, 0.22 * a, 0.70 * a, 0.30 * a),
                                          (0.0, -0.10 * a, 0.25 * a, 0.56 * a))):
        outer = K.ellipse(cx, cy, ra, rb, 40)
        inner = K.ellipse(cx, cy, ra - t, rb - t, 40)
        _ring_strip(part, bvh, outer, inner, fr, mats['chrome'], lift=0.003 + 0.0005 * k)


# ------------------------------------------------------------------ wing
# the factory wing (late RZ): one blade of constant chord across the deck lid that turns down at its ends, in rounded
# corners, into two thin swept uprights standing on the lid's outer edges, with a clear gap under the blade. Measured
# on the photos with their solved cameras (rays onto the uprights' planes; outlines in fitdata/supra/wing.json, scored
# by lampscore.py on the wing pass of lamps.py), in the finished car's frame: the wing is built after the FFD as a
# rigid part (the field twisted it) and its feet go down into the fitted lid.
#   blade: chord line LE / TE heights at the centre and its drop to the corners, LE / TE z, thickness (n01 side view,
#          n06 / n15 edge-on, n05 from behind)
#   uprights: the trailing edge's x at the corner's foot and at the deck; the toe-out (the leading edge swung outboard
#          about the trailing edge, growing from the corner to toe_deg at the deck: n06 sees the far upright edge-on, n05
#          sees thin posts, and it reconciles the leading edge seen from outside (n06, n15) with n01's), thickness,
#          corner radius of the mid-line; leading / trailing edge z by height
#   (span, height and corner radius settled between the outlines and the silhouettes: n05's GrabCut silhouette wants
#    the corners rounder and lower than the traced n06 / n15 outlines, whose far uprights sit outboard of the near
#    ones' fit; 2026-11-10)
WING = dict(y_le=1.118, y_te=1.124, sag=0.010, z_le=-2.040, z_te=-2.245, tb=0.028,
            x_top=0.545, x_foot=0.550, toe_deg=8.0, tu=0.026, rc=0.15,
            le=((1.115, -2.040), (1.07, -1.975), (1.02, -1.895), (0.96, -1.790), (0.91, -1.640), (0.885, -1.585)),
            te=((1.13, -2.245), (1.10, -2.215), (1.06, -2.150), (1.01, -2.120), (0.94, -2.078), (0.87, -2.030)))


def _profile(table):
    """a smooth edge z(y) through the measured (y, z) pairs (y falling), clamped at the ends"""
    dense = K.catmull([(y, z) for y, z in table], 60, closed=False)
    ys = [p[0] for p in dense][::-1]
    zs = [p[1] for p in dense][::-1]

    def f(y):
        if y <= ys[0]:
            return zs[0]
        if y >= ys[-1]:
            return zs[-1]
        for k in range(len(ys) - 1):
            if ys[k] <= y <= ys[k + 1]:
                t = (y - ys[k]) / max(ys[k + 1] - ys[k], 1e-9)
                return zs[k] + (zs[k + 1] - zs[k]) * t
        return zs[-1]
    return f


def _half_thickness(u):
    """NACA 00xx half thickness per unit thickness (closed, crisp trailing edge)"""
    return 5.0 * (0.2969 * math.sqrt(u) - 0.1260 * u - 0.3516 * u * u + 0.2843 * u ** 3 - 0.1036 * u ** 4)


def wing(part, mats, bvh):
    """the wing's left half (mirrored): one aerofoil section swept along the hoop (blade across, corner, upright down
    into the lid) in a frame that turns with the path (thickness along the path's normal, chord fore and aft), so
    the surface carries no twist; the chord and thickness change only through the corner and down the uprights"""
    W = WING
    le_up, te_up = _profile(W['le']), _profile(W['te'])
    xb = W['x_top'] - W['rc']                       # the blade's straight part ends here
    yb_end = W['y_le'] - W['sag']
    yc = yb_end - W['rc']                           # corner centre height
    # the lid under the feet (fitted shell): the uprights go 3 cm below its lowest point there
    deck = []
    for z in (-1.56, -1.70, -1.85, -2.0, -2.06):
        p, _ = K.project(bvh, (W['x_foot'], 1.2, z), (0, 1, 0), back=0.5)
        if p is not None:
            deck.append(p.y)
    y_bot = (min(deck) if deck else 0.86) - 0.03
    path = []                                       # (x, y, w) w: 0 blade .. 1 upright
    for k in range(18):
        x = xb * k / 17
        path.append((x, W['y_le'] - W['sag'] * (x / xb) ** 2, 0.0))
    for k in range(1, 17):
        a = math.radians(90 - 90 * k / 16)
        t = k / 16
        path.append((xb + W['rc'] * math.cos(a), yc + W['rc'] * math.sin(a), t * t * (3 - 2 * t)))
    y_top = yc
    n_up = 30
    def toe(y):
        return math.radians(W['toe_deg']) * max(0.0, min(1.0, (y_top - y) / (y_top - 0.88)))
    for k in range(1, n_up + 1):
        t = k / n_up
        t = 1 - (1 - t) ** 1.6                      # denser towards the foot, where the edges sweep
        y = y_top + (y_bot - y_top) * t
        x_te = W['x_top'] + (W['x_foot'] - W['x_top']) * (y_top - y) / (y_top - y_bot)
        chord = abs(te_up(y) - le_up(y))
        path.append((x_te + chord * math.tan(toe(y)), y, 1.0))
    M = 14
    us = [0.5 * (1 - math.cos(math.pi * k / (M - 1))) for k in range(M)]
    rows = []
    for i, (x, y, w) in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(len(path) - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty)
        nx, ny = -ty / ln, tx / ln                  # blade: +y, upright: +x (outwards)
        zl = W['z_le'] + (le_up(y) - W['z_le']) * w
        zt = W['z_te'] + (te_up(y) - W['z_te']) * w
        th = W['tb'] + (W['tu'] - W['tb']) * w
        # the TE's offset along the normal: the blade's angle of attack, the uprights' toe (LE out)
        tilt = (W['y_te'] - W['y_le']) * (1 - w) - abs(zt - zl) * math.tan(toe(y)) * w
        ring = []
        for u in us:                                # outer / upper surface, LE -> TE
            off = th * _half_thickness(u) + 0.004 * math.sin(math.pi * u) + tilt * u
            ring.append((x + nx * off, y + ny * off, zl + (zt - zl) * u))
        for u in reversed(us[1:-1]):                # inner / lower surface, TE -> LE
            off = -th * _half_thickness(u) + 0.004 * math.sin(math.pi * u) + tilt * u
            ring.append((x + nx * off, y + ny * off, zl + (zt - zl) * u))
        rows.append(ring)
    left = K.Part('wingL')
    left.grid(rows, mats['paint'], closed=True)
    left.bm.normal_update()
    # one orientation for the whole tube: the blade's upper surface faces up
    f0 = max(left.bm.faces, key=lambda f: K.G(f.calc_center_median()).y if K.G(f.calc_center_median()).x < 0.1 else -9)
    if K.G(f0.normal).y < 0:
        for f in left.bm.faces:
            f.normal_flip()
    part.absorb(left)
    part.absorb(left, mirror=True)


def build_wing(body, mats, shell, count):
    """the wing and the rear shut lines on the finished (fitted) body: rigid parts, not moved by the FFD"""
    bvh = K.bvh_of(shell)
    wp = K.Part('wing')
    wing(wp, mats, bvh)
    count['wing'] = wp.tris()
    wp.build(body)
    sp = K.Part('rear_seams')
    rear_seams(sp, mats, bvh)
    count['rear_seams'] = sp.tris()
    sp.build(body)


def seam(part, bvh, ctrl, mat, width=0.005, lift=0.0016, step=0.008):
    """a shut line through game points near the finished surface: a smooth curve through them, resampled every
    `step`, each sample pulled onto the surface (nearest point) and lifted along its normal; the strip's sides lie
    in the surface, so the line runs unbroken over the curved panels"""
    ln = sum((Vector(b) - Vector(a)).length for a, b in zip(ctrl, ctrl[1:]))
    dense = K.catmull([tuple(c) for c in ctrl], max(6, int(ln / step)), closed=False)
    hits = []
    for q in dense:
        loc, nrm, _, _ = bvh.find_nearest(K.B(*q))
        if loc is None:
            continue
        hits.append((K.G(loc), (K.G(nrm) - K.G(Vector((0, 0, 0)))).normalized()))
    prev = None
    for i, (p, n) in enumerate(hits):
        a = hits[max(0, i - 1)][0]
        b = hits[min(len(hits) - 1, i + 1)][0]
        t = (b - a).normalized()
        sd = t.cross(n).normalized() * (width / 2)
        q = (part.vert(p + sd + n * lift), part.vert(p - sd + n * lift))
        if prev is not None:
            f = part.face([prev[0], q[0], q[1], prev[1]], mat)
        prev = q


# the hatch's and the bumper's shut lines at the rear quarters (left; mirrored), traced on n06 and n15 and carried
# onto the finished body by their cameras' rays (2026-11-10): the hatch's side edge running back along the deck under
# the wing's foot down onto the top of the lamp unit, and the bumper's joint from the unit's outer end straight down
# its corner. The photos show no gap along the bumper's top under the lamps (that line is a fold, not a joint).
HATCH_SIDE = ((0.618, 0.93, -1.42), (0.635, 0.895, -1.58), (0.635, 0.873, -1.75), (0.612, 0.862, -1.90),
              (0.585, 0.853, -1.99), (0.567, 0.845, -2.035), (0.565, 0.828, -2.062))
QUARTER = ((0.662, 0.752, -2.036), (0.680, 0.744, -2.026), (0.697, 0.721, -2.016), (0.713, 0.681, -2.010),
           (0.720, 0.624, -2.009), (0.725, 0.543, -2.008), (0.727, 0.461, -2.004), (0.724, 0.375, -1.995))


def rear_seams(part, mats, bvh):
    g = mats['grille']
    for s in (1, -1):
        for line in (HATCH_SIDE, QUARTER):
            seam(part, bvh, [(x * s, y, z) for x, y, z in line], g)
    # the hatch's lower edge across the centre panel, between the lamps' inner ends at the lenses' height
    ctrl = []
    for k in range(7):
        x = -0.176 + 0.352 * k / 6
        p, _ = K.project(bvh, (x, 0.757, -2.0), (0, 0, -1), back=0.7)
        if p is not None:
            ctrl.append(tuple(p))
    seam(part, bvh, ctrl, g)


# ------------------------------------------------------------------ mirrors, wipers, handles, exhaust
def mirror(left, mats, bvh):
    """door mirror: a rounded housing wider than it is tall, its glass on the back, on an arm rising from the door's
    front corner (size and height measured on n06, n07 and n14: ~0.19 wide, 0.125 tall, its centre at 0.91)"""
    m = mats['paint']
    x0, x1 = 0.835, 1.020               # root (on the arm) -> outer tip
    yc, zc = 0.910, 0.300
    H, DF, DR = 0.125, 0.062, 0.034     # height; depth ahead of / behind the glass plane
    n, seg = 9, 16
    rows = []
    for k in range(n + 1):
        t = k / n
        prof = math.sqrt(max(0.0, 1 - ((t - 0.5) / 0.5) ** 2)) if t > 0.5 else 1.0
        prof = max(prof, 0.18)
        h = 0.5 * H * (0.94 + 0.06 * (1 - t)) * prof ** 0.55
        row = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            ca, sa = math.cos(a), math.sin(a)
            dz = (DF if ca > 0 else DR) * prof ** 0.45
            e = 2.0 if ca > 0 else 4.0          # round front, flat back
            row.append((x0 + (x1 - x0) * t, yc + h * math.copysign(abs(sa) ** (2 / 3.0), sa),
                        zc + dz * math.copysign(abs(ca) ** (2 / e), ca)))
        rows.append(row)
    p = K.Part('mirror')
    vs = p.grid(rows, m, closed=True)
    for ring, xe in ((vs[0], x0), (vs[-1], x1)):
        ctr = p.bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
        for j in range(seg):
            f = p.bm.faces.new([ring[j], ring[(j + 1) % seg], ctr])
            f.material_index = p.slot(m)
            f.smooth = True
    bmesh.ops.recalc_face_normals(p.bm, faces=p.bm.faces)
    left.absorb(p)
    # the glass: a thin bevelled plate set into the housing's flat back
    left.box(mats['chrome'], ((x0 + x1) / 2 + 0.008, yc, zc - DR + 0.001), ((x1 - x0) * 0.80, H * 0.76, 0.006),
             bevel=0.002)
    # the arm: it rises from the door skin below the window line (n07, n14: its foot ~5 cm under the housing) up and
    # out into the housing's inner end
    a, b = Vector((0.790, 0.790, 0.300)), Vector((0.875, 0.880, 0.300))
    d = b - a
    left.box(mats['paint'], (a + b) / 2, (d.length + 0.02, 0.036, 0.055), bevel=0.014, rot=_rot_along(d))


def wipers(part, mats, bvh):
    for x0, x1 in ((-0.50, 0.10), (0.06, 0.58)):
        pts = []
        for k in range(9):
            x = x0 + (x1 - x0) * k / 8
            zb = 0.585 - 0.12 * (abs(x) / 0.62) ** 2.2
            p, n = K.project(bvh, (x, 1.0, zb - 0.03), (0, 1, 0.35), back=1.0)
            if p is not None:
                pts.append(p + n * 0.012)
        for a, b in zip(pts, pts[1:]):
            d = b - a
            part.box(mats['trim'], (a + b) / 2, (d.length + 0.004, 0.012, 0.022), rot=_rot_along(d))


def _rot_along(d):
    x = d.normalized()
    up = Vector((0, 1, 0))
    z = x.cross(up).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def sail(left, mats, bvh):
    """the black sail at the door glass's front corner (the mirror's base), filling the foot of the A-pillar"""
    d = Vector((1.0, 0.55, 0.0)).normalized()
    outline = [(0.345, 0.888), (0.300, 0.912), (0.255, 0.948), (0.232, 0.968), (0.330, 0.945), (0.440, 0.910),
               (0.530, 0.886), (0.440, 0.884)]
    pts = []
    for z, y in K.catmull(outline, 24):
        p, n = K.project(bvh, (0.75, y, z), d, back=0.6)
        if p is None:
            return
        pts.append((p, n))
    c = sum((p for p, _ in pts), Vector()) / len(pts)
    cp, cn = K.project(bvh, c, d, back=0.6)
    if cp is None:
        return
    cv = left.vert(cp + cn * 0.003)
    ring = [left.vert(p + n * 0.003) for p, n in pts]
    for k in range(len(ring)):
        f = left.face([ring[k], ring[(k + 1) % len(ring)], cv], mats['trim'])
        if f is not None:
            f.normal_update()
            if K.G(f.normal).dot(cn) < 0:
                f.normal_flip()


def scoop_slot(left, mats, bvh_cut):
    """the dark slot at the rear end of the side scoop, ahead of the rear wheel"""
    fr = Frame((0.88, 0.44, -0.50), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh_cut, K.rounded_rect(0.225, -0.008, 0.055, 0.105, 0.026, 5), fr, mats['grille'], lift=0.002,
                  n_rings=2)


def handle(left, mats, bvh):
    fr = Frame((0.86, 0.795, -0.54), (1, 0, 0), e1=(0, 0, -1))
    surface_patch(left, bvh, K.rounded_rect(0, 0, 0.20, 0.042, 0.02, 4), fr, mats['trim'], lift=0.0015, n_rings=2)
    p, n = fr.hit(bvh, 0.0, 0.004)
    oriented_box(left, mats['paint'], p + n * 0.012, n, (0, 0, -1), (0.19, 0.026, 0.016), bevel=0.007)


def exhaust(mats):
    p = K.Part('exhaust')
    c = (0.52, 0.255, -2.12)
    p.cylinder(mats['chrome'], c, 0.048, 0.20, axis='z', seg=20, cap=False)
    p.cylinder(mats['under'], (c[0], c[1], c[2] - 0.06), 0.040, 0.004, axis='z', seg=20, cap=True)
    p.cylinder(mats['chrome'], (c[0], c[1], c[2] + 0.02), 0.045, 0.16, axis='z', seg=20, cap=False)
    # the pipe's inside faces inwards
    return p


def strip3d(part, bvh, pts, d, width, mat, lift=0.0015, back=0.3):
    """a shut line through game points, each dropped onto the surface along -d"""
    hits = []
    for q in pts:
        p, n = K.project(bvh, q, d, back=back)
        hits.append((p, n))
    prev = None
    for i, (p, n) in enumerate(hits):
        if p is None:
            prev = None
            continue
        a = hits[max(0, i - 1)][0] or p
        b = hits[min(len(hits) - 1, i + 1)][0] or p
        t = (b - a).normalized()
        sd = t.cross(n).normalized() * (width / 2)
        q = (part.vert(p + sd + n * lift), part.vert(p - sd + n * lift))
        if prev is not None:
            f = part.face([prev[0], q[0], q[1], prev[1]], mat)
            if f is not None and K.G(f.normal).dot(n) < 0:
                f.normal_flip()
        prev = q


def shut_lines(part, mats, bvh):
    from supra_parts import strip
    g = mats['grille']
    w = 0.006
    for s in (1, -1):
        fr = Frame((1.3 * s, 0.6, 0.0), (s, 0, 0), e1=(0, 0, -s))
        sgn = -s

        def zz(z):
            return z * sgn
        # door: front edge, bottom, rear edge (side view, z, y)
        door = [(0.50, 0.875), (0.49, 0.80), (0.475, 0.62), (0.47, 0.45), (0.455, 0.33), (0.43, 0.30)]
        door_b = [(0.43, 0.300), (0.0, 0.296), (-0.40, 0.296), (-0.60, 0.300)]
        door_r = [(-0.60, 0.300), (-0.675, 0.40), (-0.715, 0.55), (-0.73, 0.70), (-0.715, 0.82), (-0.68, 0.90), (-0.645, 0.925)]
        for line in (door, door_b, door_r):
            dense = K.catmull(line, 22, closed=False)
            strip(part, bvh, [(zz(z), y) for z, y in dense], fr, w, g)
        if s < 0:
            # fuel lid on the right rear quarter
            lid = [(zz(z), y) for z, y in K.rounded_rect(-1.62, 0.80, 0.17, 0.115, 0.03, 4)]
            strip(part, bvh, lid + lid[:1], fr, w, g)
    # bonnet: its sides along the wing crests from the windscreen to the head lamps' outer ends, its front edge across
    # the nose between the lamps' inner ends (the lamps' own seals close the line)
    fr = Frame((0.0, 1.6, 0.0), (0, 1, 0), e1=(1, 0, 0))
    top = LAMP_TOP['pts']
    outer = max(top, key=lambda p: p.x)
    inner = min(top, key=lambda p: p.x)
    for s in (1, -1):
        crest = [(0.600, 0.66), (0.625, 1.00), (0.660, 1.32), (0.700, 1.58), (outer.x - 0.012, outer.z - 0.02)]
        strip(part, bvh, [(x * s, -z) for x, z in K.catmull(crest, 30, closed=False)], fr, w, g)
    front = []
    for k in range(25):
        x = inner.x * (-1 + 2 * k / 24)
        front.append(Vector((x, inner.y + 0.006, inner.z + 0.035 * (1 - (x / inner.x) ** 2))))
    strip3d(part, bvh, front, (0, 0.55, 1.0), w, g)
    # the bumper's seam from each lamp's outer end down to the wheel arch
    for s in (1, -1):
        seam = [Vector((outer.x - 0.005, outer.y - 0.03, outer.z - 0.01)), Vector((outer.x + 0.04, 0.60, outer.z - 0.05)),
                Vector((0.88, 0.57, 1.66)), Vector((0.89, 0.55, 1.62))]
        strip3d(part, bvh, [Vector((p[0] * s, p[1], p[2])) for p in K.catmull(seam, 12, closed=False)], (s, 0.3, 0.3), w, g)


# ------------------------------------------------------------------ interior (RHD)
def interior(part, mats):
    it, tr = mats['interior'], mats['trim']
    # floor, door cards below the lining, the luggage deck and its back wall
    part.face([(-0.78, 0.21, -1.0), (0.78, 0.21, -1.0), (0.78, 0.21, 0.70), (-0.78, 0.21, 0.70)], it, smooth=False, out=(0, 1, 0))
    for s in (1, -1):
        part.face([(0.80 * s, 0.21, -0.95), (0.80 * s, 0.21, 0.62), (0.80 * s, 0.55, 0.62), (0.80 * s, 0.55, -0.95)], it,
                  smooth=False, out=(-s, 0, 0))
    part.face([(-0.70, 0.66, -1.98), (0.70, 0.66, -1.98), (0.70, 0.66, -1.0), (-0.70, 0.66, -1.0)], it, smooth=False, out=(0, 1, 0))
    part.face([(-0.70, 0.66, -1.0), (0.70, 0.66, -1.0), (0.70, 0.21, -1.0), (-0.70, 0.21, -1.0)], it, smooth=False, out=(0, 0, 1))
    part.face([(-0.55, 0.42, -1.95), (0.55, 0.42, -1.95), (0.55, 0.78, -1.95), (-0.55, 0.78, -1.95)], it, smooth=False, out=(0, 0, 1))
    # dash: a rounded slab under the windscreen, the meter hood on the right (driver), centre stack
    part.box(it, (0.0, 0.765, 0.43), (1.30, 0.15, 0.32), bevel=0.05, seg=2)
    part.box(it, (-0.37, 0.86, 0.30), (0.40, 0.07, 0.18), bevel=0.03, seg=2)
    part.box(tr, (-0.37, 0.82, 0.215), (0.30, 0.07, 0.012))
    part.box(it, (0.0, 0.52, 0.30), (0.26, 0.42, 0.32), bevel=0.03, seg=1)
    part.box(it, (0.0, 0.33, -0.15), (0.22, 0.24, 0.62), bevel=0.03, seg=1)
    part.cylinder(tr, (0.0, 0.50, -0.05), 0.012, 0.12, axis='y', seg=8)
    part.cylinder(tr, (0.0, 0.57, -0.05), 0.022, 0.03, axis='y', seg=10)
    # steering wheel (right), tilted toward the driver
    sw = K.Part('sw')
    rot = Matrix.Rotation(math.radians(-22), 4, 'X')
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=0.185, segments=24)
    ring = [v.co.copy() for v in bm.verts]
    bm.free()
    tube = []
    for k in range(25):
        a = 2 * math.pi * k / 24
        cc = Vector((0, 0.185 * math.sin(a), 0.185 * math.cos(a)))
        rr = []
        for j in range(6):
            b = 2 * math.pi * j / 6
            rad = Vector((0, math.sin(a), math.cos(a)))
            rr.append(cc + rad * 0.016 * math.cos(b) + Vector((0.016 * math.sin(b), 0, 0)))
        tube.append(rr)
    centre = Vector((-0.37, 0.86, 0.16))
    rows = []
    for rr in tube:
        rows.append([tuple(centre + _tilt(p)) for p in rr])
    sw.grid(rows, tr, closed=True)
    for a in (math.radians(90), math.radians(270), math.radians(180)):
        p0 = centre + _tilt(Vector((0, 0.0, 0.0)))
        p1 = centre + _tilt(Vector((0, 0.18 * math.sin(a), 0.18 * math.cos(a))))
        d = p1 - p0
        sw.box(tr, (p0 + p1) / 2, (0.05, 0.016, d.length), rot=_rot_z_along(d))
    sw.cylinder(tr, tuple(centre + _tilt(Vector((0.0, 0, 0)))), 0.05, 0.05, axis='x', seg=12)
    bmesh.ops.recalc_face_normals(sw.bm, faces=sw.bm.faces)
    part.absorb(sw)
    part.cylinder(tr, tuple(centre + Vector((0, -0.03, 0.12))), 0.03, 0.22, axis='z', seg=8)
    # seats: shell buckets with bolsters and head rests; small rear seats
    for x in (-0.37, 0.37):
        part.box(it, (x, 0.33, -0.25), (0.48, 0.12, 0.50), bevel=0.04, seg=2)
        for bx in (-0.21, 0.21):
            part.box(it, (x + bx, 0.40, -0.25), (0.07, 0.08, 0.46), bevel=0.03, seg=1)
        back = Matrix.Rotation(math.radians(-16), 3, 'X')
        part.box(it, (x, 0.66, -0.56), (0.48, 0.58, 0.12), bevel=0.04, seg=2, rot=back)
        for bx in (-0.22, 0.22):
            part.box(it, (x + bx, 0.62, -0.53), (0.07, 0.42, 0.16), bevel=0.03, seg=1, rot=back)
        part.box(it, (x, 1.03, -0.66), (0.26, 0.16, 0.10), bevel=0.04, seg=2, rot=back)
        part.box(it, (x * 0.95, 0.40, -1.00), (0.44, 0.10, 0.36), bevel=0.04, seg=1)
        part.box(it, (x * 0.95, 0.62, -1.20), (0.44, 0.44, 0.10), bevel=0.04, seg=1,
                 rot=Matrix.Rotation(math.radians(-30), 3, 'X'))


def _tilt(p):
    # the wheel's plane faces the driver (−z), leaning back at the top
    v = Vector((p.z, p.y, p.x))          # ring in the x-y plane
    return Matrix.Rotation(math.radians(24), 3, 'X') @ v


def _rot_z_along(d):
    z = d.normalized()
    up = Vector((0, 0, 1)) if abs(z.z) < 0.9 else Vector((1, 0, 0))
    x = up.cross(z).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def build(body, mats, bvh, bvh_cut, count):
    left = K.Part('detailsL')
    red = K.Part('taillamps')
    lamps(left, red, mats, bvh, bvh_cut)
    mirror(left, mats, bvh)
    sail(left, mats, bvh)
    scoop_slot(left, mats, bvh_cut)
    handle(left, mats, bvh)
    det = K.Part('details')
    det.absorb(left)
    det.absorb(left, mirror=True)
    red_all = K.Part('taillights')
    red_all.absorb(red)
    red_all.absorb(red, mirror=True)
    # high-mount stop lamp: a long thin bar on the tail panel above the emblem, in a dark surround (n05, n06, n15
    # triangulated: centre height 0.89, 0.30 x 0.036 with the surround)
    fr = Frame((0.0, 0.89, -2.15), (0, 0.30, -1.0), e1=(-1, 0, 0))
    hm = K.resample(K.rounded_rect(0, 0, 0.28, 0.020, 0.010, 4), 72, closed=True)
    surface_patch(det, bvh, hm, fr, mats['lamps'], lift=0.003, n_rings=3, uvbox=CELLS['stop'])
    _ring_strip(det, bvh, K.resample(K.rounded_rect(0, 0, 0.30, 0.036, 0.018, 4), 72, closed=True), hm, fr, mats['trim'],
                lift=0.0025)
    # the maker's oval badges (our own simple drawing): on the nose under the bonnet's edge (n07, n14) and on the tail
    # panel between the lamps (n05, n06, n15)
    emblem(det, mats, bvh, Frame((0.0, 0.61, 2.08), (0, 0.25, 1.0), e1=(1, 0, 0)), 0.090)
    emblem(det, mats, bvh, Frame((0.0, 0.815, -2.20), (0, 0.15, -1.0), e1=(-1, 0, 0)), 0.082)
    # plates: front on the bumper above the intake (offset to the right), rear in its recess
    # (the centre line is the shell's weld seam at the ends: the normal is taken square to the car, x dropped)
    p, n = K.project(bvh, (0.0, 0.440, 2.0), (0, 0, 1), back=0.6)
    n = Vector((0.0, n.y, n.z)).normalized()
    plate(det, mats, p + n * 0.006, n)
    p, n = K.project(bvh_cut, (0.0, 0.56, -2.1), (0, 0, -1), back=0.6)
    n = Vector((0.0, n.y, n.z)).normalized()
    plate(det, mats, p + n * 0.004, n)
    # the mouth: one slim body-coloured bar across it, a little inside the opening, black mesh behind
    # (n07: at half the opening's height, a little inside the lip)
    for y in (0.352,):
        pts = []
        for k in range(15):
            x = -0.37 + 0.74 * k / 14
            p, n = K.project(bvh, (x, y, 2.0), (0, 0, 1), back=0.6)
            if p is not None:
                pts.append(Vector((x, y, p.z - 0.022)))
        for a, b in zip(pts, pts[1:]):
            dd = b - a
            det.box(mats['paint'], (a + b) / 2, (dd.length + 0.004, 0.010, 0.018), rot=_rot_along(dd))
    wipers(det, mats, bvh)
    shut_lines(det, mats, bvh_cut)
    inter = K.Part('interior')
    interior(inter, mats)
    ex = exhaust(mats)
    for p in (det, red_all, inter, ex):
        count[p.name] = p.tris()
        p.build(body)
