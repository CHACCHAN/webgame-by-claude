"""
The FD3S body's shape as numbers: the half-section key points ("rails") along the car, and the rings that close the
nose round the main intake and the tail round the number plate recess. `key_grid()` gives the grid of key points the
spline surface (shiden_surf.surface) passes through.

Rails (half section, from the bottom centre round the side to the top centre):
  0 floor centre  1 floor edge  2 rocker (bottom of the side)  3 lower side  4 widest  5 shoulder
  6 beltline / front fender crest / rear hip  7 roof edge / bonnet edge  8 roof bubble / bonnet  9 top centre
Figures: wheelbase 2.425, track 1.46, length 4.285, width 1.76, height 1.23 (Mazda, GF-FD3S Type RS); the profile,
plan and sections are measured on the reference photos (see the report) and checked by silhouette overlays.
"""
import math

import numpy as np

from shiden_surf import table

WB = 2.425
ZF = WB / 2            # front axle
ZR = -WB / 2           # rear axle
TRACK = 1.46
TYRE_R = 0.31          # the game's wheelRadius (235/45R17 is 0.322; the physics uses 0.31)
NOSE = 2.070           # front-most point (front overhang 0.87, from the photo bundle)
TAIL = -2.205          # rear-most point (length 4.285)
HALF_W = 0.88
ROOF = 1.23

N_RAILS = 10

# ---------------------------------------------------------------- rail tables: z → value

Y = table({
    # 0/1: the floor (flat between the arches, tucked up at the ends)
    'floor': [(-2.05, 0.30), (-1.8, 0.24), (-1.5, 0.18), (1.2, 0.15), (1.45, 0.16), (1.7, 0.175), (1.9, 0.18)],
    # 2: bottom of the side (rocker lower edge; the bumpers' lower edges at the ends)
    'r2': [(-2.05, 0.33), (-1.8, 0.28), (-1.5, 0.235), (-1.2, 0.215), (1.2, 0.205), (1.6, 0.20), (1.9, 0.20)],
    'r3': [(-2.05, 0.42), (-1.75, 0.37), (-1.4, 0.33), (0.0, 0.32), (1.4, 0.31), (1.9, 0.29)],
    'r4': [(-2.05, 0.55), (-1.6, 0.53), (-1.2, 0.52), (0.0, 0.49), (1.2, 0.48), (1.6, 0.44), (1.9, 0.39)],
    'r5': [(-2.05, 0.72), (-1.6, 0.735), (-1.2, 0.735), (-0.7, 0.71), (0.0, 0.695), (0.7, 0.69), (1.2, 0.685), (1.6, 0.62), (1.9, 0.53)],
    # 6: rear hip / beltline (glass base) / front fender crest
    'r6': [(-2.05, 0.795), (-1.7, 0.845), (-1.35, 0.862), (-1.05, 0.86), (-0.8, 0.852), (-0.4, 0.843), (0.0, 0.835), (0.4, 0.823), (0.75, 0.805), (1.0, 0.792), (1.25, 0.775), (1.5, 0.735), (1.7, 0.68), (1.9, 0.61)],
    # 7: roof edge in the cabin; the hatch glass's side; the bonnet's edge ahead of the windscreen
    'r7': [(-2.05, 0.80), (-1.75, 0.85), (-1.45, 0.89), (-1.15, 0.955), (-0.85, 1.042), (-0.6, 1.095), (-0.35, 1.12), (-0.05, 1.125), (0.12, 1.06), (0.28, 0.95), (0.42, 0.83), (0.6, 0.77), (1.0, 0.745), (1.25, 0.728), (1.5, 0.692), (1.7, 0.645), (1.9, 0.588)],
    'r8': [(-2.05, 0.805), (-1.75, 0.858), (-1.55, 0.895), (-1.3, 0.965), (-1.0, 1.051), (-0.75, 1.13), (-0.5, 1.185), (-0.3, 1.197), (-0.05, 1.181), (0.15, 1.085), (0.35, 0.97), (0.52, 0.85), (0.65, 0.79), (1.0, 0.738), (1.4, 0.69), (1.7, 0.632), (1.9, 0.578)],
    'r9': [(-2.05, 0.805), (-1.75, 0.856), (-1.55, 0.892), (-1.3, 0.96), (-1.0, 1.047), (-0.75, 1.125), (-0.5, 1.178), (-0.3, 1.19), (-0.05, 1.175), (0.15, 1.081), (0.35, 0.97), (0.55, 0.85), (0.68, 0.795), (1.0, 0.742), (1.4, 0.694), (1.7, 0.636), (1.9, 0.58)],
})

X = table({
    'floor_edge': [(-2.05, 0.50), (-1.7, 0.68), (-1.2, 0.74), (1.2, 0.74), (1.6, 0.66), (1.9, 0.52)],
    'r2': [(-2.05, 0.64), (-1.85, 0.765), (-1.5, 0.835), (-1.0, 0.835), (0.0, 0.83), (1.0, 0.835), (1.5, 0.82), (1.75, 0.75), (1.9, 0.63)],
    'r3': [(-2.05, 0.70), (-1.85, 0.812), (-1.5, 0.862), (-1.0, 0.866), (0.0, 0.855), (1.0, 0.866), (1.5, 0.85), (1.75, 0.78), (1.9, 0.67)],
    'r4': [(-2.05, 0.72), (-1.85, 0.83), (-1.5, 0.872), (-1.0, 0.875), (0.0, 0.862), (1.0, 0.875), (1.5, 0.855), (1.75, 0.79), (1.9, 0.68)],
    'r5': [(-2.05, 0.70), (-1.85, 0.80), (-1.5, 0.845), (-1.0, 0.845), (-0.5, 0.835), (0.0, 0.83), (0.6, 0.835), (1.0, 0.84), (1.4, 0.815), (1.75, 0.74), (1.9, 0.63)],
    'r6': [(-2.05, 0.60), (-1.85, 0.685), (-1.5, 0.745), (-1.2, 0.76), (-0.9, 0.766), (-0.5, 0.772), (0.0, 0.775), (0.4, 0.745), (0.75, 0.712), (1.0, 0.70), (1.3, 0.69), (1.6, 0.655), (1.9, 0.55)],
    'r7': [(-2.05, 0.50), (-1.75, 0.565), (-1.4, 0.592), (-1.0, 0.598), (-0.8, 0.592), (-0.4, 0.562), (-0.05, 0.545), (0.2, 0.60), (0.42, 0.64), (0.6, 0.57), (1.0, 0.515), (1.5, 0.48), (1.9, 0.40)],
    'r8': [(-2.05, 0.26), (-1.4, 0.28), (-0.6, 0.28), (0.0, 0.29), (0.5, 0.31), (1.0, 0.31), (1.6, 0.29),
           (1.9, 0.24)],
})


def section(z):
    """the ten key points (x, y) of the half section at station z (regular part of the body)"""
    fy = Y['floor'](z)
    return np.array([
        (0.0, fy),
        (X['floor_edge'](z), fy),
        (X['r2'](z), Y['r2'](z)),
        (X['r3'](z), Y['r3'](z)),
        (X['r4'](z), Y['r4'](z)),
        (X['r5'](z), Y['r5'](z)),
        (X['r6'](z), Y['r6'](z)),
        (X['r7'](z), Y['r7'](z)),
        (X['r8'](z), Y['r8'](z)),
        (0.0, Y['r9'](z)),
    ])


# ---------------------------------------------------------------- the ends

# the main intake's lip (front view, half outline k = 0..9) and the face round it (from photo 01 / the bundle)
INTAKE = [(0.0, 0.252), (0.20, 0.251), (0.33, 0.257), (0.40, 0.276), (0.425, 0.32), (0.415, 0.36), (0.37, 0.388),
          (0.26, 0.398), (0.13, 0.402), (0.0, 0.404)]
FACE = [(0.0, 0.18), (0.36, 0.178), (0.58, 0.184), (0.70, 0.225), (0.755, 0.32), (0.74, 0.425), (0.67, 0.49),
        (0.51, 0.522), (0.27, 0.535), (0.0, 0.538)]
REAR_RING = [(0.0, 0.31), (0.12, 0.31), (0.19, 0.32), (0.205, 0.36), (0.205, 0.42), (0.205, 0.48), (0.19, 0.525),
             (0.12, 0.53), (0.06, 0.532), (0.0, 0.533)]
REAR_FACE = [(0.0, 0.28), (0.41, 0.285), (0.62, 0.31), (0.73, 0.40), (0.775, 0.55), (0.765, 0.69), (0.69, 0.775),
             (0.48, 0.80), (0.26, 0.805), (0.0, 0.805)]


def front_face_z(x, y):
    """how far forward the bumper face comes at (x, y): round in plan, leaning back above the mouth (bundle points:
    plate 2.055 at y 0.47, badge 1.965 at 0.61, combination lamps 1.979 at x 0.45 and 1.832 at x 0.71)"""
    u = min(1.0, abs(x) / 0.80)
    plan = 0.30 * u ** 2.0
    lean = 1.1 * (y - 0.43) ** 1.25 if y > 0.43 else 0.0
    if y < 0.30:
        lean = 0.3 * (0.30 - y)
    return NOSE - plan - lean


def rear_face_z(x, y):
    """the tail (bundle: rear badge −2.098 at y 0.73, lamps −2.056 / −1.906 at x 0.36 / 0.72, plate −2.165)"""
    u = min(1.0, abs(x) / 0.82)
    a = 0.185 + max(0.0, y - 0.48) * 0.37
    plan = a * u ** 2.5
    if y > 0.45:
        lean = 0.107 * ((y - 0.45) / 0.27) ** 1.6
    elif y < 0.36:
        lean = 0.55 * (0.36 - y) ** 1.25
    else:
        lean = 0.0
    return TAIL + plan + lean


Z_FRONT = 1.62           # last regular station ahead of the front arch
Z_REAR = -1.66           # last regular station behind the rear arch
CORNER_RINGS = 7
# Hermite tangent lengths per rail (× chord): larger = squarer corner
K_FRONT = (1.0, 1.0, 1.05, 1.1, 1.1, 1.1, 1.15, 1.15, 1.15, 1.15)
K_REAR = (1.1, 1.1, 1.3, 1.4, 1.45, 1.5, 1.55, 1.6, 1.6, 1.6)


def _corner(z0, face, pole, k_tan=(1.15,) * 10, rings=CORNER_RINGS):
    """
    Rings turning the corner from the regular section at z0 onto the end face: each rail runs a cubic Hermite from
    its section point (leaving along the rail) to its face-ring point (arriving heading for the pole).
    """
    S0 = section(z0)
    h = 0.01
    dS = (section(z0 + h) - section(z0 - h)) / (2 * h)
    sgn = 1.0 if face[0][2] > z0 else -1.0
    out = []
    P0 = np.array([(x, y, z0) for x, y in S0])
    T0 = np.array([(dx * sgn, dy * sgn, sgn) for dx, dy in dS])
    P1 = np.asarray(face, float)
    T1 = np.asarray(pole, float)[None, :] - P1
    for k in range(len(P0)):
        c = np.linalg.norm(P1[k] - P0[k])
        T0[k] *= k_tan[k] * c / np.linalg.norm(T0[k])
        n1 = np.linalg.norm(T1[k])
        T1[k] = T1[k] * (k_tan[k] * c / n1) if n1 > 1e-9 else T0[k]
    for i in range(1, rings + 1):
        t = i / (rings + 1)
        h00, h10, h01, h11 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        out.append(h00 * P0 + h10 * T0 + h01 * P1 + h11 * T1)
    return out


def front_rings():
    """rings from the last regular station to the pole in the intake: each is N_RAILS points (x, y, z)"""
    face = np.array([(x, y, front_face_z(x, y)) for x, y in FACE])
    lip = np.array([(x, y, front_face_z(x, y) + 0.004) for x, y in INTAKE])
    pole = (0.0, 0.33, NOSE - 0.03)
    return _corner(Z_FRONT, face, pole, K_FRONT) + [face, lip, np.array([pole] * N_RAILS)]


def rear_rings():
    face = np.array([(x, y, rear_face_z(x, y)) for x, y in REAR_FACE])
    ring = np.array([(x, y, rear_face_z(x, y) - 0.002) for x, y in REAR_RING])
    pole = (0.0, 0.42, TAIL + 0.03)
    corner = _corner(Z_REAR, face, pole, K_REAR)
    return [np.array([pole] * N_RAILS), ring, face] + corner[::-1]


def regular_stations():
    n = int(round((Z_FRONT - Z_REAR) / 0.075))
    return list(np.linspace(Z_REAR, Z_FRONT, n + 1))


def key_grid():
    """stations from the tail's pole to the nose's pole; each N_RAILS × 3"""
    rows = []
    rows += rear_rings()
    for z in regular_stations():
        S = section(z)
        rows.append(np.array([(x, y, z) for x, y in S]))
    rows += front_rings()
    return np.array(rows)


# dense sampling: steps per key interval along the rails (rear pole → nose pole) and across them (rail k → k+1)
def steps_along(n_keys):
    s = [3] * (n_keys - 1)
    s[0] = 2          # pole → plate ring (cut away)
    s[1] = 4          # plate ring → rear face
    for i in range(2, 2 + CORNER_RINGS + 1):
        s[i] = 2      # round the tail's corner
    s[-1] = 2         # intake lip → pole (cut away)
    s[-2] = 4         # face → intake lip
    for i in range(3, 3 + CORNER_RINGS + 1):
        s[-i] = 2
    return s


STEPS_ACROSS = [1, 2, 4, 5, 6, 4, 7, 6, 5]
