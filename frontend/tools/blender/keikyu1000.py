"""
Keikyu New 1000 series, 1st batch (2002, Siemens GTO "ドレミファ" inverter; painted aluminium body): three cars
Muc + Tpu + Msc, built from numbers (no outside model or texture). Run with Blender 5.x:

  blender --background --factory-startup --python tools/blender/keikyu1000.py -- --out <file.glb> [--stage N] [--render <file.png> [--view front34|side|front|rear34|roof|under]]

--stage 1 shell, 2 paint, 3 windows / doors / lamps, 4 roof, underfloor and bogies, 5 the three cars (default).
Figures (ja.wikipedia 京急1000形電車 (2代), 2026-11-03): car 18 m, width 2,830 mm, height 4,026.5 mm with the air
conditioners, floor 1,150 mm, doors 1,300 × 1,850 mm, three per side; red body with white round the windows; an
emergency door on the left of the cab face (seen from ahead), head lamps high in the windscreen, express and tail
lamps low on the nose. Our estimates: bogie centres 12 m, door pitch 4.85 m, the nose's curve and rake.
"""
import math
import os
import sys

sys.dont_write_bytecode = True  # no __pycache__ in the repo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_kit as K  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


STAGE = int(opt('--stage', '5'))
OUT = opt('--out')
RENDER = opt('--render')
VIEW = opt('--view', 'front34')

# ---------------------------------------------------------------- dimensions (m, the game's car frame)
HALF_W = 1.415          # half the body width (2.83 m)
BOTTOM = 0.98           # lower edge of the body side
FLOOR = 1.15
BAND = (1.74, 3.0)      # white round the windows
EAVE = 3.12
ROOF = 3.62
END = 8.75              # body end at a gangway (cars 18 m apart, 0.5 m gap)
NOSE = 8.82             # cab face at its sides, before the bulge
BOGIE = 6.0             # bogie centres ±6 m
DOORS = (-4.85, 0.0, 4.85)
DOOR_W = 1.3
DOOR_TOP = FLOOR + 1.85


def section():
    half = [(HALF_W - 0.03, BOTTOM), (HALF_W, 1.12), (HALF_W, BAND[0]), (HALF_W, BAND[1]), (HALF_W, EAVE)]
    # rounded shoulder, then the shallow roof arch to the centre line
    r = 0.32
    for a in (15, 30, 45, 60, 75, 90):
        t = math.radians(a)
        half.append((HALF_W - r + r * math.cos(t), EAVE + r * math.sin(t)))
    half += [(0.85, 3.50), (0.6, 3.555), (0.3, 3.605), (0.0, ROOF)]

    def zone(y, ny):
        if ny > 0.82:
            return 'roof'
        if BAND[0] <= y < BAND[1]:
            return 'white'
        return 'red'

    return K.Section(half, zone)


CAB = dict(bevel=0.42, segments=7, rake=0.14, rake_from=2.1, bulge=0.12)
GANGWAY = dict(bevel=0.08, segments=2)


def materials():
    m = K.Materials()
    if STAGE == 1:
        # the bare shape first: everything one grey
        for name in ('red', 'white', 'roof'):
            m.add(name, '#b9bcc0', roughness=0.45)
    else:
        m.add('red', '#d2192b', roughness=0.32)
        m.add('white', '#efeee8', roughness=0.35)
        m.add('roof', '#5f5c58', roughness=0.7)
    m.add('glass', '#0a0e12', metallic=0.2, roughness=0.08)
    m.add('mask', '#16181b', roughness=0.3)
    m.add('sign', '#f2efe6', roughness=0.4, emissive='#fff6e0', strength=0.25)
    m.add('lamp_head', '#c9cdd2', metallic=0.8, roughness=0.25)
    m.add('lamp_house', '#1c1d20', roughness=0.4)
    m.add('lens', '#d9dcdf', metallic=0.1, roughness=0.15)
    m.add('line', '#4a4c50', roughness=0.6)
    m.add('skirt', '#b8bcc1', metallic=0.55, roughness=0.35)
    m.add('dark', '#232427', roughness=0.75)
    m.add('bogie', '#2d2f33', roughness=0.7)
    m.add('wheel', '#55585c', metallic=0.7, roughness=0.45)
    m.add('ac', '#a3a6aa', roughness=0.55)
    m.add('coupler', '#7a7d82', metallic=0.6, roughness=0.4)
    m.add('panto', '#3d4045', metallic=0.4, roughness=0.5)
    return m


# ---------------------------------------------------------------- the parts

def side(part, shell, s, cab):
    """windows and doors on side s (+1 left, −1 right); cab: the car has its cab at +z"""
    for zc in DOORS:
        # red door frames through the white band, the leaves' seams, their windows
        for z0 in (zc - DOOR_W / 2 - 0.06, zc + DOOR_W / 2):
            K.decal(part, shell, 'red', (z0, z0 + 0.06, BAND[0], BAND[1]), 'x', from_side=s, grid=(1, 2))
        for z0 in (zc - DOOR_W / 2, zc, zc + DOOR_W / 2):
            K.decal(part, shell, 'line', (z0 - 0.009, z0 + 0.009, FLOOR, DOOR_TOP), 'x', from_side=s, lift=0.006, grid=(1, 3))
        K.decal(part, shell, 'line', (zc - DOOR_W / 2, zc + DOOR_W / 2, DOOR_TOP - 0.009, DOOR_TOP + 0.009), 'x', from_side=s, lift=0.006, grid=(2, 1))
        for z0, z1 in ((zc - 0.52, zc - 0.13), (zc + 0.13, zc + 0.52)):
            K.decal(part, shell, 'glass', (z0, z1, 1.98, 2.86), 'x', from_side=s, lift=0.007, grid=(1, 1))
    # windows between the doors: one 2.45 m opening with a centre post
    for z0 in (-3.65, 1.2):
        K.decal(part, shell, 'glass', (z0, z0 + 1.19, 1.88, 2.88), 'x', from_side=s, grid=(1, 1))
        K.decal(part, shell, 'glass', (z0 + 1.265, z0 + 2.45, 1.88, 2.88), 'x', from_side=s, grid=(1, 1))
    # the ends: a single window; a cab end has a shorter one and the crew door
    K.decal(part, shell, 'glass', (-7.45, -5.95, 1.88, 2.88), 'x', from_side=s, grid=(1, 1))
    if cab:
        K.decal(part, shell, 'glass', (5.95, 6.75, 1.88, 2.88), 'x', from_side=s, grid=(1, 1))
        for z0 in (7.05, 7.6):
            K.decal(part, shell, 'line', (z0 - 0.009, z0 + 0.009, 1.12, DOOR_TOP), 'x', from_side=s, lift=0.006, grid=(1, 3))
        K.decal(part, shell, 'line', (7.05, 7.6, DOOR_TOP - 0.009, DOOR_TOP + 0.009), 'x', from_side=s, lift=0.006, grid=(1, 1))
        K.decal(part, shell, 'glass', (7.14, 7.51, 2.02, 2.86), 'x', from_side=s, lift=0.007, grid=(1, 1))
    else:
        K.decal(part, shell, 'glass', (5.95, 7.45, 1.88, 2.88), 'x', from_side=s, grid=(1, 1))


def cab_face(part, shell):
    """the cab face at +z (seen from ahead the emergency door is on the left: −x)"""
    # the black frame stays inside the roof's rounding (rays past it miss the shell)
    K.rounded_rect(part, shell, 'mask', 0.0, 2.77, 2.44, 1.30, 0.16, 'z')
    K.decal(part, shell, 'glass', (-1.15, -0.60, 2.20, 3.34), 'z', lift=0.008, grid=(4, 6))
    K.decal(part, shell, 'glass', (-0.52, 1.15, 2.20, 3.34), 'z', lift=0.008, grid=(8, 6))
    # roller blinds: type and destination over the driver, the train number in the door window
    K.decal(part, shell, 'sign', (-0.42, -0.06, 3.12, 3.29), 'z', lift=0.012, grid=(2, 1))
    K.decal(part, shell, 'sign', (0.04, 0.80, 3.12, 3.29), 'z', lift=0.012, grid=(4, 1))
    K.decal(part, shell, 'sign', (-0.98, -0.74, 3.14, 3.27), 'z', lift=0.012, grid=(2, 1))
    for x in (-1.0, 1.0):
        K.rounded_rect(part, shell, 'lamp_head', x, 3.20, 0.16, 0.16, 0.08, 'z', lift=0.012)
    # express + tail lamp units low on the nose
    for x in (-0.95, 0.95):
        K.rounded_rect(part, shell, 'lamp_house', x, 1.47, 0.44, 0.18, 0.07, 'z', lift=0.006)
        K.rounded_rect(part, shell, 'lens', x, 1.47, 0.36, 0.11, 0.05, 'z', lift=0.01)


def nose_z(shell, x, y):
    h = shell.hit((x, y, 30.0), (0, 0, -1))
    return h[0].z if h else NOSE


def skirt(part, shell):
    """the silver skirt under the cab face with the coupler in its opening"""
    xs = [-1.30 + 2.6 * i / 16 for i in range(17)]
    top, bottom = BOTTOM + 0.01, 0.33
    for i in range(16):
        xa, xb = xs[i], xs[i + 1]
        if -0.42 < (xa + xb) / 2 < 0.42:
            y0 = 0.88
        else:
            y0 = bottom
        za, zb = nose_z(shell, xa, 1.05) - 0.05, nose_z(shell, xb, 1.05) - 0.05
        part.face([(xa, y0, za + 0.02), (xb, y0, zb + 0.02), (xb, top, zb), (xa, top, za)], 'skirt', smooth=True)
    # the opening's back wall
    zc = nose_z(shell, 0.0, 1.05) - 0.30
    part.face([(-0.42, bottom, zc), (0.42, bottom, zc), (0.42, 0.88, zc), (-0.42, 0.88, zc)], 'dark')
    # coupler: shank and head reaching the coupling plane (9 m)
    part.box('coupler', -0.07, 0.07, 0.70, 0.82, zc, 8.90)
    part.box('coupler', -0.18, 0.18, 0.60, 0.90, 8.88, 9.0, bevel=0.02)


def gangway(part, z, sign):
    part.box('dark', -0.55, 0.55, FLOOR, 3.15, min(z, z + sign * 0.24), max(z, z + sign * 0.24), bevel=0.03)


def roof_gear(part, panto):
    for c in (-4.2, 4.2):
        part.box('ac', -0.85, 0.85, 3.50, 3.86, c - 1.2, c + 1.2, bevel=0.08, segments=3)
    if panto:
        zc = 5.7
        for dx in (-0.55, 0.55):
            for dz in (-0.55, 0.55):
                part.cylinder('ac', (dx, 3.66, zc + dz), 0.06, 0.16, axis='y', segments=10)
        part.box('panto', -0.62, 0.62, 3.74, 3.80, zc - 0.65, zc + 0.65)
        part.beam('panto', (0.0, 3.80, zc - 0.55), (0.0, 4.45, zc + 0.55), 0.10, 0.08)
        part.beam('panto', (0.0, 4.45, zc + 0.55), (0.0, 4.95, zc - 0.25), 0.06, 0.05)
        part.box('panto', -0.85, 0.85, 4.95, 5.0, zc - 0.36, zc - 0.14)
        for x in (-0.85, 0.85):
            part.beam('panto', (x, 4.97, zc - 0.25), (x * 1.12, 4.86, zc - 0.25), 0.04, 0.04)


def underfloor(part, motor, cab):
    part.box('dark', -1.36, 1.36, 0.93, BOTTOM + 0.02, -END + 0.1, (NOSE - 0.3) if cab else END - 0.1)
    boxes = ([(0.05, 1.25, 0.42, -3.8, -1.0), (-1.25, -0.1, 0.50, -0.6, 1.6), (0.2, 1.2, 0.55, 1.9, 4.2), (-1.2, -0.3, 0.6, -4.3, -2.6)]
             if motor else [(-1.2, 0.0, 0.5, -3.6, -1.2), (0.3, 1.25, 0.55, -0.4, 2.4), (-1.1, -0.2, 0.62, 2.8, 4.3)])
    for x0, x1, y0, z0, z1 in boxes:
        part.box('dark', x0, x1, y0, 0.94, z0, z1, bevel=0.02)


def bogies(part, motor):
    for zb in (-BOGIE, BOGIE):
        for dz in (-1.05, 1.05):
            for x in (-0.72, 0.72):
                part.cylinder('wheel', (x, 0.43, zb + dz), 0.43, 0.13, axis='x', segments=20)
            part.cylinder('bogie', (0, 0.43, zb + dz), 0.08, 1.6, axis='x', segments=8, cap=False)
            for x in (-1.0, 1.0):
                part.box('bogie', x - 0.1, x + 0.1, 0.32, 0.55, zb + dz - 0.16, zb + dz + 0.16, bevel=0.02)
        for x in (-0.94, 0.94):
            part.box('bogie', x - 0.08, x + 0.08, 0.40, 0.72, zb - 1.45, zb + 1.45, bevel=0.04)
            part.cylinder('dark', (x, 0.84, zb), 0.24, 0.22, axis='y', segments=14)
        part.box('bogie', -1.0, 1.0, 0.50, 0.70, zb - 0.25, zb + 0.25, bevel=0.03)
        if motor:
            for dz in (-0.55, 0.55):
                part.cylinder('bogie', (0.15 * (1 if dz > 0 else -1), 0.45, zb + dz), 0.24, 0.55, axis='x', segments=12)


def build_car(name, mats, kind, z_offset, flip=False):
    """kind: 'cab' (cab at +z, motor car) or 'middle' (pantograph trailer)"""
    root = K.car_empty(name, z_offset)
    if flip:
        root.rotation_euler = (0, 0, math.pi)
    cab = kind == 'cab'
    shell = K.Shell(section(), -END, NOSE if cab else END)
    body = K.Part(f'{name}_body')
    shell.build(body, {'front': CAB if cab else GANGWAY, 'rear': GANGWAY})
    if STAGE >= 3:
        for s in (1, -1):
            side(body, shell, s, cab)
        if cab:
            cab_face(body, shell)
    body.build(root, mats)
    if STAGE >= 4:
        gear = K.Part(f'{name}_gear')
        roof_gear(gear, panto=not cab)
        underfloor(gear, motor=cab, cab=cab)
        bogies(gear, motor=cab)
        if cab:
            skirt(gear, shell)
        else:
            gangway(gear, END, 1)
        gangway(gear, -END, -1)
        gear.build(root, mats)
    return root


def main():
    K.clear_scene()
    mats = materials()
    cars = [build_car('car0', mats, 'cab', 0.0)]
    if STAGE >= 5:
        cars.append(build_car('car1', mats, 'middle', -18.0))
        cars.append(build_car('car2', mats, 'cab', -36.0, flip=True))
    if OUT:
        K.export_glb(OUT, cars)
    if RENDER:
        K.stage_render(RENDER, cars, camera=VIEW)


main()
