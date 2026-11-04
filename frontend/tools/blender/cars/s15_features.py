"""
The S15's surface features, cut into the subdivided shell (s15_body.shell): glass and its black bands, the B-pillar,
shut lines, the lamp openings, the bumper openings and the plate recesses. Outlines are drawn in side, front, rear or
top projection (game frame) and cut into the faces that face that way (s15_kit.region / groove).
"""
import math

import bmesh
import numpy as np
from mathutils import Vector

import s15_kit as K
import s15_body as BD
from s15_kit import lerp

# material slots of the shell
MATS = ['paint', 'trim', 'glass', 'chrome', 'amber', 'lens_clear', 'taillight', 'interior', 'headlight']
PAINT, TRIM, GLASS, CHROME, AMBER, CLEAR, TAIL, INTERIOR, HEAD = range(len(MATS))


def mirror_x(poly):
    """a polygon drawn for x >= 0 (u = x) and its mirror image, as one polygon running over both halves"""
    return list(poly) + [(-u, v) for u, v in reversed(poly)]


def both(poly):
    """the polygon for the left side and its mirror for the right (u = x)"""
    return [poly, [(-u, v) for u, v in reversed(poly)]]


def gc(f):
    return K.G(f.calc_center_median())


def gn(f):
    return K.G(f.normal)


def setmat(faces, idx):
    for f in faces:
        f.material_index = idx


# ---------------------------------------------------------------- outlines (game frame)

def dlo():
    """the side glass outline (z, y): belt from the A-pillar base back to the quarter glass, up and along the rail"""
    # (measured on a side-on photo: frameless door glass from z 0.65 at the belt, the quarter glass to a point at z -1.08)
    front = [(0.650, BD.Y10(0.65) + 0.014), (0.600, 0.990), (0.512, 1.098), (0.450, 1.140), (0.397, 1.167), (0.300, 1.198)]
    top = [(z, BD.YRAIL(z) - 0.028) for z in np.linspace(0.24, -0.62, 20)]
    rear = [(-0.75, 1.183), (-0.865, 1.149), (-0.98, 1.098), (-1.04, 1.050), (-1.083, 1.000)]
    belt = [(-1.07, 0.984), (-0.95, 0.950), (-0.865, 0.932)] + [(z, BD.Y10(z) + 0.014) for z in np.linspace(-0.75, 0.64, 30)]
    poly = front + top + rear + belt
    return poly


def b_pillar():
    """the black strip between the door glass and the quarter glass (side view)"""
    # (ends at the glass's top edge, flush under the roof rail)
    return [(-0.555, BD.YRAIL(-0.555) - 0.028), (-0.615, BD.YRAIL(-0.615) - 0.028), (-0.630, 0.85), (-0.570, 0.85)]


def windshield():
    """top view (x, z) of the windshield glass, x >= 0 half; the cowl edge at the bottom"""
    pts = []
    # cowl (base), centre → corner
    for x in np.linspace(0.0, 0.62, 9):
        pts.append((x, 0.98 - 0.18 * (x / 0.70) ** 2.2))
    # side edge up the A-pillar (inboard of the rail)
    for i in range(1, 25):
        z = lerp(0.80, 0.30, i / 24)
        pts.append((BD.XRAIL(z) - 0.062 - 0.02 * (1 - i / 24), z))
    # header, corner → centre
    for x in np.linspace(BD.XRAIL(0.29) - 0.06, 0.0, 9):
        pts.append((x, 0.27 + 0.035 * (1 - (x / 0.62) ** 2)))
    pts = K.round_poly(pts, 0.0)
    return mirror_x(pts)


def backlight():
    """top view (x, z) of the rear window, x >= 0"""
    pts = []
    # (narrower than the roof: the C-pillars are wide body-coloured sails)
    for x in np.linspace(0.0, 0.44, 8):
        pts.append((x, -0.88 + 0.03 * (1 - (x / 0.50) ** 2)))
    for i in range(0, 21):
        z = lerp(-0.90, -1.44, i / 20)
        pts.append((lerp(0.49, 0.575, (i / 20) ** 0.9), z))
    for x in np.linspace(0.545, 0.0, 9):
        pts.append((x, -1.47 - 0.02 * (1 - (x / 0.66) ** 2)))
    return mirror_x(pts)


def headlamp():
    """front view (x, y) of the headlamp opening, x >= 0: a slanted wedge from the inner tip to the wrapped outer end"""
    # a swept teardrop: narrow at the inner tip, ~0.15 m tall at the outer end where it wraps into the fender
    upper = [(0.300, 0.672), (0.34, 0.698), (0.42, 0.712), (0.52, 0.726), (0.62, 0.741), (0.70, 0.755), (0.76, 0.765),
             (0.800, 0.772)]
    end = [(0.822, 0.762), (0.832, 0.715), (0.830, 0.655)]
    lower = [(0.800, 0.622), (0.74, 0.612), (0.66, 0.616), (0.56, 0.628), (0.46, 0.642), (0.37, 0.656)]
    return K.round_poly(upper + end + lower, [0.006] + [0.0] * 6 + [0.02, 0.02, 0.02, 0.03] + [0.03, 0.0, 0.0, 0.0, 0.0, 0.012], 3)


def fog_pod():
    """front view: the recess round the fog lamp (outer lower bumper)"""
    return K.round_poly([(0.470, 0.235), (0.720, 0.245), (0.735, 0.355), (0.500, 0.370)], 0.05, 4)


def intake():
    """front view: the wide centre opening under the plate (x >= 0 half, mirrored)"""
    half = [(0.0, 0.225), (0.33, 0.228), (0.395, 0.26), (0.410, 0.33), (0.395, 0.405), (0.36, 0.43), (0.0, 0.43)]
    half = K.round_poly(half, [0, 0.04, 0.03, 0.0, 0.03, 0.03, 0], 3)
    return mirror_x(half[1:-1]) if False else mirror_x(half)


def plate_front():
    return K.round_poly([(-0.18, 0.39), (0.18, 0.39), (0.18, 0.56), (-0.18, 0.56)], 0.015, 2)


def tail_lamp():
    """rear view (x, y), x >= 0: the S15's wedge; returns (whole lens outline, amber band, reverse section)"""
    outer = [(0.300, 0.800), (0.335, 0.828), (0.430, 0.892), (0.470, 0.905), (0.760, 0.905), (0.800, 0.898), (0.818, 0.870),
             (0.818, 0.800), (0.800, 0.783), (0.760, 0.778), (0.360, 0.778), (0.318, 0.784)]
    outer = K.round_poly(outer, [0.01, 0, 0.02, 0.0, 0.0, 0.02, 0.0, 0.0, 0.02, 0.0, 0.0, 0.01], 3)
    amber = [(0.395, 0.862), (0.830, 0.862), (0.830, 0.93), (0.395, 0.93)]
    rev = [(0.25, 0.70), (0.405, 0.70), (0.405, 0.95), (0.25, 0.95)]
    return outer, amber, rev


def plate_rear():
    return K.round_poly([(-0.185, 0.395), (0.185, 0.395), (0.185, 0.585), (-0.185, 0.585)], 0.02, 3)


# ---------------------------------------------------------------- sockets (lamp housings, openings)

def socket(bm, faces, direction, depth, shrink=0.0, wall=TRIM, back=TRIM, steps=1):
    """delete the faces and sink their rim into the body along `direction` (game frame); close the back"""
    faces = [f for f in faces if f.is_valid]
    if not faces:
        return None
    fs = set(faces)
    rim = [e for f in faces for e in f.edges if sum(1 for g in e.link_faces if g in fs) == 1]
    rim = list(set(rim))
    bmesh.ops.delete(bm, geom=faces, context='FACES_ONLY')
    loose = [e for e in bm.edges if not e.link_faces]
    rim = [e for e in rim if e.is_valid and e.link_faces]
    bmesh.ops.delete(bm, geom=[e for e in loose if e.is_valid and e not in rim], context='EDGES')
    d = K.B(*direction) - K.B(0, 0, 0)
    d.normalize()
    edges = rim
    for k in range(steps):
        ext = bmesh.ops.extrude_edge_only(bm, edges=edges)
        nv = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
        ne = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMEdge)]
        nf = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMFace)]
        c = sum((v.co for v in nv), Vector()) / max(1, len(nv))
        for v in nv:
            v.co += d * depth / steps
            v.co += (c - v.co) * shrink / steps
        for f in nf:
            f.material_index = wall
            f.smooth = False
        edges = [e for e in ne if len(e.link_faces) == 1]
    fill = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    for f in fill['faces']:
        f.material_index = back
        f.smooth = False
    return fill['faces']


def arches(bm):
    """the wheel wells the arch cutter left: black; the opening's edge rolled into a small lip"""
    R = BD.ARCH_R

    def rad(p, zc):
        return math.hypot(p[1] - BD.TYRE_R, p[2] - zc)

    well = []
    for f in bm.faces:
        c = gc(f)
        if not 0.55 < abs(c[0]) < 0.99:
            continue
        for zc in (BD.AXLE_F, BD.AXLE_R):
            vs = [K.G(v.co) for v in f.verts]
            on_tube = all(abs(rad(p, zc) - R) < 0.004 for p in vs)
            on_wall = all(abs(abs(p[0]) - 0.6) < 0.002 for p in vs) and rad(c, zc) < R
            if on_tube or on_wall:
                well.append(f)
                break
    setmat(well, TRIM)
    ws = set(well)
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and sum(g in ws for g in e.link_faces) == 1]
    try:
        res = bmesh.ops.bevel(bm, geom=edges, offset=0.010, offset_type='OFFSET', profile_type='SUPERELLIPSE', segments=2,
                              profile=0.5, affect='EDGES', clamp_overlap=True)
        setmat(res['faces'], PAINT)
    except Exception as ex:   # noqa: BLE001
        print('arch lip bevel failed', ex)
    return well


# ---------------------------------------------------------------- applying them

def cut_all(bm, log=print):
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.material_index = PAINT
    # underside: dark
    for f in bm.faces:
        c, n = gc(f), gn(f)
        if n[1] < -0.55 and c[1] < 0.36:
            f.material_index = TRIM
    arches(bm)
    log('arches')
    side = lambda f: abs(gc(f)[0]) > 0.45
    upper = lambda f: gc(f)[1] > 0.84 and gn(f)[1] > 0.30
    # --- glass
    for s in (1, -1):
        # belt seal: a thin black band under the side glass
        poly = dlo()
        K.cut_outline(bm, poly, 'side', s, keep=side)
        glass = K.faces_in(bm, poly, 'side', s, keep=side)
        setmat(glass, GLASS)
        band = K.groove(bm, [(z, BD.Y10(z) + 0.0085) for z in np.linspace(0.64, -0.75, 30)], 'side', 0.011, s, keep=side)
        setmat(band, TRIM)
        setmat(K.region(bm, b_pillar(), 'side', s, keep=side), TRIM)
    log('glass sides')
    ws = windshield()
    frame = K.region(bm, ws, 'top', 1, keep=upper)
    setmat(frame, TRIM)
    inner = K.offset_poly(ws, -0.028)
    setmat(K.region(bm, inner, 'top', 1, keep=upper), GLASS)
    bl = backlight()
    setmat(K.region(bm, bl, 'top', 1, keep=upper), TRIM)
    setmat(K.region(bm, K.offset_poly(bl, -0.035), 'top', 1, keep=upper), GLASS)
    log('glass front/rear')
    # cowl panel (black) between the bonnet's rear edge and the windshield
    cowl = mirror_x([(x, 0.98 - 0.18 * (x / 0.70) ** 2.2) for x in np.linspace(0, 0.64, 8)] +
                    [(x, 1.035 - 0.18 * (x / 0.70) ** 2.2) for x in np.linspace(0.64, 0, 8)])
    setmat(K.region(bm, cowl, 'top', 1, keep=lambda f: gc(f)[1] > 0.8 and gn(f)[1] > 0.5 and f.material_index == PAINT), TRIM)
    # --- shut lines
    gaps = []
    for s in (1, -1):
        door = [(0.700, BD.Y10(0.70) - 0.004), (0.703, 0.80), (0.706, 0.64), (0.705, 0.45), (0.700, 0.30), (0.685, 0.272), (0.64, 0.262), (-0.56, 0.262), (-0.600, 0.275), (-0.615, 0.32),
                (-0.618, BD.Y10(-0.618) - 0.004)]
        gaps += K.groove(bm, door, 'side', 0.0045, s, keep=lambda f: abs(gc(f)[0]) > 0.6)
        # front bumper / fender seam (behind the lamp, down to the arch)
        gaps += K.groove(bm, [(1.705, 0.735), (1.67, 0.69), (1.635, 0.63)], 'side', 0.004, s, keep=lambda f: abs(gc(f)[0]) > 0.6)
        # rear bumper top line along the side, behind the arch
        gaps += K.groove(bm, [(-1.545, 0.62), (-1.62, 0.71), (-1.80, 0.748), (-2.05, 0.754), (-2.20, 0.755)], 'side', 0.004, s,
                         keep=lambda f: abs(gc(f)[0]) > 0.55)
    # bonnet: along the fenders and across the cowl
    for s in (1, -1):
        line = [(s * (BD.X10(z) - 0.060), z) for z in np.linspace(1.03, 1.65, 12)]
        gaps += K.groove(bm, line, 'top', 0.0045, 1, keep=upper)
    gaps += K.groove(bm, [(x, 1.037 - 0.18 * (abs(x) / 0.70) ** 2.2) for x in np.linspace(-0.66, 0.66, 25)], 'top', 0.0045, 1,
                     keep=lambda f: gc(f)[1] > 0.8 and gn(f)[1] > 0.4)
    # bonnet front edge (front view) between the lamps
    gaps += K.groove(bm, [(x, 0.684 - 0.006 * (1 - (abs(x) / 0.30) ** 2)) for x in np.linspace(-0.30, 0.30, 13)], 'front', 0.0045, 1,
                     keep=lambda f: gc(f)[2] > 1.9)
    # boot lid: across the deck at the backlight base, along the deck sides, down the rear face round the garnish
    gaps += K.groove(bm, [(x, -1.50 - 0.02 * (1 - (abs(x) / 0.66) ** 2)) for x in np.linspace(-0.64, 0.64, 25)], 'top', 0.0045,
                     1, keep=lambda f: gc(f)[1] > 0.85 and gn(f)[1] > 0.3)
    for s in (1, -1):
        gaps += K.groove(bm, [(s * 0.645, -1.50), (s * 0.66, -1.95), (s * 0.645, -2.10), (s * 0.60, -2.19)], 'top', 0.0045, 1,
                         keep=lambda f: gc(f)[1] > 0.85 and gn(f)[1] > 0.3)
    # the boot lid's trailing face (the garnish between the lamps) ends on the bumper's top line, just under the lamps
    for s in (1, -1):
        gaps += K.groove(bm, [(s * 0.30, 0.80), (s * 0.298, 0.757)], 'rear', 0.0045, -1, keep=lambda f: gc(f)[2] < -2.0)
    gaps += K.groove(bm, [(x, 0.755) for x in np.linspace(-0.84, 0.84, 30)], 'rear', 0.004, -1, keep=lambda f: gc(f)[2] < -2.0)
    # fuel lid (right side)
    fuel = K.round_poly([(-1.665, 0.795), (-1.48, 0.795), (-1.48, 0.915), (-1.665, 0.915)], 0.022, 3)
    gaps += K.groove(bm, fuel + [fuel[0]], 'side', 0.004, -1, keep=lambda f: gc(f)[0] < -0.6)
    setmat([f for f in gaps if f.material_index == PAINT], TRIM)
    log('shut lines')
    # --- lamps and openings: sockets; record the lamp centres for the parts
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromBMesh(bm)

    def surf(x, y, z0=4.0):
        loc, n, _, _ = bvh.ray_cast(K.B(x, y, z0), K.B(0, 0, -1) - K.B(0, 0, 0))
        return (Vector(K.G(loc)), Vector(K.G(n))) if loc else (None, None)

    info = {'head': [], 'fog': []}
    for s_, poly in zip((1, -1), both(headlamp())):
        for xx in (0.53, 0.665):
            yy = 0.5 * (np.interp(xx, [p[0] for p in headlamp()[:8]], [p[1] for p in headlamp()[:8]]) + 0.66 + 0.02 * (xx - 0.4))
            p, n = surf(s_ * xx, yy)
            info['head'].append((p, n))
        kp = lambda f, s_=s_: gc(f)[0] * s_ > 0.2 and gc(f)[2] > 1.4
        K.region(bm, poly, 'front', 1, keep=kp, min_facing=0.03)
        K.cut_outline(bm, K.offset_poly(poly, -0.007), 'front', 1, keep=kp, min_facing=0.03)
        lens = K.faces_in(bm, poly, 'front', 1, keep=kp, min_facing=0.03)
        inner = set(K.faces_in(bm, K.offset_poly(poly, -0.007), 'front', 1, keep=kp, min_facing=0.03))
        setmat([f for f in lens if f not in inner], TRIM)
        setmat(inner, HEAD)
        K.sink(bm, list(inner), 0.003)
    for s_, poly in zip((1, -1), both(fog_pod())):
        p, n = surf(s_ * 0.585, 0.302)
        info['fog'].append((p, n))
        fs = K.region(bm, poly, 'front', 1, keep=lambda f, s_=s_: gc(f)[0] * s_ > 0.3 and gc(f)[2] > 1.7)
        socket(bm, fs, (0, 0, -1), 0.045, 0.12, wall=TRIM, back=TRIM)
    fs = K.region(bm, intake(), 'front', 1, keep=lambda f: gc(f)[2] > 1.8 and gc(f)[1] < 0.5)
    socket(bm, fs, (0, 0.05, -1), 0.09, 0.08, wall=TRIM, back=TRIM, steps=2)
    info['plate_f'] = surf(0.0, 0.475)
    holes = info
    outer, amber, rev = tail_lamp()
    for s, poly in zip((1, -1), both(outer)):
        lens = K.region(bm, poly, 'rear', -1, keep=lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9, min_facing=0.08)
        rim = K.faces_in(bm, K.offset_poly(poly, -0.006), 'rear', -1, keep=lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9,
                         min_facing=0.08)
        K.cut_outline(bm, K.offset_poly(poly, -0.006), 'rear', -1, keep=lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9, min_facing=0.08)
        lens = K.faces_in(bm, poly, 'rear', -1, keep=lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9, min_facing=0.08)
        inner = set(K.faces_in(bm, K.offset_poly(poly, -0.006), 'rear', -1, keep=lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9,
                               min_facing=0.08))
        setmat([f for f in lens if f not in inner], TRIM)
        setmat(inner, TAIL)
        am = amber if s > 0 else [(-u, v) for u, v in reversed(amber)]
        rv = rev if s > 0 else [(-u, v) for u, v in reversed(rev)]
        K.cut_outline(bm, am, 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08)
        setmat(K.faces_in(bm, am, 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08), AMBER)
        K.cut_outline(bm, rv, 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08)
        setmat(K.faces_in(bm, rv, 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08), CLEAR)
    loc, n, _, _ = bvh.ray_cast(K.B(0.0, 0.49, -4.0), K.B(0, 0, 1) - K.B(0, 0, 0))
    info['plate_r'] = (Vector(K.G(loc)), Vector(K.G(n)))
    log('lamps and openings')
    # merge the flat fragments the cuts left (per material), to save triangles
    n0 = len(bm.faces)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.8), use_dissolve_boundaries=False, verts=list(bm.verts),
                             edges=list(bm.edges), delimit={'MATERIAL'})
    log(f'dissolve {n0} -> {len(bm.faces)} faces')
    return holes
