"""
L0 series: what is under the body: the bogies (articulated ones under the car joints, the end cars' leading ones
13.5 m behind the nose tip, as the game's consist puts them), each with a superconducting magnet unit on either side,
rubber support wheels standing on the guideway floor (y = 0: the train rests on them below 150 km/h; the game lifts
the model by 0.1 m above that) and small guide wheels against the side walls; and the floor between them.

Figures: estimates from published descriptions (Jacobs bogies; support and guide wheels retract at speed; the magnet
units face the guideway's side walls). Every photo of the fit (fitdata/l0) has the guideway walls in front of these
parts: nothing here is measured.
"""
import math

import train_kit as K
import l0_shape as S

P = 'l0_'
BOGIE_LEN = 4.6
MAGNET = (1.16, 1.47, 0.20, 0.92)          # x0, x1, y0, y1 of a magnet unit (its cryostat)
TYRE_R = 0.30
TYRE_W = 0.20
TYRE_X = 0.62
TYRE_Z = 1.35
GUIDE_R = 0.11


def bogie(part, zc):
    """one bogie centred at zc (the car frame)"""
    h = BOGIE_LEN / 2
    # the frame between the magnet units
    part.box(P + 'frame', -1.16, 1.16, 0.16, 0.40, zc - h + 0.25, zc + h - 0.25, bevel=0.03)
    for s in (1, -1):
        x0, x1, y0, y1 = MAGNET
        a, b = sorted((s * x0, s * x1))
        part.box(P + 'cryostat', a, b, y0, y1, zc - h, zc + h, bevel=0.07, segments=3)
        # the magnet unit's end caps and a band of bolts' flange
        for e in (-1, 1):
            part.box(P + 'frame', a - 0.005, b + 0.005, y0 + 0.05, y1 - 0.05, zc + e * h - 0.08, zc + e * h + 0.08)
        # support wheels (a pair a side), their hubs and the legs that drop them
        for e in (-1, 1):
            z = zc + e * TYRE_Z
            part.cylinder(P + 'tyre', (s * TYRE_X, TYRE_R, z), TYRE_R, TYRE_W, axis='x', segments=20)
            part.cylinder(P + 'hub', (s * (TYRE_X + TYRE_W / 2 + 0.005), TYRE_R, z), TYRE_R * 0.55, 0.012, axis='x',
                          segments=16)
            part.box(P + 'frame', s * (TYRE_X - 0.05) - 0.06, s * (TYRE_X - 0.05) + 0.06, TYRE_R, 0.30 + TYRE_R,
                     z - 0.07, z + 0.07)
        # guide wheels (axis upright) at the magnet unit's ends, against the walls
        for e in (-1, 1):
            z = zc + e * (h - 0.35)
            part.cylinder(P + 'tyre', (s * (x1 + 0.02), 0.56, z), GUIDE_R, 0.10, axis='y', segments=14)
            part.cylinder(P + 'hub', (s * (x1 + 0.02), 0.615, z), GUIDE_R * 0.55, 0.012, axis='y', segments=12)


def underfloor(part, kind):
    """the bogies a car carries (the middle car carries the two under its joints) and its floor between them"""
    if kind == 'end':
        bogie(part, S.BOGIE_FRONT)
        z0, z1 = S.JOINT_END + 2.6, S.BOGIE_FRONT - BOGIE_LEN / 2 - 0.1
        part.box(P + 'floor', -1.0, 1.0, 0.36, 0.44, z0, z1)
        part.box(P + 'floor', -0.8, 0.8, 0.36, 0.44, S.BOGIE_FRONT + BOGIE_LEN / 2 + 0.1, S.NOSE_TIP - 3.0)
    else:
        for zc in (-S.JOINT_MID, S.JOINT_MID):
            bogie(part, zc)
        part.box(P + 'floor', -1.0, 1.0, 0.36, 0.44, -S.JOINT_MID + 2.5, S.JOINT_MID - 2.5)


def add_materials(m):
    m.add(P + 'frame', '#3b3e42', roughness=0.6)
    m.add(P + 'cryostat', '#9aa0a5', metallic=1.0, roughness=0.42)
    m.add(P + 'tyre', '#151515', roughness=0.9)
    m.add(P + 'hub', '#b4b8bc', metallic=1.0, roughness=0.3)
    m.add(P + 'floor', '#46494d', roughness=0.8)
