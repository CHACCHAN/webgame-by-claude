"""
A simple cabin seen through the glass (the game draws the glass slightly see-through): floor, door cards, firewall
and dash, two front bucket seats, the rear bench, the luggage deck under the hatch, the headliner, and the
steering wheel on the right (RHD). Matte 'interior' with a few 'trim' parts; the cabin closes the body inside.
"""
import math

from mathutils import Vector

import hayate_kit as K
import hayate_body as BD

FLOOR_Y = 0.30
Z_FRONT = BD.Z_COWL - 0.01         # firewall / dash front
Z_BACK = BD.Z_HATCH + 0.03         # behind the luggage deck
DECK_Y = 0.64
X_REAR_IN = 0.56                   # rear trim panels inboard of the wheel houses


def x_in(z):
    """half width of the cabin's side trim at z"""
    x = BD.HULL('h8', z)[0] - 0.055
    if z < -0.70:
        return min(x, K.lerp(x, X_REAR_IN, K.smoothstep(-0.70, -0.85, z)))
    return x


def y_belt(z):
    return BD.HULL('h8', z)[1] - 0.012


def _zs(z0, z1, n):
    return [K.lerp(z0, z1, k / n) for k in range(n + 1)]


def shell(mesh):
    """left half: floor, door card, firewall, rear wall (normals into the cabin)"""
    zs = _zs(Z_FRONT, Z_BACK, 16)
    # side trim from the floor to the belt
    for a, b in zip(zs[:-1], zs[1:]):
        q = [(x_in(a), FLOOR_Y, a), (x_in(b), FLOOR_Y, b), (x_in(b), y_belt(b), b), (x_in(a), y_belt(a), a)]
        mesh.face(q, 'interior', out=(-1, 0, 0))
        # the top of the door card meets the hull's belt (a narrow ledge)
        xa, xb = BD.HULL('h8', a)[0], BD.HULL('h8', b)[0]
        q = [(x_in(a), y_belt(a), a), (x_in(b), y_belt(b), b), (xb - 0.004, y_belt(b) + 0.004, b), (xa - 0.004, y_belt(a) + 0.004, a)]
        mesh.face(q, 'trim', out=(0, 1, 0))
        # floor (the rear part rises to the luggage deck behind the rear seat)
        ya = FLOOR_Y if a > -1.40 else DECK_Y
        yb = FLOOR_Y if b > -1.40 else DECK_Y
        mesh.face([(0, ya, a), (x_in(a), ya, a), (x_in(b), yb, b), (0, yb, b)], 'interior', out=(0, 1, 0))
    # firewall up to the dash
    xf = x_in(Z_FRONT)
    mesh.face([(0, FLOOR_Y, Z_FRONT), (xf, FLOOR_Y, Z_FRONT), (xf, 0.64, Z_FRONT), (0, 0.64, Z_FRONT)], 'interior', out=(0, 0, -1))
    # rear wall behind the deck, up to the hull top
    yb = BD.HULL('h10', Z_BACK)[1] - 0.01
    xb = x_in(Z_BACK)
    mesh.face([(0, DECK_Y, Z_BACK), (xb, DECK_Y, Z_BACK), (xb, y_belt(Z_BACK), Z_BACK), (0, yb, Z_BACK)], 'interior', out=(0, 0, 1))


def dash(mesh):
    """dash: a slab from the windscreen base back over the knees (left half); the console between the seats"""
    xf = x_in(Z_FRONT)
    z0, z1 = Z_FRONT, 0.40
    top = 0.86
    # top surface: under the windscreen, slightly higher at the back edge
    mesh.face([(0, top - 0.04, z0), (xf, top - 0.04, z0), (xf, top, z1), (0, top, z1)], 'interior', out=(0, 1, 0))
    # rear face down to the knee panel, then back to the firewall
    mesh.face([(0, top, z1), (xf, top, z1), (xf, 0.64, z1 + 0.06), (0, 0.64, z1 + 0.06)], 'trim', out=(0, 0, -1))
    mesh.face([(0, 0.64, z1 + 0.06), (xf, 0.64, z1 + 0.06), (xf, 0.64, z0), (0, 0.64, z0)], 'interior', out=(0, -1, 0))
    mesh.face([(xf, 0.64, z0), (xf, 0.64, z1 + 0.06), (xf, top, z1), (xf, top - 0.04, z0)], 'interior', out=(-1, 0, 0))
    # centre console (half)
    mesh.box('interior', 0.0, 0.095, FLOOR_Y, 0.52, -0.45, 0.46)


def _seat(mesh, xc, w, z_front, z_back, y_cush, back_h, back_tilt, bolster=True):
    """cushion + backrest (+ headrest) as boxes; the backrest leans back by back_tilt (rad)"""
    hw = w / 2
    mesh.box('interior', xc - hw, xc + hw, FLOOR_Y + 0.02, y_cush, z_back, z_front, bevel=0.02, segments=1)
    m = K.Mesh('back')
    m.box('interior', xc - hw, xc + hw, 0.0, back_h, -0.10, 0.0, bevel=0.025, segments=1)
    if bolster:
        for s in (-1, 1):
            m.box('interior', xc + s * (hw - 0.04) - 0.04, xc + s * (hw - 0.04) + 0.04, 0.06, back_h * 0.72, -0.10, 0.05, bevel=0.015, segments=1)
        m.box('interior', xc - 0.13, xc + 0.13, back_h + 0.02, back_h + 0.19, -0.09, -0.01, bevel=0.025, segments=1)
    c, s_ = math.cos(back_tilt), math.sin(back_tilt)
    y0, z0 = y_cush - 0.04, z_back + 0.08
    m.warp(lambda p: (p[0], y0 + p[1] * c + p[2] * s_, z0 - p[1] * s_ + p[2] * c))
    mesh.merge(m)


def seats(mesh):
    """left half: the passenger's bucket (the driver's is the mirror image), half the rear bench"""
    _seat(mesh, 0.36, 0.50, -0.02, -0.52, 0.50, 0.62, math.radians(20))
    _seat(mesh, 0.27, 0.54, -0.86, -1.30, 0.48, 0.46, math.radians(28), bolster=False)
    # luggage deck front edge (closes the step behind the rear seat)
    mesh.face([(0, FLOOR_Y, -1.40), (X_REAR_IN, FLOOR_Y, -1.40), (X_REAR_IN, DECK_Y, -1.40), (0, DECK_Y, -1.40)], 'interior', out=(0, 0, 1))


def headliner(mesh):
    """the roof's inside, a little under the roof skin (normals down)"""
    zs = _zs(BD.Z_ATOP - 0.02, BD.Z_CTOP - 0.01, 8)
    rows = []
    for z in zs:
        row = []
        for k in range(6):
            s = k / 5
            x, y = BD.g_top(z, s)
            row.append((x, y - 0.03, z))
        rows.append(row)
    for j in range(len(rows) - 1):
        for i in range(len(rows[0]) - 1):
            q = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
            mesh.face(q, 'interior', out=(0, -1, 0))


def steering(mesh):
    """steering wheel and column on the right-hand side (−x): a rim, three spokes and the hub"""
    centre = Vector((-0.36, 0.80, 0.24))
    d = Vector((0.0, math.sin(math.radians(28)), -math.cos(math.radians(28))))      # towards the driver
    u = Vector((1.0, 0.0, 0.0))
    w = d.cross(u)
    m = K.Mesh('wheel')
    R, r = 0.180, 0.016
    prof = []
    for k in range(13):
        t = math.radians(90 - 360 * k / 12)
        prof.append((r * math.cos(t), R + r * math.sin(t)))
    m.lathe(prof, 28, mats='trim')
    for k in range(3):
        a = math.radians(90 + 120 * k)
        sp = K.Mesh('spoke')
        sp.box('trim', -0.012, 0.004, -0.022, 0.022, 0.0, R - 0.005)
        ca, sa = math.cos(a), math.sin(a)
        sp.warp(lambda p: (p[0], p[1] * ca - p[2] * sa, p[1] * sa + p[2] * ca))
        m.merge(sp)
    m.lathe([(-0.020, 0.055), (0.020, 0.045), (0.020, 0.004)], 16, mats='trim')
    m.warp(lambda p: tuple(centre + d * p[0] + u * p[1] + w * p[2]))
    col = K.Mesh('column')
    col.lathe([(-0.30, 0.032), (0.0, 0.032)], 10, mats='trim')
    col.warp(lambda p: tuple(centre + d * (p[0] - 0.03) + u * p[1] + w * p[2]))
    m.merge(col)
    mesh.merge(m)
    # the instrument hood over the gauges in front of the wheel
    mesh.box('trim', -0.58, -0.14, 0.86, 0.92, 0.42, 0.58, bevel=0.02, segments=1)


def build_halves(mesh):
    shell(mesh)
    dash(mesh)
    seats(mesh)
    headliner(mesh)
