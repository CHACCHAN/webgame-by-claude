"""
Underfloor equipment of the JR East E235 series 0 (Yamanote Line): the boxes under the cab cars (クハE235 / クハE234:
static inverter, battery, brake control, air compressor on one of them) and under the モハE235 (main converter /
VVVF inverter, filter reactor, brake control, tanks), and the under frame between them. A part module for the
Blender model (train_kit.Part, the game's car frame, material prefix `eu_`; the frame and the small hardware are
underfloor_n1000's helpers, which use its `uf_` material names: this module adds those names first with the E235's
greys, so the Keikyu's olive paint does not appear).

  underfloor_cab(part)       a cab car (cab at +z)
  underfloor_motor(part)     the モハE235
  add_materials(m)

Figures and where they come from:
- ja.wikipedia JR東日本E235系電車 (read 2026-11-03): the クハE235 / クハE234 carry the SIV (static inverter), the
  battery and the brake control unit; the モハE235 the main converter (SiC VVVF inverter, 1C4M ×1… per car) and its
  filter reactor; 4M7T in the 11-car set.
- Line-scan photo dllu 02 (Dllu, CC BY-SA 4.0; 86.4 px/m): under the クハE235-9 boxes over z 4.87…4.21, 3.22…−0.10
  (the long one), −0.15…−2.24, −2.67…−3.46, −3.86…−4.33, −4.73…−5.08; all dark grey with flat lids and vertical
  seams; their bottom about level with the axles' lower edge; light-grey small boxes under the cab end.
- "JR East mohaE235-2 20150419" (Rsa, CC BY-SA 3.0): under the モハE235 two light-grey boxes in the middle of the car
  (the main converter's covers), dark boxes beside them, a round fan grille, a black box near the bogie.
- Estimates: box depths across the car, which side a lid faces, the far side's equipment, the box bottom 0.36.
"""
import os
import sys

sys.dont_write_bytecode = True
try:
    import train_kit as K
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import train_kit as K
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import underfloor_n1000 as UF  # noqa: E402

MATS = {
    # underfloor_n1000's names with the E235's colours (taken first, so its own colours are skipped)
    'uf_body': ('#4a4d51', 0.35, 0.55),    # box shells: dark grey
    'uf_lid': ('#55595d', 0.35, 0.5),      # lids, a shade lighter
    'uf_light': ('#a9abab', 0.45, 0.42),   # light-grey covers (main converter, small boxes)
    'uf_steel': ('#2c2e30', 0.55, 0.55),   # frame, hangers, pipes
    'uf_hw': ('#9b9ea1', 0.8, 0.35),       # latches, plates
    'uf_dark': ('#121314', 0.2, 0.75),     # gaps, grille depth
    'eu_fan': ('#1d1e20', 0.3, 0.6),       # fan grille rings
}

X = 1.26
TOP = 0.90
BOT = 0.36


def add_materials(m):
    for name, (col, met, rough) in MATS.items():
        if name not in m.mats:
            m.add(name, col, metallic=met, roughness=rough)
    UF.add_materials(m)


def _tris(part):
    return sum(len(f.verts) - 2 for f in part.bm.faces)


def _panels(p, s, xf, z0, z1, y0, y1, n, mat='uf_lid', latches=True):
    """n flat lids side by side on a face at x = xf (outward s), with gaps and two latches each"""
    w = (z1 - z0) / n
    for k in range(n):
        a, b = z0 + k * w + 0.012, z0 + (k + 1) * w - 0.012
        UF._box(p, 'uf_dark', xf, xf + s * 0.003, y0, y1, a - 0.008, b + 0.008)
        UF._box(p, mat, xf, xf + s * 0.010, y0 + 0.01, y1 - 0.01, a, b, c=0.003)
        if latches and b - a > 0.25:
            for yy in (y1 - 0.06, y0 + 0.06):
                UF._box(p, 'uf_hw', xf + s * 0.010, xf + s * 0.020, yy - 0.012, yy + 0.012, (a + b) / 2 - 0.03, (a + b) / 2 + 0.03)


def _cabinet(p, z0, z1, x0=-X, x1=X, y0=BOT, y1=TOP, lids=(3, 3), mat='uf_body', lid='uf_lid'):
    """a box under the floor with flat lids on its outer face(s); lids: (on the −x face, on the +x face)"""
    UF._box(p, mat, x0, x1, y0, y1, z0, z1, c=0.012)
    UF._box(p, 'uf_steel', x0 - 0.008, x1 + 0.008, y0 - 0.004, y0 + 0.03, z0 - 0.008, z1 + 0.008, c=0.004)
    for s, xf, n in ((-1, x0, lids[0]), (1, x1, lids[1])):
        if n and abs(xf) > 1.0:
            _panels(p, s, xf, z0 + 0.04, z1 - 0.04, y0 + 0.06, y1 - 0.06, n, mat=lid)
            UF._hangers(p, s, xf, z0, z1, [z0 + 0.08 + (z1 - z0 - 0.16) * k / max(1, n) for k in range(n + 1)])


def _fan(p, s, xf, zc, yc, r=0.17):
    """a round fan grille on a face"""
    UF._lathe(p, 'uf_dark', 'x', (xf, yc, zc), [(0.0, r + 0.03), (s * 0.012, r + 0.03), (s * 0.012, 0.0)], n=20, smooth=False)
    for rr in (r, r * 0.66, r * 0.33):
        UF._lathe(p, 'eu_fan', 'x', (xf, yc, zc), [(s * 0.012, rr), (s * 0.022, rr), (s * 0.022, rr - 0.012),
                                                     (s * 0.012, rr - 0.012)], n=20, smooth=False)


def _cab_items(p):
    # the long box: static inverter (SIV), lids on both sides, a mesh grille at one end of the right side
    _cabinet(p, -0.10, 3.22, lids=(4, 5))
    UF._grille(p, -1, -X - 0.01, 2.45, 3.12, BOT + 0.08, TOP - 0.08)
    # brake control unit towards the cab bogie
    _cabinet(p, 4.21, 4.87, x0=-X, x1=-0.10, lids=(1, 0))
    _cabinet(p, 4.25, 4.85, x0=0.25, x1=X, y0=0.48, lids=(0, 1), mat='uf_light', lid='uf_light')
    # battery box
    _cabinet(p, -2.24, -0.15, lids=(3, 3))
    # small boxes and tanks towards the gangway end
    _cabinet(p, -3.46, -2.67, x0=-X, x1=0.0, y0=0.44, lids=(2, 0))
    UF._tank(p, (0.65, 0.62, -3.05), 0.17, 0.80, 'z', straps=(-0.3, 0.3))
    _cabinet(p, -4.33, -3.86, x0=-X, x1=-0.30, y0=0.48, lids=(1, 0))
    UF._tank(p, (0.0, 0.64, -4.20), 0.18, 2.0, 'x', straps=(-0.33, 0.0, 0.33))
    _cabinet(p, -5.08, -4.73, x0=0.30, x1=X, y0=0.52, lids=(0, 1), mat='uf_light', lid='uf_light')
    # light-grey boxes beyond the cab bogie, in front of the skirt's side panels
    _cabinet(p, 8.45, 8.85, x0=-1.05, x1=-0.40, y0=0.58, lids=(0, 0), mat='uf_light')
    _cabinet(p, 8.45, 8.85, x0=0.40, x1=1.05, y0=0.58, lids=(0, 0), mat='uf_light')


def _motor_items(p):
    # main converter (VVVF): light-grey covers in the middle of the car, dark boxes beside them
    _cabinet(p, -1.30, 1.10, lids=(2, 2), mat='uf_light', lid='uf_light')
    _cabinet(p, 1.20, 2.40, lids=(2, 2))
    _fan(p, -1, -X - 0.011, 1.80, 0.63)
    _fan(p, 1, X + 0.011, 1.80, 0.63)
    # filter reactor and line breaker box
    _cabinet(p, -3.10, -1.40, lids=(3, 2))
    _cabinet(p, 2.55, 3.45, x0=-X, x1=-0.05, lids=(2, 0))
    _cabinet(p, 2.55, 3.20, x0=0.05, x1=X, y0=0.44, lids=(0, 1), mat='uf_light', lid='uf_light')
    # brake control and tanks towards the bogies
    _cabinet(p, -4.30, -3.30, x0=-X, x1=-0.05, y0=0.46, lids=(2, 0))
    UF._tank(p, (0.65, 0.62, -3.80), 0.17, 0.90, 'z', straps=(-0.3, 0.3))
    _cabinet(p, 3.60, 4.60, x0=0.05, x1=X, y0=0.46, lids=(0, 2))
    UF._tank(p, (-0.65, 0.62, 4.10), 0.17, 0.90, 'z', straps=(-0.3, 0.3))
    _cabinet(p, -5.10, -4.50, x0=0.30, x1=X, y0=0.52, lids=(0, 1), mat='uf_dark', lid='uf_body')


def underfloor_cab(part):
    tmp = K.Part('uf_tmp')
    _cab_items(tmp)
    UF._frame(tmp, -9.4, 8.9)
    return UF._emit(part, tmp, False)


def underfloor_motor(part):
    tmp = K.Part('uf_tmp')
    _motor_items(tmp)
    UF._frame(tmp, -9.4, 9.4)
    return UF._emit(part, tmp, False)
