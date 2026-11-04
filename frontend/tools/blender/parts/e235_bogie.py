"""
JR East E235 series 0: the bolsterless bogies DT80 (motor, モハ) and TR264 / TR264B (trailer, the クハ cab cars). A part
module for the Blender model (train_kit.Part, the game's car frame, material prefix `eb_`).

  add_materials(m)
  bogie(part, zc, motor, facing=1, parking=False) -> triangles added

One bogie centred at z = zc, rails at y = 0, gauge 1,067 mm. `motor` adds the traction motors and gear units (DT80);
otherwise the axles carry brake discs (TR264). `facing` = −1 turns the bogie front to back. `parking` adds the
parking-brake cylinders of the TR264 under the cab (the front bogie of a cab car).

Mesh helpers (`_Acc`, `_slab`, `_revolve`, `_helix`, `_box`, `_tube`, `_hull`) are the Keikyu bogie module's
(bogie_th2100), imported.

Figures and where they come from
- ja.wikipedia JR東日本E235系電車 (read 2026-11-03): bolsterless bogies with axle-beam (軸はり式) axle-box
  suspension, DT80 (motor) / TR264, TR264A, TR264B (trailer); anisotropic air springs; motor bogies: tread unit
  brakes; trailer bogies: tread unit brakes and axle-mounted disc brakes; the front bogie of a cab car (TR264) has a
  parking brake; axle dampers prepared but not fitted, no yaw dampers on the 0 series; MT79 motors, 4 per motor car,
  gear ratio 7.07.
- Commons "JReast-E235-DT80.jpg" (Stealth3327, CC0): a close side view of a DT80 under a car. Scale at the frame
  plane from the axle-box caps (wheelbase 2.1 m → 696 px/m at the 1920 px thumbnail), heights from the cap centre
  (axle, y 0.43). Measured there:
  - side frame: ends (spring caps over the axle boxes) z 0.91…1.26 from the centre, y 0.60…0.90; the side beam's top
    falls from y 0.85 at the ends to 0.72 under the air spring, its underside from 0.60 to 0.415; the centre block
    (cross-beam ends) z ±0.37, y 0.42…0.72, with two round bosses ∅ 0.22 at z ±0.255 and a bolted plate with a round
    boss between them;
  - axle box: a round cap ∅ 0.24 with a three-armed cover; the axle beam runs from the box inwards and slightly up to
    a rubber-bushed pivot under the side beam at z ±0.56, y 0.48; the axle spring sits on the box under the spring
    cap (only its lowest turns show, y 0.56…0.60);
  - air spring: bellows ∅ 0.70, y 0.79…0.93, upper plate 0.93…0.97, on a laminated rubber stack ∅ 0.36 (y 0.72…0.79);
  - a link bar hangs at each frame end (z ±1.27…1.37, y 0.33…0.83; two bolts at the top, a pin at the bottom);
    the levelling valve rod (z +0.59) and a bracket plate with a cranked foot (z 0.50…0.67, y 0.33…0.67) on one side.
  - colour: mid grey paint (#707377 on the fresh frame; ours a little darker for service dust).
- Published / standard figures: wheel ∅ 860 mm; wheelbase 2,100 mm (JR East's bolsterless bogies DT71 / DT80 family);
  1,067 mm gauge, back-to-back 990 mm, wheel width 125 mm.
- Estimates: axle-box / side-beam centre line x ±0.93 (journal centres 1,860 mm), side beam 0.17 wide; motors ∅ 0.46
  on the cross beams, 0.42 from the axle; brake discs ∅ 0.60 inside the wheels (trailer); the far (−x) side is the
  near side turned round (point symmetric).
"""
import math
import os
import sys

from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_kit as K  # noqa: E402
from train_kit import B  # noqa: E402
import bogie_th2100 as BG  # noqa: E402

_Acc, _slab, _revolve, _helix, _box, _tube, _hull, _copy, _arc = (BG._Acc, BG._slab, BG._revolve, BG._helix, BG._box,
                                                                  BG._tube, BG._hull, BG._copy, BG._arc)

P = 'eb_'
MATERIALS = {
    # name: colour, metallic, roughness
    'frame': ('#5f6266', 0.05, 0.55),  # mid grey paint: frame, axle boxes, axle beams, springs
    'dark': ('#2f3134', 0.2, 0.6),     # motors, gear units, brake units, discs' calipers, rods
    'wheel': ('#55575a', 0.4, 0.5),    # wheel web and axle (painted grey on the photo)
    'tread': ('#a9a6a0', 1.0, 0.32),   # polished tread and flange
    'rubber': ('#1c1c1e', 0.0, 0.8),   # air spring bellows, bushes
    'disc': ('#7d7a76', 0.9, 0.4),     # brake discs
    'plate': ('#c9cbc8', 0.6, 0.35),   # name plates
}

AXLE_Z = 1.05        # half the 2.1 m wheelbase
AXLE_Y = 0.43        # wheel radius 0.43
JX = 0.93            # axle box / side beam centre line
FW = 0.17            # side beam width
END = 1.26           # frame end
SEGS_WHEEL = 28


def _side_frame(acc):
    """the +x side beam: spring caps at the ends, the beam dropping to the air spring seat in the middle"""
    x0, x1 = JX - FW / 2, JX + FW / 2
    # half outline (z ≥ 0) from the top centre round to the bottom centre, then mirrored
    top = [(0.0, 0.72), (0.30, 0.72), (0.40, 0.735), (0.52, 0.765), (0.66, 0.80), (0.80, 0.83), (0.905, 0.848),
           (0.91, 0.885), (0.93, 0.90), (1.22, 0.90), (1.26, 0.86)]
    bot = [(1.26, 0.60), (0.91, 0.60), (0.86, 0.595), (0.78, 0.585), (0.70, 0.56), (0.62, 0.52), (0.54, 0.475),
           (0.46, 0.44), (0.40, 0.425), (0.34, 0.415), (0.0, 0.415)]
    half = top + bot
    poly = half + [(-z, y) for z, y in reversed(half) if z > 0]
    acc.put(_slab(poly, x0, x1, chamfer=0.014, seg=1), 'frame', sharp=40, copies='both')
    # the spring cap's outer face: a raised panel with the stop lug (the "H" on the photo)
    for s in (-1, 1):
        za, zb = sorted((s * 0.95, s * 1.21))
        acc.put(_box(x1, x1 + 0.012, 0.64, 0.87, za, zb), 'frame', sharp=40, copies='both')
        zl = s * 1.05
        acc.put(_box(x1 + 0.012, x1 + 0.05, 0.70, 0.82, zl - 0.035, zl + 0.035, bevel=0.008), 'frame', sharp=40,
                copies='both')
        acc.put(_box(x1 + 0.012, x1 + 0.03, 0.74, 0.78, zl - 0.07, zl + 0.07), 'frame', sharp=40, copies='both')
    # centre block: the cross-beam ends standing out of the beam, with two round bosses and the plate between
    acc.put(_box(x1 - 0.01, x1 + 0.035, 0.425, 0.70, -0.37, 0.37, bevel=0.02, seg=2), 'frame', sharp=40, copies='both')
    for zb in (-0.255, 0.255):
        prof = [(x1 + 0.035, 0.112), (x1 + 0.062, 0.108), (x1 + 0.07, 0.09), (x1 + 0.072, 0.0)]
        acc.put(_revolve(prof, (0, 0.565, zb), 'x', segs=16), 'frame', sharp=40, copies='both')
    plate = [(-0.11, 0.48), (0.11, 0.48), (0.11, 0.63), (0.04, 0.63), (0.04, 0.665), (-0.04, 0.665), (-0.04, 0.63),
             (-0.11, 0.63)]
    acc.put(_slab(plate, x1 + 0.03, x1 + 0.055, chamfer=0.006), 'frame', sharp=40, copies='both')
    acc.put(_revolve([(x1 + 0.055, 0.045), (x1 + 0.075, 0.045), (x1 + 0.08, 0.0)], (0, 0.555, 0.0), 'x', segs=12),
            'frame', sharp=40, copies='both')
    for dz in (-0.085, 0.085):
        for yb in (0.495, 0.615):
            acc.put(_box(x1 + 0.055, x1 + 0.067, yb - 0.01, yb + 0.01, dz - 0.01, dz + 0.01), 'frame', sharp=40,
                    copies='both')
    # bracket from the body above the plate (two bolts on its foot)
    acc.put(_box(x1 + 0.03, x1 + 0.05, 0.665, 0.80, -0.022, 0.022), 'dark', sharp=40, copies='both')
    # name plate on the beam
    acc.put(_box(x1, x1 + 0.006, 0.64, 0.73, -0.52, -0.38), 'plate', sharp=40, copies='both')


def _cross_beams(acc):
    """the two transverse pipes joining the side beams, the traction centre between them"""
    for zb in (-0.255, 0.255):
        acc.put(_tube((-JX, 0.565, zb), (JX, 0.565, zb), 0.10, segs=12, caps=False), 'frame', sharp=50)
    acc.put(_box(-0.30, 0.30, 0.50, 0.66, -0.17, 0.17), 'frame', sharp=40)
    acc.put(_box(-0.10, 0.10, 0.66, 0.98, -0.10, 0.10), 'dark', sharp=40)          # centre pin from the body
    # traction link (single link) from the pin to the cross beam
    acc.put(_box(0.12, 0.20, 0.53, 0.58, -0.20, 0.20), 'dark', sharp=40)


def _axle_box(acc, za):
    """axle box with the axle beam reaching inwards to its pivot, the spring on top; +x side"""
    s = -1 if za > 0 else 1                 # towards the bogie centre
    x0, x1 = JX - 0.10, JX + 0.10
    # box body: a short cylinder along x round the bearing, flats above for the spring seat
    acc.put(_revolve([(x0, 0.0), (x0, 0.135), (x1, 0.135), (x1, 0.0)], (0, AXLE_Y, za), 'x', segs=16), 'frame',
            sharp=40, copies='both')
    acc.put(_box(x0, x1, AXLE_Y + 0.06, 0.565, za - 0.12, za + 0.12, bevel=0.015), 'frame', sharp=40, copies='both')
    # axle beam: from the box towards the centre, slightly rising, to the pivot eye (z = s·0.56 from the centre)
    zp = math.copysign(0.56, za)
    beam = [(za, AXLE_Y + 0.07), (za + s * 0.10, AXLE_Y + 0.085), (zp - s * 0.0, 0.53), (zp + s * 0.06, 0.52),
            (zp + s * 0.06, 0.44), (zp, 0.425), (za + s * 0.16, AXLE_Y - 0.035), (za, AXLE_Y - 0.09)]
    if s > 0:
        beam.reverse()
    acc.put(_slab(beam, JX - 0.07, JX + 0.07, chamfer=0.016, seg=1), 'frame', sharp=40, copies='both')
    # the pivot: rubber bush in a bracket under the side beam
    acc.put(_revolve([(JX - 0.10, 0.0), (JX - 0.10, 0.055), (JX + 0.10, 0.055), (JX + 0.10, 0.0)], (0, 0.48, zp), 'x',
                     segs=12), 'frame', sharp=40, copies='both')
    acc.put(_box(JX - 0.09, JX + 0.09, 0.48, 0.60, zp - 0.05, zp + 0.05), 'frame', sharp=40, copies='both')
    # cap: flange and a domed cover with three arms
    xc = x1
    acc.put(_revolve([(xc, 0.125), (xc + 0.02, 0.125), (xc + 0.02, 0.105), (xc + 0.04, 0.10), (xc + 0.05, 0.075),
                      (xc + 0.055, 0.0)], (0, AXLE_Y, za), 'x', segs=18), 'frame', sharp=40, copies='both')
    for k in range(3):
        a = math.radians(90 + 120 * k)
        p0 = (za + 0.03 * math.cos(a), AXLE_Y + 0.03 * math.sin(a))
        p1 = (za + 0.09 * math.cos(a), AXLE_Y + 0.09 * math.sin(a))
        acc.put(_box(xc + 0.04, xc + 0.066, min(p0[1], p1[1]) - 0.012, max(p0[1], p1[1]) + 0.012,
                     min(p0[0], p1[0]) - 0.012, max(p0[0], p1[0]) + 0.012), 'frame', sharp=40, copies='both')
    # axle spring: the lowest turns between the box top and the spring cap
    acc.put(_helix(JX, za, 0.555, 0.62, 0.085, 0.017, 2.2, per_turn=10, sides=4), 'frame', sharp=95, copies='both')


def _wheelset(acc, za, motor):
    """two wheels and the axle at z = za (1,067 mm gauge)"""
    prof = [(0.495, 0.088), (0.507, 0.447), (0.521, 0.459), (0.549, 0.431), (0.627, 0.424), (0.627, 0.372),
            (0.595, 0.20), (0.622, 0.088)]
    mats = [0, 1, 1, 1, 0, 0, 0]
    acc.put(_revolve(prof, (0, AXLE_Y, za), 'x', segs=SEGS_WHEEL, mats=mats), ['wheel', 'tread'], sharp=28,
            copies='both')
    acc.put(_tube((-0.83, AXLE_Y, za), (0.83, AXLE_Y, za), 0.085, segs=12, caps=False), 'wheel', sharp=50)
    if not motor:
        # two brake discs on the axle with their calipers (trailer)
        for xd in (-0.24, 0.24):
            acc.put(_revolve([(xd - 0.035, 0.0), (xd - 0.035, 0.30), (xd + 0.035, 0.30), (xd + 0.035, 0.0)],
                             (0, AXLE_Y, za), 'x', segs=20), 'disc', sharp=40)
            s = -1 if za > 0 else 1
            acc.put(_box(xd - 0.07, xd + 0.07, AXLE_Y + 0.05, AXLE_Y + 0.25, za + s * 0.22, za + s * 0.36),
                    'dark', sharp=40)


def _brake_unit(acc, za):
    """tread brake unit inside the +x wheel, towards the bogie centre"""
    s = -1 if za > 0 else 1
    acc.put(_box(0.47, 0.68, 0.36, 0.55, min(za + s * 0.66, za + s * 0.49), max(za + s * 0.66, za + s * 0.49),
                 bevel=0.01), 'dark', sharp=40, copies='both')
    acc.put(_tube((0.40, 0.47, za + s * 0.58), (0.47, 0.47, za + s * 0.58), 0.065, segs=10), 'dark', sharp=50,
            copies='both')
    shoe = [(za + s * 0.436 * math.cos(math.radians(a)), AXLE_Y + 0.436 * math.sin(math.radians(a))) for a in (-16, -8, 0, 8, 16)]
    back = [(za + s * 0.47 * math.cos(math.radians(a)), AXLE_Y + 0.47 * math.sin(math.radians(a))) for a in (16, 0, -16)]
    poly = shoe + back
    if s > 0:
        poly.reverse()
    acc.put(_slab(poly, 0.51, 0.62), 'dark', sharp=40, copies='both')


def _drive(acc, za):
    """MT79 motor on the cross beam, gear unit on the axle (gear side alternates)"""
    s = -1 if za > 0 else 1
    sx = -1 if za > 0 else 1
    zm = za + s * 0.42
    ym = 0.46
    hull = _hull(_arc(za, AXLE_Y, 0.27, 0, 360, 12)[:-1] + _arc(zm, ym, 0.14, 0, 360, 8)[:-1])
    gx0, gx1 = sorted((sx * 0.46, sx * 0.33))
    acc.put(_slab(hull, gx0, gx1), 'dark', sharp=40)
    mx0, mx1 = sx * 0.30, -sx * 0.40
    a0, a1 = min(mx0, mx1), max(mx0, mx1)
    prof = [(a0, 0.0), (a0, 0.17), (a0 + 0.05, 0.23), (a1 - 0.05, 0.23), (a1, 0.18), (a1, 0.0)]
    acc.put(_revolve(prof, (0, ym, zm), 'x', segs=16), 'dark', sharp=40)
    # the motor's external fan cover (外扇) on the far end and its mounting lugs to the cross beam
    xf = a1 if sx > 0 else a0
    acc.put(_revolve([(0, 0.0), (0, 0.20), (0.06, 0.20), (0.06, 0.0)], (xf - (0.06 if sx < 0 else 0), ym, zm), 'x',
                     segs=16), 'dark', sharp=40)
    zb = 0.255 if za > 0 else -0.255
    acc.put(_box(-0.25, 0.20, 0.55, 0.63, min(zb, zm), max(zb, zm)), 'dark', sharp=40)


def _end_links(acc):
    """the link bars hanging at the frame ends (two bolts above, a pin below), +x side, both ends"""
    x0 = JX + FW / 2 + 0.005
    for s in (-1, 1):
        z = s * 1.32
        bar = [(z - 0.04, 0.83), (z + 0.04, 0.83), (z + 0.04, 0.36), (z + 0.02, 0.33), (z - 0.02, 0.33), (z - 0.04, 0.36)]
        acc.put(_slab(bar, x0, x0 + 0.03, chamfer=0.006), 'frame', sharp=40)
        acc.put(_box(JX - 0.05, x0, 0.66, 0.84, min(z, s * END), max(z, s * END) + (0.04 if s > 0 else 0)),
                'frame', sharp=40)
        for yb in (0.74, 0.80):
            acc.put(_revolve([(x0 + 0.03, 0.018), (x0 + 0.045, 0.018), (x0 + 0.045, 0.0)], (0, yb, z), 'x', segs=6),
                    'frame', sharp=40)
        acc.put(_revolve([(x0 - 0.03, 0.024), (x0 + 0.06, 0.024), (x0 + 0.06, 0.0)], (0, 0.37, z), 'x', segs=8),
                'frame', sharp=40)
    # mirrored to the other side as well
    return


def _air_spring(acc):
    prof = [(0.72, 0.18), (0.79, 0.18), (0.79, 0.26), (0.81, 0.31), (0.86, 0.35), (0.91, 0.33), (0.93, 0.30),
            (0.93, 0.36), (0.97, 0.36), (0.97, 0.0)]
    acc.put(_revolve(prof, (JX, 0, 0), 'y', segs=24, mats=[0, 1, 1, 1, 1, 1, 0, 0, 0]), ['frame', 'rubber'], sharp=60,
            copies='both')


def _levelling(acc):
    """levelling valve rod and the bracket plate with the cranked foot (+x side, +z half)"""
    xo = JX + FW / 2 + 0.06
    acc.put(_tube((xo, 0.50, 0.59), (xo, 0.98, 0.59), 0.008, segs=6), 'dark', sharp=50, copies='both')
    acc.put(_box(xo - 0.02, xo + 0.02, 0.48, 0.52, 0.55, 0.63), 'dark', sharp=40, copies='both')
    plate = [(0.50, 0.67), (0.60, 0.67), (0.60, 0.40), (0.67, 0.36), (0.67, 0.33), (0.60, 0.33), (0.50, 0.40)]
    acc.put(_slab(plate, xo - 0.03, xo - 0.012, chamfer=0.004), 'frame', sharp=40, copies='both')


def bogie(part, zc, motor, facing=1, parking=False):
    """one DT80 (motor) / TR264 (trailer) bogie centred at z = zc; returns the triangles added"""
    acc = _Acc()
    _side_frame(acc)
    _cross_beams(acc)
    _air_spring(acc)
    _levelling(acc)
    for za in (AXLE_Z, -AXLE_Z):
        _axle_box(acc, za)
        _wheelset(acc, za, motor)
        _brake_unit(acc, za)
        if motor:
            _drive(acc, za)
    n0 = len(acc.bm.faces)
    _end_links(acc)
    # the end links on the far side too (point symmetric)
    links = [f for f in list(acc.bm.faces)[n0:]]
    vm = {}
    for f in links:
        vs = []
        for v in f.verts:
            if v not in vm:
                vm[v] = acc.bm.verts.new(Matrix.Rotation(math.pi, 4, 'Z') @ v.co)
            vs.append(vm[v])
        nf = acc.bm.faces.new(vs)
        nf.material_index = f.material_index
        nf.smooth = f.smooth
    if parking:
        for s in (-1, 1):
            acc.put(_tube((s * 0.62, 0.62, 0.75), (s * 0.62, 0.62, 0.55), 0.07, segs=10), 'dark', sharp=50)
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
