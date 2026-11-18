"""
The Su-47's fittings (tools/blender/jets/su47.py): landing gear, cockpit, pilot, probes, antennas, lamps. Made from
the kit's primitives in plain swatches of the airframe's texture (`SWATCHES`; su47_skin.swatch_part gives them their
place), the cockpit's tub and the instrument panel as painted skins.

The gear is the Su-27 family's as on the heavier variants: a twin-wheel nose leg and single main wheels on legs
that stand out from the engines' trunks. The wheels' places are the simulation's (vehicle/jets.ts: wheelbase 6.0 m,
track 4.0 m, nose wheels 0.6 m apart, radii 0.5 m and 0.33 m).
"""
import math

import numpy as np

import jet_kit as K
import su47_shape as SH
import su47_skin as S
from su47_shape import Z

# name: (colour, roughness, metalness[, material])
SWATCHES = {
    'sw_strut': ('#8d9398', 0.48, 0.35),         # the legs' grey enamel
    'sw_chrome': ('#d4d7da', 0.14, 1.0),         # oleo pistons
    'sw_metal': ('#6f7377', 0.38, 0.9),          # links, pins, probes
    'sw_tyre': ('#131314', 0.90, 0.0),
    'sw_hub': ('#2f5a3c', 0.52, 0.25),           # the wheels' green
    'sw_dark': ('#0b0b0c', 0.85, 0.0),
    'sw_black': ('#1c1e22', 0.46, 0.0),          # the airframe's black (doors)
    'sw_primer': ('#7d8a80', 0.7, 0.0),          # the doors' inner side, the wells
    'sw_pit': ('#4f6f7a', 0.72, 0.0),            # the cockpit's blue-grey
    'sw_seat': ('#19191a', 0.75, 0.1),
    'sw_cushion': ('#3c412f', 0.92, 0.0),
    'sw_harness': ('#8c8668', 0.9, 0.0),
    'sw_red': ('#a8170f', 0.5, 0.0),
    'sw_helmet': ('#d6d6cf', 0.32, 0.0),
    'sw_visor': ('#08090b', 0.08, 0.6),
    'sw_suit': ('#2d3d57', 0.9, 0.0),
    'sw_glove': ('#15130f', 0.8, 0.0),
    'sw_hud': ('#22382d', 0.08, 0.3),
    'sw_white': ('#dedfd9', 0.5, 0.0),
    'sw_irst': ('#0e1216', 0.06, 0.4),
    'lamp_red': ('#ff2a1a', 0.2, 0.0, 'navlight_all'),
    'lamp_green': ('#19ff5a', 0.2, 0.0, 'navlight_all'),
    'lamp_white': ('#ffffff', 0.2, 0.0, 'navlight_all'),
    'lamp_taxi': ('#fffbe8', 0.1, 0.0, 'taxilight'),
}

NOSE_WHEEL = (0.3, 0.33, 3.0)            # |x|, radius, z
MAIN_WHEEL = (2.0, 0.5, -3.0)
NOSE_HINGE = (0.0, 1.92, 3.25)
MAIN_HINGE = (1.55, 1.62, -2.72)
# where the main wheel ends up when stowed (inside the trunk, ahead of the hinge)
MAIN_STOWED = (1.30, 1.75, -1.50)


def register(atlas):
    for name, v in SWATCHES.items():
        atlas.swatch(name, v[0], v[1], v[2], v[3] if len(v) > 3 else S.AIRFRAME)


def sphere(part, mat, centre, r, seg=12, rings=8, axis=(0, 1, 0), squash=(1, 1, 1), a0=0.0, a1=math.pi):
    prof = [(r * math.sin(a0 + (a1 - a0) * k / rings), -r * math.cos(a0 + (a1 - a0) * k / rings)) for k in range(rings + 1)]
    n0 = len(part.bm.faces)
    part.revolve(mat, prof, centre, axis=axis, seg=seg)
    if squash != (1, 1, 1):
        part.bm.faces.ensure_lookup_table()
        vs = {v for f in list(part.bm.faces)[n0:] for v in f.verts}
        c = np.array(centre, float)
        for v in vs:
            g = (np.array(K.G(v.co)) - c) * np.array(squash) + c
            v.co = K.B(*g)


def wheel(part, centre, radius, width, rim, seg=28, side=1):
    """a tyre with two grooves and a dished hub, about the x axis; `side`: which way the hub's open face looks"""
    w = width / 2
    R = radius
    tyre = [(rim, -w * 0.86), (rim + 0.035, -w * 0.98), (R - 0.07, -w), (R - 0.02, -w * 0.82), (R, -w * 0.55), (R, -w * 0.24),
            (R - 0.012, -w * 0.2), (R - 0.012, -w * 0.12), (R, -w * 0.08), (R, w * 0.08), (R - 0.012, w * 0.12), (R - 0.012, w * 0.2),
            (R, w * 0.24), (R, w * 0.55), (R - 0.02, w * 0.82), (R - 0.07, w), (rim + 0.035, w * 0.98), (rim, w * 0.86)]
    part.revolve('sw_tyre', tyre, centre, axis=(1, 0, 0), seg=seg)
    # the rim's lips and the hub: dished on the outer side, the brake's housing on the inner
    o = side
    hub = [(rim, -w * 0.86 * o), (rim - 0.02, -w * 0.8 * o), (rim - 0.035, -w * 0.3 * o), (rim * 0.45, -w * 0.2 * o), (rim * 0.4, -w * 0.5 * o),
           (0.0, -w * 0.5 * o)]
    part.revolve('sw_hub', hub, centre, axis=(1, 0, 0), seg=seg)
    brake = [(rim, w * 0.86 * o), (rim - 0.02, w * 0.8 * o), (rim - 0.04, w * 0.55 * o), (rim * 0.5, w * 0.62 * o), (0.0, w * 0.62 * o)]
    part.revolve('sw_metal', brake, centre, axis=(1, 0, 0), seg=seg)
    # wheel bolts: a ring of small heads on the hub
    for k in range(8):
        a = 2 * math.pi * k / 8
        p = (centre[0] - w * 0.2 * o, centre[1] + rim * 0.62 * math.cos(a), centre[2] + rim * 0.62 * math.sin(a))
        part.cylinder('sw_metal', p, (p[0] - 0.02 * o, p[1], p[2]), 0.014, seg=6)


def link(part, a, b, r, mat='sw_strut', seg=10):
    part.cylinder(mat, a, b, r, seg=seg)


def torque_links(part, top, bottom, back, r=0.018):
    """the scissor links of an oleo leg: from the cylinder's lower end and from the axle to an elbow behind"""
    elbow = tuple(np.array(top) * 0.5 + np.array(bottom) * 0.5 + np.array(back))
    link(part, top, elbow, r, 'sw_metal', 8)
    link(part, bottom, elbow, r, 'sw_metal', 8)
    part.cylinder('sw_metal', (elbow[0] - 0.05, elbow[1], elbow[2]), (elbow[0] + 0.05, elbow[1], elbow[2]), 0.022, seg=8)


def nose_gear(leg, wheels):
    """the nose leg (hinge, strut, braces, lamps, doors) into `leg`; the two wheels and their axle into `wheels`"""
    x, r, z = NOSE_WHEEL
    H = NOSE_HINGE
    axle = (0.0, r, z)
    knee = (0.0, 1.02, z + 0.115)
    low = (0.0, r + 0.1, z + 0.012)
    link(leg, H, knee, 0.082, 'sw_strut', 14)
    leg.cylinder('sw_metal', (0.0, 1.05, z + 0.12), (0.0, 0.97, z + 0.108), 0.092, seg=14)
    link(leg, knee, low, 0.052, 'sw_chrome', 12)
    # the axle's block between the wheels
    leg.box('sw_strut', -0.085, 0.085, r - 0.07, r + 0.13, z - 0.075, z + 0.085, bevel=0.02)
    torque_links(leg, (0.0, 0.98, z + 0.2), (0.0, r + 0.08, z + 0.1), (0.0, 0.0, 0.16))
    # the drag brace back up into the bay, the retraction jack beside it
    link(leg, (0.0, 1.22, z + 0.14), (0.0, 1.86, z - 0.75), 0.04, 'sw_strut', 10)
    link(leg, (0.07, 1.5, z + 0.2), (0.07, 1.9, z + 0.75), 0.03, 'sw_metal', 8)
    # the hinge's cross tube
    leg.cylinder('sw_strut', (-0.2, H[1], H[2]), (0.2, H[1], H[2]), 0.06, seg=10)
    # landing and taxi lamps on the strut
    for sx in (-1, 1):
        c = (0.115 * sx, 1.34, z + 0.2)
        leg.cylinder('sw_dark', (c[0], c[1], c[2] - 0.05), (c[0], c[1], c[2] + 0.055), 0.078, seg=14, r2=0.085)
        leg.revolve('lamp_taxi', [(0.0, 0.07), (0.05, 0.066), (0.078, 0.055)], c, axis=(0, 0, 1), seg=14)
        link(leg, (0.0, 1.34, z + 0.15), (c[0], c[1], c[2] - 0.03), 0.018, 'sw_metal', 6)
    # the bay's doors, hanging open beside the leg
    # (the bay's forward part is shut again once the leg is down: only the pair at the leg stays open)
    for sx in (-1, 1):
        M = np.eye(4)
        tilt = math.radians(14.0) * sx
        M[:3, :3] = K.rot_matrix((0, 0, 1), tilt)
        M[:3, 3] = (0.33 * sx, 1.775, z + 0.62)
        leg.box('sw_black', -0.010, 0.010, -0.31, 0.0, -0.5, 0.5, matrix=M, bevel=0.004)
        leg.box('sw_primer', -0.017 * sx - 0.004, -0.017 * sx + 0.004, -0.285, -0.025, -0.47, 0.47, matrix=M)
        # two hinge arms up into the bay
        for dz in (-0.34, 0.34):
            link(leg, (0.3 * sx, 1.75, z + 0.62 + dz), (0.2 * sx, 1.9, z + 0.62 + dz), 0.016, 'sw_metal', 6)
    # the wheels on their common axle
    wheels.cylinder('sw_metal', (-x - 0.02, r, z), (x + 0.02, r, z), 0.045, seg=10)
    for sx in (-1, 1):
        wheel(wheels, (x * sx, r, z), r, 0.24, 0.17, seg=32, side=-sx)


def main_gear(leg, sx):
    """a main leg with its wheel and the door on it (sx: +1 = the left one)"""
    x, r, z = MAIN_WHEEL
    H = (MAIN_HINGE[0] * sx, MAIN_HINGE[1], MAIN_HINGE[2])
    foot = ((x - 0.2) * sx, r + 0.04, z)
    knee = tuple(np.array(H) * 0.42 + np.array(foot) * 0.58)
    link(leg, H, knee, 0.095, 'sw_strut', 14)
    leg.cylinder('sw_metal', tuple(np.array(H) * 0.45 + np.array(foot) * 0.55), tuple(np.array(H) * 0.39 + np.array(foot) * 0.61), 0.105, seg=14)
    link(leg, knee, foot, 0.062, 'sw_chrome', 12)
    # the axle's knuckle and the stub axle out to the wheel
    leg.box('sw_strut', min(foot[0] - 0.09, foot[0] + 0.09), max(foot[0] - 0.09, foot[0] + 0.09), r - 0.1, r + 0.14, z - 0.1, z + 0.1, bevel=0.025)
    leg.cylinder('sw_metal', (foot[0], r, z), ((x - 0.05) * sx, r, z), 0.06, seg=10)
    torque_links(leg, tuple(np.array(knee) + (0, 0.02, -0.09)), (foot[0], r + 0.1, z - 0.09), (0.0, 0.0, -0.17))
    # side brace up to the trunk, the retraction jack forward
    link(leg, tuple(np.array(H) * 0.6 + np.array(foot) * 0.4), (1.1 * sx, 1.36, z + 0.25), 0.04, 'sw_strut', 10)
    link(leg, tuple(np.array(H) * 0.7 + np.array(foot) * 0.3), (1.62 * sx, 1.5, z + 1.0), 0.032, 'sw_metal', 8)
    leg.cylinder('sw_strut', (H[0], H[1], H[2] - 0.16), (H[0], H[1], H[2] + 0.16), 0.07, seg=10)
    wheel(leg, (x * sx, r, z), r, 0.34, 0.27, seg=40, side=-sx)
    # the door carried by the leg, outboard of it
    M = np.eye(4)
    M[:3, :3] = K.rot_matrix((0, 0, 1), math.radians(-14.0) * sx)
    M[:3, 3] = (1.9 * sx, 1.47, z + 0.12)
    leg.box('sw_black', -0.012, 0.012, -0.5, 0.0, -0.5, 0.55, matrix=M, bevel=0.004)
    leg.box('sw_primer', -0.02 * sx - 0.004, -0.02 * sx + 0.004, -0.47, -0.03, -0.46, 0.51, matrix=M)
    link(leg, tuple(np.array(H) * 0.75 + np.array(foot) * 0.25), (1.9 * sx, 1.3, z + 0.2), 0.02, 'sw_metal', 6)


def fold_of(hinge, down, stowed):
    """axis and angle that carry the wheel from its place on the ground to its stowed place about the hinge"""
    a, b = np.array(down, float) - hinge, np.array(stowed, float) - hinge
    axis = K.unit(np.cross(a, b))
    ang = math.acos(max(-1.0, min(1.0, float(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b)))))
    return axis, ang


# ------------------------------------------------------------------------------------------------ cockpit

FLOOR = 2.45
TUB_X = 0.40


def cockpit_skins(atlas):
    """the tub under the canopy (welded to the opening's rim), its rear wall, the glare shield and the panel"""
    j0, j1 = SH.FB_STATIONS.index(SH.COCKPIT[0]), SH.FB_STATIONS.index(SH.COCKPIT[1])
    ds = SH.FB_STATIONS[j0:j1 + 1]
    tub = atlas.sheet('tub', (ds[-1] - ds[0], 1.5), density=0.8)
    rows, uv = [], []
    for d in ds:
        ws = SH.fb_sill(d)
        ys = SH.fb_top_y(d, ws)
        wx = min(TUB_X, ws)
        rows.append([(ws, ys, Z(d)), (wx, ys - 0.12, Z(d)), (wx, 2.80, Z(d)), (wx, FLOOR, Z(d)), (0.0, FLOOR, Z(d))])
        u = d - ds[0]
        uv.append([(u, 1.5), (u, 1.38), (u, 1.0), (u, 0.5), (u, 0.0)])
    skins = [S.Skin('tub', tub, rows, uv, mirror=True, out='in', smooth=False)]
    # the wall behind the seat, up to the canopy's rear frame
    d = SH.COCKPIT[1]
    arc = [SH.canopy_point(d, t) for t in SH.CN_ARC]
    foot = [(p[0], FLOOR, p[2]) for p in arc]
    skins.append(S.Skin('tub_rear', tub, [arc, foot], [[(2.4, 0.9 + 0.5 * t) for t in SH.CN_ARC], [(2.4, 0.3)] * len(arc)], mirror=True,
                        out=(0.0, 0.0, 1.0), smooth=False))
    # the glare shield under the windscreen: the canopy's own shape drawn in, flat on top
    shield = atlas.sheet('shield', (0.8, 0.6), density=0.6)
    gs = [4.5, 4.65, 4.8, 4.95, 5.12]
    rows, uv = [], []
    for d in gs:
        ws = SH.CN_WS(d)
        ys = SH.fb_top_y(d, ws)
        ring = []
        for t in SH.CN_ARC:
            p = SH.canopy_point(d, t)
            ring.append((p[0] * 0.84, min(ys + 0.84 * (p[1] - ys), 3.30), Z(d)))
        rows.append(ring)
        uv.append([(d - 4.5, 0.6 * k / (len(ring) - 1)) for k in range(len(ring))])
    skins.append(S.Skin('shield', shield, rows, uv, mirror=True, out='up'))
    # the instrument panel: the shield's rear face, down to the knees
    panel = atlas.sheet('panel', (0.74, 0.70), density=3.0)
    top = rows[-1]
    half = top[0][0]
    cols = [0.0, 0.25, 0.5, 0.75, 1.0]
    pr, puv = [], []
    for v in (0.0, 1.0):
        row, ruv = [], []
        for c in cols:
            x = half * c
            # the shield's lower surface at this x (its ring runs from the sill inwards)
            yt = np.interp(x, [p[0] for p in reversed(top)], [p[1] for p in reversed(top)])
            y = lerp_(2.62, yt, v)
            row.append((x, y, Z(5.12)))
            ruv.append((0.37 + x, (y - 2.62)))
        pr.append(row)
        puv.append(ruv)
    skins.append(PanelSkin('panel', panel, pr, puv, out=(0.0, 0.0, -1.0), smooth=False))
    return skins


def lerp_(a, b, t):
    return a + (b - a) * t


class PanelSkin(S.Skin):
    """the instrument panel: both halves on one sheet (the right half reads the sheet's left half)"""

    def emit(self, part, atlas, sign=1):
        S.Skin.emit(self, part, atlas, 1)
        mirrored = S.Skin(self.name, self.sheet, self.rows, [[(0.74 - u, v) for (u, v) in row] for row in self.uv], out=self.out,
                          smooth=self.smooth)
        S.Skin.emit(mirrored, part, atlas, -1)


def cockpit_fittings(part, pilot=True):
    """seat, consoles, stick, the head-up display's frame; the pilot"""
    # the K-36 seat: pan, back reclined 17°, the head box with its two telescopic tubes
    rec = math.radians(17.0)
    up = (0.0, math.cos(rec), -math.sin(rec))
    fwd = (0.0, math.sin(rec), math.cos(rec))
    seat_z = Z(6.42)
    part.box('sw_seat', -0.23, 0.23, FLOOR + 0.1, FLOOR + 0.24, seat_z - 0.05, seat_z + 0.42, bevel=0.02)
    part.box('sw_cushion', -0.19, 0.19, FLOOR + 0.24, FLOOR + 0.29, seat_z, seat_z + 0.4, bevel=0.015)
    back_c = np.array((0.0, FLOOR + 0.24, seat_z - 0.02)) + np.array(up) * 0.5
    part.obox('sw_seat', tuple(back_c), (0.46, 1.0, 0.13), axes=((1, 0, 0), up, fwd), bevel=0.02)
    part.obox('sw_cushion', tuple(back_c + np.array(fwd) * 0.075 - np.array(up) * 0.1), (0.36, 0.66, 0.04), axes=((1, 0, 0), up, fwd), bevel=0.012)
    head = back_c + np.array(up) * 0.56 + np.array(fwd) * 0.03
    part.obox('sw_seat', tuple(head), (0.30, 0.22, 0.2), axes=((1, 0, 0), up, fwd), bevel=0.02)
    part.obox('sw_cushion', tuple(head + np.array(fwd) * 0.105), (0.2, 0.15, 0.03), axes=((1, 0, 0), up, fwd), bevel=0.01)
    for sx in (-1, 1):
        a = back_c + np.array((0.19 * sx, 0, 0)) + np.array(up) * 0.1 - np.array(fwd) * 0.03
        part.cylinder('sw_metal', tuple(a), tuple(a + np.array(up) * 0.68), 0.032, seg=8)
        # harness straps over the back
        s0 = back_c + np.array((0.09 * sx, 0, 0)) + np.array(fwd) * 0.1
        part.obox('sw_harness', tuple(s0 + np.array(up) * 0.12), (0.045, 0.5, 0.012), axes=((1, 0, 0), up, fwd))
    # the firing handles between the knees
    for sx in (-1, 1):
        part.cylinder('sw_red', (0.04 * sx, FLOOR + 0.3, seat_z + 0.4), (0.04 * sx, FLOOR + 0.38, seat_z + 0.43), 0.012, seg=6)
    part.cylinder('sw_red', (-0.045, FLOOR + 0.38, seat_z + 0.43), (0.045, FLOOR + 0.38, seat_z + 0.43), 0.012, seg=6)
    # side consoles with a few raised panels, the throttle on the left
    for sx in (-1, 1):
        part.box('sw_pit', min(0.24 * sx, 0.40 * sx), max(0.24 * sx, 0.40 * sx), FLOOR, 2.80, Z(6.6), Z(5.2), bevel=0.012)
        for k, zc in enumerate((5.4, 5.7, 6.0, 6.3)):
            part.box('sw_dark', 0.32 * sx - 0.055, 0.32 * sx + 0.055, 2.80, 2.812, Z(zc + 0.11), Z(zc - 0.11))
    part.box('sw_seat', 0.27, 0.33, 2.81, 2.87, Z(5.72), Z(5.52), bevel=0.012)
    part.cylinder('sw_seat', (0.30, 2.86, Z(5.6)), (0.30, 2.95, Z(5.57)), 0.022, seg=8)
    # the stick
    part.cylinder('sw_metal', (0.0, FLOOR, Z(5.78)), (0.0, FLOOR + 0.3, Z(5.74)), 0.016, seg=8)
    part.cylinder('sw_seat', (0.0, FLOOR + 0.3, Z(5.74)), (0.0, FLOOR + 0.43, Z(5.71)), 0.024, seg=8)
    # the head-up display: two posts and the combiner glass, raked like the windscreen
    for sx in (-1, 1):
        part.cylinder('sw_dark', (0.075 * sx, 3.27, Z(5.02)), (0.075 * sx, 3.50, Z(5.09)), 0.009, seg=6)
    part.obox('sw_hud', (0.0, 3.40, Z(5.055)), (0.15, 0.19, 0.008), axes=((1, 0, 0), K.unit((0, 0.23, -0.07)), K.unit((0, 0.07, 0.23))))
    part.box('sw_dark', -0.1, 0.1, 3.22, 3.29, Z(5.1), Z(4.9), bevel=0.015)
    if pilot:
        pilot_figure(part, seat_z, up, fwd)


def pilot_figure(part, seat_z, up, fwd):
    """a seated pilot: flight suit, white helmet with the dark visor down, mask and hose, hands on stick and throttle"""
    up, fwd = np.array(up), np.array(fwd)
    hip = np.array((0.0, FLOOR + 0.36, seat_z + 0.12))
    chest = hip + up * 0.36 + fwd * 0.02
    neck = hip + up * 0.60 + fwd * 0.03
    # torso: hips to shoulders
    part.tube([tuple(hip), tuple(hip + up * 0.2 + fwd * 0.02), tuple(chest), tuple(neck - up * 0.04)], [0.15, 0.155, 0.165, 0.11], 'sw_suit',
              seg=10, ry=[0.11, 0.115, 0.115, 0.08], twist_ref=tuple(fwd))
    part.obox('sw_harness', tuple(chest + fwd * 0.115), (0.2, 0.16, 0.02), axes=((1, 0, 0), tuple(up), tuple(fwd)), bevel=0.008)
    head = neck + up * 0.15 + fwd * 0.03
    sphere(part, 'sw_helmet', tuple(head), 0.142, seg=14, rings=9, squash=(0.95, 1.0, 1.08))
    # the visor: a dark band over the face
    sphere(part, 'sw_visor', tuple(head + np.array((0, 0.0, 0.012))), 0.146, seg=14, rings=6, axis=(0, 0, 1), squash=(0.93, 0.86, 1.05),
           a0=math.radians(108), a1=math.radians(178))
    part.box('sw_dark', -0.045, 0.045, head[1] - 0.115, head[1] - 0.03, head[2] + 0.1, head[2] + 0.17, bevel=0.02)
    part.tube([(0.0, head[1] - 0.1, head[2] + 0.13), (0.03, head[1] - 0.22, head[2] + 0.12), (0.1, chest[1] - 0.02, chest[2] + 0.12)], 0.02,
              'sw_dark', seg=6)
    for sx in (-1, 1):
        sh = chest + np.array((0.19 * sx, 0.13, 0.0))
        # the left hand on the throttle, the right on the stick
        hand = np.array((0.30, 2.93, Z(5.6))) if sx > 0 else np.array((0.03, FLOOR + 0.42, Z(5.71)))
        elbow = (sh + hand) / 2 + np.array((0.07 * sx, -0.12, -0.03))
        part.tube([tuple(sh), tuple(elbow), tuple(hand)], [0.058, 0.05, 0.04], 'sw_suit', seg=8)
        sphere(part, 'sw_glove', tuple(hand), 0.045, seg=8, rings=5)
        # thigh to the knee, shin down to the pedals under the panel
        h0 = hip + np.array((0.1 * sx, -0.02, 0.05))
        knee = np.array((0.13 * sx, FLOOR + 0.42, seat_z + 0.56))
        foot = np.array((0.14 * sx, FLOOR + 0.06, seat_z + 0.98))
        part.tube([tuple(h0), tuple(knee), tuple(foot)], [0.085, 0.07, 0.05], 'sw_suit', seg=8)
        part.box('sw_glove', foot[0] - 0.05, foot[0] + 0.05, FLOOR, FLOOR + 0.1, foot[2] - 0.06, foot[2] + 0.2, bevel=0.02)


# ------------------------------------------------------------------------------------------------ small things

def details(part):
    """the nose probe, the infra-red sensor's ball, antennas, the navigation lamps"""
    # the air data probe on the radome's tip
    tip_y = SH.FB_YC(0.9)
    part.tube([(0.0, tip_y - 0.012, Z(0.0)), (0.0, tip_y - 0.008, Z(0.35)), (0.0, tip_y, Z(0.95))], [0.011, 0.016, 0.026], 'sw_metal', seg=8)
    # the infra-red search and track ball ahead of the windscreen, set to starboard
    d = 4.02
    x = -0.10
    y = SH.fb_top_y(d, x)
    sphere(part, 'sw_irst', (x, y + 0.035, Z(d)), 0.115, seg=14, rings=8)
    part.revolve('sw_black', [(0.135, 0.0), (0.125, 0.04), (0.118, 0.06)], (x, y - 0.03, Z(d)), axis=(0, 1, 0), seg=14)
    # blade antennas: on the spine, under the nose, under the belly
    for (d, top, h) in ((9.6, True, 0.26), (3.7, False, 0.22), (13.0, False, 0.24)):
        y = SH.fb_top_y(d, 0) - 0.02 if top else (SH.fb_bottom_y(d) + 0.02 if d < 12 else SH.DK_BELLY(d) + 0.02)
        s = 1 if top else -1
        prof = [(Z(d - 0.16), 0.0), (Z(d + 0.2), 0.0), (Z(d + 0.24), h * 0.95), (Z(d + 0.08), h)]
        for k in range(len(prof)):
            a, b = prof[k], prof[(k + 1) % len(prof)]
            for sx in (-1, 1):
                part.face([(0.012 * sx, y + s * a[1], a[0]), (0.012 * sx, y + s * b[1], b[0]), (0.0, y + s * b[1], b[0]), (0.0, y + s * a[1], a[0])][::(1 if (sx * s) > 0 else -1)],
                          'sw_black', smooth=False)
        for sx in (-1, 1):
            part.face([(0.012 * sx, y + s * p[1], p[0]) for p in prof][::(-1 if (sx * s) > 0 else 1)], 'sw_black', smooth=False)
    # angle-of-attack vanes and pitot heads on the nose's sides
    for sx in (-1, 1):
        d = 3.75
        xs = SH.fb_side_x(d, 2.42) * sx
        part.tube([(xs - 0.02 * sx, 2.42, Z(d)), (xs + 0.08 * sx, 2.42, Z(d)), (xs + 0.085 * sx, 2.42, Z(d - 0.22))], [0.014, 0.012, 0.007], 'sw_metal', seg=6)
    # navigation lamps: red on the left tip, green on the right, white on the fins' tops
    tip = SH.WING_TIP
    le, c, _ = SH.wing_station(tip - 0.16)
    for sx, name in ((1, 'lamp_red'), (-1, 'lamp_green')):
        sphere(part, name, ((tip - 0.045) * sx, SH.WING_Y, Z(le + 0.33 * c)), 0.05, seg=10, rings=6, squash=(0.9, 0.55, 3.2))
    b = SH.fin_span() - SH.FIN['cut'] - 0.02
    (fx, fy), _ = SH.fin_frame(b)
    le, c, _ = SH.fin_station(b)
    for sx in (-1, 1):
        sphere(part, 'lamp_white', (fx * sx, fy, Z(le + c + 0.01)), 0.04, seg=8, rings=5, squash=(0.6, 1.0, 1.6))
    # one more white lamp under the nose (the lower anti-collision light's place)
    yb = SH.fb_bottom_y(4.9)
    sphere(part, 'lamp_white', (0.0, yb + 0.01, Z(4.9)), 0.045, seg=8, rings=5, squash=(1.0, 0.5, 1.4))
