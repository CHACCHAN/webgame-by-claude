"""
JR East E235 series 0 (Yamanote Line): the cab's skirt (排障器), the tight-lock coupler under the face and the bar
coupler between the cars. A part module for the Blender model (train_kit.Part, the game's car frame, material prefix
`ec_`; the coupler pieces are the Keikyu model's coupler_n1000 functions, moved forward, so they keep its `cp_`
materials).

  skirt(part)                         the dark grey skirt plate with its central notch, stays and the dark backing
  front_coupler(part, z_face=10.0)    Shibata tight-lock head, draft gear, carrier bar, air hoses and the two vent
                                      boxes beside it (no electric coupler on the E235's cab ends)
  intercar_coupler(part, z_mid)       the semi-permanent bar coupler (coupler_n1000.intercar_coupler)
  add_materials(m)

Figures and where they come from:
- ja.wikipedia JR東日本E235系電車 (read 2026-11-03): 20,000 mm over the coupler faces, cab car body 19,570 mm:
  the front coupler face at z = 10.0 (the cars are 20.0 m apart; rear end 9.75 + half gap 0.25).
- Head-on photo "(JPN-Tokyo) … 23 @ Shibuya" (S5A-0043, CC BY 4.0; 626 px/m), heights from the face's lower edge
  (0.924): skirt top 0.644 over |x| ≤ 1.16, the central notch's bottom 0.445 with its sides sloping from |x| 0.706
  at the top to 0.514 at the bottom, the skirt's lowest edge 0.165; the vent boxes |x| 0.45…0.57, y 0.63…0.85; the
  coupler head x −0.20…+0.25, y 0.69…1.0 (axis ≈ 0.86–0.88; we keep the standard 0.88); a carrier bar under the head
  at y 0.63…0.69. The skirt is dark charcoal (#181a1d in the shadow, about #2a2d31 lit).
- Line-scan photo "Line scan photo of Yamanote line E235 series dllu 02" (Dllu, CC BY-SA 4.0; 86.4 px/m along):
  the skirt's front 0.09 m ahead of the face's lower edge (z ≈ 9.87), its lower part vertical, the upper part
  leaning back to the top edge; the bottom edge chamfered up to the front; the side panel runs back to z ≈ 8.95;
  the coupler's tip ≈ 0.36 m ahead of the body's lower edge.
- Estimates: plate thickness 0.03; the lean (0.10 at the top) and the chamfer (0.22 back at the bottom); plan corner
  radius 0.13; the stays behind the plate.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
try:
    import train_kit as K
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import train_kit as K
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coupler_n1000 as CP  # noqa: E402

MATS = {
    'ec_skirt': ('#2b2e32', 0.25, 0.55),     # the skirt plate: dark charcoal paint
    'ec_back': ('#0e0f10', 0.0, 0.85),       # what is seen behind the opening: shadow, frame
}

KEIKYU_FACE = 9.0           # coupler_n1000 builds its draft gear etc. for a coupler face at 9.0


def add_materials(m):
    CP.add_materials(m)
    for name, (col, met, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, col, metallic=met, roughness=rough)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _moved(part, build, dz=0.0, dy=0.0):
    """run build(tmp_part) and copy its faces into part, moved by dz (forward) and dy (up)"""
    tmp = K.Part('tmp')
    build(tmp)
    vmap = {}
    for v in tmp.bm.verts:
        co = v.co.copy()
        co.y -= dz            # Blender y = −z
        co.z += dy
        vmap[v] = part.bm.verts.new(co)
    for f in tmp.bm.faces:
        nf = part.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = part.slot(tmp.slots[f.material_index])
        nf.smooth = f.smooth
    for e in tmp.bm.edges:
        if not e.smooth:
            ne = part.bm.edges.get([vmap[e.verts[0]], vmap[e.verts[1]]])
            if ne is not None:
                ne.smooth = False
    tmp.bm.free()


# ---------------------------------------------------------------- skirt
SK_FRONT = 9.87
SK_X = 1.16
SK_R = 0.13
SK_REAR = 8.95
SK_TOP = 0.644
SK_TOP_REAR = 0.70
SK_LOW = 0.165
NOTCH = (0.514, 0.706, 0.445)       # notch half width at its bottom, at the top; its bottom
T = 0.03


def _plan():
    """the skirt's plan path from the left rear (−x) round the front to the right rear: [(x, z, lean factor, top)]"""
    pts = []
    for z in (SK_REAR, 9.25, 9.50, SK_FRONT - SK_R):
        pts.append((-SK_X, z))
    for k in range(1, 4):
        a = math.pi - k * math.pi / 2 / 4
        pts.append((-(SK_X - SK_R) + SK_R * math.cos(a), SK_FRONT - SK_R + SK_R * math.sin(a)))
    xs = [-(SK_X - SK_R), -0.86, -NOTCH[1], -NOTCH[0], -0.25, 0.0, 0.25, NOTCH[0], NOTCH[1], 0.86, SK_X - SK_R]
    for x in xs:
        pts.append((x, SK_FRONT))
    for k in range(1, 4):
        a = math.pi / 2 - k * math.pi / 2 / 4
        pts.append(((SK_X - SK_R) + SK_R * math.cos(a), SK_FRONT - SK_R + SK_R * math.sin(a)))
    for z in (SK_FRONT - SK_R, 9.50, 9.25, SK_REAR):
        pts.append((SK_X, z))
    out = []
    for x, z in pts:
        front = z >= SK_FRONT - 1e-6
        lean = 1.0 if front else 0.35 + 0.65 * K.smoothstep(SK_FRONT - SK_R - 0.05, SK_FRONT, z)
        if front and abs(x) < NOTCH[1]:
            t = max(0.0, min(1.0, (abs(x) - NOTCH[0]) / (NOTCH[1] - NOTCH[0])))
            top = NOTCH[2] + (SK_TOP - NOTCH[2]) * t
        elif front:
            top = SK_TOP
        else:
            top = SK_TOP + (SK_TOP_REAR - SK_TOP) * max(0.0, (SK_FRONT - SK_R - z) / (SK_FRONT - SK_R - SK_REAR))
        out.append((x, z, lean, top))
    return out


def _section(top, lean):
    """outer profile (y, setback) bottom → top"""
    def d_at(y):
        return 0.10 * lean * max(0.0, (y - 0.43) / (SK_TOP - 0.43))
    ys = [0.29, 0.43, max(top, 0.445)]
    return [(SK_LOW, 0.22 * lean)] + [(y, d_at(y)) for y in ys]


def skirt(part):
    t0 = _tris(part)
    pc = CP._Piece(angle=30)
    path = _plan()
    normals = []
    for i in range(len(path)):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        tx, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, tz)
        normals.append((-tz / ln, tx / ln))       # outward
    rings = []
    for (x, z, lean, top), (nx, nz) in zip(path, normals):
        outer = _section(top, lean)
        ring = [(x - nx * d, y, z - nz * d) for y, d in outer]
        ring += [(x - nx * (d + T), y, z - nz * (d + T)) for y, d in reversed(outer)]
        rings.append(ring)
    # loft: ring k (outer bottom → top, inner top → bottom); the faces run from left rear to right rear
    vr = pc.loft(rings, 'ec_skirt', cap0=True, cap1=True)
    pc.recalc = True
    CP._emit(part, pc)
    # a vertical joint strip in the middle of the plate (head-on photo)
    pc = CP._Piece()
    pc.box('ec_skirt', -0.012, 0.012, 0.30, 0.43, SK_FRONT - 0.002, SK_FRONT + 0.008)
    CP._emit(part, pc)
    # stays from the plate's back up to the under frame, and the mounting rail on top of the side panels
    pc = CP._Piece()
    for x in (-0.86, -0.30, 0.30, 0.86):
        pc.beam('ec_back', (x, 0.36, SK_FRONT - 0.05), (x * 0.9, 1.00, SK_FRONT - 0.55), 0.06, 0.05)
    for s in (-1, 1):
        xa, xb = sorted((s * (SK_X - 0.03), s * (SK_X - 0.12)))
        pc.box('ec_back', xa, xb, SK_TOP_REAR - 0.04, 1.02, SK_REAR + 0.05, SK_REAR + 0.20)
    # dark backing behind the opening (so the bogie does not show through the gap above the skirt)
    pc.box('ec_back', -1.12, 1.12, 0.42, 1.02, 9.20, 9.26)
    CP._emit(part, pc)
    return _tris(part) - t0


# ---------------------------------------------------------------- coupler
def front_coupler(part, z_face=10.0, y_axis=0.88, horn=0.10):
    t0 = _tris(part)
    dz = z_face - KEIKYU_FACE
    CP._head(part, z_face, y_axis, horn)

    def rest(p):
        CP._draft_gear(p, KEIKYU_FACE, y_axis)
        CP._cross_bar(p, y_axis - 0.005)
        CP._hoses(p, KEIKYU_FACE, y_axis)
    _moved(part, rest, dz=dz)
    # the vent boxes sit lower than on the Keikyu: centre ~0.74 (head-on photo: y 0.63…0.85)
    _moved(part, lambda p: [CP._vent_box(p, s * 0.51, 0.75) for s in (-1, 1)], dz=dz - 0.04)
    return _tris(part) - t0


def intercar_coupler(part, z_mid, y_axis=0.88):
    return CP.intercar_coupler(part, z_mid, y_axis)
