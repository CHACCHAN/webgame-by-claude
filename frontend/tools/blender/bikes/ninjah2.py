"""
Kawasaki Ninja H2 (2015-, road bike) for TOUGE NOCTURNE, game id `ninjah2`: the supercharged inline four in a green
steel trellis frame, single-sided swingarm on the left, one big silencer on the right, angular bodywork in mirror-coated
black, a single LED projector head lamp between the ram-air intake (left) and a louvred vent (right). Our own model,
built from the published figures (length 2085, width 770, height 1125, wheelbase 1455, seat 825 mm; 120/70ZR17,
200/55ZR17; caster 24.9 deg, trail 103 mm) and measurements of photos (fitdata/ninjah2); no outside model, no photo
pixels; the emblem and lettering are our own simple shapes. Run with Blender 5.x (see bike_main.py for the options):

  blender -t 6 -b --factory-startup --python tools/blender/bikes/ninjah2.py -- --out <file.glb> [--render <dir> ...]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

import bike_kit as K  # noqa: E402
import bike_logos as L  # noqa: E402
import bike_parts as P  # noqa: E402
import rider as RD  # noqa: E402

WB = 1.455
RF, RR = 0.300, 0.326           # 120/70ZR17, 200/55ZR17
WF, WR = 0.120, 0.200
FZ, RZ = WB / 2, -WB / 2
ST = P.Steering(WB, RF, 24.9, 0.103, 0.86)
PIVOT = np.array([0.0, 0.43, -0.145])     # swingarm pivot (measured on r01)


def materials(paint='#64686e'):
    import bpy
    m = K.Materials()
    # mirror-coated spark black: a silver mirror layer under a black-tinted clear coat, so it reads as dark chrome
    # (a dark grey metal that mirrors its surroundings), not as black paint
    m.add('paint', paint, metallic=1.0, roughness=0.05, coat=1.0)
    m.add('accent', '#55c81e', roughness=0.3, coat=0.5)              # lime green pin stripes
    m.add('glass', '#59636c', metallic=0.35, roughness=0.03)         # clear screen, light smoke
    m.add('trim', '#121214', roughness=0.55)                         # black plastics
    m.add('housing', '#2a2c30', metallic=1.0, roughness=0.22)        # head lamp housing: dark chrome
    m.add('mesh', '#2a2b2e', metallic=1.0, roughness=0.5)            # intake mesh
    m.add('frame', '#3cb52a', metallic=0.6, roughness=0.22, coat=0.6)    # green trellis (painted steel)
    m.add('frame2', '#1b1c1f', metallic=1.0, roughness=0.42)         # black-painted aluminium: subframe, rear sets
    m.add('arm', '#1d1e21', metallic=1.0, roughness=0.38)            # single-sided swingarm (black aluminium)
    m.add('engine', '#3a3c40', metallic=0.6, roughness=0.4)          # dark grey cases and head cover
    m.add('engine2', '#a7abb0', metallic=1.0, roughness=0.28)        # aluminium: supercharger, cover rims
    m.add('radiator', '#232426', metallic=1.0, roughness=0.6)
    m.add('exhaust', '#4e5054', metallic=1.0, roughness=0.16)        # stock silencer: dark brushed stainless (r07)
    m.add('duct', '#0d0e10', roughness=0.12, coat=1.0)               # glossy black ram-air duct
    m.add('engine3', '#5d6066', metallic=0.7, roughness=0.34)        # the round covers (clutch, generator, pulser)
    m.add('chamber', '#b49c6a', metallic=1.0, roughness=0.26)        # heat-tinted stainless headers, collector
    m.add('chrome', '#e2e5e9', metallic=1.0, roughness=0.06)
    lens = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'ninjah2', 'headlight.png'), check_existing=True)
    m.add('headlight', '#e8ecf2', metallic=0.0, roughness=0.1, image=lens)
    tail = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'ninjah2', 'taillight.png'), check_existing=True)
    m.add('taillight', '#ffffff', roughness=0.2, image=tail)
    m.add('indicator', '#e08a1e', roughness=0.2)
    m.add('tire', '#141415', roughness=0.85)
    m.add('rim', '#17181a', metallic=0.6, roughness=0.32)
    m.add('rim_stripe', '#5fd326', roughness=0.35)
    disc = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'ninjah2', 'disc.png'), check_existing=True)
    m.add('disc', '#8a8d90', metallic=1.0, roughness=0.35, image=disc)  # drilled steel ring (the texture: holes)
    m.add('disc_carrier', '#242528', metallic=0.6, roughness=0.4)    # the floating discs' black carriers (r01)
    m.add('gold', '#c9a24a', metallic=1.0, roughness=0.3)            # bobbins and carrier bolts
    m.add('brake', '#b8bbbf', metallic=1.0, roughness=0.36)          # cast calipers, natural finish
    m.add('seat', '#141414', roughness=0.8)
    m.add('grip', '#1a1a1a', roughness=0.9)
    m.add('chain', '#5a5a5c', metallic=1.0, roughness=0.45)
    m.add('mirror', '#aab4be', metallic=1.0, roughness=0.04)
    m.add('plate', '#e8e8e2', roughness=0.5)
    m.add('fork', '#d6d8dc', metallic=1.0, roughness=0.1)            # fork outer tubes
    m.add('fork_low', '#2c2d30', metallic=1.0, roughness=0.3)        # inner tubes, axle brackets
    m.add('logo', '#c9ccd0', metallic=1.0, roughness=0.2)
    # rider
    m.add('rider_suit', '#1e1f23', roughness=0.55)
    m.add('rider_trim', '#55c81e', roughness=0.5)
    m.add('rider_glove', '#141414', roughness=0.6)
    m.add('rider_boot', '#18181a', roughness=0.5)
    m.add('rider_slider', '#5a5c60', roughness=0.4)
    m.add('rider_helmet', '#1c1d20', roughness=0.25, coat=0.6)
    m.add('rider_helmet2', '#55c81e', roughness=0.3, coat=0.5)
    m.add('visor', '#0c0e12', metallic=0.3, roughness=0.05)
    return m


def _f(pts):
    return K.Pchip(pts)


# ---------------------------------------------------------------- fairing (upper cowl and side panels)
# sections: top edge (the cockpit/screen opening), the upper crease, widest, lower crease, bottom centre (cut away)
X_TOP = _f([(0.868, 0.0), (0.80, 0.025), (0.70, 0.075), (0.66, 0.092), (0.55, 0.15), (0.45, 0.19), (0.35, 0.20), (0.25, 0.20)])
Y_TOP = _f([(0.868, 0.796), (0.80, 0.845), (0.763, 0.877), (0.66, 0.925), (0.55, 0.95), (0.45, 0.95), (0.35, 0.90),
            (0.25, 0.85)])
WU = _f([(0.868, 0.03), (0.84, 0.09), (0.80, 0.14), (0.70, 0.18), (0.60, 0.20), (0.50, 0.215), (0.40, 0.22), (0.25, 0.215)])
YU = _f([(0.868, 0.79), (0.84, 0.79), (0.80, 0.80), (0.70, 0.82), (0.60, 0.83), (0.50, 0.83), (0.40, 0.80), (0.25, 0.76)])
WM = _f([(0.868, 0.06), (0.84, 0.13), (0.80, 0.175), (0.75, 0.195), (0.70, 0.21), (0.60, 0.232), (0.50, 0.245), (0.40, 0.25),
         (0.25, 0.235)])
YM = _f([(0.868, 0.73), (0.84, 0.725), (0.80, 0.72), (0.70, 0.71), (0.60, 0.70), (0.50, 0.68), (0.40, 0.66), (0.25, 0.64)])
WL = _f([(0.868, 0.05), (0.84, 0.11), (0.80, 0.15), (0.70, 0.19), (0.60, 0.215), (0.50, 0.225), (0.40, 0.225), (0.25, 0.22)])
YL = _f([(0.868, 0.66), (0.84, 0.655), (0.80, 0.64), (0.70, 0.60), (0.60, 0.55), (0.50, 0.48), (0.40, 0.42), (0.25, 0.38)])
YB = _f([(0.868, 0.64), (0.80, 0.62), (0.70, 0.58), (0.60, 0.52), (0.50, 0.40), (0.40, 0.33), (0.25, 0.30)])

# side outlines (z, y), measured on r01 (panel lines back-projected onto x = -0.22, nose points onto x = -0.16).
# The side fairing is layered: the upper cowl with the nose, the middle "wing" panel standing proud (pointed rear tip
# at z 0.26), the lower panel (vertical rear edge at z 0.36); a dark recess shows between the layers.
OUTLINE = [(0.78, 0.625), (0.79, 0.645), (0.815, 0.69), (0.845, 0.745), (0.872, 0.80), (0.82, 0.842), (0.763, 0.877), (0.66, 0.925),
           (0.56, 0.95), (0.505, 0.955), (0.498, 0.90), (0.502, 0.835), (0.50, 0.80), (0.417, 0.766), (0.346, 0.741),
           (0.263, 0.706), (0.30, 0.697), (0.356, 0.692), (0.358, 0.648), (0.36, 0.51), (0.361, 0.37), (0.40, 0.40),
           (0.48, 0.45), (0.56, 0.51), (0.644, 0.565), (0.70, 0.60), (0.76, 0.625)]
UPPER = [(0.78, 0.625), (0.79, 0.645), (0.815, 0.69), (0.845, 0.745), (0.872, 0.80), (0.82, 0.842), (0.763, 0.877), (0.66, 0.925),
         (0.56, 0.95), (0.505, 0.955), (0.498, 0.90), (0.502, 0.835), (0.505, 0.826), (0.567, 0.818), (0.653, 0.80),
         (0.715, 0.79), (0.753, 0.785), (0.768, 0.76), (0.775, 0.70), (0.775, 0.64), (0.775, 0.62)]
MID = [(0.505, 0.80), (0.621, 0.785), (0.716, 0.772), (0.761, 0.749), (0.70, 0.72), (0.644, 0.696), (0.524, 0.688),
       (0.421, 0.685), (0.30, 0.697), (0.263, 0.706), (0.346, 0.741), (0.417, 0.766)]
LOW = [(0.358, 0.648), (0.507, 0.611), (0.601, 0.607), (0.70, 0.612), (0.775, 0.624), (0.76, 0.62), (0.70, 0.60),
       (0.644, 0.565), (0.56, 0.51), (0.48, 0.45), (0.40, 0.40), (0.361, 0.37), (0.36, 0.51)]
BASE = [(0.77, 0.80), (0.502, 0.835), (0.50, 0.80), (0.417, 0.766), (0.346, 0.741), (0.263, 0.706), (0.30, 0.697),
        (0.356, 0.692), (0.358, 0.648), (0.36, 0.51), (0.361, 0.37), (0.40, 0.40), (0.48, 0.45), (0.56, 0.51),
        (0.644, 0.565), (0.70, 0.60), (0.76, 0.625), (0.77, 0.63)]


def section(z, s=1.0):
    return [(X_TOP(z) * s, Y_TOP(z)), (WU(z) * s, YU(z)), (WM(z) * s, YM(z)), (WL(z) * s, YL(z)), (0.0, YB(z))]


def section_mid(z, s=1.0):
    """the proud middle panel: a ridge across it (r01: the bright upper facet over the darker lower one)"""
    ridge = ((K.lerp(WU(z), WM(z), 0.4) + 0.028) * s, K.lerp(YU(z), YM(z), 0.4))
    return [(X_TOP(z) * s, Y_TOP(z)), (WU(z) * s, YU(z)), ridge, (WM(z) * s, YM(z)), (WL(z) * s, YL(z)), (0.0, YB(z))]


def section_low(z, s=1.0):
    """the lower panel: proud along a crease a third of the way down, tucked in below it (r07: a bright crease
    over a dark, inward-sloping lower face)"""
    crease = ((WM(z) + 0.012) * s, K.lerp(YM(z), YL(z), 0.35))
    return [(X_TOP(z) * s, Y_TOP(z)), (WU(z) * s, YU(z)), (WM(z) * s, YM(z)), crease, ((WL(z) - 0.03) * s, YL(z)),
            (0.0, YB(z))]


CAMBER = 0.02    # each pressed face between two creases bows out by up to 20 mm (r01/r02: the highlights run curved)


def _panel(name, outline, z0, z1, n, scale, mat, sec=None):
    p = K.Part(name)
    zs = list(np.linspace(z0, z1, n))
    sec = sec or section
    P.hull(p, zs, lambda z: sec(z, scale), mat=mat, crease_per=4, camber=CAMBER)
    P.clip_outline(p, list(p.bm.faces), outline)
    P.delete_outside(p, outline)
    return p


def fairing(m):
    """the upper cowl with the nose (holds the front openings), the proud middle panel, the lower panel, and the dark
    skin under them that shows in the gaps"""
    p = K.Part('fairing')
    zs = list(np.linspace(0.875, 0.70, 10)) + list(np.linspace(0.68, 0.49, 7))
    P.hull(p, zs, section, mat='paint', crease_per=4, camber=CAMBER)
    P.clip_outline(p, list(p.bm.faces), UPPER)
    P.delete_outside(p, UPPER)
    surf = cut_front_openings(p)
    mid = _panel('fairing_mid', MID, 0.78, 0.25, 20, 1.065, 'paint', sec=section_mid)
    low = _panel('fairing_low', LOW, 0.81, 0.35, 16, 1.0, 'paint', sec=section_low)
    base = _panel('fairing_base', BASE, 0.78, 0.25, 18, 0.95, 'trim')
    inner = [inner_skin(q, 0.004) for q in (p, mid, low)]
    # the panels' turned-in edges: each layer shows its thickness and a shadow line where it laps the next
    edges = K.Part('fairing_edges')

    def not_nose(c):
        return not (c[2] > 0.78 and 0.6 < c[1] < 0.78 and abs(c[0]) < 0.19)
    for q in (p, mid, low):
        P.edge_return(edges, q, 0.012, 'trim', keep=not_nose)
    return [p, mid, low, base, edges] + inner, surf


def inner_skin(p, t):
    """a dark inner face for a single-sided panel (seen through the cockpit and the openings)"""
    q = K.Part(p.name + '_inner')
    for f in p.bm.faces:
        pts = []
        for v in reversed(f.verts):
            g = np.array(K.G(v.co)) - np.array(K.G(v.normal)) * t
            pts.append(tuple(g))
        q.face(pts, 'trim')
    return q


def screen(m):
    """the narrow, tall screen: its base along the cowl's top edge, its top a point at the centre"""
    p = K.Part('screen')
    base = [(0.185, 0.952, 0.47), (0.16, 0.948, 0.53), (0.12, 0.938, 0.60), (0.06, 0.928, 0.645), (0.0, 0.924, 0.665)]
    top = [(0.13, 1.03, 0.385), (0.10, 1.07, 0.395), (0.065, 1.10, 0.41), (0.03, 1.122, 0.42), (0.0, 1.134, 0.426)]
    b = K.catmull(base + [(-x, y, z) for x, y, z in reversed(base[:-1])], 17)
    t = K.catmull(top + [(-x, y, z) for x, y, z in reversed(top[:-1])], 17)
    rows = []
    for k in range(6):
        s = k / 5
        row = []
        for (bx, by, bz), (tx, ty, tz) in zip(b, t):
            q = np.array([K.lerp(bx, tx, s), K.lerp(by, ty, s), K.lerp(bz, tz, s)])
            q[1] += 0.015 * math.sin(math.pi * s) * (1 - abs(bx) / 0.22)
            q[2] += 0.02 * math.sin(math.pi * s) * (1 - abs(bx) / 0.22)
            row.append(tuple(q))
        rows.append(row)
    faces, vs = p.grid(rows, 'glass')
    P._orient(p, faces, (0, 1, 1), lambda f: True)
    q = inner_skin(p, 0.003)
    for f in q.bm.faces:
        f.material_index = q.slot('glass')
    return p, q


# ---------------------------------------------------------------- the nose: head lamp, ram-air intake, vent
# front projection outlines (x, y); the lamp housing is a flattened hexagon, the intake (bike's left, +x) and the vent
# (right) are slanted trapezoids beside it (measured on r02)
LAMP_HOUSING = [(-0.05, 0.738), (-0.028, 0.765), (0.028, 0.765), (0.05, 0.738), (0.042, 0.69), (0.022, 0.664),
                (-0.022, 0.664), (-0.042, 0.69)]
LAMP_C = (0.0, 0.716)
LAMP_R = 0.029                    # lens radius incl. the chrome ring (r02: 0.0285)
INTAKE = [(0.064, 0.768), (0.165, 0.748), (0.175, 0.683), (0.07, 0.692)]
# position lamps (fangs) at the housing's lower corners, bike's left; mirrored for the right (r02 back-projection)
FANG = [(x - 0.0045, y - 0.006) for x, y in [(0.066, 0.692), (0.040, 0.700), (0.054, 0.626), (0.074, 0.664)]]
VENT = [(-x, y) for x, y in INTAKE]


def cut_front_openings(p):
    import bmesh
    surf = K.Surface(K.bvh_of_parts([p]))
    for poly in (LAMP_HOUSING, INTAKE, VENT):
        K.cut_outline(p.bm, poly, 'front', side=1, min_facing=0.05)
        dead = K.faces_in(p.bm, poly, 'front', side=1, min_facing=0.05)
        bmesh.ops.delete(p.bm, geom=dead, context='FACES')
    return surf


def nose(m, surf):
    """recessed housings behind the three openings, the projector lens, the position lamps (fangs), the louvres, the
    intake mesh, our own round emblem under the beak"""
    p = K.Part('nose')
    lamp = K.Part('headlamp')

    def on(x, y, depth=0.0):
        h = surf.hit((x, y, 1.5), (0, 0, -1))
        if h is None:
            return np.array([x, y, 0.84 - depth])
        return np.array(h[0]) - np.array([0, 0, depth])

    def recess(poly, depth, mat, back_mat, bezel=None):
        rim = [on(x, y, -0.001) for x, y in K.resample(poly, 24, closed=True)]
        if bezel:
            # a bright bezel round the opening: the rim pulled 4 mm in and 3 mm back
            c2 = np.mean(np.array(rim), axis=0)
            inner = [q + (c2 - q) * np.array([1, 1, 0]) * min(0.3, 0.004 / max(1e-6, np.linalg.norm((c2 - q)[:2])))
                     - np.array([0, 0, 0.003]) for q in rim]
            p.loft([rim, inner], bezel, closed=True, flip=True)
            rim = inner
        back = [q - np.array([0, 0, depth]) for q in rim]
        p.loft([rim, back], mat, closed=True, flip=True)
        c = np.mean(np.array(back), axis=0)
        p.loft([back, [tuple(c)] * len(back)], back_mat, closed=True, flip=True)
        return rim, back

    recess(LAMP_HOUSING, 0.03, 'housing', 'housing', bezel='chrome')
    recess(INTAKE, 0.09, 'trim', 'mesh')
    rim, back = recess(VENT, 0.05, 'trim', 'trim')
    # louvres across the vent: four slats sloping down to the front
    ys = [y for _, y in VENT]
    for k in range(4):
        y = K.lerp(min(ys), max(ys), (k + 0.6) / 4.4)
        xa, xb = -0.068, -0.168
        za = on(xa, y)[2] - 0.006
        zb = on(xb, y)[2] - 0.006
        p.obox('trim', ((xa + xb) / 2, y, (za + zb) / 2 - 0.01), (abs(xb - xa), 0.004, 0.035),
               axes=((1, 0, (za - zb) / abs(xb - xa)), (0, 0.97, 0.25), (0, -0.25, 0.97)), bevel=0.001)
    # the projector lens: a disc facing forward, a little behind the housing's rim
    c0 = on(LAMP_C[0], LAMP_C[1]) - np.array([0, 0, 0.012])
    ring = [(c0[0] + LAMP_R * math.cos(2 * math.pi * i / 32), c0[1] + LAMP_R * math.sin(2 * math.pi * i / 32), c0[2])
            for i in range(32)]
    rows = [[tuple(c0)] * 32, ring]
    faces, vs = lamp.grid(rows, 'headlight', closed_u=True, flip=True)
    uvmap = {}
    for j, row in enumerate(vs):
        for i, v in enumerate(row):
            g = np.array(K.G(v.co))
            uvmap[v] = (0.8 * (0.5 + (g[0] - c0[0]) / LAMP_R * 0.43), 0.5 + (g[1] - c0[1]) / LAMP_R * 0.43)
    for f in faces:
        for lp in f.loops:
            lp[lamp.uv].uv = uvmap[lp.vert]
    # position lamps: two fangs hanging at the housing's lower corners, clear lenses (the texture's right strip)
    for sgn in (1, -1):
        q = [on(sgn * x, y, 0.002 if k < 2 else -0.008) for k, (x, y) in enumerate(FANG)]
        uvs = [(0.96, 0.9), (0.84, 0.9), (0.9, 0.1), (0.98, 0.5)]
        order = [0, 1, 2, 3] if sgn > 0 else [3, 2, 1, 0]
        f = lamp.face([tuple(q[i]) for i in order], 'headlight', smooth=False)
        if f is not None:
            for lp, i in zip(f.loops, order):
                lp[lamp.uv].uv = uvs[i]
        # the fang's black back
        back = [tuple(v - [0, 0, 0.018]) for v in q]
        p.face([back[i] for i in order[::-1]], 'trim', smooth=False)
    # emblem: our own simple round badge (a ring and a bar) under the beak
    e = on(0.0, 0.79, -0.004)
    p.cylinder('chrome', tuple(e - [0, 0, 0.006]), tuple(e + [0, 0, 0.002]), 0.019, seg=20)
    p.cylinder('trim', tuple(e + [0, 0, 0.0015]), tuple(e + [0, 0, 0.0025]), 0.014, seg=20)
    p.obox('chrome', tuple(e + [0, 0, 0.003]), (0.022, 0.005, 0.002))
    return p, lamp


def blades(m):
    """the blades standing off the side panels (measured on r01): the front winglet with its green edge, the lower
    blade over the radiator side"""
    p = K.Part('blades')
    for sgn in (1, -1):
        for path, w, h, edge in (
                ([(0.17, 0.709, 0.652), (0.135, 0.685, 0.74), (0.10, 0.657, 0.816)], 0.012, [0.04, 0.03, 0.006], True),
                ([(0.205, 0.554, 0.418), (0.19, 0.556, 0.537), (0.17, 0.565, 0.60)], 0.010, [0.03, 0.02, 0.004], True)):
            pts = [(sgn * x, y, z) for x, y, z in path]
            P.beam_path(p, pts, w, h, 'paint', n=8, r=0.1)
            if edge:
                P.beam_path(p, [(x + sgn * 0.004, y - hh / 2 + 0.003, z) for (x, y, z), hh in zip(pts, h)], 0.006, 0.004,
                            'accent', n=8, r=0.2)
    return p


def mirrors(m):
    p = K.Part('mirrors')
    for sgn in (1, -1):
        base = np.array([sgn * 0.17, 0.90, 0.56])
        head = np.array([sgn * 0.285, 0.93, 0.54])
        # the stay: a flat blade in the body colour, broad where it leaves the cowl (r05)
        P.beam_path(p, [tuple(base), tuple((base + head) / 2 + np.array([0, 0.008, 0])), tuple(head)], [0.075, 0.055, 0.04],
                    0.008, 'paint', n=6, r=0.3)
        c = head + np.array([sgn * 0.035, 0.0, 0.0])
        p.obox('trim', tuple(c), (0.13, 0.06, 0.06), axes=((1, 0, 0.25 * sgn), (0, 1, 0), (-0.25 * sgn, 0, 1)), bevel=0.012)
        p.obox('mirror', tuple(c - np.array([0, 0, 0.031])), (0.11, 0.045, 0.003), axes=((1, 0, 0.25 * sgn), (0, 1, 0), (-0.25 * sgn, 0, 1)))
        # the indicator in the housing's front edge
        p.obox('indicator', tuple(c + np.array([sgn * 0.01, -0.012, 0.031])), (0.09, 0.012, 0.004),
               axes=((1, 0, 0.25 * sgn), (0, 1, 0), (-0.25 * sgn, 0, 1)), bevel=0.002)
    return p


# ---------------------------------------------------------------- tank, seats, tail
T_Z = [0.36, 0.30, 0.16, 0.01, -0.06, -0.11, -0.13]          # tank top and rear edge measured on r01
T_TOP = _f(list(zip(T_Z, [0.92, 0.958, 0.998, 0.99, 0.955, 0.89, 0.82])))
T_BOT = _f(list(zip(T_Z, [0.80, 0.77, 0.74, 0.735, 0.745, 0.76, 0.77])))
T_W = _f(list(zip(T_Z, [0.10, 0.17, 0.205, 0.20, 0.18, 0.15, 0.12])))


def tank_ring(z):
    """an angular tank section: flat top, a chamfered shoulder, the side's crease, the knee recess below it"""
    t, b, w = T_TOP(z), T_BOT(z), T_W(z)
    h = t - b
    half = P.polyline([(0.0, t), (0.42 * w, t - 0.018), (0.8 * w, t - 0.2 * h), (w, t - 0.5 * h), (0.92 * w, b + 0.22 * h),
                       (0.6 * w, b), (0.0, b)], 3)
    return half + [(-x, y) for x, y in reversed(half[1:-1])]


def tank(m):
    p = K.Part('tank')
    rings = [[(x, y, z) for x, y in tank_ring(z)] for z in np.linspace(0.36, -0.13, 18)]
    faces = p.loft(rings, 'paint', closed=True, cap0=True, cap1=True)
    P._orient(p, faces, (1, 0, 0), lambda f: K.G(f.calc_center_median())[0] > 0.02)
    return p


S_Z = [-0.13, -0.20, -0.28, -0.36, -0.42, -0.46]               # seat, seat cowl and tail measured on r01
S_TOP = _f(list(zip(S_Z, [0.822, 0.818, 0.82, 0.83, 0.852, 0.882])))
S_W = _f(list(zip(S_Z, [0.11, 0.125, 0.13, 0.13, 0.12, 0.11])))
PS_Z = [-0.44, -0.48, -0.52, -0.57, -0.62]
PS_TOP = _f(list(zip(PS_Z, [0.925, 0.965, 0.982, 0.98, 0.975])))
TL_Z = [-0.28, -0.33, -0.40, -0.45, -0.52, -0.60, -0.68, -0.75, -0.80]
TL_TOP = _f(list(zip(TL_Z, [0.78, 0.84, 0.885, 0.91, 0.95, 0.975, 0.99, 1.005, 1.018])))
TL_BOT = _f(list(zip(TL_Z, [0.68, 0.70, 0.72, 0.735, 0.76, 0.80, 0.845, 0.895, 0.93])))
TL_W = _f(list(zip(TL_Z, [0.14, 0.14, 0.135, 0.13, 0.12, 0.105, 0.09, 0.075, 0.065])))
TAIL_END = -0.80


def seat_tail(m):
    seat = K.Part('seat')
    zs = list(np.linspace(-0.13, -0.46, 12))
    P.closed_loft(seat, zs, lambda z: P.superellipse(0.0, S_TOP(z) - 0.04, S_W(z), 0.04, 0.03, 2.0, 4.0, n=20), n=20, mat='seat')
    zs = list(np.linspace(-0.44, -0.62, 8))
    P.closed_loft(seat, zs, lambda z: P.superellipse(0.0, PS_TOP(z) - 0.04, 0.10, 0.04, 0.04, 3.0, 4.0, n=20), n=20, mat='seat')
    tail = K.Part('tail')
    zs = list(np.linspace(-0.28, TAIL_END, 24))
    P.closed_loft(tail, zs, lambda z: P.superellipse(0.0, (TL_TOP(z) + TL_BOT(z)) / 2, TL_W(z), (TL_TOP(z) - TL_BOT(z)) / 2,
                                                       (TL_TOP(z) - TL_BOT(z)) / 2, 4.0, 4.0, n=28), n=28, mat='paint')
    # the tail lamp: the LED lens filling the tail's rear face under the tip, facing back (r03)
    lamp = K.Part('taillamp')
    a, b = TL_W(TAIL_END), (TL_TOP(TAIL_END) - TL_BOT(TAIL_END)) / 2
    cy = (TL_TOP(TAIL_END) + TL_BOT(TAIL_END)) / 2
    rows = []
    for j in range(4):
        t = K.lerp(-0.8, 0.75, j / 3)                 # fraction of the half height, bottom to top
        y = cy + b * t
        half = 0.86 * a * max(0.0, 1 - abs(t) ** 4.0) ** (1 / 4.0)
        rows.append([(K.lerp(half, -half, i / 8), y, TAIL_END - 0.0015) for i in range(9)])
    faces, vs = lamp.grid(rows, 'taillight')
    for f in faces:
        for lp in f.loops:
            j = next(jj for jj, row in enumerate(vs) if lp.vert in row)
            lp[lamp.uv].uv = (vs[j].index(lp.vert) / 8, j / 3)
    # licence plate holder: a thin arm from under the tail's tip reaching back, the plate hanging from it, the
    # indicators on short stalks at its sides (as on the stock bike, r07)
    hold = K.Part('plate_holder')
    P.beam_path(hold, [(0.0, 0.93, -0.66), (0.0, 0.905, -0.78), (0.0, 0.875, -0.87)], 0.06, 0.022, 'trim', n=6, r=0.3)
    hold.obox('trim', (0.0, 0.79, -0.885), (0.20, 0.16, 0.02), axes=((1, 0, 0), (0, 0.99, -0.12), (0, 0.12, 0.99)), bevel=0.004)
    hold.obox('plate', (0.0, 0.79, -0.897), (0.18, 0.13, 0.004), axes=((1, 0, 0), (0, 0.99, -0.12), (0, 0.12, 0.99)))
    for sgn in (1, -1):
        hold.tube([(sgn * 0.02, 0.885, -0.83), (sgn * 0.10, 0.885, -0.845)], 0.006, 'trim', seg=6)
        hold.obox('indicator', (sgn * 0.11, 0.885, -0.85), (0.03, 0.022, 0.045), bevel=0.01)
    return seat, tail, lamp, hold


# ---------------------------------------------------------------- frame, swingarm, engine, exhaust

def chassis(m):
    """the green steel trellis (nodes measured on r01), the black subframe, the single-sided swingarm on the left"""
    fr = K.Part('frame')
    r = 0.0135
    for sgn in (1, -1):
        def n(x, y, z):
            return (sgn * x, y, z)
        H1, H2 = n(0.04, 0.90, 0.405), n(0.04, 0.75, 0.47)
        U1, B, L1 = n(0.12, 0.80, 0.21), n(0.13, 0.69, 0.126), n(0.12, 0.62, 0.32)
        A, C, E = n(0.13, 0.661, -0.106), n(0.13, 0.55, -0.128), n(0.13, 0.368, -0.157)
        for a, b in ((H1, U1), (U1, A), (H2, L1), (L1, B), (B, A), (U1, B), (U1, L1), (A, C), (C, E), (B, C), (H1, H2)):
            fr.tube([a, b], r, 'frame', seg=10, cap0=True, cap1=True)
        # the pivot plate
        fr.obox('frame', n(0.13, 0.44, -0.145), (0.02, 0.15, 0.07), bevel=0.01)
    fr.tube([(0.13, 0.661, -0.106), (-0.13, 0.661, -0.106)], r, 'frame', seg=10)
    fr.cylinder('frame', tuple(ST.at_y(0.73)), tuple(ST.at_y(0.92)), 0.032, seg=14)
    sub = K.Part('subframe')
    # the black side covers under the seat, between the frame and the tail (r01, r07)
    prof = [(-0.10, 0.80), (-0.30, 0.79), (-0.44, 0.77), (-0.40, 0.68), (-0.26, 0.58), (-0.12, 0.56)]
    rings = []
    for x in (-0.128, -0.12, 0.12, 0.128):
        k = 0.012 if abs(x) > 0.125 else 0.0
        rings.append([(x, y - k * 0.5, z - k * 0.5) for z, y in K.resample(prof, 24, closed=True)])
    faces = sub.loft(rings, 'trim', closed=True, cap0=True, cap1=True)
    P._orient(sub, faces, (0, 0, -1), lambda f: K.G(f.calc_center_median())[2] < -0.40)
    for sgn in (1, -1):
        P.beam_path(sub, [(sgn * 0.12, 0.66, -0.12), (sgn * 0.10, 0.74, -0.40), (sgn * 0.06, 0.875, -0.60)], 0.02, 0.035,
                    'frame2', n=8)
        P.beam_path(sub, [(sgn * 0.13, 0.45, -0.15), (sgn * 0.11, 0.66, -0.42)], 0.018, 0.025, 'frame2', n=4)
        # rear-set plates and pegs
        sub.obox('frame2', (sgn * 0.165, 0.47, -0.27), (0.008, 0.15, 0.12), axes=((1, 0, 0), (0, 0.9, -0.43), (0, 0.43, 0.9)),
                 bevel=0.004)
        P.peg(sub, (sgn * 0.17, 0.434, -0.274), sgn)
    # single-sided swingarm (left), the hub carrier, the chain and sprocket outboard of it
    sw = K.Part('swingarm')
    P.beam_path(sw, [(0.11, PIVOT[1], PIVOT[2]), (0.12, 0.43, -0.32), (0.125, 0.38, -0.55), (0.12, RR + 0.01, RZ + 0.05)],
                0.06, [0.15, 0.16, 0.13, 0.11], 'arm', n=14, r=0.15)
    P.beam_path(sw, [(-0.11, PIVOT[1], PIVOT[2]), (0.11, PIVOT[1], PIVOT[2])], 0.06, 0.10, 'arm', n=2)
    sw.cylinder('arm', (0.08, RR, RZ), (0.15, RR, RZ), 0.085, seg=24)
    sw.cylinder('frame2', (0.0, 0.38, -0.30), (0.0, 0.62, -0.16), 0.03, seg=10)       # shock
    P.chain(sw, (0.0, 0.33, -0.05), 0.045, (0.0, RR, RZ), 0.10, 0.16)
    P.sprocket(sw, (0, RR, RZ), 0.16, 0.10, teeth=42)
    return fr, sub, sw


def engine(m):
    p = K.Part('engine')
    # crankcase and gearbox: the side profile (z, y) extruded across, its edges chamfered
    prof = K.resample([(0.30, 0.47), (0.30, 0.33), (0.25, 0.23), (0.15, 0.195), (-0.05, 0.205), (-0.115, 0.26),
                       (-0.135, 0.40), (-0.11, 0.50), (0.02, 0.52), (0.18, 0.50)], 40, closed=True)
    cz, cy = np.mean(np.array(prof), axis=0)
    rings = []
    for x, inset in ((-0.19, 0.018), (-0.175, 0.0), (0.175, 0.0), (0.19, 0.018)):
        ring = []
        for z, y in prof:
            d = np.array([cz - z, cy - y]); d = d / max(1e-6, np.linalg.norm(d)) * inset
            ring.append((x, y + d[1], z + d[0]))
        rings.append(ring)
    faces = p.loft(rings, 'engine', closed=True, cap0=True, cap1=True)
    P._orient(p, faces, (0, -1, 0), lambda f: K.G(f.calc_center_median())[1] < 0.22)
    # cylinder bank and head, inclined forwards; cooling fins round the block
    ax = ((1, 0, 0), (0, 0.95, 0.31), (0, -0.31, 0.95))
    p.obox('engine', (0.0, 0.55, 0.28), (0.34, 0.24, 0.20), axes=ax, bevel=0.02)
    p.obox('engine', (0.0, 0.69, 0.33), (0.30, 0.07, 0.17), axes=ax, bevel=0.025)
    up = np.array([0, 0.95, 0.31])
    for k in range(6):
        c = np.array([0.0, 0.55, 0.28]) + up * (-0.09 + 0.034 * k)
        p.obox('engine', tuple(c), (0.355, 0.007, 0.215), axes=ax, bevel=0.002)
    p.obox('engine2', (0.0, 0.735, 0.345), (0.26, 0.02, 0.13), axes=ax, bevel=0.008)          # cam cover rim
    # right side: the clutch casing (a D-shaped black cover) and its round inner cover, centre measured on r01
    cc = np.array([-0.19, 0.50, 0.003])
    D = [(-0.098, 0.565), (-0.06, 0.605), (0.04, 0.605), (0.098, 0.56), (0.112, 0.45), (0.07, 0.39), (-0.06, 0.39),
         (-0.103, 0.445)]
    ring = K.resample(D, 32, closed=True)
    rings = []
    for x, inset in ((-0.17, 0.0), (-0.198, 0.0), (-0.208, 0.012)):
        rr = []
        for z, y in ring:
            d = np.array([cc[2] - z, cc[1] - y]); d = d / max(1e-6, np.linalg.norm(d)) * inset
            rr.append((x, y + d[1], z + d[0]))
        rings.append(rr)
    p.loft(rings, 'engine', closed=True, cap1=True, smooth=False)
    p.revolve('engine3', [(0.072, 0.0), (0.072, 0.007), (0.066, 0.015), (0.046, 0.020), (0.0, 0.021)],
              (-0.207, cc[1], cc[2]), axis=(-1, 0, 0), seg=28)
    for k in range(9):
        t = 2 * math.pi * (k + 0.5) / 9
        q = (-0.207, cc[1] + 0.088 * math.sin(t), cc[2] + 0.088 * math.cos(t))
        if 0.395 < q[1] < 0.60:
            p.cylinder('chrome', q, (q[0] - 0.006, q[1], q[2]), 0.0055, seg=8)
    # the oil filler cap and the small pulser cover ahead of the clutch (r01)
    p.cylinder('trim', (-0.19, 0.544, 0.082), (-0.212, 0.544, 0.082), 0.018, seg=12)
    p.revolve('engine3', [(0.034, 0.0), (0.034, 0.006), (0.026, 0.011), (0.0, 0.012)], (-0.19, 0.444, 0.125), axis=(-1, 0, 0), seg=20)
    # left side: the generator cover and the sprocket cover
    p.revolve('engine3', [(0.085, 0.0), (0.085, 0.008), (0.075, 0.018), (0.05, 0.024), (0.0, 0.025)], (0.19, 0.46, 0.02),
              axis=(1, 0, 0), seg=28)
    p.obox('engine', (0.19, 0.36, -0.07), (0.03, 0.12, 0.13), bevel=0.02)
    # the supercharger behind the cylinders: its housing across the engine, the drive casing on the right in
    # natural aluminium with a round badge (r01: z -0.07..0.09, y 0.57..0.66), its intake on the left fed by the duct
    p.cylinder('engine2', (-0.16, 0.62, -0.005), (0.10, 0.62, -0.005), 0.075, seg=24)
    p.obox('engine2', (-0.175, 0.615, 0.01), (0.04, 0.09, 0.16), bevel=0.018)
    p.cylinder('chrome', (-0.195, 0.629, -0.008), (-0.20, 0.629, -0.008), 0.031, seg=20)
    p.cylinder('trim', (-0.199, 0.629, -0.008), (-0.2015, 0.629, -0.008), 0.025, seg=20)
    p.revolve('engine2', [(0.075, 0.0), (0.07, 0.02), (0.06, 0.035), (0.06, 0.05)], (0.10, 0.62, -0.005), axis=(1, 0, 0), seg=24)
    # the ram-air duct: from the intake in the nose along the left side, under the tank, into the supercharger;
    # glossy black, seen between the side panel and the trellis (r04, r05)
    P.beam_path(p, [(0.08, 0.715, 0.70), (0.13, 0.69, 0.55), (0.175, 0.645, 0.38), (0.18, 0.615, 0.22), (0.165, 0.60, 0.10),
                    (0.15, 0.61, 0.0)], [0.06, 0.07, 0.07, 0.068, 0.062, 0.06], [0.085, 0.095, 0.10, 0.095, 0.09, 0.09],
                'duct', n=14, r=0.35)
    p.box('radiator', -0.20, 0.20, 0.40, 0.68, 0.40, 0.44, bevel=0.01)
    return p


def exhaust(m):
    p = K.Part('headers')
    for i, x in enumerate((-0.105, -0.035, 0.035, 0.105)):
        P.pipe(p, [(x, 0.52, 0.40), (x * 0.9, 0.42, 0.425), (x * 0.7, 0.28, 0.385), (x * 0.4, 0.195, 0.27), (x * 0.15, 0.175, 0.13)],
               0.021, mat='chamber', seg=10, cap1=False)
    p.box('chamber', -0.09, 0.09, 0.14, 0.23, -0.10, 0.15, bevel=0.04)           # collector under the engine
    P.pipe(p, [(-0.03, 0.17, -0.10), (-0.09, 0.20, -0.18), (-0.15, 0.28, -0.22), (-0.165, 0.34, -0.25)],
           [(0, 0.045), (1, 0.05)], mat='chamber', seg=12, cap1=False)
    sil = K.Part('exhaust_silencer')
    # the stock can (r07): a large angular canister in dark stainless, rising to just behind the rear axle, its
    # outlet end slanted; a black heat shield over its outer face and top
    # outline fitted on r07's solved camera (tools canfit: 12.6 px rms against a 10 px camera)
    A, Bend = np.array([-0.17, 0.34, -0.235]), np.array([-0.215, 0.585, -0.79])
    end = P.chamfered_can(sil, tuple(A), tuple(Bend), [0.055, 0.068, 0.074, 0.072, 0.066, 0.06],
                          [0.07, 0.10, 0.12, 0.126, 0.124, 0.117], 'exhaust', slant=-0.02, n=8)
    c = np.mean(np.array(end), axis=0)
    d = K.unit(Bend - A)
    sil.cylinder('trim', tuple(c - d * 0.01), tuple(c + d * 0.006), 0.03, seg=14)
    sil.cylinder('chrome', tuple(c + d * 0.004), tuple(c + d * 0.008), 0.034, seg=14, cap=False)
    # the black heat shield: a plate over the outer face's upper half and a strip along the top
    P.beam_path(sil, [(-0.240, 0.375, -0.27), (-0.269, 0.455, -0.45), (-0.278, 0.52, -0.60)], 0.012, [0.12, 0.17, 0.16],
                'trim', n=8, r=0.2)
    P.beam_path(sil, [(-0.20, 0.44, -0.28), (-0.215, 0.573, -0.50), (-0.22, 0.62, -0.60)], 0.075, 0.012, 'trim', n=8, r=0.2)
    return p, sil


# ---------------------------------------------------------------- steering assembly, wheels

def steer_parts(m):
    p = K.Part('forks')
    legx = 0.105
    top_t = (0.93 - RF) / ST.axis[1]
    bot_t = (0.77 - RF) / ST.axis[1]
    for sgn in (1, -1):
        x = sgn * legx
        # inverted fork: the thin inner tube below, the thick outer tube above
        p.cylinder('fork_low', tuple(ST.leg_point(-0.03, x)), tuple(ST.leg_point(0.06, x)), 0.032, seg=14)
        p.cylinder('fork_low', tuple(ST.leg_point(0.04, x)), tuple(ST.leg_point(0.25, x)), 0.0215, seg=14)
        p.cylinder('fork', tuple(ST.leg_point(0.23, x)), tuple(ST.leg_point(top_t + 0.03, x)), 0.029, seg=16)
    for t, th in ((bot_t, 0.035), (top_t, 0.022)):
        c = ST.leg_point(t, 0) - ST.fwd * ST.offset * 0.5
        p.obox('frame2', tuple(c), (2 * legx + 0.08, th, 0.08), axes=((1, 0, 0), ST.axis, ST.fwd), bevel=0.012)
    p.cylinder('chrome', tuple(ST.at_y(0.94)), tuple(ST.at_y(0.955)), 0.02, seg=10)
    ST.top_leg = [ST.leg_point(top_t - 0.04, legx), ST.leg_point(top_t - 0.04, -legx)]
    grips = [(0.33, 0.905, 0.335), (-0.33, 0.905, 0.335)]
    for sgn, g in ((1, grips[0]), (-1, grips[1])):
        P.clip_on(p, ST, sgn, g, mat_bar='trim', reservoir=True)
    # front mudguard: a short black shell
    mg = K.Part('mudguard')
    rows = []
    rad = RF + 0.02
    for k in range(11):
        a = math.radians(-30 + 85 * k / 10)
        d = np.array([0, math.cos(a), math.sin(a)])
        w = 0.07
        rows.append([tuple(ST.axle + d * (rad - 0.03) + np.array([w, 0, 0])), tuple(ST.axle + d * rad + np.array([w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad + 0.008)), tuple(ST.axle + d * rad + np.array([-w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad - 0.03) + np.array([-w, 0, 0]))])
    faces, _ = mg.grid(rows, 'trim')
    P._orient(mg, faces, (0, 1, 0), lambda f: K.G(f.calc_center_median())[1] > ST.axle[1] + 0.2)
    mgi = inner_skin(mg, 0.003)
    return p, mg, mgi, grips


def stripe(part, centre, width, r):
    """the green pin stripe on a rim's outer lip (both sides)"""
    c = np.array(centre, float)
    for sgn in (1, -1):
        prof = [(r - 0.006, sgn * (width / 2 + 0.0015)), (r, sgn * (width / 2 + 0.0015))]
        part.revolve('rim_stripe', prof if sgn > 0 else prof[::-1], c, axis=(1, 0, 0), seg=48, smooth=False)


def wheels(m, wf_node, sf_node, wr_node, sr_node):
    sp = K.Part('wheel_front')
    P.tyre(sp, ST.axle, RF, WF)
    P.rim(sp, ST.axle, 0.085, spokes=5, style='split', spoke_w=0.02, spoke_depth=0.028)
    stripe(sp, ST.axle, 0.085, P.BEAD_R + 0.006)
    for sgn in (1, -1):
        P.floating_disc(sp, ST.axle, sgn * 0.07, 0.165, 0.12, arms=5, bobbins=10, hub=(0.042, 0.068), hub_bolts=6)
    cal = K.Part('calipers_front')
    for sgn in (1, -1):
        P.caliper(cal, ST.axle, sgn * 0.07, 0.165, 140, side=sgn, size=(0.036, 0.13, 0.055))
    sp.build(sf_node, m.mats, sharp=35)
    cal.build(wf_node, m.mats)
    rp = K.Part('wheel_rear')
    rc = np.array([0.0, RR, RZ])
    P.tyre(rp, rc, RR, WR)
    P.rim(rp, rc, 0.15, spokes=5, style='split', spoke_w=0.024, spoke_depth=0.034)
    stripe(rp, rc, 0.15, P.BEAD_R + 0.006)
    rp.cylinder('chrome', (-0.085, RR, RZ), (-0.10, RR, RZ), 0.03, seg=12)      # the hub nut on the open right side
    P.floating_disc(rp, rc, 0.07, 0.125, 0.09, carrier='disc_carrier', arms=5, bobbins=0, hub=(0.04, 0.06), hub_bolts=5,
                    bolt='chrome', wave=0.03)
    cal = K.Part('caliper_rear')
    P.caliper(cal, rc, 0.07, 0.125, 250, side=1)
    rp.build(sr_node, m.mats, sharp=35)
    cal.build(wr_node, m.mats)


# ---------------------------------------------------------------- livery and badges

def livery(fa, tk):
    """the green pin stripe along the upper cowl's crease, our own KAWASAKI lettering on the tank sides"""
    d = K.Part('decals')
    sf = K.Surface(K.bvh_of_parts([fa]))
    st = K.Surface(K.bvh_of_parts([tk]))
    for side in (-1, 1):
        mir = (lambda s, t: (s, t)) if side < 0 else (lambda s, t: (-s, t))
        # the green line from the screen's base down the cowl to the beak
        a, b = mir(0.62, 0.905), mir(0.84, 0.80)
        dv = np.array(b) - np.array(a)
        nv = np.array([-dv[1], dv[0]]) / np.linalg.norm(dv) * 0.003
        quad = [tuple(np.array(a) - nv), tuple(np.array(b) - nv), tuple(np.array(b) + nv), tuple(np.array(a) + nv)]
        L.decal_polys(d, sf, [quad], side, 'accent')
        L.text(d, st, 'KAWASAKI', mir(0.10, 0.93), (1.0, 0.0), 0.022, 'logo', side, stroke=0.16, gap=0.2, shear=0.25)
    return d


# ---------------------------------------------------------------- the whole bike

def build(o=None):
    o = o or {}
    m = materials(o.get('paint', '#64686e'))
    root = K.node('ninjah2')
    body = K.node('body', root)
    steer = K.node('steer', body, origin=tuple(ST.head), y_axis=tuple(ST.axis))
    wf = K.node('wheel_f', steer, origin=tuple(ST.axle))
    sf = K.node('spin_f', wf, origin=tuple(ST.axle))
    wr = K.node('wheel_r', body, origin=(0, RR, RZ))
    sr = K.node('spin_r', wr, origin=(0, RR, RZ))
    fparts, surf = fairing(m)
    fa = fparts[0]
    ns, hl = nose(m, surf)
    sc, sci = screen(m)
    bl = blades(m)
    mi = mirrors(m)
    tk = tank(m)
    seat, tail, tlamp, hold = seat_tail(m)
    fr, sub, sw = chassis(m)
    en = engine(m)
    hd, sil = exhaust(m)
    forks, mg, mgi, grips = steer_parts(m)
    dec = livery(fa, tk)
    for part in fparts + [ns, bl]:
        part.build(body, m.mats, sharp=18)          # keep the bodywork's creases crisp
    for part in [hl, sc, sci, mi, tk, seat, tail, tlamp, hold, fr, sub, sw, en, hd, dec]:
        part.build(body, m.mats, sharp=35)
    sil.build(body, m.mats, sharp=40)
    for part in (forks, mg, mgi):
        part.build(steer, m.mats, sharp=40)
    wheels(m, wf, sf, wr, sr)
    if o.get('rider', True):
        rn = K.node('rider', body)
        rp = K.Part('rider_body')
        info = RD.build(rp, {'hip': (0, 0.905, -0.28), 'grips': grips, 'pegs': [(0.17, 0.434, -0.274), (-0.17, 0.434, -0.274)],
                             'reach': 0.48, 'look': 0.10})
        print('RIDER lean', round(info['lean_deg'], 1))
        rp.build(rn, m.mats, sharp=60)
    import bpy
    bpy.context.view_layer.update()
    K.report(root)
    lamps_ = K.lamp_report(root)
    return root, m.mats, lamps_


if __name__ == '__main__':
    import bike_main
    bike_main.run(build)
