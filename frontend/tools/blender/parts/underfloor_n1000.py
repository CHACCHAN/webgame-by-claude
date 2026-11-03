"""
Keikyu New 1000 series, 1st batch: the underfloor equipment of the motor car (Muc / Msc) and the pantograph trailer
(Tpu). A part module for the Blender model (train_kit.Part, the game's car frame, material prefix `uf_`).

  underfloor_motor_car(part, cab_at_plus_z=True)  car0 / car2: the traction container, HB, BCU, air tanks, cable boxes
  underfloor_trailer_pantograph(part)             car1: SIV, CP, battery box, air tanks, BCU
  underframe(part, z0, z1)                        cross members, pipes and conduits between the boxes
  add_materials(m)

Each returns the number of triangles it added. The two car functions call `underframe` for the whole car themselves
(`with_frame=False` leaves it out); the frame stays at y ≥ 0.90 and the boxes hang below it, 0.34 ≤ y ≤ 0.90.
`cab_at_plus_z=False` turns the car round (180° about the vertical axis, x → −x and z → −z), as car2 is car0 turned
round: the equipment that was on the right side ends up on the left.

Run directly with Blender it renders test images:
  blender -t 4 --background --factory-startup --python parts/underfloor_n1000.py -- <outdir> [--clay]

Figures and where they come from (reference photos of the contract's folder; "est." = estimated from known sizes):
- Equipment hangs from y = 0.90 (frame bottom) down to y = 0.34 (box bottom; the limit given was 0.30): photo 16
  (traction container on 1009) has the box bottom about 0.3 m above the rail head and its top at the sole bar; the
  container is ≈ 0.68 m high incl. mounting rails (est. from the door pocket in the same photo, ≈ 2 mm per pixel).
- Boxes are 2.56 m wide at most (x = ±1.28; the body is 2.83 m, the bogie zone is limited to ±1.30 by the brief); a
  box that only has lids on one side is 1.25 m deep (x from the side to the centre line); the opposite side holds
  other equipment: est., the photos only show one side each.
- Traction container (Box-A, photo 16 and c09 / 18 crops): 4.8 m long (est. from the lid sizes: big lid 1.5, two
  0.75 lids, 0.32 narrow lid, grille end 0.7). The lids are the proportions of photo 16 (600 : 290 : 290 : 125 : 245
  pixels). The grille end sits towards the cab on the right side (c09 crop: mesh grille between the cab-end bogie and
  the container). Photo 16 is taken to show the RIGHT side (x < 0, the side seen in 09 / 18); the left side (louvre
  cooling intake and lids) is our own arrangement, no photo shows it.
- Traction container colour: olive-brown paint (photo 16 / 07), cleaned a little.
- SIV (75 kVA; photo 07): 3.4 m long: plain lid 0.7, two mesh grilles 0.8 each, lid with plates and 4 latches 1.0
  (ratios of 200 : 230 : 230 : 285 px). Placed on the RIGHT side (assumption).
- CP (photo 05, "空気圧縮装置" = air compressor unit): 2.1 m × 0.68 m, four lids on two rows; light stainless-like
  grey. Placed on the LEFT side (assumption, photo 05 and 07 are not known to show the same side).
- Handles: lever latches (round base ∅ 34 mm, bar 70 mm), hinge brackets and recessed pocket handles after photos
  05 and 16; plates are blank (no lettering or logos).
- Tanks: ∅ 0.30–0.40 m, domed ends, 2 straps each; the air tanks lie along z, the main reservoir across the car (est.).
- Frame: cross members every 1.2 m, 2 brake / air pipes (∅ 40 mm at x = ±0.55), 2 conduits (∅ 30 mm at x = ±1.22):
  est., photo 16 shows hangers, pipes and a conduit above the container (right end).
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
X = 1.28            # half width of the equipment
TOP = 0.90          # the boxes' top (the frame's lower edge)
BOT = 0.34          # the boxes' bottom

MATS = {
    # name: (colour, metallic, roughness)
    'uf_body': ('#5f5441', 0.35, 0.62),    # box shells: olive-brown paint (photos 16, 07)
    'uf_lid': ('#706550', 0.35, 0.55),     # lids, a shade lighter
    'uf_light': ('#9fa09b', 0.50, 0.45),   # CP and battery box: light stainless-like grey (photo 05)
    'uf_steel': ('#3a3a3b', 0.60, 0.55),   # frame, hangers, pipes, straps
    'uf_hw': ('#a4a7aa', 0.85, 0.32),      # latches, hinges, plates: bright steel
    'uf_dark': ('#141516', 0.20, 0.75),    # grille depth, pockets, cables
}


def add_materials(m):
    for name, (colour, metallic, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, colour, metallic, rough)


# ---------------------------------------------------------------- primitives (game frame, flat shaded unless noted)
def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _box(p, mat, x0, x1, y0, y1, z0, z1, c=0.0):
    """box with chamfered edges (one segment: flat faces stay flat)"""
    if x0 > x1:
        x0, x1 = x1, x0
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = B((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.z * (y1 - y0), (z0 + z1) / 2 - v.co.y * (z1 - z0))
    if c > 0:
        c = min(c, 0.4 * (x1 - x0), 0.4 * (y1 - y0), 0.4 * (z1 - z0))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=c, segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
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


# ---------------------------------------------------------------- small hardware on a side face
# a face has its outward direction s (+1: x > 0, the left side) and sits at x = xf; "xo" is the surface of a panel on it
def _lever(p, s, xo, zc, yc, vertical=False):
    """lever latch: round base and a bar"""
    _extrude(p, 'uf_hw', 'x', [(z, y) for z, y in _ngon(zc, yc, 0.021, 6)], xo, xo + s * 0.007)
    if vertical:
        _box(p, 'uf_hw', xo + s * 0.007, xo + s * 0.024, yc - 0.045, yc + 0.030, zc - 0.009, zc + 0.009, c=0.003)
    else:
        _box(p, 'uf_hw', xo + s * 0.007, xo + s * 0.024, yc - 0.009, yc + 0.009, zc - 0.045, zc + 0.030, c=0.003)


def _pocket(p, s, xo, zc, yc, w=0.07, h=0.09):
    """recessed pocket handle: dark opening in a frame"""
    _box(p, 'uf_dark', xo, xo + s * 0.002, yc - h / 2, yc + h / 2, zc - w / 2, zc + w / 2)
    b = 0.010
    for z0, z1, y0, y1 in ((zc - w / 2 - b, zc - w / 2, yc - h / 2 - b, yc + h / 2 + b), (zc + w / 2, zc + w / 2 + b, yc - h / 2 - b, yc + h / 2 + b),
                           (zc - w / 2, zc + w / 2, yc + h / 2, yc + h / 2 + b), (zc - w / 2, zc + w / 2, yc - h / 2 - b, yc - h / 2)):
        _box(p, 'uf_steel', xo, xo + s * 0.010, y0, y1, z0, z1)


def _plate(p, s, xo, zc, yc, w=0.15, h=0.035, dark=False):
    """a blank name plate"""
    _box(p, 'uf_dark' if dark else 'uf_hw', xo, xo + s * 0.003, yc - h / 2, yc + h / 2, zc - w / 2, zc + w / 2)


def _lid(p, s, xf, z0, z1, y0, y1, mat='uf_lid', plates=0, pockets=None, levers=None, t=0.013):
    """a raised lid panel with hinges on top, lever latches and optional pocket handles / plates"""
    w, h = z1 - z0, y1 - y0
    xo = xf + s * t
    _box(p, 'uf_dark', xf, xf + s * 0.004, y0 - 0.007, y1 + 0.007, z0 - 0.007, z1 + 0.007)      # the gap round the lid
    _box(p, mat, xf, xo, y0, y1, z0, z1, c=0.004)
    if levers is None:
        levers = 4 if w >= 0.5 else 2
    zc, yc = (z0 + z1) / 2, (y0 + y1) / 2
    lz = 0.07 if w >= 0.5 else 0.0
    top, bot = y1 - 0.07, y0 + 0.07
    if levers >= 4:
        for zz, yy in ((z0 + lz, top), (z1 - lz, top), (z0 + lz, bot), (z1 - lz, bot)):
            _lever(p, s, xo, zz, yy)
    else:
        _lever(p, s, xo, zc, top)
        _lever(p, s, xo, zc, bot)
    for zz in (z0 + 0.12 * w + 0.04, z1 - 0.12 * w - 0.04):      # two hinge brackets on the top edge
        _box(p, 'uf_steel', xf, xo + s * 0.006, y1 - 0.030, y1 + 0.012, zz - 0.025, zz + 0.025)
    if pockets is None:
        pockets = w >= 0.7
    if pockets:
        for zz in (z0 + 0.22 * w, z1 - 0.22 * w):
            _pocket(p, s, xo, zz, yc - 0.06 * h)
    for k in range(plates):
        _plate(p, s, xo, zc, yc + h * 0.22 - k * 0.055, dark=bool(k % 2))


def _grille(p, s, xf, z0, z1, y0, y1, pitch=0.042, depth=0.05, bar=0.032, divider=False):
    """a mesh-covered intake in a proud frame: frame bars, dark depth, real wire bars at the front"""
    xo = xf + s * depth
    _box(p, 'uf_dark', xf, xf + s * 0.004, y0, y1, z0, z1)
    for a0, a1, b0, b1 in ((z0, z0 + bar, y0, y1), (z1 - bar, z1, y0, y1), (z0 + bar, z1 - bar, y1 - bar, y1), (z0 + bar, z1 - bar, y0, y0 + bar)):
        _box(p, 'uf_lid', xf, xo, b0, b1, a0, a1, c=0.004)
    iz0, iz1, iy0, iy1 = z0 + bar, z1 - bar, y0 + bar, y1 - bar
    nz, ny = int((iz1 - iz0) / pitch), int((iy1 - iy0) / pitch)
    wire = 0.004
    for k in range(1, nz):
        zz = iz0 + (iz1 - iz0) * k / nz
        _box(p, 'uf_steel', xo - s * 0.010, xo - s * 0.002, iy0, iy1, zz - wire / 2, zz + wire / 2)
    for k in range(1, ny):
        yy = iy0 + (iy1 - iy0) * k / ny
        _box(p, 'uf_steel', xo - s * 0.012, xo - s * 0.004, yy - wire / 2, yy + wire / 2, iz0, iz1)
    if divider:       # photo 07: a fatter vertical bar in the middle of each grille
        zc = (z0 + z1) / 2
        _box(p, 'uf_lid', xf, xo, iy0, iy1, zc - 0.012, zc + 0.012, c=0.003)


def _louvre(p, s, xf, z0, z1, y0, y1, n=12):
    """a louvred intake: frame and slanted slats (outer edge lower)"""
    xo = xf + s * 0.05
    _box(p, 'uf_dark', xf, xf + s * 0.004, y0, y1, z0, z1)
    b = 0.03
    for a0, a1, b0, b1 in ((z0, z0 + b, y0, y1), (z1 - b, z1, y0, y1), (z0 + b, z1 - b, y1 - b, y1), (z0 + b, z1 - b, y0, y0 + b)):
        _box(p, 'uf_lid', xf, xo, b0, b1, a0, a1, c=0.004)
    pitch = (y1 - y0 - 2 * b) / n
    for k in range(n):
        yk = y0 + b + pitch * (k + 0.5)
        poly = [(xf + s * 0.012, yk + 0.021), (xf + s * 0.012, yk + 0.015), (xf + s * 0.046, yk - 0.015), (xf + s * 0.046, yk - 0.009)]
        _extrude(p, 'uf_body', 'z', poly, z0 + b, z1 - b)


def _hangers(p, s, xf, z0, z1, zs):
    """mounting rail along the top edge of a face and hanger plates up to the frame"""
    _box(p, 'uf_steel', xf, xf - s * 0.09, TOP, TOP + 0.04, z0 - 0.02, z1 + 0.02, c=0.004)
    for z in zs:
        _extrude(p, 'uf_steel', 'x', [(z - 0.055, TOP), (z + 0.055, TOP), (z + 0.03, TOP + 0.075), (z - 0.03, TOP + 0.075)],
                 xf - s * 0.014, xf)


def _bars(p, s, xf, zs, y0, y1, mat='uf_body'):
    """vertical stiffener bars of a cabinet face, between the lids"""
    for z in zs:
        _box(p, mat, xf, xf + s * 0.010, y0, y1, z - 0.02, z + 0.02, c=0.003)


def _flange(p, x0, x1, z0, z1, mat='uf_steel'):
    """the bottom flange of a big box (darker, brake dust)"""
    _box(p, mat, x0 - 0.01, x1 + 0.01, BOT - 0.004, BOT + 0.05, z0 - 0.01, z1 + 0.01, c=0.004)


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


def _tank(p, centre, r, length, axis, straps=(-0.3, 0.3), n=14, mat='uf_body'):
    """air tank with domed ends, straps and hanger bars up to the frame"""
    d = 0.42 * r
    half = length / 2
    prof = [(-half + d * (1 - math.cos(a)), r * math.sin(a)) for a in (0, 0.5, 1.0, 1.35, math.pi / 2)]
    prof += [(-t, rr) for t, rr in reversed(prof[:-1])]
    prof = [(t, rr) for t, rr in prof]
    prof = sorted(prof, key=lambda q: q[0])
    _lathe(p, mat, axis, centre, prof, n=n, smooth=True)
    # drain boss at the low end and a valve stub on top
    for k in straps:
        t0 = k * length
        prof_s = [(t0 - 0.03, r), (t0 - 0.03, r + 0.012), (t0 + 0.03, r + 0.012), (t0 + 0.03, r)]
        _lathe(p, 'uf_steel', axis, centre, prof_s, n=n, smooth=False)
        cx, cy, cz = centre
        if axis == 'z':
            _box(p, 'uf_steel', cx - 0.02, cx + 0.02, cy + r * 0.7, TOP, cz + t0 - 0.015, cz + t0 + 0.015)
        else:
            _box(p, 'uf_steel', cx + t0 - 0.015, cx + t0 + 0.015, cy + r * 0.7, TOP, cz - 0.02, cz + 0.02)
    cx, cy, cz = centre
    if axis == 'z':
        _box(p, 'uf_steel', cx - 0.025, cx + 0.025, cy - r - 0.03, cy - r + 0.005, cz + half * 0.6 - 0.025, cz + half * 0.6 + 0.025)
    else:
        _box(p, 'uf_steel', cx + half * 0.6 - 0.025, cx + half * 0.6 + 0.025, cy - r - 0.03, cy - r + 0.005, cz - 0.025, cz + 0.025)


def _cable_box(p, s, x0, x1, y0, y1, z0, z1, lids=2, mat='uf_body', lidmat='uf_lid'):
    """a small junction box with lids on its outer face"""
    _box(p, mat, x0, x1, y0, y1, z0, z1, c=0.008)
    xf = x1 if s > 0 else x0
    n = max(1, lids)
    zw = (z1 - z0 - 0.04) / n
    for k in range(n):
        a = z0 + 0.02 + k * zw
        _lid(p, s, xf, a + 0.01, a + zw - 0.01, y0 + 0.04, y1 - 0.04, mat=lidmat, levers=2, pockets=False)
    _hangers(p, s, xf, z0, z1, (z0 + 0.06, z1 - 0.06))


# ---------------------------------------------------------------- the frame between the boxes
def _frame(p, z0, z1):
    # cross members (I section), every 1.2 m
    k0, k1 = math.ceil(z0 / 1.2 - 1e-9), math.floor(z1 / 1.2 + 1e-9)
    for k in range(k0, k1 + 1):
        z = k * 1.2
        _box(p, 'uf_steel', -X, X, 0.915, 0.955, z - 0.004, z + 0.004)
        _box(p, 'uf_steel', -X, X, 0.955, 0.972, z - 0.05, z + 0.05)
        _box(p, 'uf_steel', -X, X, 0.898, 0.915, z - 0.05, z + 0.05)
        for x in (-0.55, 0.55):         # pipe clamps
            _box(p, 'uf_steel', x - 0.028, x + 0.028, 0.894, 0.936, z - 0.012, z + 0.012)
        for x in (-1.22, 1.22):         # conduit clamps
            _box(p, 'uf_steel', x - 0.022, x + 0.022, 0.912, 0.948, z - 0.012, z + 0.012)
    L = z1 - z0
    zc = (z0 + z1) / 2
    for x in (-0.55, 0.55):
        _pipe(p, 'uf_steel', 'z', (x, 0.915, zc), 0.020, L, n=8)
    for x in (-1.22, 1.22):
        _pipe(p, 'uf_dark', 'z', (x, 0.93, zc), 0.015, L, n=8)
    # a cable tray along the centre line
    _box(p, 'uf_dark', -0.10, 0.10, 0.905, 0.95, z0, z1)


def underframe(part, z0, z1):
    tmp = K.Part('uf_tmp')
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


# ---------------------------------------------------------------- the motor car
def _muc(p):
    # --- traction container "Box-A": VVVF inverter + filter reactor in one box, lids on both sides
    z0, z1 = -2.9, 1.9
    _box(p, 'uf_body', -X, X, BOT, TOP, z0, z1, c=0.012)
    _flange(p, -X, X, z0, z1)
    for z in (-2.2, -0.9, 0.5):                         # stiffening ribs under the box (lowest point 0.328)
        _box(p, 'uf_steel', -X + 0.1, X - 0.1, BOT - 0.012, BOT, z - 0.03, z + 0.03)
    # right side (photo 16): big lid, two lids, narrow lid, a plain strip, then the grille end towards the cab
    s, xf = -1, -X
    _lid(p, s, xf, -2.85, -1.35, 0.40, 0.84, plates=2)
    _lid(p, s, xf, -1.30, -0.55, 0.40, 0.84, plates=1)
    _lid(p, s, xf, -0.50, 0.25, 0.40, 0.84)
    _lid(p, s, xf, 0.30, 0.62, 0.40, 0.84)
    _cable_box(p, s, xf - 0.045, xf, 0.50, 0.74, 0.76, 1.04, lids=1)
    _grille(p, s, xf, 1.15, 1.85, 0.40, 0.84)
    _bars(p, s, xf, (-1.325, -0.525, 0.275, 1.10), 0.40, 0.84)
    _hangers(p, s, xf, z0, z1, (-2.75, -1.33, -0.52, 0.28, 1.1, 1.8))
    # left side: lids, the cooling louvres in the middle
    s, xf = 1, X
    _lid(p, s, xf, -2.85, -1.65, 0.40, 0.84, plates=1)
    _lid(p, s, xf, -1.58, -0.55, 0.40, 0.84, plates=1)
    _louvre(p, s, xf, -0.40, 0.90, 0.40, 0.84, n=12)
    _lid(p, s, xf, 1.00, 1.85, 0.40, 0.84)
    _bars(p, s, xf, (-1.615, -0.475, 0.95), 0.40, 0.84)
    _hangers(p, s, xf, z0, z1, (-2.75, -1.6, -0.5, 0.95, 1.8))
    # the end towards the cab: two cable conduits into the HB box, and a pipe run beside them
    for x in (-0.55, 0.55):
        _pipe(p, 'uf_dark', 'z', (x, 0.76, 2.03), 0.028, 0.28, n=8)
    _run(p, 'uf_steel', (-0.20, 0.915, 2.02), [('y', -0.30), ('x', -0.18)], 0.016)
    _run(p, 'uf_steel', (0.20, 0.915, 2.02), [('y', -0.22), ('x', 0.18)], 0.016)
    # --- high-speed circuit breaker box (right) and brake control unit (left)
    _box(p, 'uf_body', -X, -0.03, 0.50, TOP, 2.15, 3.15, c=0.010)
    _lid(p, -1, -X, 2.20, 2.65, 0.55, 0.85, levers=4)
    _lid(p, -1, -X, 2.70, 3.10, 0.55, 0.85, levers=2, pockets=False)
    _hangers(p, -1, -X, 2.15, 3.15, (2.25, 3.05))
    _box(p, 'uf_body', 0.03, X, 0.48, TOP, 2.15, 3.55, c=0.010)
    _lid(p, 1, X, 2.20, 3.00, 0.53, 0.85, plates=1)
    _lid(p, 1, X, 3.05, 3.50, 0.53, 0.85)
    _hangers(p, 1, X, 2.15, 3.55, (2.25, 3.45))
    # HB's left face and BCU's right face, seen through the gaps from the other side
    _lid(p, 1, -0.03, 2.25, 3.10, 0.55, 0.85, levers=2, pockets=False)
    _lid(p, -1, 0.03, 2.25, 3.45, 0.53, 0.85, levers=2, pockets=False)
    # --- main air reservoir across the car, just before the bogie, with its pipe to the BCU
    _tank(p, (0.0, 0.62, 3.88), 0.21, 2.24, 'x', straps=(-0.33, 0.0, 0.33), n=16)
    _run(p, 'uf_steel', (0.45, 0.66, 3.50), [('z', 0.12)], 0.016)
    # --- the other end (towards the gangway): a junction box (right) and two air tanks (left)
    _cable_box(p, -1, -X, -0.35, 0.52, TOP, -4.20, -3.20, lids=2)
    _tank(p, (1.00, 0.58, -3.72), 0.15, 1.02, 'z', straps=(-0.28, 0.28))
    _tank(p, (0.60, 0.58, -3.72), 0.15, 1.02, 'z', straps=(-0.28, 0.28))
    _run(p, 'uf_steel', (0.80, 0.78, -3.2), [('z', 0.35), ('y', -0.12)], 0.013)       # air pipe from the tanks to the container
    _run(p, 'uf_steel', (0.0, 0.915, -3.05), [('y', -0.25), ('x', 0.35)], 0.016)
    # --- small items beyond the bogies: cab end z 7.7–8.2 (the skirt starts at 8.3), gangway end −8.2…−7.7
    _cable_box(p, -1, -1.00, -0.50, 0.62, 0.86, 7.72, 8.12, lids=1)
    _cable_box(p, 1, 0.55, 1.00, 0.62, 0.86, 7.78, 8.10, lids=1)
    _cable_box(p, -1, -1.00, -0.50, 0.62, 0.86, -8.15, -7.75, lids=1)
    _cable_box(p, 1, 0.55, 1.00, 0.62, 0.86, -8.12, -7.78, lids=1)


def underfloor_motor_car(part, cab_at_plus_z=True, with_frame=True):
    tmp = K.Part('uf_tmp')
    _muc(tmp)
    if with_frame:
        _frame(tmp, -8.3, 8.2)
    return _emit(part, tmp, not cab_at_plus_z)


# ---------------------------------------------------------------- the pantograph trailer
def _tpu(p):
    # --- SIV (75 kVA, photo 07) on the right: plain lid, two mesh grilles, lid with plates
    z0, z1 = -4.25, -0.85
    _box(p, 'uf_body', -X, -0.03, BOT, TOP, z0, z1, c=0.012)
    _flange(p, -X, -0.03, z0, z1)
    for z in (-3.6, -2.2, -1.3):
        _box(p, 'uf_steel', -X + 0.1, -0.1, BOT - 0.012, BOT, z - 0.03, z + 0.03)
    s, xf = -1, -X
    _lid(p, s, xf, -4.20, -3.50, 0.40, 0.84, mat='uf_body', levers=2, pockets=False)
    _grille(p, s, xf, -3.45, -2.65, 0.42, 0.86, divider=True)
    _grille(p, s, xf, -2.60, -1.80, 0.42, 0.86, divider=True)
    _lid(p, s, xf, -1.75, -0.90, 0.40, 0.84, plates=3, pockets=False)
    _bars(p, s, xf, (-3.475, -2.625, -1.775), 0.40, 0.86)
    _hangers(p, s, xf, z0, z1, (-4.1, -3.47, -2.62, -1.78, -0.95))
    # SIV's left face (seen from the left side through the gap): two lids
    _lid(p, 1, -0.03, -1.55, -0.95, 0.42, 0.84, levers=2, pockets=False)
    _lid(p, 1, -0.03, -4.20, -3.85, 0.42, 0.84, levers=2, pockets=False)
    # --- CP (photo 05) on the left: light grey, four lids on two rows
    z0, z1 = -4.20, -2.15
    _box(p, 'uf_light', 0.03, X, 0.36, TOP, z0, z1, c=0.012)
    _flange(p, 0.03, X, z0, z1, mat='uf_steel')
    s, xf = 1, X
    _lid(p, s, xf, -4.15, -3.35, 0.42, 0.84, mat='uf_light', plates=0, pockets=False, levers=4)           # left lid
    _lid(p, s, xf, -3.30, -2.20, 0.64, 0.84, mat='uf_light', levers=4, pockets=False, plates=1)           # upper middle (label)
    _lid(p, s, xf, -3.30, -2.75, 0.42, 0.60, mat='uf_light', levers=2, pockets=False)                    # lower middle ×2
    _lid(p, s, xf, -2.70, -2.20, 0.42, 0.60, mat='uf_light', levers=2, pockets=False)
    _hangers(p, s, xf, z0, z1, (-4.1, -3.33, -2.7, -2.25))
    _run(p, 'uf_steel', (X - 0.05, 0.86, -4.18), [('y', 0.0), ('z', -0.18)], 0.02)           # the air pipe on the CP's top (photo 05)
    # --- BCU on the left
    _box(p, 'uf_body', 0.03, X, 0.48, TOP, -1.95, -0.55, c=0.010)
    _lid(p, 1, X, -1.90, -1.15, 0.53, 0.85, plates=1)
    _lid(p, 1, X, -1.10, -0.60, 0.53, 0.85)
    _hangers(p, 1, X, -1.95, -0.55, (-1.85, -0.65))
    # --- battery box on the right (lids on both sides)
    _box(p, 'uf_light', -X, -0.03, 0.44, TOP, -0.60, 0.60, c=0.010)
    _lid(p, -1, -X, -0.55, -0.02, 0.49, 0.85, mat='uf_light', levers=2, pockets=False)
    _lid(p, -1, -X, 0.02, 0.55, 0.49, 0.85, mat='uf_light', levers=2, pockets=False)
    _lid(p, 1, -0.03, -0.55, 0.55, 0.49, 0.85, mat='uf_light', levers=4, pockets=False)
    _hangers(p, -1, -X, -0.60, 0.60, (-0.5, 0.5))
    # --- air tanks along the car: right one tank, left two
    _tank(p, (-1.02, 0.58, 1.65), 0.18, 1.55, 'z', straps=(-0.28, 0.28))
    _tank(p, (1.00, 0.58, 0.95), 0.18, 1.5, 'z', straps=(-0.28, 0.28))
    _tank(p, (1.00, 0.58, 2.65), 0.18, 1.5, 'z', straps=(-0.28, 0.28))
    _run(p, 'uf_steel', (0.85, 0.58, 1.70), [('y', 0.2)], 0.014)                      # connecting pipe of the two left tanks
    _run(p, 'uf_steel', (0.55, 0.915, 1.7), [('y', -0.18), ('x', 0.30)], 0.016)
    _run(p, 'uf_steel', (-0.55, 0.915, 0.8), [('y', -0.22), ('x', -0.40)], 0.016)
    # --- filter / cable boxes near the bogies
    _cable_box(p, -1, -X, -0.30, 0.52, TOP, 2.85, 3.85, lids=2)
    _cable_box(p, 1, 0.25, X, 0.58, TOP, 3.70, 4.20, lids=1)
    # --- small items beyond the bogies
    _cable_box(p, -1, -1.00, -0.50, 0.62, 0.86, 7.75, 8.15, lids=1)
    _cable_box(p, 1, 0.55, 1.00, 0.62, 0.86, 7.78, 8.10, lids=1)
    _cable_box(p, -1, -1.00, -0.50, 0.62, 0.86, -8.15, -7.75, lids=1)
    _cable_box(p, 1, 0.55, 1.00, 0.62, 0.86, -8.12, -7.78, lids=1)


def underfloor_trailer_pantograph(part, with_frame=True):
    tmp = K.Part('uf_tmp')
    _tpu(tmp)
    if with_frame:
        _frame(tmp, -8.3, 8.2)
    return _emit(part, tmp, False)


# ================================================================ test harness (Blender only)
def _placeholders(mats):
    """body, rails, bogies at z = ±6.0 ± 1.05"""
    m = mats
    m.add('ph_body', '#c8102e', 0.0, 0.4)
    m.add('ph_steel', '#555a60', 0.7, 0.5)
    m.add('ph_rail', '#6e5f55', 0.6, 0.5)
    m.add('ph_sleeper', '#4a4a48', 0.0, 0.9)
    body = K.Part('ph_body')
    body.box('ph_body', -1.415, 1.415, 1.0, 3.6, -8.75, 8.75)
    p = K.Part('placeholders')
    for x in (-0.75, 0.75):
        p.box('ph_rail', x - 0.0315, x + 0.0315, 0.0, 0.16, -30, 30)
    for k in range(-50, 51):
        p.box('ph_sleeper', -1.3, 1.3, 0.0, 0.14, k * 0.6 - 0.1, k * 0.6 + 0.1)
    for bz in (-6.0, 6.0):
        for dz in (-1.05, 1.05):
            for x in (-0.75, 0.75):
                p.cylinder('ph_steel', (x, 0.43, bz + dz), 0.43, 0.13, axis='x', segments=28)
            p.cylinder('ph_steel', (0, 0.43, bz + dz), 0.06, 1.7, axis='x', segments=10)
        for x in (-0.92, 0.92):
            p.box('ph_steel', x - 0.05, x + 0.05, 0.50, 0.80, bz - 1.5, bz + 1.5)
        p.box('ph_steel', -0.9, 0.9, 0.55, 0.75, bz - 0.2, bz + 0.2)
        for dz in (-1.05, 1.05):          # a motor-like block on each axle
            p.box('ph_steel', -0.35, 0.35, 0.28, 0.58, bz + dz - 0.2, bz + dz + 0.2)
    return p, body


def _render(path, eye, target, lens, size=(1600, 760), samples=40):
    scene = bpy.context.scene
    cam = scene.camera
    cam.location = B(*eye)
    cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _setup_scene(clay):
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background')
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
    sun.rotation_euler = (math.radians(45), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    # a soft fill from the other side so that both flanks read
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN'))
    fill.data.energy = 1.2
    fill.data.angle = math.radians(20)
    fill.rotation_euler = (math.radians(55), 0, math.radians(145))
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
    """print the extents of what was built, in the game frame"""
    pts = [K.G(v.co) for v in part.bm.verts]
    ys = [q[1] for q in pts]
    print('  y range %.3f .. %.3f' % (min(ys), max(ys)))
    print('  z range %.3f .. %.3f' % (min(q[2] for q in pts), max(q[2] for q in pts)))
    print('  x range %.3f .. %.3f' % (min(q[0] for q in pts), max(q[0] for q in pts)))
    zone = [q for q in pts if 4.4 < abs(q[2]) < 7.6]
    print('  bogie zone: max |x| %.3f, max y %.3f, min y %.3f' % (max(abs(q[0]) for q in zone), max(q[1] for q in zone), min(q[1] for q in zone)))


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    outdir = argv[0] if argv else '/tmp'
    clay = '--clay' in argv
    only = [a for a in argv[1:] if not a.startswith('--')]
    os.makedirs(outdir, exist_ok=True)
    K.clear_scene()
    _setup_scene(clay)
    m = K.Materials()
    add_materials(m)
    ph, body = _placeholders(m)
    if clay:
        for name, mat in m.mats.items():
            if name.startswith('uf_'):
                mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#b0aca4')
                mat.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.0
                mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7
    ph.build(None, m.mats)
    bodyobj = body.build(None, m.mats)
    cars = {}
    for name, fn in (('muc', lambda t: underfloor_motor_car(t, True)), ('tpu', underfloor_trailer_pantograph),
                     ('msc', lambda t: underfloor_motor_car(t, False))):
        if only and name not in only:
            continue
        part = K.Part('uf_' + name)
        n = fn(part)
        print('TRIANGLES', name, n)
        _check(part)
        cars[name] = part.build(None, m.mats)
    tag = '_clay' if clay else ''
    views = {
        # name: (eye, target, lens)
        'right': ((-17.0, 0.55, 0.0), (0.0, 0.85, 0.0), 70),
        'left': ((17.0, 0.55, 0.0), (0.0, 0.85, 0.0), 70),
        'q_right': ((-13.0, 0.8, 11.0), (-0.8, 0.65, 0.8), 50),
        'q_left': ((13.0, 0.8, 11.0), (0.8, 0.65, 0.8), 50),
        'q_right2': ((-13.0, 0.8, -11.0), (-0.8, 0.65, -0.8), 50),
        'q_left2': ((13.0, 0.8, -11.0), (0.8, 0.65, -0.8), 50),
        'top': ((0.0, 14.0, 0.1), (0.0, 0.0, 0.0), 40),
        'top_a': ((-5.0, 6.0, 8.0), (0.0, 0.6, 0.0), 40),
        'close_r': ((-6.5, 0.6, 1.0), (-1.3, 0.62, 0.0), 40),
        'close_l': ((6.5, 0.6, 1.0), (1.3, 0.62, 0.0), 40),
    }
    want = os.environ.get('UF_VIEWS')
    for name, obj in cars.items():
        for other, o in cars.items():
            o.hide_render = other != name
        for vn, (eye, tgt, lens) in views.items():
            if want and vn not in want.split(','):
                continue
            bodyobj.hide_render = vn.startswith('top')
            _render(os.path.join(outdir, f'{name}_{vn}{tag}.png'), eye, tgt, lens, samples=36)


if __name__ == '__main__':
    _main()
