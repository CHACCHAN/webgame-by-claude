"""
Honda NSR250R (MC21, 1990-93) for TOUGE NOCTURNE, game id `nsr250r`: the gull-arm two-stroke V-twin replica with the
full fairing, twin head lamps, expansion chambers and two silencers under the tail. Our own model, built from the
published figures (length 1975, width 655, height 1060, wheelbase 1345, seat 775 mm; 110/70R17, 150/60R17; caster
23°15', trail 87 mm) and measurements of photos (fitdata/nsr250r); no outside model, no photo pixels. The HONDA wing
and NSR lettering are our own simple drawings. Run with Blender 5.x (see bike_main.py for the options):

  blender -t 6 -b --factory-startup --python tools/blender/bikes/nsr250r.py -- --out <file.glb> [--render <dir> ...]
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

WB = 1.345
RF, RR = 0.293, 0.306           # 110/70R17, 150/60R17
WF, WR = 0.110, 0.150
FZ, RZ = WB / 2, -WB / 2
ST = P.Steering(WB, RF, 23.25, 0.087, 0.79)
PIVOT = np.array([0.0, 0.365, -0.175])     # swingarm pivot


def materials(paint='#f2f2ee'):
    m = K.Materials()
    m.add('paint', paint, roughness=0.28, coat=0.5)
    m.add('accent', '#d0101c', roughness=0.28, coat=0.5)          # red
    m.add('accent2', '#1b3a9a', roughness=0.28, coat=0.5)         # blue
    m.add('logo', '#f4f4f0', roughness=0.3)                       # white lettering
    m.add('logo2', '#17224a', roughness=0.3)                      # navy lettering
    m.add('glass', '#5d6c79', metallic=0.35, roughness=0.03)      # clear screen, light smoke
    m.add('gauge', '#e6e6de', roughness=0.4)
    m.add('trim', '#141416', roughness=0.6)
    m.add('frame', '#c6c9cd', metallic=1.0, roughness=0.30)     # aluminium twin spar and swingarm (polished/brushed)
    m.add('frame2', '#9da1a6', metallic=1.0, roughness=0.42)    # cast aluminium: yokes, axle blocks, rails
    m.add('engine', '#3c3e42', metallic=1.0, roughness=0.55)    # black-painted cast cases
    m.add('exhaust', '#c9ccd0', metallic=1.0, roughness=0.24)    # silencers: aluminium
    m.add('chamber', '#2c2c2e', metallic=1.0, roughness=0.5)     # expansion chambers: black-coated steel
    m.add('chrome', '#e2e5e9', metallic=1.0, roughness=0.06)    # bolts, levers, bars
    import bpy
    lens = bpy.data.images.load(os.path.join(HERE, '..', 'textures', 'nsr250r', 'headlight.png'), check_existing=True)
    m.add('headlight', '#e8ecf2', metallic=0.0, roughness=0.12, image=lens)   # clear lens over the chrome reflector
    m.add('taillight', '#b0101a', roughness=0.2)
    m.add('indicator', '#e08a1e', roughness=0.2)
    m.add('tire', '#141415', roughness=0.85)
    m.add('rim', '#d01420', metallic=0.3, roughness=0.3, coat=0.3)
    m.add('disc', '#a9abaf', metallic=1.0, roughness=0.28)      # stainless discs
    m.add('brake', '#46484c', metallic=1.0, roughness=0.42)     # calipers
    m.add('seat', '#161616', roughness=0.75)
    m.add('grip', '#1a1a1a', roughness=0.9)
    m.add('chain', '#5a5a5c', metallic=1.0, roughness=0.45)
    m.add('mirror', '#aab4be', metallic=1.0, roughness=0.04)
    m.add('radiator', '#232426', metallic=1.0, roughness=0.6)
    m.add('plate', '#e8e8e2', roughness=0.5)
    m.add('fork', '#dcdee1', metallic=1.0, roughness=0.07)     # chrome fork tubes
    m.add('fork_low', '#9a9da2', metallic=1.0, roughness=0.36)  # cast aluminium sliders
    # rider
    m.add('rider_suit', '#1e1f23', roughness=0.55)
    m.add('rider_trim', '#d8d8d4', roughness=0.5)
    m.add('rider_glove', '#141414', roughness=0.6)
    m.add('rider_boot', '#18181a', roughness=0.5)
    m.add('rider_slider', '#5a5c60', roughness=0.4)
    m.add('rider_helmet', '#e9e9e6', roughness=0.25, coat=0.6)
    m.add('rider_helmet2', '#2a2c33', roughness=0.3, coat=0.5)
    m.add('visor', '#0c0e12', metallic=0.3, roughness=0.05)
    return m


# ---------------------------------------------------------------- fairing

def _f(pts):
    return K.Pchip(pts)


# fairing: top edge (x, y) = the screen's base and the panels' upper edge; widest (WM at YM); lower turn; bottom centre
X_TOP = _f([(0.835, 0.0), (0.715, 0.0), (0.66, 0.07), (0.58, 0.14), (0.50, 0.19), (0.42, 0.22), (0.38, 0.215), (0.30, 0.20),
            (0.15, 0.175), (0.0, 0.16), (-0.26, 0.15)])
Y_TOP = _f([(0.835, 0.70), (0.81, 0.80), (0.78, 0.855), (0.75, 0.895), (0.715, 0.92), (0.66, 0.925), (0.58, 0.935),
            (0.50, 0.945), (0.42, 0.95), (0.38, 0.90), (0.30, 0.82), (0.15, 0.74), (0.0, 0.69), (-0.26, 0.62)])
WM = _f([(0.835, 0.008), (0.82, 0.018), (0.80, 0.042), (0.78, 0.068), (0.76, 0.094), (0.74, 0.12), (0.72, 0.147), (0.70, 0.168), (0.62, 0.20),
         (0.54, 0.215), (0.46, 0.225), (0.40, 0.23), (0.30, 0.232), (0.15, 0.225), (0.0, 0.21), (-0.26, 0.18)])
YM = _f([(0.835, 0.74), (0.75, 0.74), (0.70, 0.73), (0.62, 0.70), (0.50, 0.64), (0.40, 0.56), (0.30, 0.50), (0.15, 0.45),
         (0.0, 0.42), (-0.26, 0.38)])
WL = _f([(0.835, 0.008), (0.75, 0.11), (0.70, 0.15), (0.62, 0.165), (0.50, 0.18), (0.40, 0.185), (0.30, 0.17), (0.15, 0.15),
         (0.0, 0.14), (-0.26, 0.13)])
YL = _f([(0.835, 0.675), (0.75, 0.665), (0.62, 0.65), (0.50, 0.46), (0.40, 0.27), (0.30, 0.20), (0.15, 0.165), (0.0, 0.155),
         (-0.26, 0.16)])
YB = _f([(0.835, 0.66), (0.75, 0.645), (0.62, 0.635), (0.52, 0.56), (0.42, 0.23), (0.33, 0.15), (0.15, 0.13), (0.0, 0.13),
         (-0.26, 0.135)])

# side outline of the fairing (z, y), counter-clockwise from the chin
OUTLINE = [(0.84, 0.655), (0.845, 0.73), (0.82, 0.81), (0.74, 0.93), (0.60, 0.96), (0.47, 0.985),
           # the upper cowl's rear edge (the cockpit opening, measured on r01): from the mirror base down and forwards
           (0.455, 0.955), (0.53, 0.904), (0.587, 0.853), (0.62, 0.788), (0.637, 0.741),
           # the side panel's top edge under the frame spar, its rear edge, the lower cowl's rear edge
           (0.60, 0.736), (0.45, 0.738), (0.30, 0.728), (0.223, 0.712), (0.122, 0.668), (0.0, 0.59), (-0.098, 0.527),
           (-0.09, 0.40), (-0.088, 0.30), (-0.233, 0.27), (-0.245, 0.14),
           (-0.24, 0.12), (0.20, 0.115), (0.33, 0.14), (0.40, 0.23), (0.43, 0.40), (0.47, 0.54),
           (0.52, 0.615), (0.66, 0.638), (0.80, 0.648)]


def section(z):
    xt, yt = X_TOP(z), Y_TOP(z)
    wm, ym = WM(z), YM(z)
    sh = (max(xt + 0.012, 0.8 * wm), K.lerp(yt, ym, 0.45))
    return [(xt, yt), sh, (wm, ym), (WL(z), YL(z)), (0.0, YB(z))]


def fairing(m):
    p = K.Part('fairing')
    zs = list(np.linspace(0.84, 0.70, 8)) + list(np.linspace(0.68, -0.27, 33))
    P.hull(p, zs, section, n_half=14, mat='paint')
    flat_nose(p)
    P.clip_outline(p, list(p.bm.faces), OUTLINE)
    P.delete_outside(p, OUTLINE)
    # the radiator opening behind the front wheel: forward-facing faces low down are the dark inner duct
    for f in p.bm.faces:
        c = K.G(f.calc_center_median())
        n = K.G(f.normal)
        if n[2] > 0.55 and c[1] < 0.60 and c[2] < 0.6:
            f.material_index = p.slot('trim')
    nose = cut_lamp_openings(p)
    inner = inner_skin(p, 0.004)
    return p, inner, nose


def flat_nose(p):
    """the nose round the head lamps is a flat face per side (the lamps' plane, a pointed V in plan view): cowl
    points ahead of that plane are pushed back onto it, which leaves crisp edges where it meets the sides and the top"""
    for v in p.bm.verts:
        x, y, z = K.G(v.co)
        if 0.64 < y < 0.835 and abs(x) < 0.16 and z > 0.60:
            # fade the flattening out above and below the lamp band
            w = K.smoothstep(0.64, 0.69, y) * (1 - K.smoothstep(0.80, 0.835, y))
            zf = lamp_face(max(abs(x), 0.0), y) + 0.004
            if z > zf:
                z = K.lerp(z, zf, w)
                v.co = K.B(x, y, z)
    p.bm.normal_update()


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
    p = K.Part('screen')
    base = [(0.222, 0.952, 0.42), (0.20, 0.94, 0.50), (0.15, 0.932, 0.59), (0.08, 0.925, 0.665), (0.0, 0.919, 0.715)]
    top = [(0.17, 1.02, 0.40), (0.145, 1.05, 0.385), (0.10, 1.075, 0.37), (0.05, 1.087, 0.362), (0.0, 1.09, 0.358)]
    b = K.catmull(base + [(-x, y, z) for x, y, z in reversed(base[:-1])], 17)
    t = K.catmull(top + [(-x, y, z) for x, y, z in reversed(top[:-1])], 17)
    rows = []
    for k in range(6):
        s = k / 5
        row = []
        for (bx, by, bz), (tx, ty, tz) in zip(b, t):
            q = np.array([K.lerp(bx, tx, s), K.lerp(by, ty, s), K.lerp(bz, tz, s)])
            # bowed outwards (bubble) in the middle rows
            q[1] += 0.022 * math.sin(math.pi * s) * (1 - abs(bx) / 0.28)
            q[2] += 0.02 * math.sin(math.pi * s) * (1 - abs(bx) / 0.28)
            row.append(tuple(q))
        rows.append(row)
    faces, vs = p.grid(rows, 'glass')
    P._orient(p, faces, (0, 1, 1), lambda f: True)
    q = inner_skin(p, 0.003)
    for f in q.bm.faces:
        f.material_index = q.slot('glass')
    return p, q


def lamp_face(x, y):
    """the head lamps' lens face (measured on r01): the twin lenses slant back ~38° towards the outside (pointed nose)
    and lean back 13°; the outer corners sit higher (slanted eyes)"""
    return 0.821 - 0.77 * (x - 0.02) - 0.24 * (y - lamp_y(x, 0))


def lamp_y(x, t):
    """lens height at x: t = 0 bottom edge, 1 top edge"""
    return K.lerp(0.700 + 0.15 * (x - 0.02), 0.767 + 0.19 * (x - 0.02), t)


LAMP_X0, LAMP_X1 = 0.021, 0.122
LAMP_BEZEL = (0.07, 0.16)        # the opening in the cowl round the lens (fraction of the lens width, height)


def lamp_ring(x0, x1, grow=(0.0, 0.0)):
    """the lens outline as (x, y) points (x > 0) grown about its centre"""
    cx, cy = (x0 + x1) / 2, lamp_y((x0 + x1) / 2, 0.5)
    ring = [(K.lerp(x0, x1, t / 10), 0.0) for t in range(11)] + [(x1, t / 4) for t in range(1, 5)] + \
           [(K.lerp(x1, x0, t / 10), 1.0) for t in range(1, 11)] + [(x0, 1 - t / 4) for t in range(1, 4)]
    out = []
    for x, t in ring:
        y = lamp_y(x, t)
        out.append((x + (x - cx) * grow[0], y + (y - cy) * grow[1]))
    return out


def cockpit(surf):
    """what the opened cockpit shows: the side panels' inward lip along their top edge, the radiator top and its cap,
    the gauges"""
    p = K.Part('cockpit')
    top = [(z, y) for z, y in OUTLINE[OUTLINE.index((0.637, 0.741)):OUTLINE.index((0.122, 0.668)) + 1]]
    for sgn in (1, -1):
        rows = [[], []]
        for z, y in K.resample(top, 14):
            h = surf.hit((0.0, y - 0.006, z), (-sgn * 1.0, 0.0, 0.0))
            xo = abs(h[0][0]) if h is not None else 0.2
            rows[0].append((sgn * (xo - 0.002), y - 0.006, z))
            rows[1].append((sgn * (xo - 0.05), y - 0.012, z))
        p.grid(rows, 'paint', flip=sgn < 0)
    p.obox('engine', (0.0, 0.64, 0.43), (0.30, 0.15, 0.40), bevel=0.02)
    p.cylinder('trim', (-0.06, 0.715, 0.27), (-0.06, 0.75, 0.27), 0.022, seg=12)
    for x in (-0.05, 0.05):
        c = np.array([x, 0.95, 0.405])
        nrm = np.array([0.0, 0.6, -0.8])
        p.cylinder('trim', tuple(c - nrm * 0.02), tuple(c + nrm * 0.005), 0.042, seg=16)
        p.cylinder('gauge', tuple(c + nrm * 0.005), tuple(c + nrm * 0.007), 0.036, seg=16)
    return p


def cut_lamp_openings(p):
    """the openings for the head lamp units in the nose cowl; returns the uncut cowl's surface for laying the lamps"""
    import bmesh
    surf = K.Surface(K.bvh_of_parts([p]))
    for sgn in (1, -1):
        poly = [(sgn * x, y) for x, y in lamp_ring(LAMP_X0, LAMP_X1, LAMP_BEZEL)]
        K.cut_outline(p.bm, poly, 'front', side=1, min_facing=0.05)
        dead = K.faces_in(p.bm, poly, 'front', side=1, min_facing=0.05)
        bmesh.ops.delete(p.bm, geom=dead, context='FACES')
    return surf


def lamps(m, surf):
    """twin rectangular head lamps in the nose (outline measured on r01): each lens sits recessed in an opening in the
    cowl behind a dark housing lip; the lens texture shows the reflector through its vertical flutes; the side indicators"""
    p = K.Part('lamps')
    x0, x1 = LAMP_X0, LAMP_X1
    nf = 12

    def on_cowl(x, y, depth):
        """a point on the (uncut) cowl at (x, y), moved `depth` into it along its normal"""
        h = surf.hit((x, y, 1.5), (0, 0, -1))
        if h is None:
            return np.array([x, y, lamp_face(abs(x), y)])
        q, n = h
        if n[2] < 0:
            n = -n
        return q - n * depth

    for sgn in (1, -1):
        rim = [on_cowl(sgn * x, y, -0.0006) for x, y in lamp_ring(x0, x1, LAMP_BEZEL)]
        lip = [on_cowl(sgn * x, y, 0.007) for x, y in lamp_ring(x0, x1, LAMP_BEZEL)]
        seat = [on_cowl(sgn * x, y, 0.007) for x, y in lamp_ring(x0, x1)]
        p.loft([rim, lip, seat], 'trim', closed=True, flip=sgn < 0)
        # the fluted lens: vertical flutes across the width
        rows = []
        for j in range(7):
            t = j / 6
            row = []
            for i in range(nf * 2 + 1):
                x = K.lerp(x0, x1, i / (nf * 2))
                row.append(tuple(on_cowl(sgn * x, lamp_y(x, t), 0.0055)))
            rows.append(row)
        # the flutes are in the texture: ridged geometry caught the sun as white stripes at grazing angles
        faces, vs = p.grid(rows, 'headlight', smooth=True, flip=sgn > 0)
        # the lens texture (textures/nsr250r/headlight.png): u inner → outer edge, v bottom → top
        uv = {vs[j][i]: (i / (nf * 2), j / 6) for j in range(7) for i in range(nf * 2 + 1)}
        for f in faces:
            for lp in f.loops:
                lp[p.uv].uv = uv[lp.vert]
        # front indicator: a flush teardrop on the cowl side
        c = np.array([sgn * 0.208, 0.625, 0.505])
        p.obox('indicator', tuple(c), (0.03, 0.045, 0.075), axes=((1, 0, 0.35 * sgn), (0, 1, 0), (-0.35 * sgn, 0, 1)), bevel=0.014)
    return p


# ---------------------------------------------------------------- livery
# Our own simplified tricolour after the 1990-91 MC21 (white, red, blue; measured on r01 and redrawn as plain shapes):
# side polygons (z, y), the same on both sides.
NOSE_RED = [(0.536, 0.925), (0.60, 0.85), (0.645, 0.79), (0.651, 0.735), (0.762, 0.695), (0.772, 0.71), (0.746, 0.785),
            (0.651, 0.862)]
SIDE_BLUE = [(0.146, 0.661), (0.318, 0.54), (0.465, 0.411), (0.587, 0.541)]
SIDE_RED_UP = [(0.137, 0.663), (0.316, 0.54), (0.46, 0.40), (0.289, 0.457), (-0.018, 0.59)]
SIDE_RED_LOW = [(-0.053, 0.57), (0.433, 0.366), (0.446, 0.268), (0.39, 0.29), (0.29, 0.36), (0.168, 0.411), (0.053, 0.466),
                (-0.103, 0.543)]
LOW_STRIPE = [(-0.045, 0.474), (0.163, 0.356), (0.213, 0.326), (0.378, 0.209), (0.52, 0.13), (0.518, 0.098), (0.33, 0.18),
              (0.175, 0.324)]
TANK_RED = [(-0.062, 0.916), (0.223, 0.766), (0.34, 0.79), (0.34, 1.05), (-0.062, 1.05)]
TAIL_RED_A = [(-0.068, 0.656), (-0.071, 0.689), (-0.102, 0.712), (-0.192, 0.735), (-0.275, 0.71), (-0.42, 0.757),
              (-0.345, 0.709), (-0.15, 0.626)]
TAIL_RED_B = [(-0.36, 0.80), (-0.37, 0.823), (-0.527, 0.87), (-0.526, 0.829), (-0.508, 0.796), (-0.489, 0.79), (-0.489, 0.809)]
TAIL_STRIPE = [(-0.483, 0.763), (-0.366, 0.673), (-0.307, 0.649), (-0.258, 0.601), (-0.2, 0.608), (-0.2, 0.627)]


def livery(fa, tk, tail):
    """paint areas cut into the fairing, tank and tail; lettering and the wing badge as decals (part 'decals')"""
    for poly in (NOSE_RED, SIDE_RED_UP, SIDE_RED_LOW, LOW_STRIPE):
        K.paint_region(fa, poly, 'side', 'accent', side=-1, min_facing=-1.01)
    K.paint_region(fa, SIDE_BLUE, 'side', 'accent2', side=-1, min_facing=-1.01)
    # the red divider between the head lamps
    K.paint_region(fa, [(-0.024, 0.68), (0.024, 0.68), (0.024, 0.80), (-0.024, 0.80)], 'front', 'accent', side=1)
    K.paint_region(tk, TANK_RED, 'side', 'accent', side=-1, min_facing=-1.01)
    for poly in (TAIL_RED_A, TAIL_RED_B, TAIL_STRIPE):
        K.paint_region(tail, poly, 'side', 'accent', side=-1, min_facing=-1.01)
    d = K.Part('decals')
    sf = K.Surface(K.bvh_of_parts([fa]))
    st = K.Surface(K.bvh_of_parts([tk]))
    for side in (-1, 1):
        # screen coordinates of that side: s = z on the right (seen from -x), s = -z on the left; mirrored layouts
        mir = (lambda s, t: (s, t)) if side < 0 else (lambda s, t: (-s, t))
        k = -side
        # HONDA along the lower stripe, NSR on the blue panel (read left to right on both sides)
        L.text(d, sf, 'HONDA', mir(0.1425, 0.294), (0.804, -0.593 * k), 0.062, 'logo2', side, stroke=0.2, gap=0.22)
        L.text(d, sf, 'NSR', mir(0.418, 0.556), (1.0, -0.04 * k), 0.044, 'logo', side, stroke=0.24, gap=0.12, shear=0.32)
        # the wing badge and HONDA on the tank (our own simple wing: five swept feathers)
        c = mir(0.143, 0.858)
        feathers = []
        for i in range(5):
            y0 = -0.012 + i * 0.0058
            x0 = -0.024 + i * 0.0025
            ln = 0.020 + i * 0.0065
            q = [(x0, y0), (x0 + ln, y0 + 0.0055), (x0 + ln + 0.002, y0 + 0.0092), (x0, y0 + 0.0034)]
            feathers.append([(c[0] + qx, c[1] + qy) for qx, qy in q])
        L.decal_polys(d, st, feathers, side, 'logo')
        L.text(d, st, 'HONDA', mir(0.140, 0.828), (1.0, 0.0), 0.011, 'logo', side, stroke=0.2)
    return d


# ---------------------------------------------------------------- tank, seat, tail

# the tank ends at z -0.13 (top) .. -0.17 (bottom) and the seat starts low there (measured on r01)
T_Z = [0.31, 0.26, 0.16, 0.06, -0.04, -0.10, -0.14, -0.17]
T_TOP = _f(list(zip(T_Z, [0.86, 0.915, 0.937, 0.943, 0.942, 0.925, 0.885, 0.81])))
T_BOT = _f(list(zip(T_Z, [0.78, 0.745, 0.72, 0.715, 0.715, 0.72, 0.725, 0.73])))
T_W = _f(list(zip(T_Z, [0.10, 0.16, 0.188, 0.19, 0.178, 0.16, 0.145, 0.13])))


def tank(m):
    p = K.Part('tank')
    zs = list(np.linspace(0.31, -0.17, 20))
    P.closed_loft(p, zs, lambda z: P.superellipse(0.0, (T_TOP(z) + T_BOT(z)) / 2 - 0.0, T_W(z),
                                                   (T_TOP(z) - T_BOT(z)) / 2, (T_TOP(z) - T_BOT(z)) / 2, 2.4, 3.5, n=28),
                  n=28, mat='paint')
    return p


# the seat rises from the tank (0.765) to the solo cowl's front face at z -0.53 (measured on r01)
S_Z = [-0.15, -0.22, -0.30, -0.38, -0.46, -0.54]
S_TOP = _f(list(zip(S_Z, [0.765, 0.785, 0.81, 0.828, 0.836, 0.84])))
S_W = _f(list(zip(S_Z, [0.10, 0.118, 0.128, 0.13, 0.128, 0.122])))

# the solo cowl's hump rises behind the seat at z -0.50 .. -0.55 (its front face measured on r01)
TL_Z = [-0.17, -0.30, -0.42, -0.48, -0.515, -0.55, -0.60, -0.66, -0.74, -0.82, -0.90, -0.935]
TL_TOP = _f(list(zip(TL_Z, [0.72, 0.735, 0.75, 0.78, 0.875, 0.943, 0.963, 0.978, 0.997, 1.01, 1.014, 0.995])))
TL_BOT = _f(list(zip(TL_Z, [0.585, 0.585, 0.59, 0.597, 0.605, 0.615, 0.63, 0.655, 0.70, 0.75, 0.80, 0.835])))
TL_W = _f(list(zip(TL_Z, [0.14, 0.142, 0.142, 0.14, 0.138, 0.136, 0.132, 0.127, 0.12, 0.112, 0.102, 0.092])))


def seat_tail(m):
    seat = K.Part('seat')
    zs = list(np.linspace(-0.15, -0.54, 13))
    P.closed_loft(seat, zs, lambda z: P.superellipse(0.0, S_TOP(z) - 0.04, S_W(z), 0.04, 0.03, 2.8, 4.0, n=20), n=20, mat='seat')
    tail = K.Part('tail')
    zs = list(np.linspace(-0.17, -0.935, 30))
    P.closed_loft(tail, zs, lambda z: P.superellipse(0.0, (TL_TOP(z) + TL_BOT(z)) / 2, TL_W(z), (TL_TOP(z) - TL_BOT(z)) / 2,
                                                       (TL_TOP(z) - TL_BOT(z)) / 2, 4.0, 3.2, n=28), n=28, mat='paint')
    # the solo cowl's pad on the hump's front
    for f in tail.bm.faces:
        c = K.G(f.calc_center_median())
        n = K.G(f.normal)
        if -0.60 < c[2] < -0.47 and c[1] > 0.81 and n[2] > 0.35 and abs(c[0]) < 0.105:
            f.material_index = tail.slot('seat')
    # tail lamp (under the tail's rear lip) and rear indicators, plate holder
    lamp = K.Part('taillamp')
    rows = []
    for j in range(3):
        y = K.lerp(0.845, 0.895, j / 2)
        rows.append([(K.lerp(0.08, -0.08, i / 8), y, -0.94 - 0.008 * math.cos(math.pi * (i / 8 - 0.5)) ** 2) for i in range(9)])
    lamp.grid(rows, 'taillight', flip=True)
    lamp.obox('trim', (0.0, 0.87, -0.932), (0.18, 0.065, 0.02), bevel=0.008)
    for sgn in (1, -1):
        lamp.tube([(sgn * 0.06, 0.79, -0.90), (sgn * 0.15, 0.79, -0.92)], 0.006, 'trim', seg=6)
        lamp.obox('indicator', (sgn * 0.16, 0.79, -0.925), (0.03, 0.028, 0.05), bevel=0.012)
    hold = K.Part('plate_holder')
    hold.face([(0.09, 0.80, -0.88), (-0.09, 0.80, -0.88), (-0.09, 0.64, -0.99), (0.09, 0.64, -0.99)], 'trim')
    hold.face([(0.09, 0.64, -0.99), (-0.09, 0.64, -0.99), (-0.09, 0.80, -0.88), (0.09, 0.80, -0.88)], 'trim')
    hold.face([(0.085, 0.725, -0.937), (-0.085, 0.725, -0.937), (-0.085, 0.645, -0.992), (0.085, 0.645, -0.992)], 'plate')
    return seat, tail, lamp, hold


# ---------------------------------------------------------------- frame, swingarm, engine, exhaust

def chassis(m):
    p = K.Part('frame')
    for sgn in (1, -1):
        x = sgn * 0.125
        P.beam_path(p, [(sgn * 0.06, 0.80, 0.43), (x, 0.775, 0.33), (x, 0.70, 0.12), (x, 0.62, -0.06), (x, 0.55, -0.14),
                        (x, 0.42, -0.17), (x, 0.28, -0.16)], 0.038, [0.07, 0.11, 0.12, 0.12, 0.10, 0.09, 0.08], 'frame', n=16,
                    r=0.12)
        # seat rail
        P.beam_path(p, [(sgn * 0.11, 0.62, -0.10), (sgn * 0.10, 0.70, -0.45), (sgn * 0.08, 0.77, -0.80)], 0.022, 0.03, 'frame2', n=8)
        P.beam_path(p, [(sgn * 0.11, 0.44, -0.17), (sgn * 0.10, 0.62, -0.42)], 0.02, 0.022, 'frame2', n=4)
    # head stock
    p.cylinder('frame', tuple(ST.at_y(0.69)), tuple(ST.at_y(0.85)), 0.032, seg=14)
    # pivot bolts
    for sgn in (1, -1):
        p.cylinder('chrome', (sgn * 0.14, PIVOT[1], PIVOT[2]), (sgn * 0.155, PIVOT[1], PIVOT[2]), 0.014, seg=10)
    # swingarm: left straight, right gull (curved up over the chamber)
    sw = K.Part('swingarm')
    ax = np.array([0.0, RR, RZ])
    P.beam_path(sw, [(0.115, PIVOT[1], PIVOT[2]), (0.112, 0.345, -0.40), (0.105, RR + 0.01, RZ + 0.03)], 0.04,
                [0.075, 0.07, 0.05], 'frame', n=8)
    # the gull arm arches up over the right stinger (measured on r01)
    P.beam_path(sw, [(-0.115, PIVOT[1], PIVOT[2]), (-0.125, 0.44, -0.30), (-0.125, 0.47, -0.41), (-0.118, 0.42, -0.52),
                     (-0.108, 0.335, -0.62), (-0.105, RR + 0.01, RZ + 0.03)],
                0.04, [0.08, 0.10, 0.105, 0.09, 0.07, 0.05], 'frame', n=16, r=0.15)
    P.beam_path(sw, [(0.10, 0.37, -0.29), (-0.10, 0.40, -0.29)], 0.04, 0.06, 'frame', n=2)
    for sgn in (1, -1):
        sw.obox('frame2', (sgn * 0.105, RR, RZ), (0.03, 0.05, 0.07), bevel=0.008)
    # rear shock (mostly hidden) and the chain
    sw.cylinder('engine', (0.0, 0.35, -0.30), (0.0, 0.62, -0.18), 0.025, seg=10)
    P.chain(sw, (0.0, 0.33, -0.07), 0.04, (0.0, RR, RZ), 0.085, 0.085)
    P.sprocket(sw, (0, RR, RZ), 0.085, 0.09, teeth=40)
    # pegs and rear sets
    for sgn in (1, -1):
        P.peg(sw, (sgn * 0.155, 0.355, -0.235), sgn)
        # the rear-set heel plate (polished aluminium)
        sw.obox('frame', (sgn * 0.163, 0.425, -0.245), (0.008, 0.17, 0.11), axes=((1, 0, 0), (0, 0.94, -0.34), (0, 0.34, 0.94)),
                bevel=0.003)
    return p, sw


def engine(m):
    p = K.Part('engine')
    p.box('engine', -0.12, 0.12, 0.17, 0.42, -0.13, 0.22, bevel=0.03)
    p.box('engine', -0.08, 0.08, 0.36, 0.50, 0.18, 0.37, bevel=0.02)     # front cylinder (near horizontal)
    p.box('engine', -0.08, 0.08, 0.40, 0.62, -0.02, 0.13, bevel=0.02)    # rear cylinder
    p.box('radiator', -0.17, 0.17, 0.33, 0.70, 0.37, 0.41, bevel=0.01)
    # side cases
    for sgn in (1, -1):
        p.cylinder('engine', (sgn * 0.12, 0.30, 0.04), (sgn * 0.14, 0.30, 0.04), 0.09, seg=20)
    return p


def exhaust(m):
    """the expansion chambers run under the engine behind the lower fairing; only their stingers show, running straight
    up under the swingarm to the aluminium silencers below the tail (stinger and silencer measured on r01)"""
    p = K.Part('chambers')
    rad = [(0, 0.022), (0.12, 0.03), (0.3, 0.05), (0.5, 0.05), (0.64, 0.032), (0.71, 0.017), (1, 0.017)]
    # right: rear cylinder (exhausts backwards) → down under the engine → stinger under the gull arm
    P.pipe(p, [(-0.03, 0.55, -0.04), (-0.06, 0.42, -0.07), (-0.085, 0.27, -0.10), (-0.10, 0.19, -0.18), (-0.12, 0.17, -0.28),
               (-0.135, 0.205, -0.36), (-0.15, 0.33, -0.47), (-0.163, 0.47, -0.597), (-0.168, 0.53, -0.65)], rad,
           mat='chamber', seg=14, cap1=False)
    # left: front cylinder → under the engine → the same stinger on the left
    P.pipe(p, [(0.0, 0.40, 0.33), (0.03, 0.26, 0.35), (0.06, 0.195, 0.22), (0.09, 0.185, 0.02), (0.11, 0.18, -0.16),
               (0.125, 0.18, -0.28), (0.135, 0.205, -0.36), (0.15, 0.33, -0.47), (0.163, 0.47, -0.597), (0.168, 0.53, -0.65)],
           [(0, 0.022), (0.1, 0.03), (0.25, 0.05), (0.52, 0.05), (0.66, 0.032), (0.73, 0.017), (1, 0.017)],
           mat='chamber', seg=14, cap1=False)
    sil = K.Part('exhaust_silencers')
    for sgn in (1, -1):
        P.silencer(sil, (sgn * 0.17, 0.528, -0.646), (sgn * 0.17, 0.728, -0.921), 0.040, 0.044, mat='exhaust', oval=1.1, end_cap=0.015)
    return p, sil


# ---------------------------------------------------------------- steering assembly, wheels

def steer_parts(m):
    p = K.Part('forks')
    legx = 0.098
    top_t = (0.865 - RF) / ST.axis[1]
    bot_t = (0.70 - RF) / ST.axis[1]
    for sgn in (1, -1):
        x = sgn * legx
        p.cylinder('fork_low', tuple(ST.leg_point(-0.035, x)), tuple(ST.leg_point(0.27, x)), 0.031, seg=14)
        p.cylinder('fork', tuple(ST.leg_point(0.26, x)), tuple(ST.leg_point(top_t + 0.03, x)), 0.0205, seg=14)
        # axle lug and brake-caliper bracket
        p.obox('fork_low', tuple(ST.leg_point(0.0, x) + np.array([0, -0.01, -0.01])), (0.05, 0.07, 0.06), bevel=0.012)
    # yokes: plates between the legs and the steering axis
    for t, th in ((bot_t, 0.035), (top_t, 0.02)):
        c = ST.leg_point(t, 0) - ST.fwd * ST.offset * 0.5
        p.obox('frame2' if th > 0.03 else 'frame', tuple(c), (2 * legx + 0.07, th, 0.075),
               axes=((1, 0, 0), ST.axis, ST.fwd), bevel=0.012)
    p.cylinder('chrome', tuple(ST.at_y(0.88) + np.array([0, 0, 0])), tuple(ST.at_y(0.895)), 0.02, seg=10)
    # clip-ons, grips, levers
    ST.top_leg = [ST.leg_point(top_t - 0.035, legx), ST.leg_point(top_t - 0.035, -legx)]
    grips = [(0.30, 0.845, 0.325), (-0.30, 0.845, 0.325)]
    for sgn, g in ((1, grips[0]), (-1, grips[1])):
        P.clip_on(p, ST, sgn, g, reservoir=True)
    # front mudguard: a shell over the tyre (angles from the top: −35° behind … +60° in front)
    mg = K.Part('mudguard')
    rows = []
    rad = RF + 0.022
    for k in range(13):
        a = math.radians(-38 + 98 * k / 12)
        d = np.array([0, math.cos(a), math.sin(a)])
        w = 0.066 - 0.012 * (k / 12) ** 2
        rows.append([tuple(ST.axle + d * (rad - 0.035) + np.array([w, 0, 0])), tuple(ST.axle + d * rad + np.array([w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad + 0.008) + np.array([0, 0, 0])), tuple(ST.axle + d * rad + np.array([-w * 0.85, 0, 0])),
                     tuple(ST.axle + d * (rad - 0.035) + np.array([-w, 0, 0]))])
    faces, _ = mg.grid(rows, 'accent')
    P._orient(mg, faces, (0, 1, 0), lambda f: K.G(f.calc_center_median())[1] > ST.axle[1] + 0.2)
    mgi = inner_skin(mg, 0.003)
    return p, mg, mgi, grips


def wheels(m, wf_node, sf_node, wr_node, sr_node):
    # front
    sp = K.Part('wheel_front')
    P.tyre(sp, ST.axle, RF, WF)
    P.rim(sp, ST.axle, 0.076, spokes=7, style='straight', spoke_w=0.022, spoke_depth=0.026)
    for sgn in (1, -1):
        P.disc(sp, ST.axle, sgn * 0.066, 0.138, 0.098, carrier='frame2', bolts=8)
    cal = K.Part('calipers_front')
    for sgn in (1, -1):
        P.caliper(cal, ST.axle, sgn * 0.066, 0.138, 135, side=sgn)
    sp.build(sf_node, m.mats, sharp=35)
    cal.build(wf_node, m.mats)
    # rear
    rp = K.Part('wheel_rear')
    rc = np.array([0.0, RR, RZ])
    P.tyre(rp, rc, RR, WR)
    P.rim(rp, rc, 0.114, spokes=7, style='straight', spoke_w=0.024, spoke_depth=0.03)
    P.disc(rp, rc, -0.072, 0.11, 0.08, carrier='frame2', bolts=5)
    cal = K.Part('caliper_rear')
    P.caliper(cal, rc, -0.072, 0.11, 115, side=-1)
    rp.build(sr_node, m.mats, sharp=35)
    cal.build(wr_node, m.mats)


# ---------------------------------------------------------------- the whole bike

def build(o=None):
    o = o or {}
    m = materials(o.get('paint', '#f2f2ee'))
    root = K.node('nsr250r')
    body = K.node('body', root)
    steer = K.node('steer', body, origin=tuple(ST.head), y_axis=tuple(ST.axis))
    wf = K.node('wheel_f', steer, origin=tuple(ST.axle))
    sf = K.node('spin_f', wf, origin=tuple(ST.axle))
    wr = K.node('wheel_r', body, origin=(0, RR, RZ))
    sr = K.node('spin_r', wr, origin=(0, RR, RZ))
    fa, fai, nose = fairing(m)
    sc, sci = screen(m)
    lp = lamps(m, nose)
    tk = tank(m)
    seat, tail, tlamp, hold = seat_tail(m)
    fr, sw = chassis(m)
    en = engine(m)
    ch, sil = exhaust(m)
    forks, mg, mgi, grips = steer_parts(m)
    mir = K.Part('mirrors')
    for sgn in (1, -1):
        P.mirror(mir, (sgn * 0.21, 0.95, 0.45), (sgn * 0.27, 1.04, 0.435), size=(0.13, 0.065, 0.045))
    dash = K.Part('dash')
    dash.obox('trim', (0.0, 0.92, 0.40), (0.24, 0.10, 0.03), axes=((1, 0, 0), (0, 0.5, -0.86), (0, 0.86, 0.5)), bevel=0.01)
    dec = livery(fa, tk, tail)
    cp = cockpit(nose)
    for part in (fa, fai, sc, sci, lp, tk, seat, tail, tlamp, hold, fr, sw, en, ch, mir, dash, dec, cp):
        part.build(body, m.mats, sharp=40)
    sil.build(body, m.mats, sharp=40)
    for part in (forks, mg, mgi):
        part.build(steer, m.mats, sharp=40)
    wheels(m, wf, sf, wr, sr)
    if o.get('rider', True):
        rn = K.node('rider', body)
        rp = K.Part('rider_body')
        info = RD.build(rp, {'hip': (0, 0.90, -0.39), 'grips': grips, 'pegs': [(0.155, 0.355, -0.235), (-0.155, 0.355, -0.235)],
                             'reach': 0.47, 'look': 0.10})
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
