"""
JR East E231 series 0 (Musashino Line MU sets): the coupler gear under the cab and the semi-permanent bar coupler
between the cars of a set. A part module for the Blender model (train_kit.Part, the game's car frame, material prefix
`ec_`). The counterpart of the Keikyu module coupler_n1000 (its mesh helpers are imported).

  add_materials(m)
  front_coupler(part, z_face=10.0, y_axis=0.88, pocket=True, corner_boxes=True, electric=False)
      tight-lock head, shank, draft gear, carrier bar, release lever, the two louvred horn boxes, the skirt stays, the
      air hoses with their cocks, the dark back plate behind the skirt's notch, the coupler pocket's walls (`pocket`)
      and the two hinged boxes at the cab face's bottom corners (`corner_boxes`)
  intercar_coupler(part, z_mid, y_axis=0.88)
      semi-permanent bar coupler centred on z_mid (car ends at z_mid ± 0.25), hoses and cocks hanging between

Each returns the number of triangles it added. Run directly with Blender it renders test images on a placeholder
cab bottom and skirt (the main builder's envelope):
  blender -t 4 --background --factory-startup --python parts/e231_coupler.py -- <outdir> [--views a,b,...] [--clay]

No electric coupler on the Musashino Line sets (photos p02, p03, p04, p10, p17). The Jōban rapid sets carry one
(`electric=True`, ja.wikipedia: 電気連結器 on the cab cars for splitting and joining): a grey box hung under the head,
its front lid just behind the contact face (Commons "E231系0番台マト101編成(LED化後).jpg", 1065F, CC0, and "JRE
Series-E231 104.jpg", MaedaAkihiko, CC BY-SA 4.0): x ±0.20, y 0.49…0.645, lid 0.03 behind the face, 0.42 deep, a
cable bundle out of its back (sizes est. against the head's 0.48 width).

Figures and where they come from. Photo p04 (Commons "E231-0 Series Musashino Line of JR East", Hyper Maniac Man,
CC BY-SA 4.0; a long-lens view almost head-on) is the main source: ≈ 318 px/m at the front (the cab bottom panel,
≈ 2.85 m, spans 907 px); p17 (MaedaAkihiko, CC BY-SA 4.0; ≈ 233 px/m) checks it, p02 / p03 (3/4 views) give depths.
Heights are offsets from the coupler axis (standard height 0.88), the axis being midway between the two air ports.
- Head (柴田式密着連結器, JR EMU type), p04 / p17 / p02: face 0.48 wide (x ±0.24); air ports 0.28 apart (±0.14 from
  the axis), each in a rust-brown flange across the whole head with a hump round the port (flange top / bottom ±0.20
  over the hump, ±0.175 beside it); between the flanges a grey face frame (y −0.13…+0.13). Seen from ahead the guide
  horn (凸) is left of the centre (car's −x: x −0.115…+0.015), rust-brown, with a big front face carrying a triangular
  and a round hole (p02 / p04); the socket (凹) right of it (x +0.02…+0.17, ±0.085); narrow vertical slots at
  x ±(0.18…0.215): a latch block in the left one, a rib in the right one. Horn length 0.10, head depth 0.17, shank
  0.18 × 0.16 (est.). Release lever: a rod down the head's right side (x +0.27) and along the top of the carrier bar
  to x +0.52 (p04 / p17).
- Carrier bar (coupler carrier / 胴受け), p04 / p17: a grey bar x −0.62…+0.60, 0.11 high (axis −0.235…−0.125, i.e.
  y 0.645…0.755), its front 0.25 behind the coupler face (p03: the head's bottom flange stands clear ahead of it);
  0.09 deep (est.); a wear plate under the shank (p03).
- Louvred boxes (horn outlets) beside the head, p04 / p17 (positions corrected for the yaw of the views, which shifts
  them with their depth ≈ 0.4 m behind the coupler face): x ±0.53, 0.14 wide, y 0.765…0.985 (they sit on the bar's
  ends); an oval louvre 0.066 × 0.11 with 6 slats in a raised frame (p02 / p03); front at z_face − 0.36 (est.).
- Skirt stays: light-grey square posts 0.055 (x ±0.86, p04 / p17 / p02) and dark ones 0.05 (x ±1.06, p04) from the
  end beam (y 1.0) down behind the skirt plate (to y 0.62), with flange plates at the top (p02).
- Air hoses: a black hose loop hanging from an angle cock on each side (x ±1.0…±1.22, down to y 0.74; p04 left side,
  p17 right side); routing est.
- Coupler pocket (main builder's figure): |x| ≤ 0.33, open below, up to y 1.10, its walls dark, back at z 9.45.
  Dark back plate behind the notch: |x| < 0.37, y 0.60…1.00, z 9.42 (behind it only the bogie's darkness shows).
- Corner boxes on the cab face's bottom corners (p02 / p03 / p17; their use unverified): x ±(0.98…1.27),
  y 0.975…1.09, a white box on the inner side and a silver hinge barrel ∅ 0.07 with a handle on the outer side,
  0.08 proud of the face (est.).
- Intercar: semi-permanent bar coupler (est., hidden by the gangways on the photos): shanks ∅ 0.13, a bolted flange
  joint at z_mid, draft gear boxes at the car ends, MR / BP hoses hanging between the cars with cocks.
- Colours (sampled from p02 / p03 / p17 in sun): grey paint #8c8f90, rust #7d4527, louvre frames like the grey,
  corner boxes #d6d8d6.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import train_kit as K  # noqa: E402
import coupler_n1000 as CK  # noqa: E402  (mesh helpers only; its materials are not used)

B = K.B
_Piece, _lathe, _emit, _bolt, _catmull = CK._Piece, CK._lathe, CK._emit, CK._bolt, CK._catmull
_chamfered_rect, _rounded_rect = CK._chamfered_rect, CK._rounded_rect

# name: (colour, metallic, roughness)
MATS = {
    'ec_grey': ('#868a8b', 0.3, 0.55),      # grey paint: head frame, bar, louvre boxes, stays, brackets
    'ec_rust': ('#4a3a32', 0.2, 0.8),       # rusty flanges and guide horn
    'ec_dark': ('#2b2c2e', 0.3, 0.7),       # socket, draft gear, pocket walls, things in the shadow
    'ec_rubber': ('#121213', 0.0, 0.8),     # hoses, gaskets
    'ec_white': ('#d6d8d6', 0.05, 0.4),     # corner boxes
    'ec_silver': ('#b8bcbf', 0.85, 0.3),    # hinge barrels, port bushes, cock levers
}

GR, RU, DK, RB, WH, SV = 'ec_grey', 'ec_rust', 'ec_dark', 'ec_rubber', 'ec_white', 'ec_silver'


def add_materials(m):
    for name, (col, met, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, col, metallic=met, roughness=rough)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _box(part, mat, x0, x1, y0, y1, z0, z1, ch=0.0):
    pc = _Piece()
    pc.box(mat, min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1), ch=ch)
    _emit(part, pc)


def _plate_z(part, mat, poly, z0, z1, ch=0.0):
    """a polygon in (x, y) extruded along z"""
    pc = _Piece()
    pc.prism(mat, 'z', poly, z0, z1)
    if ch > 0:
        pc.chamfer(ch)
    _emit(part, pc)


def _cock(part, p, side, mat=GR):
    """an angle cock: body, a silver lever lying along x towards `side`, the feed pipe up to the end beam"""
    x, y, z = p
    _box(part, mat, x - 0.028, x + 0.028, y - 0.03, y + 0.03, z - 0.03, z + 0.03, ch=0.006)
    _box(part, SV, x + side * 0.02, x + side * 0.11, y + 0.012, y + 0.024, z - 0.008, z + 0.008, ch=0.003)
    pc = _Piece(angle=50)
    pc.cyl(mat, (x, y + 0.025, z), (x, 1.0, z), 0.016, n=8, cap0=False, cap1=False)
    _emit(part, pc)


# ---------------------------------------------------------------- the head
def _head(part, zf, Y0, horn=0.10):
    zb = zf - 0.17
    # face frame (y −0.13…+0.13) with the socket on the right (+x), a blind pocket 0.15 deep
    x0, x1, y0, y1 = -0.24, 0.24, Y0 - 0.13, Y0 + 0.13
    hx0, hx1, hy0, hy1, zp = 0.022, 0.168, Y0 - 0.085, Y0 + 0.085, zf - 0.15
    pc = _Piece()
    O = [pc.v(p) for p in ((x0, y0, zf), (x1, y0, zf), (x1, y1, zf), (x0, y1, zf))]
    Ob = [pc.v(p) for p in ((x0, y0, zb), (x1, y0, zb), (x1, y1, zb), (x0, y1, zb))]
    H = [pc.v(p) for p in ((hx0, hy0, zf), (hx1, hy0, zf), (hx1, hy1, zf), (hx0, hy1, zf))]
    Hb = [pc.v(p) for p in ((hx0, hy0, zp), (hx1, hy0, zp), (hx1, hy1, zp), (hx0, hy1, zp))]
    for i in range(4):
        j = (i + 1) % 4
        pc.f([Ob[i], Ob[j], O[j], O[i]], GR)
        pc.f([O[i], O[j], H[j], H[i]], GR)
        pc.f([H[i], H[j], Hb[j], Hb[i]], DK)
    pc.f(list(reversed(Ob)), GR)
    pc.f(Hb, DK)
    bmesh.ops.recalc_face_normals(pc.bm, faces=pc.bm.faces)
    pc.chamfer(0.008)
    _emit(part, pc)

    # side slots: dark windows in the face, a latch block in the left one, a rib in the right one
    for s in (-1, 1):
        xa, xb = sorted((s * 0.180, s * 0.218))
        _box(part, DK, xa, xb, Y0 - 0.075, Y0 + 0.085, zf - 0.02, zf + 0.002)
    _box(part, GR, -0.214, -0.184, Y0 - 0.060, Y0 - 0.005, zf - 0.03, zf + 0.012, ch=0.004)
    _box(part, GR, 0.190, 0.206, Y0 - 0.070, Y0 + 0.080, zf - 0.03, zf + 0.010, ch=0.003)

    # guide horn (凸) on the left: a truncated pyramid with a large front face (two holes: a triangle and a round
    # one, p02 / p04), rust-brown
    bx0, bx1, by0, by1 = -0.118, 0.016, Y0 - 0.088, Y0 + 0.082
    base = [(x, y, zf - 0.004) for x, y in _chamfered_rect(bx0, bx1, by0, by1, 0.012)]
    neck = [(x, y, zf + 0.014) for x, y in _chamfered_rect(bx0 + 0.003, bx1 - 0.003, by0 + 0.003, by1 - 0.003, 0.012)]
    tx0, tx1, ty0, ty1 = bx0 + 0.022, bx1 - 0.024, by0 + 0.026, by1 - 0.022
    tip = [(x, y, zf + horn) for x, y in _chamfered_rect(tx0, tx1, ty0, ty1, 0.014)]
    pc = _Piece(angle=25)
    pc.loft([base, neck, tip], RU, cap0=False, cap1=True)
    _emit(part, pc)
    # the holes on the front face: an inverted triangle low left, a round one high right
    tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
    tri = [(tcx - 0.040, tcy + 0.016), (tcx + 0.012, tcy + 0.004), (tcx - 0.026, tcy - 0.048)]
    _plate_z(part, DK, tri, zf + horn - 0.004, zf + horn + 0.0015)
    _lathe(part, (tcx + 0.024, tcy + 0.028, zf + horn), (0, 0, 1),
           [(0.017, -0.004, DK), (0.017, 0.0015, DK), (0, 0.0015, DK)], n=12)

    # top and bottom flanges (rust) across the head, humped round the air ports
    for s in (1, -1):
        yp = Y0 + s * 0.14
        y_in, y_out = Y0 + s * 0.125, Y0 + s * 0.175
        rb = 0.058
        hump = [(rb * math.cos(math.radians(a)), yp + s * rb * math.sin(math.radians(a))) for a in range(15, 166, 15)]
        hump = [(x, y) for x, y in hump if s * (y - y_out) > 0] or hump
        poly = [(-0.24, y_in), (0.24, y_in), (0.24, y_out - s * 0.015), (0.225, y_out),
                (rb + 0.012, y_out)] + hump + [(-rb - 0.012, y_out), (-0.225, y_out), (-0.24, y_out - s * 0.015)]
        if s < 0:
            poly.reverse()
        _plate_z(part, RU, poly, zf - 0.175, zf + 0.004, ch=0.006)
        _lathe(part, (0, yp, zf + 0.004), (0, 0, 1), [
            (0.036, -0.004, RU), (0.036, 0.008, RU), (0.031, 0.012, SV), (0.026, 0.012, SV),
            (0.026, 0.014, RB), (0.016, 0.014, RB), (0.016, 0.002, DK), (0, 0.002, DK)], n=18)

    # release lever: down the head's right side, then along the top of the carrier bar
    pc = _Piece(angle=50)
    pc.tube(GR, [(0.236, Y0 + 0.03, zf - 0.07), (0.268, Y0 + 0.03, zf - 0.07), (0.272, Y0 - 0.02, zf - 0.08),
                 (0.272, Y0 - 0.105, zf - 0.11), (0.29, Y0 - 0.117, zf - 0.17), (0.52, Y0 - 0.117, zf - 0.20)], 0.009, n=8)
    _emit(part, pc)

    # behind the face: the head tapers into the shank, which runs back to the draft gear
    pc = _Piece()
    pc.loft([[(x, y, zb) for x, y in _chamfered_rect(-0.22, 0.22, Y0 - 0.16, Y0 + 0.16, 0.03)],
             [(x, y, zf - 0.34) for x, y in _chamfered_rect(-0.09, 0.09, Y0 - 0.08, Y0 + 0.08, 0.02)]],
            GR, cap0=False, cap1=False)
    _emit(part, pc)
    _plate_z(part, GR, _chamfered_rect(-0.09, 0.09, Y0 - 0.08, Y0 + 0.08, 0.02), 9.45, zf - 0.34)


def _draft_gear(part, zf, Y0):
    _box(part, DK, -0.21, 0.21, Y0 - 0.12, Y0 + 0.11, 9.45, 9.62, ch=0.01)         # draft gear housing
    _box(part, GR, -0.13, 0.13, Y0 - 0.10, Y0 + 0.10, 9.62, 9.64, ch=0.005)       # yoke plate
    for s in (-1, 1):                                                              # hangers up to the end beam
        _box(part, DK, s * 0.17 - 0.015, s * 0.17 + 0.015, Y0 + 0.10, 1.0, 9.47, 9.60)
    # centring springs, shank to the housing
    for s in (-1, 1):
        pc = _Piece(angle=40)
        pc.cyl(DK, (s * 0.09, Y0 - 0.02, 9.78), (s * 0.19, Y0 - 0.035, 9.64), 0.02, n=8)
        _emit(part, pc)


def _carrier(part, zf, Y0):
    ya, yb = Y0 - 0.235, Y0 - 0.125
    zfr = zf - 0.25
    zbk = zfr - 0.09
    # a box bar, a little lip along its top front edge (p03)
    _box(part, GR, -0.62, 0.60, ya, yb, zbk, zfr, ch=0.008)
    _box(part, GR, -0.62, 0.60, yb - 0.004, yb + 0.006, zfr - 0.012, zfr + 0.004, ch=0.002)
    # wear plate under the shank, and the stay from the bar down and back into the frame
    _box(part, GR, -0.12, 0.12, yb, yb + 0.022, zbk + 0.01, zfr - 0.01, ch=0.004)
    pc = _Piece()
    for s in (-1, 1):
        pc.beam(DK, (s * 0.30, ya + 0.01, zbk + 0.02), (s * 0.22, 0.56, 9.44), 0.04, 0.03)
    _emit(part, pc)
    # end hangers up to the end beam, behind the louvre boxes
    for s in (-1, 1):
        x = s * 0.61
        _box(part, DK, x - 0.02, x + 0.02, ya, 1.0, zbk - 0.02, zbk + 0.03)
    for xb in (-0.56, -0.46, 0.46, 0.56):
        _bolt(part, xb, (ya + yb) / 2, zfr, r=0.009, h=0.006, mat=GR)


def _louvre_box(part, xc, zf):
    w, ya, yb = 0.14, 0.765, 0.985
    zfr = zf - 0.36
    _box(part, GR, xc - w / 2, xc + w / 2, ya, yb, zfr - 0.15, zfr, ch=0.008)
    # foot plate on the bar, hanger plate to the end beam
    _box(part, GR, xc - 0.082, xc + 0.082, ya - 0.012, ya + 0.004, zfr - 0.16, zfr + 0.005, ch=0.003)
    _box(part, GR, xc - 0.05, xc + 0.05, yb, 1.0, zfr - 0.12, zfr - 0.03)
    # raised frame round the face
    pc = _Piece(recalc=False)
    out = _rounded_rect(xc - w / 2 + 0.006, xc + w / 2 - 0.006, ya + 0.006, yb - 0.006, 0.014, 2)
    inn = _rounded_rect(xc - w / 2 + 0.018, xc + w / 2 - 0.018, ya + 0.018, yb - 0.018, 0.008, 2)
    vo = [pc.v((x, y, zfr + 0.010)) for x, y in out]
    vi = [pc.v((x, y, zfr + 0.010)) for x, y in inn]
    vob = [pc.v((x, y, zfr - 0.001)) for x, y in out]
    n = len(out)
    yc0 = (ya + yb) / 2
    for k in range(n):
        k1 = (k + 1) % n
        for vs, want in (([vo[k], vo[k1], vi[k1], vi[k]], 'z'), ([vob[k], vob[k1], vo[k1], vo[k]], 'out')):
            f = pc.f(vs, GR)
            f.normal_update()
            nz = K.G(f.normal)
            c = K.G(f.calc_center_median())
            got = nz[2] if want == 'z' else Vector((nz[0], nz[1], 0)).dot(Vector((c[0] - xc, c[1] - yc0, 0)))
            if got < 0:
                f.normal_flip()
    _emit(part, pc)
    # oval louvre: dark stadium, rim, 6 slats
    yc, ow, oh = 0.885, 0.066, 0.11
    rr = ow / 2

    def stadium(r):
        pts = []
        for k in range(9):
            a = math.radians(180 + 180 * k / 8)
            pts.append((xc + r * math.cos(a), yc - oh / 2 + rr + r * math.sin(a)))
        for k in range(9):
            a = math.radians(180 * k / 8)
            pts.append((xc + r * math.cos(a), yc + oh / 2 - rr + r * math.sin(a)))
        return pts
    _plate_z(part, DK, stadium(rr), zfr - 0.002, zfr + 0.002)
    rim_o, rim_i = stadium(rr + 0.007), stadium(rr)
    pc = _Piece(recalc=False)
    vo = [pc.v((x, y, zfr + 0.007)) for x, y in rim_o]
    vi = [pc.v((x, y, zfr + 0.007)) for x, y in rim_i]
    vob = [pc.v((x, y, zfr - 0.001)) for x, y in rim_o]
    vib = [pc.v((x, y, zfr + 0.001)) for x, y in rim_i]
    n = len(rim_o)
    for k in range(n):
        k1 = (k + 1) % n
        for vs, want in (([vo[k], vo[k1], vi[k1], vi[k]], 'z'), ([vob[k], vob[k1], vo[k1], vo[k]], 'out'),
                         ([vi[k], vi[k1], vib[k1], vib[k]], 'in')):
            f = pc.f(vs, GR)
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
        y = yc - oh / 2 + 0.013 + i * (oh - 0.026) / 5
        half = math.sqrt(max(0.0, rr * rr - max(0.0, abs(y - yc) - (oh / 2 - rr)) ** 2)) - 0.003
        pc.box(GR, xc - half, xc + half, y - 0.0045, y + 0.0045, zfr + 0.001, zfr + 0.008)
    _emit(part, pc)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        _bolt(part, xc + dx * (w / 2 - 0.012), (yb if dy > 0 else ya) - dy * 0.012, zfr + 0.010, r=0.005, h=0.004,
              mat=GR)


def _stays(part):
    """skirt stays from the end beam down behind the skirt plate"""
    for s in (-1, 1):
        x = s * 0.86
        _box(part, GR, x - 0.0275, x + 0.0275, 0.62, 0.995, 9.70, 9.755, ch=0.004)
        _box(part, GR, x - 0.05, x + 0.05, 0.985, 1.0, 9.66, 9.78, ch=0.003)          # flange under the beam
        for dx in (-0.035, 0.035):
            _bolt(part, x + dx, 0.985, 9.72, r=0.008, h=0.006, mat=GR, axis=(0, -1, 0))
        x = s * 1.06
        _box(part, DK, x - 0.025, x + 0.025, 0.62, 1.0, 9.66, 9.71, ch=0.004)
        # diagonal brace from the post back into the frame
        pc = _Piece()
        pc.beam(DK, (s * 0.86, 0.70, 9.70), (s * 0.80, 0.98, 9.44), 0.03, 0.03)
        _emit(part, pc)


def _hoses(part):
    for s in (-1, 1):
        _cock(part, (s * 0.98, 0.94, 9.60), -s)
        ctrl = [(s * 0.98, 0.91, 9.60), (s * 0.99, 0.82, 9.61), (s * 1.04, 0.75, 9.62), (s * 1.12, 0.74, 9.62),
                (s * 1.19, 0.79, 9.61), (s * 1.21, 0.87, 9.60)]
        pc = _Piece(angle=50)
        pc.tube(RB, _catmull(ctrl, 4), 0.022, n=10)
        _emit(part, pc)
        # the hose head parked in its holder (a dummy coupling on a bracket)
        _box(part, GR, s * 1.17, s * 1.25, 0.87, 0.92, 9.56, 9.64, ch=0.006)
        _box(part, DK, s * 1.20, s * 1.23, 0.92, 1.0, 9.57, 9.62)


def _pocket(part):
    """the coupler pocket's dark walls (|x| ≤ 0.33, up to y 1.10, back at z 9.45), open below"""
    _box(part, DK, -0.33, 0.33, 1.095, 1.105, 9.45, 9.80)
    for s in (-1, 1):
        _box(part, DK, s * 0.325, s * 0.335, 0.98, 1.10, 9.45, 9.80)
    _box(part, DK, -0.33, 0.33, 0.98, 1.10, 9.44, 9.45)


def _back_plate(part):
    """dark plate behind the skirt's notch, so nothing shows through the gap between y 0.60 and 1.00"""
    _box(part, DK, -0.37, 0.37, 0.58, 1.0, 9.41, 9.43)
    # a lower cross member seen through the notch, below the carrier bar
    _box(part, DK, -0.50, 0.50, 0.55, 0.60, 9.43, 9.52, ch=0.005)


def _corner_boxes(part):
    """the hinged boxes at the cab face's bottom corners: white box inside, silver hinge barrel and handle outside"""
    for s in (-1, 1):
        _box(part, WH, s * 0.98, s * 1.085, 0.975, 1.085, 9.79, 9.875, ch=0.008)
        pc = _Piece(angle=40)
        pc.cyl(SV, (s * 1.085, 1.045, 9.84), (s * 1.255, 1.045, 9.84), 0.032, n=12)
        _emit(part, pc)
        _box(part, SV, s * 1.085, s * 1.26, 0.982, 1.012, 9.79, 9.86, ch=0.004)     # lid lip under the barrel
        _box(part, WH, s * 1.085, s * 1.255, 1.01, 1.085, 9.79, 9.83, ch=0.004)      # back plate
        pc = _Piece(angle=50)                                                          # handle
        pc.tube(SV, [(s * 1.20, 0.995, 9.865), (s * 1.24, 0.985, 9.885), (s * 1.27, 0.975, 9.885)], 0.006, n=6)
        _emit(part, pc)
        for dx in (0.995, 1.065):
            _bolt(part, s * dx, 1.06, 9.875, r=0.006, h=0.004, mat=SV)


def _electric(part, zf, Y0):
    """the electric coupler under the head: box, front lid with its seam and latches, guide pins, cable bundle"""
    y0, y1 = Y0 - 0.39, Y0 - 0.235
    zl = zf - 0.03
    _box(part, GR, -0.20, 0.20, y0, y1, zl - 0.42, zl - 0.03, ch=0.01)                   # the body
    _box(part, GR, -0.195, 0.195, y0 + 0.006, y1 - 0.006, zl - 0.03, zl, ch=0.008)      # the lid
    _box(part, DK, -0.19, 0.19, y0 + 0.004, y1 - 0.004, zl - 0.036, zl - 0.026)         # the lid's seam
    for s in (-1, 1):
        _box(part, SV, s * 0.15 - 0.02, s * 0.15 + 0.02, (y0 + y1) / 2 - 0.015, (y0 + y1) / 2 + 0.015,
             zl, zl + 0.012, ch=0.003)                                                   # latches
        pc = _Piece(angle=40)
        pc.cyl(SV, (s * 0.215, y1 - 0.03, zl - 0.06), (s * 0.215, y1 - 0.03, zl + 0.02), 0.012, n=8)  # guide pins
        _emit(part, pc)
    _box(part, DK, -0.10, 0.10, y0 - 0.012, y0, zl - 0.36, zl - 0.06)                   # the drain / rail below
    pc = _Piece(angle=40)
    pc.cyl(RB, (0.0, (y0 + y1) / 2, zl - 0.42), (0.0, 0.70, 9.42), 0.035, n=8)          # cable bundle
    _emit(part, pc)


def front_coupler(part, z_face=10.0, y_axis=0.88, pocket=True, corner_boxes=True, electric=False):
    """
    Everything under the cab between the body bottom and the skirt: the tight-lock head (contact face at z_face, the
    horn reaching z_face + 0.10), shank, draft gear, carrier bar and release lever, the louvred boxes, the skirt
    stays, the hoses, the dark back plate; `pocket`: the pocket's walls; `corner_boxes`: the boxes at the face's
    bottom corners. Fixed parts assume the cab face at z 9.80 and the body bottom at y 1.00. Returns the triangles.
    """
    t0 = _tris(part)
    Y0 = y_axis
    _head(part, z_face, Y0)
    _draft_gear(part, z_face, Y0)
    _carrier(part, z_face, Y0)
    for s in (-1, 1):
        _louvre_box(part, s * 0.53, z_face)
    _stays(part)
    _hoses(part)
    _back_plate(part)
    if pocket:
        _pocket(part)
    if corner_boxes:
        _corner_boxes(part)
    if electric:
        _electric(part, z_face, Y0)
    return _tris(part) - t0


# ---------------------------------------------------------------- between the cars
def intercar_coupler(part, z_mid, y_axis=0.88):
    """the semi-permanent bar coupler between two cars, centred on z_mid; returns the triangles added"""
    t0 = _tris(part)
    Y0, zm = y_axis, z_mid
    oct_ = [(0.065 * math.cos(math.radians(22.5 + 45 * k)), Y0 + 0.065 * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    for s in (-1, 1):
        pc = _Piece(angle=50)
        za, zb = sorted((zm + s * 0.04, zm + s * 0.52))
        pc.prism(GR, 'z', oct_, za, zb)
        _emit(part, pc)
        pc = _Piece()
        za, zb = sorted((zm + s * 0.52, zm + s * 0.66))
        pc.box(DK, -0.17, 0.17, Y0 - 0.11, 1.0, za, zb, ch=0.01)                    # draft gear, up to the frame
        za, zb = sorted((zm + s * 0.006, zm + s * 0.04))
        pc.box(GR, -0.105, 0.105, Y0 - 0.10, Y0 + 0.10, za, zb, ch=0.006)          # flange of the joint
        za, zb = sorted((zm + s * 0.30, zm + s * 0.50))
        pc.box(GR, -0.12, 0.12, Y0 - 0.10, Y0 - 0.075, za, zb, ch=0.004)          # carrier
        for xs in (-1, 1):                                                          # its hangers
            pc.box(GR, xs * 0.11 - 0.01, xs * 0.11 + 0.01, Y0 - 0.10, 1.0, za + 0.08, za + 0.12)
        _emit(part, pc)
    for dx in (-0.078, 0.078):
        for dy in (-0.072, 0.072):
            pc = _Piece(angle=50)
            pc.cyl(SV, (dx, Y0 + dy, zm - 0.055), (dx, Y0 + dy, zm + 0.055), 0.011, n=6)
            _emit(part, pc)
    # MR and BP hoses hanging between the cars, with cocks under each car end
    for x in (-0.26, 0.26):
        for s in (-1, 1):
            _cock(part, (x, Y0 - 0.02, zm + s * 0.34), 1 if x > 0 else -1)
        ctrl = [(x, Y0 - 0.05, zm - 0.34), (x, Y0 - 0.14, zm - 0.27), (x * 1.05, Y0 - 0.24, zm - 0.12),
                (x * 1.08, Y0 - 0.27, zm), (x * 1.05, Y0 - 0.24, zm + 0.12), (x, Y0 - 0.14, zm + 0.27), (x, Y0 - 0.05, zm + 0.34)]
        pc = _Piece(angle=50)
        pc.tube(RB, _catmull(ctrl, 2), 0.02, n=8)
        _emit(part, pc)
    return _tris(part) - t0


# ---------------------------------------------------------------- test harness
SKIRT = dict(top=0.69, bottom=0.16, tip=9.94, corner=(1.15, 9.80), wing=(1.34, 9.45), notch=(0.51, 0.53, 0.73))


def _skirt_top(x):
    nb, w0, w1 = SKIRT['notch']
    ax = abs(x)
    if ax <= w0:
        return nb
    if ax <= w1:
        return nb + (SKIRT['top'] - nb) * (ax - w0) / (w1 - w0)
    return SKIRT['top']


def _placeholder_skirt(part, mat):
    """the main builder's skirt envelope: a V plate in plan with the notch, front faces only"""
    cx, cz = SKIRT['corner']
    wx, wz = SKIRT['wing']
    nb, w0, w1 = SKIRT['notch']
    xs = sorted(set([-wx, -cx, -w1, -w0, 0.0, w0, w1, cx, wx] + [i * 0.1 - 1.3 for i in range(27)]))
    xs = [x for x in xs if -wx <= x <= wx]

    def z_at(x):
        ax = abs(x)
        if ax <= cx:
            return SKIRT['tip'] + (cz - SKIRT['tip']) * ax / cx
        return cz + (wz - cz) * (ax - cx) / (wx - cx)
    for a, b in zip(xs[:-1], xs[1:]):
        za, zb = z_at(a), z_at(b)
        part.face([(a, SKIRT['bottom'], za), (b, SKIRT['bottom'], zb), (b, _skirt_top(b), zb), (a, _skirt_top(a), za)], mat)
        # the plate's top edge (8 mm), seen from above
        ta, tb = _skirt_top(a), _skirt_top(b)
        part.face([(a, ta, za), (b, tb, zb), (b, tb, zb - 0.008), (a, ta, za - 0.008)], mat)


def _harness():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else '/tmp/e231_coupler'
    views = argv[argv.index('--views') + 1].split(',') if '--views' in argv else [
        'head_on', 'front34', 'front34r', 'low34', 'side', 'cullhead', 'cull34', 'cullside', 'inter34', 'cullinter']
    clay_all = '--clay' in argv
    samples = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 32
    os.makedirs(out, exist_ok=True)
    K.clear_scene()
    scene = bpy.context.scene
    m = K.Materials()
    add_materials(m)
    m.add('ph_body', '#c4c7c9', metallic=0.6, roughness=0.35)
    m.add('ph_skirt', '#d4d6d6', metallic=0.05, roughness=0.45)
    m.add('ph_back', '#0b0b0d', roughness=0.9)
    m.add('ph_rail', '#6f6a64', metallic=0.8, roughness=0.4)
    m.add('ph_orange', '#f26a21', roughness=0.4)
    root = K.car_empty('car0')

    p = K.Part('coupler')
    nf = front_coupler(p)
    ni = intercar_coupler(p, -10.0)
    print('TRIS front', nf, 'intercar', ni)
    p.build(root, m.mats)

    # placeholders: the main builder's envelope (cab face z 9.80, body bottom 1.00, pocket |x| ≤ 0.33 up to 1.10,
    # dark end-beam boxes |x| 0.36…1.30, y 0.62…1.00, z 9.40…9.46, the skirt)
    ph = K.Part('placeholder_front')
    ph.box('ph_body', -1.475, -0.33, 1.0, 1.10, 7.0, 9.80)
    ph.box('ph_body', 0.33, 1.475, 1.0, 1.10, 7.0, 9.80)
    ph.box('ph_body', -1.475, 1.475, 1.10, 1.70, 7.0, 9.80)
    ph.box('ph_orange', -1.475, 1.475, 1.70, 2.0, 7.0, 9.80)
    ph.box('ph_body', -1.475, 1.475, 2.0, 3.6, 7.0, 9.80)
    for s in (-1, 1):
        ph.box('ph_back', min(s * 0.36, s * 1.30), max(s * 0.36, s * 1.30), 0.62, 1.0, 9.40, 9.46)
    _placeholder_skirt(ph, 'ph_skirt')
    ph_front = ph.build(root, m.mats)
    ph = K.Part('placeholder_inter')
    ph.box('ph_body', -1.475, 1.475, 1.0, 3.6, -9.0, -9.75)
    ph.box('ph_body', -1.475, 1.475, 1.0, 3.6, -10.25, -11.0)
    ph_inter = ph.build(root, m.mats)
    rails = K.Part('rails')
    for x in (-0.5335 - 0.032, 0.5335 + 0.032):
        rails.box('ph_rail', x - 0.0325, x + 0.0325, -0.16, 0.0, -14, 14)
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
    d = B(0.45, -0.65, -0.62)
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'Standard'
    clay = bpy.data.materials.new('clay')
    clay.use_nodes = True
    clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = K.srgb('#c9c4bb')
    clay.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7

    # eye, target, lens (or ('ortho', scale)), size, hide front placeholder, hide intercar placeholder
    V = {
        # head-on, orthographic at 318 px/m like photo p04 (crop x 660…1600, y 940…1320 of the original)
        'head_on': ((0.05, 0.79, 16.0), (0.05, 0.79, 0.0), ('ortho', 1200 / 318), (1200, 480), False, True),
        # like photo p03: from the platform, left of the train (car's −x), above the coupler
        'front34': ((-2.3, 1.75, 13.6), (0.0, 0.80, 9.6), 50, (1280, 720), False, True),
        'front34r': ((2.2, 0.55, 12.0), (0.0, 0.78, 9.6), 45, (1280, 720), False, True),
        'side': ((3.6, 0.80, 9.5), (0.0, 0.80, 9.5), 45, (1280, 720), True, True),
        'low34': ((1.3, 0.35, 11.6), (0.0, 0.80, 9.6), 32, (1280, 720), False, True),
        'cullhead': ((0.4, 0.85, 13.0), (0.0, 0.80, 9.6), 50, (1280, 720), True, True),
        'cull34': ((-2.3, 1.45, 12.6), (0.0, 0.80, 9.6), 45, (1280, 720), True, True),
        'cullside': ((2.6, 0.5, 10.6), (0.0, 0.80, 9.5), 35, (1280, 720), True, True),
        'inter34': ((1.6, 0.5, -8.6), (0.0, 0.8, -10.0), 35, (1280, 720), True, False),
        'cullinter': ((1.6, 0.5, -8.6), (0.0, 0.8, -10.0), 35, (1280, 720), True, True),
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
        scene.view_layers[0].material_override = clay if clay_all else None
        if name.startswith('cull'):
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.display.shading.light = 'STUDIO'
            scene.display.shading.color_type = 'MATERIAL'
            scene.display.shading.show_backface_culling = True
        else:
            scene.render.engine = 'CYCLES'
        scene.render.resolution_x, scene.render.resolution_y = size
        scene.render.filepath = os.path.join(out, name + ('_clay' if clay_all else '') + '.png')
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    _harness()
