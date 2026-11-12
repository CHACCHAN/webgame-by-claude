"""
Street light (a Japanese road-lighting pole on a mountain road): a hot-dip galvanised tapered steel pole, bent over
into its own arm along -X (the usual one-piece pole), standing with a base plate on four anchor bolts on a concrete
footing; a hand-hole door for the gear, the road office's number plate strapped on; at the arm's end a cobra-head
luminaire (cast aluminium shell, hinged frame with its latch, a prismatic glass bowl) tipped up 5 degrees.
7.6 m to the top, the bowl 2.4 m out from the pole; origin at the foot of the pole on the ground.

    blender -t 4 --background --factory-startup --python street_light.py -- --out <dir> [--render <dir>]

One material, baked (prop_bake): the bowl is the only thing in the emissive map (white = lit), which the game tints
per lamp colour (sodium / LED).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

TILT = math.radians(5)
PLATE_TOP = 0.10
BEND_Y = 6.26                    # where the pole starts to bend over
END = (-1.86, 7.50)              # the bend's end; the arm runs on straight for the luminaire's sleeve
R0, R1 = 0.095, 0.038            # the pipe's radius at the plate and at the arm's end
NECK = (-1.92, 7.505)            # where the luminaire's body begins
HEAD_L = 0.80
LENS_U, LENS_A, LENS_B = 0.49, 0.215, 0.115   # the bowl: centre along the head, half length, half width


def arm_path():
    dx, dy = -math.cos(TILT), math.sin(TILT)
    p2 = (END[0] - dx * 1.2, END[1] - dy * 1.2, 0)
    pts = [(0, PLATE_TOP, 0), (0, 0.5, 0), (0, 1.2, 0), (0, 2.4, 0), (0, 3.6, 0), (0, 4.8, 0), (0, 5.6, 0)]
    pts += K.bezier((0, BEND_Y, 0), (0, BEND_Y + 0.98, 0), p2, (END[0], END[1], 0), 14)
    pts.append((END[0] + dx * 0.20, END[1] + dy * 0.20, 0))
    return pts


def head_point(u, v, w):
    """the luminaire's own frame (u out along it, v up, w across) → game frame, before the tilt"""
    return (NECK[0] - u, NECK[1] + v, w)


def head_ring(u, hw, ht, rim, bot, n=9):
    """a cross-section of the shell: an arch over the rim line, a flat belly below"""
    pts = []
    for i in range(n):
        a = math.pi * i / (n - 1)
        pts.append(head_point(u, rim + ht * math.sin(a) ** 0.8, hw * math.cos(a)))
    pts += [head_point(u, bot, -hw * 0.9), head_point(u, bot, hw * 0.9)]
    return pts


def ellipse(u0, a, b, v, n=24):
    return [head_point(u0 + a * math.cos(2 * math.pi * k / n), v, b * math.sin(2 * math.pi * k / n)) for k in range(n)]


def build(out):
    d = K.paint(out, ['pole'])
    tag = K.load_image(os.path.join(d, 'pole_tag.png'))
    zinc = PB.surface('zinc', '#a3a8a8', metallic=0.6, roughness=0.5, vary=0.09, mottle=0.4, mottle_scale=26, mottle_colour='#8a8f90',
                      mottle_rough=0.62, dirt=0.55, streak=0.4, foot=0.55, foot_h=0.45, rust=0.14, grain=0.12, grain_scale=220)
    nuts = PB.surface('nuts', '#8d9090', metallic=0.7, roughness=0.55, dirt=0.7, rust=0.75, foot=0.5, foot_h=0.3)
    cast = PB.surface('cast', '#8b9193', metallic=0.2, roughness=0.48, vary=0.06, dirt=0.65, streak=0.35, dust=0.3, wear=0.35,
                      wear_colour='#b9bdbd', wear_metal=0.9, grain=0.2, grain_scale=300)
    conc = PB.surface('concrete', '#8d8c85', roughness=0.9, vary=0.14, mottle=0.45, mottle_scale=30, grain=0.9, grain_scale=160,
                      dirt=0.7, foot=0.7, foot_h=0.07, moss=0.5)
    label = PB.surface('label', '#ffffff', roughness=0.42, image=tag, dirt=0.5, streak=0.35, vary=0.04)

    cx, cy, cz = head_point(LENS_U, -0.10, 0.0)

    def prisms(g, ch):
        # the bowl's prism rings, and the lamp behind it: brightest in the middle
        x = g.xyz(g.pos())[0]
        ring = g.math('ABSOLUTE', g.math('SINE', g.mul(x, 2 * math.pi / 0.022)))
        v = g.scaled(g.pos(), (1 / LENS_A, 1 / LENS_B, 1 / 0.12), (-cx / LENS_A, cz / LENS_B, -cy / 0.12))
        ln = g.new('ShaderNodeVectorMath', operation='LENGTH')
        g.put(ln.inputs[0], v)
        centre = g.step(ln.outputs['Value'], 1.25, 0.1)
        ch['emit'] = g.mix(g.rgb((0, 0, 0)), g.rgb((1, 1, 1)), g.mul(g.add(0.5, g.mul(centre, 0.5)), g.add(0.8, g.mul(ring, 0.2))))
        ch['base'] = g.mix(ch['base'], g.rgb('#7d837f'), g.mul(ring, 0.25))
        ch['height'] = g.add(ch['height'], g.mul(ring, 0.5))

    lens = PB.surface('lens', '#c2c7c1', roughness=0.16, emit='#ffffff', dirt=0.25, vary=0.03, rough_vary=0.04, custom=prisms)

    m = K.M('street_light')
    # --- footing, grout, base plate, anchor bolts, gussets
    m.box(conc, -0.31, 0.31, 0.0, 0.06, -0.31, 0.31, bevel=0.012, seg=1)
    m.box(conc, -0.225, 0.225, 0.055, 0.076, -0.225, 0.225, bevel=0.008, seg=1)
    m.box(zinc, -0.20, 0.20, 0.075, PLATE_TOP, -0.20, 0.20, bevel=0.004, seg=1)
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.bolt(nuts, (sx * 0.152, PLATE_TOP, sz * 0.152), (0, 1, 0), r=0.024, h=0.022, washer=0.034, stud=0.03)
    for k in range(4):
        with m.at(K.rot_y(math.pi / 2 * k + math.pi / 4)):
            tri = [(R0 - 0.004, PLATE_TOP), (R0 + 0.10, PLATE_TOP), (R0 + 0.10, PLATE_TOP + 0.02), (R0 - 0.004, PLATE_TOP + 0.17)]
            m.loft(zinc, [[(a, b, -0.006) for a, b in tri], [(a, b, 0.006) for a, b in tri]])
    # --- the pole and its arm: one tapered pipe
    path = arm_path()
    seglen = [0.0]
    for a, b in zip(path, path[1:]):
        seglen.append(seglen[-1] + math.dist(a, b))
    scales = [1.0 + (R1 / R0 - 1.0) * s / seglen[-1] for s in seglen]
    m.sweep(zinc, path, K.circle_pts(0, 0, R0, 16), up=(0, 0, 1), scales=scales)
    m.cyl(zinc, (0, PLATE_TOP, 0), (0, PLATE_TOP + 0.012, 0), R0 + 0.012, R0 + 0.002, seg=16)          # the weld at the plate
    rj = R0 * (1.0 + (R1 / R0 - 1.0) * 4.4 / seglen[-1])
    m.lathe(zinc, [(rj + 0.001, 4.36), (rj + 0.007, 4.375), (rj + 0.006, 4.60), (rj - 0.002, 4.615)], seg=16)  # sleeve joint
    # hand hole: a door let into the pole, its frame, the screw that holds it
    m.box(zinc, -0.058, 0.058, 0.52, 0.96, 0.066, 0.094, bevel=0.01, seg=2)
    m.box(zinc, -0.047, 0.047, 0.535, 0.945, 0.07, 0.099, bevel=0.006, seg=1)
    m.bolt(nuts, (0, 0.90, 0.099), (0, 0, 1), r=0.009, h=0.006)
    m.box(nuts, -0.012, 0.012, 0.70, 0.745, 0.099, 0.106, bevel=0.002, seg=1)
    # the number plate, strapped on with two steel bands, facing the road
    rp = R0 * (1.0 + (R1 / R0 - 1.0) * 1.7 / seglen[-1])
    for y in (1.62, 1.76):
        m.cyl(nuts, (0, y - 0.006, 0), (0, y + 0.006, 0), rp + 0.0025, seg=16, caps=(False, False))
    m.box(zinc, -rp - 0.006, -rp - 0.002, 1.60, 1.78, -0.045, 0.045)
    with m.dense(4):
        with m.uvmap(lambda cs: [((c.z + 0.0425) / 0.085, (c.y - 1.605) / 0.17) for c in cs], only=label):
            m.quad(label, [(-rp - 0.0065, 1.605, -0.0425), (-rp - 0.0065, 1.605, 0.0425), (-rp - 0.0065, 1.775, 0.0425), (-rp - 0.0065, 1.775, -0.0425)], flip=True)
    # --- the luminaire, tipped up about its neck
    with m.at(K.move(NECK[0], NECK[1], 0) @ K.rot_z(-TILT) @ K.move(-NECK[0], -NECK[1], 0)):
        # slip fitter over the arm's end, its two clamp bolts
        m.cyl(cast, head_point(-0.13, 0, 0), head_point(0.05, 0, 0), 0.05, 0.052, seg=14)
        m.cyl(cast, head_point(-0.14, 0, 0), head_point(-0.125, 0, 0), 0.056, seg=14)
        for u in (-0.09, -0.03):
            m.bolt(nuts, head_point(u, 0.048, 0), (0, 1, 0), r=0.011, h=0.012)
        rings = [head_ring(*r) for r in (
            (0.00, 0.056, 0.052, 0.000, -0.050), (0.07, 0.080, 0.064, -0.004, -0.058), (0.16, 0.118, 0.082, -0.010, -0.068),
            (0.27, 0.152, 0.098, -0.016, -0.074), (0.40, 0.170, 0.104, -0.020, -0.076), (0.53, 0.170, 0.098, -0.020, -0.076),
            (0.64, 0.150, 0.082, -0.020, -0.073), (0.72, 0.116, 0.062, -0.020, -0.068), (0.775, 0.070, 0.038, -0.020, -0.058),
            (HEAD_L, 0.030, 0.016, -0.020, -0.040))]
        m.loft(cast, rings)
        # the hinged frame under it, the hinge at the neck's end, the latch at the tip
        m.loft(cast, [ellipse(LENS_U, 0.25, 0.142, -0.074), ellipse(LENS_U, 0.25, 0.142, -0.088), ellipse(LENS_U, 0.232, 0.128, -0.092)], cap0=False)
        m.cyl(cast, head_point(0.215, -0.082, -0.07), head_point(0.215, -0.082, 0.07), 0.008, seg=8)
        m.box(cast, NECK[0] - 0.775, NECK[0] - 0.735, NECK[1] - 0.10, NECK[1] - 0.05, -0.022, 0.022, bevel=0.004, seg=1)
        # the glass bowl
        bowl = [(1.0, -0.090), (0.985, -0.108), (0.93, -0.128), (0.80, -0.146), (0.58, -0.158), (0.30, -0.164)]
        with m.dense(1.5):
            m.loft(lens, [ellipse(LENS_U, LENS_A * s, LENS_B * s, v) for s, v in bowl], cap0=False)
    ob = m.build()
    PB.finish([ob], out, 'street_light', size=1024, orm_size=512, emit_size=256, near=0.08, wide=0.5, edge=0.01)
    return [ob]


SPEC = K.Spec('street_light.glb', build, [
    dict(name='main', eye=(-2.5, 3.9, 11.0), target=(-1.0, 3.8, 0), lens=35, size=(540, 720)),
    dict(name='close', eye=(-4.6, 5.6, 2.6), target=(-2.2, 7.35, 0), lens=45),
    dict(name='under', eye=(-2.3, 4.6, 2.2), target=(-2.4, 7.3, 0), lens=45),
    dict(name='foot', eye=(-1.6, 1.3, 2.2), target=(0, 0.7, 0), lens=40),
    dict(name='night', eye=(-5.6, 4.6, 3.6), target=(-1.8, 7.0, 0), lens=45, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
