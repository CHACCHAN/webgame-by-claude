"""
Village house of the AUTOBAHN course: a two-storey German house with plastered walls, a steep tiled gable roof with
overhanging eaves and a chimney. The walls are bays of house_facade.png (paint_autobahn.py): windows lit, dark or
shuttered, picked from a seed, so the same model shows a lived-in pattern of lit windows at night (the emissive map
lights only the glass). village_farmhouse.py builds the larger half-timbered farmhouse with the same code.
Origin at the centre of the footprint, front (+Z) with the door, ~10 m tall.

    blender -t 4 --background --factory-startup --python village_house.py -- --out <dir> [--render <dir>]
"""
import math
import os
import random
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402

BAY_H = 2.8


def painted(out, job):
    d = os.path.join(out, 'tex')
    os.makedirs(d, exist_ok=True)
    subprocess.run([K.host_python(), '-I', os.path.join(HERE, 'paint_autobahn.py'), d, job], check=True)
    return d


def tile_uv(col, row):
    """corner UVs (bottom-left, bottom-right, top-right, top-left) of facade tile (col, row); row 0 at the top"""
    u0, u1 = col / 4 + 0.002, (col + 1) / 4 - 0.002
    v1, v0 = 1 - row / 4 - 0.002, 1 - (row + 1) / 4 + 0.002
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def wall(m, mat, p0, along, length, floors, pick):
    """a wall from p0 (its bottom left seen from outside) running `along` (unit x/z) for `length`: bays per floor"""
    n = max(1, round(length / 2.6))
    w = length / n
    ax, az = along
    for f in range(floors):
        for k in range(n):
            col, row = pick(f, k, n)
            x0, z0 = p0[0] + ax * w * k, p0[2] + az * w * k
            x1, z1 = x0 + ax * w, z0 + az * w
            y0, y1 = p0[1] + f * BAY_H, p0[1] + (f + 1) * BAY_H
            uv = tile_uv(col, row)
            with m.uvmap(lambda cs, uv=uv: uv):
                m.quad(mat, [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)])


def build_house(name, W, D, floors, pitch, seed, timber_upper, out, barn=0.0):
    """W across the front (x), D deep (z); ridge along x; barn: share of the length (from +x) that is a timber barn"""
    d = painted(out, 'house')
    facade_img = K.load_image(os.path.join(d, 'house_facade.png'))
    emit_img = K.load_image(os.path.join(d, 'house_emit.png'))
    facade = K.material('facade', '#ffffff', roughness=0.85, base_image=facade_img, emit_image=emit_img, emit_strength=1.0)
    roof = K.material('roof', '#6e3326', roughness=0.75)
    trim = K.material('trim', '#4a3a30', roughness=0.8)
    rnd = random.Random(seed)
    m = K.M(name)
    H = floors * BAY_H
    wx, wz = W / 2, D / 2
    barn_x = wx - W * barn  # x beyond which the front/back walls are barn boards

    def pick_front(f, k, n):
        if f == 0 and k == n // 2 and not barn:
            return (0 if rnd.random() < 0.6 else 1), 2
        row = 1 if (timber_upper and f > 0) else 0
        r = rnd.random()
        return (0 if r < 0.42 else 1 if r < 0.75 else 2), row

    def pick_plain(f, k, n):
        row = 1 if (timber_upper and f > 0) else 0
        r = rnd.random()
        return (0 if r < 0.35 else 1 if r < 0.75 else 2 if r < 0.9 else 3), row

    # front (+Z) and back (-Z): left-to-right seen from outside is +X → -X on the front... (outside at +Z looks to -Z,
    # its right is +X): the front runs from -X to +X; the back from +X to -X
    if barn:
        wall(m, facade, (-wx, 0, wz), (1, 0), W - W * barn, floors, pick_front)
        wall(m, facade, (barn_x, 0, -wz), (-1, 0), W - W * barn, floors, pick_plain)
        # the barn: dark boards with a big door on the front
        for z, sgn in ((wz, 1), (-wz, -1)):
            xa, xb = (barn_x, wx) if sgn > 0 else (wx, barn_x)
            uv = tile_uv(3, 3)
            with m.uvmap(lambda cs, uv=uv: uv):
                m.quad(facade, [(xa, 0, z), (xb, 0, z), (xb, H, z), (xa, H, z)])
        uv = tile_uv(2, 2)
        with m.uvmap(lambda cs, uv=uv: uv):
            cx = (barn_x + wx) / 2
            m.quad(facade, [(cx - 2.0, 0, wz + 0.02), (cx + 2.0, 0, wz + 0.02), (cx + 2.0, 3.4, wz + 0.02), (cx - 2.0, 3.4, wz + 0.02)])
    else:
        wall(m, facade, (-wx, 0, wz), (1, 0), W, floors, pick_front)
        wall(m, facade, (wx, 0, -wz), (-1, 0), W, floors, pick_plain)
    # sides: +X (outside looks to -X; its right is -Z... runs +Z → -Z) and -X (runs -Z → +Z)
    wall(m, facade, (wx, 0, wz), (0, -1), D, floors, pick_plain)
    wall(m, facade, (-wx, 0, -wz), (0, 1), D, floors, pick_plain)
    # gables at the ends of the ridge (the ridge runs along x)
    rise = wz * math.tan(math.radians(pitch))
    for x, sgn in ((wx, 1), (-wx, -1)):
        # outside at +X: left-to-right runs +Z → -Z
        za, zb = (wz, -wz) if sgn > 0 else (-wz, wz)
        u = tile_uv(1 if timber_upper else 0, 3)
        um = ((u[0][0] + u[1][0]) / 2, u[2][1])
        with m.uvmap(lambda cs, u=u, um=um: [u[0], u[1], um]):
            m.quad(facade, [(x, H, za), (x, H, zb), (x, H + rise, 0)])
    # roof: a slab with overhangs, as a closed loft along x
    o, t = 0.55, 0.22
    ye = H - o * math.tan(math.radians(pitch))
    prof = [(wz + o, ye), (wz + o, ye + t), (0, H + rise + t * 1.2), (-wz - o, ye + t), (-wz - o, ye), (0, H + rise)]
    ring = lambda x: [(x, y, z) for z, y in prof]  # noqa: E731
    m.loft(roof, [ring(-wx - 0.45), ring(wx + 0.45)])
    # chimney and a fascia board along the eaves
    cx = rnd.uniform(-wx * 0.5, wx * 0.3)
    m.box(trim, cx - 0.3, cx + 0.3, H + rise * 0.4, H + rise + 0.9, -wz * 0.35 - 0.3, -wz * 0.35 + 0.3)
    for z in (wz + o, -wz - o):
        m.box(trim, -wx - 0.45, wx + 0.45, ye - 0.12, ye + 0.05, z - 0.04, z + 0.04)
    # a plinth so the walls do not float on uneven ground
    m.box(trim, -wx - 0.05, wx + 0.05, -0.6, 0.02, -wz - 0.05, wz + 0.05)
    return [m.build(sharp=30)]


def build(out):
    return build_house('village_house', 10.0, 9.0, 2, 46, 11, False, out)


SPEC = K.Spec('village_house.glb', build, [
    dict(name='front', eye=(9.0, 5.0, 18.0), target=(0, 4.0, 0), lens=35),
    dict(name='night', eye=(9.0, 5.0, 18.0), target=(0, 4.0, 0), lens=35, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
