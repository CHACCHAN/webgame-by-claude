"""
The rider for the motorcycles of TOUGE NOCTURNE: a generic adult (about 1.75 m) in one-piece leathers with a speed hump,
gloves, boots and a full-face helmet with a dark visor. Our own design (no brand, nobody's likeness).

Parametric: `build(part, pose)` puts the rider into a Part, posed by the bike's contact points (game frame, metres):
  pose = {'hip': (0, y, z)            the H-point: hip joints' midpoint, just above the seat,
          'grips': ((x, y, z), ...)   left, right grip centres,
          'pegs': ((x, y, z), ...)    left, right footpeg tips (the ball of the boot rests on them),
          'reach': 0.46               shoulder-to-grip distance wanted (elbows bent),
          'head_up': 0.0              extra head lift (rad), 'look': 0.0 helmet pitch (rad, + = chin down),
          'knee_out': 0.05            how far the knees sit outside the tank line}
Materials: rider_suit, rider_trim (panels), rider_glove, rider_boot, rider_helmet, rider_helmet2, visor, rider_slider.
"""
import math

import numpy as np

import bike_kit as K

# body measures (m)
SPINE = 0.53        # hip joints' midpoint → shoulder joints' midpoint
HIP_W = 0.095       # half the distance between the hip joints
SHO_W = 0.185       # half the distance between the shoulder joints
UPPER_ARM = 0.30
FOREARM = 0.27      # elbow → grip centre (wrist + half a fist)
THIGH = 0.45
SHIN = 0.45
NECK = 0.055


def ik2(a, t, l1, l2, pole):
    """the middle joint of a two-bone chain from a to t, bending towards pole (a direction)"""
    a, t = np.array(a, float), np.array(t, float)
    d = t - a
    L = np.linalg.norm(d)
    L = min(L, (l1 + l2) * 0.995)
    u = K.unit(d)
    t = a + u * L
    x = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    h = math.sqrt(max(0.0, l1 * l1 - x * x))
    p = np.array(pole, float)
    p = K.unit(p - u * (p @ u))
    return a + u * x + p * h, t


def sphere(part, mat, c, r, seg=12, rings=8, scale=(1, 1, 1)):
    rows = []
    for j in range(rings + 1):
        th = math.pi * j / rings
        row = []
        for i in range(seg):
            ph = 2 * math.pi * i / seg
            row.append((c[0] + r * scale[0] * math.sin(th) * math.cos(ph), c[1] - r * scale[1] * math.cos(th),
                        c[2] + r * scale[2] * math.sin(th) * math.sin(ph)))
        rows.append(row)
    part.loft(rows, mat, closed=True, flip=True)


def limb(part, a, b, ra, rb, mat, seg=12, n=5, mats=None, bulge=0.0, ref=None):
    """a tapered tube from a to b (radii ra → rb), with a little muscle bulge in the middle"""
    a, b = np.array(a, float), np.array(b, float)
    path, rad = [], []
    for k in range(n):
        s = k / (n - 1)
        path.append(a + (b - a) * s)
        rad.append(K.lerp(ra, rb, s) * (1 + bulge * math.sin(math.pi * s)))
    part.tube(path, rad, mat, seg=seg, cap0=False, cap1=False, twist_ref=ref, mats=mats)


def torso(part, hip, sho, up_hint):
    """the torso as a loft along a bowed spine from the seat to the neck, with the speed hump on the back"""
    H, S = np.array(hip, float), np.array(sho, float)
    ax = K.unit(S - H)
    back = K.unit(np.cross(np.array([1.0, 0, 0]), ax))        # perpendicular to the spine, towards the back/up
    if back @ np.array(up_hint) < 0:
        back = -back
    L = np.linalg.norm(S - H)
    # spine control: bowed towards the back (a rounded crouch)
    C = (H + S) / 2 + back * 0.045
    # sections: s along the spine (0 = seat, 1 = neck base), half-width, half-depth (front, back), centre shift (back)
    sec = [(-0.10, 0.155, 0.125, 0.110, -0.01), (0.0, 0.180, 0.130, 0.125, 0.0), (0.18, 0.165, 0.120, 0.105, 0.0),
           (0.40, 0.160, 0.120, 0.110, 0.0), (0.62, 0.182, 0.130, 0.125, 0.0), (0.82, 0.212, 0.125, 0.120, 0.0),
           (0.95, 0.218, 0.105, 0.110, -0.01), (1.04, 0.170, 0.080, 0.095, -0.015), (1.12, 0.080, 0.060, 0.080, -0.01)]
    seg = 24
    rings = []
    for s, hw, df, db, sh in [(s, *rest) for s, *rest in sec]:
        t = min(1.0, max(0.0, s))
        p = (1 - t) ** 2 * H + 2 * t * (1 - t) * C + t * t * S
        if s < 0:
            p = H + ax * s * L
        if s > 1:
            p = S + ax * (s - 1) * L
        tan = K.unit(2 * (1 - t) * (C - H) + 2 * t * (S - C)) if 0 <= s <= 1 else ax
        bk = K.unit(np.cross(np.array([1.0, 0, 0]), tan))
        if bk @ back < 0:
            bk = -bk
        ring = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            cx, cy = math.cos(a), math.sin(a)            # cx: lateral, cy: + back / - front
            e = 2.6                                       # superellipse exponent (boxy torso)
            fx = math.copysign(abs(cx) ** (2 / e), cx)
            fy = math.copysign(abs(cy) ** (2 / e), cy)
            d = db if cy > 0 else df
            # the speed hump: a ridge on the back between the shoulder blades and the neck
            hump = 0.0
            if cy > 0:
                hump = 0.055 * K.smoothstep(0.55, 0.9, s) * (1 - K.smoothstep(1.02, 1.12, s)) * max(0.0, cy) ** 3 * \
                    math.exp(-(cx / 0.45) ** 2)
            q = p + np.array([1.0, 0, 0]) * fx * hw + bk * (fy * d + sh + hump)
            ring.append(tuple(q))
        rings.append(ring)
    # trim panels down the flanks (i = 0 and 12 are the sides; 6 is the back, 18 the chest)
    mats = lambda i, j: 'rider_trim' if (2 <= j <= 6 and (i in (23, 0) or i in (11, 12))) else 'rider_suit'
    part.loft(rings, 'rider_suit', closed=True, cap0=True, cap1=False, mats=mats)


def helmet(part, centre, fwd, up, scale=1.0):
    """full-face helmet: a shaped shell with the chin bar, the visor over the eye port, a small spoiler"""
    f = K.unit(fwd)
    u = K.unit(up - f * (np.array(up) @ f))
    l = np.cross(u, f)
    c = np.array(centre, float)
    seg, rings = 28, 16
    R = (0.135 * scale, 0.150 * scale, 0.160 * scale)    # half width, half height, half length
    rows = []
    mat_rows = []
    for j in range(rings + 1):
        th = math.pi * j / rings          # 0 = top
        el = math.pi / 2 - th             # elevation
        row, mrow = [], []
        for i in range(seg):
            az = 2 * math.pi * i / seg - math.pi    # 0 = forward
            dl = math.cos(el) * math.sin(az)
            df = math.cos(el) * math.cos(az)
            du = math.sin(el)
            pf, pl, pu = df * R[2], dl * R[0], du * R[1]
            # the bottom is open and pulled in (neck roll), the back drops lower than the chin
            if du < -0.35:
                k = K.smoothstep(-0.35, -1.0, du)
                pl *= 1 - 0.30 * k
                pf *= 1 - 0.25 * k
            # chin bar: the front lower part pushed forward and down
            if df > 0 and du < 0.1:
                k = K.smoothstep(0.1, -0.6, du) * df ** 1.5
                pf += 0.035 * scale * k
                pu -= 0.02 * scale * k
            # flatter sides
            pl *= 1 - 0.06 * abs(math.sin(az)) ** 4
            # the eye port: visor material, a bit proud of the shell
            port = df > 0.0 and abs(az) < math.radians(74) and \
                math.radians(-20) < el < math.radians(26 - 14 * (abs(az) / math.radians(74)) ** 2)
            vis = 0.0
            if port:
                vis = 0.006 * scale
            p = c + f * pf + l * pl + u * pu
            n = K.unit(f * df / R[2] + l * dl / R[0] + u * du / R[1])
            row.append(tuple(p + n * vis))
            mrow.append(port)
        rows.append(row)
        mat_rows.append(mrow)

    def mats(i, j):
        if mat_rows[j][i] and mat_rows[j + 1][i] and mat_rows[j][(i + 1) % seg] and mat_rows[j + 1][(i + 1) % seg]:
            return 'visor'
        # a graphic band round the shell
        el = math.pi / 2 - math.pi * (j + 0.5) / rings
        az = 2 * math.pi * (i + 0.5) / seg - math.pi
        if math.radians(18) < el < math.radians(40) and abs(az) > math.radians(105):
            return 'rider_helmet2'
        return 'rider_helmet'
    part.loft(rows[:-1], 'rider_helmet', closed=True, flip=True, mats=mats)


def glove(part, grip, bar_out, fwd, up):
    """a fist round the grip: knuckles forward-up, thumb under"""
    g = np.array(grip, float)
    o = K.unit(bar_out)
    u = K.unit(up - o * (np.array(up) @ o))
    f = np.cross(o, u)
    if f @ np.array(fwd) < 0:
        f = -f
    part.obox('rider_glove', tuple(g + u * 0.012 - f * 0.005), (0.10, 0.085, 0.10), axes=(o, u, f), bevel=0.028, seg=3)
    # knuckle guard
    part.obox('rider_trim', tuple(g + u * 0.035 + f * 0.035), (0.075, 0.03, 0.04), axes=(o, u, f), bevel=0.01)


def boot(part, ankle, ball, out):
    """boot: heel at the ankle's back, sole along ankle → ball, a toe slider"""
    A, Bp = np.array(ankle, float), np.array(ball, float)
    f = K.unit(Bp - A)
    f[1] *= 0.5
    f = K.unit(f)
    o = np.array([math.copysign(1.0, out), 0, 0])
    u = K.unit(np.cross(f, o) * math.copysign(1.0, out) * -1)
    if u[1] < 0:
        u = -u
    c = A + (Bp - A) * 0.55 + u * -0.005
    part.obox('rider_boot', tuple(c), (0.10, 0.095, 0.27), axes=(o, u, f), bevel=0.035, seg=3)
    part.obox('rider_slider', tuple(Bp + f * 0.04 + o * 0.045 - u * 0.02), (0.02, 0.04, 0.07), axes=(o, u, f), bevel=0.008)


def build(part, pose):
    H = np.array(pose['hip'], float)
    grips = [np.array(g, float) for g in pose['grips']]
    pegs = [np.array(p, float) for p in pose['pegs']]
    reach = pose.get('reach', 0.46)
    gm = (grips[0] + grips[1]) / 2
    # torso lean: the shoulder line where the arms reach the grips with the wanted bend
    best = None
    for k in range(91):
        th = math.radians(5 + k)
        S = H + np.array([0, math.cos(th), math.sin(th)]) * SPINE
        d = np.linalg.norm(S + np.array([SHO_W, -0.02, 0]) - grips[0])
        if best is None or abs(d - reach) < best[0]:
            best = (abs(d - reach), th, S)
    th, S = best[1], best[2]
    S = S + np.array([0, pose.get('sho_dy', 0.0), 0])
    up_hint = np.array([0, math.sin(th), -math.cos(th)])          # the back's outward normal
    torso(part, H, S, np.array([0, 1.0, -0.4]))
    shoulders = [S + np.array([SHO_W, -0.02, 0]), S + np.array([-SHO_W, -0.02, 0])]
    # arms: elbows out and down
    for sgn, sh, g in ((1, shoulders[0], grips[0]), (-1, shoulders[1], grips[1])):
        el, wr = ik2(sh, g, UPPER_ARM, FOREARM, (sgn * 0.8, -0.6, -0.2))
        sphere(part, 'rider_suit', sh, 0.080, scale=(1, 0.95, 1.05))
        limb(part, sh, el, 0.064, 0.052, 'rider_suit', bulge=0.10, mats=lambda i, j: 'rider_trim' if i in (2, 3) else 'rider_suit')
        sphere(part, 'rider_suit', el, 0.052)
        wrist = g - K.unit(g - el) * 0.06
        limb(part, el, wrist, 0.053, 0.040, 'rider_suit', bulge=0.10)
        # gauntlet cuff
        limb(part, wrist - K.unit(g - el) * 0.07, wrist + K.unit(g - el) * 0.01, 0.045, 0.046, 'rider_glove', n=2)
        glove(part, g, (sgn, 0, 0), (0, 0, 1), (0, 1, 0))
    # legs: knees forward, against the tank (a little outside it)
    for sgn, peg in ((1, pegs[0]), (-1, pegs[1])):
        hipj = H + np.array([sgn * HIP_W, -0.01, 0.02])
        ankle = peg + np.array([sgn * 0.005, 0.075, -0.12])
        knee, ankle = ik2(hipj, ankle, THIGH, SHIN, (sgn * pose.get('knee_out', 0.35), 0.55, 1.0))
        sphere(part, 'rider_suit', hipj, 0.11, scale=(0.9, 1, 1.15))
        limb(part, hipj, knee, 0.102, 0.068, 'rider_suit', bulge=0.07)
        sphere(part, 'rider_suit', knee, 0.066)
        # knee slider on the outside of the knee
        kout = knee + np.array([sgn * 0.058, -0.01, 0.0])
        part.obox('rider_slider', tuple(kout), (0.022, 0.075, 0.10), axes=((1, 0, 0), K.unit(knee - ankle), K.unit(np.cross((1, 0, 0), K.unit(knee - ankle)) * -1)), bevel=0.01)
        mid = knee + (ankle - knee) * 0.42
        limb(part, knee, mid, 0.062, 0.054, 'rider_suit', n=3)
        limb(part, mid - (ankle - knee) * 0.03, ankle, 0.056, 0.052, 'rider_boot', n=3)
        sphere(part, 'rider_boot', ankle, 0.052)
        ball = peg + np.array([0, 0.012, 0.02])
        boot(part, ankle, ball, sgn)
    # neck and head
    nb = S + K.unit(S - H) * 0.05 + np.array([0, 0.0, 0.0])
    look_up = pose.get('head_up', 0.0)
    ndir = K.unit(np.array([0, math.cos(th * 0.35 - look_up), math.sin(th * 0.35 - look_up)]))
    hc = nb + ndir * (NECK + 0.085)
    limb(part, nb - ndir * 0.04, nb + ndir * NECK, 0.060, 0.058, 'rider_suit', n=3)
    pitch = pose.get('look', 0.12)
    fwd = np.array([0, -math.sin(pitch), math.cos(pitch)])
    upv = np.array([0, math.cos(pitch), math.sin(pitch)])
    helmet(part, hc + fwd * 0.02, fwd, upv)
    return {'shoulder': S, 'lean_deg': math.degrees(th), 'head': hc}
