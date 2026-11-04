"""
Fittings cut into or laid on the R34's body: front grille / intake / ducts and the bonnet vent (boolean cutters whose
walls and backs bring their own materials), headlamps and indicators (lenses laid on the nose by ray casts), the
round tail lamps, plates, reverse and fog lamps, the V-spec chin spoiler and rear diffuser, the tailpipe.

Positions (head-on and tail-on photos scaled from the 1,785 mm width; list in the scratch dir): headlamps |x| 0.46 ..
0.84, y 0.64 .. 0.74; grille |x| <= 0.43, y 0.62 .. 0.70; lower intake |x| <= 0.45, y 0.21 .. 0.43; tail lamps: outer
dia 0.204 at |x| 0.72, inner dia 0.166 at |x| 0.51, centres y 0.845.
"""
import math

import bmesh
import numpy as np

import r34_kit as K
import r34_shell as SH

AX = {'x': 0, 'y': 1, 'z': 2}


# ---------------------------------------------------------------- outlines


def rounded_poly(pts, r, seg=4):
    """a closed polygon [(u, v)] with rounded corners (radius r, at most 45 % of the shorter neighbour edge)"""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = (np.array(pts[k % n], float) for k in (i - 1, i, i + 1))
        a, b = p0 - p1, p2 - p1
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        rr = min(r, la * 0.45, lb * 0.45)
        if rr < 1e-5:
            out.append(tuple(p1))
            continue
        q0, q2 = p1 + a / la * rr, p1 + b / lb * rr
        for k in range(seg + 1):
            t = k / seg
            out.append(tuple((1 - t) ** 2 * q0 + 2 * t * (1 - t) * p1 + t * t * q2))
    return out


def resample(poly, n):
    P = np.array(list(poly) + [poly[0]], float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for k in range(n):
        s = L[-1] * k / n
        i = int(np.clip(np.searchsorted(L, s, side='right') - 1, 0, len(seg) - 1))
        t = (s - L[i]) / max(seg[i], 1e-9)
        out.append(tuple(P[i] + (P[i + 1] - P[i]) * t))
    return out


def mirror_u(poly):
    return [(-u, v) for u, v in reversed(poly)]


def dedupe(poly):
    out = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def lift3(axis, u, v, a):
    """(u, v) in the view plane of `axis` + the coordinate a along it -> game point"""
    if axis == 'z':
        return (u, v, a)
    if axis == 'x':
        return (a, v, u)
    return (u, a, v)


def fix(f, want):
    """turn a face to face `want` (game frame)"""
    if f is None:
        return
    f.normal_update()
    if np.dot(np.array(K.G(f.normal)), want) < 0:
        f.normal_flip()


class Surface:
    """ray casts onto a body mesh (game frame)"""

    def __init__(self, obj):
        self.bvh = K.bvh_of(obj)

    def onto(self, u, v, axis, side, lift=0.0, far=4.0):
        """the surface point seen at (u, v) looking along -side*axis; lifted along the normal (towards the viewer)"""
        o = lift3(axis, u, v, side * far)
        d = [0.0, 0.0, 0.0]
        d[AX[axis]] = -side
        loc, nrm, _, _ = self.bvh.ray_cast(K.B(*o), K.B(*d))
        if loc is None:
            return None
        p, n = np.array(K.G(loc)), np.array(K.G(nrm))
        if np.dot(n, d) > 0:
            n = -n
        return p + n * lift


def patch(part, surf, poly, axis, side, mat, lift=0.002, rings=3, uv_box=None, centre=None):
    """a lens / plate laid on the surface over the closed outline `poly`: concentric rings towards the centre"""
    poly = np.array(poly, float)
    c = np.array(centre if centre is not None else poly.mean(axis=0))
    grid = [[c + (p - c) * (k / rings) for p in poly] for k in range(rings, 0, -1)]
    P = [[surf.onto(q[0], q[1], axis, side, lift) for q in ring] for ring in grid]
    cp = surf.onto(c[0], c[1], axis, side, lift)
    u0, v0, u1, v1 = uv_box if uv_box is not None else (*poly.min(axis=0), *poly.max(axis=0))
    uvf = lambda q: ((q[0] - u0) / (u1 - u0), (q[1] - v0) / (v1 - v0))
    want = np.zeros(3)
    want[AX[axis]] = side
    n = len(poly)
    for j in range(rings):
        for i in range(n):
            i2 = (i + 1) % n
            if j + 1 < rings:
                q = [P[j][i], P[j][i2], P[j + 1][i2], P[j + 1][i]]
                uv = [uvf(grid[j][i]), uvf(grid[j][i2]), uvf(grid[j + 1][i2]), uvf(grid[j + 1][i])]
            else:
                q = [P[j][i], P[j][i2], cp]
                uv = [uvf(grid[j][i]), uvf(grid[j][i2]), uvf(c)]
            if any(p is None for p in q):
                continue
            fix(part.face([tuple(p) for p in q], mat, smooth=True, uvs=uv), want)


def prism(mats, poly, axis, a0, a1, back='grille', wall='trim', tile=0.14):
    """
    A boolean cutter: the outline extruded along `axis` from a0 (inside the body) to a1 (outside). Cut with
    material transfer, its sides become the opening's walls (`wall`) and the a0 cap its back (`back`, UVs tiled).
    """
    part = K.Part('cutter')
    poly = list(poly)
    lo = np.array(poly).min(axis=0)
    p0 = [lift3(axis, u, v, a0) for u, v in poly]
    p1 = [lift3(axis, u, v, a1) for u, v in poly]
    part.face(p0, back, smooth=False, uvs=[((u - lo[0]) / tile, (v - lo[1]) / tile) for u, v in poly])
    part.face(p1[::-1], wall, smooth=False)
    n = len(poly)
    for i in range(n):
        i2 = (i + 1) % n
        part.face([p0[i], p1[i], p1[i2], p0[i2]], wall, smooth=False)
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(mats, merge_dist=0)


def inset_quad(q, l=0.0, r=0.0, b=0.0, t=0.0):
    """a quad [(lower left), (lower right), (upper right), (upper left)] with its sides moved inwards"""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    return [(x0 + l, y0 + b), (x1 - r, y1 + b), (x2 - r, y2 - t), (x3 + l, y3 - t)]


def bevel_cutter(mats, surf, outer, inner, axis, side, depth, back_a, bevel='paint', wall='trim', back='grille',
                 tile=0.14):
    """
    A boolean cutter for an opening with chamfered edges: at the body surface the outline is `outer`, sloping in to
    `inner` (same vertex count and order) `depth` below the surface (chamfer faces: `bevel`), then straight walls
    (`wall`) to the back at the coordinate `back_a` along `axis` (cap: `back`). The surface is found by ray casts
    (`surf`, the uncut body), so the chamfer starts exactly on it.
    """
    outer, inner = np.array(outer, float), np.array(inner, float)
    k = AX[axis]
    zs = []
    for u, v in outer:
        hit = surf.onto(u, v, axis, side)
        zs.append(hit[k] if hit is not None else np.nan)
    zs = np.array(zs)
    zs = np.where(np.isnan(zs), np.nanmax(zs * side) * side, zs)
    ext = outer + (outer - inner) * (0.012 / depth)            # the chamfer carried on 12 mm outside the surface
    rings = [[lift3(axis, u, v, back_a) for u, v in inner],
             [lift3(axis, u, v, a - side * depth) for (u, v), a in zip(inner, zs)],
             [lift3(axis, u, v, a + side * 0.012) for (u, v), a in zip(ext, zs)],
             [lift3(axis, u, v, a + side * 0.4) for (u, v), a in zip(ext, zs)]]
    part = K.Part('cutter')
    lo = inner.min(axis=0)
    part.face(rings[0], back, smooth=False, uvs=[((u - lo[0]) / tile, (v - lo[1]) / tile) for u, v in inner])
    part.face(rings[3][::-1], bevel, smooth=False)
    n = len(outer)
    for r, mat in ((0, wall), (1, bevel), (2, bevel)):
        A, B_ = rings[r], rings[r + 1]
        for i in range(n):
            i2 = (i + 1) % n
            part.face([A[i], B_[i], B_[i2], A[i2]], mat, smooth=False)
    bmesh.ops.remove_doubles(part.bm, verts=part.bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(part.bm, faces=part.bm.faces)
    return part.build(mats, merge_dist=0)


def slab(part, ring, y0, y1, mat):
    """a closed slab over a plan outline [(x, z)] between heights y0 and y1"""
    bm = bmesh.new()
    vs = [bm.verts.new(K.B(x, y0, z)) for x, z in ring]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in (e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)):
        v.co.z += (y1 - y0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    part.merge(bm, mat)


# ---------------------------------------------------------------- the nose

# the lamp units: wide angular blocks from the grille's frame to the wing corner, the top edge straight under the
# bonnet's leading edge, the lower edge stepping down towards the outside (head-on photo 22091110195, r04)
HEADLAMP = [(0.336, 0.746), (0.60, 0.747), (0.800, 0.746), (0.836, 0.735), (0.851, 0.707), (0.850, 0.667),
            (0.836, 0.637), (0.800, 0.618), (0.612, 0.617), (0.588, 0.630), (0.360, 0.634), (0.333, 0.645),
            (0.329, 0.697)]
LAMP_BOX = (0.329, 0.617, 0.851, 0.747)
# the grille: a recessed slot between the lamps, as tall as they are, under a thin body-coloured top bar
GRILLE = [(-0.272, 0.640), (0.272, 0.640), (0.276, 0.726), (-0.276, 0.726)]
# the big central intake (intercooler behind), the tall outer ducts with the clear indicators above them; corner
# order (lower inner/left, lower outer/right, upper outer/right, upper inner/left). Chamfers (l, r, b, t, depth):
# the intake sits back under the bumper's brow (no chamfer at the top: the brow's underside), its sill and pillars
# slope in; the outer ducts' inner edges and tops are wide angled faces
INTAKE = [(-0.505, 0.222), (0.505, 0.222), (0.492, 0.462), (-0.492, 0.462)]
INTAKE_BEVEL = dict(l=0.026, r=0.026, b=0.034, t=0.0)
DUCT = [(0.600, 0.205), (0.838, 0.215), (0.836, 0.372), (0.612, 0.368)]
DUCT_BEVEL = dict(l=0.045, r=0.012, b=0.010, t=0.026)
INDICATOR = [(0.632, 0.402), (0.805, 0.404), (0.803, 0.460), (0.628, 0.458)]
PLATE_F = (-0.300, 0.290)      # centre x (car's right, -x: off-centre as on Japanese cars), bottom edge y
# (z, y) on the bumper's side: a pocket whose front edge is a long angled face (the crease from the bumper's corner
# down to the wheel), the black slot at its back
BRAKE_DUCT = [(1.730, 0.255), (1.905, 0.245), (1.955, 0.535), (1.755, 0.500)]
BRAKE_BEVEL = dict(l=0.006, r=0.060, b=0.006, t=0.014)
BONNET_VENT = [(-0.17, 1.30), (0.17, 1.30), (0.15, 1.54), (-0.15, 1.54)]      # (x, z) on the bonnet


INTAKE_BACK = 2.17


def front_cutters(mats, surf):
    """surf: the uncut shell (the chamfers start on its surface)"""
    rp = lambda q, r: rounded_poly(q, r)
    cs = [prism(mats, rp(GRILLE, 0.012), 'z', SH.nose_z(0.0, 0.68) - 0.045, 2.6),
          bevel_cutter(mats, surf, rp(INTAKE, 0.03), rp(inset_quad(INTAKE, **INTAKE_BEVEL), 0.03), 'z', 1, 0.045,
                       INTAKE_BACK),
          prism(mats, rp(BONNET_VENT, 0.03), 'y', 0.845, 1.3)]
    o, i = rp(DUCT, 0.02), rp(inset_quad(DUCT, **DUCT_BEVEL), 0.02)
    cs.append(bevel_cutter(mats, surf, o, i, 'z', 1, 0.045, 2.10))
    cs.append(bevel_cutter(mats, surf, mirror_u(o), mirror_u(i), 'z', 1, 0.045, 2.10))
    o, i = rp(BRAKE_DUCT, 0.025), rp(inset_quad(BRAKE_DUCT, **BRAKE_BEVEL), 0.025)
    for s in (1, -1):
        cs.append(bevel_cutter(mats, surf, o if s > 0 else o[::-1], i if s > 0 else i[::-1], 'x', s, 0.045, s * 0.66))
    return cs


def front_fittings(part, surf):
    """lamps laid on the nose, the plate and intercooler in the intake, vent fins, the splitter"""
    for s in (1, -1):
        hl = resample(rounded_poly(HEADLAMP if s > 0 else mirror_u(HEADLAMP), 0.012), 72)
        u0, v0, u1, v1 = LAMP_BOX
        box = (u0, v0, u1, v1) if s > 0 else (-u0, v0, -u1, v1)
        cx = 0.59 * s
        # thin dark seal round the lens, then the clear lens over the lamp's works (headlight texture)
        # (many rings: the outer end wraps round the wing's corner, coarse triangles would dip under the body there)
        patch(part, surf, [(cx + (x - cx) * 1.012, 0.682 + (y - 0.682) * 1.05) for x, y in hl], 'z', 1, 'trim',
              lift=0.0015, rings=7)
        patch(part, surf, hl, 'z', 1, 'headlight', lift=0.003, rings=7, uv_box=box)
        # indicator: clear lens with the amber bulb behind
        ind = resample(rounded_poly(INDICATOR if s > 0 else mirror_u(INDICATOR), 0.01), 28)
        patch(part, surf, ind, 'z', 1, 'lens_clear', lift=0.0025, rings=2)
        ic = np.array(ind).mean(axis=0)
        bulb = [(ic[0] + (x - ic[0]) * 0.32, ic[1] + (y - ic[1]) * 0.55) for x, y in ind]
        patch(part, surf, bulb, 'z', 1, 'amber', lift=0.0032, rings=1)
    # number plate off-centre on a bracket in the intake (the intercooler's mesh is the opening's back)
    z = SH.nose_z(PLATE_F[0], 0.36) + 0.006
    w, h = 0.330, 0.165
    x0, y0 = PLATE_F[0] - w / 2, PLATE_F[1]
    part.box('trim', PLATE_F[0] - 0.05, PLATE_F[0] + 0.05, 0.31, 0.42, INTAKE_BACK + 0.001, z - 0.006)
    part.box('trim', x0 - 0.004, x0 + w + 0.004, y0 - 0.004, y0 + h + 0.004, z - 0.008, z - 0.002)
    fix(part.face([(x0, y0, z), (x0 + w, y0, z), (x0 + w, y0 + h, z), (x0, y0 + h, z)], 'plate', smooth=False,
                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)]), np.array((0, 0, 1.0)))
    # bonnet vent fins
    for k in range(5):
        x = -0.12 + 0.06 * k
        top = surf.onto(x, 1.42, 'y', 1)
        part.box('trim', x - 0.004, x + 0.004, 0.82, (top[1] if top is not None else 0.90) - 0.008, 1.31, 1.53)
    # V-spec splitter: a crisp, flat black blade under the bumper, sticking out 4 cm
    xs = np.linspace(0.0, 0.86, 24)
    front = [(x, SH.nose_z(x, 0.16) + 0.04 - 0.02 * (x / 0.86) ** 6) for x in xs]
    half = front + [(x, z - 0.24) for x, z in reversed(front)]
    full = half + [(-x, z) for x, z in reversed(half) if x > 1e-6]
    slab(part, dedupe(full), 0.106, 0.126, 'trim')


# ---------------------------------------------------------------- the tail

TAIL_LAMPS = [(0.720, 0.845, 0.102), (0.510, 0.845, 0.083)]
PLATE_R = [(-0.19, 0.315), (0.19, 0.315), (0.19, 0.515), (-0.19, 0.515)]


def rear_cutters(mats):
    return [prism(mats, rounded_poly(PLATE_R, 0.02), 'z', -2.27, -2.7, back='trim', wall='paint')]


def tail_lamp(part, surf, x, y, R, u_off):
    """a round lamp: dark bezel ring, a domed lens (taillight texture: one lamp per half of the map)"""
    hit = surf.onto(x, y, 'z', -1)
    z0 = hit[2] if hit is not None else SH.lamp_face_z(x, y)
    # body-coloured lip round the lamp's cup, a black bezel, then the domed lens
    prof = [(R + 0.024, 0.008), (R + 0.022, -0.003), (R + 0.016, -0.007), (R + 0.011, -0.006), (R + 0.005, -0.003),
            (R, -0.006), (R * 0.88, -0.014), (R * 0.62, -0.021), (R * 0.30, -0.025), (0.0, -0.026)]
    segs = 40
    V = []
    for s in range(segs):
        th = 2 * math.pi * s / segs
        V.append([(x + r * math.cos(th), y + r * math.sin(th), z0 + a) for r, a in prof])
    inside = np.array((x, y, z0 + 0.10))
    sg = 1 if x > 0 else -1
    for s in range(segs):
        s2 = (s + 1) % segs
        for k in range(len(prof) - 1):
            q = [V[s][k], V[s2][k], V[s2][k + 1], V[s][k + 1]]
            if k == len(prof) - 2:
                q = [V[s][k], V[s2][k], V[s][k + 1]]
            mat = 'paint' if k < 2 else ('trim' if k < 5 else 'taillight')
            uv = [(u_off + 0.5 * (0.5 + sg * (p[0] - x) / (2.1 * R)), 0.5 + (p[1] - y) / (2.1 * R)) for p in q]
            f = part.face(q, mat, smooth=k >= 5 or k == 0, uvs=uv)
            if f is not None:
                fix(f, np.mean(np.array(q), axis=0) - inside)


def rear_fittings(part, surf_body, surf_bumper):
    for x, y, R in TAIL_LAMPS:
        for s in (1, -1):
            tail_lamp(part, surf_body, s * x, y, R, 0.0 if x > 0.6 else 0.5)
    # high-mount stop lamp on the lid's rear edge
    stop = resample(rounded_poly([(0.095, 0.906), (-0.095, 0.906), (-0.095, 0.930), (0.095, 0.930)], 0.008), 28)
    patch(part, surf_body, stop, 'z', -1, 'lens_red', lift=0.003, rings=2)
    # reverse lamp (car's left, +x) and fog lamp (right) beside the plate
    for s, mat in ((1, 'lens_clear'), (-1, 'lens_red')):
        r = [(s * 0.225, 0.47), (s * 0.385, 0.47), (s * 0.385, 0.52), (s * 0.225, 0.52)]
        patch(part, surf_bumper, resample(rounded_poly(r, 0.01), 28), 'z', -1, mat, lift=0.003, rings=2)
    # plate on the recess back
    z = -2.27 - 0.003
    w, h, y0 = 0.330, 0.165, 0.332
    fix(part.face([(w / 2, y0, z), (-w / 2, y0, z), (-w / 2, y0 + h, z), (w / 2, y0 + h, z)], 'plate', smooth=False,
                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)]), np.array((0, 0, -1.0)))
    diffuser(part)


def diffuser(part):
    """V-spec rear diffuser: a black undertray below the bumper with fins"""
    zf = lambda x: -2.30 + 0.10 * (x / 0.86) ** 2
    xs = np.linspace(0.0, 0.78, 14)
    edge = [(x, zf(x)) for x in xs]
    ring = edge[::-1] + [(-x, z) for x, z in edge[1:]] + [(-0.78, -1.85), (0.78, -1.85)]
    slab(part, dedupe(ring), 0.235, 0.247, 'trim')
    for x in (-0.36, -0.18, 0.0, 0.18, 0.36):
        part.box('trim', x - 0.004, x + 0.004, 0.17, 0.236, zf(x) + 0.01, -1.95)


def exhaust(mats, parent):
    """the stock single tailpipe, car's left, under the bumper"""
    part = K.Part('exhaust')
    x, y, z = 0.50, 0.185, -2.29
    prof = [(0.040, 0.30), (0.046, 0.06), (0.054, 0.02), (0.057, 0.003), (0.057, 0.0), (0.052, -0.002),
            (0.049, 0.0), (0.047, 0.08)]
    part.lathe(prof, 'chrome', (x, y, z), axis='z', segments=24, flip=True)
    part.cylinder('trim', (x, y, z + 0.05), 0.0375, 0.004, axis='z', segments=16)
    o = part.build(mats)
    o.parent = parent
    return o
