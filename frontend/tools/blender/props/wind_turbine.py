"""
Wind turbine: 3-blade upwind machine, tapered tower, nacelle; 86 m to the top of the upright blade, hub at 60.6 m.
The rotor (spinner + 3 blades) is the separate object `Blades`: its origin is the hub centre and its axis the prop's
local Z (the rotor disc is the XY plane, facing +Z); blade 0 points straight up.

    blender -t 4 --background --factory-startup --python wind_turbine.py -- --out <dir> [--render <dir>]
"""
import math
import os
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prop_kit as K  # noqa: E402

HUB = (0.0, 60.6, 4.6)
TIP = 25.4  # hub centre to blade tip


def tower(white, dark):
    m = K.M('Tower')
    seg = 24
    prof = [(2.25, 0.0), (2.25, 0.3), (2.1, 0.45), (1.86, 20.0), (1.91, 20.0), (1.91, 20.25), (1.86, 20.25),
            (1.64, 40.0), (1.69, 40.0), (1.69, 40.25), (1.64, 40.25), (1.42, 58.7), (1.55, 58.7), (1.55, 59.0), (1.2, 59.0)]
    m.lathe(white, prof, seg=seg)
    # door at the foot (front), with a frame
    m.box(dark, -0.55, 0.55, 0.45, 2.55, 1.88, 2.12, bevel=0.03, seg=1)
    m.box(white, -0.5, 0.5, 0.5, 2.5, 2.11, 2.15, bevel=0.02, seg=1)
    # base platform
    m.cyl(dark, (0, 0, 0), (0, 0.12, 0), 3.0, seg=seg)
    return m


def nacelle(white, dark):
    m = K.M('Nacelle')
    cy = HUB[1]
    m.box(white, -1.75, 1.75, cy - 1.9, cy + 1.7, -5.2, 3.4, bevel=0.55, seg=3)
    m.box(dark, -1.0, 1.0, cy + 1.62, cy + 1.95, -4.4, -1.4, bevel=0.1, seg=1)   # cooling unit on the roof
    m.cyl(white, (0, cy, 3.0), (0, cy, 3.9), 1.45, seg=24)                          # neck to the hub
    m.cyl(dark, (0.6, cy + 1.7, -4.2), (0.6, cy + 3.2, -4.2), 0.05, seg=6)         # wind sensor mast
    m.box(dark, -0.4, 0.9, cy + 3.15, cy + 3.28, -4.35, -4.05)
    m.cyl(dark, (0, cy - 0.6, -5.2), (0, cy - 0.6, -5.35), 0.9, seg=16)           # rear hatch
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


def blade(m, white, red, angle):
    # r (from hub), chord, thickness/chord, twist (deg), roundness of the section
    st = [(1.4, 1.9, 0.0, 17, 1.0), (2.8, 2.0, 0.0, 17, 0.9), (4.2, 2.6, 0.30, 16, 0.45), (6.5, 3.3, 0.24, 13, 0.0),
          (9.5, 3.15, 0.20, 10, 0.0), (13.5, 2.6, 0.17, 7, 0.0), (17.5, 2.1, 0.15, 5, 0.0), (21.0, 1.55, 0.14, 3.5, 0.0),
          (23.6, 1.0, 0.13, 2.5, 0.0), (25.0, 0.62, 0.12, 2, 0.0), (TIP, 0.22, 0.12, 2, 0.0)]
    rings = []
    for r, c, th, tw, rw in st:
        ring = []
        for x, z in airfoil(28, th if th else 0.2, rw):
            x = (x - 0.3) * c
            z = z * c
            t = math.radians(tw)
            xr, zr = x * math.cos(t) + z * math.sin(t), -x * math.sin(t) + z * math.cos(t)
            # the blade stands along +Y from the hub, turned by `angle` about the rotor axis (Z)
            px, py = xr, r
            ring.append((HUB[0] + px * math.cos(angle) - py * math.sin(angle), HUB[1] + px * math.sin(angle) + py * math.cos(angle), HUB[2] + zr))
        rings.append(ring)
    cut = 8  # from here the tip is painted red
    m.loft(white, rings[:cut + 1])
    m.loft(red, rings[cut:])


def rotor(white, red):
    m = K.M('Blades')
    z0 = HUB[2]
    # spinner (nose cone) along the rotor axis
    sp = [(-1.15, 1.5), (-0.2, 1.8), (1.0, 1.82), (2.1, 1.45), (2.9, 0.85), (3.4, 0.4), (3.65, 0.1)]
    rings = [[(1.0 * r * math.cos(2 * math.pi * k / 24) + HUB[0], HUB[1] + r * math.sin(2 * math.pi * k / 24), z0 + dz) for k in range(24)] for dz, r in sp]
    m.loft(white, rings)
    for i in range(3):
        blade(m, white, red, i * 2 * math.pi / 3)
    return m


def build(out):
    white = K.material('white', '#e9ebec', roughness=0.42)
    dark = K.material('dark', '#3b3f43', metallic=0.2, roughness=0.55)
    red = K.material('red', '#d5301f', roughness=0.45)
    t, n = tower(white, dark), nacelle(white, dark)
    t.absorb(n)  # tower + nacelle in one object, the rotor as `Blades`
    t.name = 'Tower'
    a = t.build()
    rot = rotor(white, red)
    rot.name = 'Rotor'
    b = rot.build(origin=HUB)
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
    dict(name='front', eye=(0, 50, 90), target=(0, 50, 0), lens=45, ground=60),
    dict(name='foot', eye=(-9, 4, 14), target=(0, 3, 0), lens=40, ground=60),
])

if __name__ == '__main__':
    K.run(SPEC)
