"""
Village church of the AUTOBAHN course (a southern German village church): a whitewashed nave on a stone plinth,
buttresses between its tall round-headed windows (cut into the walls, leaded, lit and dark in turn), a steep roof of
clay tiles and a round apse; the west tower with string courses, louvred belfry openings and a lit clock face on
each side under a cornice, the copper onion dome gone green, its lantern, the small onion, spire, gilt ball and
cross; the portal with its steps in the tower's west face. Weathered: runs under every ledge, a dirty foot, moss on
the tiles. The clock faces are church.png / church_emit.png from paint_autobahn.py.
Origin at the centre of the footprint on the ground (the plinth reaches 0.5 m into it), the tower towards -Z,
~37 m to the cross.

    blender -t 4 --background --factory-startup --python village_church.py -- --out <dir> [--render <dir>]

One baked material (prop_bake).
"""
import math
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402
from village_house import Wall, roof_surface, surfaces, boards  # noqa: E402

NW, NL, NH = 10.0, 20.0, 9.0      # nave width (x), length (z), wall height
TW, TH = 6.0, 23.0                # tower width, wall height
Z0 = -7.0                         # west end of the nave; the tower stands west of it
PITCH = 52


def painted(out, job):
    d = os.path.join(out, 'tex')
    os.makedirs(d, exist_ok=True)
    subprocess.run([K.host_python(), '-I', os.path.join(HERE, 'paint_autobahn.py'), d, job], check=True)
    return d


def verdigris(g, ch):
    """copper sheet gone green: paler runs down it, brown patches where the patina is younger"""
    run = g.noise(1.2, 3.0, 0.6, stretch=(1, 0.12, 1), seed=3.0)
    ch['base'] = g.mix(ch['base'], g.rgb('#9cc4ad'), g.mul(g.step(run, 0.5, 0.75), 0.6))
    ch['base'] = g.mix(ch['base'], g.rgb('#5a4a34'), g.mul(g.step(g.noise(0.9, 2.0, 0.5, seed=8.0), 0.62, 0.8), 0.45))


def build(out):
    d = painted(out, 'church')
    img = K.load_image(os.path.join(d, 'church.png'))
    emit = K.load_image(os.path.join(d, 'church_emit.png'))
    S = surfaces()
    S['roof'] = roof_surface('z', PITCH)
    S['plaster'] = PB.surface('whitewash', '#e9e4d6', roughness=0.92, vary=0.08, mottle=0.3, mottle_scale=1.0, mottle_colour='#cfc7b4', grain=0.4,
                              grain_scale=30, dirt=0.75, streak=0.75, streak_scale=2.5, foot=0.7, foot_h=1.2, foot_colour='#6b6455', moss=0.2)
    S['clock'] = PB.surface('clock', '#ffffff', roughness=0.5, image=img, emit_image=emit, vary=0.03, dirt=0.3, streak=0.2)
    S['copper'] = PB.surface('copper', '#5f9079', metallic=0.3, roughness=0.6, vary=0.12, mottle=0.4, mottle_scale=2, mottle_colour='#47705f',
                             dirt=0.5, streak=0.5, streak_scale=2, custom=verdigris)
    S['gold'] = PB.surface('gold', '#c9a24a', metallic=1.0, roughness=0.32, vary=0.05, dirt=0.4)
    S['door'] = PB.surface('church_door', '#4a3020', roughness=0.8, vary=0.12, grain=0.4, grain_scale=60, fibre=(1, 0.08, 1), dirt=0.6,
                           foot=0.4, foot_h=0.4, custom=boards(0.14, 0.5))
    plaster, stone = S['plaster'], S['stone']
    m = K.M('village_church')
    z1 = Z0 + NL
    # --- nave: the long walls with their windows and buttresses, the end walls with their gables
    rise = (NW / 2) * math.tan(math.radians(PITCH))
    sides = (Wall(m, (NW / 2, z1), (0, -1), NL), Wall(m, (-NW / 2, Z0), (0, 1), NL))
    bay = NL / 5
    for si, wall in enumerate(sides):
        for k in range(5):
            uc = (k + 0.5) * bay
            lit = (k + si) % 2 == 0
            wall.arched(plaster, S['lit'] if lit else S['dark'], (k * bay, (k + 1) * bay, 0.0, NH), (uc - 0.75, uc + 0.75, 3.2, 6.3))
            for du in (-0.25, 0.25):                                                        # the leading
                wall.box(S['zinc'], uc + du - 0.025, uc + du + 0.025, 3.2, 6.75, -0.3, -0.25)
            for y in (4.0, 4.8, 5.6, 6.3):
                wall.box(S['zinc'], uc - 0.75, uc + 0.75, y - 0.025, y + 0.025, -0.3, -0.25)
            wall.box(stone, uc - 0.9, uc + 0.9, 3.08, 3.2, -0.25, 0.1)                       # sill
        for k in range(6):                                                                  # buttresses, stepped
            u = min(max(k * bay, 0.35), NL - 0.35)
            wall.box(plaster, u - 0.35, u + 0.35, 0.0, 5.2, 0.0, 0.75)
            wall.box(stone, u - 0.4, u + 0.4, 5.2, 5.32, 0.0, 0.82)
            wall.box(plaster, u - 0.35, u + 0.35, 5.32, 7.6, 0.0, 0.4)
            wall.box(stone, u - 0.4, u + 0.4, 7.6, 7.72, 0.0, 0.47)
        wall.box(stone, 0.0, NL, NH - 0.3, NH, 0.0, 0.14)                                    # cornice under the eaves
    for wall in (Wall(m, (-NW / 2, z1), (1, 0), NW), Wall(m, (NW / 2, Z0), (-1, 0), NW)):
        wall.rect(plaster, 0.0, NW, 0.0, NH)
        m.quad(plaster, [wall.P(0, NH), wall.P(NW, NH), wall.P(NW / 2, NH + rise)])
    m.box(S['plinth'], -NW / 2 - 0.1, NW / 2 + 0.1, -0.5, 0.9, Z0 - 0.1, z1 + 0.1)
    o, t = 0.5, 0.25
    prof = [(NW / 2 + o, NH - 0.4), (NW / 2 + o, NH - 0.4 + t), (0, NH + rise + t), (-NW / 2 - o, NH - 0.4 + t), (-NW / 2 - o, NH - 0.4), (0, NH + rise)]
    with m.dense(0.8):
        m.loft(S['roof'], [[(x, y, Z0 + 0.2) for x, y in prof], [(x, y, z1 + 0.5) for x, y in prof]])
    m.tube(S['roof'], [(0, NH + rise + t - 0.03, Z0 + 0.2), (0, NH + rise + t - 0.03, z1 + 0.52)], 0.14, seg=8)
    # apse: a half cylinder with a half cone roof, three small windows
    R = 4.0
    seg = 12
    pts = [(R * math.cos(math.pi * k / seg), z1 + R * math.sin(math.pi * k / seg)) for k in range(seg + 1)]
    m.prism(plaster, pts, 0.0, NH - 1.2, cap0=False)
    m.prism(S['plinth'], [(x * 1.03, (z - z1) * 1.03 + z1) for x, z in pts], -0.5, 0.9, cap0=False)
    m.prism(stone, [(x * 1.04, (z - z1) * 1.04 + z1) for x, z in pts], NH - 1.5, NH - 1.2)
    rings = [[(x * 1.12, NH - 1.4, (z - z1) * 1.12 + z1) for x, z in pts], [(0.0, NH + 2.4, z1)] * len(pts)]
    m.loft(S['roof'], rings, cap0=True, cap1=False)
    for a in (30, 90, 150):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        with m.at(K.move(R * ca, 0, z1 + R * sa) @ K.rot_y(math.radians(90 - a))):
            m.box(stone, -0.55, 0.55, 3.3, 6.3, -0.1, 0.06)
            m.box(S['dark'] if a == 90 else S['lit'], -0.42, 0.42, 3.45, 6.15, -0.1, 0.1)
    # --- tower: string courses, belfry openings with their louvres, a clock on each face, the cornice
    tz0, tz1 = Z0 - TW, Z0
    tc = (tz0 + tz1) / 2
    m.box(plaster, -TW / 2, TW / 2, 0.0, TH, tz0, tz1)
    m.box(S['plinth'], -TW / 2 - 0.12, TW / 2 + 0.12, -0.5, 1.1, tz0 - 0.12, tz1 + 0.12)
    for y in (8.2, 13.6):
        m.box(stone, -TW / 2 - 0.1, TW / 2 + 0.1, y, y + 0.22, tz0 - 0.1, tz1 + 0.1)
    m.box(stone, -TW / 2 - 0.18, TW / 2 + 0.18, TH - 0.4, TH + 0.25, tz0 - 0.18, tz1 + 0.18)
    faces = (Wall(m, (-TW / 2, tz1), (1, 0), TW), Wall(m, (TW / 2, tz1), (0, -1), TW), Wall(m, (TW / 2, tz0), (-1, 0), TW),
             Wall(m, (-TW / 2, tz0), (0, 1), TW))
    for wall in faces:
        uc = TW / 2
        cy, r = TH - 2.6, 1.3
        c0 = wall.P(uc, cy, 0.0)

        def clock_uv(cs, wall=wall, c0=c0):
            return [(0.25 + 0.234 * ((c.x - c0[0]) * wall.ax + (c.z - c0[2]) * wall.az) / r, 0.75 + 0.234 * (c.y - cy) / r) for c in cs]

        with m.dense(3.0), m.uvmap(clock_uv, only=S['clock']):
            m.cyl(S['clock'], c0, wall.P(uc, cy, 0.1), r, seg=28, caps=(False, True))
        y0, y1 = TH - 8.2, TH - 5.2
        wall.box(stone, uc - 1.0, uc + 1.0, y0 - 0.18, y1 + 0.18, 0.0, 0.06)
        wall.box(S['dark'], uc - 0.8, uc + 0.8, y0, y1, 0.0, 0.09)
        for k in range(9):
            y = y0 + 0.12 + k * (y1 - y0 - 0.24) / 8
            wall.box(S['timber'], uc - 0.8, uc + 0.8, y - 0.07, y + 0.07, 0.09, 0.17)
        for y in (3.8, 10.4):                                                               # slit windows up the stair
            wall.box(stone, uc - 0.32, uc + 0.32, y - 0.1, y + 1.5, 0.0, 0.05)
            wall.box(S['dark'], uc - 0.2, uc + 0.2, y, y + 1.4, 0.0, 0.08)
    # onion dome, lantern, small onion, spire, the gilt ball and cross
    prof = [(TW / 2 + 0.1, TH + 0.25), (3.05, TH + 0.9), (3.35, TH + 2.2), (3.2, TH + 3.4), (2.4, TH + 4.6), (1.2, TH + 5.6),
            (0.55, TH + 6.2), (0.55, TH + 6.3)]
    m.lathe(S['copper'], prof, seg=20, cz=tc, caps=(False, False))
    m.lathe(plaster, [(0.75, TH + 6.3), (0.75, TH + 8.0)], seg=12, cz=tc, caps=(False, False))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        m.box(S['dark'], 0.77 * math.cos(a) - 0.16, 0.77 * math.cos(a) + 0.16, TH + 6.6, TH + 7.7, tc + 0.77 * math.sin(a) - 0.16,
              tc + 0.77 * math.sin(a) + 0.16)
    m.lathe(S['copper'], [(0.95, TH + 8.0), (1.15, TH + 8.6), (1.05, TH + 9.3), (0.55, TH + 10.0), (0.12, TH + 11.6), (0.0, TH + 12.6)], seg=14,
            cz=tc, caps=(True, False))
    m.lathe(S['gold'], [(0.18, TH + 12.4), (0.22, TH + 12.6), (0.18, TH + 12.8), (0.0, TH + 12.9)], seg=10, cz=tc)
    m.box(S['gold'], -0.05, 0.05, TH + 12.8, TH + 14.4, tc - 0.05, tc + 0.05)
    m.box(S['gold'], -0.45, 0.45, TH + 13.65, TH + 13.75, tc - 0.05, tc + 0.05)
    # the portal in the tower's west face: stone jambs and lintel, a double door of boards, two steps
    west = faces[2]
    uc = TW / 2
    west.box(stone, uc - 1.25, uc - 0.9, 0.0, 3.5, 0.0, 0.16)
    west.box(stone, uc + 0.9, uc + 1.25, 0.0, 3.5, 0.0, 0.16)
    west.box(stone, uc - 1.35, uc + 1.35, 3.5, 3.95, 0.0, 0.2)
    west.box(S['door'], uc - 0.9, uc + 0.9, 0.3, 3.5, 0.0, 0.07)
    west.box(S['zinc'], uc - 0.03, uc + 0.03, 0.3, 3.5, 0.07, 0.09)
    for s in (-1, 1):
        west.box(S['zinc'], uc + s * 0.16 - 0.03, uc + s * 0.16 + 0.03, 1.4, 1.65, 0.07, 0.12)
    west.box(stone, uc - 1.7, uc + 1.7, -0.4, 0.15, 0.0, 1.1)
    west.box(stone, uc - 1.4, uc + 1.4, 0.15, 0.3, 0.0, 0.7)
    ob = m.build(sharp=35, recentre=(0.0, (tz0 + z1 + R) / 2))
    PB.finish([ob], out, 'village_church', size=2048, orm_size=1024, normal_size=512, emit_size=512, near=0.4, wide=3.0, edge=0.04, max_len=8.0,
              margin=0.002)
    return [ob]


SPEC = K.Spec('village_church.glb', build, [
    dict(name='side', eye=(34.0, 12.0, -6.0), target=(0, 13.0, 0), lens=32),
    dict(name='west', eye=(-16.0, 5.0, -36.0), target=(0, 12.0, -6), lens=32),
    dict(name='night', eye=(34.0, 12.0, -6.0), target=(0, 13.0, 0), lens=32, night=True),
])

if __name__ == '__main__':
    K.run(SPEC)
