"""
Keikyu New 1000 series, 1st batch: the bogies TH-2100AM (motor) and TH-2100AT (trailer). A part module for the Blender
model (train_kit.Part, the game's car frame, material prefix `bg_`).

  add_materials(m)
  bogie(part, zc, motor, facing=1, ceramic_jet=False) -> triangles added

One bogie centred at z = zc, rails at y = 0. `motor` adds the traction motors, gear units and TD couplings.
`facing` = -1 mirrors the bogie front to back (the motor / gear side, the bolster anchors and the levelling valve rod
change sides). `ceramic_jet` adds the ceramic-particle jet nozzles ahead of the leading axle (the +z·facing axle).

Run directly with Blender it renders test images:
  blender -t 4 --background --factory-startup --python parts/bogie_th2100.py -- <outdir> [am|at|both] [--clay]

The bogie (ja.wikipedia 京急1000形電車 (2代) / 京急2100形電車; photos 12, 13, bogies.png of the contract's folder and
Commons "File:TH-2100AM on 1009.JPG", Hahifuheho, CC0, a low side view without the body's shadow):
- Bolster bogie with direct-mount air springs (the body sits on the air springs, which stand on the bolster), bolster
  anchors to brackets hanging from the body, cylindrical-guide axle boxes (rubber-bushed guide pins inside the coil
  springs), two coil springs per axle box, tread brake units, TD parallel cardan drive (motor bogie).
- Wheel ∅ 0.86 m (contract estimate). Check on the 1009 photo: the wheel's top shows above the side frame, 0.45 m
  above the axle box cap centre at the wheelbase scale.
- Wheelbase 2.10 m: the axle box caps are 3.55 sleeper pitches apart in photos 12 and 13 (≈ 0.59–0.60 m pitch).
- Every other figure is measured on the 1009 photo (476 px/m at the axle box plane, from the 2.1 m wheelbase), axle
  box cap centre = axle centre (y = 0.43):
  - side frame: 3.02 m long (ends 0.46 m beyond the axles), top y 0.756, bottom 0.60 over the springs; the centre
    drops (fish-belly) to y 0.37 between z ±0.44 (seen under the bolster arm), the dip starting just inside the inner
    spring; its top drops to y 0.62 in the middle, where the bolster rests (est.: hidden in the photos);
    0.20 m wide (est.), centred on the axle box (x ±1.00, est. for 1,435 mm gauge, journal centres ≈ 2.0 m);
  - coil springs: ∅ 0.26 m outside, wire ∅ 0.048, 0.29 m high (y 0.31–0.60), centres 0.27 m either side of the axle,
    5.3 turns with closed ends (tight coils as in the photo);
  - axle box cap ∅ 0.236 m with a square 4-bolt flange, a U loop on top (y 0.56–0.68), the spring-seat wings reach
    0.41 m either side of the axle and their bottom is at y 0.24;
  - axle damper seats (1st/2nd batch: prepared, no damper fitted): a wedge bracket on the frame above the outer
    spring and two small blocks at the outer end of the axle box wing (both visible in the photos);
  - air springs: ∅ 0.62 m bellows, y 0.81–0.98, seen through a cut-out of the body bracket; bolster end below them:
    a lip plate (z ±0.33, y 0.785–0.81) with sloped ears, a box with a thick rim round a recessed panel (z ±0.19,
    y 0.635–0.785), and a slanted arm from under the box down to the anchor pin (bottom y 0.43, z 0.18–0.41);
  - body bracket (light grey, hangs from the body round the air spring): a wide leg sweeping down along the wheel to
    y 0.43 on one side (its outer edge an arc round the wheel), a narrow leg (z 0.30–0.39) to y 0.66 on the other,
    small lateral stops on both legs beside the seat box; bolster anchor (link with bushed eyes) at y 0.46 from
    z −0.29 (bracket) to +0.44 (bolster arm); the levelling valve rod (z +0.46, y 0.57–0.94) with its lever beside the
    narrow leg; bracket faces x 1.23–1.36 (est.: inside the body side, outside the air spring). The arrangement is point-symmetric between the two sides (est.: the photos show one side only).
- Frame colour: light grey paint (photos 12, 13 in sunlight; the 1009 photo is dusty brown at a works open day).
- Motor bogie (est., hidden in the photos except low views): the motors hang between the cross beams and the axles,
  centre 0.40 m from the axle (gear ratio 83:14 → centre distance ≈ 0.4 m), ∅ 0.46 m; the gear unit sits inside the
  wheel, the TD coupling between it and the motor; point-symmetric (gear units on opposite sides). Trailer: the same
  frame without motor mounts.
- Brake: a tread brake unit inside each wheel (dark units low between the wheels in the 1009 photo).
- Wheel profile: back-to-back 1,360 mm, width 125 mm, flange 27 mm (standard-gauge practice).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import train_kit as K  # noqa: E402
from train_kit import B  # noqa: E402

P = 'bg_'
MATERIALS = {
    # name: colour, metallic, roughness
    'frame': ('#9a9ea3', 0.0, 0.58),   # light grey paint: frame, springs, bolster, body brackets
    'dark': ('#3c3f43', 0.2, 0.6),     # motors, gear units, brake units, plates
    'wheel': ('#4f4d4b', 0.5, 0.55),   # wheel web and axle
    'tread': ('#a9a6a0', 1.0, 0.32),   # polished tread and flange
    'rubber': ('#1c1c1e', 0.0, 0.8),   # air spring bellows, bushes
}

# ---------------------------------------------------------------- dimensions (local: bogie centre at z = 0)
AXLE_Z = 1.05        # half the 2.1 m wheelbase
AXLE_Y = 0.43        # wheel radius 0.43
JOURNAL_X = 1.00     # axle box / side frame / air spring centre line
FRAME_W = 0.20
FRAME_END = 1.51
FRAME_TOP = 0.756
FRAME_BOT = 0.60
BELLY = 0.37
SPRING_DZ = 0.27
SPRING_R = 0.108     # coil centre radius (outside ∅ 0.264 with the wire)
WIRE_R = 0.024
SPRING_Y = (0.31, 0.60)
AIR_Y = (0.81, 0.98)
SEGS_WHEEL = 32


# ---------------------------------------------------------------- mesh helpers (all in Blender coords via B)
def _mark_sharp(bm, deg):
    """smooth shading with hard edges above `deg` degrees (like 'smooth by angle')"""
    lim = math.radians(deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim:
            e.smooth = False


def _copy(dst, src, slot_of, matrix=None, flip=False):
    """append src's faces to dst (keeps per-face smooth, material and sharp edges)"""
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(matrix @ v.co if matrix is not None else v.co)
    for f in src.faces:
        vs = [vmap[v] for v in f.verts]
        if flip:
            vs.reverse()
        nf = dst.faces.new(vs)
        nf.material_index = slot_of(f.material_index)
        nf.smooth = f.smooth
    for e in src.edges:
        if not e.smooth:
            ne = dst.edges.get([vmap[e.verts[0]], vmap[e.verts[1]]])
            if ne is not None:
                ne.smooth = False


def _orient_closed(bm):
    """make a closed piece's normals point outwards"""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _box(x0, x1, y0, y1, z0, z1, bevel=0.0, seg=1):
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
    for v in r['verts']:
        v.co = B(v.co.x * sx + (x0 + x1) / 2, v.co.y * sy + (y0 + y1) / 2, v.co.z * sz + (z0 + z1) / 2)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.05, sy / 2.05, sz / 2.05), segments=seg,
                        profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm


def _slab(poly, x0, x1, chamfer=0.0, seg=1):
    """a polygon in the (z, y) plane extruded across x from x0 to x1, its outline edges chamfered"""
    bm = bmesh.new()
    # drop repeated points
    pts = []
    for p in poly:
        if not pts or (abs(p[0] - pts[-1][0]) > 1e-6 or abs(p[1] - pts[-1][1]) > 1e-6):
            pts.append(p)
    if abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
        pts.pop()
    a = [bm.verts.new(B(x0, y, z)) for z, y in pts]
    b = [bm.verts.new(B(x1, y, z)) for z, y in pts]
    n = len(pts)
    caps = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], b[j], b[i]])
    _orient_closed(bm)
    if chamfer > 0:
        edges = list({e for f in caps for e in f.edges})
        bmesh.ops.bevel(bm, geom=edges, offset=chamfer, segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True)
    return bm


def _revolve(profile, centre, axis='x', segs=16, closed=False, mats=None, phase=0.0):
    """
    a surface of revolution: profile [(a, r)] with a along the axis from `centre` and r the radius (r = 0 closes the
    end in a fan). `mats[i]` is the material index of the band between profile points i and i + 1.
    """
    bm = bmesh.new()
    cx, cy, cz = centre
    rings = []
    for a, r in profile:
        if r < 1e-6:
            p = {'x': (cx + a, cy, cz), 'y': (cx, cy + a, cz), 'z': (cx, cy, cz + a)}[axis]
            rings.append([bm.verts.new(B(*p))])
            continue
        ring = []
        for i in range(segs):
            t = 2 * math.pi * i / segs + phase
            c, s = r * math.cos(t), r * math.sin(t)
            p = {'x': (cx + a, cy + c, cz + s), 'y': (cx + c, cy + a, cz + s), 'z': (cx + c, cy + s, cz + a)}[axis]
            ring.append(bm.verts.new(B(*p)))
        rings.append(ring)
    n = len(rings)
    pairs = [(k, k + 1) for k in range(n - 1)] + ([(n - 1, 0)] if closed else [])
    for band, (k, l) in enumerate(pairs):
        r0, r1 = rings[k], rings[l]
        mi = mats[band] if mats else 0
        for i in range(segs):
            j = (i + 1) % segs
            if len(r0) == 1 and len(r1) == 1:
                continue
            if len(r0) == 1:
                f = bm.faces.new([r0[0], r1[j], r1[i]])
            elif len(r1) == 1:
                f = bm.faces.new([r0[i], r0[j], r1[0]])
            else:
                f = bm.faces.new([r0[i], r0[j], r1[j], r1[i]])
            f.material_index = mi
    bm.normal_update()
    # orientation: the face farthest from the axis must face away from it
    ax = {'x': Vector((1, 0, 0)), 'y': Vector((0, 0, 1)), 'z': Vector((0, -1, 0))}[axis]
    c0 = B(*centre)

    def radial(f):
        d = f.calc_center_median() - c0
        return d - ax * d.dot(ax)

    far = max(bm.faces, key=lambda f: radial(f).length)
    if far.normal.dot(radial(far)) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return bm


def _tube(a, b, r, segs=8, caps=True):
    """a cylinder from a to b (game frame)"""
    a, b = B(*a), B(*b)
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs, radius1=r, radius2=r, depth=d.length)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4(), verts=bm.verts)
    return bm


def _helix(cx, cz, y0, y1, R, wr, turns, per_turn=10, sides=4):
    """a coil spring standing on y0 with closed (flat) end turns"""
    bm = bmesh.new()
    n = int(turns * per_turn)
    pitch = (y1 - y0 - 2 * wr) / (turns - 1.1)
    rings = []
    for i in range(n + 1):
        u = turns * i / n
        th = 2 * math.pi * u
        y = min(max(y0 + wr + pitch * (u - 0.55), y0 + wr), y1 - wr)
        c = Vector((cx + R * math.cos(th), y, cz + R * math.sin(th)))
        # tangent by finite difference
        u2 = u + 0.01
        th2 = 2 * math.pi * u2
        y2 = min(max(y0 + wr + pitch * (u2 - 0.55), y0 + wr), y1 - wr)
        t = (Vector((cx + R * math.cos(th2), y2, cz + R * math.sin(th2))) - c).normalized()
        rad = Vector((math.cos(th), 0, math.sin(th)))
        nrm = (rad - t * rad.dot(t)).normalized()
        bin_ = t.cross(nrm)
        ring = []
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            p = c + (nrm * math.cos(ph) + bin_ * math.sin(ph)) * wr
            ring.append(bm.verts.new(B(*p)))
        rings.append(ring)
    for i in range(n):
        for k in range(sides):
            l = (k + 1) % sides
            bm.faces.new([rings[i][k], rings[i][l], rings[i + 1][l], rings[i + 1][k]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    _orient_closed(bm)
    return bm


def _arc(cz, cy, r, a0, a1, n):
    """points on a circle in the (z, y) plane, angles in degrees (0 = +z, 90 = +y)"""
    return [(cz + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


# ---------------------------------------------------------------- the bogie, assembled in a local frame
class _Acc:
    """pieces of one bogie in the local frame (Blender coords), with per-face material slots by name"""

    def __init__(self):
        self.bm = bmesh.new()
        self.names = []

    def slot(self, name):
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)

    def put(self, bm, mat, sharp=35.0, copies='one'):
        """mat: a name, or a list of names indexed by the piece's face material_index.
        copies: 'one'; 'both' = also turned 180° about the vertical (the other side, point-symmetric);
        'mirror' = also mirrored across x = 0"""
        names = [mat] if isinstance(mat, str) else mat
        if sharp is not None:
            _mark_sharp(bm, sharp)
        else:
            for f in bm.faces:
                f.smooth = False

        def slot_of(i):
            return self.slot(names[min(i, len(names) - 1)])

        _copy(self.bm, bm, slot_of)
        if copies == 'both':
            _copy(self.bm, bm, slot_of, Matrix.Rotation(math.pi, 4, 'Z'))
        elif copies == 'mirror':
            _copy(self.bm, bm, slot_of, Matrix.Scale(-1, 4, Vector((1, 0, 0))), flip=True)
        bm.free()


def _side_frame(acc):
    """one side frame (x > 0): flat top over the axle boxes, fish-belly dip between them"""
    x0, x1 = JOURNAL_X - FRAME_W / 2, JOURNAL_X + FRAME_W / 2
    top, bot = [], []
    # top edge from the −z end to the +z end: flat, then down into the bolster dip
    zs_top = [-1.51, -0.66, -0.60, -0.55, -0.50, -0.45, -0.40, 0.40, 0.45, 0.50, 0.55, 0.60, 0.66, 1.51]
    for z in zs_top:
        top.append((z, FRAME_TOP - (FRAME_TOP - 0.62) * K.smoothstep(0.64, 0.40, abs(z))))
    # bottom edge back from +z to −z: rounded end corners, flat over the springs, belly in the middle
    zs_bot = [0.70, 0.66, 0.62, 0.58, 0.54, 0.50, 0.46, 0.42]
    end = []
    for a in (0, -30, -60, -90):
        t = math.radians(a)
        end.append((FRAME_END - 0.06 + 0.06 * math.cos(t), FRAME_BOT + 0.06 + 0.06 * math.sin(t)))
    bot += end
    for z in zs_bot:
        bot.append((z, FRAME_BOT - (FRAME_BOT - BELLY) * K.smoothstep(0.71, 0.44, z)))
    bot += [(-z, y) for z, y in reversed([(z, FRAME_BOT - (FRAME_BOT - BELLY) * K.smoothstep(0.71, 0.44, z)) for z in zs_bot])]
    bot += [(-z, y) for z, y in reversed(end)]
    poly = top + bot
    # top front end corner: the end of the frame is cut square, its top edge chamfered by the bevel
    acc.put(_slab(poly, x0, x1, chamfer=0.016, seg=1), 'frame', sharp=40, copies='both')


def _axle_box(acc, za):
    """axle box at axle z = za on the +x side, with its two springs and the damper seats; side = outward sign"""
    out = 1 if za > 0 else -1
    x0, x1 = JOURNAL_X - 0.13, JOURNAL_X + 0.13
    poly = [(-0.13, 0.585), (0.13, 0.585), (0.13, 0.31), (0.41, 0.31), (0.41, 0.272), (0.37, 0.24), (-0.37, 0.24),
            (-0.41, 0.272), (-0.41, 0.31), (-0.13, 0.31)]
    acc.put(_slab([(za + z, y) for z, y in poly], x0, x1, chamfer=0.012, seg=1), 'frame', sharp=40, copies='both')
    # sloped gussets on the outer face, from the box down to the wings (the trapezoid seen in the photos)
    for s in (-1, 1):
        g = [(za + s * 0.12, 0.40), (za + s * 0.12, 0.31), (za + s * 0.30, 0.31)]
        acc.put(_slab(g if s < 0 else list(reversed(g)), x1 - 0.03, x1 + 0.012), 'frame', sharp=40, copies='both')
    # the cap: square flange with 4 bolts and the domed cover
    flange = [(za + z, AXLE_Y + y) for z, y in ((-0.135, -0.10), (-0.10, -0.135), (0.10, -0.135), (0.135, -0.10),
                                                (0.135, 0.10), (0.10, 0.135), (-0.10, 0.135), (-0.135, 0.10))]
    acc.put(_slab(flange, x1, x1 + 0.016), 'frame', sharp=40, copies='both')
    prof = [(x1 + 0.016, 0.118), (x1 + 0.036, 0.116), (x1 + 0.048, 0.085), (x1 + 0.052, 0.0)]
    acc.put(_revolve(prof, (0, AXLE_Y, za), 'x', segs=14), 'frame', sharp=50, copies='both')
    for dy in (-0.105, 0.105):
        for dz in (-0.105, 0.105):
            acc.put(_box(x1 + 0.016, x1 + 0.032, AXLE_Y + dy - 0.013, AXLE_Y + dy + 0.013, za + dz - 0.013,
                         za + dz + 0.013), 'frame', sharp=40, copies='both')
    # U loop on top of the box (hooks into the frame)
    loop = [(-0.065, 0.555), (-0.04, 0.555), (-0.04, 0.68), (0.04, 0.68), (0.04, 0.555), (0.065, 0.555), (0.065, 0.69),
            (0.05, 0.705), (-0.05, 0.705), (-0.065, 0.69)]
    acc.put(_slab([(za + z, y) for z, y in loop], x1 - 0.045, x1 - 0.005), 'frame', sharp=40, copies='both')
    # axle damper lower seat: two blocks at the outer end of the wing
    for dz in (0.30, 0.355):
        acc.put(_box(x1 - 0.01, x1 + 0.035, 0.235, 0.275, za + out * dz - 0.02, za + out * dz + 0.02),
                'frame', sharp=40, copies='both')
    # axle damper upper seat: a wedge bracket on the frame's outer face above the outer spring
    fx = JOURNAL_X + FRAME_W / 2
    w = [(za + out * 0.18, 0.745), (za + out * 0.36, 0.745), (za + out * 0.36, 0.70), (za + out * 0.22, 0.665)]
    acc.put(_slab(w, fx - 0.01, fx + 0.06), 'frame', sharp=40,
            copies='both')
    # coil springs
    for dz in (-SPRING_DZ, SPRING_DZ):
        acc.put(_helix(JOURNAL_X, za + dz, SPRING_Y[0], SPRING_Y[1], SPRING_R, WIRE_R, 5.3, per_turn=8, sides=4),
                'frame', sharp=95, copies='both')


def _wheelset(acc, za):
    """two wheels and the axle at z = za"""
    # profile (x, r) of the +x wheel, closed: back face, flange, tread, front face, dished web, hub
    prof = [(0.668, 0.088), (0.680, 0.447), (0.694, 0.459), (0.722, 0.431), (0.806, 0.424), (0.806, 0.372),
            (0.770, 0.20), (0.800, 0.088)]
    # band materials: 0 wheel, 1 tread (flange back to the tread's outer edge)
    mats = [0, 1, 1, 1, 0, 0, 0]
    acc.put(_revolve(prof, (0, AXLE_Y, za), 'x', segs=SEGS_WHEEL, mats=mats), ['wheel', 'tread'], sharp=28,
            copies='both')
    acc.put(_tube((-0.89, AXLE_Y, za), (0.89, AXLE_Y, za), 0.088, segs=12, caps=False), 'wheel', sharp=50)


def _brake_unit(acc, za):
    """tread brake unit on the inner side of the +x wheel at axle za"""
    s = -1 if za > 0 else 1        # towards the bogie centre
    zw = za
    z_in, z_out = zw + s * 0.68, zw + s * 0.50
    acc.put(_box(0.63, 0.88, 0.40, 0.57, min(z_in, z_out), max(z_in, z_out)), 'dark', sharp=40,
            copies='both')
    # cylinder (diaphragm) on the inner end
    acc.put(_tube((0.55, 0.485, zw + s * 0.59), (0.63, 0.485, zw + s * 0.59), 0.07, segs=8), 'dark', sharp=50,
            copies='both')
    # brake head and shoe on the tread
    acc.put(_box(0.73, 0.80, 0.45, 0.52, min(zw + s * 0.50, zw + s * 0.47), max(zw + s * 0.50, zw + s * 0.47)),
            'dark', sharp=40, copies='both')
    shoe = []
    for a in (-17, -8, 0, 8, 17):
        t = math.radians(a)
        shoe.append((zw + s * 0.436 * math.cos(t), AXLE_Y + 0.436 * math.sin(t)))
    back = [(zw + s * 0.47 * math.cos(math.radians(a)), AXLE_Y + 0.47 * math.sin(math.radians(a))) for a in (17, 0, -17)]
    poly = shoe + back
    if s > 0:
        poly.reverse()
    acc.put(_slab(poly, 0.725, 0.80), 'dark', sharp=40, copies='both')


def _bolster(acc, motor):
    """bolster with the air spring seats, the arms to the anchor pins, the air springs, the cross beams"""
    acc.put(_box(-1.10, 1.10, 0.62, 0.81, -0.28, 0.28), 'frame', sharp=40)
    # centre pin
    acc.put(_tube((0, 0.40, 0), (0, 0.62, 0), 0.075, segs=8), 'frame', sharp=50)
    # cross beams (box section) joining the side frames in the dip
    for z in (-0.30, 0.30):
        acc.put(_box(-0.90, 0.90, 0.46, 0.60, z - 0.065, z + 0.065), 'frame', sharp=40)
    # bolster end on the +x side: air spring seat box with a framed recess, lip plate on top
    # (1009 photo: box z ±0.19 with a thick rim round a recessed panel, lip z ±0.33 with sloped ears under its ends)
    xe = 1.25
    acc.put(_box(1.10, 1.29, 0.785, 0.81, -0.33, 0.33), 'frame', sharp=40, copies='both')
    acc.put(_box(1.10, xe, 0.635, 0.786, -0.19, 0.19), 'frame', sharp=40, copies='both')
    for y0, y1, z0, z1 in ((0.763, 0.786, -0.19, 0.19), (0.635, 0.658, -0.19, 0.19), (0.658, 0.763, -0.19, -0.165),
                           (0.658, 0.763, 0.165, 0.19)):
        acc.put(_box(xe - 0.005, xe + 0.022, y0, y1, z0, z1), 'frame', sharp=40, copies='both')
    for s in (-1, 1):
        g = [(s * 0.19, 0.70), (s * 0.33, 0.785), (s * 0.19, 0.785)]
        acc.put(_slab(g, 1.16, 1.25), 'frame', sharp=40, copies='both')
    # the arm: a slanted plate from under the seat box down to the anchor pin (+z on the +x side)
    arm = [(0.19, 0.636), (-0.14, 0.636), (0.18, 0.43), (0.41, 0.43), (0.41, 0.556)]
    acc.put(_slab(arm, 1.12, 1.26, chamfer=0.012), 'frame', sharp=40, copies='both')
    # air springs: bellows on the seats, top plate against the body
    prof = [(AIR_Y[0], 0.235), (0.835, 0.288), (0.880, 0.312), (0.925, 0.300), (0.958, 0.264), (AIR_Y[1], 0.258), (AIR_Y[1], 0.0)]
    acc.put(_revolve(prof, (JOURNAL_X, 0, 0), 'y', segs=20), 'rubber', sharp=60, copies='both')


def _body_brackets(acc):
    """the anchor brackets hanging from the body round the air spring (+x side; wide leg at −z), anchors, levelling rod"""
    top = 0.97
    # outer edge: an arc round the wheel (centre z −1.10, y 0.55, r 0.50, 1009 photo), filleted into the body and
    # into the bottom where the anchor pin sits
    wide = [(-0.97, top), (-0.88, 0.968)] + _arc(-1.10, 0.55, 0.50, 55, -5, 6) + [
        (-0.585, 0.475), (-0.55, 0.448), (-0.50, 0.433), (-0.45, 0.43), (-0.27, 0.43), (-0.25, 0.445), (-0.25, 0.50),
        (-0.30, 0.52), (-0.38, 0.53), (-0.38, 0.86), (-0.372, 0.90), (-0.35, 0.935), (-0.32, 0.96), (-0.29, top)]
    acc.put(_slab(wide, 1.23, 1.36, chamfer=0.014, seg=1), 'frame', sharp=40, copies='both')
    narrow = [(0.22, top), (0.25, 0.96), (0.28, 0.935), (0.30, 0.90), (0.30, 0.69), (0.315, 0.665), (0.345, 0.655),
              (0.375, 0.665), (0.39, 0.69), (0.39, top)]
    narrow.reverse()
    acc.put(_slab(narrow, 1.29, 1.36, chamfer=0.012, seg=1), 'frame', sharp=40, copies='both')
    # bolster anchor: rod with rubber-bushed eyes, bracket pin at z −0.30, bolster pin at +0.43
    ya, xa = 0.462, 1.315
    za, zb = -0.29, 0.44
    acc.put(_tube((xa, ya, za + 0.05), (xa, ya, zb - 0.05), 0.026, segs=8), 'frame', sharp=50, copies='both')
    for z in (za, zb):
        acc.put(_revolve([(1.255, 0.052), (1.375, 0.052), (1.375, 0.0)], (0, ya, z), 'x', segs=10),
                'frame', sharp=50, copies='both')
    # levelling valve rod beside the narrow leg
    acc.put(_tube((1.32, 0.55, 0.45), (1.32, 0.94, 0.45), 0.009, segs=6), 'frame', sharp=50, copies='both')
    acc.put(_box(1.30, 1.34, 0.915, 0.94, 0.40, 0.47), 'frame', sharp=40, copies='both')
    acc.put(_tube((1.32, 0.567, 0.46), (1.32, 0.567, 0.29), 0.012, segs=6), 'frame', sharp=50, copies='both')
    # lateral stops on the legs' inner edges, beside the seat box
    acc.put(_box(1.27, 1.33, 0.66, 0.705, 0.255, 0.30), 'frame', sharp=40, copies='both')
    acc.put(_box(1.27, 1.33, 0.66, 0.705, -0.38, -0.335), 'frame', sharp=40, copies='both')


def _nameplate(acc):
    fx = JOURNAL_X + FRAME_W / 2
    acc.put(_box(fx - 0.004, fx + 0.006, 0.675, 0.725, -0.62, -0.45), 'dark', sharp=40, copies='both')


def _drive(acc, za):
    """motor, TD coupling and gear unit for the axle at za (gear unit on the −x side for za > 0)"""
    s = -1 if za > 0 else 1         # towards the centre
    sx = -1 if za > 0 else 1        # gear side
    zm = za + s * 0.40              # motor / pinion axis
    ym = 0.45
    # gear unit: a stadium round the gear wheel and the pinion
    big = _arc(za, AXLE_Y, 0.29, 0, 360, 12)[:-1]
    small = _arc(zm, ym, 0.15, 0, 360, 8)[:-1]
    pts = big + small
    hull = _hull(pts)
    gx0, gx1 = sorted((sx * 0.58, sx * 0.44))
    acc.put(_slab(hull, gx0, gx1), 'dark', sharp=40)
    # gear case hanger to the cross beam
    acc.put(_tube((sx * 0.51, 0.58, zm), (sx * 0.51, 0.60, za + s * 0.70), 0.03, segs=6), 'dark', sharp=50)
    # TD coupling (flexible plates) between pinion and motor
    acc.put(_revolve([(0, 0.0), (0, 0.125), (0.072, 0.125), (0.072, 0.0)],
                     (sx * 0.44 - (0.072 if sx > 0 else 0), ym, zm), 'x', segs=12), 'dark', sharp=40)
    # motor: frame cylinder with end bells, from the coupling across the bogie
    mx0 = sx * 0.36
    mx1 = -sx * 0.30
    a0, a1 = min(mx0, mx1), max(mx0, mx1)
    prof = [(a0, 0.0), (a0, 0.17), (a0 + 0.06, 0.23), (a1 - 0.06, 0.23), (a1, 0.18), (a1, 0.0)]
    acc.put(_revolve(prof, (0, ym, zm), 'x', segs=14), 'dark', sharp=40)
    # cooling ribs / terminal box on top and the mounting lug to the cross beam
    acc.put(_box(-0.18, 0.12, 0.60, 0.70, zm - 0.10, zm + 0.10), 'dark', sharp=40)
    zb = 0.30 if za > 0 else -0.30
    acc.put(_box(-0.22, 0.16, 0.52, 0.60, min(zb, zm), max(zb, zm)), 'dark', sharp=40)


def _hull(pts):
    """convex hull of (z, y) points, counter-clockwise"""
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _ceramic_jet(acc):
    """nozzles ahead of the leading (+z) axle, on brackets from the frame ends (both rails)"""
    z = FRAME_END + 0.06
    acc.put(_box(0.76, 1.00, 0.62, 0.66, FRAME_END - 0.06, z + 0.04), 'dark', sharp=40, copies='mirror')
    acc.put(_tube((0.78, 0.64, z), (0.78, 0.22, z), 0.022, segs=8), 'dark', sharp=50, copies='mirror')
    acc.put(_box(0.745, 0.815, 0.12, 0.23, z - 0.05, z + 0.03), 'dark', sharp=40, copies='mirror')


def bogie(part, zc, motor, facing=1, ceramic_jet=False):
    """one TH-2100AM (motor) / TH-2100AT (trailer) bogie centred at z = zc; returns the triangles added"""
    acc = _Acc()
    _side_frame(acc)
    _nameplate(acc)
    for za in (AXLE_Z, -AXLE_Z):
        _axle_box(acc, za)
        _wheelset(acc, za)
        _brake_unit(acc, za)
        if motor:
            _drive(acc, za)
    _bolster(acc, motor)
    _body_brackets(acc)
    if ceramic_jet:
        _ceramic_jet(acc)
    # place: facing −1 mirrors front to back (Blender y), then to zc
    m = Matrix.Translation(B(0, 0, zc))
    flip = facing < 0
    if flip:
        m = m @ Matrix.Scale(-1, 4, Vector((0, 1, 0)))
    names = acc.names
    tris = sum(len(f.verts) - 2 for f in acc.bm.faces)
    _copy(part.bm, acc.bm, lambda i: part.slot(P + names[i]), m, flip=flip)
    acc.bm.free()
    return tris


def add_materials(m):
    for name, (colour, metal, rough) in MATERIALS.items():
        if P + name not in m.mats:
            m.add(P + name, colour, metallic=metal, roughness=rough)


# ---------------------------------------------------------------- test harness
def _scene(body=True, clay=False):
    scene = bpy.context.scene
    mats = K.Materials()
    add_materials(mats)
    mats.add('rail', '#6b5a4c', metallic=0.6, roughness=0.5)
    mats.add('sleeper', '#8a8780', roughness=0.9)
    mats.add('body', '#c8102e', roughness=0.35)
    if clay:
        for n in MATERIALS:
            p = mats[P + n].node_tree.nodes['Principled BSDF']
            p.inputs['Base Color'].default_value = K.srgb('#b8b8b8')
            p.inputs['Metallic'].default_value = 0.0
            p.inputs['Roughness'].default_value = 0.7
    root = K.car_empty('stage')
    track = K.Part('track')
    for x in (-0.7495, 0.7495):
        track.box('rail', x - 0.0315, x + 0.0315, -0.16, 0.0, -12, 12)
    for i in range(-20, 21):
        track.box('sleeper', -1.2, 1.2, -0.36, -0.18, i * 0.6 - 0.12, i * 0.6 + 0.12)
    track.build(root, mats)
    if body:
        b = K.Part('body')
        b.box('body', -1.415, 1.415, 1.0, 3.6, -9.0, 9.0)
        b.build(root, mats)
    return mats, root


def _world_and_ground():
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background')
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'MULTIPLE_SCATTERING'
    except TypeError:
        pass
    sky.sun_elevation = math.radians(35)
    sky.sun_rotation = math.radians(150)
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.05
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    bmesh.ops.translate(bm, vec=(0, 0, -0.36), verts=bm.verts)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    scene.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#6f6d68')
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 2.2
    sun.data.angle = math.radians(3)
    # from high on the +x side, a little ahead
    sun.rotation_euler = (math.radians(40), 0, math.radians(70))
    scene.collection.objects.link(sun)


def _render(path, eye, target, lens=35, ortho=None, size=(1600, 900), samples=48):
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.location = B(*eye)
    d = B(*target) - B(*eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    cam.data.clip_start = 0.05
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'AgX'
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else '/tmp/bogie'
    which = argv[1] if len(argv) > 1 and not argv[1].startswith('--') else 'both'
    clay = '--clay' in argv
    views = [a.split('=', 1)[1] for a in argv if a.startswith('--views=')]
    views = views[0].split(',') if views else ['side', 'low34', 'top', 'body', 'photo', 'under']
    os.makedirs(out, exist_ok=True)
    K.clear_scene()
    _world_and_ground()
    mats, root = _scene(body=False, clay=clay)
    parts = {}
    for key, motor in (('am', True), ('at', False)):
        if which not in (key, 'both'):
            continue
        p = K.Part('bogie_' + key)
        n = bogie(p, 0.0, motor, facing=1, ceramic_jet=(key == 'am'))
        print(f'BOGIE {key}: {n} triangles')
        parts[key] = p.build(root, mats)
    body = K.Part('body')
    body.box('body', -1.415, 1.415, 1.0, 3.6, -9.0, 9.0)
    bobj = body.build(root, mats)
    suffix = '_clay' if clay else ''
    for key, obj in parts.items():
        for k2, o2 in parts.items():
            o2.hide_render = k2 != key
        cams = {
            'side': dict(eye=(12.0, 0.55, 0.0), target=(0, 0.55, 0.0), ortho=3.6, size=(1600, 900)),
            'photo': dict(eye=(3.3, 0.45, 0.0), target=(0, 0.52, 0.0), lens=24, size=(1600, 620)),
            'low34': dict(eye=(3.6, 0.30, 3.4), target=(0.3, 0.50, 0.0), lens=32),
            'top': dict(eye=(0.0, 12.0, 0.001), target=(0, 0, 0), ortho=3.8, size=(1200, 1000)),
            'body': dict(eye=(4.6, 0.95, 4.2), target=(0.6, 0.62, 0.0), lens=30),
            'under': dict(eye=(2.4, 0.12, -3.2), target=(-0.2, 0.55, 0.3), lens=26),
            'end': dict(eye=(0.0, 0.6, 9.0), target=(0, 0.6, 0), ortho=3.2, size=(1200, 900)),
        }
        for v in views:
            c = cams[v]
            bobj.hide_render = v not in ('body', 'photo', 'side')
            _render(os.path.join(out, f'{key}_{v}{suffix}.png'), c['eye'], c['target'], lens=c.get('lens', 35),
                    ortho=c.get('ortho'), size=c.get('size', (1600, 900)))


if __name__ == '__main__':
    _main()
