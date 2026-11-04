"""
E5 series underfloor: what shows between and below the full-length skirts. The skirts (the body's lower side, down
to ≈ 0.30 m above the rail) hide nearly all the equipment from the side, so this is the equipment's underside and
ends as a low camera sees them, the snow plough under the nose, and the bar couplers at the gangway ends.

Figures: skirt bottom ≈ 0.30 m (side photos, see e5_shape); the plough: head-on and 3/4 photos ("E5系 U19編成",
the Omiya 3/4 views): a light grey blade ≈ 2.5 m wide under the coupler cover, its front ≈ 0.7 m behind the tip,
≈ 0.25 m above the rail. Equipment boxes, couplers: our own estimates (Shinkansen bar couplers between cars, the
coupler face at ±12.5).
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN
import e5_shape as S

P = 'e5_'


def add_materials(m):
    m.add(P + 'equip', '#3c3e41', metallic=0.2, roughness=0.65)
    m.add(P + 'plough', '#4c4f52', metallic=0.3, roughness=0.55)
    m.add(P + 'coupler', '#55585b', metallic=0.5, roughness=0.5)


def _equipment(mm, z0, z1):
    """boxes hanging from the floor (y 1.0) between the skirts, with gaps between them"""
    y_top = 1.0
    zs = [z0]
    rng = [2.3, 1.6, 2.8, 1.9, 2.4, 1.5, 2.6]
    k = 0
    while zs[-1] < z1 - 1.0:
        zs.append(min(z1, zs[-1] + rng[k % len(rng)]))
        k += 1
    for k, (a, b) in enumerate(zip(zs, zs[1:])):
        depth = 0.42 + 0.12 * ((k * 7) % 3) / 2
        hw = 1.05 if k % 2 == 0 else 0.85
        RN.box(mm, P + 'equip', -hw, hw, y_top - depth, y_top - 0.001, a + 0.12, b - 0.12, skip=('+y',))
    # the main air pipe and cable ducts along the car, under the floor's edges
    for x in (-1.25, 1.25):
        RN.cyl(mm, P + 'coupler', (x, 0.88, z0), (x, 0.88, z1), 0.035, seg=6, caps=(False, False))


def _coupler(mm, sign):
    """a bar coupler between the cars, from the draft gear under the floor to its face at the coupler line"""
    zf = sign * S.COUPLER
    zi = sign * (S.END - 0.9)
    y = 0.98
    RN.box(mm, P + 'coupler', -0.22, 0.22, y - 0.14, y + 0.12, min(zi, zi + sign * 0.5), max(zi, zi + sign * 0.5))
    RN.box(mm, P + 'coupler', -0.08, 0.08, y - 0.07, y + 0.07, min(zi + sign * 0.5, zf - sign * 0.06),
           max(zi + sign * 0.5, zf - sign * 0.06))
    RN.box(mm, P + 'coupler', -0.20, 0.20, y - 0.15, y + 0.15, min(zf, zf - sign * 0.06), max(zf, zf - sign * 0.06))


def _plough(mm):
    """the snow plough under the nose: a curved blade following the nose's plan, closed top and bottom"""
    yb, yt = 0.20, 0.36
    front = 1.25                       # its front's distance behind the nose tip
    rear = 3.30
    # plan outline (x, d) round the front: a superellipse half from the left rear corner to the right one
    hw0 = 1.02
    pts = []
    n = 14
    for k in range(n + 1):
        a = math.pi * k / n            # 0 = left rear, π = right rear
        s = math.cos(a)
        c = math.sin(a)
        x = hw0 * math.copysign(abs(s) ** 0.55, s)
        d = rear - (rear - front) * (abs(c) ** 0.45)
        pts.append((x, S.NOSE_TIP - d))
    bottom = [mm.v((x, yb, z)) for x, z in pts]
    top = [mm.v((x, yt - 0.10 * (1 - (S.NOSE_TIP - z - front) / (rear - front)), z)) for x, z in pts]
    ref = (0.0, (yb + yt) / 2, S.NOSE_TIP - (front + rear) / 2)
    for k in range(n):
        mm.face([bottom[k], bottom[k + 1], top[k + 1], top[k]], P + 'plough', smooth=True, ref=ref)
    mm.face(list(bottom), P + 'equip', ref=ref)
    mm.face(list(top), P + 'equip', ref=ref)
    # the plough's back: a dark panel closing it towards the bogie
    mm.face([bottom[0], top[0], top[-1], bottom[-1]], P + 'equip', ref=ref)


def underfloor(gear, kind):
    mm = RN._Mesh(gear)
    cab = kind in ('e523', 'e514')
    z0 = -S.BOGIE_Z + 1.75
    z1 = S.BOGIE_Z - 1.75
    _equipment(mm, z0, z1)
    _coupler(mm, -1)
    if cab:
        _plough(mm)
    else:
        _coupler(mm, 1)
    return mm.tris
