"""
Bus shelter (a small rural Japanese bus stop, as villages build them): a timber hut on a concrete slab: four 105 mm
posts in steel shoes, beams, braces, rafters and purlins under a corrugated galvanised roof (the real 76 mm wave)
falling to the back, where a PVC gutter and its downpipe take the rain; board walls (back and left full height, right
half height) on rails, a slatted bench, on the back wall the timetable, the town's bear warning and an enamel sign;
beside the hut the stop's pole: a concrete disc, a steel pipe, the round sign printed on both faces (fictional stop
「朧峠入口」, no operator logo) and a timetable case.
About 2.5 m tall (the sign's top at 2.59 m), 3.4 m shelter width; open side towards +Z; origin at the centre of the
footprint on the ground (the slab on its foundation reaches 1.6 m into it: the ground there is never level, and the
game stands the hut on the highest of it).
Texture busstop.png (painted by paint.py): the sign, the timetable, the posters.

    blender -t 4 --background --factory-startup --python bus_stop.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

SIGN = (1.95, 2.34, 0.62)     # sign disc centre
SIGN_R = 0.25
CENTRE = (-0.10, 0.12)        # footprint centre in design coordinates (x, z), moved to the origin at the end
BW = 0.18                     # a wall board's width


def under(z):
    """the roof sheet's underside above z (it falls 10 cm per metre to the back)"""
    return 2.26 + 0.101 * (z + 1.0)


def px_uv(x0, y0, x1, y1, rect, flip=False):
    """a rectangle of the picture (pixels: left, top, right, bottom) over the face x0..x1, y0..y1"""
    l, t, r, b = rect

    def fn(cs):
        out = []
        for c in cs:
            u = (c.x - x0) / (x1 - x0)
            u = 1 - u if flip else u
            out.append(((l + u * (r - l)) / 1024, 1 - (b - (c.y - y0) / (y1 - y0) * (b - t)) / 1024))
        return out
    return fn


def planks(axis, phase):
    """every board a shade of its own: axis 'x' or 'z' (game), `phase` = minus the first board's edge there (final frame)"""
    def fn(g, ch):
        x, y, z = g.xyz(g.pos())
        c = x if axis == 'x' else g.mul(y, -1.0)       # Blender y = -(game z)
        n = g.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        g.put(n.inputs['W'], g.math('FLOOR', g.math('DIVIDE', g.add(c, phase), BW)))
        ch['base'] = g.mix(ch['base'], g.rgb((0, 0, 0)), g.mul(n.outputs['Value'], 0.32))
    return fn


def timber(m, mat, a, b, w, h):
    """a rectangular timber from a to b, w across and h deep"""
    m.sweep(mat, [a, b], [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])


def corrugated(m, mat, x0, x1, y_front, y_back, z_front, z_back, pitch=0.0762, depth=0.018, thick=0.006):
    """a corrugated sheet sloping from the front to the back, the wave running along x; cut in three along the fall"""
    waves = round((x1 - x0) / pitch)
    n = waves * 4
    top, bot = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        w = depth / 2 * math.sin(2 * math.pi * waves * i / n)
        top.append((x, w))
        bot.append((x, w - thick))
    prof = top + bot[::-1]
    rings = []
    for k in range(4):
        t = k / 3
        z, y = z_front + (z_back - z_front) * t, y_front + (y_back - y_front) * t
        rings.append([(x, y + dy, z) for x, dy in prof])
    m.loft(mat, rings)


def build(out):
    d = K.paint(out, ['bus'])
    sheet = K.load_image(os.path.join(d, 'busstop.png'))
    wood = dict(roughness=0.86, vary=0.14, mottle=0.35, mottle_scale=5, mottle_colour='#8b8479', grain=1.0, grain_scale=34, dirt=0.6,
                streak=0.4, foot=0.7, foot_h=0.55, foot_colour='#2c2620', moss=0.45, wear=0.4, wear_colour='#a39480')
    # the grain runs along the timber: upright (posts, boards), along x (beams, slats), along z (rafters, side rails)
    cx, cz = CENTRE
    wood_post = PB.surface('wood_post', '#6a5744', fibre=(1, 0.05, 1), **wood)
    wood_back = PB.surface('wood_back', '#6f5b47', fibre=(1, 0.05, 1), custom=planks('x', 1.95 + cx), **wood)
    wood_side = PB.surface('wood_side', '#6f5b47', fibre=(1, 0.05, 1), custom=planks('z', 0.83 + cz), **wood)
    wood_x = PB.surface('wood_x', '#6a5744', fibre=(0.05, 1, 1), **wood)
    wood_z = PB.surface('wood_z', '#6a5744', fibre=(1, 1, 0.05), **wood)
    conc = PB.surface('concrete', '#8f8e87', roughness=0.9, vary=0.16, mottle=0.5, mottle_scale=11, grain=0.9, grain_scale=150, dirt=0.7,
                      foot=0.5, foot_h=0.05, moss=0.6, streak=0.3)
    tin = PB.surface('tin', '#9ea3a2', metallic=0.75, roughness=0.5, vary=0.1, mottle=0.5, mottle_scale=3, mottle_colour='#7e7468',
                     mottle_rough=0.75, dirt=0.5, dust=0.5, rust=0.5, grain=0.2, grain_scale=200)
    zinc = PB.surface('zinc', '#a3a8a8', metallic=0.7, roughness=0.48, rust=0.4, dirt=0.5, streak=0.3, foot=0.5, foot_h=0.3)
    pvc = PB.surface('pvc', '#9a9f9c', roughness=0.55, vary=0.06, dirt=0.6, streak=0.5, moss=0.4, mottle=0.3, mottle_scale=12)
    printed = PB.surface('printed', '#ffffff', roughness=0.45, image=sheet, vary=0.04, dirt=0.45, streak=0.3, rust=0.1)
    enamel = PB.surface('enamel', '#ffffff', roughness=0.2, image=sheet, vary=0.04, dirt=0.5, streak=0.35, rust=0.5, wear=0.3,
                        wear_colour='#3a2a20')

    m = K.M('bus_stop')
    # --- slab (cast against boards: a chamfer), into the ground
    with m.dense(0.7):
        m.box(conc, -2.2, 1.5, -0.35, 0.12, -1.0, 1.25, bevel=0.015, seg=1)
    with m.dense(0.3):   # its foundation: the shelter stands level on the highest ground under it
        m.box(conc, -2.17, 1.47, -1.6, -0.3, -0.97, 1.22)
    # --- posts in their steel shoes
    for x in (-2.0, 1.3):
        for z0, top in ((0.80, 2.30), (-0.94, 2.13)):
            zc = z0 + 0.0525
            m.box(wood_post, x - 0.0525, x + 0.0525, 0.12, top, z0, z0 + 0.105, bevel=0.006, seg=1)
            m.box(zinc, x - 0.058, x + 0.058, 0.12, 0.24, z0 - 0.0055, z0 + 0.1105)
            m.box(zinc, x - 0.09, x + 0.09, 0.12, 0.127, zc - 0.09, zc + 0.09)
            for s in (-1, 1):
                m.bolt(zinc, (x + s * 0.058, 0.20, zc), (s, 0, 0), r=0.009, h=0.007)
                m.bolt(zinc, (x + s * 0.075, 0.127, zc + s * 0.07), (0, 1, 0), r=0.009, h=0.008)
    # --- beams along the front and the back, braces under the front beam, top rails along the sides
    m.box(wood_x, -2.10, 1.40, 2.17, 2.31, 0.77, 0.935, bevel=0.006, seg=1)
    m.box(wood_x, -2.10, 1.40, 2.00, 2.14, -0.965, -0.81, bevel=0.006, seg=1)
    for x, s in ((-2.0, 1), (1.3, -1)):
        timber(m, wood_x, (x + s * 0.04, 1.80, 0.8525), (x + s * 0.44, 2.19, 0.8525), 0.06, 0.06)
        timber(m, wood_z, (x, 2.235, 0.80), (x, 2.065, -0.83), 0.09, 0.09)
    # --- rafters, purlins, the corrugated sheet, a fascia board at the front
    for x in (-2.0, -1.175, -0.35, 0.475, 1.3):
        timber(m, wood_z, (x, under(1.12) - 0.09, 1.12), (x, under(-0.98) - 0.09, -0.98), 0.045, 0.09)
    for z in (1.04, 0.36, -0.30, -0.92):
        m.box(wood_x, -2.34, 1.64, under(z) - 0.045, under(z), z - 0.02, z + 0.02)
    with m.dense(0.8):
        corrugated(m, tin, -2.38, 1.68, under(1.18) + 0.015, under(-1.04) + 0.015, 1.18, -1.04)
    m.box(wood_x, -2.36, 1.66, under(1.16) - 0.13, under(1.16), 1.145, 1.17, bevel=0.004, seg=1)
    # --- gutter under the roof's back edge, its downpipe at the right corner
    arc = [(0.055 * math.cos(math.radians(a)), 0.055 * math.sin(math.radians(a))) for a in range(180, 361, 30)]
    arc += [(0.05 * math.cos(math.radians(a)), 0.05 * math.sin(math.radians(a))) for a in range(360, 179, -30)]
    gy = under(-1.04) - 0.02
    m.sweep(pvc, [(-2.40, gy, -1.065), (1.70, gy - 0.02, -1.065)], arc)
    for x in (-2.0, -0.35, 1.3):
        m.box(zinc, x - 0.012, x + 0.012, gy - 0.062, gy + 0.01, -1.125, -0.97)
    m.tube(pvc, [(1.52, gy - 0.07, -1.065), (1.52, gy - 0.16, -1.065), (1.50, gy - 0.26, -1.02), (1.47, gy - 0.34, -0.99),
                 (1.47, 1.2, -0.99), (1.47, 0.22, -0.99), (1.47, 0.14, -1.03), (1.47, 0.13, -1.10)], 0.03, seg=10)
    for y in (0.5, 1.6):
        m.cyl(zinc, (1.47, y - 0.012, -0.99), (1.47, y + 0.012, -0.99), 0.034, seg=10, caps=(False, False))
    # --- back wall: upright boards on three rails
    x = -1.95
    while x + BW <= 1.28:
        m.box(wood_back, x + 0.002, x + BW - 0.002, 0.14, 2.02, -0.90, -0.88, bevel=0.003, seg=1)
        x += BW
    for y in (0.45, 1.20, 1.90):
        m.box(wood_x, -1.95, 1.25, y, y + 0.05, -0.88, -0.845, bevel=0.003, seg=1)
    # --- left wall: boards up to the top rail; right wall: boards to 1.15 m under a cap rail
    z = -0.83
    while z + BW <= 0.80:
        top = 2.065 + (z + BW / 2 + 0.83) / 1.63 * 0.17 - 0.03
        m.box(wood_side, -2.005, -1.985, 0.14, top, z + 0.002, z + BW - 0.002, bevel=0.003, seg=1)
        m.box(wood_side, 1.285, 1.305, 0.14, 1.15, z + 0.002, z + BW - 0.002, bevel=0.003, seg=1)
        z += BW
    m.box(wood_z, 1.25, 1.335, 1.15, 1.20, -0.86, 0.80, bevel=0.004, seg=1)
    for y in (0.45, 1.20):
        m.box(wood_z, -1.985, -1.95, y, y + 0.05, -0.83, 0.80, bevel=0.003, seg=1)
    m.box(wood_z, 1.25, 1.285, 0.45, 0.50, -0.83, 0.80, bevel=0.003, seg=1)
    # --- bench along the back wall: three slats on three frames, a back rest
    for k in range(3):
        m.box(wood_x, -1.7, 1.2, 0.42, 0.455, -0.82 + k * 0.145, -0.82 + k * 0.145 + 0.125, bevel=0.005, seg=1)
    for x in (-1.6, -0.25, 1.1):
        m.box(wood_post, x - 0.03, x + 0.03, 0.12, 0.42, -0.47, -0.41, bevel=0.003, seg=1)
        m.box(wood_post, x - 0.03, x + 0.03, 0.12, 0.92, -0.845, -0.80, bevel=0.003, seg=1)
        m.box(wood_z, x - 0.03, x + 0.03, 0.36, 0.42, -0.80, -0.41, bevel=0.003, seg=1)
    m.box(wood_x, -1.7, 1.2, 0.78, 0.90, -0.80, -0.775, bevel=0.004, seg=1)
    # --- on the back wall: the timetable in its frame, the bear warning, the taxi's enamel sign
    zw = -0.845
    bx0, bx1, by0, by1 = 0.42, 0.92, 1.30, 1.92
    m.box(wood_x, bx0 - 0.03, bx1 + 0.03, by0 - 0.03, by1 + 0.03, zw, zw + 0.022, bevel=0.004, seg=1)
    with m.dense(2.5):
        with m.uvmap(px_uv(bx0, by0, bx1, by1, (512, 0, 1024, 640)), only=printed):
            m.quad(printed, [(bx0, by0, zw + 0.0225), (bx1, by0, zw + 0.0225), (bx1, by1, zw + 0.0225), (bx0, by1, zw + 0.0225)])
        px0, px1, py0, py1 = -0.40, 0.24, 1.32, 1.80
        m.box(zinc, px0, px1, py0, py1, zw, zw + 0.004)
        with m.uvmap(px_uv(px0, py0, px1, py1, (512, 640, 1024, 1024)), only=printed):
            m.quad(printed, [(px0, py0, zw + 0.0045), (px1, py0, zw + 0.0045), (px1, py1, zw + 0.0045), (px0, py1, zw + 0.0045)])
        ex0, ex1, ey0, ey1 = -1.60, -1.15, 1.28, 1.88
        m.box(zinc, ex0, ex1, ey0, ey1, zw, zw + 0.004)
        with m.uvmap(px_uv(ex0, ey0, ex1, ey1, (0, 512, 384, 1024)), only=enamel):
            m.quad(enamel, [(ex0, ey0, zw + 0.0045), (ex1, ey0, zw + 0.0045), (ex1, ey1, zw + 0.0045), (ex0, ey1, zw + 0.0045)])
    for (x0, x1, y0, y1) in ((px0, px1, py0, py1), (ex0, ex1, ey0, ey1)):
        for cx_, cy_ in ((x0 + 0.03, y0 + 0.03), (x1 - 0.03, y0 + 0.03), (x0 + 0.03, y1 - 0.03), (x1 - 0.03, y1 - 0.03)):
            m.cyl(zinc, (cx_, cy_, zw + 0.004), (cx_, cy_, zw + 0.008), 0.007, 0.004, seg=8, caps=(False, True))
    # --- the stop's pole: a concrete disc, a steel pipe, the round sign (both faces), a timetable case
    sx, sy, sz = SIGN
    with m.dense(0.8):
        m.lathe(conc, [(0.26, -1.6), (0.26, 0.10), (0.24, 0.14), (0.06, 0.155)], seg=20, cx=sx, cz=sz - 0.045)
    m.cyl(zinc, (sx, 0.15, sz - 0.045), (sx, 0.21, sz - 0.045), 0.034, seg=12)
    m.cyl(zinc, (sx, 0.15, sz - 0.045), (sx, 2.32, sz - 0.045), 0.0243, seg=12)
    ring_pts = K.circle_pts(0, 0, SIGN_R, 36)
    back = [(sx + a, sy + b, sz - 0.02) for a, b in ring_pts]
    front = [(sx + a, sy + b, sz - 0.014) for a, b in ring_pts]
    m.loft(zinc, [back, front], cap0=False, cap1=False)
    m.torus(zinc, (sx, sy, sz - 0.017), SIGN_R, 0.006, 'z', seg=36, tube=6)
    with m.dense(2.5):
        with m.uvmap(px_uv(sx - SIGN_R, sy - SIGN_R, sx + SIGN_R, sy + SIGN_R, (4, 4, 508, 508)), only=printed):
            m.quad(printed, front)
        with m.uvmap(px_uv(sx - SIGN_R, sy - SIGN_R, sx + SIGN_R, sy + SIGN_R, (4, 4, 508, 508), flip=True), only=printed):
            m.quad(printed, back, flip=True)
    for y in (sy - 0.12, sy + 0.12):
        m.box(zinc, sx - 0.035, sx + 0.035, y - 0.012, y + 0.012, sz - 0.075, sz - 0.02)
    tx0, tx1, ty0, ty1 = sx - 0.16, sx + 0.16, 1.22, 1.62
    m.box(zinc, tx0 - 0.012, tx1 + 0.012, ty0 - 0.012, ty1 + 0.012, sz - 0.02, sz + 0.012, bevel=0.004, seg=1)
    with m.dense(2.5):
        with m.uvmap(px_uv(tx0, ty0, tx1, ty1, (512, 0, 1024, 640)), only=printed):
            m.quad(printed, [(tx0, ty0, sz + 0.0125), (tx1, ty0, sz + 0.0125), (tx1, ty1, sz + 0.0125), (tx0, ty1, sz + 0.0125)])
    ob = m.build(recentre=CENTRE)
    PB.finish([ob], out, 'bus_stop', size=2048, orm_size=1024, near=0.08, wide=0.7, edge=0.012, max_len=2.2, margin=0.002, normal_size=1024)
    return [ob]


SPEC = K.Spec('bus_stop.glb', build, [
    dict(name='main', eye=(-4.8, 2.0, 7.2), target=(0, 1.1, 0), lens=36),
    dict(name='inside', eye=(0.6, 1.5, 1.6), target=(-0.3, 1.2, -0.8), lens=30),
    dict(name='back', eye=(4.6, 2.6, -5.4), target=(0, 1.2, 0), lens=36),
    dict(name='sign', eye=(1.3, 1.9, 3.0), target=(1.9, 1.8, 0.5), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
