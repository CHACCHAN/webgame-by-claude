"""
Vending machine (a Japanese outdoor drink machine, generic: no brands, logos or real product names): 1.0 x 0.75 m,
1.83 m tall, as they are built: a steel cabinet on levelling feet behind a kick plate, a thick door on three hinges
with its gasket line; in the door a lit display case with three rows of nine samples (PET bottles, cans, short cans)
on shelves, under each its price tag and its lit button (blue = cold, red = hot); below, a poster, the payment panel
(price display, bill validator, coin slot, return lever, IC pad), the take-out port, the change cup, the lock. Behind:
the condenser's louvres, a service plate, the power cable into its conduit. On the side the address sticker every
machine carries. It stands on a concrete pad, held by two tip-over brackets.
Origin at the centre of the footprint on the ground, the front towards +Z; the pad reaches 0.15 m into the ground.

    blender -t 4 --background --factory-startup --python vending_machine.py -- --out <dir> [--render <dir>]

Textures in (painted by paint.py, no photo pixels): the front elevation, what of it is lit, the samples' labels, the
sticker. Out: one baked material (prop_bake); its emissive map holds the display case, the samples, the buttons and
the price display, which the game turns up at night.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

PAD = 0.04                 # the pad's top above the ground: the machine's own heights start there
ZF, ZD, ZC = 0.375, 0.262, 0.285   # the door's face, its back, the display case's back wall
ZS = 0.327                 # where the samples stand
# layout shared with paint.py
WIN = (-0.43, 0.43, 0.86, 1.70)
ROWS = [1.42, 1.14, 0.86]
NCOL = 9
COLS = [WIN[0] + (WIN[1] - WIN[0]) * (i + 0.5) / NCOL for i in range(NCOL)]
CELL_W, CELL_H = 64, 200
ATLAS_X, ATLAS_Y, ATLAS_DX, ATLAS_DY = 8, 8, 66, 202
LABELS = 640

# lathe profiles (radius, y): a 500 ml PET bottle, a 350 ml can, a 190 ml can
BOTTLE = [(0.027, 0), (0.032, 0.008), (0.032, 0.045), (0.0302, 0.055), (0.032, 0.065), (0.032, 0.125), (0.029, 0.142),
          (0.014, 0.182), (0.0135, 0.186), (0.0155, 0.188), (0.0155, 0.203), (0.012, 0.205)]
CAN = [(0.026, 0.0), (0.033, 0.008), (0.033, 0.112), (0.028, 0.120), (0.027, 0.122)]
SHORT = [(0.021, 0.0), (0.0265, 0.006), (0.0265, 0.097), (0.023, 0.104)]


def uv_px(px, py):
    return (px / LABELS, 1 - py / LABELS)


def plate_uv(p, n):
    """the front elevation: x -0.5..0.5, y 0..1.83 (above the pad) over the whole picture"""
    return (p.x + 0.5, (p.y - PAD) / 1.83)


def drink_uv(cx, cz, ybase, h, col, row):
    x0, y0 = ATLAS_X + ATLAS_DX * col, ATLAS_Y + ATLAS_DY * row

    def fn(cs):
        if all(abs(c.y - cs[0].y) < 1e-6 for c in cs):   # a cap
            top = cs[0].y > ybase + h * 0.5
            return [uv_px(x0 + CELL_W / 2, y0 + (10 if top else 196))] * len(cs)
        out = []
        ref = None
        for c in cs:
            t = math.atan2(c.x - cx, c.z - cz) / (2 * math.pi) + 0.5   # 0.5 = the front (+Z), the seam at the back
            if ref is None:
                ref = t
            elif t - ref > 0.5:
                t -= 1
            elif t - ref < -0.5:
                t += 1
            out.append(uv_px(x0 + t * CELL_W, y0 + (1 - (c.y - ybase) / h) * CELL_H))
        return out
    return fn


def build(out):
    d = K.paint(out, ['vending'])
    img = {n: K.load_image(os.path.join(d, f'vending_{n}.png')) for n in ('plate', 'emit', 'labels', 'sticker')}
    body = PB.surface('body', '#e2e5e8', roughness=0.38, vary=0.04, dirt=0.6, streak=0.5, dust=0.4, foot=0.55, foot_h=0.5,
                      rust=0.12, wear=0.25, wear_colour='#b4b8bc', grain=0.06, grain_scale=260)
    front = PB.surface('front', '#ffffff', roughness=0.36, image=img['plate'], emit_image=img['emit'], vary=0.02, dirt=0.45,
                       streak=0.22, foot=0.4, foot_h=0.4)

    def lit_case(g, ch):
        # the case's own lamps: less light where the samples and shelves stand in its way
        ch['emit'] = g.mix(g.rgb((0, 0, 0)), g.rgb('#eef3ff'), g.add(0.3, g.mul(ch['occ'], 0.6)))

    case = PB.surface('case', '#f1f3f4', roughness=0.5, emit='#eef3ff', vary=0.02, dirt=0.3, custom=lit_case)
    sample = PB.surface('sample', '#ffffff', roughness=0.3, image=img['labels'], emit_image=img['labels'], emit_strength=0.75,
                        vary=0.0, dirt=0.15)
    trim = PB.surface('trim', '#2a2e34', roughness=0.5, vary=0.05, dirt=0.4, dust=0.35, wear=0.3, wear_colour='#5c626a', foot=0.5,
                      foot_h=0.14)
    rubber = PB.surface('rubber', '#131415', roughness=0.8, dirt=0.3)
    zinc = PB.surface('zinc', '#a3a8a8', metallic=0.7, roughness=0.45, rust=0.4, dirt=0.5, foot=0.4, foot_h=0.1)
    conc = PB.surface('concrete', '#8d8c85', roughness=0.9, vary=0.14, mottle=0.45, mottle_scale=30, grain=0.9, grain_scale=160,
                      dirt=0.7, foot=0.6, foot_h=0.05, moss=0.45)
    pit = PB.surface('pit', '#07080a', roughness=0.9, dirt=0.0, vary=0.0)
    led = PB.surface('led', '#ffffff', roughness=0.3, emit='#ffffff', dirt=0.0, vary=0.0)
    sticker = PB.surface('sticker', '#ffffff', roughness=0.4, image=img['sticker'], dirt=0.45, streak=0.35, vary=0.03)

    m = K.M('vending_machine')
    # --- the pad it stands on (into the ground: the shoulder is not level)
    with m.dense(0.6):
        m.box(conc, -0.57, 0.57, -0.15, PAD, -0.45, 0.52, bevel=0.012, seg=1)
    with m.at(K.move(0, PAD, 0)):
        # --- feet, kick plate, tip-over brackets with their anchors
        for sx in (-1, 1):
            for z in (-0.31, 0.30):
                m.cyl(zinc, (sx * 0.44, 0, z), (sx * 0.44, 0.006, z), 0.03, seg=10)
                m.cyl(zinc, (sx * 0.44, 0.006, z), (sx * 0.44, 0.03, z), 0.011, seg=8, caps=(False, False))
            m.box(zinc, sx * 0.40 - 0.03, sx * 0.40 + 0.03, 0.0, 0.005, 0.36, 0.47)
            m.box(zinc, sx * 0.40 - 0.03, sx * 0.40 + 0.03, 0.0, 0.075, 0.366, 0.371)
            m.bolt(zinc, (sx * 0.40, 0.005, 0.435), (0, 1, 0), r=0.011, h=0.01, washer=0.016, stud=0.012)
            m.bolt(zinc, (sx * 0.40, 0.055, 0.371), (0, 0, 1), r=0.008, h=0.006)
        m.box(trim, -0.492, 0.492, 0.02, 0.102, -0.36, 0.366, bevel=0.004, seg=1)
        # --- cabinet, gasket, hinges
        m.box(body, -0.5, 0.5, 0.10, 1.83, -0.375, 0.255, bevel=0.012, seg=2)
        m.box(rubber, -0.493, 0.493, 0.107, 1.823, 0.25, 0.266)
        for y in (0.30, 0.96, 1.62):
            m.cyl(zinc, (-0.508, y - 0.045, 0.259), (-0.508, y + 0.045, 0.259), 0.009, seg=8)
        # --- the door: header, the window's two stiles, the lower half; what looks forward takes the painted elevation
        with m.dense(2.0):
            m.box(body, -0.5, 0.5, 1.70, 1.83, ZD, ZF, bevel=0.01, seg=2, front=front)
            for x0, x1 in ((-0.5, WIN[0]), (WIN[1], 0.5)):
                m.box(body, x0, x1, WIN[2], WIN[3], ZD, ZF - 0.002, bevel=0.006, seg=1, front=front)
            m.box(body, -0.5, 0.5, 0.10, 0.86, ZD, ZF, bevel=0.01, seg=2, front=front)
        # --- the display case: lit walls, a lamp bar under its top, shelves; samples, price strips, buttons
        m.box(case, WIN[0], WIN[1], WIN[2], WIN[3], ZC - 0.004, ZC)
        m.box(case, WIN[0], WIN[0] + 0.004, WIN[2], WIN[3], ZC, ZF - 0.004)
        m.box(case, WIN[1] - 0.004, WIN[1], WIN[2], WIN[3], ZC, ZF - 0.004)
        m.box(case, WIN[0], WIN[1], WIN[3] - 0.004, WIN[3], ZC, ZF - 0.004)
        m.box(led, WIN[0] + 0.02, WIN[1] - 0.02, WIN[3] - 0.02, WIN[3] - 0.006, ZF - 0.03, ZF - 0.012)
        kinds = [(BOTTLE, 0.205), (CAN, 0.122), (SHORT, 0.104)]
        for row, (yb, (prof, h)) in enumerate(zip(ROWS, kinds)):
            with m.dense(2.0):
                m.box(trim, WIN[0], WIN[1], yb, yb + 0.05, ZC, ZF - 0.006, front=front)
                for cx in COLS:
                    m.box(trim, cx - 0.034, cx + 0.034, yb + 0.0045, yb + 0.0225, ZF - 0.007, ZF - 0.001, bevel=0.002, seg=1, front=front)
            m.box(case, WIN[0], WIN[1], yb + 0.05, yb + 0.058, ZC, ZF - 0.012)
            ybase = yb + 0.058
            with m.dense(2.0):
                for col, cx in enumerate(COLS):
                    with m.uvmap(drink_uv(cx, ZS, ybase, h, col, row), only=sample):
                        m.lathe(sample, [(r, ybase + y) for r, y in prof], seg=10, cx=cx, cz=ZS)
        # --- payment panel: a raised plate, the bill validator, the coin slot, the return lever
        with m.dense(2.0):
            m.box(body, 0.14, 0.455, 0.52, 0.84, ZF - 0.002, ZF + 0.004, bevel=0.003, seg=1, front=front)
        m.box(trim, 0.255, 0.425, 0.724, 0.766, ZF + 0.003, ZF + 0.02, bevel=0.004, seg=1)
        m.box(pit, 0.272, 0.408, 0.741, 0.749, ZF + 0.019, ZF + 0.0205)
        m.box(zinc, 0.30, 0.38, 0.648, 0.698, ZF + 0.003, ZF + 0.011, bevel=0.003, seg=1)
        m.box(pit, 0.3365, 0.3435, 0.655, 0.691, ZF + 0.0105, ZF + 0.0115)
        m.cyl(zinc, (0.36, 0.575, ZF + 0.003), (0.36, 0.575, ZF + 0.016), 0.017, seg=12)
        m.box(zinc, 0.353, 0.367, 0.552, 0.598, ZF + 0.016, ZF + 0.024, bevel=0.002, seg=1)
        # --- take-out port and change cup: frames standing out of the door; the lock
        for (x0, x1, y0, y1, t, h) in ((-0.425, 0.225, 0.135, 0.445, 0.024, 0.01), (0.28, 0.42, 0.30, 0.40, 0.012, 0.007)):
            m.box(trim, x0, x1, y1 - t, y1, ZF - 0.002, ZF + h, bevel=0.003, seg=1)
            m.box(trim, x0, x1, y0, y0 + t, ZF - 0.002, ZF + h, bevel=0.003, seg=1)
            m.box(trim, x0, x0 + t, y0 + t, y1 - t, ZF - 0.002, ZF + h, bevel=0.003, seg=1)
            m.box(trim, x1 - t, x1, y0 + t, y1 - t, ZF - 0.002, ZF + h, bevel=0.003, seg=1)
        m.cyl(zinc, (0.35, 0.225, ZF), (0.35, 0.225, ZF + 0.012), 0.021, 0.018, seg=12)
        m.box(pit, 0.3485, 0.3515, 0.214, 0.236, ZF + 0.0115, ZF + 0.0125)
        # --- the back: louvres over the condenser, a service plate, the cable into its conduit
        with m.dense(0.7):
            m.box(pit, -0.40, 0.40, 0.17, 0.75, -0.378, -0.374)
            for (x0, x1, y0, y1) in ((-0.44, 0.44, 0.75, 0.78), (-0.44, 0.44, 0.14, 0.17), (-0.44, -0.40, 0.17, 0.75), (0.40, 0.44, 0.17, 0.75)):
                m.box(body, x0, x1, y0, y1, -0.39, -0.374, bevel=0.003, seg=1)
            for k in range(13):
                y = 0.19 + k * 0.045
                with m.at(K.move(0, y, -0.383) @ K.rot_x(math.radians(-38))):
                    m.box(body, -0.40, 0.40, -0.002, 0.002, -0.017, 0.017)
            m.box(body, -0.30, 0.30, 1.02, 1.62, -0.379, -0.374, bevel=0.002, seg=1)
            for sx in (-0.27, 0.27):
                for y in (1.05, 1.59):
                    m.bolt(zinc, (sx, y, -0.379), (0, 0, -1), r=0.007, h=0.004)
        m.tube(rubber, [(0.36, 0.26, -0.372), (0.36, 0.25, -0.40), (0.36, 0.20, -0.415), (0.36, 0.06, -0.42), (0.36, -0.03, -0.42)], 0.009, seg=8)
        m.cyl(zinc, (0.36, -0.04, -0.42), (0.36, 0.05, -0.42), 0.016, seg=10)
        # --- the address sticker, on both sides near the front
        with m.dense(3.0):
            y0, y1, z0, z1 = 1.36, 1.435, 0.02, 0.22
            with m.uvmap(lambda cs: [((z1 - c.z) / (z1 - z0), (c.y - PAD - y0) / (y1 - y0)) for c in cs], only=sticker):
                m.quad(sticker, [(0.5006, y0, z1), (0.5006, y0, z0), (0.5006, y1, z0), (0.5006, y1, z1)])
            with m.uvmap(lambda cs: [((c.z - z0) / (z1 - z0), (c.y - PAD - y0) / (y1 - y0)) for c in cs], only=sticker):
                m.quad(sticker, [(-0.5006, y0, z0), (-0.5006, y0, z1), (-0.5006, y1, z1), (-0.5006, y1, z0)])
    m.uv(front, plate_uv)
    ob = m.build(sharp=40)
    PB.finish([ob], out, 'vending_machine', size=2048, orm_size=1024, emit_size=1024, normal_size=1024, near=0.05, wide=0.35, edge=0.008, max_len=2.0)
    return [ob]


SPEC = K.Spec('vending_machine.glb', build, [
    dict(name='main', eye=(-1.5, 1.5, 3.4), target=(0, 0.95, 0), lens=40, size=(540, 720)),
    dict(name='front', eye=(0, 1.0, 3.2), target=(0, 0.97, 0), lens=40, size=(540, 720)),
    dict(name='close', eye=(-0.45, 1.45, 1.5), target=(-0.1, 1.2, 0.3), lens=40),
    dict(name='back', eye=(1.6, 1.5, -3.2), target=(0, 0.9, 0), lens=40, size=(540, 720)),
    dict(name='night', eye=(-1.5, 1.5, 3.4), target=(0, 0.95, 0), lens=40, size=(540, 720), night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
