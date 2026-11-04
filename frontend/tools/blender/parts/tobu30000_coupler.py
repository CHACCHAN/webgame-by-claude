"""
The cab car's skirt and coupler gear of the Tobu 30000 series as on the Tojo Line (no electric coupler), and the bar
coupler between the cars. A part module for the Blender model (train_kit.Part, the game's car frame, material prefix
`tc_`; the coupler pieces come from coupler_n1000 with its `cp_` materials).

  add_materials(m)
  front(part, z_face)            skirt, Shibata tight-lock coupler (contact face at z_face), gear behind the skirt
  intercar_coupler(part, z_mid)  coupler_n1000's semi-permanent bar coupler
Each returns the triangles added.

Figures (Commons "File:Tobu-Series30000 31612.jpg", MaedaAkihiko, CC0, head-on: ≈ 233 px/m over the 2.77 m front;
"File:Tobu railway 31613 at Ikebukuro Station 20240629 094055.jpg", Mike Peel, CC BY-SA 4.0):
- skirt in light blue-grey steel, very low: bottom bar y 0.19–0.30 across the whole width; corner panels |x| 0.965–1.36
  swept back towards the sides (est. 0.2 m); openings |x| 0.61–0.965 showing the gear behind; posts |x| 0.50–0.61;
  the centre opening |x| < 0.50 with the coupler; a cross bar (the coupler carrier's beam) y 0.66–0.76 between the
  posts; a small grab handle on each corner panel.
- behind the openings: on the right seen from ahead (−x) a light grey box with a red fitting on top (coupler / cock
  box), on the left a red angle cock; the end beam dark behind (est.).
- tight-lock coupler (柴田式密着連結器), axis 0.88; the 2-tier electric coupler was removed for the Tojo Line
  (ja.wikipedia), photos 2024–2026 show none. Coupler face 0.32 m ahead of the cab face (est.).
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN
import coupler_n1000 as CN

SKIRT = 'tc_skirt'
STEEL = 'tc_steel'
DARK = 'tc_dark'
BOX = 'tc_box'
RED = 'tc_red'

MATERIALS = [
    (SKIRT, '#8e9395', 0.45, 0.5),
    (STEEL, '#6d6f70', 0.4, 0.55),
    (DARK, '#1d1e20', 0.2, 0.75),
    (BOX, '#b7b8b3', 0.2, 0.5),
    (RED, '#b0242a', 0.1, 0.5),
]

Y0 = 0.88
SK_Z = 9.74             # skirt front (posts, bottom bar)
SK_BOT, SK_TOP = 0.19, 0.885
BAR_TOP = 0.30


def add_materials(m):
    for name, colour, metallic, roughness in MATERIALS:
        if name not in m.mats:
            m.add(name, colour, metallic=metallic, roughness=roughness)
    CN.add_materials(m)
    return 0


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _panel(mm, mat, a, b, y0, y1, t=0.012):
    """a plate standing on the line a → b (x, z) from y0 to y1, its face to the front side of the line"""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L = math.hypot(dx, dz)
    ux, uz = dx / L, dz / L
    nx, nz = -uz, ux
    if nz < 0:
        nx, nz = -nx, -nz
    c = ((ax + bx) / 2 - nx * t / 2, (y0 + y1) / 2, (az + bz) / 2 - nz * t / 2)
    RN.obox(mm, mat, c, (ux, 0, uz), (0, 1, 0), (nx, 0, nz), L / 2, (y1 - y0) / 2, t / 2)


def front(part, z_face):
    n0 = _tris(part)
    mm = RN._Mesh(part)
    for s in (-1, 1):
        # corner panel swept back, with its return to the body side and a grab handle
        a, b = (s * 0.965, SK_Z), (s * 1.36, SK_Z - 0.20)
        _panel(mm, SKIRT, a, b, SK_BOT, SK_TOP)
        _panel(mm, SKIRT, (s * 1.35, SK_Z - 0.20), (s * 1.35, SK_Z - 0.60), SK_BOT + 0.06, SK_TOP)
        RN.cyl(mm, SKIRT, (s * 1.08, 0.61, SK_Z - 0.06), (s * 1.24, 0.61, SK_Z - 0.14), 0.011, seg=6)
        # post, opening frame edges
        RN.box(mm, SKIRT, *sorted((s * 0.50, s * 0.61)), BAR_TOP - 0.01, SK_TOP - 0.012, SK_Z - 0.16, SK_Z - 0.002)
        RN.box(mm, SKIRT, *sorted((s * 0.94, s * 0.975)), BAR_TOP - 0.01, SK_TOP - 0.012, SK_Z - 0.20, SK_Z - 0.004)
        # behind the opening
        if s < 0:
            RN.box(mm, BOX, -0.93, -0.66, 0.34, 0.72, 9.28, 9.56)
            RN.box(mm, STEEL, -0.90, -0.69, 0.52, 0.55, 9.56, 9.565)
            RN.box(mm, RED, -0.92, -0.78, 0.72, 0.84, 9.40, 9.52)
        else:
            RN.box(mm, RED, 0.72, 0.84, 0.72, 0.81, 9.44, 9.52)
            RN.box(mm, RED, 0.84, 0.94, 0.755, 0.775, 9.47, 9.49)
            RN.cyl(mm, STEEL, (0.78, 0.81, 9.48), (0.78, SK_TOP, 9.48), 0.02, seg=8)
            RN.box(mm, STEEL, 0.68, 0.90, 0.40, 0.70, 9.20, 9.40)
        # hoses from the coupler to the cocks behind the posts
        ctrl = [(s * 0.17, Y0 - 0.12, z_face - 0.20), (s * 0.24, Y0 - 0.30, z_face - 0.28), (s * 0.30, Y0 - 0.40, 9.60),
                (s * 0.38, Y0 - 0.34, 9.50), (s * 0.42, Y0 - 0.10, 9.48)]
        RN.tube(mm, 'cp_rubber', CN._catmull(ctrl, 4), 0.02, seg=8)
        CN._cock(part, (s * 0.42, Y0 - 0.08, 9.48), s, y_top=SK_TOP, mat='cp_grime')
    # bottom bar across the whole width, cross bar between the posts
    RN.box(mm, SKIRT, -0.97, 0.97, SK_BOT, BAR_TOP, SK_Z - 0.12, SK_Z + 0.003)
    RN.box(mm, STEEL, -0.50, 0.50, 0.66, 0.76, SK_Z - 0.20, SK_Z - 0.08)
    RN.box(mm, SKIRT, -1.36, 1.36, SK_TOP - 0.01, SK_TOP + 0.005, 9.05, SK_Z)          # top plate
    # the body's front comes lower than its sides: a stainless apron under the face down to 0.89 (31612 head-on)
    RN.box(mm, 'tb_steel', -1.30, 1.30, SK_TOP, 0.99, 9.55, 9.765)
    for s in (-1, 1):
        RN.box(mm, 'tb_steel', *sorted((s * 1.30, s * 1.355)), SK_TOP, 0.99, 9.40, 9.70)
    # the end beam, dark, behind everything
    RN.box(mm, DARK, -1.30, 1.30, 0.35, 0.97, 8.95, 9.02)
    CN._head(part, z_face, Y0, 0.10)
    CN._draft_gear(part, z_face, Y0)
    return _tris(part) - n0


def intercar_coupler(part, z_mid):
    return CN.intercar_coupler(part, z_mid)
