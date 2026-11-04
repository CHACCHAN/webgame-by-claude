"""
E5 series roof: the PS208 single-arm pantograph of a pantograph car (E525), its two large noise shields (side plates,
light grey) and the insulators, the high-voltage cable's covers along the roof.

Figures:
- ja.wikipedia 新幹線E5系・H5系電車: PS208, a single-arm pantograph with a "く"-shaped frame and a head of one
  collector; large noise shields on the sides (遮音板) and small insulator covers; car height 4,490 mm over the shields.
- Photos (see the e5 scratch list.json): "E525-101.jpg", "E525-1.jpg" (side), "E5kei PS208.jpg" (close-up), the
  aerial "Tohoku Shinkansen ... Hoku Topia" (plan): the shields are two upright plates ≈ 7.2 m long at the base,
  ≈ 4.6 m on top (45° ends), standing on the roof's shoulders at x ≈ ±1.30, their top 4.49 m above the rail; the
  pantograph between them in the plates' middle.
Our own: the pantograph's exact frame (link lengths for a working height of 5.0 m), the insulators' ribs.
"""
import math

import train_kit as K  # noqa: F401
import roof_n1000 as RN
import e5_shape as S

P = 'e5_'
SHIELD = dict(z0=4.40, z1=11.60, slope=1.30, x=1.30, top=4.49, t=0.035)
PANTO_Z = 8.0
WORK_H = 5.0            # collector height (raised): the contact wire's 5.0 m


def add_materials(m):
    m.add(P + 'shield', '#b7bbbf', metallic=0.35, roughness=0.3)
    m.add(P + 'insulator', '#3a2f2c', roughness=0.35)
    m.add(P + 'panto', '#c23a30', metallic=0.2, roughness=0.45)
    m.add(P + 'pbase', '#8e9295', metallic=0.5, roughness=0.45)
    m.add(P + 'strip', '#202022', roughness=0.7)


def roof_y(x):
    """the body's roof height at x (the full section)"""
    p = S.BODY
    xe, ye, yt, nr = p['xe'], p['ye'], p['yt'], p['nr']
    if abs(x) >= xe:
        return ye
    return ye + (yt - ye) * (1 - (abs(x) / xe) ** nr) ** (1 / nr)


def _shield(mm, side):
    s = SHIELD
    x = side * s['x']
    y0 = roof_y(s['x']) - 0.03
    top = s['top']
    zs = [s['z0'], s['z0'] + s['slope'], s['z1'] - s['slope'], s['z1']]
    # outline (z, y) as a flat plate, rounded top corners by short chamfers
    outline = [(zs[0], y0), (zs[1] - 0.08, top - 0.08), (zs[1] + 0.05, top), (zs[2] - 0.05, top), (zs[2] + 0.08, top - 0.08),
               (zs[3], y0)]
    t = s['t']
    outer = [mm.v((x + side * t / 2, y, z)) for z, y in outline]
    inner = [mm.v((x - side * t / 2, y, z)) for z, y in outline]
    mid = ((y0 + top) / 2, (zs[0] + zs[3]) / 2)
    # faces: outer plate (faces outwards), inner plate, the rim
    mm.face(outer, P + 'shield', ref=(x - side * 0.5, (y0 + top) / 2, (zs[0] + zs[3]) / 2))
    mm.face(inner, P + 'shield', ref=(x + side * 0.5, (y0 + top) / 2, (zs[0] + zs[3]) / 2))
    n = len(outline)
    for k in range(n - 1):
        mm.face([outer[k], outer[k + 1], inner[k + 1], inner[k]], P + 'shield', ref=(x, mid[0], mid[1]))
    # stays: three struts from the plate's inside to the roof
    for z in (zs[1] + 0.4, (zs[1] + zs[2]) / 2, zs[2] - 0.4):
        RN.beam(mm, P + 'pbase', (x - side * 0.02, top - 0.35, z), (side * 0.75, roof_y(0.75) - 0.01, z), 0.05, 0.03)


def _insulator(mm, x, z, y0, h=0.26, r=0.075):
    prof = [(r * 0.8, 0.0)]
    n = 4
    for k in range(n):
        t0 = h * k / n
        prof += [(r * 1.55, t0 + h / n * 0.30), (r * 1.55, t0 + h / n * 0.45), (r, t0 + h / n * 0.75)]
    prof += [(r * 0.8, h)]
    RN.lathe(mm, P + 'insulator', (x, y0, z), (0, 1, 0), prof, seg=12)


def _pantograph(mm, zc):
    yr = roof_y(0.0)
    yb = yr + 0.30                      # base frame on its insulators
    for x in (-0.42, 0.42):
        for dz in (-0.45, 0.45):
            _insulator(mm, x, zc + dz, yr - 0.02)
    RN.box(mm, P + 'pbase', -0.55, 0.55, yb - 0.02, yb + 0.07, zc - 0.62, zc + 0.62)
    # the lower arm from the hinge (base's +z end) back up to the knee, the upper arm forward to the head ("く")
    hinge = (0.0, yb + 0.12, zc + 0.48)
    knee = (0.0, yb + 0.12 + (WORK_H - yb) * 0.55, zc - 0.85)
    head = (0.0, WORK_H - 0.10, zc - 0.05)
    RN.cyl(mm, P + 'pbase', (-0.30, hinge[1], hinge[2]), (0.30, hinge[1], hinge[2]), 0.06, seg=10)
    for x in (-0.22, 0.22):
        RN.tube(mm, P + 'panto', [(x, hinge[1], hinge[2]), (x * 0.25, knee[1], knee[2])], [0.045, 0.03], seg=8)
    RN.tube(mm, P + 'panto', [knee, head], [0.032, 0.022], seg=8)
    # the lower link (thin rod) and the damper / raising spring box on the base
    RN.tube(mm, P + 'pbase', [(0.0, yb + 0.10, zc + 0.15), (0.0, knee[1] - 0.12, knee[2] + 0.18)], 0.012, seg=6)
    RN.box(mm, P + 'pbase', -0.14, 0.14, yb + 0.05, yb + 0.22, zc + 0.05, zc + 0.40)
    RN.cyl(mm, P + 'strip', (0.0, yb + 0.15, zc - 0.10), (0.0, yb + 0.15, zc - 0.50), 0.04, seg=8)
    # the head: a single collector (carbon strip on a long aluminium bar) on a small pan spring box, red horns
    y = WORK_H
    RN.box(mm, P + 'pbase', -0.12, 0.12, y - 0.16, y - 0.06, head[2] - 0.08, head[2] + 0.08)
    RN.box(mm, P + 'pbase', -0.62, 0.62, y - 0.07, y - 0.015, head[2] - 0.05, head[2] + 0.05)
    RN.box(mm, P + 'strip', -0.60, 0.60, y - 0.015, y, head[2] - 0.03, head[2] + 0.03)
    for side in (1, -1):
        pts = [(side * 0.60, y - 0.04, head[2])]
        for k in range(1, 6):
            a = (math.pi / 2) * k / 5
            pts.append((side * (0.60 + 0.30 * math.sin(a)), y - 0.04 - 0.22 * (1 - math.cos(a)), head[2]))
        RN.tube(mm, P + 'panto', pts, 0.016, seg=6)
    # the high-voltage lead from the base to the roof's cable cover
    RN.tube(mm, P + 'strip', [(0.42, yb - 0.02, zc - 0.62), (0.42, yr + 0.06, zc - 1.0), (0.42, yr + 0.04, zc - 2.0)],
            0.03, seg=8)


def _cable_cover(mm, z0, z1, x=0.42):
    """the low cover over the roof cable (a half-round strip)"""
    y = roof_y(x)
    RN.box(mm, P + 'pbase', x - 0.07, x + 0.07, y - 0.03, y + 0.06, z0, z1)


def roof(gear, kind):
    mm = RN._Mesh(gear)
    if kind == 'e525':
        for side in (1, -1):
            _shield(mm, side)
        _pantograph(mm, PANTO_Z)
        _cable_cover(mm, S.END - 0.6, PANTO_Z - 2.0)
        _cable_cover(mm, -S.END + 0.6, PANTO_Z - 2.0)
    return mm.tris
