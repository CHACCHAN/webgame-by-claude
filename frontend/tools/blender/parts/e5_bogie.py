"""
E5 series bogies: DT209 (motor cars) and TR7008 (trailers), bolsterless, axle-beam located, wheel-mounted disc
brakes. On the E5 they sit behind the body's full-length skirts and carbon bogie covers, so the side shows only the
wheels' lower halves and the axle boxes' undersides; the detail goes where a low camera or the ends can see it.

Figures (ja.wikipedia 新幹線E5系・H5系電車): wheel ∅ 860 mm; gauge 1,435 mm; bogie centres 17,500 mm and wheelbase
2,500 mm (the Shinkansen standard; estimates for the E5). Air springs, yaw dampers (two a side), axle-beam arms and
the traction motor's place: the usual Shinkansen bolsterless layout (estimates, from photos of other DT20x bogies).
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN
import e5_shape as S

P = 'e5_'
GAUGE_X = 0.7175 + 0.035        # the wheel's tread centre (rail centre 0.7175 + a little)
FRAME_X = 1.03                  # side frame centre line
MOTOR_KINDS = ('e525', 'e526')


def add_materials(m):
    m.add(P + 'bogie', '#2e3032', metallic=0.2, roughness=0.6)
    m.add(P + 'wheel', '#8d8f91', metallic=0.9, roughness=0.35)
    m.add(P + 'web', '#3b3c3e', metallic=0.3, roughness=0.6)
    m.add(P + 'rubber', '#19191a', roughness=0.8)
    m.add(P + 'disc', '#6a6b6d', metallic=0.7, roughness=0.45)
    m.add(P + 'box', '#4a4c4f', metallic=0.3, roughness=0.55)


def _wheelset(mm, z, motor):
    r = S.WHEEL_R
    for side in (1, -1):
        x = side * GAUGE_X
        # wheel: flange inside, tread, then the web and the hub (lathe along +x outwards from the axle)
        prof = [(0.085, -0.10), (r * 0.70, -0.075), (r + 0.028, -0.075), (r + 0.028, -0.055), (r + 0.004, -0.045),
                (r, -0.035), (r - 0.008, 0.065), (r - 0.04, 0.068), (r * 0.80, 0.045), (r * 0.42, 0.045),
                (0.13, 0.095), (0.085, 0.095)]
        RN.lathe(mm, None, (x, r, z), (side, 0, 0), [(a, b) for a, b in prof], seg=22, cap0=False, cap1=False,
                 mats=[P + 'web', P + 'web', P + 'wheel', P + 'wheel', P + 'wheel', P + 'wheel', P + 'wheel',
                       P + 'web', P + 'web', P + 'web', P + 'web'])
        # wheel-mounted brake discs, both faces of the web
        for t, n in ((-0.085, -1), (0.055, 1)):
            RN.cyl(mm, P + 'disc', (x + side * t, r, z), (x + side * (t + n * 0.02), r, z), r * 0.78, seg=20,
                   caps=(False, True))
        # calipers (behind the wheel, at axle height, one each side of the web)
        RN.box(mm, P + 'bogie', x + side * 0.1 - 0.06, x + side * 0.1 + 0.06, r - 0.08, r + 0.10, z + 0.36, z + 0.48)
    RN.cyl(mm, P + 'web', (-FRAME_X - 0.12, r, z), (FRAME_X + 0.12, r, z), 0.085, seg=10, caps=(True, True))
    # axle boxes (outside the wheels), their covers, the axle-beam arm towards the bogie centre
    for side in (1, -1):
        x = side * FRAME_X
        RN.cyl(mm, P + 'box', (x - side * 0.13, r, z), (x + side * 0.13, r, z), 0.135, seg=14)
        RN.disc(mm, P + 'bogie', (x + side * 0.131, r, z), (side, 0, 0), 0.10, seg=12)
        RN.box(mm, P + 'box', x - 0.12, x + 0.12, r + 0.08, r + 0.22, z - 0.17, z + 0.17)
    if motor:
        # traction motor and gearbox (frame-hung motor, cardan drive) beside the axle
        RN.cyl(mm, P + 'web', (-0.55, r + 0.02, z), (0.35, r + 0.02, z), 0.075, seg=8)
        return


def _side_frame(mm, zc, side):
    x = side * FRAME_X
    w = 0.12
    r = S.WHEEL_R
    # a side frame dipping between the axle boxes (the bolsterless frame's U)
    pts = [(-1.62, 0.76, 0.92), (-1.15, 0.72, 0.92), (-0.75, 0.52, 0.82), (0.75, 0.52, 0.82), (1.15, 0.72, 0.92),
           (1.62, 0.76, 0.92)]
    for (z0, y0, y1), (z1, y2, y3) in zip(pts, pts[1:]):
        a = [mm.v((x - w, y0, zc + z0)), mm.v((x + w, y0, zc + z0)), mm.v((x + w, y1, zc + z0)), mm.v((x - w, y1, zc + z0))]
        b = [mm.v((x - w, y2, zc + z1)), mm.v((x + w, y2, zc + z1)), mm.v((x + w, y3, zc + z1)), mm.v((x - w, y3, zc + z1))]
        ref = (x, (y0 + y1 + y2 + y3) / 4, zc + (z0 + z1) / 2)
        for k in range(4):
            mm.face([a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]], P + 'bogie', ref=ref)
        if z0 == pts[0][0]:
            mm.face(a, P + 'bogie', ref=ref)
        if z1 == pts[-1][0]:
            mm.face(b, P + 'bogie', ref=ref)
    # axle springs (coil pairs on the axle-box tops) under the frame ends
    for dz in (-1.25, 1.25):
        for e in (-0.11, 0.11):
            RN.cyl(mm, P + 'web', (x, r + 0.22, zc + dz + e), (x, 0.76, zc + dz + e), 0.065, seg=10)
    # the air spring on the frame's middle, under the body
    RN.lathe(mm, None, (x, 0.82, zc), (0, 1, 0),
             [(0.22, 0.0), (0.30, 0.04), (0.32, 0.10), (0.29, 0.15), (0.24, 0.17)], seg=18,
             mats=[P + 'rubber'] * 4)
    # yaw dampers: two along the frame's outside, to the body's bolster brackets
    for dz, y in ((0.0, 0.70), (0.0, 0.84)):
        RN.cyl(mm, P + 'rubber', (x + side * 0.20, y, zc - 0.15), (x + side * 0.20, y, zc + 0.75), 0.045, seg=8)
        RN.cyl(mm, P + 'box', (x + side * 0.20, y, zc + 0.75), (x + side * 0.20, y, zc + 1.05), 0.035, seg=8)
    # the brake / bracket boxes on the outside face
    RN.box(mm, P + 'box', x + side * 0.12 - 0.04, x + side * 0.12 + 0.04, 0.56, 0.78, zc - 0.55, zc - 0.25)


def _bogie(mm, zc, motor):
    for dz in (-S.WHEELBASE / 2, S.WHEELBASE / 2):
        _wheelset(mm, zc + dz, motor)
    for side in (1, -1):
        _side_frame(mm, zc, side)
    # transoms (two cross tubes) and the centre pivot
    for dz in (-0.32, 0.32):
        RN.cyl(mm, P + 'bogie', (-FRAME_X, 0.64, zc + dz), (FRAME_X, 0.64, zc + dz), 0.10, seg=10, caps=(False, False))
    RN.box(mm, P + 'bogie', -0.30, 0.30, 0.66, 0.98, zc - 0.20, zc + 0.20)
    if motor:
        for dz in (-0.62, 0.62):
            RN.cyl(mm, P + 'box', (-0.62, 0.62, zc + dz), (0.20, 0.62, zc + dz), 0.24, seg=14)
    # a lateral damper and the earthing / speed-sensor lead
    RN.cyl(mm, P + 'rubber', (-0.55, 0.78, zc + 0.05), (0.40, 0.78, zc + 0.05), 0.04, seg=8)


def bogies(gear, kind):
    """both bogies of a car (car frame)"""
    mm = RN._Mesh(gear)
    motor = kind in MOTOR_KINDS
    for zc in (-S.BOGIE_Z, S.BOGIE_Z):
        _bogie(mm, zc, motor)
    return mm.tris
