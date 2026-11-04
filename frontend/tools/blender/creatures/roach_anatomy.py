"""
Proportions of the adult American cockroach (Periplaneta americana) in real millimetres, game frame (+x = the insect's
left, +y up, +z forward, ground y = 0, z = 0 at the front of the head seen from above).

Measured on the dorsal photo by Alex Wild (Insects Unlocked, CC0, Commons "Periplaneta americana - American cockroach
(25859665686).jpg", scaled to a 38 mm body): pronotum 7.1 long × 9.6 wide, widest 62 % back; head 1.9 mm ahead of it,
4.9 wide; tegmina 13 mm across, tips 29 mm behind the pronotum; mid feet ±16 mm, hind tarsi reaching 6 mm behind the
wing tips. Leg segment lengths: hind tibia 11.6, hind tarsus 9.5 (photo); the others scaled from the literature
(hind leg ≈ coxa 5.4, femur 9, tibia 11.6, tarsus 9.5 mm). Heights from the side photos (Commons, see list.json).
"""
import math

BODY_LENGTH = 38.0            # head front → wing tips
HEAD_FRONT = 0.0
WING_TIP = -38.0

# ---- pronotum: outline (projected), centre of the outline, dome
PRONOTUM = dict(front=-1.9, rear=-9.0, zc=-6.2, half_w=4.85, rear_sq=2.6,
                top=7.7, front_y=5.7, rear_y=7.55, side_drop=2.0, thick=0.22)

# ---- tegmina: projected half-width of the pair by z (mm) and the dorsal envelope
WING_BASE = -6.6
WING_OUTLINE = [(-6.6, 3.2), (-8.0, 4.5), (-9.0, 4.9), (-12.0, 5.75), (-16.0, 6.4), (-20.0, 6.55), (-25.0, 6.45),
                (-29.0, 5.95), (-32.5, 5.0), (-35.2, 3.9), (-37.0, 2.6), (-38.0, 0.0)]
# envelope: crest height and how far the sides fall at |x| = ENV_A
ENV_TOP = [(-5.0, 5.9), (-7.0, 6.3), (-9.0, 6.8), (-11.5, 7.25), (-14.0, 7.45), (-17.0, 7.5), (-22.0, 7.2), (-27.0, 6.55),
           (-31.0, 5.7), (-34.0, 4.85), (-36.5, 4.05), (-39.0, 3.3)]
ENV_DROP = [(-5.0, 2.9), (-12.0, 3.25), (-22.0, 3.3), (-30.0, 2.9), (-34.0, 2.2), (-39.0, 1.2)]
ENV_A = 7.2
ENV_P = 3.2
WING_THICK = 0.2
# how far each tegmen's inner (anal) margin crosses the midline: the left one lies over the right one
OVERLAP_LEFT = 2.1            # the left tegmen's inner margin, mm right of the midline (visible)
OVERLAP_RIGHT = 1.0           # the right tegmen's inner margin, under the left one

# ---- abdomen (under the tegmina): z, half width, underside y, top y
ABDOMEN = [(-10.0, 3.9, 3.35, 6.2), (-12.5, 5.0, 3.0, 6.6), (-16.0, 5.7, 2.75, 6.75), (-20.0, 5.85, 2.7, 6.6),
           (-24.0, 5.55, 2.75, 6.2), (-27.5, 4.75, 2.9, 5.6), (-30.5, 3.6, 3.15, 4.95), (-32.6, 2.3, 3.45, 4.5),
           (-33.6, 1.2, 3.7, 4.35)]
STERNITES = [-12.4, -15.3, -18.2, -21.0, -23.8, -26.6]    # posterior edges of the visible sternites (2..7 start)

# ---- thorax (under the pronotum and the wing bases): z, half width, underside y, top y
THORAX = [(-2.6, 1.3, 4.4, 5.6), (-3.6, 2.4, 3.8, 6.0), (-5.5, 3.2, 3.6, 6.3), (-8.0, 3.6, 3.5, 6.2),
          (-10.5, 3.9, 3.4, 6.3), (-12.5, 4.0, 3.35, 6.4)]

# ---- head (hypognathous, tucked under the pronotum's front): the capsule along its own axis
HEAD = dict(vertex=(0.0, 5.2, -2.6), axis=(0.0, -1.0, 0.62), length=4.9,
            # half width (x) and front / back depth along the face normal by t along the axis
            width=[(0.0, 1.6), (0.12, 2.15), (0.3, 2.45), (0.45, 2.35), (0.62, 1.95), (0.78, 1.5), (0.9, 1.2), (1.0, 0.9)],
            front=[(0.0, 0.5), (0.15, 0.9), (0.35, 1.45), (0.55, 1.45), (0.75, 1.15), (0.9, 0.75), (1.0, 0.4)],
            back=[(0.0, 1.3), (0.15, 1.6), (0.35, 1.55), (0.55, 1.2), (0.75, 0.8), (0.9, 0.5), (1.0, 0.3)])
# compound eyes (kidney shaped) on the head's upper sides: t range along the head axis, lateral position
EYE = dict(t0=0.08, t1=0.56, half_w=0.62, depth=0.45)
# antenna: socket in the eye's notch (t along the head, x), length, segment count
ANTENNA = dict(t=0.33, x=1.15, length=46.0, annuli=110, scape=(1.25, 0.32), pedicel=(0.5, 0.24), r0=0.17, r1=0.05)
# maxillary palp: 5 segments (mm); labial palp: 3
MAX_PALP = [0.55, 0.5, 1.45, 1.25, 1.35]
LAB_PALP = [0.5, 0.55, 0.9]

# ---- cerci: base, direction, length, segments
CERCUS = dict(base=(1.3, 4.0, -32.4), dir=(0.62, 0.1, -0.78), length=5.2, segs=15, r=0.36)

# ---- legs (left side; right = mirror): coxa base on the thorax, coxa direction, segment lengths, neutral foot,
# the tarsus' heading on the ground, knee pole, coxa swing
LEGS = {
    1: dict(hip=(1.4, 4.0, -3.9), coxa_dir=(0.35, -0.55, -0.6), coxa=3.7, coxa_w=(1.15, 0.6), coxa_t=0.42,
            femur=5.6, femur_r=(0.42, 0.68), tibia=5.0, tibia_r=(0.27, 0.34), tarsi=[1.85, 0.85, 0.65, 0.5, 1.05],
            tarsus_r=0.21, foot=(9.0, 1.5), heading=(0.25, 1.0), pole=(0.8, 0.6, 0.2), swing=0.42, lift=1.8,
            ankle=28, femur_spines=(9, 3), tibia_rows=3, tibia_spines=3, spine_len=(0.9, 1.25)),
    2: dict(hip=(2.0, 3.75, -8.6), coxa_dir=(0.55, -0.35, -0.76), coxa=4.3, coxa_w=(1.35, 0.7), coxa_t=0.48,
            femur=6.9, femur_r=(0.47, 0.76), tibia=7.8, tibia_r=(0.28, 0.37), tarsi=[2.4, 1.05, 0.8, 0.6, 1.15],
            tarsus_r=0.22, foot=(17.8, -20.0), heading=(0.62, -0.78), pole=(1.0, 0.35, 0.0), swing=0.42, lift=2.0,
            ankle=26, femur_spines=(4, 3), tibia_rows=4, tibia_spines=4, spine_len=(1.1, 1.6)),
    3: dict(hip=(2.3, 3.6, -12.2), coxa_dir=(0.45, -0.25, -0.86), coxa=5.3, coxa_w=(1.6, 0.75), coxa_t=0.52,
            femur=8.9, femur_r=(0.52, 0.86), tibia=11.6, tibia_r=(0.3, 0.42), tarsi=[3.9, 1.55, 1.1, 0.8, 1.75],
            tarsus_r=0.24, foot=(12.2, -38.6), heading=(0.45, -0.9), pole=(1.0, 0.3, 0.15), swing=0.4, lift=2.2,
            ankle=24, femur_spines=(4, 3), tibia_rows=4, tibia_spines=6, spine_len=(1.2, 1.9)),
}

# ---- gait: one cycle covers STRIDE mm of ground (1.6 m at game scale), the alternating tripod
STRIDE = 1.6 / (3.4 / 38.0)   # 17.88 mm
DUTY = 0.52                   # share of the cycle a foot is on the ground
FRAMES = 48                   # keyframes per cycle (frame 0 == frame FRAMES)
TRIPOD_A = ('L1', 'R2', 'L3')  # in stance from phase 0, the other tripod from phase 0.5


def interp(table, x):
    """piecewise-linear lookup in [(x, y...)] (x decreasing or increasing); returns a tuple of the y columns"""
    xs = [r[0] for r in table]
    dec = xs[0] > xs[-1]
    rows = list(reversed(table)) if dec else table
    if x <= rows[0][0]:
        return rows[0][1:]
    if x >= rows[-1][0]:
        return rows[-1][1:]
    for a, b in zip(rows[:-1], rows[1:]):
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return tuple(p + (q - p) * t for p, q in zip(a[1:], b[1:]))
    return rows[-1][1:]


def smooth_interp(table, x):
    """a Catmull-Rom curve through the table (single y column)"""
    xs = [r[0] for r in table]
    ys = [r[1] for r in table]
    if xs[0] > xs[-1]:
        xs, ys = xs[::-1], ys[::-1]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = max(k for k in range(len(xs) - 1) if xs[k] <= x)
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    p0 = ys[i - 1] if i > 0 else 2 * ys[i] - ys[i + 1]
    p1, p2 = ys[i], ys[i + 1]
    p3 = ys[i + 2] if i + 2 < len(ys) else 2 * ys[i + 1] - ys[i]
    t2, t3 = t * t, t * t * t
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def env_y(x, z):
    """the dorsal envelope the tegmina lie on: crest height minus a superelliptic fall to the sides"""
    top = smooth_interp(ENV_TOP, z)
    drop = smooth_interp(ENV_DROP, z)
    return top - drop * (abs(x) / ENV_A) ** ENV_P


def env_slope(x, z):
    drop = smooth_interp(ENV_DROP, z)
    if x == 0:
        return 0.0
    return -math.copysign(drop * ENV_P * abs(x) ** (ENV_P - 1) / ENV_A ** ENV_P, x)


def wing_half_width(z):
    return smooth_interp(WING_OUTLINE, z) if z > -32.5 else _tip_half(z)


def _tip_half(z):
    # rounded apex: an ellipse from z = -32.5 (half width 5.0) to the tip
    z0, w0 = -32.5, 5.0
    t = (z0 - z) / (z0 - WING_TIP)
    return w0 * math.sqrt(max(0.0, 1 - t ** 2.2))
