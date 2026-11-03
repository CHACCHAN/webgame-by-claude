"""
Keikyu New 1000 series, 1st batch: the coupler gear in the cab skirt's opening and the semi-permanent bar coupler
between the cars of a set. A part module for the Blender model (train_kit.Part, the game's car frame, material
prefix `cp_`).

  front_coupler(part, z_face=9.0, y_axis=0.88, horn=0.10)   tight-lock head, shank, draft gear, electric coupler,
                                                            hoses and cocks, cross bar, the two vent boxes
  intercar_coupler(part, z_mid)                             bar coupler centred on z_mid (car ends at z_mid ± 0.25)
  add_materials(m)

Each returns the number of triangles it added. Run directly with Blender it renders test images:
  blender -t 4 --background --factory-startup --python parts/coupler_n1000.py -- <outdir> [--views a,b,...] [--clay]

Figures and where they come from. Photo 02 (c02_meas.png, head-on, 1:1 crop of the original) is the main source:
its scale is ≈ 253 px/m (front width 2.83 m over x 20…735); pixels are square, so 253 px/m vertically as well.
Heights are anchored on the coupler axis (Japanese standard coupler height 880 mm), every other height is an offset
from the axis measured on photo 02 (axis = middle between the two air ports, crop y 738.8):
- red body bottom edge 0.10 above the axis (y ≈ 0.985); notch in the red body above the head: x ±0.33, up to 0.21
  above the axis (y ≈ 1.09); opening bottom 0.50 below (y ≈ 0.38); skirt bottom 0.65 below (y ≈ 0.23).
  NB: the brief's figures (opening 0.45…1.00, red bottom 1.05) put the axis at ≈ 0.90–0.95 instead; `y_axis`
  moves everything of the front coupler together.
- Opening x ±0.636 (crop x 227…548), bottom corners r ≈ 0.065.
- Shibata-type tight-lock head (密着連結器), photos 02 / 08 / 09 / 18 / 19: face frame 0.34 wide × 0.19 high; top and
  bottom flanges 0.33 × 0.078 with the main-reservoir air ports (ring ∅ 0.068, black gasket, ∅ 0.028 bore) 0.13
  above / below the axis; two bolt holes 0.085 beside the top port. Seen from ahead the guide horn (凸) is on the
  left (car's −x; it ends in a worn, roughly triangular tip with a pin hole), the socket (凹, 0.107 × 0.144) on the
  right. A lug on the left side and the release lever rod on the right side (photos 02 / 18).
  Horn length 0.10 (est. from its side face in the 3/4 photo 08). The head is 0.20 deep, the shank 0.15 × 0.13
  (est.), running back to the draft gear at the back wall (z ≈ 8.35–8.47, est.).
- Electric coupler (電気連結器) under the head: 0.45 wide × 0.19 high, rounded light-grey cover (photos 02 / 11 / 18),
  its front 0.035 behind the head's face (est.); hangs from the head and the cross bar on two side links: a rod and
  plate with a pin on the left, a flat link and plate with a hole on the right (photo 02 / 18).
- Cross bar: a channel 0.09 high (y 0.24…0.15 below the axis), x ±0.575, bolted end plates with 2 bolts each
  (photo 02); its front ≈ 0.06 behind the skirt face (est.).
- Vent boxes at the sides of the opening: x ±(0.441…0.566), from 0.094 above to 0.123 below the axis, a raised frame,
  an oval louvre 0.059 × 0.112 with 6 slats (photos 02 / 08 / 18).
- Air hoses: two black hoses coming down behind the electric coupler to cocks on the back wall (photo 11 shows the
  black hoses at the bottom of the opening; the routing behind is est.).
- Intercar: semi-permanent bar coupler (est., not visible on the photos: hidden by the gangway): shanks ∅ 0.13, a
  bolted flange joint at z_mid, draft gear boxes at the car ends, MR / BP hoses hanging between the cars with cocks.
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
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import train_kit as K

B = K.B

# name: (colour, metallic, roughness)
MATS = {
    'cp_steel': ('#9a9892', 0.35, 0.5),     # the coupler's grey paint, brackets, bar
    'cp_grime': ('#5e5b56', 0.3, 0.65),     # dirty grey: flanges, shank, carrier
    'cp_worn': ('#c6c3ba', 0.3, 0.42),      # worn bright guide horn, port bushes
    'cp_cover': ('#cfcfcb', 0.05, 0.45),    # electric coupler cover, vent frames
    'cp_dark': ('#2a2a2d', 0.3, 0.7),       # socket, draft gear, things in the shadow at the back
    'cp_rubber': ('#111112', 0.0, 0.8),     # hoses, gaskets
}


def add_materials(m):
    for name, (col, met, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, col, metallic=met, roughness=rough)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


# ---------------------------------------------------------------- mesh pieces (game frame), kept with smooth flags
def _basis(d):
    d = Vector(d).normalized()
    a = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
    u = d.cross(a).normalized()
    return d, u, d.cross(u).normalized()


class _Piece:
    """a temporary bmesh in Blender coords built from game-frame points; faces carry a material name"""

    def __init__(self, recalc=True, angle=35.0):
        self.bm = bmesh.new()
        self.mats = []
        self.recalc = recalc
        self.angle = angle

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def v(self, p):
        return self.bm.verts.new(B(*p))

    def f(self, verts, mat):
        face = self.bm.faces.new(verts)
        face.material_index = self.mi(mat)
        return face

    def loft(self, rings, mat, cap0=True, cap1=True, closed=True):
        """rings joined in order; mat may be a list with one material per band (caps take the end bands')"""
        mats = mat if isinstance(mat, list) else [mat] * (len(rings) - 1)
        vr = [[self.v(p) for p in r] for r in rings]
        n = len(rings[0])
        m = n if closed else n - 1
        for i in range(len(vr) - 1):
            for k in range(m):
                k1 = (k + 1) % n
                self.f([vr[i][k], vr[i][k1], vr[i + 1][k1], vr[i + 1][k]], mats[i])
        if cap0:
            self.f(list(reversed(vr[0])), mats[0])
        if cap1:
            self.f(vr[-1], mats[-1])
        return vr

    def box(self, mat, x0, x1, y0, y1, z0, z1, ch=0.0):
        r = [[(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)] for z in (z0, z1)]
        start = len(self.bm.faces)
        self.loft(r, mat)
        if ch > 0:
            self.bm.faces.ensure_lookup_table()
            faces = self.bm.faces[start:]
            edges = list({e for f in faces for e in f.edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=min(ch, (x1 - x0) / 2.1, (y1 - y0) / 2.1, (z1 - z0) / 2.1),
                            segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)

    def prism(self, mat, axis, poly, a0, a1):
        """a 2D polygon extruded along a game axis: 'x' → poly in (y, z), 'y' → (x, z), 'z' → (x, y)"""
        def p3(p, a):
            return {'x': (a, p[0], p[1]), 'y': (p[0], a, p[1]), 'z': (p[0], p[1], a)}[axis]
        self.loft([[p3(p, a0) for p in poly], [p3(p, a1) for p in poly]], mat)

    def cyl(self, mat, a, b, r, n=12, cap0=True, cap1=True, r1=None):
        a, b = Vector(a), Vector(b)
        _, u, w = _basis(b - a)
        rings = []
        for c, rr in ((a, r), (b, r if r1 is None else r1)):
            rings.append([tuple(c + rr * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w)) for k in range(n)])
        self.loft(rings, mat, cap0, cap1)

    def tube(self, mat, pts, r, n=10, cap=True):
        """a round tube along a polyline (parallel-transported frames)"""
        pts = [Vector(p) for p in pts]
        tang = []
        for i in range(len(pts)):
            d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
            tang.append(d.normalized())
        _, u, _ = _basis(tang[0])
        rings = []
        for i, p in enumerate(pts):
            t = tang[i]
            u = (u - t * u.dot(t)).normalized()
            w = t.cross(u)
            rings.append([tuple(p + r * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w)) for k in range(n)])
        self.loft(rings, mat, cap, cap)

    def beam(self, mat, a, b, w, h):
        """a square beam from a to b (game frame), w across (horizontal) × h"""
        a, b = Vector(a), Vector(b)
        d = (b - a).normalized()
        side = d.cross(Vector((0, 1, 0)))
        side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
        up = side.cross(d).normalized()
        rect = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        self.loft([[tuple(c + side * u + up * v) for u, v in rect] for c in (a, b)], mat)

    def sweep(self, mat, path, prof):
        """a profile (y, d) swept along a plan path [(x, z)]; d is the offset along the path's front normal (mitred)"""
        segs = []
        for i in range(len(path) - 1):
            t = Vector((path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])).normalized()
            segs.append(Vector((-t.y, t.x)))          # front normal (+z for a path running +x)
        rings = []
        for i, (x, z) in enumerate(path):
            na = segs[max(i - 1, 0)]
            nb = segs[min(i, len(segs) - 1)]
            n = (na + nb).normalized()
            k = 1.0 / max(0.3, n.dot(nb))
            rings.append([(x + n.x * d * k, y, z + n.y * d * k) for y, d in prof])
        self.loft(rings, mat)

    def chamfer(self, offset, min_angle=60.0, faces=None):
        self.bm.normal_update()
        lim = math.radians(min_angle)
        src = faces if faces is not None else self.bm.faces
        edges = list({e for f in src for e in f.edges if len(e.link_faces) == 2
                      and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > lim})
        if edges:
            bmesh.ops.bevel(self.bm, geom=edges, offset=offset, segments=1, profile=0.5, affect='EDGES',
                            clamp_overlap=True)


def _lathe(part, centre, axis, prof, n=16, angle=40.0):
    """
    A surface of revolution: prof = [(r, t, mat)] along the axis (t measured from centre); the outside is on the
    right of the profile's direction of travel in the (r, t) plane, so a profile running forward on the outer radius
    and inward over the front faces out. Segment i takes the material of point i. r = 0 ends close in a fan.
    """
    pc = _Piece(recalc=False, angle=angle)
    c = Vector(centre)
    d, u, w = _basis(axis)
    rings = []
    for r, t, _ in prof:
        base = c + d * t
        if r < 1e-9:
            rings.append([pc.v(tuple(base))])
        else:
            rings.append([pc.v(tuple(base + r * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w)))
                          for k in range(n)])
    for i in range(len(prof) - 1):
        r0, t0, mat = prof[i]
        r1, t1, _ = prof[i + 1]
        dr, dt = r1 - r0, t1 - t0
        nr, nt = dt, -dr          # outward normal in the (r, t) plane
        for k in range(n):
            k1 = (k + 1) % n
            a, b = rings[i], rings[i + 1]
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                vs = [a[0], b[k], b[k1]]
            elif len(b) == 1:
                vs = [a[k], a[k1], b[0]]
            else:
                vs = [a[k], a[k1], b[k1], b[k]]
            face = pc.f(vs, mat)
            ang = 2 * math.pi * (k + 0.5) / n
            radial = math.cos(ang) * u + math.sin(ang) * w
            expect = B(*(nr * radial + nt * d))
            face.normal_update()
            if face.normal.dot(expect) < 0:
                face.normal_flip()
    _emit(part, pc)


def _emit(part, pc):
    """hand a piece to the part: smooth faces, sharp edges above the piece's angle, materials by name"""
    bm = pc.bm
    if pc.recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    lim = math.radians(pc.angle)
    vmap = {v: part.bm.verts.new(v.co) for v in bm.verts}
    for f in bm.faces:
        nf = part.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = part.slot(pc.mats[f.material_index])
        nf.smooth = True
    for e in bm.edges:
        lf = e.link_faces
        sharp = len(lf) != 2 or lf[0].normal.angle(lf[1].normal, 0) > lim or lf[0].material_index != lf[1].material_index
        if sharp:
            ne = part.bm.edges.get([vmap[e.verts[0]], vmap[e.verts[1]]])
            if ne is not None:
                ne.smooth = False
    bm.free()


def _chamfered_rect(x0, x1, y0, y1, c):
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


def _rounded_rect(x0, x1, y0, y1, r, seg=3):
    out = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for s in range(seg + 1):
            a = math.radians(a0 + 90 * s / seg)
            out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def _bolt(part, x, y, z, r=0.011, h=0.008, mat='cp_steel', axis=(0, 0, 1)):
    """a hex bolt head standing on a surface at z (facing +axis)"""
    _lathe(part, (x, y, z), axis, [(r, -0.002, mat), (r, h * 0.7, mat), (r * 0.7, h, mat), (0, h, mat)], n=6, angle=20)


# ---------------------------------------------------------------- the front coupler
def _head(part, zf, Y0, horn):
    st, dk, wn, gr = 'cp_steel', 'cp_dark', 'cp_worn', 'cp_grime'
    # face frame with the socket (凹) on the right as seen from ahead (+x), blind pocket 0.16 deep
    x0, x1, y0, y1, zb = -0.17, 0.17, Y0 - 0.095, Y0 + 0.095, zf - 0.20
    hx0, hx1, hy0, hy1, zp = 0.035, 0.142, Y0 - 0.070, Y0 + 0.074, zf - 0.16
    pc = _Piece()
    O = [pc.v(p) for p in ((x0, y0, zf), (x1, y0, zf), (x1, y1, zf), (x0, y1, zf))]
    Ob = [pc.v(p) for p in ((x0, y0, zb), (x1, y0, zb), (x1, y1, zb), (x0, y1, zb))]
    H = [pc.v(p) for p in ((hx0, hy0, zf), (hx1, hy0, zf), (hx1, hy1, zf), (hx0, hy1, zf))]
    Hb = [pc.v(p) for p in ((hx0, hy0, zp), (hx1, hy0, zp), (hx1, hy1, zp), (hx0, hy1, zp))]
    for i in range(4):
        j = (i + 1) % 4
        pc.f([Ob[i], Ob[j], O[j], O[i]], st)
        pc.f([O[i], O[j], H[j], H[i]], st)
        pc.f([H[i], H[j], Hb[j], Hb[i]], st)
    pc.f(list(reversed(Ob)), st)
    pc.f(Hb, dk)
    bmesh.ops.recalc_face_normals(pc.bm, faces=pc.bm.faces)
    pc.chamfer(0.009)
    _emit(part, pc)

    # guide horn (凸) on the left: a blunt pyramid (photo 02 / 18: four sloping faces meeting in an X, the apex a
    # little low, the pin hole in the upper face), worn bright
    bx0, bx1, by0, by1 = -0.112, 0.016, Y0 - 0.066, Y0 + 0.070
    bxc = (bx0 + bx1) / 2
    base = [(x, y, zf - 0.004) for x, y in _chamfered_rect(bx0, bx1, by0, by1, 0.012)]
    neck = [(x, y, zf + 0.012) for x, y in _chamfered_rect(bx0 + 0.002, bx1 - 0.002, by0 + 0.002, by1 - 0.002, 0.012)]
    ty = Y0 - 0.012
    tip = [(x, y, zf + horn) for x, y in _chamfered_rect(bxc - 0.022, bxc + 0.022, ty - 0.02, ty + 0.02, 0.008)]
    pc = _Piece(angle=25)
    pc.loft([base, neck, tip], wn, cap0=False, cap1=True)
    _emit(part, pc)
    # pin hole in the upper face, 45 % of the way up the slope
    a_, b_ = Vector((by1 - 0.002, zf + 0.012)), Vector((ty + 0.02, zf + horn))
    q = a_ + (b_ - a_) * 0.42
    slope = (b_ - a_).normalized()
    nrm = Vector((0.0, slope.y, -slope.x))
    if nrm.y < 0:
        nrm = -nrm
    _lathe(part, (bxc + 0.004, q.x + nrm.y * 0.0005, q.y + nrm.z * 0.0005), (0, nrm.y, nrm.z),
           [(0.0145, -0.004, dk), (0.0145, 0.0012, dk), (0, 0.0012, dk)], n=12)

    # top and bottom flanges with the air ports and bolt holes
    for s in (1, -1):
        yp = Y0 + s * 0.13
        # outline: a plate 0.33 wide, its outer edge humped round the port (photo 02 / 18)
        y_in, y_out = Y0 + s * 0.088, Y0 + s * 0.152
        rb = 0.046
        hump = [(rb * math.cos(math.radians(a)), yp + s * rb * math.sin(math.radians(a))) for a in range(30, 151, 15)]
        poly = [(-0.165, y_in), (0.165, y_in), (0.165, y_out - s * 0.018), (0.147, y_out),
                (rb + 0.014, y_out)] + hump + [(-rb - 0.014, y_out), (-0.147, y_out), (-0.165, y_out - s * 0.018)]
        if s < 0:
            poly.reverse()
        pc = _Piece()
        pc.prism(gr, 'z', poly, zf - 0.19, zf - 0.024)
        pc.chamfer(0.006)
        _emit(part, pc)
        _lathe(part, (0, yp, zf - 0.024), (0, 0, 1), [
            (0.036, -0.004, gr), (0.036, 0.010, gr), (0.032, 0.014, wn), (0.024, 0.014, wn),
            (0.024, 0.017, 'cp_rubber'), (0.015, 0.017, 'cp_rubber'), (0.015, 0.004, dk), (0, 0.004, dk)], n=20)
        for xb in (-0.085, 0.085):
            _lathe(part, (xb, yp + s * 0.004, zf - 0.024), (0, 0, 1), [(0.016, -0.002, gr), (0.016, 0.004, gr),
                   (0.011, 0.004, dk), (0.011, 0.0, dk), (0, 0.0, dk)], n=10)
    # lug on the left side, release lever on the right
    pc = _Piece()
    pc.box(st, -0.206, -0.168, Y0 - 0.062, Y0 + 0.018, zf - 0.13, zf - 0.025, ch=0.006)
    pc.box(st, 0.168, 0.196, Y0 - 0.022, Y0 + 0.006, zf - 0.075, zf - 0.035, ch=0.004)
    _emit(part, pc)
    pc = _Piece(angle=50)
    pc.tube(st, [(0.19, Y0 - 0.125, zf - 0.07), (0.19, Y0 - 0.02, zf - 0.055), (0.19, Y0 + 0.002, zf - 0.04),
                 (0.19, Y0 + 0.006, zf - 0.012)], 0.008, n=8)
    _emit(part, pc)

    # behind the face: the head tapers into the shank, which runs back to the draft gear at the back wall
    pc = _Piece()
    pc.loft([[(x, y, zf - 0.185) for x, y in _chamfered_rect(-0.155, 0.155, Y0 - 0.16, Y0 + 0.16, 0.03)],
             [(x, y, zf - 0.30) for x, y in _chamfered_rect(-0.075, 0.075, Y0 - 0.065, Y0 + 0.065, 0.02)]],
            gr, cap0=False, cap1=False)
    _emit(part, pc)
    pc = _Piece()
    pc.prism(gr, 'z', _chamfered_rect(-0.075, 0.075, Y0 - 0.065, Y0 + 0.065, 0.02), 8.47, zf - 0.30)
    _emit(part, pc)


def _draft_gear(part, zf, Y0):
    st, dk = 'cp_steel', 'cp_dark'
    pc = _Piece()
    pc.box(dk, -0.18, 0.18, Y0 - 0.11, Y0 + 0.11, 8.355, 8.47, ch=0.01)        # draft gear housing
    pc.box('cp_grime', -0.13, 0.13, Y0 - 0.095, Y0 + 0.095, 8.47, 8.49, ch=0.005)      # yoke plate
    pc.box('cp_grime', -0.13, 0.13, Y0 - 0.10, Y0 - 0.074, 8.47, 8.66, ch=0.004)       # coupler carrier
    for s in (-1, 1):
        pc.box('cp_grime', s * 0.12 - 0.01, s * 0.12 + 0.01, Y0 - 0.10, Y0 + 0.08, 8.47, 8.50)  # carrier hangers
        pc.box(dk, s * 0.35 - 0.02, s * 0.35 + 0.02, Y0 - 0.14, Y0 + 0.10, 8.355, 8.44, ch=0.006)  # brackets
    _emit(part, pc)
    # centring springs, shank to the brackets
    for s in (-1, 1):
        pc = _Piece(angle=40)
        pc.cyl(dk, (s * 0.08, Y0 - 0.02, 8.60), (s * 0.33, Y0 - 0.04, 8.42), 0.020, n=10)
        _emit(part, pc)
        pc = _Piece(angle=40)
        pc.cyl('cp_grime', (s * 0.16, Y0 - 0.027, 8.54), (s * 0.27, Y0 - 0.036, 8.465), 0.028, n=10)   # spring cup
        _emit(part, pc)


def _electric_coupler(part, zf, Y0):
    st, dk, cv = 'cp_steel', 'cp_dark', 'cp_cover'
    ef = zf - 0.035                     # front of the cover
    ya, yb = Y0 - 0.453, Y0 - 0.262     # 0.427 … 0.618 at the standard height
    r = 0.085
    prof = [(ya, ef - 0.20)]
    for k in range(7):                  # bottom front round
        a = math.radians(-90 + 90 * k / 6)
        prof.append((ya + r + r * math.sin(a), ef - r + r * math.cos(a)))
    for k in range(7):                  # top front round
        a = math.radians(90 * k / 6)
        prof.append((yb - r + r * math.sin(a), ef - r + r * math.cos(a)))
    prof.append((yb, ef - 0.20))
    pc = _Piece(angle=30)
    pc.prism(cv, 'x', prof, -0.224, 0.224)
    pc.chamfer(0.005, min_angle=70)
    _emit(part, pc)
    pc = _Piece()
    pc.box(dk, -0.20, 0.20, ya + 0.018, yb - 0.02, 8.50, ef - 0.195, ch=0.008)    # body behind the cover
    _emit(part, pc)

    # left: plate with the pin, rod up to a bracket on the cross bar, arm from the head
    pc = _Piece()
    pc.box(st, -0.339, -0.226, Y0 - 0.347, Y0 - 0.275, ef - 0.06, ef - 0.045, ch=0.003)
    pc.box(st, -0.285, -0.255, Y0 - 0.33, Y0 - 0.29, ef - 0.10, ef - 0.06)
    pc.box(st, -0.296, -0.244, Y0 - 0.18, Y0 - 0.135, 8.79, 8.875, ch=0.004)
    pc.box(st, 0.21, 0.27, Y0 - 0.18, Y0 - 0.135, 8.79, 8.875, ch=0.004)
    # right: plate with a hole, flat link up to the bar
    pc.box(st, 0.235, 0.307, Y0 - 0.38, Y0 - 0.28, ef - 0.06, ef - 0.045, ch=0.003)
    pc.box(st, 0.236, 0.262, Y0 - 0.30, Y0 - 0.27, 8.855, ef - 0.06)
    pc.box(st, 0.228, 0.248, Y0 - 0.29, Y0 - 0.135, 8.85, 8.866)
    _emit(part, pc)
    pc = _Piece(angle=50)
    pc.cyl(st, (-0.27, Y0 - 0.315, 8.862), (-0.27, Y0 - 0.135, 8.862), 0.009, n=8)
    pc.box(st, -0.26, -0.24, Y0 - 0.35, Y0 - 0.33, ef - 0.10, ef - 0.06)
    _emit(part, pc)
    _lathe(part, (-0.262, Y0 - 0.327, ef - 0.045), (0, 0, 1), [(0.012, -0.001, st), (0.012, 0.012, st), (0.008, 0.02, st),
           (0.008, 0.024, 'cp_worn'), (0, 0.026, 'cp_worn')], n=10)
    _lathe(part, (0.272, Y0 - 0.325, ef - 0.045), (0, 0, 1), [(0.012, -0.001, dk), (0.012, 0.001, dk), (0, 0.001, dk)], n=10)
    # arms from the head's bottom corners to the link tops
    pc = _Piece()
    for a, b in (((-0.15, Y0 - 0.118, 8.875), (-0.27, Y0 - 0.15, 8.865)), ((0.15, Y0 - 0.118, 8.875), (0.238, Y0 - 0.15, 8.865))):
        pc.prism(st, 'z', [(a[0], a[1] - 0.012), (b[0], b[1] - 0.012), (b[0], b[1] + 0.012), (a[0], a[1] + 0.012)]
                 if a[0] < b[0] else [(b[0], b[1] - 0.012), (a[0], a[1] - 0.012), (a[0], a[1] + 0.012), (b[0], b[1] + 0.012)],
                 8.855, 8.882)
    _emit(part, pc)


def _cross_bar(part, Y0):
    st = 'cp_steel'
    ya, yb = Y0 - 0.242, Y0 - 0.152          # 0.638 … 0.728
    zb, zfr = 8.71, 8.79
    # the coupler carrier: a channel open at the back right across the opening (photo 08: lit all along; photo 02:
    # its middle is in the head's shadow); the head's bottom flange overlaps its top by 0.016 seen from ahead
    prof = [(ya, zb), (ya, zfr), (yb, zfr), (yb, zb), (yb - 0.012, zb), (yb - 0.012, zfr - 0.014),
            (ya + 0.012, zfr - 0.014), (ya + 0.012, zb)]
    pc = _Piece()
    pc.prism(st, 'x', prof, -0.575, 0.575)
    _emit(part, pc)
    # stays from the skirt's bottom bar back and up into the frame (photo 08: light diagonals at the opening's
    # bottom corners; photo 02: faint, rising towards the middle)
    pc = _Piece()
    for s in (-1, 1):
        pc.beam('cp_grime', (s * 0.47, Y0 - 0.47, 8.80), (s * 0.20, Y0 - 0.38, 8.36), 0.04, 0.03)
    _emit(part, pc)
    pc = _Piece()
    for s in (-1, 1):
        xa, xb = sorted((s * 0.437, s * 0.556))
        pc.box(st, xa, xb, ya + 0.008, yb - 0.022, zfr, zfr + 0.008, ch=0.002)       # end plate
        xa, xb = sorted((s * 0.545, s * 0.575))
        pc.box('cp_dark', xa, xb, ya, yb, 8.36, zb + 0.005, ch=0.004)                # end bracket to the back
    _emit(part, pc)
    for s in (-1, 1):
        for xb in (s * 0.457, s * 0.536):
            _bolt(part, xb, (ya + yb) / 2 - 0.007, zfr + 0.008)


def _vent_box(part, xc, Y0):
    st, cv, dk = 'cp_steel', 'cp_cover', 'cp_dark'
    w, ya, yb = 0.125, Y0 - 0.123, Y0 + 0.094
    zf = 8.75
    pc = _Piece()
    pc.box('cp_grime', xc - w / 2, xc + w / 2, ya, yb, 8.40, zf, ch=0.008)
    _emit(part, pc)
    # raised frame round the face
    pc = _Piece()
    out = _rounded_rect(xc - w / 2 + 0.004, xc + w / 2 - 0.004, ya + 0.004, yb - 0.004, 0.012, 2)
    inn = _rounded_rect(xc - w / 2 + 0.016, xc + w / 2 - 0.016, ya + 0.016, yb - 0.016, 0.006, 2)
    vo = [pc.v((x, y, zf + 0.012)) for x, y in out]
    vi = [pc.v((x, y, zf + 0.012)) for x, y in inn]
    vob = [pc.v((x, y, zf - 0.001)) for x, y in out]
    vib = [pc.v((x, y, zf - 0.001)) for x, y in inn]
    n = len(out)
    for k in range(n):
        k1 = (k + 1) % n
        pc.f([vo[k], vo[k1], vi[k1], vi[k]], st)
        pc.f([vob[k], vob[k1], vo[k1], vo[k]], st)
        pc.f([vi[k], vi[k1], vib[k1], vib[k]], st)
    for f in pc.bm.faces:   # outward: front faces +z, outer wall away from the centre, inner wall towards it
        f.normal_update()
        c = K.G(f.calc_center_median())
        nz = K.G(f.normal)
        if abs(nz[2]) > 0.9:
            want = 1
            got = nz[2]
        else:
            d = Vector((c[0] - xc, c[1] - (ya + yb) / 2, 0))
            inner = any(v in vi or v in vib for v in f.verts)
            want = -1 if inner else 1
            got = Vector((nz[0], nz[1], 0)).dot(d)
        if got * want < 0:
            f.normal_flip()
    pc.recalc = False
    _emit(part, pc)
    # oval louvre: a dark stadium with a raised rim and 6 slats
    yc, ow, oh = Y0 + 0.005, 0.059, 0.112
    rr = ow / 2
    stad = []
    for k in range(9):
        a = math.radians(180 + 180 * k / 8)
        stad.append((xc + rr * math.cos(a), yc - oh / 2 + rr + rr * math.sin(a)))
    for k in range(9):
        a = math.radians(180 * k / 8)
        stad.append((xc + rr * math.cos(a), yc + oh / 2 - rr + rr * math.sin(a)))
    pc = _Piece()
    pc.prism(dk, 'z', stad, zf - 0.002, zf + 0.003)
    _emit(part, pc)
    rim = []
    for k in range(9):
        a = math.radians(180 + 180 * k / 8)
        rim.append((xc + (rr + 0.007) * math.cos(a), yc - oh / 2 + rr + (rr + 0.007) * math.sin(a)))
    for k in range(9):
        a = math.radians(180 * k / 8)
        rim.append((xc + (rr + 0.007) * math.cos(a), yc + oh / 2 - rr + (rr + 0.007) * math.sin(a)))
    pc = _Piece(recalc=False)
    vo = [pc.v((x, y, zf + 0.008)) for x, y in rim]
    vi = [pc.v((x, y, zf + 0.008)) for x, y in stad]
    vob = [pc.v((x, y, zf - 0.001)) for x, y in rim]
    vib = [pc.v((x, y, zf + 0.002)) for x, y in stad]
    n = len(rim)
    for k in range(n):
        k1 = (k + 1) % n
        for vs, want in (([vo[k], vo[k1], vi[k1], vi[k]], 'z'), ([vob[k], vob[k1], vo[k1], vo[k]], 'out'),
                         ([vi[k], vi[k1], vib[k1], vib[k]], 'in')):
            f = pc.f(vs, st)
            f.normal_update()
            nz = K.G(f.normal)
            c = K.G(f.calc_center_median())
            d = Vector((c[0] - xc, c[1] - yc, 0))
            got = nz[2] if want == 'z' else Vector((nz[0], nz[1], 0)).dot(d) * (1 if want == 'out' else -1)
            if got < 0:
                f.normal_flip()
    _emit(part, pc)
    pc = _Piece()
    for i in range(6):
        y = yc - oh / 2 + 0.014 + i * (oh - 0.028) / 5
        half = math.sqrt(max(0.0, rr * rr - max(0.0, abs(y - yc) - (oh / 2 - rr)) ** 2)) - 0.003
        pc.box(st, xc - half, xc + half, y - 0.004, y + 0.004, zf + 0.002, zf + 0.009)
    _emit(part, pc)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        _bolt(part, xc + dx * (w / 2 - 0.010), (yb if dy > 0 else ya) - dy * 0.010, zf + 0.012, r=0.005, h=0.004)


def _catmull(ctrl, per=4):
    pts = [Vector(p) for p in ctrl]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for s in range(per):
            t = s / per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return [tuple(p) for p in out]


def _cock(part, p, side, y_top=None, mat='cp_steel'):
    """an angle cock: body, a lever lying along x towards `side`, the feed pipe up to y_top (none: on a wall)"""
    x, y, z = p
    pc = _Piece()
    pc.box(mat, x - 0.028, x + 0.028, y - 0.03, y + 0.03, z - 0.03, z + 0.03, ch=0.006)
    xa, xb = sorted((x + side * 0.02, x + side * 0.11))
    pc.box(mat, xa, xb, y + 0.012, y + 0.024, z - 0.008, z + 0.008, ch=0.003)
    _emit(part, pc)
    if y_top is not None:
        pc = _Piece(angle=50)
        pc.cyl(mat, (x, y + 0.025, z), (x, y_top, z), 0.016, n=8, cap0=False, cap1=False)
        _emit(part, pc)


def _hoses(part, zf, Y0):
    for s in (-1, 1):
        ctrl = [(s * 0.06, Y0 - 0.135, 8.62), (s * 0.20, Y0 - 0.21, 8.63), (s * 0.25, Y0 - 0.34, 8.60),
                (s * 0.24, Y0 - 0.46, 8.52), (s * 0.18, Y0 - 0.49, 8.44), (s * 0.12, Y0 - 0.47, 8.405)]
        pc = _Piece(angle=50)
        pc.tube('cp_rubber', _catmull(ctrl, 4), 0.021, n=10)
        _emit(part, pc)
        # hose fittings at the ends
        pc = _Piece(angle=50)
        pc.cyl('cp_steel', (s * 0.03, Y0 - 0.125, 8.62), (s * 0.075, Y0 - 0.14, 8.62), 0.022, n=10)
        _emit(part, pc)
        _cock(part, (s * 0.10, Y0 - 0.45, 8.385), s, mat='cp_grime')


def front_coupler(part, z_face=9.0, y_axis=0.88, horn=0.10):
    """
    Everything in the cab skirt's opening: tight-lock head (contact face at z_face, guide horn reaching z_face + horn),
    shank and draft gear, electric coupler, hoses and cocks, cross bar and the vent boxes at the opening's sides.
    y_axis: the coupler's centre line (standard 0.88). Returns the triangles added.
    """
    t0 = _tris(part)
    _head(part, z_face, y_axis, horn)
    _draft_gear(part, z_face, y_axis)
    _electric_coupler(part, z_face, y_axis)
    _cross_bar(part, y_axis)
    for s in (-1, 1):
        _vent_box(part, s * 0.5035, y_axis)
    _hoses(part, z_face, y_axis)
    return _tris(part) - t0


# ---------------------------------------------------------------- between the cars
def intercar_coupler(part, z_mid, y_axis=0.88):
    """the semi-permanent bar coupler between two cars, centred on z_mid; returns the triangles added"""
    t0 = _tris(part)
    Y0, zm = y_axis, z_mid
    st, dk = 'cp_steel', 'cp_dark'
    oct_ = [(0.065 * math.cos(math.radians(22.5 + 45 * k)), Y0 + 0.065 * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    for s in (-1, 1):
        pc = _Piece(angle=50)
        za, zb = sorted((zm + s * 0.04, zm + s * 0.52))
        pc.prism(st, 'z', oct_, za, zb)
        _emit(part, pc)
        pc = _Piece()
        za, zb = sorted((zm + s * 0.52, zm + s * 0.66))
        pc.box(dk, -0.17, 0.17, Y0 - 0.11, 1.0, za, zb, ch=0.01)                    # draft gear, up to the frame
        za, zb = sorted((zm + s * 0.006, zm + s * 0.04))
        pc.box(st, -0.105, 0.105, Y0 - 0.10, Y0 + 0.10, za, zb, ch=0.006)          # flange of the joint
        za, zb = sorted((zm + s * 0.30, zm + s * 0.50))
        pc.box(st, -0.12, 0.12, Y0 - 0.10, Y0 - 0.075, za, zb, ch=0.004)          # carrier
        for xs in (-1, 1):                                                          # its hangers
            pc.box(st, xs * 0.11 - 0.01, xs * 0.11 + 0.01, Y0 - 0.10, 1.0, za + 0.08, za + 0.12)
        _emit(part, pc)
    for dx in (-0.078, 0.078):
        for dy in (-0.072, 0.072):
            pc = _Piece(angle=50)
            pc.cyl(st, (dx, Y0 + dy, zm - 0.055), (dx, Y0 + dy, zm + 0.055), 0.011, n=6)
            _emit(part, pc)
    # MR and BP hoses hanging between the cars, with cocks under each car end
    for x in (-0.26, 0.26):
        for s in (-1, 1):
            _cock(part, (x, Y0 - 0.02, zm + s * 0.34), 1 if x > 0 else -1, y_top=1.0)
        ctrl = [(x, Y0 - 0.05, zm - 0.34), (x, Y0 - 0.14, zm - 0.27), (x * 1.05, Y0 - 0.24, zm - 0.12),
                (x * 1.08, Y0 - 0.27, zm), (x * 1.05, Y0 - 0.24, zm + 0.12), (x, Y0 - 0.14, zm + 0.27), (x, Y0 - 0.05, zm + 0.34)]
        pc = _Piece(angle=50)
        pc.tube('cp_rubber', _catmull(ctrl, 2), 0.02, n=8)
        _emit(part, pc)
    return _tris(part) - t0


# ---------------------------------------------------------------- test harness
def _harness():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else '/tmp/coupler'
    views = argv[argv.index('--views') + 1].split(',') if '--views' in argv else ['head_on', 'front34', 'front34r', 'low34', 'side', 'clay34', 'inter_side', 'inter34', 'cullhead', 'cull34', 'cullside', 'cullinter']
    os.makedirs(out, exist_ok=True)
    K.clear_scene()
    scene = bpy.context.scene
    m = K.Materials()
    add_materials(m)
    m.add('ph_skirt', '#bfc2c6', metallic=0.35, roughness=0.45)
    m.add('ph_red', '#c8102e', metallic=0.1, roughness=0.35)
    m.add('ph_back', '#0b0b0d', roughness=0.9)
    m.add('ph_rail', '#6f6a64', metallic=0.8, roughness=0.4)
    root = K.car_empty('car0')

    p = K.Part('coupler')
    nf = front_coupler(p)
    ni = intercar_coupler(p, -9.0)
    print('TRIS front', nf, 'intercar', ni)
    p.build(root, m.mats)

    # placeholders (figures of the docstring: red bottom 0.985, notch to 1.09, opening 0.383…, skirt bottom 0.231)
    ph = K.Part('placeholder_front')
    RB, NT, OB, SB, OW = 0.985, 1.09, 0.383, 0.231, 0.636
    ph.box('ph_skirt', -1.30, -OW, SB, RB, 8.80, 8.85)
    ph.box('ph_skirt', OW, 1.30, SB, RB, 8.80, 8.85)
    ph.box('ph_skirt', -OW, OW, SB, OB, 8.80, 8.85)
    ph.box('ph_red', -1.415, -0.33, RB, NT, 7.0, 8.85)
    ph.box('ph_red', 0.33, 1.415, RB, NT, 7.0, 8.85)
    ph.box('ph_red', -1.415, 1.415, NT, 3.6, 7.0, 8.85)
    ph.box('ph_back', -0.66, 0.66, 0.30, NT, 8.30, 8.35)
    ph.box('ph_back', -0.66, 0.66, NT - 0.01, NT, 8.35, 8.80)       # ceiling of the opening
    ph.box('ph_back', -0.66, -OW, 0.30, NT, 8.35, 8.80)
    ph.box('ph_back', OW, 0.66, 0.30, NT, 8.35, 8.80)
    ph.box('ph_back', -0.66, 0.66, 0.30, OB, 8.35, 8.80)
    ph_front = ph.build(root, m.mats)
    ph = K.Part('placeholder_inter')
    ph.box('ph_red', -1.415, 1.415, 1.0, 3.6, -8.0, -8.75)
    ph.box('ph_red', -1.415, 1.415, 1.0, 3.6, -9.25, -10.0)
    ph_inter = ph.build(root, m.mats)
    rails = K.Part('rails')
    for x in (-0.7495, 0.7495):
        rails.box('ph_rail', x - 0.0315, x + 0.0315, -0.16, 0.0, -14, 14)
    rails.build(root, m.mats)

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
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.12
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    g.location.z = -0.17
    scene.collection.objects.link(g)
    gm = m.add('ground', '#7d7b76', roughness=0.9)
    me.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 2.2
    sun.data.angle = math.radians(3)
    d = B(-0.35, -0.75, -0.55)
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'Standard'
    clay = bpy.data.materials.new('clay')
    clay.use_nodes = True
    clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#c9c4bb')
    clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7

    # eye, target, lens (or ortho scale), size, hide front placeholder, hide intercar placeholder
    V = {
        # head-on, orthographic at 759 px/m like the 3× crop of photo 02 (ref/c02_coupler.png, 1080 × 720)
        'head_on': ((0.03, 0.678, 14.0), (0.03, 0.678, 0.0), ('ortho', 1080 / 759), (1080, 720), False, True),
        'front34': ((-2.6, 1.15, 11.6), (0.0, 0.72, 8.8), 55, (1200, 800), False, True),
        'front34r': ((2.2, 0.55, 11.0), (0.0, 0.72, 8.8), 50, (1200, 800), False, True),
        'side': ((3.2, 0.80, 8.7), (0.0, 0.70, 8.7), 50, (1200, 800), True, True),
        'clay34': ((-2.6, 1.15, 11.6), (0.0, 0.72, 8.8), 55, (1200, 800), False, True),
        'low34': ((1.3, 0.35, 10.6), (0.0, 0.70, 8.8), 40, (1200, 800), False, True),
        # Workbench with back faces culled (as in the game): holes show flipped normals
        'cullhead': ((0.4, 0.75, 12.0), (0.0, 0.72, 8.8), 60, (1200, 800), True, True),
        'cull34': ((-2.6, 1.15, 11.6), (0.0, 0.72, 8.8), 55, (1200, 800), True, True),
        'cullside': ((2.4, 0.5, 9.6), (0.0, 0.70, 8.7), 40, (1200, 800), True, True),
        'cullinter': ((1.6, 0.5, -7.6), (0.0, 0.8, -9.0), 35, (1200, 800), True, True),
        'inter_side': ((3.0, 0.8, -9.0), (0.0, 0.8, -9.0), 45, (1200, 800), True, False),
        'inter34': ((1.6, 0.5, -7.6), (0.0, 0.8, -9.0), 35, (1200, 800), True, True),
    }
    for name in views:
        eye, tgt, lens, size, hide_f, hide_i = V[name]
        ph_front.hide_render = hide_f
        ph_inter.hide_render = hide_i
        cam.location = B(*eye)
        dd = B(*tgt) - B(*eye)
        cam.rotation_euler = dd.to_track_quat('-Z', 'Y').to_euler()
        if isinstance(lens, tuple):
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = lens[1]
        else:
            cam.data.type = 'PERSP'
            cam.data.lens = lens
        cam.data.clip_start = 0.05
        scene.view_layers[0].material_override = clay if name.startswith('clay') else None
        if name.startswith('cull'):
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.display.shading.light = 'STUDIO'
            scene.display.shading.color_type = 'MATERIAL'
            scene.display.shading.show_backface_culling = True
        else:
            scene.render.engine = 'CYCLES'
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.filepath = os.path.join(out, name + '.png')
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    _harness()
