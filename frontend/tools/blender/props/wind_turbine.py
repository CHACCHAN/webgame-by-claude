"""
Wind turbine of the 2 MW class: 3-blade upwind machine on a tapered tubular steel tower in three flanged sections,
86 m to the top of the upright blade, hub at 60.6 m. At the foot: the concrete foundation's ring with the anchor
bolts of the base flange, the door up a flight of steel steps with its landing and rails, a vent over it, the
transformer kiosk on its slab beside the tower. On top: the nacelle with its roof hatch, cooler, wind sensors,
lightning rod and two red obstruction lamps; the spinner with the blade roots' collars; blades with red tips.
Paint that has been out for years: rain runs under every flange and seam, grime at the foot.

The rotor (spinner + 3 blades) is the separate object under the node `Blades`: its origin is the hub centre and its
axis the prop's local Z (the rotor disc is the XY plane, facing +Z); blade 0 points straight up. Origin at the
tower's centre on the ground (the foundation reaches 0.8 m into it).

    blender -t 4 --background --factory-startup --python wind_turbine.py -- --out <dir> [--render <dir>]

One baked material (prop_bake) over both objects: two draw calls (tower, rotor).
"""
import math
import os
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402
import prop_bake as PB  # noqa: E402

HUB = (0.0, 60.6, 4.6)
TIP = 25.4  # hub centre to blade tip
SEG = 32
DOOR_Y = 1.5


def tower_r(y):
    """the shell's radius at a height"""
    pts = [(0.3, 2.25), (0.45, 2.1), (20.0, 1.86), (40.0, 1.64), (58.7, 1.42)]
    for (y0, r0), (y1, r1) in zip(pts, pts[1:]):
        if y <= y1:
            return r0 + (r1 - r0) * max(0.0, (y - y0)) / (y1 - y0)
    return pts[-1][1]


def tower(S):
    m = K.M('Tower')
    white, dark, conc, zinc = S['white'], S['dark'], S['concrete'], S['zinc']
    # foundation: the concrete pedestal ring, into the ground
    with m.dense(2.0):
        m.lathe(conc, [(3.3, -0.8), (3.3, 0.10), (3.2, 0.18), (2.5, 0.2)], seg=SEG, caps=(False, False))
    prof = [(2.38, 0.18), (2.38, 0.26), (2.25, 0.26), (2.25, 0.3), (2.1, 0.45), (1.86, 20.0), (1.92, 20.0), (1.92, 20.25), (1.86, 20.25),
            (1.64, 40.0), (1.70, 40.0), (1.70, 40.25), (1.64, 40.25), (1.42, 58.7), (1.55, 58.7), (1.55, 59.0), (1.2, 59.0)]
    with m.dense(1.0):
        m.lathe(white, prof, seg=SEG, caps=(False, True))
    with m.dense(3.0):
        # anchor bolts round the base flange
        for k in range(36):
            a = 2 * math.pi * (k + 0.5) / 36
            m.cyl(zinc, (2.315 * math.sin(a), 0.26, 2.315 * math.cos(a)), (2.315 * math.sin(a), 0.33, 2.315 * math.cos(a)), 0.035, seg=6,
                  caps=(False, True))
        # the door (front) in its frame, a vent over it
        zr = tower_r(DOOR_Y + 1.0)
        m.box(white, -0.56, 0.56, DOOR_Y - 0.06, DOOR_Y + 2.12, zr - 0.25, zr + 0.06, bevel=0.03, seg=1)
        m.box(dark, -0.46, 0.46, DOOR_Y, DOOR_Y + 2.02, zr + 0.03, zr + 0.075)
        m.box(white, -0.44, 0.44, DOOR_Y + 0.02, DOOR_Y + 2.0, zr + 0.06, zr + 0.095, bevel=0.012, seg=1)
        m.box(zinc, 0.30, 0.36, DOOR_Y + 0.95, DOOR_Y + 1.12, zr + 0.095, zr + 0.14)                    # handle
        for y in (DOOR_Y + 0.3, DOOR_Y + 1.7):
            m.box(zinc, -0.46, -0.40, y - 0.06, y + 0.06, zr + 0.06, zr + 0.11)                           # hinges
        zv = tower_r(DOOR_Y + 2.8)
        m.box(dark, -0.35, 0.35, DOOR_Y + 2.5, DOOR_Y + 3.0, zv - 0.2, zv + 0.03)
        for k in range(5):
            m.box(white, -0.37, 0.37, DOOR_Y + 2.52 + k * 0.095, DOOR_Y + 2.56 + k * 0.095, zv + 0.0, zv + 0.07)
        # landing and steps (galvanised grating), rails
        z0, z1 = zr + 0.05, zr + 1.35
        m.box(zinc, -0.8, 0.8, DOOR_Y - 0.10, DOOR_Y - 0.04, z0 - 0.3, z1)
        n = 7
        for k in range(n):
            y = DOOR_Y - 0.04 - (k + 1) * (DOOR_Y - 0.24) / n
            x = 0.8 + k * 0.27
            m.box(zinc, x, x + 0.29, y - 0.04, y, z1 - 0.9, z1)
        xe = 0.8 + n * 0.27
        for z in (z1 - 0.9, z1):   # stringers
            m.sweep(zinc, [(0.8, DOOR_Y - 0.14, z), (xe, 0.2, z)], [(-0.02, -0.09), (0.02, -0.09), (0.02, 0.09), (-0.02, 0.09)])
        for x, z in ((-0.78, z1 - 0.02), (0.78, z1 - 0.02), (-0.78, z0 + 0.1), (0.0, z1 - 0.02)):
            m.cyl(zinc, (x, DOOR_Y - 0.04, z), (x, DOOR_Y + 1.06, z), 0.022, seg=6, caps=(False, True))
        for y in (DOOR_Y + 0.52, DOOR_Y + 1.06):
            m.tube(zinc, [(-0.78, y, z0 + 0.1), (-0.78, y, z1 - 0.02), (0.78, y, z1 - 0.02), (xe, y - DOOR_Y + 0.24, z1 - 0.02)], 0.022, seg=6)
        m.cyl(zinc, (xe, 0.2, z1 - 0.02), (xe, 1.3, z1 - 0.02), 0.022, seg=6, caps=(False, True))
        for x in (-0.6, 0.6):   # the landing's legs
            m.cyl(zinc, (x, 0.2, z1 - 0.06), (x, DOOR_Y - 0.1, z1 - 0.06), 0.03, seg=6, caps=(False, False))
        # transformer kiosk on its slab, beside the tower
        kx, kz = -5.2, 1.2
        m.box(conc, kx - 1.7, kx + 1.7, -0.6, 0.22, kz - 1.45, kz + 1.45, bevel=0.03, seg=1)
        m.box(S['kiosk'], kx - 1.4, kx + 1.4, 0.22, 2.3, kz - 1.15, kz + 1.15, bevel=0.02, seg=1)
        m.box(S['kiosk'], kx - 1.5, kx + 1.5, 2.3, 2.42, kz - 1.25, kz + 1.25, bevel=0.02, seg=1)     # roof
        for x in (kx - 0.68, kx + 0.68):                                                                # doors, front
            m.box(S['kiosk'], x - 0.62, x + 0.62, 0.34, 2.18, kz + 1.15, kz + 1.18, bevel=0.01, seg=1)
            for k in range(4):
                m.box(dark, x - 0.4, x + 0.4, 1.5 + k * 0.12, 1.56 + k * 0.12, kz + 1.18, kz + 1.195)
        m.box(S['warn'], kx - 0.2, kx + 0.2, 0.95, 1.3, kz + 1.18, kz + 1.19)
        m.box(zinc, kx - 0.06, kx + 0.06, 1.0, 1.25, kz + 1.18, kz + 1.215)
    # cable duct from the kiosk to the tower
    m.box(conc, -3.6, -2.2, -0.3, 0.12, 0.9, 1.5)
    return m


def nacelle(S):
    m = K.M('Nacelle')
    white, dark, zinc = S['white'], S['dark'], S['zinc']
    cy = HUB[1]
    with m.dense(1.6):
        m.box(white, -1.75, 1.75, cy - 1.9, cy + 1.7, -5.2, 3.4, bevel=0.55, seg=3)
        m.cyl(white, (0, cy, 3.0), (0, cy, 3.9), 1.45, seg=SEG)                           # neck to the hub
        m.cyl(white, (0, 59.0, 0), (0, cy - 1.85, 0), 1.3, 1.5, seg=24, caps=(False, False))   # yaw collar
        m.box(dark, -1.0, 1.0, cy + 1.62, cy + 2.0, -4.5, -2.0, bevel=0.08, seg=1)        # cooler on the roof
        for k in range(6):
            m.box(white, -1.02, 1.02, cy + 1.68 + k * 0.05, cy + 1.70 + k * 0.05, -4.52, -1.98)
        m.box(white, -0.6, 0.6, cy + 1.68, cy + 1.78, -0.9, 0.6, bevel=0.03, seg=1)       # roof hatch
        m.cyl(dark, (0, cy - 0.5, -5.2), (0, cy - 0.5, -5.33), 0.8, seg=20)               # rear hatch
        # the shell's seam between its two halves, panel joints
        m.box(dark, -1.77, 1.77, cy - 0.12, cy - 0.08, -4.7, 2.9)
        for z in (-2.6, 0.2):
            m.box(dark, -1.77, 1.77, cy - 1.4, cy + 1.2, z - 0.02, z + 0.02)
        # wind sensors on their mast, lightning rod, the two obstruction lamps
        m.cyl(zinc, (0.7, cy + 1.7, -4.8), (0.7, cy + 3.3, -4.8), 0.05, seg=6)
        m.box(zinc, 0.2, 1.2, cy + 3.2, cy + 3.28, -4.84, -4.76)
        m.cyl(dark, (0.3, cy + 3.28, -4.8), (0.3, cy + 3.5, -4.8), 0.11, 0.05, seg=8)
        m.box(dark, 1.05, 1.15, cy + 3.28, cy + 3.5, -5.1, -4.5)
        m.cyl(zinc, (-0.7, cy + 1.7, -4.8), (-0.7, cy + 3.9, -4.8), 0.03, 0.01, seg=6)
        for x in (-1.1, 1.1):
            m.cyl(zinc, (x, cy + 1.66, -1.5), (x, cy + 1.86, -1.5), 0.13, seg=10)
            m.lathe(S['lamp'], [(0.15, cy + 1.86), (0.15, cy + 2.06), (0.10, cy + 2.14), (0.0, cy + 2.16)], seg=10, cx=x, cz=-1.5)
    return m


def airfoil(n, thick, round_w):
    """unit chord ring of n points in (x, z): LE at x = 0 (towards -x after the pitch axis shift), TE at 1;
    blended with a circle (round_w = 1) for the blade root"""
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        xc = 0.5 * (1 + math.cos(th))
        side = 1 if math.sin(th) >= 0 else -1
        t = 5 * thick * (0.2969 * math.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
        ax, az = xc, side * t
        cx, cz = 0.5 + 0.5 * math.cos(th), 0.5 * math.sin(th)
        pts.append(((1 - round_w) * ax + round_w * cx, (1 - round_w) * az + round_w * cz))
    return pts


def blade(m, white, red, dark, angle):
    # r (from hub), chord, thickness/chord, twist (deg), roundness of the section
    st = [(1.4, 1.9, 0.0, 17, 1.0), (2.8, 2.0, 0.0, 17, 0.9), (4.2, 2.6, 0.30, 16, 0.45), (6.5, 3.3, 0.24, 13, 0.0),
          (9.5, 3.15, 0.20, 10, 0.0), (13.5, 2.6, 0.17, 7, 0.0), (17.5, 2.1, 0.15, 5, 0.0), (21.0, 1.55, 0.14, 3.5, 0.0),
          (23.6, 1.0, 0.13, 2.5, 0.0), (25.0, 0.62, 0.12, 2, 0.0), (TIP, 0.22, 0.12, 2, 0.0)]
    ca, sa = math.cos(angle), math.sin(angle)

    def put(px, py, pz):
        return (HUB[0] + px * ca - py * sa, HUB[1] + px * sa + py * ca, HUB[2] + pz)

    rings = []
    for r, c, th, tw, rw in st:
        ring = []
        for x, z in airfoil(28, th if th else 0.2, rw):
            x = (x - 0.3) * c
            z = z * c
            t = math.radians(tw)
            xr, zr = x * math.cos(t) + z * math.sin(t), -x * math.sin(t) + z * math.cos(t)
            ring.append(put(xr, r, zr))      # the blade stands along +Y from the hub, turned by `angle` about the rotor axis (Z)
        rings.append(ring)
    cut = 8  # from here the tip is painted red
    m.loft(white, rings[:cut + 1], cap0=False, cap1=False)
    m.loft(red, rings[cut:], cap0=False)
    # the root's collar on the spinner (the pitch bearing's cover)
    c0 = 1.9 * 0.2
    ring0 = [put((0.5 - 0.3) * 1.9 + 1.02 * math.cos(2 * math.pi * k / 20), 1.25, 1.02 * math.sin(2 * math.pi * k / 20)) for k in range(20)]
    ring1 = [put((0.5 - 0.3) * 1.9 + 1.02 * math.cos(2 * math.pi * k / 20), 1.62, 1.02 * math.sin(2 * math.pi * k / 20)) for k in range(20)]
    ring2 = [put((0.5 - 0.3) * 1.9 + 0.93 * math.cos(2 * math.pi * k / 20), 1.66, 0.93 * math.sin(2 * math.pi * k / 20)) for k in range(20)]
    m.loft(dark, [ring0, ring1, ring2], cap0=False, cap1=False)
    del c0


def rotor(S):
    m = K.M('Blades')
    z0 = HUB[2]
    # spinner (nose cone) along the rotor axis
    sp = [(-1.15, 1.5), (-0.2, 1.8), (1.0, 1.82), (2.1, 1.45), (2.9, 0.85), (3.4, 0.4), (3.65, 0.1)]
    rings = [[(1.0 * r * math.cos(2 * math.pi * k / 24) + HUB[0], HUB[1] + r * math.sin(2 * math.pi * k / 24), z0 + dz) for k in range(24)] for dz, r in sp]
    with m.dense(1.6):
        m.loft(S['white'], rings)
    for i in range(3):
        blade(m, S['white'], S['red'], S['dark'], i * 2 * math.pi / 3)
    return m


def build(out):
    S = dict(
        white=PB.surface('white', '#e6e8e8', roughness=0.42, vary=0.05, mottle=0.25, mottle_scale=0.6, mottle_colour='#cfd0cb', dirt=0.6,
                         streak=0.6, streak_scale=1.2, foot=0.5, foot_h=1.6, foot_colour='#6f7262', moss=0.2, rust=0.08),
        dark=PB.surface('dark', '#34383c', metallic=0.2, roughness=0.55, vary=0.08, dirt=0.4, dust=0.4, streak=0.3),
        red=PB.surface('red', '#cf2f20', roughness=0.45, vary=0.06, mottle=0.3, mottle_scale=0.8, mottle_colour='#d86a5a', dirt=0.5, streak=0.4,
                       streak_scale=1.2),
        concrete=PB.surface('concrete', '#8f8e87', roughness=0.9, vary=0.15, mottle=0.5, mottle_scale=3, grain=0.0, dirt=0.7, foot=0.6, foot_h=0.15,
                            moss=0.5, streak=0.4),
        zinc=PB.surface('zinc', '#a3a8a8', metallic=0.7, roughness=0.46, rust=0.3, dirt=0.5, streak=0.2),
        kiosk=PB.surface('kiosk', '#6f7f72', roughness=0.5, vary=0.08, dirt=0.6, streak=0.5, foot=0.5, foot_h=0.5, rust=0.2, wear=0.2),
        warn=PB.surface('warn', '#e8c21a', roughness=0.45, dirt=0.4),
        lamp=PB.surface('lamp', '#7a1208', roughness=0.25, emit='#ff2a14', dirt=0.2, vary=0.0),
    )
    t, n = tower(S), nacelle(S)
    t.absorb(n)  # tower + nacelle in one object, the rotor as `Blades`
    t.name = 'Tower'
    a = t.build()
    rot = rotor(S)
    rot.name = 'Rotor'
    b = rot.build(origin=HUB)
    PB.finish([a, b], out, 'wind_turbine', size=1024, orm_size=512, emit_size=256, normal=False, near=0.5, wide=4.0, edge=0.05, max_len=14.0,
              margin=0.003)
    # the game turns the node `Blades` about its own origin: an empty at the hub holding the rotor mesh (the optimiser
    # moves a mesh node's own origin when it quantises the geometry, but leaves an empty's alone)
    pivot = bpy.data.objects.new('Blades', None)
    bpy.context.scene.collection.objects.link(pivot)
    pivot.location = b.location.copy()
    b.parent = pivot
    b.location = (0.0, 0.0, 0.0)
    pivot['tris'] = 0
    return [a, pivot, b]


SPEC = K.Spec('wind_turbine.glb', build, [
    dict(name='main', eye=(-95, 48, 150), target=(0, 43, 3), lens=40, ground=60),
    dict(name='nacelle', eye=(-16, 64, 26), target=(0, 61, 3), lens=40, ground=60),
    dict(name='foot', eye=(7, 3.2, 13), target=(-1.5, 2.2, 0), lens=40, ground=60),
])

if __name__ == '__main__':
    K.run(SPEC)
