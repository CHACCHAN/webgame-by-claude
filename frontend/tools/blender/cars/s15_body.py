"""
The Silvia S15's body shell: a control cage lofted from measured profile, plan and section curves (half car, x >= 0),
mirrored and subdivided (Catmull-Clark, level 1), the wheel arches cut by booleans.

The cage: rings at stations along z, each ring a half section of 16 key points (subdivided further), from the floor's
centre (0) out under the car (bottom arm, 0..5), up the side (5..10) and in over the bonnet / greenhouse / deck to
the top centre (top arm, 10..15). The ends are closed by caps whose grid pairs bottom-arm point k with top-arm
point 15-k (vertical strips across the nose and the tail).
"""
import math

import bmesh
import bpy
import numpy as np

import s15_kit as K
from s15_kit import Pchip, smoothstep, lerp

# ---------------------------------------------------------------- dimensions (spec-R, GF-S15)
WHEELBASE = 2.525
AXLE_F = WHEELBASE / 2
AXLE_R = -WHEELBASE / 2
TRACK_F = 1.480
TRACK_R = 1.470
TYRE_R = 0.31                  # 215/45R17 → 0.3127 m; the game's wheelRadius
Z_NOSE = AXLE_F + 0.905        # 2.1675: overall length 4.445
Z_TAIL = AXLE_R - 1.015        # -2.2775
HALF_W = 0.8475                # 1.695
ROOF = 1.285
ARCH_R = 0.350                 # wheel-arch opening radius (tyre 0.31: a ~4 cm gap)

# stations: the front and rear rings (at the sides)
Z_FR = 1.90
Z_RR = -2.11

# ---------------------------------------------------------------- feature curves (game frame, z)
# floor height under the car
YB = Pchip([(-2.11, 0.33), (-1.95, 0.29), (-1.70, 0.215), (-1.45, 0.175), (-1.0, 0.165), (1.0, 0.165), (1.45, 0.17),
            (1.75, 0.18), (2.10, 0.19)])
# half-width at the widest height (plan)
W = Pchip([(-2.11, 0.775), (-2.02, 0.812), (-1.85, 0.838), (-1.55, 0.8475), (-1.15, 0.846), (-0.75, 0.838), (0.0, 0.834),
           (0.75, 0.837), (1.05, 0.843), (1.40, 0.845), (1.65, 0.832), (1.80, 0.808), (1.90, 0.776)])
# height of the widest line
# (the character line: from the headlamp's outer end along the doors just under the handles to the tail lamps)
YW = Pchip([(-2.11, 0.790), (-1.6, 0.800), (-1.0, 0.800), (0.0, 0.795), (0.8, 0.785), (1.3, 0.760), (1.6, 0.725), (1.90, 0.700)])
# the side's top edge: fender top / belt / rear deck edge (height, half-width)
Y10 = Pchip([(-2.11, 0.880), (-1.90, 0.900), (-1.60, 0.910), (-1.25, 0.910), (-0.6, 0.902), (0.0, 0.897), (0.32, 0.895),
             (0.80, 0.875), (1.20, 0.852), (1.55, 0.818), (1.75, 0.795), (1.90, 0.775)])
X10 = Pchip([(-2.11, 0.700), (-2.0, 0.745), (-1.80, 0.775), (-1.40, 0.792), (-0.8, 0.787), (0.0, 0.782), (0.5, 0.780),
             (1.0, 0.784), (1.40, 0.786), (1.70, 0.770), (1.90, 0.725)])
# the centre line's top (nose edge, bonnet, windshield, roof, backlight, deck)
# (measured on a side-on photo scaled by the wheelbase, heights from the roof: the windshield's base is at z ~1.0,
#  just behind the front wheel; the roof peaks at z ~-0.4; the backlight runs down to the deck at z ~-1.47)
YTOP = Pchip([(-2.19, 0.900), (-2.05, 0.925), (-1.85, 0.948), (-1.70, 0.963), (-1.58, 0.985), (-1.47, 1.015), (-1.30, 1.125),
              (-1.10, 1.205), (-0.86, 1.255), (-0.64, 1.278), (-0.40, 1.285), (-0.17, 1.281), (0.05, 1.268), (0.28, 1.233),
              (0.47, 1.150), (0.65, 1.058), (0.86, 0.970), (1.00, 0.912), (1.25, 0.855), (1.50, 0.808), (1.75, 0.760),
              (2.10, 0.690)])
# bonnet / deck crown exponent
# greenhouse: the roof rail's height and half-width in side view (A-pillar, rail, C-pillar)
Z_AB, Z_AT = 0.72, 0.30       # A-pillar base, top (at the side)
Z_CT, Z_CB = -0.62, -1.55      # C-pillar top (behind the B-pillar), base (on the deck)
YRAIL = Pchip([(Z_CB, 0.975), (-1.30, 1.040), (-1.10, 1.105), (-0.95, 1.160), (-0.80, 1.205), (Z_CT, 1.235), (-0.45, 1.245),
               (-0.20, 1.252), (0.05, 1.250), (Z_AT, 1.222), (0.42, 1.180), (0.52, 1.120), (0.62, 1.040), (Z_AB, 0.935)])
XRAIL = Pchip([(Z_CB, 0.745), (-1.30, 0.712), (-1.05, 0.685), (Z_CT, 0.668), (-0.30, 0.665), (Z_AT, 0.672), (0.50, 0.705),
               (0.62, 0.730), (Z_AB, 0.755)])
# nose and tail: plan offset of the top edge from the side (forward of the side ring at the centre)
NOSE_PLAN = 0.185
TAIL_PLAN = 0.12
# front face (centre line): z of the face by height
# (the bumper face runs fairly flat under the plate; the nose's leading edge just under the lamps)
ZFACE_F = Pchip([(0.19, 2.110), (0.26, 2.138), (0.36, 2.150), (0.46, 2.156), (0.56, 2.164), (0.63, Z_NOSE), (0.67, 2.150),
                 (0.70, 2.110)])
ZFACE_R = Pchip([(0.33, -2.205), (0.40, -2.255), (0.50, Z_TAIL), (0.62, -2.272), (0.70, -2.250), (0.74, -2.225),
                 (0.80, -2.205), (0.92, -2.195), (0.975, -2.185)])


def plan_front(x):
    """how far the nose's outline lies forward of the side ring at half-width x"""
    return NOSE_PLAN * max(0.0, 1 - (x / 0.80) ** 2) ** 0.85


def plan_rear(x):
    return TAIL_PLAN * max(0.0, 1 - (x / 0.78) ** 2) ** 0.7


def rake_f(x, y):
    """the nose's upper corners recede (the swept headlamp corners)"""
    return (0.09 + 0.11 * smoothstep(0.50, 0.80, y)) * smoothstep(0.30, 0.80, x)


def rake_r(x, y):
    # upper corners recede to the wrapped lamps; the bumper's lower corners round off under it
    return (0.07 * smoothstep(0.60, 0.95, y) + 0.04 * smoothstep(0.50, 0.22, y)) * smoothstep(0.35, 0.80, x)


def greenhouse(z):
    """1 where the side has a glasshouse above the belt, 0 on the bonnet and the deck"""
    return smoothstep(Z_AB + 0.04, Z_AB - 0.10, z) * smoothstep(Z_CB - 0.04, Z_CB + 0.10, z)


def crown(f, p=2.4):
    return f ** p


SHARP = {5: 1.0, 8: 0.7, 10: 0.9, 11: 0.8}     # key index → crease (rocker corner, shoulder edge, glass base)
INSET = (0.035, 0.075, 0.12)           # on the bonnet / deck: points 11..13 this far inboard of the edge


def ring_points(zs, front_w=0.0, rear_w=0.0):
    """the 16 key points (x, y, z) of the half section at station zs; front_w / rear_w bend it to the nose / tail plan"""
    yb = YB(zs)
    w = W(zs)
    yw = YW(zs)
    x10, y10 = X10(zs), Y10(zs)

    def zof(x, y):
        return zs + front_w * (plan_front(x) - rake_f(x, y)) - rear_w * (plan_rear(x) - rake_r(x, y))

    xf = (w - 0.07) / x10
    # floor points mirror the top arm's spacing (the end caps pair them into vertical strips)
    xf = (w - 0.11) / x10
    # the sill tucks in under the doors; the side runs out to the character line (8), then leans in to the belt (10)
    pts = [(0.0, yb), (0.45 * x10 * xf, yb), ((x10 - INSET[2]) * xf, yb), ((x10 - INSET[1]) * xf, yb),
           ((x10 - INSET[0]) * xf, yb + 0.002), (w - 0.072, yb + 0.024),
           (w - 0.040, lerp(yb, yw, 0.22)), (w - 0.011, lerp(yb, yw, 0.60)), (w, yw), (lerp(w, x10, 0.42), lerp(yw, y10, 0.55)),
           (x10, y10)]
    res = [(x, y, zof(x, y)) for x, y in pts]

    def bonnet(x, z):
        ytop = YTOP(z)
        return ytop + (y10 - ytop) * crown(min(1.0, x / x10))

    g = greenhouse(zs)
    # the bonnet / deck version of the top arm
    xb = [x10 - INSET[0], x10 - INSET[1], x10 - INSET[2], 0.45 * x10, 0.0]
    # the glasshouse version: glass base, mid glass, rail, roof / windshield / backlight
    xr, yr = XRAIL(zs), YRAIL(zs)
    e = max(smoothstep(Z_AB - 0.32, Z_AB + 0.02, zs), smoothstep(Z_CB + 0.36, Z_CB - 0.02, zs))
    z13 = zof(xb[2], y10)
    xr = lerp(xr, xb[2], e)
    yr = lerp(yr, bonnet(xb[2], z13), e)
    x11, y11 = x10 - 0.032, y10 + 0.016
    for k in range(5):
        xg = [x11, lerp(x11, xr, 0.5) + 0.008 * (1 - e), xr, 0.45 * xr, 0.0][k]
        x = lerp(xb[k], xg, g)
        z = zof(x, y10)
        yb_ = bonnet(xb[k], z)
        if k == 0:
            yg = y11
        elif k == 1:
            yg = lerp(y11, yr, 0.5)
        elif k == 2:
            yg = yr
        else:
            ytop = YTOP(z)
            yg = ytop + (yr - ytop) * crown(min(1.0, x / xr) if xr > 0 else 0.0, 2.2)
        res.append((x, lerp(yb_, yg, g), z))
    return res


def refine_ring(key, per=2):
    """subdivide each key segment into `per` parts along a smooth curve through the key points (corners at SHARP keys)"""
    pts = np.array(key, float)
    out = []
    n = len(pts)

    def tangent(i, toward):
        """tangent at key i for the segment towards key `toward` (one-sided at sharp keys and the ends)"""
        if i == 0 or i == n - 1 or i in SHARP:
            return (pts[toward] - pts[i]) * (1 if toward > i else -1) * 0.0 + (pts[toward] - pts[i]) * (1 if toward > i else -1)
        d0 = max(1e-6, float(np.linalg.norm(pts[i] - pts[i - 1])))
        d1 = max(1e-6, float(np.linalg.norm(pts[i + 1] - pts[i])))
        seg = d1 if toward > i else d0
        return (pts[i + 1] - pts[i - 1]) * seg / (d0 + d1)

    for i in range(n - 1):
        p1, p2 = pts[i], pts[i + 1]
        m1, m2 = tangent(i, i + 1), tangent(i + 1, i)
        for s_ in range(per):
            t = s_ / per
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1
            h10 = t ** 3 - 2 * t ** 2 + t
            h01 = -2 * t ** 3 + 3 * t ** 2
            h11 = t ** 3 - t ** 2
            out.append(tuple(h00 * p1 + h10 * m1 + h01 * p2 + h11 * m2))
    out.append(tuple(pts[-1]))
    return out


def stations():
    zs = []
    z = Z_RR
    while z < Z_FR - 1e-6:
        zs.append(z)
        # finer at the ends and round the windshield base / backlight
        step = 0.115
        if z < Z_RR + 0.25 or z > Z_FR - 0.30:
            step = 0.06
        z += step
    zs.append(Z_FR)
    return zs


def cage_rings():
    rings = []
    for zs in stations():
        fw = smoothstep(Z_FR - 0.55, Z_FR, zs)
        rw = smoothstep(Z_RR + 0.35, Z_RR, zs)
        rings.append(refine_ring(ring_points(zs, fw, rw), 2))
    return rings


def cap_grid(ring, front=True):
    """the end cap's vertices: rows k (pair lines from the bottom arm to the top arm), each from bottom to top"""
    n = len(ring) - 1           # 30 segments: bottom arm 0..10, side 10..20, top arm 20..30
    m = n // 3
    rows = []
    for k in range(m + 1):
        if k == m:
            rows.append([ring[i] for i in range(m, 2 * m + 1)])
            continue
        pb, pt = np.array(ring[k]), np.array(ring[n - k])
        row = [tuple(pb)]
        hs = m
        for j in range(1, hs):
            t = j / hs
            # follow the side's height spacing
            side = ring[m + j]
            ts = (side[1] - ring[m][1]) / max(1e-6, ring[2 * m][1] - ring[m][1])
            t = lerp(t, ts, 0.7)
            x = lerp(pb[0], pt[0], t)
            y = lerp(pb[1], pt[1], t)
            if front:
                zc = ZFACE_F(y)
                z = zc - (NOSE_PLAN - plan_front(x)) - rake_f(x, y)
                # blend into the ring's own corner near the outer rows
                zr = lerp(pb[2], pt[2], t)
                z = max(z, zr + 0.002) if k < m else zr
            else:
                zc = ZFACE_R(y)
                z = zc + (TAIL_PLAN - plan_rear(x)) + rake_r(x, y)
                zr = lerp(pb[2], pt[2], t)
                z = min(z, zr - 0.002)
            row.append((x, y, z))
        row.append(tuple(pt))
        rows.append(row)
    return rows


def dump_cage(path):
    """the cage's rings and caps as JSON (for wire drawings)"""
    import json
    rings = cage_rings()
    json.dump({'rings': rings, 'front': cap_grid(rings[-1], True), 'rear': cap_grid(rings[0], False)}, open(path, 'w'))


def build_cage():
    """the half cage as a bmesh (game coordinates via K.B)"""
    rings = cage_rings()
    bm = bmesh.new()
    V = [[bm.verts.new(K.B(*p)) for p in r] for r in rings]
    n = len(rings[0])
    for j in range(len(rings) - 1):
        for i in range(n - 1):
            bm.faces.new([V[j][i], V[j + 1][i], V[j + 1][i + 1], V[j][i + 1]])
    cl = bm.edges.layers.float.new('crease_edge')
    for key, c in SHARP.items():
        i = key * 2
        for j in range(len(rings) - 1):
            e = bm.edges.get([V[j][i], V[j + 1][i]])
            if e is not None:
                e[cl] = c
    for front, idx in ((True, -1), (False, 0)):
        ring = rings[idx]
        Vr = V[idx]
        rows = cap_grid(ring, front)
        m = len(rows) - 1
        nn = n - 1
        grid = []
        for k, row in enumerate(rows):
            g = []
            for j, p in enumerate(row):
                # reuse the ring's vertices on the cap's boundary
                if j == 0:
                    g.append(Vr[k])
                elif j == len(row) - 1:
                    g.append(Vr[nn - k])
                elif k == m:
                    g.append(Vr[m + j])
                else:
                    g.append(bm.verts.new(K.B(*p)))
            grid.append(g)
        for k in range(m):
            for j in range(len(rows[0]) - 1):
                q = [grid[k][j], grid[k][j + 1], grid[k + 1][j + 1], grid[k + 1][j]]
                if not front:
                    q.reverse()
                bm.faces.new(q)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return bm


def shell(subdiv=1, arches=True):
    """the full body shell (mirrored, subdivided, arches cut) as a new bmesh in Blender coordinates"""
    bm = build_cage()
    # outward normals: the cage's centre is inside
    bm.normal_update()
    me = bpy.data.meshes.new('cage')
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new('cage', me)
    bpy.context.scene.collection.objects.link(obj)
    mir = obj.modifiers.new('mirror', 'MIRROR')
    mir.use_axis = (True, False, False)
    mir.use_clip = True
    mir.use_mirror_merge = True
    mir.merge_threshold = 1e-4
    if subdiv:
        sub = obj.modifiers.new('sub', 'SUBSURF')
        sub.levels = subdiv
        sub.render_levels = subdiv
        sub.boundary_smooth = 'ALL'
    if arches:
        cutter = _arch_cutter()
        bo = obj.modifiers.new('arches', 'BOOLEAN')
        bo.operation = 'DIFFERENCE'
        bo.solver = 'EXACT'
        bo.object = cutter
        cutter.hide_render = True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    out = bmesh.new()
    out.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bpy.data.objects.remove(obj)
    if arches:
        bpy.data.objects.remove(cutter)
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    return out


def _arch_cutter():
    bm = bmesh.new()
    for zc in (AXLE_F, AXLE_R):
        for s in (1, -1):
            r = bmesh.new()
            bmesh.ops.create_cone(r, cap_ends=True, cap_tris=False, segments=72, radius1=ARCH_R, radius2=ARCH_R, depth=0.8)
            rot = __import__('mathutils').Matrix.Rotation(math.pi / 2, 4, 'Y')
            bmesh.ops.transform(r, matrix=__import__('mathutils').Matrix.Translation(K.B(s * 1.0, TYRE_R, zc)) @ rot, verts=r.verts)
            tmp = bpy.data.meshes.new('t')
            r.to_mesh(tmp)
            r.free()
            bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new('arch_cutter')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('arch_cutter', me)
    bpy.context.scene.collection.objects.link(o)
    return o
