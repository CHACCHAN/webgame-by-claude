"""
Village house of the AUTOBAHN course: a two-storey German house, rendered masonry on a darker plinth, under a steep
gable roof of clay tiles (overhanging eaves, ridge tiles, gutters with their downpipes, a brick chimney). The
windows are cut into the walls: reveals, a sill, a white frame with its cross, folding shutters beside them (open)
or over them (closed); the front door up two steps under a small canopy, with its lamp. Which windows are lit, dark
or shuttered comes from a seed, so the same model shows a lived-in pattern at night (the emissive map lights only
the glass and the lamp). village_farmhouse.py builds the larger half-timbered farmhouse with its barn from the same
code. Weathered: runs under the sills and the eaves, splashed soil along the plinth, moss on the tiles.
Origin at the centre of the footprint on the ground (the plinth reaches 0.6 m into it), front (+Z) with the door,
~10 m tall.

    blender -t 4 --background --factory-startup --python village_house.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import math
import os
import random
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

BAY_H = 2.8
REVEAL = 0.15


def tiles(axis, pitch, row=0.30, col=0.22):
    """clay tiles in courses up the slope: `axis` 'x' or 'z' (game) is the ridge's direction; every tile a shade of its own"""
    rh = row * math.sin(math.radians(pitch))

    def fn(g, ch):
        x, y, z = g.xyz(g.pos())
        along = x if axis == 'x' else y
        rowf = g.math('DIVIDE', z, rh)
        ri = g.math('FLOOR', rowf)
        r = g.math('FRACT', rowf)
        colf = g.add(g.math('DIVIDE', along, col), g.mul(g.math('MODULO', ri, 2.0), 0.5))
        ci = g.math('FLOOR', colf)
        c = g.math('FRACT', colf)
        n = g.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        g.put(n.inputs['W'], g.add(g.mul(ri, 37.17), ci))
        ch['base'] = g.mix(ch['base'], g.rgb((0, 0, 0)), g.mul(n.outputs['Value'], 0.3))
        joint = g.math('MAXIMUM', g.step(r, 0.14, 0.0), g.step(c, 0.10, 0.0))
        ch['base'] = g.mix(ch['base'], g.rgb('#241511'), g.mul(joint, 0.7))
        ch['height'] = g.add(ch['height'], g.mul(g.math('SUBTRACT', 1.0, r), 1.2))
    return fn


def courses(h, w, colour='#b9b3a6', amount=0.75):
    """brick or board courses: joints every `h` m of height and every `w` m along the wall, alternate courses shifted"""
    def fn(g, ch):
        x, y, z = g.xyz(g.pos())
        rowf = g.math('DIVIDE', z, h)
        ri = g.math('FLOOR', rowf)
        r = g.math('FRACT', rowf)
        c = g.math('FRACT', g.add(g.math('DIVIDE', g.add(x, y), w), g.mul(g.math('MODULO', ri, 2.0), 0.5)))
        joint = g.math('MAXIMUM', g.step(r, 0.16, 0.0), g.step(c, 0.07, 0.0))
        ch['base'] = g.mix(ch['base'], g.rgb(colour), g.mul(joint, amount))
        ch['height'] = g.add(ch['height'], g.mul(joint, -0.8))
    return fn


def boards(w=0.16, amount=0.6):
    """upright boards: a dark joint every `w` m along the wall, every board a shade of its own"""
    def fn(g, ch):
        x, y, z = g.xyz(g.pos())
        f = g.math('DIVIDE', g.add(x, y), w)
        n = g.new('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        g.put(n.inputs['W'], g.math('FLOOR', f))
        ch['base'] = g.mix(ch['base'], g.rgb((0, 0, 0)), g.mul(n.outputs['Value'], 0.3))
        joint = g.step(g.math('FRACT', f), 0.09, 0.0)
        ch['base'] = g.mix(ch['base'], g.rgb('#120c08'), g.mul(joint, amount))
        ch['height'] = g.add(ch['height'], g.mul(joint, -0.8))
    return fn


def slats(h=0.06):
    """a shutter's slats"""
    def fn(g, ch):
        z = g.xyz(g.pos())[2]
        r = g.math('FRACT', g.math('DIVIDE', z, h))
        ch['base'] = g.mix(ch['base'], g.rgb((0, 0, 0)), g.mul(g.step(r, 0.35, 0.0), 0.45))
    return fn


def roof_surface(axis, pitch):
    return PB.surface('roof_tiles', '#8a4330', roughness=0.8, vary=0.14, mottle=0.5, mottle_scale=1.5, mottle_colour='#5a3026', dirt=0.6,
                      streak=0.3, moss=0.45, dust=0.2, custom=tiles(axis, pitch))


def surfaces():
    wood = dict(roughness=0.8, vary=0.14, grain=0.4, grain_scale=60, dirt=0.6, streak=0.4, foot=0.4, foot_h=0.4, wear=0.25, wear_colour='#8a7560')
    return dict(
        plaster=PB.surface('plaster', '#e0d9c8', roughness=0.92, vary=0.08, mottle=0.3, mottle_scale=1.2, mottle_colour='#c9c0ad', grain=0.5,
                           grain_scale=40, dirt=0.75, streak=0.7, streak_scale=3, foot=0.7, foot_h=0.7, foot_colour='#6b6455', moss=0.2),
        plinth=PB.surface('plinth', '#8c877d', roughness=0.9, vary=0.12, mottle=0.5, mottle_scale=4, grain=0.6, grain_scale=40, dirt=0.7,
                          foot=0.8, foot_h=0.35, foot_colour='#4f4a3c', moss=0.5),
        timber=PB.surface('timber', '#4a3426', fibre=(1, 0.08, 1), **wood),
        boards=PB.surface('boards', '#5a4433', fibre=(1, 0.08, 1), custom=boards(), **wood),
        door=PB.surface('door', '#5b3b26', fibre=(1, 0.08, 1), custom=boards(0.11, 0.4), **wood),
        frame=PB.surface('frame', '#e9e6dd', roughness=0.5, vary=0.05, dirt=0.6, streak=0.4),
        stone=PB.surface('stone', '#a8a297', roughness=0.85, vary=0.1, mottle=0.4, mottle_scale=6, dirt=0.7, streak=0.5, moss=0.3),
        shutter=PB.surface('shutter', '#3f5a40', roughness=0.6, vary=0.1, dirt=0.5, streak=0.4, wear=0.3, wear_colour='#7d8a72', custom=slats()),
        brick=PB.surface('brick', '#8a4a38', roughness=0.9, vary=0.14, mottle=0.4, mottle_scale=3, mottle_colour='#4a2c24', dirt=0.6, streak=0.4,
                         custom=courses(0.075, 0.25)),
        zinc=PB.surface('zinc', '#8f9698', metallic=0.7, roughness=0.5, vary=0.1, dirt=0.5, streak=0.4, rust=0.2),
        lit=PB.surface('lit', '#d8b888', roughness=0.25, emit='#ffcf90', vary=0.06, dirt=0.3),
        dark=PB.surface('glass', '#161b20', roughness=0.12, vary=0.03, dirt=0.3),
    )


class Wall:
    """a wall from p0 (x, z: its left end seen from outside) running `along` (unit x / z): u along it, d outwards"""

    def __init__(self, m, p0, along, length):
        self.m, self.p0, self.length = m, p0, length
        self.ax, self.az = along
        self.nx, self.nz = -along[1], along[0]

    def P(self, u, y, d=0.0):
        return (self.p0[0] + self.ax * u + self.nx * d, y, self.p0[1] + self.az * u + self.nz * d)

    def rect(self, mat, u0, u1, y0, y1, d=0.0):
        P = self.P
        self.m.quad(mat, [P(u0, y0, d), P(u1, y0, d), P(u1, y1, d), P(u0, y1, d)])

    def box(self, mat, u0, u1, y0, y1, d0, d1, **kw):
        a, b = self.P(u0, y0, d0), self.P(u1, y1, d1)
        self.m.box(mat, min(a[0], b[0]), max(a[0], b[0]), y0, y1, min(a[2], b[2]), max(a[2], b[2]), **kw)

    def opening(self, mat, cell, hole, depth=REVEAL):
        """the wall of one cell (u0, u1, y0, y1) around a hole (u0, u1, y0, y1), and the hole's four reveals"""
        cu0, cu1, cy0, cy1 = cell
        u0, u1, y0, y1 = hole
        P = self.P
        self.rect(mat, cu0, u0, cy0, cy1)
        self.rect(mat, u1, cu1, cy0, cy1)
        if y0 > cy0:
            self.rect(mat, u0, u1, cy0, y0)
        self.rect(mat, u0, u1, y1, cy1)
        self.m.quad(mat, [P(u0, y0, -depth), P(u0, y1, -depth), P(u0, y1), P(u0, y0)])
        self.m.quad(mat, [P(u1, y0, -depth), P(u1, y0), P(u1, y1), P(u1, y1, -depth)])
        self.m.quad(mat, [P(u0, y0, -depth), P(u0, y0), P(u1, y0), P(u1, y0, -depth)])
        self.m.quad(mat, [P(u0, y1, -depth), P(u1, y1, -depth), P(u1, y1), P(u0, y1)])

    def arched(self, mat, glass, cell, hole, depth=0.3, n=8):
        """the wall of one cell around a round-headed hole (u0, u1, y0, the arch's springing), its reveals, the glass"""
        cu0, cu1, cy0, cy1 = cell
        u0, u1, y0, ys = hole
        P = self.P
        uc, r = (u0 + u1) / 2, (u1 - u0) / 2
        arch = [(uc - r * math.cos(math.pi * k / n), ys + r * math.sin(math.pi * k / n)) for k in range(n + 1)]   # left to right
        self.rect(mat, cu0, u0, cy0, cy1)
        self.rect(mat, u1, cu1, cy0, cy1)
        self.rect(mat, u0, u1, cy0, y0)
        self.m.quad(mat, [P(u, y) for u, y in arch] + [P(u1, cy1), P(u0, cy1)])
        self.m.quad(mat, [P(u0, y0, -depth), P(u0, ys, -depth), P(u0, ys), P(u0, y0)])
        self.m.quad(mat, [P(u1, y0, -depth), P(u1, y0), P(u1, ys), P(u1, ys, -depth)])
        self.m.quad(mat, [P(u0, y0, -depth), P(u0, y0), P(u1, y0), P(u1, y0, -depth)])
        for (ua, ya), (ub, yb) in zip(arch, arch[1:]):
            self.m.quad(mat, [P(ua, ya, -depth), P(ub, yb, -depth), P(ub, yb), P(ua, ya)])
        self.m.quad(glass, [P(u0, y0, -depth), P(u1, y0, -depth)] + [P(u, y, -depth) for u, y in arch[::-1]])

    def brace(self, mat, a, b, w=0.16, t=0.035, d=0.0):
        """a timber lying on the wall (or `d` before it) from a to b ((u, y) each)"""
        self.m.sweep(mat, [self.P(a[0], a[1], d + t / 2), self.P(b[0], b[1], d + t / 2)],
                     [(-w / 2, -t / 2), (w / 2, -t / 2), (w / 2, t / 2), (-w / 2, t / 2)], up=(self.nx, 0, self.nz))


def window(wall, S, cell, state, shutters, w=1.1, y_in=(1.0, 2.3)):
    """one bay's window: cut into the wall, glass, the frame's cross, a sill; shutters open beside it or closed over it"""
    cu0, cu1, cy0, cy1 = cell
    uc = (cu0 + cu1) / 2
    u0, u1, y0, y1 = uc - w / 2, uc + w / 2, cy0 + y_in[0], cy0 + y_in[1]
    wall.opening(S['plaster'], cell, (u0, u1, y0, y1))
    if state == 'shut':
        wall.rect(S['dark'], u0, u1, y0, y1, -REVEAL)
        for a, b in ((u0, uc - 0.01), (uc + 0.01, u1)):
            wall.box(S['shutter'], a, b, y0, y1, -0.07, -0.02)
    else:
        wall.rect(S['lit'] if state == 'lit' else S['dark'], u0, u1, y0, y1, -REVEAL)
        wall.box(S['frame'], uc - 0.035, uc + 0.035, y0, y1, -REVEAL, -REVEAL + 0.05)
        yt = y0 + (y1 - y0) * 0.66
        wall.box(S['frame'], u0, u1, yt - 0.03, yt + 0.03, -REVEAL, -REVEAL + 0.05)
        if shutters:
            for a, b in ((u0 - 0.03 - w / 2, u0 - 0.03), (u1 + 0.03, u1 + 0.03 + w / 2)):
                wall.box(S['shutter'], a, b, y0, y1, 0.0, 0.04)
    wall.box(S['stone'], u0 - 0.07, u1 + 0.07, y0 - 0.07, y0, -REVEAL + 0.02, 0.06)


def build_house(name, W, D, floors, pitch, seed, timber_upper, out, barn=0.0):
    """W across the front (x), D deep (z); ridge along x; barn: share of the length (from +x) that is a timber barn"""
    S = surfaces()
    S['roof'] = roof_surface('x', pitch)
    rnd = random.Random(seed)
    m = K.M(name)
    H = floors * BAY_H
    wx, wz = W / 2, D / 2
    lw = W - W * barn                 # the dwelling's length along the front
    shutters = not timber_upper

    def state():
        r = rnd.random()
        return 'lit' if r < 0.4 else 'dark' if r < 0.78 else 'shut'

    def bays(wall, length, u_from=0.0, door=False):
        n = max(1, round(length / 2.6))
        w = length / n
        for f in range(floors):
            for k in range(n):
                cell = (u_from + k * w, u_from + (k + 1) * w, f * BAY_H, (f + 1) * BAY_H)
                if door and f == 0 and k == n // 2:
                    uc = (cell[0] + cell[1]) / 2
                    wall.opening(S['plaster'], cell, (uc - 0.55, uc + 0.55, 0.36, 2.55), depth=0.2)
                    wall.rect(S['door'], uc - 0.55, uc + 0.55, 0.36, 2.2, -0.2)
                    wall.rect(S['lit'], uc - 0.55, uc + 0.55, 2.2, 2.55, -0.2)                     # fanlight
                    wall.box(S['frame'], uc - 0.55, uc + 0.55, 2.17, 2.23, -0.2, -0.14)
                    wall.box(S['zinc'], uc + 0.36, uc + 0.40, 1.25, 1.45, -0.2, -0.14)           # handle
                    wall.box(S['stone'], uc - 0.95, uc + 0.95, -0.3, 0.18, 0.0, 0.85)            # steps
                    wall.box(S['stone'], uc - 0.75, uc + 0.75, 0.18, 0.36, 0.0, 0.5)
                    wall.box(S['roof'], uc - 0.95, uc + 0.95, 2.72, 2.80, 0.0, 0.75)             # canopy
                    for s in (-1, 1):
                        wall.brace(S['timber'], (uc + s * 0.85, 2.3), (uc + s * 0.85, 2.72), w=0.06, t=0.06)
                    wall.box(S['zinc'], uc + 0.72, uc + 0.84, 1.95, 2.0, 0.0, 0.13)              # the lamp's bracket
                    wall.box(S['lit'], uc + 0.73, uc + 0.83, 2.0, 2.18, 0.03, 0.13)
                else:
                    window(wall, S, cell, state(), shutters and not (timber_upper and f > 0))
        if timber_upper:   # the upper floors' frame: posts between the bays, rails, braces in the end bays
            for f in range(1, floors):
                y = f * BAY_H
                for k in range(n + 1):
                    u = u_from + min(max(k * w, 0.09), length - 0.09)
                    wall.box(S['timber'], u - 0.09, u + 0.09, y, y + BAY_H, 0.0, 0.035)
                for ya, yb in ((y, y + 0.2), (y + 0.82, y + 0.98), (y + 2.32, y + 2.46), (y + BAY_H - 0.2, y + BAY_H)):
                    for k in range(n):
                        wall.box(S['timber'], u_from + k * w + 0.09, u_from + (k + 1) * w - 0.09, ya, yb, 0.0, 0.03)
                for k in range(n):
                    uc = u_from + (k + 0.5) * w
                    for u in (uc - 0.64, uc + 0.64):
                        wall.box(S['timber'], u - 0.06, u + 0.06, y + 0.98, y + 2.32, 0.0, 0.03)
                for k, s in ((0, 1), (n - 1, -1)):
                    ua = u_from + (k + 0.5 - s * 0.42) * w
                    wall.brace(S['timber'], (ua, y + 0.2), (ua + s * 0.55, y + 0.82), w=0.13, t=0.03)

    front = Wall(m, (-wx, wz), (1, 0), W)
    back = Wall(m, (wx, -wz), (-1, 0), W)
    right = Wall(m, (wx, wz), (0, -1), D)        # the +X end
    left = Wall(m, (-wx, -wz), (0, 1), D)
    bays(front, lw, 0.0, door=True)
    bays(back, lw, W - lw)
    bays(left, D)
    if barn:
        # the barn: boarded walls, the big double door with its braces at the front
        bw = W * barn
        front.rect(S['boards'], lw, W, 0.0, H)
        back.rect(S['boards'], 0.0, bw, 0.0, H)
        right.rect(S['boards'], 0.0, D, 0.0, H)
        uc = lw + bw / 2
        front.box(S['timber'], uc - 1.95, uc + 1.95, 0.0, 3.5, 0.0, 0.05)
        for s in (-1, 1):
            a, b = sorted((uc + s * 0.02, uc + s * 1.85))
            front.box(S['door'], a, b, 0.05, 3.4, 0.05, 0.10)
            front.brace(S['timber'], (a + 0.08, 0.3), (b - 0.08, 1.65), w=0.14, t=0.035, d=0.10)
            front.brace(S['timber'], (a + 0.08, 3.1), (b - 0.08, 1.75), w=0.14, t=0.035, d=0.10)
            for y in (0.25, 1.7, 3.15):
                front.box(S['timber'], a, b, y - 0.07, y + 0.07, 0.10, 0.135)
        right.box(S['door'], D / 2 - 0.5, D / 2 + 0.5, H - 1.5, H - 0.5, 0.0, 0.05)     # the loft's hatch
        right.box(S['timber'], D / 2 - 0.58, D / 2 + 0.58, H - 1.58, H - 0.42, 0.0, 0.03)
    else:
        bays(right, D)
    # gables at the ends of the ridge, each with its attic window
    rise = wz * math.tan(math.radians(pitch))
    for wall, boarded in ((right, bool(barn)), (left, False)):
        mat = S['boards'] if boarded else S['plaster']
        m.quad(mat, [wall.P(0, H), wall.P(D, H), wall.P(D / 2, H + rise)])
        if not boarded:
            wall.box(S['frame'], D / 2 - 0.5, D / 2 + 0.5, H + 0.9, H + 2.1, 0.0, 0.04)
            wall.box(S['lit'] if rnd.random() < 0.3 else S['dark'], D / 2 - 0.42, D / 2 + 0.42, H + 0.98, H + 2.02, 0.0, 0.08)
            wall.box(S['stone'], D / 2 - 0.58, D / 2 + 0.58, H + 0.82, H + 0.9, 0.0, 0.1)
        if timber_upper and not boarded:
            wall.box(S['timber'], 0.0, D, H - 0.1, H + 0.12, 0.0, 0.035)
            for u in (D * 0.25, D * 0.75, D / 2 - 0.62, D / 2 + 0.62):
                top = H + rise * (1 - abs(u - D / 2) / (D / 2)) - 0.25
                wall.box(S['timber'], u - 0.08, u + 0.08, H + 0.12, top, 0.0, 0.03)
            yc = H + rise * 0.56
            half = (D / 2) * (1 - 0.56) - 0.15
            wall.box(S['timber'], D / 2 - half, D / 2 + half, yc - 0.08, yc + 0.08, 0.0, 0.03)
    # the plinth, into the ground
    m.box(S['plinth'], -wx - 0.05, wx + 0.05, -0.6, 0.5, -wz - 0.05, wz + 0.05)
    # roof: a slab with overhangs, as a closed loft along x; ridge tiles; a bargeboard under each verge
    o, t = 0.55, 0.22
    ye = H - o * math.tan(math.radians(pitch))
    prof = [(wz + o, ye), (wz + o, ye + t), (0, H + rise + t * 1.2), (-wz - o, ye + t), (-wz - o, ye), (0, H + rise)]
    ring = lambda x: [(x, y, z) for z, y in prof]  # noqa: E731
    with m.dense(0.8):
        m.loft(S['roof'], [ring(-wx - 0.45), ring(wx + 0.45)])
    m.tube(S['roof'], [(-wx - 0.47, H + rise + t * 1.2 - 0.03, 0), (wx + 0.47, H + rise + t * 1.2 - 0.03, 0)], 0.13, seg=8)
    # gutters along both eaves, a downpipe at two corners
    for s in (-1, 1):
        zg = s * (wz + o + 0.07)
        arc = [(0.075 * math.cos(math.radians(a)), 0.075 * math.sin(math.radians(a))) for a in range(180, 361, 36)]
        arc += [(0.06 * math.cos(math.radians(a)), 0.06 * math.sin(math.radians(a))) for a in range(360, 179, -36)]
        m.sweep(S['zinc'], [(-wx - 0.45, ye + 0.03, zg), (wx + 0.45, ye + 0.03, zg)], arc)
        xd = s * (wx - 0.25)
        m.tube(S['zinc'], [(xd, ye - 0.04, zg), (xd, ye - 0.3, zg), (xd, ye - 0.75, s * (wz + 0.09)), (xd, 0.1, s * (wz + 0.09))], 0.045, seg=8)
    # the chimney: brick, a concrete cap
    cx = rnd.uniform(-wx * 0.5, wx * 0.3) - (W * barn) / 2
    cz = -wz * 0.3
    top = H + rise + 0.95
    m.box(S['brick'], cx - 0.32, cx + 0.32, H + rise * 0.45, top, cz - 0.32, cz + 0.32)
    m.box(S['stone'], cx - 0.38, cx + 0.38, top, top + 0.08, cz - 0.38, cz + 0.38)
    m.box(S['dark'], cx - 0.2, cx + 0.2, top + 0.08, top + 0.1, cz - 0.2, cz + 0.2)
    ob = m.build(sharp=30)
    PB.finish([ob], out, name, size=1024, orm_size=512, normal_size=512, emit_size=256, near=0.3, wide=2.0, edge=0.03, max_len=6.0,
              margin=0.002)
    return [ob]


def build(out):
    return build_house('village_house', 10.0, 9.0, 2, 46, 11, False, out)


SPEC = K.Spec('village_house.glb', build, [
    dict(name='front', eye=(9.0, 5.0, 18.0), target=(0, 4.0, 0), lens=35),
    dict(name='back', eye=(-12.0, 6.0, -16.0), target=(0, 4.0, 0), lens=35),
    dict(name='night', eye=(9.0, 5.0, 18.0), target=(0, 4.0, 0), lens=35, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
