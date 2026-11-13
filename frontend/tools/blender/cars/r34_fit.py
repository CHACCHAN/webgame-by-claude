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



class Unrolled:
    """
    The nose's surface unrolled round its corners: at height y, s is the distance round the horizontal section (s = x
    up to x = S0 on the front, then the arc length on, round the wing's corner and back along the side). Sections are
    ray-cast fans from inside the nose (left half), cached by height.
    """
    S0 = 0.43

    def __init__(self, surf, zc=1.40, n=360, dy=0.002):
        self.surf, self.zc, self.n, self.dy = surf, zc, n, dy
        self.cache = {}

    def section(self, k):
        if k in self.cache:
            return self.cache[k]
        y = k * self.dy
        P, N = [], []
        for i in range(self.n + 1):
            phi = math.radians(82.0) * i / self.n
            d = np.array([math.sin(phi), 0.0, math.cos(phi)])
            loc, nrm, _, _ = self.surf.bvh.ray_cast(K.B(0.0, y, self.zc), K.B(*d))
            if loc is None:
                continue
            p, nn = np.array(K.G(loc)), np.array(K.G(nrm))
            if np.dot(nn, d) < 0:
                nn = -nn
            P.append(p)
            N.append(nn)
        P, N = np.array(P), np.array(N)
        i0 = int(np.argmax(P[:, 0] >= self.S0))
        t = (self.S0 - P[i0 - 1, 0]) / (P[i0, 0] - P[i0 - 1, 0])
        p0 = P[i0 - 1] + (P[i0] - P[i0 - 1]) * t
        n0 = N[i0 - 1] + (N[i0] - N[i0 - 1]) * t
        P, N = np.vstack([p0, P[i0:]]), np.vstack([n0, N[i0:]])
        sv = self.S0 + np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        self.cache[k] = (sv, P, N)
        return self.cache[k]

    def _pair(self, y):
        f = y / self.dy
        k = int(math.floor(f))
        return self.section(k), self.section(k + 1), f - k

    def s_of(self, kind, a, y):
        """s of a point given by its head-on x ('x') or, on the side, its station z ('z')"""
        out = []
        for sv, P, _ in self._pair(y)[:2]:
            if kind == 'x':
                if a <= self.S0:
                    out.append(a)
                    continue
                i = int(np.argmax(P[:, 0] >= a))
                t = (a - P[i - 1, 0]) / (P[i, 0] - P[i - 1, 0])
            else:
                i = int(np.argmax(P[:, 2] <= a))
                t = (P[i - 1, 2] - a) / (P[i - 1, 2] - P[i, 2])
            out.append(sv[i - 1] + (sv[i] - sv[i - 1]) * t)
        f = self._pair(y)[2]
        return out[0] + (out[1] - out[0]) * f

    def at(self, s, y, lift=0.0):
        """the surface point (game frame) at (s, y) on the left half, lifted along the normal; and the normal"""
        if s <= self.S0:
            hit = self.surf.onto(s, y, 'z', 1)
            loc, nrm, _, _ = self.surf.bvh.ray_cast(K.B(s, y, 4.0), K.B(0, 0, -1.0))
            n = np.array(K.G(nrm)) if nrm is not None else np.array((0, 0, 1.0))
            if n[2] < 0:
                n = -n
            return (hit + n * lift if hit is not None else None), n
        A, Bq, f = self._pair(y)
        ps, ns = [], []
        for sv, P, N in (A, Bq):
            i = int(np.clip(np.searchsorted(sv, s) - 1, 0, len(sv) - 2))
            t = float(np.clip((s - sv[i]) / max(sv[i + 1] - sv[i], 1e-9), 0, 1))
            ps.append(P[i] + (P[i + 1] - P[i]) * t)
            ns.append(N[i] + (N[i + 1] - N[i]) * t)
        p = ps[0] + (ps[1] - ps[0]) * f
        n = ns[0] + (ns[1] - ns[0]) * f
        n /= np.linalg.norm(n)
        return p + n * lift, n


def patch_unrolled(part, U, poly, mat, lift=0.002, rings=3, uv_box=None, side=1):
    """patch() on the unrolled nose: the outline poly [(s, y)] (left half; side -1 mirrors the result)"""
    poly = np.array(poly, float)
    c = poly.mean(axis=0)
    grid = [[c + (p - c) * (k / rings) for p in poly] for k in range(rings, 0, -1)]
    mir = np.array((side, 1.0, 1.0))
    PN = [[U.at(q[0], q[1], lift) for q in ring] for ring in grid]
    cpn = U.at(c[0], c[1], lift)
    u0, v0, u1, v1 = uv_box if uv_box is not None else (*poly.min(axis=0), *poly.max(axis=0))
    uvf = lambda q: ((q[0] - u0) / (u1 - u0), (q[1] - v0) / (v1 - v0))
    n = len(poly)
    for j in range(rings):
        for i in range(n):
            i2 = (i + 1) % n
            if j + 1 < rings:
                q = [PN[j][i], PN[j][i2], PN[j + 1][i2], PN[j + 1][i]]
                uv = [uvf(grid[j][i]), uvf(grid[j][i2]), uvf(grid[j + 1][i2]), uvf(grid[j + 1][i])]
            else:
                q = [PN[j][i], PN[j][i2], cpn]
                uv = [uvf(grid[j][i]), uvf(grid[j][i2]), uvf(c)]
            if any(p[0] is None for p in q):
                continue
            want = np.mean([p[1] for p in q], axis=0) * mir
            fix(part.face([tuple(p[0] * mir) for p in q], mat, smooth=True, uvs=uv), want)

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



def offset_poly(poly, d):
    """the closed outline moved inwards by d (mitred corners)"""
    P = np.array(poly, float)
    n = len(P)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    sg = 1.0 if area > 0 else -1.0
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e0, e1 = (b - a) / np.linalg.norm(b - a), (c - b) / np.linalg.norm(c - b)
        n0, n1 = sg * np.array([-e0[1], e0[0]]), sg * np.array([-e1[1], e1[0]])     # inward normals
        m = n0 + n1
        m /= np.linalg.norm(m)
        out.append(tuple(b + m * d / max(0.3, float(np.dot(m, n0)))))
    return out


def naca_cutter(mats, surf, tri, depth):
    """
    A NACA duct: a ramp sunk into the bonnet, flush at its point (tri[2]) and `depth` deep at the open rear edge
    (tri[0] .. tri[1]); the cutter's floor and walls become the duct's carbon (trim)
    """
    part = K.Part('cutter')
    P = [np.array(p, float) for p in resample(list(tri), 24)]
    zt, zr = tri[2][1], tri[0][1]
    bot, top = [], []
    for x, z in P:
        hit = surf.onto(x, z, 'y', 1)
        y = hit[1] if hit is not None else 0.85
        f = float(np.clip((zt - z) / (zt - zr), 0.0, 1.0))
        bot.append((x, y - 0.002 - depth * f ** 1.4, z))
        top.append((x, y + 0.3, z))
    part.face(bot, 'trim', smooth=False)
    part.face(top[::-1], 'trim', smooth=False)
    n = len(P)
    for i in range(n):
        i2 = (i + 1) % n
        part.face([bot[i], top[i], top[i2], bot[i2]], 'trim', smooth=False)
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

# The nose's layout, measured: the outlines traced on the head-on photo (r29, P&S museum) and the front 3/4 (r07),
# carried back onto the fitted body and through the inverse FFD into this design frame (fitdata/r34/lamps.json,
# tools/lampback.py); left half (+x), (x, y) seen head-on.
# The head lamps: slanted "eyes" whose top edge is the bonnet's leading edge (SH.BONNET_EDGE) rising to the wing's
# corner; the inner end a near-vertical edge beside the grille; the outer end wraps round the corner and runs back
# along the wing's side to a D-shaped end at z 1.875, its top edge dropping towards the corner (side photo r36,
# rear 3/4 r11). Points: ('x', x, y)
# on the front (head-on x), ('z', z, y) on the side (station z); laid on the body unrolled (Unrolled, s by y)
HEADLAMP = [('x', 0.452, 0.712), ('x', 0.50, 0.726), ('x', 0.55, 0.735), ('x', 0.60, 0.743), ('x', 0.65, 0.749),
            ('x', 0.70, 0.755), ('x', 0.75, 0.760), ('x', 0.80, 0.762), ('x', 0.835, 0.757),
            ('z', 2.06, 0.742), ('z', 2.00, 0.751), ('z', 1.94, 0.756), ('z', 1.905, 0.757),
            ('z', 1.884, 0.748), ('z', 1.877, 0.730), ('z', 1.875, 0.705), ('z', 1.877, 0.680), ('z', 1.886, 0.656),
            ('z', 1.899, 0.639), ('z', 1.924, 0.631), ('z', 1.96, 0.630), ('z', 2.03, 0.632), ('z', 2.08, 0.637),
            ('x', 0.835, 0.646), ('x', 0.80, 0.646), ('x', 0.70, 0.635), ('x', 0.60, 0.623), ('x', 0.50, 0.609),
            ('x', 0.456, 0.602), ('x', 0.444, 0.608), ('x', 0.447, 0.660)]
# the lens's box in unrolled coordinates (s, y): the headlight texture spans it (r34_textures.LAMP_BOX)
LAMP_BOX = (0.444, 0.602, 1.118, 0.765)
# the grille: a wide recessed slot under a narrow body-coloured bar below the bonnet's edge
GRILLE = [(-0.402, 0.524), (0.402, 0.524), (0.412, 0.650), (-0.412, 0.650)]
# the big central intake (intercooler behind) under the bumper's brow; corner order (lower inner/left, lower
# outer/right, upper outer/right, upper inner/left). Chamfers (l, r, b, t): the sill and pillars slope in, no
# chamfer at the top (the brow's underside)
INTAKE = [(-0.415, 0.262), (0.415, 0.262), (0.415, 0.412), (-0.415, 0.412)]
INTAKE_BEVEL = dict(l=0.022, r=0.022, b=0.030, t=0.0)
# the outer mesh openings under the indicators: a strip tapering towards the intake (left half)
MESH = [(0.505, 0.344), (0.500, 0.290), (0.776, 0.284), (0.781, 0.384), (0.695, 0.391), (0.611, 0.382),
        (0.545, 0.367)]
MESH_BEVEL = 0.010
# the clear indicator lenses (ribbed, amber bulb behind) between the lamps and the mesh openings, in black bezels;
# the top edge rises a little outwards (head-on r29)
INDICATOR = [(0.672, 0.449), (0.800, 0.452), (0.800, 0.516), (0.672, 0.513)]
PLATE_F = (-0.255, 0.252)      # centre x (car's right, -x: off-centre as on Japanese cars), bottom edge y
# (z, y) on the bumper's side: a pocket whose front edge is a long angled face (the crease from the bumper's corner
# down to the wheel), the black slot at its back
BRAKE_DUCT = [(1.730, 0.255), (1.905, 0.245), (1.955, 0.535), (1.755, 0.500)]
BRAKE_BEVEL = dict(l=0.006, r=0.060, b=0.006, t=0.014)
# the V-spec II's NACA duct in the carbon bonnet, car's left (x, z): the open rear edge, the point forward
NACA = [(0.350, 1.320), (0.467, 1.320), (0.427, 1.480)]
NACA_DEPTH = 0.026


INTAKE_BACK = 2.17


def front_cutters(mats, surf):
    """surf: the uncut shell (the chamfers start on its surface)"""
    rp = lambda q, r: rounded_poly(q, r)
    # the grille in a body-coloured frame: a chamfer sloping in to the opening (head-on r29: the "nostril" surround)
    cs = [bevel_cutter(mats, surf, rp(inset_quad(GRILLE, l=-0.010, r=-0.010, b=-0.010), 0.02),
                       rp(inset_quad(GRILLE, l=0.008, r=0.008, b=0.006, t=0.004), 0.02), 'z', 1, 0.022,
                       SH.nose_z(0.0, 0.59) - 0.045),
          bevel_cutter(mats, surf, rp(INTAKE, 0.03), rp(inset_quad(INTAKE, **INTAKE_BEVEL), 0.03), 'z', 1, 0.045,
                       INTAKE_BACK),
          naca_cutter(mats, surf, NACA, NACA_DEPTH)]
    o = resample(rp(MESH, 0.015), 40)
    i = [tuple(p) for p in offset_poly(o, MESH_BEVEL)]
    # the side openings are dark right up to their outline (the photo's traced edge): black chamfers
    cs.append(bevel_cutter(mats, surf, o, i, 'z', 1, 0.03, 2.12, bevel='trim'))
    cs.append(bevel_cutter(mats, surf, mirror_u(o), mirror_u(i), 'z', 1, 0.03, 2.12, bevel='trim'))
    o, i = rp(BRAKE_DUCT, 0.025), rp(inset_quad(BRAKE_DUCT, **BRAKE_BEVEL), 0.025)
    for s in (1, -1):
        cs.append(bevel_cutter(mats, surf, o if s > 0 else o[::-1], i if s > 0 else i[::-1], 'x', s, 0.045, s * 0.66))
    return cs


def front_fittings(part, surf):
    """lamps laid on the nose, the plate and intercooler in the intake, vent fins, the splitter"""
    U = Unrolled(surf)
    outline = [(U.s_of(k, a, y), y) for k, a, y in HEADLAMP]
    hl = resample(rounded_poly(outline, 0.012), 96)
    seal = offset_poly(hl, -0.004)
    for s in (1, -1):
        # thin dark seal round the lens, then the clear lens over the lamp's works (headlight texture)
        patch_unrolled(part, U, seal, 'trim', lift=0.0015, rings=7, side=s)
        patch_unrolled(part, U, hl, 'headlight', lift=0.003, rings=7, uv_box=LAMP_BOX, side=s)
        # indicator: clear lens with the amber bulb behind
        ind = resample(rounded_poly(INDICATOR if s > 0 else mirror_u(INDICATOR), 0.01), 28)
        bezel = resample(rounded_poly(offset_poly(INDICATOR if s > 0 else mirror_u(INDICATOR), -0.011), 0.02), 32)
        patch(part, surf, bezel, 'z', 1, 'trim', lift=0.0015, rings=2)
        # the clear ribbed lens (indicator texture: the amber bulb only a faint glow behind it)
        patch(part, surf, ind, 'z', 1, 'lens_clear', lift=0.0025, rings=2)
    # GT-R emblem on the grille's mesh (own simple shape: a small chrome badge)
    zb = SH.nose_z(0.0, 0.59) - 0.040
    part.box('chrome', -0.034, 0.034, 0.552, 0.614, zb, zb + 0.008, bevel=0.006)
    # number plate off-centre on a bracket in the intake (the intercooler's mesh is the opening's back)
    z = SH.nose_z(PLATE_F[0], 0.36) + 0.006
    w, h = 0.330, 0.165
    x0, y0 = PLATE_F[0] - w / 2, PLATE_F[1]
    part.box('trim', PLATE_F[0] - 0.05, PLATE_F[0] + 0.05, 0.31, 0.42, INTAKE_BACK + 0.001, z - 0.006)
    part.box('trim', x0 - 0.004, x0 + w + 0.004, y0 - 0.004, y0 + h + 0.004, z - 0.008, z - 0.002)
    fix(part.face([(x0, y0, z), (x0 + w, y0, z), (x0 + w, y0 + h, z), (x0, y0 + h, z)], 'plate', smooth=False,
                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)]), np.array((0, 0, 1.0)))
    # V-spec splitter: a crisp, flat black blade under the bumper, sticking out 4 cm
    xs = np.linspace(0.0, 0.86, 24)
    front = [(x, SH.nose_z(x, 0.16) + 0.04 - 0.02 * (x / 0.86) ** 6) for x in xs]
    half = front + [(x, z - 0.24) for x, z in reversed(front)]
    full = half + [(-x, z) for x, z in reversed(half) if x > 1e-6]
    slab(part, dedupe(full), 0.106, 0.126, 'trim')


# ---------------------------------------------------------------- the tail

# (x, y, lens radius): the red lenses traced on the tail-on (r37) and rear 3/4 photos (r38, r11), ellipses fitted
# (tools/lamptrace.py) and carried back onto the body (lampback.py); the outer lamps sit higher than the inner ones
TAIL_LAMPS = [(0.690, 0.832, 0.102), (0.485, 0.806, 0.078)]
TAIL_YAW = [math.radians(12.0), math.radians(8.0)]       # turned outwards (round lenses seen narrower than tall)
PLATE_R = [(-0.19, 0.315), (0.19, 0.315), (0.19, 0.515), (-0.19, 0.515)]


def rear_cutters(mats):
    return [prism(mats, rounded_poly(PLATE_R, 0.02), 'z', -2.27, -2.7, back='trim', wall='paint')]


def tail_lamp(part, surf, x, y, R, u_off, yaw=0.0):
    """
    a round lamp: body-coloured lip seated on the panel, a thin dark gap and bright rim, a domed lens (taillight texture: one lamp
    per half of the map). The lamp faces back and `yaw` (rad) outwards: the real lenses follow the panel as it turns
    round the corners (the outer ones look narrower than tall on the tail-on photo)
    """
    sg = 1 if x > 0 else -1
    hit = surf.onto(x, y, 'z', -1)
    z0 = hit[2] if hit is not None else SH.lamp_face_z(x, y)
    c = np.array((x, y, z0))
    ez = np.array((-sg * math.sin(yaw), 0.0, math.cos(yaw)))        # into the car
    ex = np.array((math.cos(yaw), 0.0, sg * math.sin(yaw)))
    ey = np.array((0.0, 1.0, 0.0))
    # body-coloured lip round the lamp's cup, a black bezel, then the domed lens
    prof = [(R + 0.020, 0.008), (R + 0.018, -0.003), (R + 0.010, -0.006), (R + 0.006, -0.005), (R + 0.003, -0.004),
            (R, -0.006), (R * 0.88, -0.014), (R * 0.62, -0.021), (R * 0.30, -0.025), (0.0, -0.026)]
    segs = 40
    V = []
    for k_ in range(segs):
        th = 2 * math.pi * k_ / segs
        ring = [c + r * (math.cos(th) * ex + math.sin(th) * ey) + a * ez for r, a in prof]
        # the lip's outer edge sits on the panel itself (the lamp turned outwards would float off or sink in)
        p0 = ring[0]
        on = surf.onto(p0[0], p0[1], 'z', -1)
        if on is not None:
            ring[0] = np.array((p0[0], p0[1], on[2] + 0.002))
        V.append([tuple(p) for p in ring])
    inside = c + ez * 0.10
    for k_ in range(segs):
        k2 = (k_ + 1) % segs
        for k in range(len(prof) - 1):
            q = [V[k_][k], V[k2][k], V[k2][k + 1], V[k_][k + 1]]
            if k == len(prof) - 2:
                q = [V[k_][k], V[k2][k], V[k_][k + 1]]
            mat = 'paint' if k < 2 else ('trim' if k < 4 else ('chrome' if k < 5 else 'taillight'))
            uv = []
            for p in q:
                d = np.array(p) - c
                uv.append((u_off + 0.5 * (0.5 + sg * float(d @ ex) / (2.1 * R)), 0.5 + float(d @ ey) / (2.1 * R)))
            f = part.face(q, mat, smooth=k >= 5 or k == 0, uvs=uv)
            if f is not None:
                fix(f, np.mean(np.array(q), axis=0) - inside)


def rear_fittings(part, surf_body, surf_bumper):
    for (x, y, R), yaw in zip(TAIL_LAMPS, TAIL_YAW):
        for s in (1, -1):
            tail_lamp(part, surf_body, s * x, y, R, 0.0 if x > 0.6 else 0.5, yaw)
    # high-mount stop lamp on the lid's rear edge
    stop = resample(rounded_poly([(0.092, 0.930), (-0.092, 0.930), (-0.092, 0.959), (0.092, 0.959)], 0.008), 28)
    patch(part, surf_body, stop, 'z', -1, 'lens_red', lift=0.003, rings=2)
    # reverse lamp (car's left, +x) and fog lamp (right) beside the plate
    for s, mat in ((1, 'lens_clear'), (-1, 'lens_red')):
        r = [(s * 0.200, 0.463), (s * 0.335, 0.463), (s * 0.335, 0.534), (s * 0.200, 0.534)]
        patch(part, surf_bumper, resample(rounded_poly(r, 0.01), 28), 'z', -1, mat, lift=0.003, rings=2)
    # Nissan roundel and the GT-R emblem on the lid's right-hand lower corner (own simple shapes; tail-on r37)
    for (x, y), (w, h) in (((-0.270, 0.790), (0.030, 0.030)), ((-0.290, 0.712), (0.058, 0.046))):
        hit = surf_body.onto(x, y, 'z', -1)
        if hit is not None:
            z = hit[2]
            part.box('chrome', x - w / 2, x + w / 2, y - h / 2, y + h / 2, z - 0.006, z + 0.004, bevel=min(w, h) * 0.3)
    # plate on the recess back
    z = -2.27 - 0.003
    w, h, y0 = 0.330, 0.165, 0.332
    fix(part.face([(w / 2, y0, z), (-w / 2, y0, z), (-w / 2, y0 + h, z), (w / 2, y0 + h, z)], 'plate', smooth=False,
                  uvs=[(0, 0), (1, 0), (1, 1), (0, 1)]), np.array((0, 0, -1.0)))
    diffuser(part)


def diffuser(part):
    """V-spec rear diffuser: a black undertray below the bumper with fins, notched round the tailpipe"""
    zf = lambda x: -2.30 + 0.10 * (x / 0.86) ** 2
    xs = [x for x in np.linspace(0.0, 0.78, 14) if not 0.40 < x < 0.64]
    edge = [(x, zf(x)) for x in xs if x <= 0.40] + [(0.40, -1.90), (0.64, -1.90)] + [(x, zf(x)) for x in xs if x >= 0.64]
    ring = edge[::-1] + [(-x, z) for x, z in edge[1:]] + [(-0.78, -1.85), (0.78, -1.85)]
    slab(part, dedupe(ring), 0.235, 0.247, 'trim')
    for x in (-0.36, -0.18, 0.0, 0.18, 0.36):
        part.box('trim', x - 0.004, x + 0.004, 0.17, 0.236, zf(x) + 0.01, -1.95)


EXHAUST = (0.52, 0.272, -2.29)          # the tailpipe's mouth: in the recess under the bumper's lower edge (r37)


def exhaust(mats, parent):
    """the stock single tailpipe, car's left, under the bumper"""
    part = K.Part('exhaust')
    x, y, z = EXHAUST
    prof = [(0.040, 0.30), (0.046, 0.06), (0.054, 0.02), (0.057, 0.003), (0.057, 0.0), (0.052, -0.002),
            (0.049, 0.0), (0.047, 0.08)]
    part.lathe(prof, 'chrome', (x, y, z), axis='z', segments=24, flip=True)
    part.cylinder('trim', (x, y, z + 0.05), 0.0375, 0.004, axis='z', segments=16)
    o = part.build(mats)
    o.parent = parent
    return o
