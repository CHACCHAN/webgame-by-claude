"""
The cabin seen through the glass: carpeted floor, door cards with arm rests, firewall and dash with the instruments'
hood, two front seats with bolsters and head rests on posts, the rear bench, the luggage deck under the hatch, the
grey headliner, the three-spoke wheel on the right (RHD), gear lever, hand brake and the mirror at the screen's top.
The shell is built as a half and mirrored (build_halves); the furniture comes from car_common (furnish).
"""
import math

from mathutils import Vector

import car_common as CC
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
        mesh.face([(0, ya, a), (x_in(a), ya, a), (x_in(b), yb, b), (0, yb, b)], 'c_carpet', out=(0, 1, 0))
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
    mesh.face([(0, top - 0.04, z0), (xf, top - 0.04, z0), (xf, top, z1), (0, top, z1)], 'c_dash', out=(0, 1, 0))
    # rear face down to the knee panel, then back to the firewall
    mesh.face([(0, top, z1), (xf, top, z1), (xf, 0.64, z1 + 0.06), (0, 0.64, z1 + 0.06)], 'trim', out=(0, 0, -1))
    mesh.face([(0, 0.64, z1 + 0.06), (xf, 0.64, z1 + 0.06), (xf, 0.64, z0), (0, 0.64, z0)], 'interior', out=(0, -1, 0))
    mesh.face([(xf, 0.64, z0), (xf, 0.64, z1 + 0.06), (xf, top, z1), (xf, top - 0.04, z0)], 'interior', out=(-1, 0, 0))
    # centre console (half)
    mesh.box('interior', 0.0, 0.095, FLOOR_Y, 0.52, -0.45, 0.46)


def seats(mesh):
    """left half: the luggage deck's front edge (closes the step behind the rear seat)"""
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
            mesh.face(q, 'c_lining', out=(0, -1, 0))


def furnish(mesh):
    """the whole cabin's furniture (not mirrored: the driver sits on the right, −x)"""
    for x in (-0.36, 0.36):
        CC.seat(mesh, x, FLOOR_Y, -0.52, width=0.50, length=0.50, h=0.20, back=0.60, recline=20.0, headrest='posts')
    CC.bench(mesh, -0.54, 0.54, FLOOR_Y, -1.30, length=0.44, h=0.18, back=0.46, recline=28.0)
    CC.steering_wheel(mesh, (-0.36, 0.78, 0.25), tilt=28.0, R=0.180)
    CC.binnacle(mesh, -0.36, 0.858, 0.40, width=0.42, height=0.070, depth=0.22, drop=0.030)
    CC.gear_lever(mesh, 0.0, 0.52, 0.12)
    CC.hand_brake(mesh, 0.0, 0.52, -0.42)
    CC.inside_mirror(mesh, 1.165, 0.22)
    for s in (1, -1):
        CC.arm_rest(mesh, s * x_in(-0.15), 0.60, -0.40, 0.12, s)


def build_halves(mesh):
    shell(mesh)
    dash(mesh)
    seats(mesh)
    headliner(mesh)
