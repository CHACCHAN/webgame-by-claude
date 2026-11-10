"""
Suzuki GSX1300R Hayabusa (first generation, 1999-2007) for TOUGE NOCTURNE, game id `hayabusa`: the round-nosed
full fairing with the stacked head lamps and the ram-air scoops in its flanks, the humped tail, the aluminium twin-spar
frame and swingarm, the two big silencers. Our own model, built from the published figures (length 2140, width 740,
height 1155, wheelbase 1485, seat 805 mm; 120/70ZR17, 190/50ZR17; caster 24.2°, trail 98 mm) and measurements of
photos (fitdata/hayabusa); no outside model, no photo pixels. The 隼 character, SUZUKI and GSX1300R are our own plain
block drawings, not the maker's logos. Paint: the 2000 Pearl Suzuki Deep Blue (paint) over Metallic Sonic Silver
(accent). Run with Blender 5.x (see bike_main.py for the options):

  blender -t 6 -b --factory-startup --python tools/blender/bikes/hayabusa.py -- --out <file.glb> [--render <dir> ...]
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

WB = 1.485
RF, RR = 0.300, 0.311           # 120/70ZR17, 190/50ZR17
WF, WR = 0.120, 0.190
FZ, RZ = WB / 2, -WB / 2
ST = P.Steering(WB, RF, 24.2, 0.098, 0.88)
PIVOT = np.array([0.0, 0.432, -0.193])     # swingarm pivot (r01)


def materials(paint='#18266e'):
    m = K.Materials()
    m.add('paint', paint, metallic=0.45, roughness=0.22, coat=1.0)      # pearl deep blue
    m.add('accent', '#b8bcc2', metallic=0.8, roughness=0.3, coat=0.8)   # metallic sonic silver
    m.add('logo', '#f2f2ee', roughness=0.3)                             # white lettering
    m.add('logo2', '#2f62c4', roughness=0.3)                            # the light blue 隼
    m.add('logo3', '#1a2a6c', roughness=0.3)                            # navy lettering
    m.add('logo_red', '#c81a1e', roughness=0.3)
    m.add('glass', '#3c4652', metallic=0.3, roughness=0.03)             # smoked screen
    m.add('trim', '#151517', roughness=0.6)
    m.add('frame', '#b9bdc2', metallic=1.0, roughness=0.34)   # silver-painted aluminium twin spar and swingarm
    m.add('frame2', '#9ea2a7', metallic=1.0, roughness=0.42)  # cast aluminium: yokes, rear sets, rails
    m.add('frame3', '#202124', metallic=0.5, roughness=0.5)          # black seat rails (dark under the tail on r01)
    m.add('engine', '#26282b', metallic=0.5, roughness=0.45, coat=0.3)   # black-painted cases (dark, not mirror-grey)
    m.add('engine2', '#a9adb2', metallic=1.0, roughness=0.3)  # the silver clutch and generator covers, fin edges
    m.add('exhaust', '#d3d6da', metallic=1.0, roughness=0.15)  # silencers: polished
    m.add('link', '#b9bcc0', metallic=1.0, roughness=0.12)     # stock link pipes: polished stainless (r04)
    m.add('chamber', '#8c7d68', metallic=1.0, roughness=0.32)  # header pipes: heat-tinted stainless
    m.add('chrome', '#e2e5e9', metallic=1.0, roughness=0.06)
    m.add('housing', '#2a2c30', metallic=1.0, roughness=0.25)
    import bpy
    lens = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'hayabusa', 'headlight.png'), check_existing=True)
    m.add('headlight', '#ffffff', roughness=0.1, image=lens)   # clear cover over the two chrome bowls
    tail = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'hayabusa', 'taillight.png'), check_existing=True)
    m.add('taillight', '#ffffff', roughness=0.2, image=tail)
    m.add('indicator', '#e0861c', roughness=0.2)              # amber lenses (2000 model)
    m.add('mesh', '#1c1d20', metallic=0.6, roughness=0.6)     # the ram-air intake mesh
    m.add('tire', '#141415', roughness=0.85)
    m.add('rim', '#1a1a1d', metallic=0.3, roughness=0.4, coat=0.3)   # black three-spoke wheels
    dimg = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'hayabusa', 'disc.png'), check_existing=True)
    m.add('disc', '#8a8d90', metallic=1.0, roughness=0.35, image=dimg)  # drilled steel rings (the texture: holes)
    m.add('disc_steel', '#8a8d90', metallic=1.0, roughness=0.35)    # the one-piece rear disc's arms
    m.add('carrier', '#c3a35a', metallic=1.0, roughness=0.3)  # gold disc carriers
    m.add('brake', '#b39c6a', metallic=1.0, roughness=0.36)   # gold six-piston calipers
    m.add('seat', '#161616', roughness=0.75)
    m.add('grip', '#1a1a1a', roughness=0.9)
    m.add('chain', '#5a5a5c', metallic=1.0, roughness=0.45)
    m.add('mirror', '#aab4be', metallic=1.0, roughness=0.04)
    m.add('radiator', '#232426', metallic=1.0, roughness=0.6)
    m.add('plate', '#e8e8e2', roughness=0.5)
    m.add('fork', '#dcdee1', metallic=1.0, roughness=0.07)   # chrome fork tubes
    m.add('fork_low', '#a3a6ab', metallic=1.0, roughness=0.34)  # cast aluminium sliders
    m.add('fork_cap', '#c2a560', metallic=1.0, roughness=0.3)   # gold adjuster caps
    # rider
    m.add('rider_suit', '#1d2230', roughness=0.55)
    m.add('rider_trim', '#c9ccd2', roughness=0.5)
    m.add('rider_glove', '#141414', roughness=0.6)
    m.add('rider_boot', '#18181a', roughness=0.5)
    m.add('rider_slider', '#5a5c60', roughness=0.4)
    m.add('rider_helmet', '#e9e9e6', roughness=0.25, coat=0.6)
    m.add('rider_helmet2', '#24357e', roughness=0.3, coat=0.5)
    m.add('visor', '#0c0e12', metallic=0.3, roughness=0.05)
    return m


# ---------------------------------------------------------------- fairing

def _f(pts):
    return K.Pchip(pts)


# sections (measured on r01 at the centre line and the flanks): top edge (the nose's crest, then the screen's base and
# the cockpit rim, then the panel's top edge under the tank); widest (WM at YM); lower turn; bottom centre
X_TOP = _f([(0.952, 0.0), (0.67, 0.0), (0.62, 0.08), (0.56, 0.15), (0.50, 0.19), (0.45, 0.205), (0.40, 0.205), (0.36, 0.195),
            (0.20, 0.185), (0.0, 0.175), (-0.17, 0.165)])
Y_TOP = _f([(0.952, 0.764), (0.935, 0.81), (0.90, 0.866), (0.85, 0.926), (0.80, 0.974), (0.74, 1.022), (0.67, 1.06),
            (0.62, 1.055), (0.56, 1.03), (0.50, 1.00), (0.45, 0.97), (0.40, 0.93), (0.36, 0.885), (0.20, 0.81), (0.0, 0.725),
            (-0.17, 0.64)])
WM = _f([(0.952, 0.012), (0.935, 0.05), (0.90, 0.105), (0.85, 0.145), (0.80, 0.18), (0.74, 0.205), (0.68, 0.225), (0.60, 0.245),
         (0.50, 0.262), (0.40, 0.272), (0.30, 0.275), (0.15, 0.268), (0.0, 0.255), (-0.17, 0.235)])
YM = _f([(0.952, 0.762), (0.90, 0.775), (0.80, 0.80), (0.70, 0.80), (0.60, 0.74), (0.50, 0.64), (0.40, 0.55), (0.30, 0.48),
         (0.15, 0.44), (0.0, 0.42), (-0.17, 0.42)])
WL = _f([(0.952, 0.010), (0.90, 0.075), (0.80, 0.13), (0.70, 0.18), (0.60, 0.21), (0.50, 0.23), (0.40, 0.235), (0.30, 0.23),
         (0.15, 0.22), (0.0, 0.205), (-0.17, 0.19)])
YL = _f([(0.952, 0.745), (0.90, 0.71), (0.80, 0.665), (0.70, 0.625), (0.60, 0.575), (0.50, 0.45), (0.40, 0.24), (0.30, 0.205),
         (0.15, 0.195), (0.0, 0.195), (-0.17, 0.20)])
YB = _f([(0.952, 0.735), (0.90, 0.695), (0.80, 0.655), (0.70, 0.625), (0.60, 0.575), (0.52, 0.40), (0.45, 0.20), (0.40, 0.155),
         (0.30, 0.150), (0.15, 0.152), (0.0, 0.16), (-0.17, 0.168)])

# the fairing's side outline (z, y): chin, nose crest (kept loose), cockpit rim, the panel's top edge under the tank,
# the lower cowl's rear edge, the belly, the front edge behind the wheel (r01)
OUTLINE = [(0.93, 0.716), (0.952, 0.745), (0.962, 0.765), (0.95, 0.82), (0.90, 0.88), (0.82, 0.975), (0.74, 1.03), (0.67, 1.07),
           (0.58, 1.08), (0.50, 1.06), (0.45, 1.02),
           (0.43, 0.975), (0.395, 0.915), (0.36, 0.875),
           (0.20, 0.815), (0.0, 0.73), (-0.04, 0.705),
           (-0.045, 0.565), (-0.09, 0.534), (-0.154, 0.459), (-0.165, 0.34), (-0.143, 0.294), (-0.10, 0.20), (-0.086, 0.15),
           (0.20, 0.15), (0.40, 0.15),
           (0.445, 0.20), (0.47, 0.30), (0.50, 0.40), (0.55, 0.48), (0.61, 0.55), (0.68, 0.60), (0.76, 0.635), (0.86, 0.672)]


def section(z):
    xt, yt = X_TOP(z), Y_TOP(z)
    wm, ym = WM(z), YM(z)
    sh = (max(xt + 0.012, 0.8 * wm), K.lerp(yt, ym, 0.45))
    return [(xt, yt), sh, (wm, ym), (WL(z), YL(z)), (0.0, YB(z))]


def inner_skin(p, t, keep=None):
    """a dark inner face for a single-sided panel (seen through the cockpit and the openings)"""
    q = K.Part(p.name + '_inner')
    for f in p.bm.faces:
        if keep is not None and not keep(K.G(f.calc_center_median())):
            continue
        pts = []
        for v in reversed(f.verts):
            g = np.array(K.G(v.co)) - np.array(K.G(v.normal)) * t
            pts.append(tuple(g))
        q.face(pts, 'trim')
    return q


# front projection (x, y) of the head lamp cover: a tall lens, broad round the upper lamp, waisted, narrower round the
# lower one (r03, r05); side projection (z, y) of the ram-air scoops in the nose's flanks and the vents (r01)
LAMP = [(0.0, 0.776), (0.028, 0.779), (0.047, 0.79), (0.057, 0.808), (0.059, 0.83), (0.056, 0.853), (0.064, 0.872),
        (0.074, 0.895), (0.078, 0.92), (0.075, 0.945), (0.064, 0.966), (0.042, 0.98), (0.0, 0.985)]
LAMP = LAMP + [(-x, y) for x, y in reversed(LAMP[1:-1])]
SCOOP = [(0.665, 0.815), (0.675, 0.865), (0.71, 0.895), (0.765, 0.905), (0.815, 0.88), (0.86, 0.825), (0.885, 0.775),
         (0.865, 0.745), (0.82, 0.725), (0.76, 0.72), (0.70, 0.74), (0.672, 0.775)]
INDICATOR = [(0.68, 0.868), (0.682, 0.878), (0.693, 0.881), (0.715, 0.872), (0.734, 0.847), (0.747, 0.822), (0.755, 0.794),
             (0.754, 0.775), (0.747, 0.76), (0.734, 0.763), (0.715, 0.778), (0.699, 0.802), (0.69, 0.827), (0.683, 0.849)]
def _grow(poly, k):
    c = np.mean(np.array(poly), axis=0)
    return [tuple(c + (np.array(q) - c) * k) for q in poly]


INDICATOR = _grow(INDICATOR, 1.06)
SIDE_VENT = [(0.43, 0.735), (0.445, 0.62), (0.43, 0.47), (0.395, 0.465), (0.375, 0.58), (0.355, 0.70), (0.335, 0.728)]
LOW_VENT = [(0.212, 0.43), (0.236, 0.43), (0.276, 0.33), (0.27, 0.262), (0.25, 0.262), (0.252, 0.33)]
LOW_SLOT = [(0.02, 0.232), (0.10, 0.232), (0.11, 0.214), (0.03, 0.212)]


def fairing(m):
    p = K.Part('fairing')
    zs = list(np.linspace(0.952, 0.80, 8)) + list(np.linspace(0.78, -0.17, 27))
    P.hull(p, zs, section, n_half=14, mat='paint')
    P.clip_outline(p, list(p.bm.faces), OUTLINE)
    P.delete_outside(p, OUTLINE)
    surf = K.Surface(K.bvh_of_parts([p]))
    cut_openings(p)
    # the inner skin only where the inside shows: the nose and cockpit (through the openings) and the rear edges
    inner = inner_skin(p, 0.004, keep=lambda c: c[2] > 0.30 or c[2] < 0.02)
    return p, inner, surf


def cut_openings(p):
    import bmesh
    K.cut_outline(p.bm, LAMP, 'front', side=1, min_facing=0.05)
    dead = K.faces_in(p.bm, LAMP, 'front', side=1, min_facing=0.05)
    bmesh.ops.delete(p.bm, geom=dead, context='FACES')
    for sgn in (1, -1):
        for poly in (SCOOP, SIDE_VENT, LOW_VENT, LOW_SLOT):
            K.cut_outline(p.bm, poly, 'side', side=sgn, min_facing=0.05)
            dead = K.faces_in(p.bm, poly, 'side', side=sgn, min_facing=0.05)
            bmesh.ops.delete(p.bm, geom=dead, context='FACES')


def nose(m, surf):
    """the head lamp behind its clear cover (two chrome bowls in the texture) in a dark housing, the scoops with the
    indicator lens in front of the intake mesh, the dark vents"""
    p = K.Part('nose')
    lamp = K.Part('headlamp')

    def on_front(x, y, depth=0.0):
        h = surf.hit((x, y, 1.6), (0, 0, -1))
        if h is None:
            return np.array([x, y, 0.9 - depth])
        q, n = h
        if n[2] < 0:
            n = -n
        return q - n * depth

    def on_side(sgn, z, y, depth=0.0):
        h = surf.hit((sgn * 0.6, y, z), (-sgn, 0, 0))
        if h is None:
            return np.array([sgn * 0.15, y, z])
        q, n = h
        if n[0] * sgn < 0:
            n = -n
        return q - n * depth

    # head lamp: housing walls from the cut edge back, the lens a little behind the cowl surface
    ring = K.resample(LAMP, 40, closed=True)
    rim = [on_front(x, y, -0.0005) for x, y in ring]
    back = [on_front(x, y, 0.012) for x, y in ring]
    p.loft([rim, back], 'housing', closed=True, flip=True)
    rows = []
    nv = 8
    for j in range(nv + 1):
        y = K.lerp(0.776, 0.985, j / nv)
        # the lens's half width at this height (from the outline)
        xs = [abs(x) for x, yy in ring if abs(yy - y) < 0.02] or [0.01]
        hw = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
                hw = max(hw, abs(K.lerp(x0, x1, (y - y0) / (y1 - y0))))
        hw = max(hw, 0.004)
        rows.append([tuple(on_front(K.lerp(-hw, hw, i / 12), y, 0.006)) for i in range(13)])
    faces, vs = lamp.grid(rows, 'headlight', smooth=True)
    P._orient(lamp, faces, (0, 0, 1), lambda f: True)
    for f in faces:
        for lp in f.loops:
            g = K.G(lp.vert.co)
            lp[lamp.uv].uv = ((g[0] + 0.08) / 0.16, (g[1] - 0.775) / 0.215)
    # scoops: the opening's walls into the nose, the intake mesh at the back, the indicator lens in its rear end
    for sgn in (1, -1):
        sring = K.resample(SCOOP, 32, closed=True)
        rim = [on_side(sgn, z, y, -0.0005) for z, y in sring]
        back = [q - np.array([sgn * 0.045, 0, 0]) for q in rim]
        p.loft([rim, back], 'trim', closed=True, flip=sgn > 0)
        c = np.mean(np.array(back), axis=0)
        p.loft([back, [tuple(c)] * len(back)], 'mesh', closed=True, flip=sgn > 0)
        iring = K.resample(INDICATOR, 24, closed=True)
        ip = [on_side(sgn, z, y, 0.006) for z, y in iring]
        ci = np.mean(np.array(ip), axis=0) + np.array([sgn * 0.004, 0, 0])
        p.loft([ip, [tuple(ci)] * len(ip)], 'indicator', closed=True, flip=sgn < 0)
        p.loft([ip, [tuple(q - np.array([sgn * 0.03, 0, 0])) for q in ip]], 'trim', closed=True, flip=sgn > 0)
        # vents: dark recesses
        for poly, depth in ((SIDE_VENT, 0.04), (LOW_VENT, 0.03), (LOW_SLOT, 0.02)):
            vr = K.resample(poly, 20, closed=True)
            rim = [on_side(sgn, z, y, -0.0005) for z, y in vr]
            back = [q - np.array([sgn * depth, 0, 0]) for q in rim]
            p.loft([rim, back], 'trim', closed=True, flip=sgn > 0)
            c = np.mean(np.array(back), axis=0)
            p.loft([back, [tuple(c)] * len(back)], 'trim', closed=True, flip=sgn > 0)
    return p, lamp


def screen(m):
    p = K.Part('screen')
    base = [(0.205, 0.975, 0.45), (0.19, 1.003, 0.50), (0.15, 1.034, 0.56), (0.08, 1.054, 0.62), (0.0, 1.06, 0.665)]
    top = [(0.15, 1.095, 0.405), (0.13, 1.128, 0.41), (0.09, 1.148, 0.418), (0.045, 1.158, 0.424), (0.0, 1.16, 0.428)]
    b = K.catmull(base + [(-x, y, z) for x, y, z in reversed(base[:-1])], 17)
    t = K.catmull(top + [(-x, y, z) for x, y, z in reversed(top[:-1])], 17)
    rows = []
    for k in range(7):
        s = k / 6
        row = []
        for (bx, by, bz), (tx, ty, tz) in zip(b, t):
            q = np.array([K.lerp(bx, tx, s), K.lerp(by, ty, s), K.lerp(bz, tz, s)])
            q[1] += 0.03 * math.sin(math.pi * s) * (1 - abs(bx) / 0.26)      # the bubble
            q[2] += 0.025 * math.sin(math.pi * s) * (1 - abs(bx) / 0.26)
            row.append(tuple(q))
        rows.append(row)
    faces, vs = p.grid(rows, 'glass')
    P._orient(p, faces, (0, 1, 1), lambda f: True)
    q = inner_skin(p, 0.003)
    for f in q.bm.faces:
        f.material_index = q.slot('glass')
    return p, q


def cockpit(surf):
    """what the open cockpit shows: the panels' inward lip, the instrument panel with its four dials"""
    p = K.Part('cockpit')
    for sgn in (1, -1):
        rows = [[], []]
        for z in np.linspace(0.44, 0.37, 6):
            y = Y_TOP(z) - 0.006
            h = surf.hit((0.0, y, z), (sgn * 1.0, 0.0, 0.0))
            xo = abs(h[0][0]) if h is not None else 0.2
            rows[0].append((sgn * (xo - 0.002), y, z))
            rows[1].append((sgn * (xo - 0.05), y - 0.008, z))
        p.grid(rows, 'trim', flip=sgn < 0)
    p.obox('trim', (0.0, 0.975, 0.45), (0.30, 0.13, 0.03), axes=((1, 0, 0), (0, 0.5, -0.86), (0, 0.86, 0.5)), bevel=0.01)
    for x in (-0.09, -0.03, 0.03, 0.09):
        c = np.array([x, 0.99, 0.46])
        nrm = np.array([0.0, 0.86, -0.5])
        p.cylinder('trim', tuple(c - nrm * 0.012), tuple(c + nrm * 0.004), 0.032, seg=14)
        p.cylinder('plate', tuple(c + nrm * 0.004), tuple(c + nrm * 0.006), 0.026, seg=14)
    return p


def mirrors(m):
    p = K.Part('mirrors')
    for sgn in (1, -1):
        P.mirror(p, (sgn * 0.195, 0.99, 0.50), (sgn * 0.255, 1.08, 0.50), size=(0.12, 0.07, 0.05), stalk_r=0.011)
    return p


# ---------------------------------------------------------------- livery
# side polygons (z, y), the same on both sides. Measured on r01: the photo's blue areas (by colour) traced and picked
# onto the model through the solved camera (fitdata/hayabusa: livery_img.json → livery_zy.json), then cleaned by hand
# where the vent's shadow and the 隼 graphic broke them. The fairing is silver with the nose blue round the scoops and
# a blue band from the knee down to the front of the side panel; a black duct strip under the tank; the tank silver
# on top at the front, blue behind the diagonal
ALL = [(1.3, 1.4), (1.3, -0.1), (-0.4, -0.1), (-0.4, 1.4)]
NOSE_BLUE = [(0.575, 1.30), (0.555, 0.902), (0.60, 0.865), (0.658, 0.83), (0.72, 0.79), (0.778, 0.759), (0.82, 0.733),
             (0.876, 0.707), (0.92, 0.70), (1.2, 0.69), (1.2, 1.30)]
BAND_BLUE = [(-0.30, 0.56), (-0.07, 0.548), (0.045, 0.51), (0.148, 0.486), (0.26, 0.463), (0.372, 0.441), (0.454, 0.457),
             (0.49, 0.50), (0.44, 0.555), (0.42, 0.59), (0.38, 0.61), (0.345, 0.66), (0.314, 0.707), (0.28, 0.73),
             (0.245, 0.766), (0.167, 0.744), (-0.006, 0.618), (-0.07, 0.59), (-0.30, 0.60)]
DUCT = [(0.40, 0.92), (0.36, 0.855), (0.0, 0.684), (-0.06, 0.66), (-0.06, 0.71), (0.0, 0.725), (0.36, 0.89)]
TANK_BLUE = [(0.142, 0.803), (0.04, 0.887), (-0.058, 0.948), (-0.14, 1.06), (-0.35, 1.06), (-0.35, 0.60), (-0.211, 0.67),
             (-0.075, 0.734), (0.019, 0.738), (0.106, 0.787)]


def livery(fa, tk, tail):
    K.paint_region(fa, ALL, 'side', 'accent', side=-1, min_facing=-1.01, cut=False)
    for poly, mat in ((NOSE_BLUE, 'paint'), (BAND_BLUE, 'paint'), (DUCT, 'trim')):
        K.paint_region(fa, poly, 'side', mat, side=-1, min_facing=-1.01)
    K.paint_region(tk, ALL, 'side', 'accent', side=-1, min_facing=-1.01, cut=False)
    K.paint_region(tk, TANK_BLUE, 'side', 'paint', side=-1, min_facing=-1.01)
    d = K.Part('decals')
    sf = K.Surface(K.bvh_of_parts([fa]))
    st = K.Surface(K.bvh_of_parts([tk]))
    sl = K.Surface(K.bvh_of_parts([tail]))
    for side in (-1, 1):
        mir = (lambda s, t: (s, t)) if side < 0 else (lambda s, t: (-s, t))
        k = -side
        # the 隼 over the band's front end (r01: centre z 0.55, y 0.63), HAYABUSA under it, SUZUKI on the tank's
        # silver front, GSX1300R on the tail; the italics lean forwards on both sides
        L.text(d, sf, '隼', mir(0.55, 0.632), (1.0, 0.0), 0.125, 'logo2', side, stroke=0.13, shear=0.22 * k)
        L.text(d, sf, 'HAYABUSA', mir(0.50, 0.556), (1.0, 0.0), 0.014, 'logo3', side, stroke=0.18, gap=0.2, shear=0.25 * k,
               condense=0.85, min_seg=0.2)
        L.text(d, st, 'SUZUKI', mir(0.17, 0.925), (1.0, -0.33 * k), 0.032, 'logo3', side, stroke=0.2, gap=0.18, min_seg=0.18)
        c, dv, h = np.array(mir(-0.80, 0.868)), np.array([1.0, -0.19 * k]), 0.026
        w = L.text(d, sl, 'GSX1300', tuple(c), tuple(dv), h, 'logo', side, stroke=0.2, gap=0.16, shear=0.2 * k, min_seg=0.2)
        cr = c + dv / np.linalg.norm(dv) * (w / 2 + 0.36 * h + 0.33 * h)
        L.text(d, sl, 'R', tuple(cr), tuple(dv), h, 'logo_red', side, stroke=0.2, shear=0.2 * k, min_seg=0.2)
    return d


# ---------------------------------------------------------------- tank, seat, tail
T_Z = [0.36, 0.30, 0.20, 0.10, 0.00, -0.10, -0.17, -0.24]
T_TOP = _f(list(zip(T_Z, [0.93, 0.962, 0.985, 0.995, 0.998, 0.962, 0.91, 0.84])))
T_BOT = _f(list(zip(T_Z, [0.86, 0.80, 0.75, 0.72, 0.70, 0.69, 0.69, 0.70])))
T_W = _f(list(zip(T_Z, [0.16, 0.19, 0.205, 0.207, 0.20, 0.185, 0.165, 0.14])))


def tank(m):
    p = K.Part('tank')
    zs = list(np.linspace(0.36, -0.24, 22))
    P.closed_loft(p, zs, lambda z: P.superellipse(0.0, (T_TOP(z) + T_BOT(z)) / 2, T_W(z), (T_TOP(z) - T_BOT(z)) / 2,
                                                   (T_TOP(z) - T_BOT(z)) / 2, 2.4, 3.5, n=28), n=28, mat='paint')
    return p


S_Z = [-0.22, -0.26, -0.33, -0.40, -0.46, -0.52, -0.56]
S_TOP = _f(list(zip(S_Z, [0.794, 0.796, 0.816, 0.83, 0.842, 0.852, 0.858])))
S_W = _f(list(zip(S_Z, [0.12, 0.14, 0.15, 0.15, 0.145, 0.135, 0.12])))
PS_Z = [-0.55, -0.585, -0.65, -0.75, -0.84, -0.88]
PS_TOP = _f(list(zip(PS_Z, [0.885, 0.912, 0.925, 0.937, 0.942, 0.935])))
TL_Z = [-0.24, -0.32, -0.42, -0.52, -0.62, -0.72, -0.82, -0.90, -0.96, -1.00, -1.035]
TL_TOP = _f(list(zip(TL_Z, [0.76, 0.79, 0.81, 0.83, 0.86, 0.885, 0.905, 0.94, 0.937, 0.912, 0.876])))
TL_BOT = _f(list(zip(TL_Z, [0.625, 0.632, 0.64, 0.645, 0.65, 0.66, 0.668, 0.675, 0.69, 0.725, 0.778])))
TL_W = _f(list(zip(TL_Z, [0.17, 0.16, 0.155, 0.15, 0.145, 0.135, 0.125, 0.115, 0.10, 0.085, 0.068])))
TAIL_END = -1.02
LAMP_TIP = -1.074                 # the tail lamp stands out of the tail's end under the hump (r01: z -1.02 .. -1.07)


def tail_section(z):
    # a rounded hump over sides that draw in towards the bottom
    return P.superellipse(0.0, (TL_TOP(z) + TL_BOT(z)) / 2 + 0.01, TL_W(z), (TL_TOP(z) - TL_BOT(z)) / 2 - 0.01,
                          (TL_TOP(z) - TL_BOT(z)) / 2 + 0.01, 2.3, 2.6, n=28, x_scale_bot=0.78)


def seat_tail(m):
    seat = K.Part('seat')
    zs = list(np.linspace(-0.22, -0.56, 12))
    P.closed_loft(seat, zs, lambda z: P.superellipse(0.0, S_TOP(z) - 0.045, S_W(z), 0.045, 0.03, 2.6, 4.0, n=20), n=20, mat='seat')
    zs = list(np.linspace(-0.55, -0.88, 10))
    P.closed_loft(seat, zs, lambda z: P.superellipse(0.0, PS_TOP(z) - 0.04, 0.115, 0.04, 0.03, 2.6, 4.0, n=20), n=20, mat='seat')
    tail = K.Part('tail')
    zs = list(np.linspace(-0.24, TAIL_END, 28))
    P.closed_loft(tail, zs, tail_section, n=28, mat='paint', cap1=False)
    # the tail lamp: a rounded red lens standing out of the tail's end below the hump (traced on r01)
    lamp = K.Part('taillamp')
    zs = list(np.linspace(TAIL_END + 0.006, LAMP_TIP, 5))

    def lamp_section(z):
        t = max(0.0, (z - TAIL_END) / (LAMP_TIP - TAIL_END))
        a = K.lerp(0.072, 0.034, t ** 1.6)
        return P.superellipse(0.0, 0.834 - 0.004 * t, a, K.lerp(0.032, 0.024, t), K.lerp(0.032, 0.022, t), 3.0, 3.0, n=24)
    P.closed_loft(lamp, zs, lamp_section, n=24, mat='taillight')
    for f in lamp.bm.faces:
        for lp in f.loops:
            g = K.G(lp.vert.co)
            lp[lamp.uv].uv = ((g[0] + 0.11) / 0.22, (g[1] - 0.79) / 0.085)
    # plate holder under the tip, the plate, the rear indicators on stalks
    hold = K.Part('plate_holder')
    P.beam_path(hold, [(0.0, 0.69, -0.90), (0.0, 0.665, -0.98), (0.0, 0.635, -1.03)], 0.09, 0.02, 'trim', n=6, r=0.3)
    hold.obox('trim', (0.0, 0.565, -1.05), (0.21, 0.15, 0.02), axes=((1, 0, 0), (0, 0.97, -0.24), (0, 0.24, 0.97)), bevel=0.004)
    hold.obox('plate', (0.0, 0.565, -1.062), (0.18, 0.125, 0.004), axes=((1, 0, 0), (0, 0.97, -0.24), (0, 0.24, 0.97)))
    for sgn in (1, -1):
        hold.tube([(sgn * 0.03, 0.70, -0.97), (sgn * 0.11, 0.715, -0.98)], 0.006, 'trim', seg=6)
        hold.obox('indicator', (sgn * 0.12, 0.715, -0.985), (0.03, 0.026, 0.05), bevel=0.011)
    # the black hugger over the rear tyre
    P.beam_path(hold, [(0.0, 0.66, -0.36), (0.0, 0.64, -0.52), (0.0, 0.66, -0.62)], 0.12, 0.012, 'trim', n=6, r=0.3)
    return seat, tail, lamp, hold


# ---------------------------------------------------------------- frame, swingarm, engine, exhaust

FRAME_PLATE = [(-0.376, 0.718), (-0.277, 0.724), (-0.269, 0.67), (-0.245, 0.617), (-0.199, 0.603), (-0.138, 0.612),
               (-0.092, 0.597), (-0.13, 0.536), (-0.144, 0.482), (-0.136, 0.399), (-0.15, 0.353), (-0.203, 0.338),
               (-0.256, 0.36), (-0.273, 0.458), (-0.282, 0.533), (-0.306, 0.594), (-0.344, 0.654), (-0.376, 0.699)]


REARSET = [(-0.391, 0.538), (-0.381, 0.545), (-0.297, 0.526), (-0.287, 0.513), (-0.263, 0.476), (-0.246, 0.443),
           (-0.275, 0.412), (-0.299, 0.415), (-0.309, 0.446), (-0.318, 0.462), (-0.369, 0.464), (-0.387, 0.474), (-0.392, 0.501)]


def _plate(p, outline, sgn, x0, x1, inset, mat, n):
    # a cast plate: the (z, y) outline extruded across x0..x1 with a chamfer of `inset` on the outer face
    ring = K.resample(outline, n, closed=True)
    cz, cy = np.mean(np.array(ring), axis=0)
    rings = []
    for x, ins in ((x0, 0.0), (x1 - inset, 0.0), (x1, inset)):
        rr = []
        for z, y in ring:
            d = np.array([cz - z, cy - y]); d = d / max(1e-6, np.linalg.norm(d)) * ins
            rr.append((sgn * x, y + d[1], z + d[0]))
        rings.append(rr)
    faces = p.loft(rings, mat, closed=True, cap0=True, cap1=True, smooth=False)
    P._orient(p, faces, (sgn, 0, 0), lambda f: abs(K.G(f.calc_center_median())[0]) > x1 - 0.002)


def chassis(m):
    p = K.Part('frame')
    for sgn in (1, -1):
        # the twin spar from the head stock round the engine to the pivot plates (visible between the tank, the
        # panels and the lower cowl)
        P.beam_path(p, [(sgn * 0.07, 0.84, 0.44), (sgn * 0.15, 0.79, 0.32), (sgn * 0.165, 0.71, 0.06), (sgn * 0.16, 0.66, -0.08),
                        (sgn * 0.158, 0.615, -0.14)], 0.04, [0.07, 0.11, 0.13, 0.13, 0.12], 'frame', n=8, r=0.12)
        # the cast pivot section: one silver plate from under the tank down round the swingarm pivot and up back to the
        # seat rails (outline measured on r01, back-projected onto its outer face)
        _plate(p, FRAME_PLATE, sgn, 0.145, 0.171, 0.007, 'frame', 34)
        for (z, y), r, mat in (((-0.13, 0.539), 0.013, 'chrome'), ((-0.237, 0.591), 0.014, 'trim')):
            p.cylinder(mat, (sgn * 0.166, y, z), (sgn * 0.175, y, z), r, seg=10)
        # seat rails from the plate's upper arm
        P.beam_path(p, [(sgn * 0.13, 0.71, -0.36), (sgn * 0.11, 0.75, -0.55), (sgn * 0.07, 0.80, -0.90)], 0.022, 0.03, 'frame3', n=8)
        P.beam_path(p, [(sgn * 0.14, 0.48, -0.22), (sgn * 0.11, 0.66, -0.48)], 0.02, 0.022, 'frame3', n=4)
        # the rear-set plates (cast, silver, traced on r01) with their two slots, and pegs; pillion pegs on their own hangers
        _plate(p, REARSET, sgn, 0.168, 0.18, 0.004, 'frame2', 22)
        for (z, y) in ((-0.367, 0.504), (-0.331, 0.495)):
            p.obox('trim', (sgn * 0.1805, y, z), (0.002, 0.026, 0.011), axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)), bevel=0.004)
        for (z, y) in ((-0.302, 0.515), (-0.308, 0.458)):
            p.cylinder('chrome', (sgn * 0.178, y, z), (sgn * 0.186, y, z), 0.009, seg=8)
        P.peg(p, (sgn * 0.17, 0.452, -0.35), sgn, hanger=False)
        p.obox('frame2', (sgn * 0.15, 0.56, -0.52), (0.01, 0.12, 0.08), axes=((1, 0, 0), (0, 0.8, -0.6), (0, 0.6, 0.8)), bevel=0.004)
        P.peg(p, (sgn * 0.16, 0.53, -0.56), sgn, length=0.06)
    p.cylinder('frame', tuple(ST.at_y(0.70)), tuple(ST.at_y(0.88)), 0.034, seg=14)
    for sgn in (1, -1):
        p.cylinder('chrome', (sgn * 0.155, PIVOT[1], PIVOT[2]), (sgn * 0.172, PIVOT[1], PIVOT[2]), 0.016, seg=10)
    # swingarm: box-section arms with a brace under each, the axle blocks
    sw = K.Part('swingarm')
    for sgn in (1, -1):
        P.beam_path(sw, [(sgn * 0.125, PIVOT[1], PIVOT[2]), (sgn * 0.13, 0.40, -0.45), (sgn * 0.125, RR + 0.01, RZ + 0.04)], 0.045,
                    [0.10, 0.085, 0.06], 'frame', n=10, r=0.2)
        P.beam_path(sw, [(sgn * 0.13, 0.37, -0.25), (sgn * 0.13, 0.285, -0.50), (sgn * 0.125, 0.29, -0.68)], 0.03, 0.03,
                    'frame', n=8, r=0.3)
        sw.obox('frame2', (sgn * 0.125, RR, RZ), (0.035, 0.05, 0.08), bevel=0.008)
    P.beam_path(sw, [(0.12, 0.42, -0.25), (-0.12, 0.42, -0.25)], 0.04, 0.06, 'frame', n=2)
    sw.cylinder('engine', (0.0, 0.40, -0.28), (0.0, 0.64, -0.17), 0.028, seg=10)
    P.chain(sw, (0.0, 0.36, -0.08), 0.045, (0.0, RR, RZ), 0.11, 0.105)
    P.sprocket(sw, (0, RR, RZ), 0.105, 0.11, teeth=42)
    return p, sw


def engine(m):
    p = K.Part('engine')
    # the inline four: crankcase and gearbox, the block and head inclined forwards, the side covers
    p.box('engine', -0.16, 0.16, 0.20, 0.52, -0.16, 0.26, bevel=0.03)
    p.obox('engine', (0.0, 0.62, 0.24), (0.36, 0.22, 0.21), axes=((1, 0, 0), (0, 0.96, 0.28), (0, -0.28, 0.96)), bevel=0.02)
    p.obox('engine', (0.0, 0.76, 0.29), (0.33, 0.08, 0.20), axes=((1, 0, 0), (0, 0.96, 0.28), (0, -0.28, 0.96)), bevel=0.025)
    # cooling fins round the block: their polished edges show in the gap under the fairing
    up = np.array([0, 0.96, 0.28])
    for k in range(6):
        c = np.array([0.0, 0.62, 0.24]) + up * (-0.085 + 0.032 * k)
        p.obox('engine', tuple(c), (0.372, 0.006, 0.222), axes=((1, 0, 0), (0, 0.96, 0.28), (0, -0.28, 0.96)), bevel=0.002)
        p.obox('engine2', tuple(c + np.array([-0.187, 0, 0])), (0.002, 0.006, 0.222),
               axes=((1, 0, 0), (0, 0.96, 0.28), (0, -0.28, 0.96)))
    # the silver clutch cover (right) and generator cover (left): domed, with bolts round the rim
    for sgn, c, r in ((-1, (0.16, 0.40, -0.07), 0.105), (1, (0.16, 0.38, 0.12), 0.085)):
        x0 = sgn * c[0]
        p.revolve('engine2', [(r, 0.0), (r, 0.008), (r - 0.008, 0.02), (r * 0.6, 0.03), (0.0, 0.032)], (x0, c[1], c[2]),
                  axis=(sgn, 0, 0), seg=28)
        for k in range(8):
            t = 2 * math.pi * (k + 0.5) / 8
            q = (x0 + sgn * 0.012, c[1] + (r - 0.012) * math.sin(t), c[2] + (r - 0.012) * math.cos(t))
            p.cylinder('chrome', q, (q[0] + sgn * 0.006, q[1], q[2]), 0.005, seg=6)
    p.box('engine', 0.14, 0.18, 0.30, 0.42, -0.14, -0.04, bevel=0.015)                       # sprocket cover
    p.box('radiator', -0.21, 0.21, 0.42, 0.80, 0.40, 0.44, bevel=0.01)
    return p


def exhaust(m):
    """four headers down the front of the engine and under it to the collector, link pipes up to the two big polished
    silencers either side of the tail (stock; measured on c08/r04: the silencers reach the tail's end)"""
    p = K.Part('headers')
    for x in (-0.12, -0.04, 0.04, 0.12):
        P.pipe(p, [(x, 0.66, 0.40), (x * 0.95, 0.52, 0.46), (x * 0.8, 0.34, 0.43), (x * 0.5, 0.20, 0.30), (x * 0.2, 0.16, 0.12)],
               0.022, mat='chamber', seg=8, n=10, cap1=False)
    p.box('chamber', -0.10, 0.10, 0.155, 0.245, -0.12, 0.10, bevel=0.04)
    for sgn in (1, -1):
        P.pipe(p, [(sgn * 0.05, 0.19, -0.11), (sgn * 0.11, 0.21, -0.26), (sgn * 0.16, 0.31, -0.36), (sgn * 0.18, 0.38, -0.42)],
               [(0, 0.032), (1, 0.036)], mat='link', seg=12, cap1=False)
    sil = K.Part('exhaust_silencers')
    for sgn in (1, -1):
        P.silencer(sil, (sgn * 0.18, 0.37, -0.40), (sgn * 0.205, 0.555, -0.975), 0.064, 0.074, mat='exhaust', cap_mat='chrome',
                   seg=18, oval=1.12, end_cap=0.022, tip_r=0.028)
    return p, sil


# ---------------------------------------------------------------- steering assembly, wheels

def steer_parts(m):
    p = K.Part('forks')
    legx = 0.105
    top_t = (0.925 - RF) / ST.axis[1]
    bot_t = (0.765 - RF) / ST.axis[1]
    for sgn in (1, -1):
        x = sgn * legx
        # conventional fork: the cast slider below, the chrome tube above, the gold cap
        p.cylinder('fork_low', tuple(ST.leg_point(-0.035, x)), tuple(ST.leg_point(0.30, x)), 0.033, seg=14)
        p.cylinder('fork', tuple(ST.leg_point(0.29, x)), tuple(ST.leg_point(top_t + 0.02, x)), 0.0215, seg=14)
        p.cylinder('fork_cap', tuple(ST.leg_point(top_t + 0.02, x)), tuple(ST.leg_point(top_t + 0.04, x)), 0.019, seg=12)
        p.obox('fork_low', tuple(ST.leg_point(0.0, x) + np.array([0, -0.01, -0.01])), (0.05, 0.07, 0.06), bevel=0.012)
    for t, th in ((bot_t, 0.035), (top_t, 0.022)):
        c = ST.leg_point(t, 0) - ST.fwd * ST.offset * 0.5
        p.obox('frame2', tuple(c), (2 * legx + 0.07, th, 0.08), axes=((1, 0, 0), ST.axis, ST.fwd), bevel=0.012)
    p.cylinder('chrome', tuple(ST.at_y(0.94)), tuple(ST.at_y(0.955)), 0.02, seg=10)
    ST.top_leg = [ST.leg_point(top_t + 0.01, legx), ST.leg_point(top_t + 0.01, -legx)]
    grips = [(0.33, 0.95, 0.385), (-0.33, 0.95, 0.385)]
    for sgn, g in ((1, grips[0]), (-1, grips[1])):
        P.clip_on(p, ST, sgn, g, reservoir=True)
    # front mudguard: a long painted shell
    mg = K.Part('mudguard')
    rows = []
    rad = RF + 0.018
    for k in range(13):
        a = math.radians(-40 + 95 * k / 12)
        d = np.array([0, math.cos(a), math.sin(a)])
        w = 0.07 - 0.01 * (k / 12) ** 2
        rows.append([tuple(ST.axle + d * (rad - 0.035) + np.array([w, 0, 0])), tuple(ST.axle + d * rad + np.array([w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad + 0.008)), tuple(ST.axle + d * rad + np.array([-w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad - 0.035) + np.array([-w, 0, 0]))])
    faces, _ = mg.grid(rows, 'paint')
    P._orient(mg, faces, (0, 1, 0), lambda f: K.G(f.calc_center_median())[1] > ST.axle[1] + 0.2)
    mgi = inner_skin(mg, 0.003)
    return p, mg, mgi, grips


def wheels(m, wf_node, sf_node, wr_node, sr_node):
    sp = K.Part('wheel_front')
    P.tyre(sp, ST.axle, RF, WF, seg=32)
    P.rim(sp, ST.axle, 0.085, spokes=3, style='curved', spoke_w=0.05, spoke_depth=0.03, seg=32)
    for sgn in (1, -1):
        # 320 mm floating discs: drilled steel rings on gold carriers (six broad arms: r01 reads as a gold plate
        # with round holes), silver bobbins
        P.floating_disc(sp, ST.axle, sgn * 0.072, 0.16, 0.115, carrier='carrier', bobbin='chrome', bolt='chrome', arms=6,
                        arm_w=0.03, bobbins=8, hub=(0.042, 0.072), hub_bolts=6, wave=0.0, n=40, seg=28)
    cal = K.Part('calipers_front')
    for sgn in (1, -1):
        P.caliper(cal, ST.axle, sgn * 0.072, 0.16, 140, side=sgn, size=(0.036, 0.14, 0.055))
    sp.build(sf_node, m.mats, sharp=35)
    cal.build(wf_node, m.mats)
    rp = K.Part('wheel_rear')
    rc = np.array([0.0, RR, RZ])
    P.tyre(rp, rc, RR, WR, seg=32)
    P.rim(rp, rc, 0.15, spokes=3, style='curved', spoke_w=0.055, spoke_depth=0.034, seg=32)
    P.floating_disc(rp, rc, -0.075, 0.12, 0.085, carrier='disc_steel', bolt='chrome', arms=5, arm_w=0.02, bobbins=0,
                    hub=(0.04, 0.058), hub_bolts=5, wave=0.0, n=40, seg=24)
    cal = K.Part('caliper_rear')
    P.caliper(cal, rc, -0.075, 0.12, 250, side=-1)
    rp.build(sr_node, m.mats, sharp=35)
    cal.build(wr_node, m.mats)


# ---------------------------------------------------------------- the whole bike

def build(o=None):
    o = o or {}
    m = materials(o.get('paint', '#18266e'))
    root = K.node('hayabusa')
    body = K.node('body', root)
    steer = K.node('steer', body, origin=tuple(ST.head), y_axis=tuple(ST.axis))
    wf = K.node('wheel_f', steer, origin=tuple(ST.axle))
    sf = K.node('spin_f', wf, origin=tuple(ST.axle))
    wr = K.node('wheel_r', body, origin=(0, RR, RZ))
    sr = K.node('spin_r', wr, origin=(0, RR, RZ))
    fa, fai, surf = fairing(m)
    ns, hl = nose(m, surf)
    sc, sci = screen(m)
    mi = mirrors(m)
    tk = tank(m)
    seat, tail, tlamp, hold = seat_tail(m)
    fr, sw = chassis(m)
    en = engine(m)
    hd, sil = exhaust(m)
    forks, mg, mgi, grips = steer_parts(m)
    dec = livery(fa, tk, tail)
    cp = cockpit(surf)
    # the bodywork is smooth-shaded: normals split only at real creases (openings and panel edges are free edges anyway)
    for part in (fa, fai, tk, tail):
        part.build(body, m.mats, sharp=75)
    ns.build(body, m.mats, sharp=40)
    for part in (hl, sc, sci, mi, seat, tlamp, hold, fr, sw, en, hd, dec, cp):
        part.build(body, m.mats, sharp=35)
    sil.build(body, m.mats, sharp=40)
    for part in (forks, mg, mgi):
        part.build(steer, m.mats, sharp=40)
    wheels(m, wf, sf, wr, sr)
    if o.get('rider', True):
        rn = K.node('rider', body)
        rp = K.Part('rider_body')
        info = RD.build(rp, {'hip': (0, 0.885, -0.36), 'grips': grips, 'pegs': [(0.17, 0.487, -0.34), (-0.17, 0.487, -0.34)],
                             'reach': 0.50, 'look': 0.10})
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
