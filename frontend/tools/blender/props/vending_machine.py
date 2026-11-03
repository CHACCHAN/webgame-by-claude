"""
Vending machine (Japanese drink machine, generic: no brands, logos or product names): 1.0 x 0.75 m, 1.83 m tall.
Body + front plate, a framed display window with three shelves of drinks modelled in 3D (PET bottles, cans, short
cans; their labels are cells of the same texture), price tags, 18 selection buttons, bill / coin slots, return
lever and cup, dispensing flap. Origin at the centre of the footprint, the front towards +Z.

    blender -t 4 --background --factory-startup --python vending_machine.py -- --out <dir> [--render <dir>]

Texture: vending.png (1024 px, painted by paint.py, no photo pixels): the front plate and the label atlas. It is the
base colour and the emissive map of the `front` material (Emission Strength 1); the other materials do not glow.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

ZF = 0.375
S = 1024 / 1.83
# layout shared with paint.py
WIN = (-0.46, 0.14, 0.60, 1.62)
ROWS = [1.28, 0.94, 0.60]
COLS = [-0.46 + 0.05 + 0.1 * i for i in range(6)]
CELL_W, CELL_H = 64, 200
ATLAS_X, ATLAS_Y, ATLAS_DX, ATLAS_DY = 608, 8, 66, 202

# lathe profiles (radius, y) of the three kinds of drink
BOTTLE_S = 0.225 / 0.27
BOTTLE = [(r * BOTTLE_S, y * BOTTLE_S) for r, y in [(0.028, 0), (0.034, 0.012), (0.034, 0.17), (0.0145, 0.232), (0.0145, 0.236),
                                                    (0.0165, 0.238), (0.0165, 0.268), (0.0125, 0.27)]]
CAN = [(0.032, 0.0), (0.038, 0.010), (0.038, 0.135), (0.032, 0.145)]
SHORT = [(0.034, 0.0), (0.040, 0.009), (0.040, 0.106), (0.034, 0.115)]


def cell_uv0(col, row):
    return ATLAS_X + ATLAS_DX * col, ATLAS_Y + ATLAS_DY * row


def uv_px(px, py):
    return (px / 1024, 1 - py / 1024)


def plate_uv(p, n):
    """the front plate: x -0.5..0.5 → 0..576 px, y 1.83..0 → 0..1024 px"""
    return ((p.x + 0.5) * 576 / 1024, p.y / 1.83)


def drink_uv(cx, cz, ybase, h, col, row):
    x0, y0 = cell_uv0(col, row)

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


def const_uv(px, py):
    return lambda cs: [uv_px(px, py)] * len(cs)


def build(out):
    d = K.paint(out, ['vending'])
    atlas = K.load_image(os.path.join(d, 'vending.png'))
    front = K.material('front', '#ffffff', roughness=0.4, base_image=atlas, emit_image=atlas, emit_strength=1.0)
    body = K.material('body', '#dde2e7', roughness=0.45)
    trim = K.material('trim', '#2a2e34', roughness=0.5)

    m = K.M('vending_machine')
    # body; its front face carries the painted plate
    m.box(body, -0.5, 0.5, 0.0, 1.83, -ZF, ZF, bevel=0.022, seg=2, front=front)
    # window frame (a lip standing out in front of the plate) and the shelf boards
    x0, x1, y0, y1 = WIN
    lip = 0.09
    m.box(trim, x0 - 0.028, x0 - 0.002, y0 - 0.028, y1 + 0.028, ZF - 0.005, ZF + lip, bevel=0.004, seg=1)
    m.box(trim, x1 + 0.002, x1 + 0.028, y0 - 0.028, y1 + 0.028, ZF - 0.005, ZF + lip, bevel=0.004, seg=1)
    m.box(trim, x0 - 0.002, x1 + 0.002, y1 + 0.002, y1 + 0.028, ZF - 0.005, ZF + lip, bevel=0.004, seg=1)
    m.box(trim, x0 - 0.002, x1 + 0.002, y0 - 0.028, y0 - 0.002, ZF - 0.005, ZF + lip, bevel=0.004, seg=1)
    for yb in ROWS:
        m.box(body, x0, x1, yb + 0.093, yb + 0.108, ZF - 0.005, ZF + lip - 0.01, bevel=0.003, seg=1)
    # selection buttons: 3 rows of 6, lit cap from the atlas
    bx, by = cell_uv0(0, 3)
    with m.uvmap(const_uv(bx + 32, by + 100), only=front):
        for yb in ROWS:
            for cx in COLS:
                m.box(trim, cx - 0.018, cx + 0.018, yb + 0.012, yb + 0.040, ZF, ZF + 0.014, bevel=0.003, seg=1, front=front)
    # the drinks: bottles on the top shelf, cans, short cans
    seg = 8
    kinds = [(BOTTLE, 0.27 * BOTTLE_S), (CAN, 0.145), (SHORT, 0.115)]
    for row, (yb, (prof, h)) in enumerate(zip(ROWS, kinds)):
        for col, cx in enumerate(COLS):
            ybase = yb + 0.108
            with m.uvmap(drink_uv(cx, ZF + 0.035, ybase, h, col, row), only=front):
                m.lathe(front, [(r, ybase + y) for r, y in prof], seg=seg, cx=cx, cz=ZF + 0.035)
    # coin and bill slots, return lever, return cup, dispensing flap
    m.box(trim, 0.255, 0.395, 1.322, 1.346, ZF, ZF + 0.010, bevel=0.003, seg=1)   # bill slot
    m.box(trim, 0.316, 0.334, 1.19, 1.24, ZF, ZF + 0.010, bevel=0.003, seg=1)      # coin slot
    m.cyl(trim, (0.325, 0.89, ZF), (0.325, 0.89, ZF + 0.02), 0.032, 0.026, seg=12)
    m.box(trim, 0.225, 0.425, 0.645, 0.755, ZF, ZF + 0.012, bevel=0.005, seg=1)
    m.box(trim, -0.395, 0.125, 0.145, 0.395, ZF, ZF + 0.016, bevel=0.006, seg=1, front=front)
    m.uv(front, plate_uv)
    return [m.build(sharp=40)]


SPEC = K.Spec('vending_machine.glb', build, [
    dict(name='main', eye=(-1.5, 1.5, 3.4), target=(0, 0.9, 0), lens=40, size=(540, 720)),
    dict(name='front', eye=(0, 1.0, 3.2), target=(0, 0.95, 0), lens=40, size=(540, 720)),
    dict(name='close', eye=(-0.35, 1.45, 1.5), target=(-0.15, 1.2, 0.3), lens=40),
    dict(name='night', eye=(-1.5, 1.5, 3.4), target=(0, 0.9, 0), lens=40, size=(540, 720), night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
