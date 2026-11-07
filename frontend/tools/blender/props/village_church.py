"""
Village church of the AUTOBAHN course: a whitewashed nave with a steep tiled roof and a round apse, and a west tower
with lit clock faces under a copper onion dome, lantern and cross (a southern German village church). The tall
arched windows glow faintly at night (church.png / church_emit.png from paint_autobahn.py).
Origin at the centre of the footprint, the tower towards -Z, ~37 m to the cross.

    blender -t 4 --background --factory-startup --python village_church.py -- --out <dir> [--render <dir>]
"""
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402

NW, NL, NH = 10.0, 20.0, 9.0      # nave width (x), length (z), wall height
TW, TH = 6.0, 23.0                # tower width, wall height
Z0 = -7.0                         # west end of the nave; the tower stands west of it


def painted(out, job):
    d = os.path.join(out, 'tex')
    os.makedirs(d, exist_ok=True)
    subprocess.run([K.host_python(), '-I', os.path.join(HERE, 'paint_autobahn.py'), d, job], check=True)
    return d


def rect_uv(x0, y0, x1, y1):
    """UVs (bl, br, tr, tl) of a pixel rectangle of the 512 px texture (y down)"""
    return [(x0 / 512, 1 - y1 / 512), (x1 / 512, 1 - y1 / 512), (x1 / 512, 1 - y0 / 512), (x0 / 512, 1 - y0 / 512)]


def build(out):
    d = painted(out, 'church')
    img = K.load_image(os.path.join(d, 'church.png'))
    emit = K.load_image(os.path.join(d, 'church_emit.png'))
    plaster = K.material('plaster', '#ebe6da', roughness=0.9)
    detail = K.material('church', '#ffffff', roughness=0.6, base_image=img, emit_image=emit, emit_strength=1.0)
    roof = K.material('roof', '#6a3024', roughness=0.75)
    copper = K.material('copper', '#4f7a66', metallic=0.35, roughness=0.5)
    gold = K.material('gold', '#c9a24a', metallic=0.9, roughness=0.3)
    stone = K.material('stone', '#9d978b', roughness=0.85)
    m = K.M('village_church')
    z1 = Z0 + NL
    # --- nave walls and roof
    m.box(plaster, -NW / 2, NW / 2, -0.5, NH, Z0, z1)
    rise = (NW / 2) * math.tan(math.radians(52))
    o, t = 0.5, 0.25
    prof = [(NW / 2 + o, NH - 0.4), (NW / 2 + o, NH - 0.4 + t), (0, NH + rise + t), (-NW / 2 - o, NH - 0.4 + t), (-NW / 2 - o, NH - 0.4), (0, NH + rise)]
    m.loft(roof, [[(x, y, Z0 + 0.2) for x, y in prof], [(x, y, z1 + 0.5) for x, y in prof]])
    # east gable
    m.prism(plaster, [(-NW / 2, z1 - 0.3), (NW / 2, z1 - 0.3), (NW / 2, z1), (-NW / 2, z1)], NH, NH + 0.01)
    m.loft(plaster, [[(-NW / 2, NH, z1), (NW / 2, NH, z1), (0, NH + rise, z1)], [(-NW / 2, NH, z1 - 0.4), (NW / 2, NH, z1 - 0.4), (0, NH + rise, z1 - 0.4)]])
    # apse: a half cylinder with a half cone roof
    R = 4.0
    seg = 10
    pts = [(R * math.cos(math.pi * k / seg), z1 + R * math.sin(math.pi * k / seg)) for k in range(seg + 1)]
    m.prism(plaster, pts, -0.5, NH - 1.2)
    rings = [[(x * 1.12, NH - 1.4, (z - z1) * 1.12 + z1) for x, z in pts], [(0.0, NH + 2.4, z1)] * len(pts)]
    m.loft(roof, rings, cap0=True, cap1=False)
    # tall arched windows along both sides (lit and dark alternating)
    for side in (-1, 1):
        x = side * (NW / 2 + 0.02)
        for k in range(5):
            zc = Z0 + 3.0 + k * 3.6
            lit = (k + (side > 0)) % 2 == 0
            uv = rect_uv(316, 22 if lit else 278, 452, 246 if lit else 502)
            a, b = (zc + 0.75, zc - 0.75) if side > 0 else (zc - 0.75, zc + 0.75)
            with m.uvmap(lambda cs, uv=uv: uv):
                m.quad(detail, [(x, 3.2, a), (x, 3.2, b), (x, 7.6, b), (x, 7.6, a)])
    # --- tower
    tz0, tz1 = Z0 - TW, Z0
    m.box(plaster, -TW / 2, TW / 2, -0.5, TH, tz0, tz1)
    m.box(stone, -TW / 2 - 0.15, TW / 2 + 0.15, TH - 0.4, TH + 0.25, tz0 - 0.15, tz1 + 0.15)
    tc = (tz0 + tz1) / 2
    # clock faces on all four sides, belfry openings under them
    for ang in range(4):
        a = ang * math.pi / 2
        nx, nz = math.sin(a), math.cos(a)
        rx, rz = nz, -nx   # right, seen from outside
        cx, cz = nx * (TW / 2 + 0.03), tc + nz * (TW / 2 + 0.03)
        r = 1.25
        cy = TH - 2.6
        uv = rect_uv(0, 0, 256, 256)
        with m.uvmap(lambda cs, uv=uv: uv):
            m.quad(detail, [(cx - rx * r, cy - r, cz - rz * r), (cx + rx * r, cy - r, cz + rz * r), (cx + rx * r, cy + r, cz + rz * r), (cx - rx * r, cy + r, cz - rz * r)])
        uv = rect_uv(316, 278, 452, 502)
        w, y0, y1 = 0.8, TH - 8.2, TH - 5.2
        with m.uvmap(lambda cs, uv=uv: uv):
            m.quad(detail, [(cx - rx * w, y0, cz - rz * w), (cx + rx * w, y0, cz + rz * w), (cx + rx * w, y1, cz + rz * w), (cx - rx * w, y1, cz - rz * w)])
    # onion dome, lantern, small onion, spire and cross
    prof = [(TW / 2 + 0.1, TH + 0.25), (3.05, TH + 0.9), (3.35, TH + 2.2), (3.2, TH + 3.4), (2.4, TH + 4.6), (1.2, TH + 5.6),
            (0.55, TH + 6.2), (0.55, TH + 6.3)]
    m.lathe(copper, prof, seg=16, cz=tc)
    m.lathe(plaster, [(0.75, TH + 6.3), (0.75, TH + 8.0)], seg=12, cz=tc)
    m.lathe(copper, [(0.95, TH + 8.0), (1.15, TH + 8.6), (1.05, TH + 9.3), (0.55, TH + 10.0), (0.12, TH + 11.6), (0.0, TH + 12.6)], seg=12, cz=tc)
    m.lathe(gold, [(0.18, TH + 12.4), (0.22, TH + 12.6), (0.18, TH + 12.8), (0.0, TH + 12.9)], seg=8, cz=tc)
    m.box(gold, -0.05, 0.05, TH + 12.8, TH + 14.4, tc - 0.05, tc + 0.05)
    m.box(gold, -0.45, 0.45, TH + 13.65, TH + 13.75, tc - 0.05, tc + 0.05)
    # door in the tower's west face
    m.box(stone, -1.1, 1.1, 0.0, 3.4, tz0 - 0.12, tz0 + 0.02)
    m.box(K.material('door', '#4a3020', roughness=0.8), -0.85, 0.85, 0.0, 3.0, tz0 - 0.16, tz0 - 0.1)
    return [m.build(sharp=35, recentre=(0.0, (tz0 + z1 + R) / 2))]


SPEC = K.Spec('village_church.glb', build, [
    dict(name='side', eye=(34.0, 12.0, -6.0), target=(0, 13.0, 0), lens=32),
    dict(name='night', eye=(34.0, 12.0, -6.0), target=(0, 13.0, 0), lens=32, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
