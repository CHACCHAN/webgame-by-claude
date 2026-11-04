"""
JR East E231 series 0番台 as converted for the Musashino Line (MU sets): the underfloor equipment of the cab cars
クハE231 (Tc) and クハE230 (Tc') and of the VVVF motor car モハE231 (M). A part module for the Blender model
(train_kit.Part, the game's car frame, material prefix `eu_`).

  underfloor_tc(part, car='E231', cab_at_plus_z=True)  car0 (car='E231') / car2 (car='E230'): distribution boxes,
                                                      BCU, air tanks, battery box, small boxes beyond the bogies
  underfloor_m(part)                                  car1: VVVF inverter (SC60A look, stainless fin coolers), filter
                                                      reactor, line breaker / HB box, blower box, BCU, air tanks
  underframe(part, z0, z1)                            cross members, brake pipes and wire conduits between the boxes
  add_materials(m)

Each returns the number of triangles it added. The car functions call `underframe` for the whole car themselves
(`with_frame=False` leaves it out). Everything stays at y ≤ 0.985 (body side bottom ≈ 1.00), |x| ≤ 1.26,
y ≥ 0.33, and out of the bogie zones z = ±6.9 ± 1.7 (only frame members and pipes cross them, at y ≥ 0.93).
`cab_at_plus_z=False` turns the car round (half a turn about the vertical axis: x → −x, z → −z). The assembly builds
car2 with its cab at +z and turns the whole car, so it normally stays True.

Run directly with Blender it renders test images on a placeholder body with bogie blocks:
  blender -t 4 --background --factory-startup --python parts/e231_underfloor.py -- <outdir> [tc|tc2|m|all] [--clay]
  (env UF_VIEWS=right,left,... picks views)

Sources (photos in the helper's scratch folder, Wikimedia Commons; "est." = estimated, "assumed" = no photo):
- Box style (photos "JR-East-E231-TIMSbox.jpg", "-SC61A.jpg", "-SC62A.jpg", "JR-East-E231-500-ATC.jpg", The RW place,
  CC BY-SA 3.0): flat grey lids with narrow gaps, two vertical hold-down bars from the top edge on each lid, round
  lever latches along the bottom edge, small blank plates; boxes hang on brackets ≈ 0.12 m below the body side.
- Colour: lids and boxes a medium warm grey (TIMS box photo ≈ #888783 in shade, SC61A ≈ #7a7267); in service they are
  brake-dust brown (Musashino photos p10–p17) but the fresh 2017 conversion (p08) is a plain mid grey: we use a clean
  grey a shade darker than the TIMS box; frames, hangers and pipes dark grey.
- Heights: box tops at y 0.88, bottoms 0.34–0.38 (TIMS / ATC photos: lid ≈ 0.52 m tall, the lids start ≈ 0.12 m
  below the side sill; scaled from the 1300 mm door: est.).
- TIMS distribution box (クハE231, photo "TIMSbox": five lids ATS-P / IMS / NFB / GS / ATS, widths in the ratio
  240 : 205 : 163 : 277 : 230 px → 0.55 / 0.47 / 0.38 / 0.64 / 0.53 m, 2.6 m in all, est. from the 2.3 mm/px scale).
  It is shown on the RIGHT side (x < 0): the side seen in the Musashino photos p10 / p11 / p17 (train running towards
  Minami-Funabashi = クハE231 leading, its right side towards the camera), which show a tall lidded box, a darker
  box and a horizontal tank with a domed end and fittings towards the cab. The order along the car follows those
  photos; the exact z positions are est. (the 3/4 views cannot be mapped reliably).
- ATS-SN box on クハE231 (the Musashino conversion added ATS-SN beside ATS-P: ja.wikipedia), small, RIGHT side,
  next to the TIMS box: assumed.
- クハE230 LEFT side (photo "Kuha E230-11 Mitaka Rolling Stock Center 20211101.jpg"): behind the cab bogie a large
  tank set inboard, a tall narrow lidded box, a dark inboard box, a lighter box and a small box with a handle, then
  little before the rear bogie. Its RIGHT side (battery box, BCU): assumed.
- モハE231 VVVF (photo "JR-East-E231-SC60A.jpg", モハE231-18): centre lid (≈ 0.80 m, two handle slots, blank
  plates) between two groups of three stainless fin coolers (each ≈ 0.31 × 0.55 m, a 2 × 2 grid of fine mesh panels,
  ≈ 0.04 m gaps), ≈ 3.3 m in all (scaled from the body side to rail gap, est.). The Musashino conversion renewed the
  control equipment (ja.wikipedia: 制御装置などの機器を更新); p12 (MU7) still shows mesh fin modules of this kind
  on the M car, so the SC60A look is kept. Fins on the RIGHT side: assumed (the photo's side is not known).
- Blower box with a round mesh grille at the モハE231's end towards クハE231 (p08, p11, p17: right side, just
  beyond the first bogie of the second car): ≈ 0.85 m long, round grille ∅ 0.30 (est.).
- Filter reactor, line breaker / HB box, BCU, air tanks, junction boxes: sizes and places est. after the 209 /
  E231 family (tank ∅ 0.34–0.46 m with domed ends and straps).
- Frame: cross members every 1.2 m, brake / main reservoir pipes ∅ 40 mm at x = ±0.50, wire conduits ∅ 50 mm at
  x = ±1.05 (est.).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
try:
    import train_kit as K
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import train_kit as K

B = K.B
X = 1.26            # outer face of the widest boxes (body bottom ≈ ±1.415)
TOP = 0.88          # box tops
HANG = 0.985        # hanger tops (just under the body side bottom, 1.00)
BOT = 0.36          # usual box bottom

MATS = {
    # name: (colour, metallic, roughness)
    'eu_box': ('#64645f', 0.30, 0.60),     # box shells: mid warm grey paint (TIMS / SC61A photos, p08)
    'eu_lid': ('#73736d', 0.30, 0.55),     # lids, a shade lighter
    'eu_fin': ('#a3a5a2', 0.85, 0.38),     # stainless fin coolers, grille frames
    'eu_steel': ('#36373a', 0.55, 0.60),   # frame, hangers, pipes, straps, tanks' fittings
    'eu_hw': ('#b1b3b4', 0.85, 0.30),      # latches, plates: bright steel
    'eu_dark': ('#121314', 0.20, 0.80),    # gaps, mesh depth, cables
}


def add_materials(m):
    for name, (colour, metallic, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, colour, metallic, rough)


# ---------------------------------------------------------------- primitives (game frame, flat shaded unless noted)
def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _box(p, mat, x0, x1, y0, y1, z0, z1, c=0.0, skip=()):
    """box with chamfered edges (one segment); `skip` leaves out unchamfered faces nobody sees ('top', 'bottom')"""
    if x0 > x1:
        x0, x1 = x1, x0
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = B((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.z * (y1 - y0), (z0 + z1) / 2 - v.co.y * (z1 - z0))
    if c > 0:
        c = min(c, 0.4 * (x1 - x0), 0.4 * (y1 - y0), 0.4 * (z1 - z0))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=c, segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
    elif skip:
        bm.normal_update()
        kill = []
        for f in bm.faces:
            n = f.normal
            if ('top' in skip and n.z > 0.9) or ('bottom' in skip and n.z < -0.9):
                kill.append(f)
        bmesh.ops.delete(bm, geom=kill, context='FACES_ONLY')
    p.merge(bm, mat, smooth=False)


def _solid(p, mat, verts, faces, smooth=False):
    """convex solid from game-frame points; faces get outward normals"""
    bm = bmesh.new()
    vs = [bm.verts.new(B(*v)) for v in verts]
    cen = sum((Vector(v) for v in verts), Vector()) / len(verts)
    for f in faces:
        pts = [Vector(verts[i]) for i in f]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        fc = sum(pts, Vector()) / len(pts)
        idx = list(f) if n.dot(fc - cen) >= 0 else list(reversed(f))
        bm.faces.new([vs[i] for i in idx])
    p.merge(bm, mat, smooth)


def _extrude(p, mat, axis, poly, a0, a1):
    """a convex polygon extruded: axis 'x' → poly in (z, y) from x = a0 to a1; 'z' → poly in (x, y) from z = a0 to a1"""
    n = len(poly)
    if axis == 'x':
        verts = [(a0, y, z) for z, y in poly] + [(a1, y, z) for z, y in poly]
    else:
        verts = [(x, y, a0) for x, y in poly] + [(x, y, a1) for x, y in poly]
    faces = [list(range(n)), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    _solid(p, mat, verts, faces)


def _ngon(cx, cy, r, n, rot=0.0):
    return [(cx + r * math.cos(rot + 2 * math.pi * i / n), cy + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def _lathe(p, mat, axis, c, prof, n=16, smooth=True):
    """surface of revolution around a game axis through c; prof = [(t along the axis, radius)]; convex bodies only"""
    bm = bmesh.new()
    rings = []
    for t, r in prof:
        if r < 1e-9:
            pt = (c[0], c[1], c[2] + t) if axis == 'z' else (c[0] + t, c[1], c[2])
            rings.append([bm.verts.new(B(*pt))] * n)
            continue
        ring = []
        for j in range(n):
            a = 2 * math.pi * j / n
            u, v = r * math.cos(a), r * math.sin(a)
            pt = (c[0] + u, c[1] + v, c[2] + t) if axis == 'z' else (c[0] + t, c[1] + u, c[2] + v)
            ring.append(bm.verts.new(B(*pt)))
        rings.append(ring)
    cb = B(*c)
    for i in range(len(prof) - 1):
        for j in range(n):
            j1 = (j + 1) % n
            vs = []
            for v in (rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]):
                if v not in vs:
                    vs.append(v)
            if len(vs) < 3:
                continue
            f = bm.faces.new(vs)
            f.normal_update()
            if f.normal.dot(f.calc_center_median() - cb) < 0:
                f.normal_flip()
    p.merge(bm, mat, smooth)


def _pipe(p, mat, axis, centre, r, length, n=8):
    p.cylinder(mat, centre, r, length, axis=axis, segments=n, cap=False)


def _run(p, mat, start, moves, r, n=8):
    """an axis-aligned pipe run: start (x, y, z), moves [(axis, delta)]; the segments overlap at the elbows"""
    cur = list(start)
    for axis, d in moves:
        i = 'xyz'.index(axis)
        end = list(cur)
        end[i] += d
        centre = tuple((a + b) / 2 for a, b in zip(cur, end))
        _pipe(p, mat, axis, centre, r, abs(d) + 2 * r, n)
        cur = end
    return cur


# ---------------------------------------------------------------- hardware on a side face
# a face has its outward direction s (+1: x > 0, the car's left) and sits at x = xf; xo = the surface of a lid on it
def _latch(p, s, xo, zc, yc):
    """round lever latch at a lid's bottom edge: a disc and a short bar (TIMS / ATC photos)"""
    _extrude(p, 'eu_hw', 'x', _ngon(zc, yc, 0.026, 8), xo, xo + s * 0.008)
    _box(p, 'eu_hw', xo + s * 0.008, xo + s * 0.022, yc - 0.010, yc + 0.030, zc - 0.007, zc + 0.007)


def _holdbar(p, s, xo, zc, y1, length):
    """the vertical hold-down bar hanging from a lid's top edge, with a thicker lower part (TIMS photo)"""
    _box(p, 'eu_box', xo, xo + s * 0.014, y1 - length, y1 + 0.02, zc - 0.011, zc + 0.011)
    _box(p, 'eu_box', xo, xo + s * 0.024, y1 - length, y1 - length + 0.075, zc - 0.016, zc + 0.016)


def _plate(p, s, xo, zc, yc, w=0.11, h=0.032):
    """a blank name plate (no lettering)"""
    _box(p, 'eu_hw', xo, xo + s * 0.003, yc - h / 2, yc + h / 2, zc - w / 2, zc + w / 2)


def _lid(p, s, xf, z0, z1, y0, y1, mat='eu_lid', bars=True, latches=None, plate=True, big_plate=False, rib=False,
         t=0.010):
    """an E231 lid: gap round it, the raised panel, two hold-down bars from the top edge, round latches along the
    bottom edge, an optional blank plate in the middle and a horizontal stiffening rib (ATC photo)"""
    w, h = z1 - z0, y1 - y0
    xo = xf + s * t
    _box(p, 'eu_dark', xf, xf + s * 0.004, y0 - 0.007, y1 + 0.007, z0 - 0.007, z1 + 0.007)
    _box(p, mat, xf, xo, y0, y1, z0, z1, c=0.003)
    zc = (z0 + z1) / 2
    if bars:
        for zz in ((z0 + 0.17 * w, z1 - 0.17 * w) if w > 0.3 else (zc,)):
            _holdbar(p, s, xo, zz, y1, 0.55 * h)
    if latches is None:
        latches = 3 if w > 0.75 else (2 if w > 0.28 else 1)
    for k in range(latches):
        zz = zc if latches == 1 else z0 + 0.12 * w + (w * 0.76) * k / (latches - 1)
        _latch(p, s, xo, zz, y0 + 0.050)
    if plate:
        _plate(p, s, xo, zc, y0 + 0.30 * h)
    if big_plate:
        _plate(p, s, xo, zc, y1 - 0.20 * h, w=0.20, h=0.05)
    if rib:
        _box(p, mat, xo, xo + s * 0.010, y0 + 0.32 * h, y0 + 0.32 * h + 0.012, z0 + 0.05, z1 - 0.05)


def _hangers(p, s, xf, z0, z1, zs):
    """mounting rail along the top edge of a box face and hanger plates up to the underframe"""
    _box(p, 'eu_steel', xf, xf - s * 0.08, TOP, TOP + 0.035, z0 - 0.015, z1 + 0.015, c=0.004)
    for z in zs:
        _extrude(p, 'eu_steel', 'x', [(z - 0.06, TOP), (z + 0.06, TOP), (z + 0.035, HANG), (z - 0.035, HANG)],
                 xf - s * 0.012, xf + s * 0.002)


def _flange(p, x0, x1, z0, z1, y=None):
    """the bottom flange of a box"""
    y = BOT if y is None else y
    _box(p, 'eu_steel', x0 - 0.008, x1 + 0.008, y - 0.006, y + 0.03, z0 - 0.008, z1 + 0.008, skip=('top',))


def _cabinet(p, s, x_in, z0, z1, y0, lids, y1=TOP, hang=None, mat='eu_box', lidmat='eu_lid', flange=True, **kw):
    """a box from x_in to the side (x = s·X) with lids on its outer face; lids = [(z0, z1, opts)]"""
    xf = s * X
    _box(p, mat, x_in, xf, y0, y1, z0, z1, c=0.010)
    if flange:
        _flange(p, min(x_in, xf), max(x_in, xf), z0, z1, y0)
    for a, b, opts in lids:
        o = dict(kw)
        o.update(opts)
        _lid(p, s, xf, a, b, y0 + 0.020, y1 - 0.025, mat=lidmat, **o)
    _hangers(p, s, xf, z0, z1, hang or (z0 + 0.10, z1 - 0.10))


def _small_box(p, s, x0, x1, y0, y1, z0, z1, lids=1, mat='eu_box', lidmat='eu_lid'):
    """a junction box with lids on its outer face"""
    _box(p, mat, x0, x1, y0, y1, z0, z1, c=0.008)
    xf = x1 if s > 0 else x0
    n = max(1, lids)
    zw = (z1 - z0 - 0.04) / n
    for k in range(n):
        a = z0 + 0.02 + k * zw
        _lid(p, s, xf, a + 0.01, a + zw - 0.01, y0 + 0.03, y1 - 0.03, mat=lidmat, plate=False, latches=1 if zw < 0.4 else 2)
    _hangers(p, s, xf, z0, z1, (z0 + 0.06, z1 - 0.06))
    # hangers of a short box reach from its own top
    if y1 < TOP - 0.01:
        for z in (z0 + 0.06, z1 - 0.06):
            _box(p, 'eu_steel', xf - s * 0.012, xf + s * 0.002, y1 - 0.02, TOP, z - 0.025, z + 0.025)


def _tank(p, centre, r, length, axis, straps=(-0.3, 0.3), n=14, mat='eu_lid', drain=True):
    """air tank with domed ends, straps and hanger bars up to the frame"""
    d = 0.42 * r
    half = length / 2
    prof = [(-half + d * (1 - math.cos(a)), r * math.sin(a)) for a in (0, 0.5, 1.0, 1.35, math.pi / 2)]
    prof += [(-t, rr) for t, rr in reversed(prof[:-1])]
    prof = sorted(prof, key=lambda q: q[0])
    _lathe(p, mat, axis, centre, prof, n=n, smooth=True)
    cx, cy, cz = centre
    for k in straps:
        t0 = k * length
        prof_s = [(t0 - 0.03, r), (t0 - 0.03, r + 0.012), (t0 + 0.03, r + 0.012), (t0 + 0.03, r)]
        _lathe(p, 'eu_steel', axis, centre, prof_s, n=n, smooth=False)
        if axis == 'z':
            _box(p, 'eu_steel', cx - 0.02, cx + 0.02, cy + r * 0.7, HANG, cz + t0 - 0.015, cz + t0 + 0.015)
        else:
            _box(p, 'eu_steel', cx + t0 - 0.015, cx + t0 + 0.015, cy + r * 0.7, HANG, cz - 0.02, cz + 0.02)
    if drain:
        if axis == 'z':
            _box(p, 'eu_steel', cx - 0.022, cx + 0.022, cy - r - 0.03, cy - r + 0.005, cz + half * 0.6 - 0.022, cz + half * 0.6 + 0.022)
        else:
            _box(p, 'eu_steel', cx + half * 0.6 - 0.022, cx + half * 0.6 + 0.022, cy - r - 0.03, cy - r + 0.005, cz - 0.022, cz + 0.022)


def _valve_cluster(p, x, y, z, s_z=1):
    """fittings on a tank's end (p08 / p11: a cluster of cocks and a pipe on the cab-side end of the tank)"""
    _pipe(p, 'eu_steel', 'z', (x, y, z + s_z * 0.04), 0.035, 0.09, n=8)
    _box(p, 'eu_steel', x - 0.05, x + 0.05, y - 0.05, y + 0.05, z + s_z * 0.08 - 0.04, z + s_z * 0.08 + 0.04, c=0.008)
    _box(p, 'eu_hw', x - 0.012, x + 0.012, y + 0.05, y + 0.12, z + s_z * 0.08 - 0.012, z + s_z * 0.08 + 0.012)
    _run(p, 'eu_steel', (x, y, z + s_z * 0.08), [('y', HANG - 0.02 - y)], 0.016)
    _run(p, 'eu_steel', (x, y - 0.04, z + s_z * 0.08), [('x', 0.25 if x < 0 else -0.25), ('y', -0.10)], 0.013)


def _quad(p, mat, s, x, z0, z1, y0, y1):
    """a single face in the plane x, facing s"""
    pts = [(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)]
    f = p.face(pts if s < 0 else pts[::-1], mat)      # this order faces −x
    f.normal_update()


def _mesh(p, s, xo, z0, z1, y0, y1, pitch=0.045, wire=0.006, depth=0.03, mat='eu_fin'):
    """a fine mesh panel: dark depth behind and wires at the front as single faces (xo = the mesh plane)"""
    _quad(p, 'eu_dark', s, xo - s * depth, z0, z1, y0, y1)
    nz, ny = max(1, round((z1 - z0) / pitch)), max(1, round((y1 - y0) / pitch))
    for k in range(1, nz):
        zz = z0 + (z1 - z0) * k / nz
        _quad(p, mat, s, xo - s * 0.002, zz - wire / 2, zz + wire / 2, y0, y1)
    for k in range(1, ny):
        yy = y0 + (y1 - y0) * k / ny
        _quad(p, mat, s, xo, z0, z1, yy - wire / 2, yy + wire / 2)


def _fin_module(p, s, xf, z0, z1, y0, y1):
    """an SC60A stainless fin cooler: a proud box with a 2 × 2 grid of fine mesh panels and a top tag"""
    xo = xf + s * 0.11
    _box(p, 'eu_fin', xf, xo - s * 0.034, y0, y1, z0, z1, c=0.010)          # the body; the mesh face is open
    for a0, a1, b0, b1 in ((z0, z0 + 0.006, y0, y1), (z1 - 0.006, z1, y0, y1), (z0, z1, y1 - 0.006, y1), (z0, z1, y0, y0 + 0.006)):
        _box(p, 'eu_fin', xo - s * 0.036, xo - s * 0.004, b0, b1, a0, a1)
    # the open front: frame bars round and across, mesh in the four panels
    fb = 0.022
    zm, ym = (z0 + z1) / 2, (y0 + y1) / 2
    for a0, a1, b0, b1 in ((z0, z0 + fb, y0, y1), (z1 - fb, z1, y0, y1), (z0, z1, y1 - fb, y1), (z0, z1, y0, y0 + 0.04),
                           (zm - 0.010, zm + 0.010, y0, y1), (z0, z1, ym - 0.010, ym + 0.010)):
        _box(p, 'eu_fin', xo - s * 0.004, xo + s * 0.006, b0, b1, a0, a1, c=0.002)
    for a0, a1 in ((z0 + fb, zm - 0.010), (zm + 0.010, z1 - fb)):
        for b0, b1 in ((y0 + 0.04, ym - 0.010), (ym + 0.010, y1 - fb)):
            _mesh(p, s, xo, a0, a1, b0, b1, pitch=0.030)
    # the oval tag on top and the bottom drain slot
    _box(p, 'eu_hw', xo + s * 0.006, xo + s * 0.010, y1 - 0.016, y1 - 0.004, zm - 0.03, zm + 0.03)
    _box(p, 'eu_dark', xo + s * 0.006, xo + s * 0.008, y0 + 0.012, y0 + 0.024, z0 + 0.05, z1 - 0.05)


def _round_grille(p, s, xo, zc, yc, r=0.15):
    """round blower grille: a ring, concentric wire rings and radial bars over a dark recess"""
    _extrude(p, 'eu_dark', 'x', _ngon(zc, yc, r, 20), xo - s * 0.002, xo + s * 0.002)
    ring_o, ring_i = _ngon(zc, yc, r + 0.025, 20), _ngon(zc, yc, r, 20)
    for i in range(20):        # the outer ring as 20 small quads extruded
        a, b = ring_o[i], ring_o[(i + 1) % 20]
        c, d = ring_i[(i + 1) % 20], ring_i[i]
        _extrude(p, 'eu_fin', 'x', [a, b, c, d], xo, xo + s * 0.014)
    for rr in (0.4 * r, 0.7 * r):
        pts = _ngon(zc, yc, rr, 16)
        for i in range(16):
            (z_a, y_a), (z_b, y_b) = pts[i], pts[(i + 1) % 16]
            _box(p, 'eu_fin', xo + s * 0.004, xo + s * 0.010, min(y_a, y_b) - 0.003, max(y_a, y_b) + 0.003,
                 min(z_a, z_b) - 0.003, max(z_a, z_b) + 0.003)
    _box(p, 'eu_fin', xo + s * 0.002, xo + s * 0.008, yc - 0.004, yc + 0.004, zc - r, zc + r)      # cross bars
    _box(p, 'eu_fin', xo + s * 0.002, xo + s * 0.008, yc - r, yc + r, zc - 0.004, zc + 0.004)
    _box(p, 'eu_fin', xo + s * 0.006, xo + s * 0.016, yc - 0.03, yc + 0.03, zc - 0.03, zc + 0.03, c=0.006)   # hub


# ---------------------------------------------------------------- the frame between the boxes
def _frame(p, z0, z1, bogies=(-6.9, 6.9)):
    # cross members (lips of the floor's cross beams, just under the body), every 1.2 m outside the bogies
    k0, k1 = math.ceil(z0 / 1.2 - 1e-9), math.floor(z1 / 1.2 + 1e-9)
    for k in range(k0, k1 + 1):
        z = k * 1.2
        if any(abs(z - b) < 1.55 for b in bogies):
            continue
        _box(p, 'eu_steel', -X, X, 0.950, 0.985, z - 0.004, z + 0.004, skip=('top',))
        _box(p, 'eu_steel', -X, X, 0.940, 0.952, z - 0.04, z + 0.04, skip=('top',))
        for x in (-0.50, 0.50):         # pipe clamps
            _box(p, 'eu_steel', x - 0.026, x + 0.026, 0.925, 0.950, z - 0.012, z + 0.012, skip=('top',))
        for x in (-1.05, 1.05):         # conduit clamps
            _box(p, 'eu_steel', x - 0.032, x + 0.032, 0.915, 0.950, z - 0.014, z + 0.014, skip=('top',))
    L = z1 - z0
    zc = (z0 + z1) / 2
    for x in (-0.50, 0.50):
        _pipe(p, 'eu_steel', 'z', (x, 0.935, zc), 0.020, L, n=8)
    _pipe(p, 'eu_steel', 'z', (-0.40, 0.940, zc), 0.014, L, n=6)
    for x in (-1.05, 1.05):
        _pipe(p, 'eu_dark', 'z', (x, 0.940, zc), 0.025, L, n=8)
    # a cable tray along the centre line
    _box(p, 'eu_dark', -0.10, 0.10, 0.925, 0.975, z0, z1, skip=('top',))


def underframe(part, z0, z1):
    tmp = K.Part('eu_tmp')
    _frame(tmp, z0, z1)
    return _emit(part, tmp, False)


def _emit(part, tmp, rotate):
    """copy tmp's faces into part (rotated half a turn about the vertical axis when asked); returns the triangles"""
    n = _tris(tmp)
    vmap = {}
    names = tmp.slots
    for v in tmp.bm.verts:
        co = v.co.copy()
        if rotate:
            co.x, co.y = -co.x, -co.y        # Blender (x, y, z) = game (x, −z, y): the half turn negates x and y
        vmap[v] = part.bm.verts.new(co)
    for f in tmp.bm.faces:
        nf = part.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = part.slot(names[f.material_index])
        nf.smooth = f.smooth
    tmp.bm.free()
    return n


# ---------------------------------------------------------------- the cab cars
def _tc_e231(p):
    """クハE231: TIMS distribution box, ATS-SN box, a dark box and the domed tank on the right; BCU, a box and two
    tanks on the left (assumed)"""
    R, L = -1, 1
    # --- right side (photos p10 / p11 / p17), from the gangway-end bogie towards the cab
    _small_box(p, R, -X + 0.04, -0.72, 0.50, TOP, -4.95, -4.30, lids=1)                       # ATS-SN (assumed)
    # TIMS distribution box: five lids (photo TIMSbox)
    z = -4.10
    lids = []
    for w in (0.55, 0.47, 0.38, 0.64, 0.53):
        lids.append((z + 0.012, z + w - 0.012, {'big_plate': abs(w - 0.38) < 1e-6}))
        z += w
    _cabinet(p, R, -0.08, -4.13, z + 0.03, BOT - 0.02, lids, hang=(-4.0, -2.9, -2.1, z - 0.1))
    _lid(p, L, -0.08, -3.95, -2.45, BOT + 0.05, TOP - 0.05, bars=False, latches=2, plate=False)      # inner face
    # dark box (BCU of the right side, est.)
    _box(p, 'eu_box', -X + 0.03, -0.30, 0.48, TOP, -1.35, -0.25, c=0.010)
    _lid(p, R, -X + 0.03, -1.30, -0.80, 0.52, TOP - 0.035, plate=True)
    _lid(p, R, -X + 0.03, -0.75, -0.30, 0.52, TOP - 0.035, plate=False)
    _hangers(p, R, -X + 0.03, -1.35, -0.25, (-1.25, -0.35))
    _run(p, 'eu_steel', (-0.45, 0.60, -0.25), [('z', 0.35), ('y', 0.30)], 0.014)
    # the big tank, domed end towards the cab with fittings (p08: a valve cluster on that end)
    _tank(p, (-0.82, 0.64, 1.05), 0.23, 2.0, 'z', straps=(-0.32, 0.18), n=18)
    _valve_cluster(p, -0.82, 0.64, 2.05)
    _small_box(p, R, -1.18, -0.70, 0.62, TOP, 2.55, 3.05, lids=1)                             # junction box
    _run(p, 'eu_dark', (-0.95, 0.66, 2.55), [('y', 0.28)], 0.020)
    # --- left side (assumed)
    _cabinet(p, L, 0.10, -3.65, -2.35, 0.44, [(-3.60, -3.00, {}), (-2.95, -2.40, {'plate': False})])    # BCU
    _cabinet(p, L, 0.20, -1.95, -0.55, 0.40, [(-1.90, -1.25, {'rib': True}), (-1.20, -0.60, {'rib': True})])
    _tank(p, (0.96, 0.62, 0.75), 0.17, 1.40, 'z', straps=(-0.28, 0.28))
    _tank(p, (0.56, 0.62, 0.75), 0.17, 1.40, 'z', straps=(-0.28, 0.28))
    _run(p, 'eu_steel', (0.76, 0.62, 1.30), [('y', 0.30)], 0.014)
    _small_box(p, L, 0.55, X - 0.06, 0.56, TOP, 2.20, 2.95, lids=2)
    _run(p, 'eu_steel', (0.50, 0.935, 2.0), [('y', -0.25), ('x', 0.30)], 0.016)
    # --- beyond the bogies: the cab end (skirt from ≈ 9.3) and the gangway end
    _small_box(p, R, -1.00, -0.55, 0.64, TOP, 8.70, 9.10, lids=1)
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, 8.70, 9.10, lids=1)
    _small_box(p, R, -1.00, -0.55, 0.64, TOP, -9.45, -8.75, lids=1)
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, -9.40, -8.85, lids=1)


def _tc_e230(p):
    """クハE230: the left side after the Kuha E230-11 photo; battery box and BCU on the right (assumed)"""
    R, L = -1, 1
    # --- left side (photo): big inboard tank behind the cab bogie, then the boxes
    _tank(p, (0.42, 0.60, 3.25), 0.25, 2.10, 'z', straps=(-0.30, 0.30), n=18)
    _valve_cluster(p, 0.42, 0.60, 4.30)
    _cabinet(p, L, 0.55, 1.45, 2.10, 0.42, [(1.48, 2.07, {'latches': 2})], hang=(1.55, 2.0))             # tall narrow
    _box(p, 'eu_box', 0.12, 0.85, 0.50, TOP, 0.35, 1.30, c=0.010)                                        # dark inboard
    _lid(p, L, 0.85, 0.42, 1.23, 0.55, TOP - 0.04, plate=False, latches=2)
    _hangers(p, L, 0.85, 0.35, 1.30, (0.45, 1.2))
    _cabinet(p, L, 0.30, -0.95, 0.20, 0.40, [(-0.92, -0.38, {}), (-0.33, 0.17, {'plate': False})])     # lighter box
    _small_box(p, L, 0.70, X - 0.02, 0.56, TOP, -1.55, -1.10, lids=1)
    _run(p, 'eu_steel', (0.80, 0.935, -2.0), [('y', -0.30), ('z', 0.45)], 0.016)
    # --- right side (assumed): battery box with vent slots, BCU, a junction box
    z0, z1 = -3.40, -1.20
    _box(p, 'eu_box', -X, -0.15, 0.40, TOP, z0, z1, c=0.012)
    _flange(p, -X, -0.15, z0, z1, 0.40)
    for a, b in ((-3.35, -2.32), (-2.28, -1.25)):
        _lid(p, R, -X, a, b, 0.44, TOP - 0.04, plate=(a < -3), latches=3)
        for k in range(6):                                  # vent slots along the lid's upper part
            zz = a + 0.15 + k * (b - a - 0.30) / 5
            _box(p, 'eu_dark', -X - 0.010, -X - 0.012, 0.66, 0.76, zz - 0.012, zz + 0.012)
    _hangers(p, R, -X, z0, z1, (-3.3, -2.3, -1.3))
    _cabinet(p, R, -0.15, -0.90, 0.40, 0.46, [(-0.86, -0.25, {}), (-0.20, 0.36, {'plate': False})])     # BCU
    _small_box(p, R, -1.15, -0.60, 0.58, TOP, 0.80, 1.40, lids=1)
    _tank(p, (-0.95, 0.62, 2.70), 0.17, 1.30, 'z', straps=(-0.28, 0.28))
    _run(p, 'eu_steel', (-0.50, 0.935, 1.6), [('y', -0.28), ('x', -0.30)], 0.016)
    # --- beyond the bogies
    _small_box(p, R, -1.00, -0.55, 0.64, TOP, 8.70, 9.10, lids=1)
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, 8.70, 9.10, lids=1)
    _small_box(p, R, -1.00, -0.55, 0.64, TOP, -9.40, -8.85, lids=1)
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, -9.45, -8.75, lids=1)


def underfloor_tc(part, car='E231', cab_at_plus_z=True, with_frame=True):
    tmp = K.Part('eu_tmp')
    (_tc_e231 if car == 'E231' else _tc_e230)(tmp)
    if with_frame:
        _frame(tmp, -9.5, 9.2)
    return _emit(part, tmp, not cab_at_plus_z)


# ---------------------------------------------------------------- the motor car
def _vvvf(p):
    """VVVF inverter, SC60A look: centre lid between two groups of three stainless fin coolers (right side); lids on
    the left face"""
    R, L = -1, 1
    z0, z1 = -1.80, 1.80
    xb = -X + 0.10                 # the box's right face; the fin coolers stand 0.11 proud of it (to −X − 0.01)
    _box(p, 'eu_box', xb + 0.10, X, BOT + 0.06, TOP, z0, z1, c=0.012)       # the main box, its right face set back
    _box(p, 'eu_steel', xb, xb + 0.10, BOT + 0.06, TOP, z0, z1)              # dark recess behind the fins (photo)
    _flange(p, xb + 0.10, X, z0, z1, BOT + 0.06)
    # right: three fins, the centre lid, three fins
    w, g = 0.31, 0.045
    zs = [-1.72 + k * (w + g) for k in range(3)]
    zs += [0.44 + 0.05 + k * (w + g) for k in range(3)]
    for a in zs:
        _fin_module(p, R, xb, a, a + w, BOT - 0.01, TOP - 0.05)
    # the centre lid (VVVF): plates, two handle slots, latches
    lz0, lz1 = -0.62, 0.40
    _box(p, 'eu_lid', xb, xb - 0.030, BOT + 0.05, TOP - 0.05, lz0, lz1, c=0.012)
    xo = xb - 0.030
    for zz in (lz0 + 0.08, lz1 - 0.08):
        _box(p, 'eu_dark', xo, xo - 0.003, 0.58, 0.68, zz - 0.022, zz + 0.022)
    _plate(p, R, xo, -0.30, 0.76, w=0.10, h=0.05)
    _plate(p, R, xo, -0.05, 0.76, w=0.16, h=0.06)
    _plate(p, R, xo, -0.05, 0.66, w=0.12, h=0.045)
    for zz in (-0.40, 0.18):
        _latch(p, R, xo, zz, BOT + 0.09)
    _box(p, 'eu_steel', xo, xo - 0.012, BOT + 0.05, BOT + 0.10, lz0 + 0.04, lz1 - 0.04)
    _hangers(p, R, xb, z0, z1, (-1.70, -0.62, 0.40, 1.70))
    # left face: four lids with plates and ribs
    s, xf = L, X
    for a, b in ((-1.75, -0.95), (-0.90, -0.05), (0.00, 0.85), (0.90, 1.75)):
        _lid(p, s, xf, a, b, BOT + 0.07, TOP - 0.04, rib=True, plate=True)
    _hangers(p, s, xf, z0, z1, (-1.70, -0.5, 0.5, 1.70))
    # end faces: cable glands
    for zz in (z0, z1):
        sz = 1 if zz > 0 else -1
        for x in (-0.55, 0.0, 0.55):
            _pipe(p, 'eu_dark', 'z', (x, 0.78, zz + sz * 0.10), 0.030, 0.20, n=8)


def _mc(p):
    R, L = -1, 1
    _vvvf(p)
    # --- filter reactor (right, towards +z): a plain tall box with stiffening ribs and a cable gland box (est.)
    z0, z1 = 2.10, 3.55
    _box(p, 'eu_box', -X, -0.15, 0.40, TOP, z0, z1, c=0.012)
    _flange(p, -X, -0.15, z0, z1, 0.40)
    _lid(p, R, -X, 2.15, 2.80, 0.44, TOP - 0.04, latches=2)
    _lid(p, R, -X, 2.85, 3.50, 0.44, TOP - 0.04, latches=2, plate=False)
    _hangers(p, R, -X, z0, z1, (2.2, 2.82, 3.45))
    # --- the line breaker / HB box (right, towards −z, the pantograph end)
    _cabinet(p, R, -0.20, -3.55, -2.15, 0.42, [(-3.50, -2.88, {'big_plate': True}), (-2.83, -2.20, {})])
    _small_box(p, R, -1.15, -0.55, 0.58, TOP, -4.80, -4.05, lids=1)                       # main fuse box
    _run(p, 'eu_dark', (-0.85, 0.60, -4.05), [('z', 0.50)], 0.028)                         # cable to the HB box
    # --- left side: BCU, air tanks, a ground switch box (est.)
    _cabinet(p, L, 0.15, 2.10, 3.30, 0.46, [(2.15, 2.70, {}), (2.75, 3.25, {'plate': False})])
    _tank(p, (0.98, 0.62, 4.30), 0.17, 1.30, 'z', straps=(-0.28, 0.28))
    _tank(p, (0.58, 0.62, 4.30), 0.17, 1.30, 'z', straps=(-0.28, 0.28))
    _run(p, 'eu_steel', (0.78, 0.62, 3.75), [('y', 0.31)], 0.014)
    _cabinet(p, L, 0.30, -3.30, -2.20, 0.48, [(-3.25, -2.25, {'rib': True})])
    _tank(p, (0.80, 0.64, -4.25), 0.20, 1.40, 'z', straps=(-0.28, 0.28))
    _run(p, 'eu_steel', (0.50, 0.935, -3.6), [('y', -0.25), ('x', 0.25)], 0.016)
    # --- the blower box with the round grille at the +z end, right side (p08 / p11 / p17)
    zb0, zb1 = 8.68, 9.55
    _box(p, 'eu_box', -X + 0.04, -0.50, 0.46, TOP, zb0, zb1, c=0.010)
    _flange(p, -X + 0.04, -0.50, zb0, zb1, 0.46)
    xf = -X + 0.04
    _box(p, 'eu_lid', xf, xf - 0.010, 0.50, TOP - 0.035, zb0 + 0.04, zb1 - 0.04, c=0.003)
    _round_grille(p, -1, xf - 0.010, (zb0 + zb1) / 2 - 0.06, 0.66, r=0.15)
    _plate(p, -1, xf - 0.010, zb1 - 0.14, 0.78, w=0.08, h=0.04)
    for zz in (zb0 + 0.12, zb1 - 0.14):
        _latch(p, -1, xf - 0.010, zz, 0.54)
    _hangers(p, -1, xf, zb0, zb1, (zb0 + 0.08, zb1 - 0.08))
    # --- small boxes at the other end and on the left of the +z end
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, 8.75, 9.20, lids=1)
    _small_box(p, R, -1.00, -0.55, 0.64, TOP, -9.45, -8.80, lids=1)
    _small_box(p, L, 0.55, 1.00, 0.64, TOP, -9.40, -8.85, lids=1)


def underfloor_m(part, with_frame=True):
    tmp = K.Part('eu_tmp')
    _mc(tmp)
    if with_frame:
        _frame(tmp, -9.5, 9.5)
    return _emit(part, tmp, False)


# ================================================================ test harness (Blender only)
def _placeholders(mats):
    """body (E231: 2.95 m wide, 19.5 m long, bottom at 1.00), rails, sleepers, bogie blocks at z = ±6.9"""
    m = mats
    m.add('ph_body', '#b9bcbf', 0.8, 0.35)
    m.add('ph_band', '#f15a22', 0.0, 0.5)
    m.add('ph_steel', '#4a4d52', 0.6, 0.5)
    m.add('ph_rail', '#6e5f55', 0.6, 0.5)
    m.add('ph_sleeper', '#5a5a57', 0.0, 0.9)
    body = K.Part('ph_body')
    body.box('ph_body', -1.415, 1.415, 1.0, 1.25, -9.75, 9.75)
    body.box('ph_body', -1.475, 1.475, 1.25, 3.6, -9.75, 9.75)
    body.box('ph_band', -1.478, 1.478, 1.85, 1.98, -9.75, 9.75)
    p = K.Part('placeholders')
    for x in (-0.5335, 0.5335):
        p.box('ph_rail', x - 0.0325, x + 0.0325, 0.0, 0.16, -30, 30)
    for k in range(-50, 51):
        p.box('ph_sleeper', -1.1, 1.1, 0.0, 0.14, k * 0.6 - 0.1, k * 0.6 + 0.1)
    for bz in (-6.9, 6.9):
        for dz in (-1.05, 1.05):
            for x in (-0.5335, 0.5335):
                p.cylinder('ph_steel', (x, 0.43, bz + dz), 0.43, 0.13, axis='x', segments=28)
            p.cylinder('ph_steel', (0, 0.43, bz + dz), 0.06, 1.5, axis='x', segments=10)
        for x in (-0.95, 0.95):
            p.box('ph_steel', x - 0.06, x + 0.06, 0.48, 0.78, bz - 1.45, bz + 1.45)
        p.box('ph_steel', -0.95, 0.95, 0.52, 0.76, bz - 0.25, bz + 0.25)
    return p, body


def _render(path, eye, target, lens, size=(1280, 640), samples=32):
    scene = bpy.context.scene
    cam = scene.camera
    cam.location = B(*eye)
    cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _setup_scene():
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.42, 0.52, 0.68, 1.0)
    bg.inputs['Strength'].default_value = 0.9
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=120)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    scene.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#6b6862')
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    me.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(55), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN'))
    fill.data.energy = 1.2
    fill.data.angle = math.radians(20)
    fill.rotation_euler = (math.radians(60), 0, math.radians(145))
    scene.collection.objects.link(fill)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'Standard'
    scene.cycles.max_bounces = 4


def _check(part):
    """print the extents of what was built, in the game frame, and what enters the bogie zones"""
    pts = [K.G(v.co) for v in part.bm.verts]
    ys = [q[1] for q in pts]
    print('  y range %.3f .. %.3f' % (min(ys), max(ys)))
    print('  z range %.3f .. %.3f' % (min(q[2] for q in pts), max(q[2] for q in pts)))
    print('  x range %.3f .. %.3f' % (min(q[0] for q in pts), max(q[0] for q in pts)))
    zone = [q for q in pts if 5.2 < abs(q[2]) < 8.6]
    if zone:
        print('  bogie zone: min y %.3f (frame only should be ≥ 0.91)' % min(q[1] for q in zone))


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    outdir = argv[0] if argv else '/tmp'
    clay = '--clay' in argv
    only = [a for a in argv[1:] if not a.startswith('--')]
    if 'all' in only:
        only = []
    os.makedirs(outdir, exist_ok=True)
    K.clear_scene()
    _setup_scene()
    m = K.Materials()
    add_materials(m)
    ph, body = _placeholders(m)
    if clay:
        for name, mat in m.mats.items():
            if name.startswith('eu_'):
                bsdf = mat.node_tree.nodes['Principled BSDF']
                bsdf.inputs['Base Color'].default_value = K.srgb('#b0aca4')
                bsdf.inputs['Metallic'].default_value = 0.0
                bsdf.inputs['Roughness'].default_value = 0.7
    phobj = ph.build(None, m.mats)
    bodyobj = body.build(None, m.mats)
    ground = bpy.data.objects['ground']
    cars = {}
    for name, fn in (('tc', lambda t: underfloor_tc(t, 'E231')), ('tc2', lambda t: underfloor_tc(t, 'E230')),
                     ('m', underfloor_m)):
        if only and name not in only:
            continue
        part = K.Part('eu_' + name)
        n = fn(part)
        print('TRIANGLES', name, n)
        _check(part)
        cars[name] = part.build(None, m.mats)
    tag = '_clay' if clay else ''
    views = {
        # name: (eye, target, lens)
        'right': ((-19.0, 0.62, 0.0), (0.0, 0.70, 0.0), 60),
        'left': ((19.0, 0.62, 0.0), (0.0, 0.70, 0.0), 60),
        'q_right': ((-11.0, 1.1, 13.0), (-0.8, 0.62, 2.0), 45),
        'q_left': ((11.0, 1.1, 13.0), (0.8, 0.62, 2.0), 45),
        'q_right2': ((-11.0, 1.1, -13.0), (-0.8, 0.62, -2.0), 45),
        'q_left2': ((11.0, 1.1, -13.0), (0.8, 0.62, -2.0), 45),
        'under': ((0.0, -12.0, 0.01), (0.0, 0.0, 0.0), 30),
        'close_r': ((-5.5, 0.62, 0.5), (-1.3, 0.62, 0.0), 35),
        'vvvf': ((-5.0, 0.64, 0.0), (-1.2, 0.64, 0.0), 35),
        'tims': ((-5.0, 0.64, -2.6), (-1.2, 0.64, -2.6), 35),
        'p11': ((-6.0, 1.9, 21.0), (-0.6, 0.75, 1.0), 55),
        'blower': ((-4.5, 0.70, 11.5), (-1.0, 0.65, 8.0), 35),
        'close_l': ((5.5, 0.62, 0.5), (1.3, 0.62, 0.0), 35),
    }
    want = os.environ.get('UF_VIEWS')
    for name, obj in cars.items():
        for other, o in cars.items():
            o.hide_render = other != name
        for vn, (eye, tgt, lens) in views.items():
            if want and vn not in want.split(','):
                continue
            bodyobj.hide_render = ground.hide_render = phobj.hide_render = vn == 'under'
            _render(os.path.join(outdir, f'{name}_{vn}{tag}.png'), eye, tgt, lens)


if __name__ == '__main__':
    _main()
