"""
JR East E231 series 0 (Musashino Line MU sets): the bolsterless bogies DT61G (motor, モハE231) and TR246 / TR246M
(trailer, the クハ cab cars; TR246M = the cab-end bogie). A part module for the Blender model (train_kit.Part, the
game's car frame, material prefix `eb_`). The counterpart of the Keikyu module bogie_th2100 (its mesh helpers are
imported).

  add_materials(m)
  bogie(part, zc, kind, facing=1) -> triangles added        kind: 'DT61G' | 'TR246' | 'TR246M'

One bogie centred at z = zc, rails at y = 0, gauge 1,067 mm. `facing` = −1 turns the bogie front to back (the
levelling valve rod, the nameplate, the motors' gear sides and, on the TR246M, the life guards, the speed sensor and
the parking brake change ends). The TR246M's front (life guard) is the +z·facing end: under a cab at +z use facing=1.

Run directly with Blender it renders test images on a placeholder body bottom and rails:
  blender -t 4 --background --factory-startup --python parts/e231_bogie.py -- <outdir> [dt61g|tr246|tr246m|all]
          [--clay] [--views side,photo,34,low34,end,top,under] [--samples N]

Figures and where they come from
- ja.wikipedia JR東日本E231系電車 / 209系電車: bolsterless bogies, axle-beam (軸梁式) axle boxes with one coil spring
  over each box; DT61G motor bogie (TD cardan drive, MT73 motors, 2 per bogie; tread brake units), TR246 trailer bogie
  (tread brakes plus one disc per axle), the cab-end bogie with a life guard and a parking brake (TR246M here, as the
  brief names it); wheel ∅ 860 mm; wheelbase 2,100 mm (the DT61 / TR246 family, as the 209 series' DT50 / TR235).
- Commons "JR East E231 series EMU 1007.JPG" (Tennen-Gas, CC BY-SA 3.0; photo p07: a TR246 cab-end bogie, square on
  from the side) is the main source. Scale 314 px/m at the frame plane from the 2.1 m wheelbase (axle-box caps 660 px
  apart), heights from the cap centre (the axle, y 0.43). Measured there:
  - side beam: over each axle box a spring head z ±(0.87…1.22) (it reaches 0.17 beyond the axle), y 0.60…0.87; the
    beam's top falls from the heads to y 0.80 at |z| < 0.55 (the air spring seat), its underside from 0.60 down to a
    flat 0.51 (|z| 0.47…0.72) and a fish belly at 0.46 (|z| < 0.40);
  - the cross beams are two pipes whose ends show as round bosses ∅ 0.17 on the beam at z ±0.245, y 0.62; between
    them a bracket plate z ±0.115, y 0.53…0.78 with two slotted pads;
  - axle box: round cap ∅ 0.20 with a three-armed cover, the box y 0.32…0.58, the spring seat on its top showing
    under the head (0.56…0.60); the axle beam runs from the box inwards to a rubber-bushed pivot in a bracket under the
    beam at |z| 0.52, y 0.47 (the beam 0.08–0.10 high); a bracket hangs from the head's outer end beside the box
    (axle damper seat, prepared);
  - air spring: bellows ∅ 0.66, y 0.855…0.965, on a laminated rubber stack ∅ 0.32, y 0.79…0.855;
  - dark brackets under the body beside the air spring z ±(0.38…0.50), y 0.80…0.97 (yaw damper seats on the body,
    prepared: no yaw dampers on the 0 series);
  - levelling valve rod at z −0.50 (the rear half on the photo's side) from the body down to a bracket plate hanging
    from the beam (z −0.43…−0.56, y 0.30…0.64);
  - a nameplate on the beam z +0.44…+0.58, y 0.705…0.765;
  - the cab end (TR246M): the frame continues forward to z +1.50 (y 0.60…0.835); the life guard (rust brown) hangs
    from it, its plate reaching ≈ 0.9 ahead of the leading axle at y 0.12…0.42; the leading axle carries the speed
    sensor (a domed housing ∅ 0.26 with a connector box) and its cable sweeps forward and up into the body; a light
    rod frame (two rods at z 1.13 / 1.35, rungs at y 0.86 / 0.38) hangs from the body outside it.
  - colours: frame #8c929c (light blue-grey paint in sun), wheels painted grey (#676669), bellows dark brown-grey,
    life guard rust brown.
- Commons "JR-East-E231-DT61G.jpg" (Tennen-Gas, CC BY-SA 3.0): the DT61G seen from the side has the same frame,
  heads, axle beams, bosses and levelling bracket as the TR246 (376 px/m: head top 0.84, belly 0.455); the motors
  show dark in the gap under the beam.
- Estimates: journal / side beam / air spring centre line x ±0.95 (journal centres 1,900 mm; side beam 0.18 wide, heads
  0.24); wheel profile (back-to-back 990 mm, width 125 mm, flange 27 mm); motors ∅ 0.44 with their axis 0.42 inside the
  axle (gear ratio 99:14), gear units inside the wheel, gear sides point-symmetric; tread brake units inside each
  wheel; the disc ∅ 0.60 on the axle at x +0.18 (point-symmetric) with its caliper on a bracket from the cross beam;
  the parking brake cylinder lies on the side beam's inner edge behind the leading head (Commons
  "JR-East-E231-TR246-Pbreak.jpg", Tennen-Gas, CC BY-SA 3.0, shows it from outside: size est.); traction by a single link from the body's centre
  pin to the cross beam, a lateral damper; the far side (−x) is the near side turned round (point-symmetric).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.dirname(_here)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import train_kit as K  # noqa: E402
from train_kit import B  # noqa: E402
import bogie_th2100 as BG  # noqa: E402

_Acc, _slab, _revolve, _helix, _box, _tube, _hull, _copy, _arc = (BG._Acc, BG._slab, BG._revolve, BG._helix, BG._box,
                                                                  BG._tube, BG._hull, BG._copy, BG._arc)

P = 'eb_'
MATERIALS = {
    # name: colour, metallic, roughness
    'frame': ('#8f959e', 0.1, 0.55),   # blue-grey paint: frame, axle boxes, beams, brackets
    'dark': ('#34363a', 0.2, 0.6),     # motors, gear units, brake units, body brackets, rods
    'wheel': ('#747477', 0.25, 0.5),    # wheel web, axle, disc (painted grey on the photos)
    'tread': ('#a9a6a0', 1.0, 0.32),   # polished tread and flange
    'rubber': ('#40362f', 0.0, 0.75),  # air spring bellows and stack, cable, bushes
    'rust': ('#6b4a39', 0.3, 0.75),    # life guard, nameplate, connector box
}

AXLE_Z = 1.05        # half the 2.1 m wheelbase
AXLE_Y = 0.43        # wheel radius 0.43
JX = 0.95            # axle box / side beam / air spring centre line (est.)
FW = 0.18            # side beam width (est.)
HW = 0.24            # spring head width (est.)
HEAD = (0.87, 1.22)  # spring head z range (|z|)
SEGS_WHEEL = 24


# ---------------------------------------------------------------- frame
def _side_frame(acc):
    """the +x side beam with its spring heads (both ends), the cross-beam bosses and the centre bracket"""
    x0, x1 = JX - FW / 2, JX + FW / 2
    h0, h1 = HEAD
    # half outline, z ≥ 0: top from the centre to the head, then the bottom back to the centre
    top = [(0.0, 0.80), (0.50, 0.80), (0.56, 0.806), (0.70, 0.834), (h0 + 0.01, 0.862)]
    bot = [(h0 + 0.01, 0.60), (0.84, 0.598), (0.79, 0.575), (0.74, 0.528), (0.70, 0.51), (0.49, 0.51), (0.45, 0.497),
           (0.42, 0.475), (0.38, 0.462), (0.30, 0.458), (0.0, 0.458)]
    half = top + bot
    poly = half + [(-z, y) for z, y in reversed(half) if z > 0]
    acc.put(_slab(poly, x0, x1, chamfer=0.012, seg=1), 'frame', sharp=40, copies='both')
    # spring heads: boxes wider than the beam, top 0.868, the outer top corner chamfered
    for s in (-1, 1):
        head = [(h0, 0.60), (h1, 0.60), (h1, 0.84), (h1 - 0.03, 0.868), (h0, 0.868)]
        head = [(s * z, y) for z, y in head]
        if s < 0:
            head.reverse()
        acc.put(_slab(head, JX - HW / 2, JX + HW / 2, chamfer=0.014, seg=1), 'frame', sharp=40, copies='both')
        # the stop lug on the head's face (a vertical pad), and the axle damper seat hanging from its outer end
        zl = s * 1.035
        acc.put(_box(JX + HW / 2, JX + HW / 2 + 0.03, 0.69, 0.80, zl - 0.025, zl + 0.025, bevel=0.008), 'frame',
                sharp=40, copies='both')
        hook = [(h1 - 0.06, 0.60), (h1 + 0.015, 0.60), (h1 + 0.015, 0.46), (h1 - 0.01, 0.425), (h1 - 0.05, 0.425),
                (h1 - 0.05, 0.46), (h1 - 0.02, 0.47), (h1 - 0.02, 0.56), (h1 - 0.06, 0.575)]
        hook = [(s * z, y) for z, y in hook]
        if s < 0:
            hook.reverse()
        acc.put(_slab(hook, JX + 0.06, JX + 0.10), 'frame', sharp=40, copies='both')
    # cross-beam bosses on the beam's outer face: a rim round a flat cap
    for zb in (-0.245, 0.245):
        prof = [(x1 - 0.005, 0.088), (x1 + 0.024, 0.086), (x1 + 0.024, 0.066), (x1 + 0.014, 0.0)]
        acc.put(_revolve(prof, (0, 0.62, zb), 'x', segs=14), 'frame', sharp=40, copies='both')
    # centre bracket plate with two slotted pads, its top block under the air spring
    acc.put(_box(x1 - 0.005, x1 + 0.025, 0.53, 0.785, -0.115, 0.115, bevel=0.006), 'frame', sharp=40, copies='both')
    for dz in (-0.062, 0.062):
        acc.put(_box(x1 + 0.025, x1 + 0.037, 0.565, 0.695, dz - 0.024, dz + 0.024, bevel=0.003), 'frame', sharp=40,
                copies='both')
        acc.put(_box(x1 + 0.036, x1 + 0.039, 0.59, 0.67, dz - 0.007, dz + 0.007), 'dark', sharp=40, copies='both')
    acc.put(_box(JX - 0.15, JX + 0.15, 0.785, 0.80, -0.16, 0.16, bevel=0.004), 'frame', sharp=40, copies='both')
    # nameplate on the slope (one per side)
    acc.put(_box(x1, x1 + 0.006, 0.705, 0.765, 0.44, 0.58), 'rust', sharp=40, copies='both')


def _cross_beams(acc):
    """the two transverse pipes, the bracket for the traction link and the lateral damper's seat"""
    for zb in (-0.245, 0.245):
        acc.put(_tube((-JX, 0.62, zb), (JX, 0.62, zb), 0.085, segs=12, caps=False), 'frame', sharp=50)
    # a box between the pipes on the centre line carries the lateral stops; link bracket on the −z pipe
    for s in (-1, 1):
        acc.put(_box(s * 0.20 - 0.03, s * 0.20 + 0.03, 0.55, 0.69, -0.17, 0.17, bevel=0.006), 'frame', sharp=40)
    acc.put(_box(0.10, 0.30, 0.50, 0.58, -0.30, -0.16, bevel=0.006), 'frame', sharp=40)


def _centre_pin(acc):
    """the body's centre pin (bolsterless), the traction link and the lateral damper"""
    acc.put(_box(-0.14, 0.14, 0.50, 0.99, -0.10, 0.10, bevel=0.01), 'dark', sharp=40)
    acc.put(_box(-0.22, 0.22, 0.95, 0.99, -0.16, 0.16), 'dark', sharp=40)
    # traction link with rubber-bushed eyes: from the pin's bottom to the bracket on the −z cross beam
    acc.put(_tube((0.20, 0.54, -0.05), (0.20, 0.54, -0.24), 0.026, segs=8), 'dark', sharp=50)
    for z in (-0.05, -0.24):
        acc.put(_revolve([(0.15, 0.045), (0.25, 0.045), (0.25, 0.0)], (0, 0.54, z), 'x', segs=10), 'rubber', sharp=50)
    acc.put(_box(0.14, 0.17, 0.50, 0.58, -0.08, 0.0), 'dark', sharp=40)
    # lateral damper: from the pin across to a bracket on the +x side beam's inner face
    acc.put(_tube((0.14, 0.56, 0.05), (0.50, 0.56, 0.05), 0.04, segs=10), 'dark', sharp=50)
    acc.put(_tube((0.50, 0.56, 0.05), (0.80, 0.56, 0.05), 0.022, segs=8), 'frame', sharp=50)
    acc.put(_box(0.80, JX - FW / 2, 0.50, 0.62, 0.00, 0.10), 'frame', sharp=40)


def _air_spring(acc):
    stack = [(0.792, 0.165), (0.806, 0.152), (0.818, 0.16), (0.832, 0.144), (0.846, 0.15), (0.856, 0.20)]
    bell = [(0.856, 0.20), (0.875, 0.29), (0.905, 0.330), (0.935, 0.322), (0.965, 0.29), (0.965, 0.30), (0.99, 0.30),
            (0.99, 0.0)]
    acc.put(_revolve(stack + bell[1:], (JX, 0, 0), 'y', segs=16), 'rubber', sharp=60, copies='both')


def _body_brackets(acc):
    """the dark brackets under the body beside each air spring (yaw damper seats, prepared), the levelling valve"""
    for zc in (-0.44, 0.44):
        acc.put(_box(JX - 0.05, JX + 0.06, 0.83, 0.99, zc - 0.045, zc + 0.045), 'dark', sharp=40, copies='both')
        acc.put(_box(JX + 0.06, JX + 0.075, 0.86, 0.93, zc - 0.03, zc + 0.03), 'rust', sharp=40, copies='both')
        acc.put(_box(JX - 0.08, JX + 0.09, 0.975, 0.995, zc - 0.07, zc + 0.07), 'dark', sharp=40, copies='both')
    # levelling valve: a bracket plate hanging from the beam (z −0.43…−0.56), the rod up to the valve on the body
    xo = JX + FW / 2
    plate = [(-0.43, 0.515), (-0.56, 0.515), (-0.56, 0.36), (-0.535, 0.30), (-0.455, 0.30), (-0.455, 0.36),
             (-0.43, 0.38)]
    plate.reverse()
    acc.put(_slab(plate, xo, xo + 0.012, chamfer=0.003), 'frame', sharp=40, copies='both')
    acc.put(_box(xo - 0.02, xo + 0.012, 0.50, 0.53, -0.57, -0.42), 'frame', sharp=40, copies='both')
    acc.put(_tube((xo + 0.03, 0.31, -0.495), (xo + 0.03, 0.95, -0.495), 0.008, segs=6), 'frame', sharp=50,
            copies='both')
    acc.put(_box(xo + 0.012, xo + 0.045, 0.30, 0.33, -0.51, -0.48), 'frame', sharp=40, copies='both')
    acc.put(_box(xo - 0.02, xo + 0.06, 0.93, 0.99, -0.56, -0.44), 'dark', sharp=40, copies='both')


# ---------------------------------------------------------------- axle boxes and wheels
def _axle_box(acc, za, sensor=False):
    """axle box at axle z = za on the +x side, the axle beam to its pivot, the spring seat; `sensor`: speed sensor"""
    inw = -1 if za > 0 else 1                  # towards the bogie centre
    xb0, xb1 = JX - 0.11, JX + 0.11
    # the box: rounded at the bottom, its top under the spring seat
    body = [(za - 0.13, 0.58), (za + 0.13, 0.58), (za + 0.13, 0.40)] + \
        [(za + 0.13 * math.cos(math.radians(a)), 0.40 + 0.08 * math.sin(math.radians(a))) for a in (-30, -60, -90, -120, -150)] + \
        [(za - 0.13, 0.40)]
    body.reverse()
    acc.put(_slab(body, xb0, xb1, chamfer=0.012), 'frame', sharp=40, copies='both')
    # spring seat (a drum with a rim) between the box and the head; the coil spring itself is inside the head
    acc.put(_revolve([(0.0, 0.115), (0.012, 0.115), (0.012, 0.105), (0.03, 0.105)],
                     (JX, 0.575, za), 'y', segs=12), 'frame', sharp=40, copies='both')
    # the axle beam: from the box inwards to the pivot at |z| 0.52
    zp = 0.52 if za > 0 else -0.52
    arm = [(za + inw * 0.10, 0.515), (zp - inw * 0.01, 0.512), (zp - inw * 0.01, 0.428), (za + inw * 0.10, 0.405)]
    if inw > 0:
        arm.reverse()
    acc.put(_slab(arm, JX - 0.05, JX + 0.05, chamfer=0.01), 'frame', sharp=40, copies='both')
    # the pivot bracket under the beam, its bushed pin
    br = [(zp - 0.07, 0.515), (zp + 0.07, 0.515), (zp + 0.07, 0.47)] + \
        [(zp + 0.07 * math.cos(math.radians(a)), 0.47 + 0.07 * math.sin(math.radians(a))) for a in (-30, -60, -90, -120, -150)] + \
        [(zp - 0.07, 0.47)]
    br.reverse()
    acc.put(_slab(br, JX + 0.05, JX + 0.09), 'frame', sharp=40, copies='both')
    acc.put(_revolve([(JX + 0.09, 0.03), (JX + 0.105, 0.03), (JX + 0.11, 0.0)], (0, 0.47, zp), 'x', segs=6), 'frame',
            sharp=40, copies='both')
    # the cap on the outer face
    xc = xb1
    if not sensor:
        acc.put(_revolve([(xc - 0.002, 0.112), (xc + 0.012, 0.112), (xc + 0.016, 0.104), (xc + 0.016, 0.098),
                          (xc + 0.028, 0.092), (xc + 0.036, 0.075), (xc + 0.040, 0.0)], (0, AXLE_Y, za), 'x', segs=12),
                'frame', sharp=40, copies='both')
        # three-armed cover (a rounded triangle) and its centre boss
        tri = []
        for k in range(3):
            a = math.radians(90 + 120 * k)
            for d in (-24, 0, 24):
                r = 0.062 if d == 0 else 0.05
                t = a + math.radians(d)
                tri.append((za + r * math.cos(t), AXLE_Y + r * math.sin(t)))
        acc.put(_slab(tri, xc + 0.036, xc + 0.052), 'dark', sharp=40, copies='both')
        acc.put(_revolve([(xc + 0.05, 0.022), (xc + 0.062, 0.022), (xc + 0.064, 0.0)], (0, AXLE_Y, za), 'x', segs=8),
                'frame', sharp=40, copies='both')
    return xc


def _sensor(acc, za):
    """the speed sensor on the leading axle (+x side only): domed housing, connector box, the cable to the body"""
    xc = JX + 0.11
    acc.put(_revolve([(xc - 0.002, 0.145), (xc + 0.02, 0.145), (xc + 0.026, 0.138), (xc + 0.085, 0.138),
                      (xc + 0.095, 0.125), (xc + 0.098, 0.0)], (0, AXLE_Y - 0.01, za), 'x', segs=14), 'frame', sharp=20)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        acc.put(_box(xc + 0.02, xc + 0.034, AXLE_Y - 0.01 + 0.118 * math.sin(a) - 0.012, AXLE_Y - 0.01 + 0.118 * math.sin(a) + 0.012,
                     za + 0.118 * math.cos(a) - 0.012, za + 0.118 * math.cos(a) + 0.012), 'frame', sharp=40)
    zc = za + 0.15
    acc.put(_box(xc + 0.02, xc + 0.075, AXLE_Y - 0.02, AXLE_Y + 0.07, zc - 0.03, zc + 0.04, bevel=0.006), 'rust',
            sharp=40)
    # the cable: down from the connector, forward round the wheel and up into the body
    pts = [(xc + 0.06, AXLE_Y - 0.08, za + 0.10), (xc + 0.07, AXLE_Y - 0.17, za + 0.17), (xc + 0.08, AXLE_Y - 0.22, za + 0.30),
           (xc + 0.09, AXLE_Y - 0.18, za + 0.48), (xc + 0.10, AXLE_Y + 0.02, za + 0.62), (xc + 0.10, AXLE_Y + 0.25, za + 0.64),
           (xc + 0.10, AXLE_Y + 0.42, za + 0.58), (xc + 0.09, AXLE_Y + 0.52, za + 0.50), (xc + 0.06, 0.99, za + 0.48)]
    import coupler_n1000 as CK
    sm = CK._catmull(pts, 2)
    bm = _tube_path(sm, 0.017, 6)
    acc.put(bm, 'frame', sharp=60)


def _tube_path(pts, r, n):
    """a round tube along a polyline (game-frame points), parallel-transported rings, capped"""
    import bmesh
    bm = bmesh.new()
    pts = [Vector(p) for p in pts]
    rings = []
    u = None
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        if u is None:
            a = Vector((0, 1, 0)) if abs(t.y) < 0.9 else Vector((1, 0, 0))
            u = t.cross(a).normalized()
        u = (u - t * u.dot(t)).normalized()
        w = t.cross(u)
        rings.append([bm.verts.new(B(*(p + r * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w))))
                      for k in range(n)])
    for i in range(len(rings) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            bm.faces.new([rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    BG._orient_closed(bm)
    return bm


def _wheelset(acc, za):
    """two wheels and the axle at z = za (back-to-back 990 mm)"""
    prof = [(0.495, 0.088), (0.495, 0.405), (0.500, 0.447), (0.514, 0.459), (0.536, 0.431), (0.620, 0.424),
            (0.590, 0.36), (0.600, 0.088)]
    mats = [0, 0, 1, 1, 1, 0, 0]
    acc.put(_revolve(prof, (0, AXLE_Y, za), 'x', segs=SEGS_WHEEL, mats=mats), ['wheel', 'tread'], sharp=28,
            copies='both')
    acc.put(_tube((-(JX - 0.10), AXLE_Y, za), (JX - 0.10, AXLE_Y, za), 0.085, segs=12, caps=False), 'wheel', sharp=50)


def _brake_unit(acc, za):
    """tread brake unit on the inner side of the +x wheel at axle za, hung from the side beam"""
    s = -1 if za > 0 else 1        # towards the bogie centre
    z_in, z_out = za + s * 0.66, za + s * 0.475
    acc.put(_box(0.53, 0.86, 0.43, 0.57, min(z_in, z_out), max(z_in, z_out), bevel=0.012), 'dark', sharp=40,
            copies='both')
    acc.put(_tube((0.50, 0.50, za + s * 0.57), (0.53, 0.50, za + s * 0.57), 0.065, segs=10), 'dark', sharp=50,
            copies='both')
    shoe = [(za + s * 0.436 * math.cos(math.radians(a)), AXLE_Y + 0.436 * math.sin(math.radians(a))) for a in (-16, -8, 0, 8, 16)]
    back = [(za + s * 0.475 * math.cos(math.radians(a)), AXLE_Y + 0.475 * math.sin(math.radians(a))) for a in (16, 0, -16)]
    poly = shoe + back
    if s > 0:
        poly.reverse()
    acc.put(_slab(poly, 0.53, 0.61), 'dark', sharp=40, copies='both')


def _parking(acc):
    """the parking brake cylinder on top of the side beam's inner edge between the air spring and the leading head
    (Commons "JR-East-E231-TR246-Pbreak.jpg"), its rod down to the leading brake unit; +x side, point-symmetric"""
    xi = JX - FW / 2 - 0.10
    acc.put(_tube((xi, 0.885, 0.50), (xi, 0.885, 0.86), 0.07, segs=14), 'dark', sharp=40, copies='both')
    acc.put(_revolve([(0.86, 0.0), (0.86, 0.075), (0.90, 0.075), (0.90, 0.0)], (xi, 0.885, 0), 'z', segs=14),
            'dark', sharp=40, copies='both')
    acc.put(_box(xi - 0.06, xi + 0.10, 0.80, 0.83, 0.52, 0.84), 'dark', sharp=40, copies='both')
    acc.put(_tube((xi, 0.885, 0.50), (xi - 0.02, 0.60, 0.45), 0.012, segs=6), 'dark', sharp=50, copies='both')


def _disc(acc, za):
    """one disc on the axle (x +0.18 for za > 0, point-symmetric) and its caliper on a bracket from the cross beam"""
    sx = 1 if za > 0 else -1
    s = -1 if za > 0 else 1
    xd = sx * 0.18
    acc.put(_revolve([(xd - 0.05, 0.12), (xd - 0.05, 0.30), (xd + 0.05, 0.30), (xd + 0.05, 0.12)],
                     (0, AXLE_Y, za), 'x', segs=20, closed=True), 'wheel', sharp=40)
    acc.put(_revolve([(xd - 0.07, 0.085), (xd - 0.07, 0.13), (xd + 0.07, 0.13), (xd + 0.07, 0.085)],
                     (0, AXLE_Y, za), 'x', segs=12, closed=True), 'wheel', sharp=40)
    zc = za + s * 0.27
    acc.put(_box(xd - 0.10, xd + 0.10, AXLE_Y - 0.06, AXLE_Y + 0.07, min(zc, zc + s * 0.10), max(zc, zc + s * 0.10),
                 bevel=0.01), 'dark', sharp=40)
    zb = 0.245 if za > 0 else -0.245
    acc.put(_box(xd - 0.03, xd + 0.03, AXLE_Y + 0.05, 0.62, min(zb, zc + s * 0.05), max(zb, zc + s * 0.05)),
            'frame', sharp=40)


def _drive(acc, za):
    """MT73 motor, TD coupling and gear unit for the axle at za (gear unit on the −x side for za > 0)"""
    s = -1 if za > 0 else 1         # towards the centre
    sx = -1 if za > 0 else 1        # gear side
    zm = za + s * 0.42
    ym = 0.455
    big = _arc(za, AXLE_Y, 0.27, 0, 360, 12)[:-1]
    small = _arc(zm, ym, 0.13, 0, 360, 8)[:-1]
    hull = _hull(big + small)
    gx0, gx1 = sorted((sx * 0.47, sx * 0.34))
    acc.put(_slab(hull, gx0, gx1, chamfer=0.01), 'dark', sharp=40)
    acc.put(_tube((sx * 0.405, 0.60, zm), (sx * 0.405, 0.62, za + s * 0.79), 0.025, segs=6), 'dark', sharp=50)
    # TD coupling
    acc.put(_revolve([(0, 0.0), (0, 0.11), (0.05, 0.11), (0.05, 0.0)], (sx * 0.34 - (0.05 if sx > 0 else 0), ym, zm),
                     'x', segs=12), 'dark', sharp=40)
    # motor frame with end bells and cooling ribs, hung from the cross beam
    a0, a1 = sorted((sx * 0.29, -sx * 0.31))
    prof = [(a0, 0.0), (a0, 0.15), (a0 + 0.05, 0.21), (a1 - 0.05, 0.21), (a1, 0.16), (a1, 0.0)]
    acc.put(_revolve(prof, (0, ym, zm), 'x', segs=14), 'dark', sharp=40)
    for k in range(3):
        x = a0 + 0.12 + k * (a1 - a0 - 0.24) / 2
        acc.put(_revolve([(x - 0.01, 0.21), (x - 0.01, 0.225), (x + 0.01, 0.225), (x + 0.01, 0.21)],
                         (0, ym, zm), 'x', segs=14, closed=True), 'dark', sharp=40)
    zb = 0.245 if za > 0 else -0.245
    acc.put(_box(-0.20, 0.14, ym + 0.12, 0.68, min(zb, zm), max(zb, zm), bevel=0.01), 'dark', sharp=40)
    acc.put(_box(-0.12, 0.08, ym + 0.20, ym + 0.27, zm - 0.09, zm + 0.09, bevel=0.01), 'dark', sharp=40)


# ---------------------------------------------------------------- the cab-end extras (TR246M)
def _life_guards(acc):
    """the frame extensions forward of the leading heads and the life guards hanging from them (both rails)"""
    h1 = HEAD[1]
    ext = [(h1 - 0.02, 0.60), (1.50, 0.60), (1.50, 0.81), (1.47, 0.835), (h1 - 0.02, 0.835)]
    ext.reverse()
    acc.put(_slab(ext, JX - 0.08, JX + 0.08, chamfer=0.012), 'frame', sharp=40, copies='mirror')
    # guard: an arm from the extension's front down to the rail, the deflector plate across the rail ahead of it
    # upper part outboard at the frame, lower part over the rail: a cranked flat bar
    upper = [(1.50, 0.80), (1.64, 0.80), (1.64, 0.40), (1.50, 0.40)]
    upper.reverse()
    acc.put(_slab(upper, JX - 0.04, JX + 0.02, chamfer=0.006), 'rust', sharp=40, copies='mirror')
    acc.put(_box(0.62, JX + 0.02, 0.40, 0.46, 1.50, 1.62, bevel=0.006), 'rust', sharp=40, copies='mirror')
    lower = [(1.50, 0.46), (1.62, 0.46), (1.62, 0.20), (1.66, 0.12), (1.50, 0.12)]
    lower.reverse()
    acc.put(_slab(lower, 0.62, 0.69, chamfer=0.006), 'rust', sharp=40, copies='mirror')
    # deflector: a plate across the rail, its outer end trailing, with a folded top edge
    a, b = (0.44, 1.97), (0.80, 1.66)
    d = Vector((b[0] - a[0], b[1] - a[1])).normalized()
    n = Vector((d.y, -d.x)) * 0.012
    import bmesh
    bm = bmesh.new()
    pts = [(a[0], a[1]), (b[0], b[1]), (b[0] + n.x, b[1] + n.y), (a[0] + n.x, a[1] + n.y)]
    lo = [bm.verts.new(B(x, 0.10, z)) for x, z in pts]
    hi = [bm.verts.new(B(x, 0.40, z)) for x, z in pts]
    bm.faces.new(lo)
    bm.faces.new(list(reversed(hi)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([lo[i], lo[j], hi[j], hi[i]])
    BG._orient_closed(bm)
    acc.put(bm, 'rust', sharp=40, copies='mirror')
    bm = bmesh.new()
    n2 = Vector((d.y, -d.x)) * 0.06
    pts = [(a[0], a[1]), (b[0], b[1]), (b[0] + n2.x, b[1] + n2.y), (a[0] + n2.x, a[1] + n2.y)]
    lo = [bm.verts.new(B(x, 0.385, z)) for x, z in pts]
    hi = [bm.verts.new(B(x, 0.40, z)) for x, z in pts]
    bm.faces.new(lo)
    bm.faces.new(list(reversed(hi)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new([lo[i], lo[j], hi[j], hi[i]])
    BG._orient_closed(bm)
    acc.put(bm, 'rust', sharp=40, copies='mirror')
    # gusset between the lower bar and the deflector's back
    acc.put(_box(0.60, 0.72, 0.12, 0.30, 1.60, 1.70), 'rust', sharp=40, copies='mirror')


def _rod_frame(acc):
    """the light rod frame hanging from the body outside the leading axle box (+x side)"""
    x = JX + 0.20
    for z in (1.13, 1.35):
        acc.put(_tube((x, 0.38, z), (x, 0.99, z), 0.008, segs=6), 'frame', sharp=50)
        acc.put(_box(x - 0.015, x + 0.015, 0.90, 0.99, z - 0.02, z + 0.02), 'frame', sharp=40)
    for y in (0.38, 0.86):
        acc.put(_tube((x, y, 1.13), (x, y, 1.35), 0.007, segs=6), 'frame', sharp=50)


# ---------------------------------------------------------------- the bogie
def bogie(part, zc, kind, facing=1):
    """one DT61G / TR246 / TR246M bogie centred at z = zc; returns the triangles added"""
    kind = kind.upper()
    assert kind in ('DT61G', 'TR246', 'TR246M'), kind
    motor = kind == 'DT61G'
    cab = kind == 'TR246M'
    acc = _Acc()
    _side_frame(acc)
    _cross_beams(acc)
    _centre_pin(acc)
    _air_spring(acc)
    _body_brackets(acc)
    for za in (AXLE_Z, -AXLE_Z):
        _axle_box(acc, za, sensor=False)
        _wheelset(acc, za)
        _brake_unit(acc, za)
        if motor:
            _drive(acc, za)
        else:
            _disc(acc, za)
    if cab:
        _life_guards(acc)
        _sensor(acc, AXLE_Z)
        _rod_frame(acc)
        _parking(acc)
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
def _main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else '/tmp/e231_bogie'
    which = argv[1].lower() if len(argv) > 1 and not argv[1].startswith('--') else 'all'
    clay = '--clay' in argv
    views = argv[argv.index('--views') + 1].split(',') if '--views' in argv else ['side', 'photo', '34', 'end']
    samples = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 32
    os.makedirs(out, exist_ok=True)
    K.clear_scene()
    BG._world_and_ground()
    scene = bpy.context.scene
    mats = K.Materials()
    add_materials(mats)
    mats.add('rail', '#6b5a4c', metallic=0.6, roughness=0.5)
    mats.add('sleeper', '#8a8780', roughness=0.9)
    mats.add('body', '#c3c6c9', metallic=0.7, roughness=0.35)
    if clay:
        for n in MATERIALS:
            p = mats[P + n].node_tree.nodes['Principled BSDF']
            p.inputs['Base Color'].default_value = K.srgb('#b8b8b8')
            p.inputs['Metallic'].default_value = 0.0
            p.inputs['Roughness'].default_value = 0.7
    root = K.car_empty('stage')
    track = K.Part('track')
    for x in (-0.566, 0.566):
        track.box('rail', x - 0.0325, x + 0.0325, -0.153, 0.0, -12, 12)
    for i in range(-20, 21):
        track.box('sleeper', -1.0, 1.0, -0.33, -0.17, i * 0.6 - 0.1, i * 0.6 + 0.1)
    track.build(root, mats)
    body = K.Part('body')
    body.box('body', -1.415, 1.415, 1.0, 1.6, -4.0, 4.0)
    bobj = body.build(root, mats)
    parts = {}
    for key in ('dt61g', 'tr246', 'tr246m'):
        if which not in (key, 'all'):
            continue
        p = K.Part('bogie_' + key)
        n = bogie(p, 0.0, key.upper(), facing=1)
        print(f'BOGIE {key}: {n} triangles')
        parts[key] = p.build(root, mats)
    suffix = '_clay' if clay else ''
    cams = {
        # like photo p07 (square on, 314 px/m, front to the left): ortho 1150 × 360 px
        'photo': dict(eye=(12.0, 0.588, 0.275), target=(0, 0.588, 0.275), ortho=1150 / 314, size=(1150, 360)),
        'side': dict(eye=(12.0, 0.55, 0.0), target=(0, 0.55, 0.0), ortho=4.4, size=(1280, 560)),
        '34': dict(eye=(2.9, 0.70, 2.7), target=(0.4, 0.50, 0.0), lens=28, size=(1280, 720)),
        'low34': dict(eye=(3.4, 0.25, 3.2), target=(0.3, 0.50, 0.0), lens=28, size=(1280, 720)),
        'end': dict(eye=(0.0, 0.6, 12.0), target=(0, 0.6, 0), ortho=3.0, size=(1100, 720)),
        'top': dict(eye=(0.0, 12.0, 0.001), target=(0, 0, 0), ortho=4.4, size=(1100, 1000)),
        'under': dict(eye=(2.2, 0.10, -3.4), target=(-0.2, 0.55, 0.3), lens=24, size=(1280, 720)),
    }
    if views == ['none']:
        return
    for key, obj in parts.items():
        for k2, o2 in parts.items():
            o2.hide_render = k2 != key
        for v in views:
            c = cams[v]
            bobj.hide_render = v in ('top', 'end')
            BG._render(os.path.join(out, f'{key}_{v}{suffix}.png'), c['eye'], c['target'], lens=c.get('lens', 35),
                       ortho=c.get('ortho'), size=c['size'], samples=samples)


if __name__ == '__main__':
    _main()
