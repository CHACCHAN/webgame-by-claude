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
MATS = ['paint', 'trim', 'glass', 'chrome', 'amber', 'lens_clear', 'taillight', 'interior', 'headlight', 'lens_inner']
PAINT, TRIM, GLASS, CHROME, AMBER, CLEAR, TAIL, INTERIOR, HEAD, CLEAR_IN = range(len(MATS))


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
    """top view (x, z) of the rear window, x >= 0: its top and bottom edges run at constant heights (~1.225 and ~0.966)
    across the crowned roof and deck, straight in the rear view, so in plan they bow rearwards at the centre
    (ray hits on r30: bottom centre z -1.675, corners (0.62, -1.44) and (0.51, -0.86))"""
    top = [(0.0, -1.000), (0.15, -0.988), (0.30, -0.950), (0.42, -0.902), (0.50, -0.861)]
    side = [(0.578, -0.925), (0.600, -1.10), (0.612, -1.30), (0.622, -1.44)]
    bottom = [(x, -1.675 + 0.57 * x * x) for x in (0.58, 0.45, 0.30, 0.15, 0.0)]
    pts = K.round_poly(top + side + bottom, [0, 0, 0, 0, 0.05, 0.03, 0, 0, 0.04, 0.02, 0, 0, 0, 0], 3)
    return mirror_x(pts)


def headlamp():
    """front view (x, y) of the headlamp opening, x >= 0: a long lens under the bonnet's edge, its top edge nearly
    level, ~10 cm tall, a blunt rounded inner end beside the grille and a rounder, taller outer end.
    Lamp review 2026-11-10: the lens outlines traced on r43 (right lamp) and r10 (left lamp), carried back onto the
    fitted body through the solved cameras and averaged here. The old lens ran out to a low pointed tip at x 0.285 and
    its top edge fell 3-4 cm too low over the inner half; on both photos the inner end is blunt at x ~0.34, as tall as
    the middle"""
    upper = [(0.345, 0.636), (0.372, 0.656), (0.42, 0.672), (0.47, 0.678), (0.52, 0.681), (0.60, 0.687), (0.67, 0.694),
             (0.72, 0.698), (0.752, 0.694)]
    end = [(0.775, 0.680), (0.785, 0.652), (0.780, 0.622), (0.764, 0.603)]
    lower = [(0.70, 0.590), (0.62, 0.586), (0.52, 0.587), (0.42, 0.590), (0.375, 0.594), (0.350, 0.604), (0.340, 0.620)]
    return K.round_poly(upper + end + lower, [0.010] + [0.0] * 7 + [0.015, 0.015, 0.015, 0.02, 0.02] + [0.0] * 4
                        + [0.008, 0.010, 0.010], 3)


HEAD_UNITS = ((0.559, 0.629), (0.428, 0.634))     # the projector low beam, the high-beam reflector (front view)


def fog_pod():
    """front view: the oval recess round the fog lamp, the lamp at its inboard end (triangulated on r10 / r43)"""
    return K.round_poly([(0.455, 0.352), (0.475, 0.405), (0.55, 0.420), (0.650, 0.410), (0.690, 0.362), (0.665, 0.305),
                         (0.600, 0.292), (0.490, 0.290)], [0.035, 0.03, 0.03, 0.035, 0.03, 0.03, 0.03, 0.035], 4)


FOG_LAMP = (0.528, 0.357)               # the round fog lamp's centre (front view, x >= 0), radius ~0.04
PLATE_F = 0.415                          # the front plate's centre height (it hangs over the mouth's upper half)


def intake():
    """front view: the wide shallow mouth under the bonnet's point (x >= 0 half, mirrored): a flat top hidden behind the
    plate, rounded D-shaped ends, the bottom on the chin's crease (triangulated on r10 / r43)"""
    half = [(0.0, 0.272), (0.24, 0.272), (0.292, 0.282), (0.326, 0.315), (0.338, 0.362), (0.330, 0.410), (0.305, 0.438),
            (0.26, 0.449), (0.0, 0.453)]
    half = K.round_poly(half, [0, 0.03, 0.02, 0.0, 0.02, 0.02, 0.02, 0.02, 0], 3)
    return mirror_x(half)


def plate_front():
    return K.round_poly([(-0.18, 0.33), (0.18, 0.33), (0.18, 0.50), (-0.18, 0.50)], 0.015, 2)


def tail_lamp():
    """rear view (x, y), x >= 0, measured on the rear-on photo r48 (rays onto the fitted body, field undone): the S15's
    swept wedge, a black bezel round it; returns (outline, amber band above the divider, divider, reverse lamp)"""
    sweep = [(0.334, 0.731), (0.353, 0.751), (0.377, 0.777), (0.410, 0.810), (0.446, 0.843), (0.487, 0.870), (0.527, 0.885)]
    top = [(0.580, 0.892), (0.657, 0.893), (0.736, 0.887), (0.790, 0.876)]
    end = [(0.812, 0.852), (0.823, 0.808), (0.817, 0.769), (0.792, 0.733)]
    bottom = [(0.746, 0.728), (0.642, 0.727), (0.499, 0.728), (0.387, 0.727)]
    outer = K.round_poly(sweep + top + end + bottom, [0.006, 0, 0, 0, 0, 0.015, 0.02, 0, 0, 0, 0.02, 0.02, 0, 0, 0.02,
                                                      0, 0, 0, 0.012], 3)
    amber = [(0.40, 0.95), (0.40, 0.87), (0.47, 0.852), (0.52, 0.836), (0.65, 0.830), (0.87, 0.827), (0.87, 0.95)]
    divider = [(0.40, 0.817), (0.65, 0.812), (0.87, 0.806), (0.87, 0.827), (0.65, 0.830), (0.52, 0.836), (0.47, 0.852),
               (0.40, 0.87)]
    # the reverse lamp (lamp review 2026-11-10: both lamps traced on r48, carried back onto the body and averaged): a
    # wedge, its inner edge parallel to the lens's sweep, a sharp tip at the inner bottom, the outer end round
    rev = K.round_poly([(0.383, 0.752), (0.395, 0.745), (0.420, 0.745), (0.448, 0.748), (0.466, 0.753), (0.476, 0.766),
                        (0.478, 0.780), (0.474, 0.791), (0.458, 0.794), (0.439, 0.792), (0.421, 0.784), (0.403, 0.772)],
                       [0.004, 0.004, 0, 0, 0.008, 0.004, 0, 0.007, 0.004, 0, 0, 0.004], 3)
    return outer, amber, divider, rev, sweep


def plate_rear():
    """the recess the rear plate sits in (rear view, r48)"""
    return K.round_poly([(-0.200, 0.378), (0.200, 0.378), (0.203, 0.585), (-0.203, 0.585)], 0.025, 3)


# ---------------------------------------------------------------- sockets (lamp housings, openings)

def crease(bm, line, proj, side, width, depth, edge, keep=None):
    """a character line: cut a strip along the line and push one of its edges into the body, so the strip becomes a
    facet facing down ('low': its lower edge goes in, a shadowed crease under an overhang) or up ('high': a lit step)"""
    strip = K.groove(bm, line, proj, width, side, keep=keep)
    vs = {v for f in strip for v in f.verts}
    if not vs:
        return strip
    ys = [K.G(v.co)[1] for v in vs]
    mid = 0.5 * (min(ys) + max(ys))
    bm.normal_update()
    for v in vs:
        y = K.G(v.co)[1]
        if (edge == 'low' and y < mid) or (edge == 'high' and y > mid):
            v.co -= v.normal * depth
    return strip


def socket(bm, faces, direction, depth, shrink=0.0, wall=TRIM, back=TRIM, steps=1, walls=None):
    """delete the faces and sink their rim into the body along `direction` (game frame); close the back
    (walls: a material per step, e.g. a body-coloured return before the black)"""
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
            f.material_index = wall if walls is None else walls[k]
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
        gaps += K.groove(bm, [(1.725, 0.640), (1.685, 0.598), (1.630, 0.555)], 'side', 0.004, s, keep=lambda f: abs(gc(f)[0]) > 0.6)
        # rear bumper top line along the side, behind the arch
        gaps += K.groove(bm, [(-1.545, 0.60), (-1.62, 0.68), (-1.80, 0.713), (-2.05, 0.719), (-2.20, 0.720)], 'side', 0.004, s,
                         keep=lambda f: abs(gc(f)[0]) > 0.55)
    # bonnet: along the fenders and across the cowl
    for s in (1, -1):
        line = [(s * (BD.X10(z) - 0.060), z) for z in np.linspace(1.03, 1.70, 13)]
        gaps += K.groove(bm, line, 'top', 0.0045, 1, keep=upper)
    gaps += K.groove(bm, [(x, 1.037 - 0.18 * (abs(x) / 0.70) ** 2.2) for x in np.linspace(-0.66, 0.66, 25)], 'top', 0.0045, 1,
                     keep=lambda f: gc(f)[1] > 0.8 and gn(f)[1] > 0.4)
    # bonnet front edge (front view) between the lamps
    # (out to the lamps' blunt inner ends at x ±0.34, lamp review 2026-11-10)
    gaps += K.groove(bm, [(x, 0.618 - 0.018 * (abs(x) / 0.30) ** 1.5) for x in np.linspace(-0.34, 0.34, 15)], 'front', 0.0045, 1,
                     keep=lambda f: gc(f)[2] > 1.9)
    # boot lid: across the deck at the backlight base, along the deck sides, down the rear face round the garnish
    gaps += K.groove(bm, [(x, -1.708 + 0.57 * x * x) for x in np.linspace(-0.645, 0.645, 25)], 'top', 0.0045,
                     1, keep=lambda f: gc(f)[1] > 0.85 and gn(f)[1] > 0.3)
    for s in (1, -1):
        gaps += K.groove(bm, [(s * 0.645, -1.47), (s * 0.66, -1.95), (s * 0.645, -2.10), (s * 0.60, -2.19)], 'top', 0.0045, 1,
                         keep=lambda f: gc(f)[1] > 0.85 and gn(f)[1] > 0.3)
    # the boot lid's trailing face runs between the lamps' swept bezels down to the bumper's top line under the lamps
    gaps += K.groove(bm, [(x, 0.720) for x in np.linspace(-0.84, 0.84, 30)], 'rear', 0.004, -1, keep=lambda f: gc(f)[2] < -2.0)
    # fuel lid (right side)
    fuel = K.round_poly([(-1.683, 0.685), (-1.488, 0.685), (-1.488, 0.815), (-1.683, 0.815)], 0.024, 3)
    gaps += K.groove(bm, fuel + [fuel[0]], 'side', 0.004, -1, keep=lambda f: gc(f)[0] < -0.6)
    setmat([f for f in gaps if f.material_index == PAINT], TRIM)
    # the side's lower character line between the arches, a lit step (r14), and the amber side markers behind the front
    # arches (triangulated on r10 / r43)
    for s in (1, -1):
        crease(bm, [(z, 0.4325 - 0.0185 * z) for z in np.linspace(-0.91, 0.91, 40)], 'side', s, 0.012, 0.006, 'high',
               keep=lambda f: abs(gc(f)[0]) > 0.6)
        mk = K.round_poly([(0.873, 0.533), (0.849, 0.531), (0.836, 0.565), (0.860, 0.567)], 0.006, 2)
        setmat(K.region(bm, mk, 'side', s, keep=lambda f: abs(gc(f)[0]) > 0.6 and 0.75 < gc(f)[2] < 0.95), AMBER)
    # the chin's crease beside the mouth, under the fog lamp pods: a lit step
    for s in (1, -1):
        crease(bm, [(s * x, 0.268) for x in np.linspace(0.35, 0.80, 16)], 'front', 1, 0.014, 0.010, 'high',
               keep=lambda f: gc(f)[2] > 1.6)
    log('shut lines')
    # --- lamps and openings: sockets; record the lamp centres for the parts
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromBMesh(bm)

    def surf(x, y, z0=4.0):
        loc, n, _, _ = bvh.ray_cast(K.B(x, y, z0), K.B(0, 0, -1) - K.B(0, 0, 0))
        return (Vector(K.G(loc)), Vector(K.G(n))) if loc else (None, None)

    info = {'head': [], 'fog': []}
    for s_, poly in zip((1, -1), both(headlamp())):
        for xx, yy in HEAD_UNITS:
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
        p, n = surf(s_ * FOG_LAMP[0], FOG_LAMP[1])
        info['fog'].append((p, n))
        fs = K.region(bm, poly, 'front', 1, keep=lambda f, s_=s_: gc(f)[0] * s_ > 0.3 and gc(f)[2] > 1.7)
        socket(bm, fs, (0, 0, -1), 0.04, 0.10, wall=TRIM, back=TRIM)
    # the plate hangs in front of the mouth's upper half: its depth from the face just above the mouth
    pf, nf_ = surf(0.0, 0.48)
    if pf is not None:
        pf = Vector((0.0, PLATE_F, pf.z))
    info['plate_f'] = (pf, nf_)
    # the mouth: a body-coloured return (the chin's shelf shows at its bottom), then black
    fs = K.region(bm, intake(), 'front', 1, keep=lambda f: gc(f)[2] > 1.8 and gc(f)[1] < 0.5)
    socket(bm, fs, (0, 0, -1), 0.11, 0.06, wall=TRIM, back=TRIM, steps=3, walls=[PAINT, TRIM, TRIM])
    holes = info
    outer, amber, divider, rev, sweep = tail_lamp()
    for s, poly in zip((1, -1), both(outer)):
        kp = lambda f, s=s: gc(f)[0] * s > 0.2 and gc(f)[2] < -1.9
        lens = K.region(bm, poly, 'rear', -1, keep=kp, min_facing=0.08)
        K.cut_outline(bm, K.offset_poly(poly, -0.007), 'rear', -1, keep=kp, min_facing=0.08)
        lens = K.faces_in(bm, poly, 'rear', -1, keep=kp, min_facing=0.08)
        inner = set(K.faces_in(bm, K.offset_poly(poly, -0.007), 'rear', -1, keep=kp, min_facing=0.08))
        setmat([f for f in lens if f not in inner], TRIM)
        setmat(inner, TAIL)
        mir = (lambda q: q) if s > 0 else (lambda q: [(-u, v) for u, v in reversed(q)])
        # the bezel is wider along the swept inner edge
        sw = [(s * u, v) for u, v in sweep]
        setmat(K.groove(bm, sw, 'rear', 0.016, -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08), TRIM)
        for q, mat in ((amber, AMBER), (divider, TRIM), (rev, CLEAR)):
            K.cut_outline(bm, mir(q), 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08)
            setmat(K.faces_in(bm, mir(q), 'rear', -1, keep=lambda f: f.material_index == TAIL, min_facing=0.08), mat)
        # inside the reverse lamp's bright clear rim: the grey, fluted reflector (r48)
        ri = K.offset_poly(mir(rev), -0.005)
        K.cut_outline(bm, ri, 'rear', -1, keep=lambda f: f.material_index == CLEAR, min_facing=0.08)
        setmat(K.faces_in(bm, ri, 'rear', -1, keep=lambda f: f.material_index == CLEAR, min_facing=0.08), CLEAR_IN)
    # rear bumper: the roll under the lamps overhangs a shadowed crease; a fine line at the plate's top; the plate recess
    rear = lambda f: gc(f)[2] < -1.95 and abs(gc(f)[0]) < 0.86
    crease(bm, [(x, 0.656) for x in np.linspace(-0.86, 0.86, 40)], 'rear', -1, 0.020, 0.015, 'low', keep=rear)
    crease(bm, [(x, 0.518) for x in np.linspace(-0.86, 0.86, 40)], 'rear', -1, 0.010, 0.005, 'high', keep=rear)
    pr = K.region(bm, plate_rear(), 'rear', -1, keep=lambda f: gc(f)[2] < -2.0)
    socket(bm, pr, (0, 0, 1), 0.016, 0.0, wall=PAINT, back=PAINT)
    bvh = BVHTree.FromBMesh(bm)
    loc, n, _, _ = bvh.ray_cast(K.B(0.0, 0.485, -4.0), K.B(0, 0, 1) - K.B(0, 0, 0))
    info['plate_r'] = (Vector(K.G(loc)), Vector(K.G(n)))
    log('lamps and openings')
    # merge the flat fragments the cuts left (per material), to save triangles
    n0 = len(bm.faces)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.8), use_dissolve_boundaries=False, verts=list(bm.verts),
                             edges=list(bm.edges), delimit={'MATERIAL'})
    log(f'dissolve {n0} -> {len(bm.faces)} faces')
    return holes
