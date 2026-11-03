"""
Bus shelter (a small rural Japanese bus stop): open timber hut with a corrugated metal roof sloping to the back, board
walls (back and left full height, right half height), a slatted bench along the back wall and a timetable board on it,
on a concrete slab; beside it a round bus-stop sign on a steel pole (fictional stop 「朧峠入口」, no operator logo).
About 2.5 m tall (the sign's top at 2.6 m), 3.4 m shelter width; open side towards +Z; origin at the centre of the
footprint. Texture busstop.png (painted by paint.py): the sign and the timetable.

    blender -t 4 --background --factory-startup --python bus_stop.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

SIGN = (1.95, 2.34, 0.62)     # sign disc centre
SIGN_R = 0.25
CENTRE = (-0.10, 0.12)        # footprint centre in design coordinates (x, z), moved to the origin at the end


def sign_uv(cs):
    out = []
    for c in cs:
        px = 256 + (c.x - SIGN[0]) / SIGN_R * 252
        py = 256 - (c.y - SIGN[1]) / SIGN_R * 252
        out.append((px / 1024, 1 - py / 1024))
    return out


def board_uv(x0, x1, y0, y1):
    """the timetable (512 x 640 px at 512, 0) over a rectangle"""
    def fn(cs):
        return [((512 + (c.x - x0) / (x1 - x0) * 512) / 1024, 1 - ((y1 - c.y) / (y1 - y0) * 640) / 1024) for c in cs]
    return fn


def corrugated(m, mat, x0, x1, y_front, y_back, z_front, z_back, waves=14, thick=0.014, amp=0.025):
    """a corrugated sheet sloping from the front to the back: the wave runs along x"""
    n = waves * 4
    top, bot = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        w = amp * math.sin(2 * math.pi * waves * i / n)
        top.append((x, w))
        bot.append((x, w - thick))
    prof = top + bot[::-1]

    def ring(z, y):
        return [(x, y + dy, z) for x, dy in prof]

    m.loft(mat, [ring(z_front, y_front), ring(z_back, y_back)])


def build(out):
    d = K.paint(out, ['bus'])
    printed = K.material('printed', '#ffffff', roughness=0.5, base_image=K.load_image(os.path.join(d, 'busstop.png')))
    wood = K.material('wood', '#7b5d41', roughness=0.85)
    concrete = K.material('concrete', '#9c9b95', roughness=0.92)
    metal = K.material('metal', '#6c787d', metallic=0.3, roughness=0.5)

    m = K.M('bus_stop')
    # --- slab and a kerb step at the open front
    m.box(concrete, -2.2, 1.5, 0.0, 0.12, -1.0, 1.25, bevel=0.012, seg=1)
    # --- posts (timber 0.11 square): front pair, back pair, a ridge beam on top
    for x in (-2.0, 1.3):
        m.box(wood, x - 0.055, x + 0.055, 0.12, 2.42, 0.80, 0.91, bevel=0.006, seg=1)
        m.box(wood, x - 0.055, x + 0.055, 0.12, 2.22, -0.94, -0.83, bevel=0.006, seg=1)
    m.box(wood, -2.10, 1.40, 2.30, 2.44, 0.76, 0.93, bevel=0.006, seg=1)       # front beam
    m.box(wood, -2.10, 1.40, 2.10, 2.24, -0.95, -0.80, bevel=0.006, seg=1)     # back beam
    for x in (-2.0, -0.35, 1.3):                                                 # rafters, sloping to the back
        m.cyl(wood, (x, 2.40, 0.84), (x, 2.20, -0.88), 0.045, seg=6)
    # --- back wall: vertical boards, two inside rails
    bw = 0.18
    x = -1.95
    while x + bw <= 1.28:
        m.box(wood, x + 0.006, x + bw - 0.006, 0.12, 2.20, -0.90, -0.865, bevel=0.003, seg=1)
        x += bw
    for y in (1.25, 2.0):
        m.box(wood, -1.95, 1.30, y, y + 0.08, -0.865, -0.83, bevel=0.003, seg=1)
    # --- left wall: boards full height; right wall: boards to 1.15 m, a rail above
    z = -0.83
    while z + bw <= 0.75:
        m.box(wood, -2.0, -1.97, 0.12, 2.22 - (z + 0.83) * 0.1, z + 0.006, z + bw - 0.006, bevel=0.003, seg=1)
        m.box(wood, 1.27, 1.30, 0.12, 1.15, z + 0.006, z + bw - 0.006, bevel=0.003, seg=1)
        z += bw
    m.box(wood, 1.25, 1.32, 1.15, 1.22, -0.88, 0.80, bevel=0.004, seg=1)
    m.box(wood, -2.05, -1.95, 1.25, 1.33, -0.88, 0.80, bevel=0.004, seg=1)
    # --- roof: corrugated sheet and a fascia board along the front edge
    corrugated(m, metal, -2.38, 1.68, 2.52, 2.30, 1.18, -1.00, waves=16)
    m.box(wood, -2.36, 1.66, 2.38, 2.54, 1.16, 1.20, bevel=0.004, seg=1)
    # --- bench along the back wall (three slats, two end frames)
    for k in range(3):
        m.box(wood, -1.7, 1.2, 0.44, 0.47, -0.80 + k * 0.145, -0.80 + k * 0.145 + 0.125, bevel=0.004, seg=1)
    for x in (-1.6, -0.35, 1.1):
        m.box(wood, x - 0.03, x + 0.03, 0.12, 0.44, -0.78, -0.44, bevel=0.003, seg=1)
        m.box(wood, x - 0.03, x + 0.03, 0.44, 0.92, -0.80, -0.76, bevel=0.003, seg=1)   # backrest posts
    m.box(wood, -1.7, 1.2, 0.80, 0.90, -0.80, -0.77, bevel=0.003, seg=1)              # back rest board
    # --- timetable on the back wall (frame + printed face)
    bx0, bx1, by0, by1 = 0.35, 0.85, 1.10, 1.72
    m.box(wood, bx0 - 0.03, bx1 + 0.03, by0 - 0.03, by1 + 0.03, -0.83, -0.80, bevel=0.004, seg=1)
    with m.uvmap(board_uv(bx0, bx1, by0, by1), only=printed):
        m.quad(printed, [(bx0, by0, -0.795), (bx1, by0, -0.795), (bx1, by1, -0.795), (bx0, by1, -0.795)])
    # --- bus-stop sign: a drum base, a steel pole, a round sign
    sx, sy, sz = SIGN
    m.cyl(concrete, (sx, 0.12, sz), (sx, 0.40, sz), 0.20, 0.16, seg=16)
    m.cyl(metal, (sx, 0.40, sz - 0.05), (sx, 2.30, sz - 0.05), 0.032, seg=12)   # behind the sign
    m.box(metal, sx - 0.02, sx + 0.02, 2.22, 2.30, sz - 0.05, sz - 0.012)
    ring_pts = K.circle_pts(0, 0, SIGN_R, 32)
    back = [(sx + a, sy + b, sz - 0.012) for a, b in ring_pts]
    front = [(sx + a, sy + b, sz + 0.012) for a, b in ring_pts]
    m.loft(metal, [back, front], cap0=True, cap1=False)
    with m.uvmap(sign_uv, only=printed):
        m.quad(printed, front)
    m.box(metal, sx - 0.04, sx + 0.04, sy - 0.30, sy - 0.26, sz - 0.04, sz - 0.012, bevel=0.003, seg=1)  # clamp plate
    return [m.build(recentre=CENTRE)]


SPEC = K.Spec('bus_stop.glb', build, [
    dict(name='main', eye=(-4.8, 2.0, 7.2), target=(0, 1.1, 0), lens=36),
    dict(name='front', eye=(0, 1.5, 8.5), target=(0, 1.3, 0), lens=34),
    dict(name='inside', eye=(0.6, 1.5, 1.4), target=(-0.2, 1.0, -0.8), lens=32),
    dict(name='sign', eye=(1.5, 2.2, 3.0), target=(1.9, 2.0, 0.5), lens=45),
])

if __name__ == '__main__':
    K.run(SPEC)
