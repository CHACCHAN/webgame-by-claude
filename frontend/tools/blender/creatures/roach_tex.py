"""
Textures of the cockroach, painted with numpy at build time (deterministic): three atlases (shell, body, legs), each
a base colour (sRGB), a tangent-space normal map from a painted height field (mm) and a roughness map (glTF
metallic-roughness: G = roughness, B = 1 so a metallic livery can switch metalness on through the material factor).

The base colour is the natural deep red-brown; the surface detail (wing veins, segment edges, pits, the pronotum's
relief, ommatidia) lives in the normal map as well, so it still shows when a livery replaces the colour map.
Each region is painted in its own coordinates (u, v in 0..1 over the part's parameters; see LAYOUT).
"""
import math
import os

import bpy
import numpy as np

import roach_anatomy as A

# ---------------------------------------------------------------- UV layout: (u0, v0, u1, v1) per part
LAYOUT = {
    # roach_shell
    'tegmen_L': (0.0, 0.0, 0.38, 1.0),
    'tegmen_R': (0.38, 0.0, 0.70, 1.0),
    'pronotum': (0.70, 0.45, 1.0, 1.0),
    'head': (0.70, 0.0, 1.0, 0.45),
    # roach_body (the abdomen's patch is its venter and sides: its back lies under the tergites, see roach_body)
    'abdomen': (0.0, 0.0, 0.5, 0.26),
    # the back under the wings (roach_dorsum), flat projections: the two nota, and the tergites
    'nota': (0.0, 0.26, 0.25, 0.44),
    'tergites': (0.68, 0.6, 1.0, 1.0),
    'root': (0.25, 0.26, 0.5, 0.35),
    'seta': (0.25, 0.35, 0.5, 0.44),
    'thorax': (0.5, 0.0, 0.75, 0.3),
    'eye': (0.75, 0.0, 1.0, 0.15),
    'cercus': (0.75, 0.15, 1.0, 0.3),
    'antenna': (0.5, 0.3, 0.55, 1.0),
    'palp': (0.55, 0.3, 0.62, 1.0),
    'lpalp': (0.62, 0.3, 0.68, 1.0),
    'mouth': (0.68, 0.3, 1.0, 0.6),
    # (both hind wings, across u and along v, as wide as the fan is; the eyes' patch is told by its place, see RoachModel)
    'hindwing': (0.0, 0.44, 0.5, 1.0),
    # roach_legs
    'spine': (0.9, 0.0, 1.0, 0.5),
    'claw': (0.9, 0.5, 1.0, 0.7),
    'pad': (0.9, 0.7, 1.0, 0.9),
}
LEG_V = {'coxa': (0.0, 0.15), 'femur': (0.15, 0.42), 'tibia': (0.42, 0.74), 'tarsus1': (0.74, 0.85),
         'tarsus2': (0.85, 1.0)}
ATLAS_OF = {'roach_shell': ('tegmen_L', 'tegmen_R', 'pronotum', 'head'),
            'roach_body': ('abdomen', 'thorax', 'eye', 'cercus', 'antenna', 'palp', 'lpalp', 'mouth', 'hindwing', 'nota',
                           'tergites', 'root', 'seta'),
            'roach_legs': ('spine', 'claw', 'pad')}


def leg_rect(k, seg, sub=(0.0, 1.0)):
    u0, u1 = (k - 1) * 0.3, k * 0.3
    v0, v1 = LEG_V[seg]
    a, b = sub
    return (u0, v0 + (v1 - v0) * a, u1, v0 + (v1 - v0) * b)


# ---------------------------------------------------------------- noise and helpers

_TABLES = {}


def vnoise(x, y, seed):
    t = _TABLES.get(seed)
    if t is None:
        t = np.random.RandomState(seed).rand(256, 256).astype(np.float32)
        _TABLES[seed] = t
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf = x - xi
    yf = y - yi
    xf = xf * xf * (3 - 2 * xf)
    yf = yf * yf * (3 - 2 * yf)
    x0, x1 = xi & 255, (xi + 1) & 255
    y0, y1 = yi & 255, (yi + 1) & 255
    a = t[y0, x0] * (1 - xf) + t[y0, x1] * xf
    b = t[y1, x0] * (1 - xf) + t[y1, x1] * xf
    return a * (1 - yf) + b * yf


def fbm(x, y, seed, octaves=4):
    s, amp, tot = 0.0, 1.0, 0.0
    for i in range(octaves):
        s = s + amp * vnoise(x * 2 ** i, y * 2 ** i, seed + 17 * i)
        tot += amp
        amp *= 0.5
    return s / tot


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def mix(c0, c1, t):
    c0 = np.asarray(c0, np.float32)
    c1 = np.asarray(c1, np.float32)
    t = np.asarray(t, np.float32)[..., None]
    return c0 * (1 - t) + c1 * t


def ridge(phi, spacing, width):
    """bump profile (0..1) on the level sets phi = n·spacing, `width` mm wide"""
    f = phi / spacing
    d = np.abs(f - np.round(f)) * spacing
    return np.exp(-(d / width) ** 2)


def full(shape, c):
    out = np.empty(shape + (3,), np.float32)
    out[:] = c
    return out


# ---------------------------------------------------------------- tegmina

def paint_tegmen(U, V, shape):
    smin, smax, zmin, zmax = shape.uv_box
    sig = smin + U * (smax - smin)
    z = zmin + V * (zmax - zmin)
    zrow = z[:, 0]
    marg = np.array([shape.margins(float(zz)) for zz in zrow])
    s_in = marg[:, 0][:, None]
    s_out = marg[:, 1][:, None]
    W = np.abs(s_out - s_in) + 1e-3
    t = np.clip((sig - s_in) / (s_out - s_in + 1e-6 * np.sign(s_out - s_in + 1e-9)), -0.2, 1.2)
    a = t * W                                       # mm from the inner margin
    b = shape.z0 - z                                # mm from the base
    ell = np.clip(b / (shape.z0 - shape.apex[1]), 0, 1)
    seed = 11 if shape.side > 0 else 23
    n1 = fbm(sig * 0.9, z * 0.9, seed)
    n2 = fbm(sig * 6.0, z * 6.0, seed + 5)
    # main longitudinal vein (R) and the claval furrow
    tR = 0.70 - 0.16 * ell ** 1.5
    aR = tR * W
    t_cf = 0.52 * (1 - np.clip(ell / 0.36, 0, 1)) ** 0.8
    clavus = (t < t_cf).astype(np.float32)
    # costal field: branches of R running out and back to the costal margin
    th1 = np.radians(31) * (1 - 0.55 * ell)
    phi_c = b * np.sin(th1) - (a - aR) * np.cos(th1)
    # inner field: branches of M / CuA running in and back to the inner margin
    th2 = np.radians(17) * (1 - 0.5 * ell)
    phi_i = b * np.sin(th2) + (a - aR) * np.cos(th2)
    costal = ss(-0.15, 0.15, a - aR)
    main = ridge(phi_c, 0.92, 0.034) * costal + ridge(phi_i, 0.8, 0.032) * (1 - costal)
    fine = ridge(phi_c + 0.46, 0.92 / 3, 0.017) * costal + ridge(phi_i + 0.4, 0.8 / 3, 0.016) * (1 - costal)
    # the clavus: anal veins arc parallel to the furrow
    phi_a = (t_cf - t) * W + 0.15 * b
    anal = ridge(phi_a, 0.55, 0.03) * clavus
    main = main * (1 - clavus) + anal
    fine = fine * (1 - clavus)
    # crossveins: a faint net across the lines
    cross = ridge(phi_c * 0.0 + (a - aR) * np.sin(th1) + b * np.cos(th1), 0.14, 0.012) * (0.35 + 0.65 * (n2 > 0.45))
    vR = np.exp(-((a - aR) / 0.07) ** 2) * (1 - ss(0.85, 1.0, ell))
    furrow = np.exp(-((t - t_cf) * W / 0.05) ** 2) * (t_cf > 0.02)
    edge = np.minimum(np.abs(sig - s_in), np.abs(sig - s_out))
    rim = np.exp(-(edge / 0.12) ** 2)
    h = (0.016 * main + 0.006 * fine + 0.002 * cross + 0.022 * vR - 0.02 * furrow + 0.018 * rim
         + 0.012 * (n1 - 0.5))
    # colour: dark over the overlap and the middle, chestnut, orange costal field, pale amber apex
    dark = (0.22, 0.1, 0.06)
    mid = (0.36, 0.15, 0.07)
    cost = (0.62, 0.3, 0.1)
    apex = (0.83, 0.55, 0.25)
    if shape.side > 0:
        col = mix(dark, mid, ss(0.25, 0.8, t))
    else:
        col = mix(mid, (0.48, 0.2, 0.08), ss(0.3, 0.8, t))
    col = mix(col, cost, ss(0.8, 0.97, t))
    col = mix(col, apex, ss(0.7, 0.98, ell) * (0.55 + 0.45 * np.clip(t, 0, 1)))
    col = mix(col, (0.18, 0.08, 0.06), ss(0.12, 0.0, ell) * 0.6)
    col = col * (0.93 + 0.12 * n1)[..., None] * (0.97 + 0.14 * main + 0.05 * fine)[..., None]
    rough = 0.30 + 0.04 * (n2 - 0.5) + 0.04 * ss(0.75, 1.0, ell) + 0.03 * main
    return col, h, rough


# ---------------------------------------------------------------- hind wings

def _vein(r, phi, at, width, r0=0.0, r1=1e9):
    """a vein on the ray `at` (degrees) from the wing's base, `width` mm wide, between r0 and r1 mm out"""
    d = r * np.radians(np.abs(phi - at))
    return np.exp(-(d / width) ** 2) * ss(r0 - 0.6, r0 + 0.6, r) * ss(r1 + 0.6, r1 - 0.6, r)


def paint_hindwing(U, V):
    """
    A hind wing, painted as it is in flight (the fan open: `unfold` times as wide as the model has it): U across
    from the leading edge's line, V along. The stiff front part with its veins running to the tip and the costal
    margin (the radius and its comb of branches, media, cubitus), the fold behind it, and the fan: veins on rays
    from the wing's base, alternately on the crests and in the furrows of its pleats, a net of cross veins between.
    The membrane is smoky and clear in life: here it is opaque (the game draws no see-through surfaces on the
    cockroach), painted pale with darker veins, lighter in the middle of each cell, a faint sheen of thin-film
    colours over it, and smooth enough to glint.
    """
    H = A.HIND
    L, k = H['length'], H['unfold']
    l = V
    b = l * L                                           # mm from the hinge along the leading edge's line
    a = U * A.hind_across() * k                         # mm behind that line
    inset = H['tip_inset'] * np.clip((l - 0.75) / 0.25, 0, None) ** 2
    t4 = np.clip(l / 0.4, 0, 1)
    f = np.where(l < 0.4, 0.14 + 0.86 * t4 * t4 * (3 - 2 * t4),
                 np.where(l < 0.7, 1.0, np.sqrt(np.clip(1 - ((l - 0.7) / 0.3) ** 2, 0, 1))))
    a_le = inset * k
    a_te = a_le + H['chord'] * f * k
    q = a - a_le                                        # mm behind the leading edge
    e = a_te - a                                        # mm before the trailing edge
    db, da = b + 0.9, a - 0.7
    r = np.hypot(db, da)
    phi = np.degrees(np.arctan2(da, db))
    n1 = fbm(b * 0.35, a * 0.35, 41)
    n2 = fbm(b * 3.0, a * 3.0, 47)
    n3 = fbm(b * 0.12, a * 0.12, 43)
    fold = 19.5
    fan = ss(fold - 0.6, fold + 0.6, phi)               # 1 behind the fold
    # the front part
    costa = np.exp(-(np.clip(q, 0, None) / 0.2) ** 2)
    sc = _vein(r, phi, 1.4, 0.07, 0.0, 10.5)
    rad = _vein(r, phi, 3.1, 0.11)
    comb = ridge(b + q * 2.25, 1.7, 0.06) * ss(3.3, 2.6, phi) * ss(6.5, 8.5, r) * ss(0.05, 0.3, q)
    media = _vein(r, phi, 6.9, 0.085) + _vein(r, phi, 8.4, 0.06, 13.0)
    cub = (_vein(r, phi, 11.4, 0.09) + _vein(r, phi, 13.1, 0.06, 6.0) + _vein(r, phi, 14.7, 0.06, 9.0)
           + _vein(r, phi, 16.2, 0.055, 12.0) + _vein(r, phi, 17.6, 0.05, 15.0))
    furrow = _vein(r, phi, fold, 0.1)
    # the fan: a vein every 2.4°, crests and furrows by turns, thinner ones between them in the outer half
    step = 2.4
    fa = (phi - (fold + step)) / step
    near = np.abs(fa - np.round(fa)) * step
    anal = np.exp(-(r * np.radians(near) / 0.075) ** 2) * fan
    mid = np.abs(fa - 0.5 - np.round(fa - 0.5)) * step
    inter = np.exp(-(r * np.radians(mid) / 0.045) ** 2) * fan * ss(11.0, 15.0, r)
    tri = np.abs(((fa / 2) % 1.0) * 2 - 1) * 2 - 1     # −1 in a furrow … 1 on a crest
    pleat = tri * fan * ss(1.5, 6.0, r)
    # cross veins: short rungs between neighbouring veins, staggered from one cell to the next
    cell = np.where(fan > 0.5, np.floor(fa), np.floor(phi / 1.55) + 40.0)
    shift = np.modf(np.abs(np.sin(cell * 12.9898) * 43758.5453))[0]
    cross = ridge(r + shift * 1.3 + 0.25 * n1, 1.3, 0.022) * ss(0.35, 0.6, n2) * (1 - 0.3 * fan)
    strong = np.clip(costa + rad + 0.8 * (sc + media + cub) + 0.9 * anal, 0, 1)
    fine = np.clip(0.8 * comb + 0.6 * inter + 0.3 * cross, 0, 1)
    rim = np.exp(-(np.clip(e, 0, None) / 0.12) ** 2)
    base = ss(1.9, 0.4, b)                              # the wing's root: small dark plates in pale membrane
    h = (0.03 * (costa + rad) + 0.02 * (sc + media + cub) + 0.018 * anal + 0.008 * comb + 0.006 * inter
         + 0.004 * cross - 0.03 * furrow + 0.085 * pleat + 0.01 * rim + 0.004 * (n1 - 0.5) + 0.025 * base * (n2 - 0.5))
    # the membrane: amber in the stiff front, paler and greyer in the fan, lighter away from the veins
    front_col = mix((0.56, 0.37, 0.18), (0.66, 0.49, 0.27), ss(0.15, 0.95, l))
    fan_col = mix((0.72, 0.62, 0.45), (0.63, 0.53, 0.38), ss(4.5, 0.0, e))
    col = mix(front_col, fan_col, fan)
    col = col * (1.0 + 0.1 * (1 - np.clip(1.6 * strong + fine, 0, 1)) * (0.6 + 0.8 * n1))[..., None]
    # thin-film colours: faint bands of rose, gold and green wandering over the membrane
    ph = 2 * math.pi * (1.6 * n3 + 0.9 * n1 + 0.035 * r)
    film = np.stack([np.cos(ph), np.cos(ph + 2.1), np.cos(ph + 4.2)], axis=-1)
    col = col + film * (0.007 + 0.011 * fan)[..., None]
    col = mix(col, (0.3, 0.13, 0.06), np.clip(0.92 * strong, 0, 1))
    col = mix(col, (0.36, 0.18, 0.09), fine * 0.75 * (1 - strong))
    col = mix(col, (0.42, 0.26, 0.14), 0.5 * rim * (1 - strong))
    col = mix(col, (0.5, 0.36, 0.2), 0.35 * furrow)
    plates = ss(0.42, 0.66, fbm(b * 1.3, a * 1.3, 49))
    col = mix(col, mix((0.7, 0.52, 0.31), (0.33, 0.15, 0.07), plates), base * 0.9)
    col = col * (0.95 + 0.1 * n2)[..., None]
    rough = 0.2 + 0.05 * (n2 - 0.5) + 0.16 * strong + 0.08 * fine + 0.2 * base
    return col, h, rough


# ---------------------------------------------------------------- pronotum

def paint_pronotum(U, V):
    import roach_body as RB
    P = A.PRONOTUM
    X0, X1, Z0, Z1 = -5.3, 5.3, P['rear'] - 0.5, P['front'] + 0.5
    x = X0 + U * (X1 - X0)
    z = Z0 + V * (Z1 - Z0)
    # outline radius by polar angle round the centre
    ths = np.linspace(0, 2 * math.pi, 1441)
    ol = np.array([RB.pronotum_outline(t) for t in ths])
    ang = np.arctan2(ol[:, 1] - P['zc'], ol[:, 0])
    rad = np.hypot(ol[:, 0], ol[:, 1] - P['zc'])
    o = np.argsort(ang)
    ang, rad = ang[o], rad[o]
    pa = np.arctan2(z - P['zc'], x)
    pr = np.hypot(x, z - P['zc'])
    R = np.interp(pa, ang, rad, period=2 * math.pi)
    rho = pr / R
    dist = R - pr                                    # mm inside the outline (radial)
    n1 = fbm(x * 1.3, z * 1.3, 31)
    n2 = fbm(x * 4.0, z * 4.0, 37)
    n3 = fbm(x * 12.0, z * 12.0, 41)
    cream = (0.84, 0.66, 0.4)
    tan = (0.7, 0.4, 0.17)
    dark = (0.17, 0.08, 0.045)
    col = full(x.shape, cream)
    # the dark centre and its orange-brown halo
    front = ss(-6.6, -2.0, z)                        # 1 at the front
    band = 0.4 + 0.45 * front + 0.25 * (n1 - 0.5)
    inner = ss(band, band + 0.8, dist)               # 0 in the ring, 1 inside
    col = mix(col, tan, inner)
    # the dark pattern: two broad lobes meeting at the midline behind a pale notch, ragged edges
    lob = np.zeros_like(x)
    for sx in (1.0, -1.0):
        cx, cz = 1.25 * sx, -4.5
        dx = (x - cx) / 2.0
        dz = (z - cz) / np.where(z > cz, 1.45, 1.2)
        r = np.sqrt(dx * dx + dz * dz) + 0.38 * (n2 - 0.5) + 0.15 * (n3 - 0.5)
        lob = np.maximum(lob, ss(1.08, 0.72, r))
    notch = np.exp(-(x / (0.16 + 0.25 * ss(-4.6, -2.8, z))) ** 2) * ss(-4.4, -3.2, z)
    lob = lob * (1 - 0.95 * notch)
    col = mix(col, (0.45, 0.2, 0.08), ss(0.0, 0.35, lob) * 0.75)
    col = mix(col, dark, ss(0.3, 0.75, lob))
    # the dark band along the rear margin, round the hind corners
    rear_d = np.where(z < P['zc'], dist, 99.0)
    rb = ss(0.95 + 0.25 * (n1 - 0.5), 0.55, rear_d) * ss(P['zc'] + 0.2, P['zc'] - 1.2, z)
    col = mix(col, (0.30, 0.15, 0.07), ss(0.0, 0.5, rb) * 0.7)
    col = mix(col, (0.13, 0.07, 0.045), ss(0.4, 0.9, rb))
    # mottling in the pale centre behind the lobes
    col = col * (0.92 + 0.14 * n2)[..., None]
    col = mix(col, (0.62, 0.38, 0.18), (n3 > 0.62) * inner * (1 - lob) * 0.35)
    # a fine darker rim
    col = mix(col, (0.62, 0.38, 0.18), np.exp(-(dist / 0.07) ** 2) * 0.6)
    pits = ss(0.66, 0.74, n3) * 0.5 + ss(0.55, 0.8, fbm(x * 30, z * 30, 43)) * 0.5
    h = (0.015 * ss(0.0, 1.2, dist) - 0.012 * pits + 0.01 * (n1 - 0.5) + 0.02 * np.exp(-((dist - 0.12) / 0.08) ** 2)
         - 0.012 * np.exp(-(x / 0.2) ** 2) * ss(-7.5, -5.5, z) * ss(-2.5, -4.0, z))
    rough = 0.34 + 0.04 * (n2 - 0.5) + 0.04 * (1 - inner)
    return col, h, rough


# ---------------------------------------------------------------- head and eyes

def paint_head(U, V):
    th = U * 2 * math.pi                     # 0 back, π face, π/2 left side
    t = V
    face = np.cos(th - math.pi)              # 1 on the face
    n1 = fbm(U * 18, V * 10, 51)
    n2 = fbm(U * 70, V * 40, 53)
    dark = (0.07, 0.04, 0.03)
    red = (0.36, 0.14, 0.06)
    clyp = (0.58, 0.31, 0.13)
    lab = (0.68, 0.42, 0.2)
    col = mix(dark, red, ss(0.42, 0.7, t) * ss(-0.2, 0.5, face))
    col = mix(col, clyp, ss(0.72, 0.78, t) * ss(0.2, 0.6, face))
    col = mix(col, lab, ss(0.88, 0.93, t) * ss(0.0, 0.5, face))
    # a dark band between the eyes, the face lighter beneath it
    col = mix(col, (0.08, 0.04, 0.03), ss(0.18, 0.3, t) * ss(0.45, 0.25, t) * ss(0.4, 0.8, face) * 0.7)
    # fenestrae (the ocellar spots) beside the antennal sockets
    for sgn in (1, -1):
        d = np.hypot((th - (math.pi - sgn * 0.5)) * 2.0, (t - 0.25) * 5.4)
        col = mix(col, (0.7, 0.55, 0.36), ss(0.22, 0.12, d) * 0.8)
    col = col * (0.92 + 0.14 * n1)[..., None]
    # frontoclypeal suture and the epicranial suture (Y on the vertex)
    suture = np.exp(-((t - 0.74) / 0.008) ** 2) * ss(0.0, 0.5, face)
    ep = np.exp(-((th - math.pi) / 0.03) ** 2) * ss(0.25, 0.1, t)
    pits = ss(0.6, 0.8, n2)
    h = -0.02 * suture - 0.015 * ep - 0.006 * pits + 0.008 * (n1 - 0.5)
    rough = 0.36 + 0.06 * (n1 - 0.5) + 0.06 * ss(0.85, 0.95, t)
    return col, h, rough


def paint_eye(U, V, size_mm):
    w_mm, h_mm = size_mm
    x = U * w_mm
    y = V * h_mm
    # hexagonal facets ~ 40 µm
    p = 0.042
    q = p * math.sqrt(3) / 2
    row = np.round(y / q)
    xs = x + (row % 2) * p / 2
    fx = xs - np.round(xs / p) * p
    fy = y - row * q
    d = np.hypot(fx, fy) / (p / 2)
    dome = np.clip(1 - d * d, 0, 1)
    n1 = fbm(U * 6, V * 6, 61)
    col = full(U.shape, (0.075, 0.045, 0.032))
    col = col * (0.85 + 0.3 * n1)[..., None] * (0.92 + 0.08 * dome)[..., None]
    h = 0.004 * dome
    rough = np.full(U.shape, 0.24, np.float32)
    return col, h, rough


# ---------------------------------------------------------------- thorax, abdomen, appendages

def paint_thorax(U, V):
    n1 = fbm(U * 10, V * 10, 71)
    col = full(U.shape, (0.27, 0.12, 0.065)) * (0.9 + 0.2 * n1)[..., None]
    ventral = np.cos((U - 0.5) * 2 * math.pi)
    col = mix(col, (0.62, 0.36, 0.17), ss(0.3, 0.8, ventral) * 0.6)
    h = 0.01 * (n1 - 0.5) - 0.02 * np.exp(-((V * 3 % 1 - 0.5) / 0.03) ** 2) * ss(0.2, 0.7, ventral)
    rough = 0.45 + 0.05 * (n1 - 0.5)
    return col, h, rough


def paint_abdomen(U, V):
    """the abdomen's tube: the sternites underneath, the pleural membranes with the spiracles along the sides"""
    import roach_body as RB
    z_front, z_tip = A.ABDOMEN[0][0], A.ABDOMEN[-1][0]
    z = z_front - V * (z_front - z_tip)
    edges = np.array([z_front + 0.4] + A.STERNITES + [z_tip + 0.9])
    # the way round (0 the top, 0.5 the keel); position inside the segment (0 front, 1 rear edge), bent forward at
    # the sides as the plates are
    W = RB.abdomen_unwarp(U)
    th = math.pi / 2 + W * 2 * math.pi
    side = np.abs(np.cos(th))
    zz = z - 0.55 * side ** 2 * np.where(np.sin(th) < 0, 1.0, 0.6)
    k = np.clip(np.searchsorted(-edges, -zz) - 1, 0, len(edges) - 2)
    za, zb = edges[k], edges[k + 1]
    s = np.clip((za - zz) / (za - zb), 0, 1)
    ventral = ss(0.0, 0.6, -np.sin(th))
    n1 = fbm(W * 20, V * 12, 81)
    n2 = fbm(W * 90, V * 50, 83)
    plate = mix((0.36, 0.14, 0.07), (0.55, 0.23, 0.1), ss(0.05, 0.3, s))
    plate = mix(plate, (0.74, 0.45, 0.22), ss(0.8, 0.97, s) * 0.8)
    col = mix((0.3, 0.13, 0.07), plate, 0.35 + 0.65 * ventral)
    # the pleural membrane between the tergites' margins and the sternites': pale, in lengthwise folds
    pleura = ss(-0.22, 0.0, np.sin(th)) * ss(0.62, 0.3, np.sin(th))
    folds = np.sin(W * 2 * math.pi * 46 + 3.0 * fbm(W * 8, V * 30, 87))
    col = mix(col, mix((0.62, 0.42, 0.24), (0.76, 0.58, 0.36), 0.5 + 0.5 * folds), pleura * 0.85)
    col = col * (0.9 + 0.2 * n1)[..., None]
    # spiracles on the sides: a dark slit in a brown ring, one to a segment
    spir = np.zeros(U.shape)
    ring = np.zeros(U.shape)
    for sgn in (1, -1):
        uu = 0.5 + sgn * 0.265
        d = np.hypot((W - uu) * 55, (s - 0.35) * 5.5)
        spir = np.maximum(spir, ss(0.5, 0.3, d) * (k < len(edges) - 2))
        ring = np.maximum(ring, ss(1.0, 0.75, d) * (k < len(edges) - 2))
    col = mix(col, (0.4, 0.2, 0.1), ring * 0.8)
    col = mix(col, (0.06, 0.03, 0.025), spir)
    h = (0.03 * ss(0.0, 0.9, s) - 0.025 * ss(0.06, 0.0, s) + 0.004 * (n2 - 0.5) + 0.006 * np.sin(s * 40) * (s < 0.2)
         + 0.012 * folds * pleura + 0.015 * ring - 0.03 * spir)
    rough = 0.38 + 0.12 * ss(0.12, 0.0, s) + 0.04 * (n1 - 0.5) + 0.14 * pleura
    return col, h, rough


def _back_surface(x, z, u, s, mm, me, seed):
    """what all the plates of the back share: the cuticle's grain, the sockets of fine setae, the setae lying
    backwards along the hind margins and the sides, the raised rim of the lateral margin and the groove inside it"""
    import roach_dorsum as RD
    hw = RD.half(z)
    n1 = fbm(x * 1.6, z * 1.6, seed)
    n2 = fbm(x * 9.0, z * 9.0, seed + 2)
    pits = ss(0.7, 0.8, fbm(x * 15.0, z * 15.0, seed + 4))
    hair = ss(0.62, 0.76, fbm(x * 24.0, z * 3.4, seed + 6)) * np.clip(ss(0.9, 0.2, me) + ss(0.8, 0.95, u), 0, 1)
    edge = (1 - u) * hw                                  # mm inside the lateral margin
    rim = np.exp(-(edge / 0.11) ** 2)
    groove = np.exp(-((edge - 0.42) / 0.1) ** 2)
    striae = np.sin(z * 2 * math.pi / 0.085 + 5.0 * n1)   # the cuticle's fine cross ridges
    bead = np.exp(-((me - 0.13) / 0.11) ** 2)            # the hind margin's thickened edge
    wrinkle = np.sin(mm * 2 * math.pi / 0.12 + 2.0 * n2) * ss(0.45, 0.1, mm)   # the membrane it comes out of
    h = (0.02 * ss(0.0, 0.6, mm) + 0.028 * bead + 0.006 * wrinkle + 0.0022 * striae + 0.005 * (n1 - 0.5) + 0.003 * (n2 - 0.5)
         - 0.008 * pits + 0.006 * hair + 0.022 * rim - 0.016 * groove - 0.005 * np.exp(-(x / 0.12) ** 2))
    return n1, n2, pits, hair, rim, groove, bead, h


def paint_tergites(U, V):
    """
    The abdomen's back: tergites 1–9 and the supra-anal plate, a flat projection (roach_dorsum TERG_BOX). Each
    plate comes out pale from under the one before it (the membrane between them shows as a pale band), is
    chestnut over its middle with the pits where muscles hold on, and ends in a dark hind margin with a thin clear
    edge; darker towards the sides and along the heart's line down the middle.
    """
    import roach_dorsum as RD
    x0, x1, z0, z1 = RD.TERG_BOX
    x = x0 + U * (x1 - x0)
    z = z0 + V * (z1 - z0)
    k, s, mm, me, u = RD.plate_of(x, z)
    n1, n2, pits, hair, rim, groove, bead, h = _back_surface(x, z, u, s, mm, me, 131)
    last = k == RD.N_PLATES - 1
    col = mix((0.38, 0.155, 0.07), (0.5, 0.215, 0.095), n1)
    col = mix(col, (0.56, 0.3, 0.135), ss(0.42, 0.05, mm) * 0.45)
    col = mix(col, (0.8, 0.62, 0.4), ss(0.1, 0.0, mm) * 0.6)
    col = mix(col, (0.26, 0.11, 0.06), 0.3 * np.exp(-(x / 0.45) ** 2))
    col = mix(col, (0.24, 0.1, 0.05), ss(0.78, 1.0, u) * 0.5)
    col = mix(col, (0.2, 0.085, 0.045), ss(0.6, 0.15, me) * 0.7)
    col = mix(col, (0.5, 0.27, 0.12), ss(0.06, 0.0, me) * 0.6)
    # where the muscles hold on: two pairs of small pits in a row across each tergite
    scars = np.zeros(x.shape)
    hw = RD.half(z)
    for uc in (0.2, 0.52):
        d = np.hypot((u - uc) * hw / 0.17, (s - 0.42) * 8.0)
        scars = np.maximum(scars, ss(1.0, 0.4, d))
    scars = scars * (k >= 2) * (k <= 8)
    col = mix(col, (0.27, 0.11, 0.06), scars * 0.6)
    # the supra-anal plate: thin and clear, amber towards its lobes
    col = mix(col, (0.74, 0.5, 0.24), last * ss(0.2, 0.85, s) * 0.85)
    col = mix(col, (0.3, 0.14, 0.07), pits * 0.3)
    col = mix(col, (0.8, 0.6, 0.36), hair * 0.2)
    col = col * (0.9 + 0.2 * n2)[..., None]
    h = h - 0.014 * scars
    rough = 0.27 + 0.24 * ss(0.4, 0.05, mm) + 0.06 * pits + 0.05 * hair + 0.04 * (n2 - 0.5) + 0.05 * last
    return col, h, rough


def paint_nota(U, V):
    """
    The mesonotum and the metanotum (roach_dorsum NOTA_BOX): paler and duller than the abdomen's plates, each with
    its median line, the two domed lobes of the scutum, the V of the furrow that sets the scutellum off behind
    them, darker where the wings' muscles sit, pale membrane at the sides where the wings are hinged.
    """
    import roach_dorsum as RD
    x0, x1, z0, z1 = RD.NOTA_BOX
    x = x0 + U * (x1 - x0)
    z = z0 + V * (z1 - z0)
    k, s, mm, me, u = RD.plate_of(x, z)
    n1, n2, pits, hair, rim, groove, bead, h = _back_surface(x, z, u, s, mm, me, 141)
    hw = RD.half(z)
    # the V: from the middle of the plate back and out to its hind corners
    v_at = 0.5 + 0.42 * u
    vee = np.exp(-(((s - v_at) * 3.6) / 0.11) ** 2) * ss(0.02, 0.1, u) * ss(1.0, 0.85, u)
    scutellum = ss(v_at - 0.02, v_at + 0.06, s)
    lobe = np.exp(-(((u - 0.45) / 0.3) ** 2 + ((s - 0.3) / 0.28) ** 2))
    median = np.exp(-(x / 0.09) ** 2)
    col = mix((0.5, 0.29, 0.13), (0.62, 0.4, 0.19), n1)
    col = mix(col, (0.34, 0.15, 0.07), lobe * 0.75)
    col = mix(col, (0.42, 0.19, 0.085), scutellum * 0.6)
    col = mix(col, (0.74, 0.54, 0.3), ss(0.5, 0.05, mm) * 0.6)
    col = mix(col, (0.2, 0.09, 0.05), vee * 0.7)
    col = mix(col, (0.74, 0.56, 0.32), median * 0.5 * (1 - scutellum))
    col = mix(col, (0.17, 0.075, 0.045), ss(0.55, 0.15, me) * 0.85)
    # the sides: pale membrane with the small dark plates of the wing's base
    memb = ss(0.74, 0.92, u)
    plates = ss(0.42, 0.66, fbm(x * 1.5, z * 1.5, 149))
    col = mix(col, mix((0.7, 0.52, 0.31), (0.34, 0.155, 0.075), plates), memb * 0.8)
    col = mix(col, (0.8, 0.6, 0.36), hair * 0.25)
    col = col * (0.9 + 0.2 * n2)[..., None] * (1 - 0.25 * pits)[..., None]
    h = h + 0.03 * lobe - 0.024 * vee + 0.014 * scutellum - 0.01 * median + 0.012 * memb * (plates - 0.5)
    rough = 0.36 + 0.14 * ss(0.4, 0.05, mm) + 0.1 * memb - 0.06 * lobe + 0.05 * pits + 0.04 * (n2 - 0.5)
    return col, h, rough


def paint_root(U, V):
    """a mound a wing is hinged on (U round it, V from its foot to its top): dark plates in pale, wrinkled membrane"""
    n1 = fbm(U * 14, V * 6, 151)
    n2 = fbm(U * 40, V * 18, 153)
    plates = ss(0.4, 0.62, fbm(U * 5, V * 2.5, 151)) * ss(0.4, 0.7, V)
    col = mix((0.68, 0.5, 0.3), (0.32, 0.145, 0.07), np.clip(plates + ss(0.8, 0.95, V), 0, 1))
    col = col * (0.9 + 0.2 * n2)[..., None]
    wr = np.sin(V * 2 * math.pi * 9 + 4 * n1)
    h = 0.03 * plates + 0.008 * wr * (1 - plates) + 0.004 * (n2 - 0.5)
    rough = 0.5 - 0.16 * plates + 0.04 * (n2 - 0.5)
    return col, h, rough


def paint_seta(U, V):
    """a bristle: dark at its socket, golden towards its tip"""
    n1 = fbm(U * 5, V * 14, 161)
    col = mix((0.32, 0.15, 0.07), (0.74, 0.52, 0.27), ss(0.05, 0.8, V)) * (0.92 + 0.16 * n1)[..., None]
    return col, 0.002 * (n1 - 0.5), np.full(U.shape, 0.36, np.float32)


def _annuli(s):
    """count of antennal annuli along the flagellum at arc length s (mm)"""
    a = A.ANTENNA
    base = a['scape'][0] + a['pedicel'][0]
    sp = np.maximum(s - base, 0.0)
    l0, l1 = 0.22, 0.5
    L = a['length'] - base
    k = (l1 - l0) / L
    return np.log1p(k * sp / l0) / k


def paint_antenna(U, V):
    a = A.ANTENNA
    s = V * a['length']
    base = a['scape'][0] + a['pedicel'][0]
    n = _annuli(s)
    f = n - np.floor(n)
    joint = np.exp(-(np.minimum(f, 1 - f) / 0.06) ** 2) * (s > base)
    n1 = fbm(U * 4, V * 300, 91)
    col = mix((0.55, 0.27, 0.12), (0.36, 0.15, 0.07), ss(0.8, base + 0.2, s))
    col = mix(col, (0.28, 0.12, 0.06), ss(5.0, 46.0, s) * 0.5)
    col = col * (1 - 0.35 * joint)[..., None] * (0.92 + 0.14 * n1)[..., None]
    # scape / pedicel joint
    jb = np.exp(-((s - a['scape'][0]) / 0.05) ** 2) + np.exp(-((s - base) / 0.04) ** 2)
    col = col * (1 - 0.4 * jb)[..., None]
    h = 0.006 * np.sin(np.pi * f) * (s > base) - 0.01 * jb + 0.002 * (n1 - 0.5)
    rough = 0.42 + 0.05 * joint
    return col, h, rough


def _segments_paint(U, V, bounds, base_col, joint_col, seed, hairs=0.0):
    k = np.clip(np.searchsorted(bounds, V) - 1, 0, len(bounds) - 2)
    a, b = bounds[k], bounds[k + 1]
    s = (V - a) / np.maximum(b - a, 1e-6)
    joint = np.exp(-(np.minimum(s, 1 - s) / 0.08) ** 2)
    n1 = fbm(U * 6, V * 80, seed)
    col = mix(base_col, joint_col, joint * 0.7) * (0.9 + 0.2 * n1)[..., None]
    streak = fbm(U * 60, V * 6, seed + 3)
    h = 0.012 * np.sin(np.pi * s) - 0.006 * joint + hairs * 0.004 * ss(0.6, 0.8, streak)
    rough = 0.42 + 0.06 * joint
    return col, h, rough


def paint_palp(U, V, lengths):
    c = np.concatenate([[0.0], np.cumsum(lengths)]) / sum(lengths)
    col, h, r = _segments_paint(U, V, c, (0.62, 0.34, 0.16), (0.32, 0.15, 0.07), 101)
    col = mix(col, (0.8, 0.62, 0.4), ss(0.9, 1.0, V) * 0.6)
    return col, h, r


def paint_cercus(U, V):
    import roach_body as RB
    j = RB.cercus_joints(1)
    d = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in zip(j[:-1], j[1:])])])
    col, h, r = _segments_paint(U, V, d / d[-1], (0.58, 0.29, 0.13), (0.3, 0.14, 0.07), 111, hairs=1.0)
    # the sockets of its bristles: dark pits in pale rings, a whorl to each segment
    pits = ss(0.66, 0.76, fbm(U * 9, V * 60, 113))
    col = col * (1 - 0.3 * pits)[..., None]
    return col, h - 0.006 * pits, r + 0.06 * pits


def paint_mouth(U, V):
    part = np.clip((U * 4).astype(int), 0, 3)
    n1 = fbm(U * 30, V * 30, 121)
    cols = np.array([(0.66, 0.4, 0.2), (0.14, 0.06, 0.035), (0.5, 0.24, 0.1), (0.56, 0.31, 0.15)], np.float32)
    col = cols[part] * (0.9 + 0.2 * n1)[..., None]
    # the mandibles' cutting edges near black
    col = np.where(((part == 1) & (V > 0.62))[..., None], col * 0.4, col)
    h = 0.006 * (n1 - 0.5)
    rough = np.where(part == 1, 0.3, 0.42) + 0.0 * n1
    return col, h, rough


# ---------------------------------------------------------------- legs

LEG_COL = {
    'coxa': ((0.82, 0.64, 0.42), (0.6, 0.36, 0.17)),
    'femur': ((0.78, 0.5, 0.24), (0.5, 0.22, 0.09)),
    'tibia': ((0.58, 0.24, 0.1), (0.4, 0.15, 0.06)),
    'tarsus1': ((0.62, 0.3, 0.12), (0.38, 0.16, 0.07)),
    'tarsus2': ((0.6, 0.29, 0.12), (0.36, 0.15, 0.07)),
}


LEG_PHYS = {}


def paint_leg(U, V, k, seg):
    base, end = LEG_COL[seg]
    seed = 200 + 10 * k + list(LEG_COL).index(seg)
    n1 = fbm(U * 8, V * 30, seed)
    circ, length = LEG_PHYS[k][seg]
    n2 = fbm(U * circ * 9, V * length * 9, seed + 3)
    col = mix(base, end, ss(0.8, 1.0, V) if seg in ('femur', 'coxa') else ss(0.0, 1.0, V) * 0.5)
    if seg == 'femur':
        # a darker stripe along the dorsal edge (−Z side: θ = 3π/2)
        th = (U * 2 * math.pi + math.pi / 12) % (2 * math.pi)
        col = mix(col, (0.62, 0.32, 0.13), np.exp(-((th - 1.5 * math.pi) / 0.5) ** 2) * 0.5)
    if seg == 'tarsus2':
        lens = A.LEGS[k]['tarsi'][1:]
        c = np.concatenate([[0.0], np.cumsum(lens)]) / sum(lens)
        kk = np.clip(np.searchsorted(c, V) - 1, 0, len(c) - 2)
        s = (V - c[kk]) / (c[kk + 1] - c[kk])
        col = mix(col, end, ss(0.75, 1.0, s) * 0.6)
    col = col * (0.9 + 0.18 * n1)[..., None]
    # setal sockets: small dark pits
    pits = ss(0.68, 0.78, n2)
    col = col * (1 - 0.25 * pits)[..., None]
    carina = np.abs(np.sin(U * 2 * math.pi * 4))
    # fine setae lying along the segment (short pale streaks, raised), thickest on the tibia and the tarsus
    hair = ss(0.6, 0.75, fbm(U * circ * 16, V * length * 2.6, seed + 5)) * ss(0.35, 0.6, fbm(U * circ * 5, V * length * 5, seed + 7))
    hair = hair * {'coxa': 0.5, 'femur': 0.6}.get(seg, 1.0)
    col = mix(col, (0.86, 0.66, 0.4), hair * 0.3)
    h = (0.006 * carina ** 4 - 0.008 * pits + 0.004 * (n1 - 0.5) - 0.02 * (ss(0.04, 0.0, V) + ss(0.96, 1.0, V))
         + 0.007 * hair)
    rough = 0.4 + 0.06 * (n1 - 0.5) + 0.05 * pits + 0.05 * hair
    return col, h, rough


def paint_spine(U, V):
    n1 = fbm(U * 6, V * 20, 301)
    col = mix((0.3, 0.13, 0.06), (0.07, 0.035, 0.025), ss(0.0, 0.55, V)) * (0.9 + 0.2 * n1)[..., None]
    h = 0.002 * (n1 - 0.5)
    return col, h, np.full(U.shape, 0.34, np.float32)


def paint_claw(U, V):
    col = mix((0.3, 0.13, 0.06), (0.07, 0.035, 0.025), ss(0.0, 0.8, V))
    return col, np.zeros(U.shape, np.float32), np.full(U.shape, 0.3, np.float32)


def paint_pad(U, V):
    n1 = fbm(U * 10, V * 10, 311)
    col = full(U.shape, (0.86, 0.74, 0.55)) * (0.92 + 0.12 * n1)[..., None]
    return col, 0.004 * (n1 - 0.5), np.full(U.shape, 0.55, np.float32)


# ---------------------------------------------------------------- atlases

class Atlas:
    def __init__(self, name, size):
        self.name = name
        self.N = size
        self.rgb = np.zeros((size, size, 3), np.float32)
        self.rgb[:] = (0.4, 0.18, 0.09)
        self.nrm = np.zeros((size, size, 3), np.float32)
        self.nrm[:] = (0.5, 0.5, 1.0)
        self.rough = np.full((size, size), 0.45, np.float32)

    def region(self, rect, painter, phys, pad=6):
        """paint `rect` with painter(U, V) → (rgb, height mm, rough); phys = the part's size (mm) over u and v"""
        N = self.N
        u0, v0, u1, v1 = rect
        x0, x1 = max(0, int(math.floor(u0 * N)) - pad), min(N, int(math.ceil(u1 * N)) + pad)
        y0, y1 = max(0, int(math.floor(v0 * N)) - pad), min(N, int(math.ceil(v1 * N)) + pad)
        us = ((np.arange(x0, x1) + 0.5) / N - u0) / (u1 - u0)
        vs = ((np.arange(y0, y1) + 0.5) / N - v0) / (v1 - v0)
        U, V = np.meshgrid(np.clip(us, 0, 1), np.clip(vs, 0, 1))
        rgb, h, rough = painter(U.astype(np.float64), V.astype(np.float64))
        h = np.broadcast_to(np.asarray(h, np.float64), U.shape)
        rough = np.broadcast_to(np.asarray(rough, np.float32), U.shape)
        du = phys[0] * (1.0 / N) / (u1 - u0)        # mm per texel along u
        dv = phys[1] * (1.0 / N) / (v1 - v0)
        gx = np.gradient(h, axis=1) / du
        gy = np.gradient(h, axis=0) / dv
        n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        self.rgb[y0:y1, x0:x1] = np.clip(rgb, 0, 1)
        self.nrm[y0:y1, x0:x1] = n * 0.5 + 0.5
        self.rough[y0:y1, x0:x1] = np.clip(rough, 0.05, 1)

    def images(self, out_dir, mr_size=None):
        os.makedirs(out_dir, exist_ok=True)
        N = self.N

        def save(name, arr, colour):
            h, w = arr.shape[:2]
            rgba = np.ones((h, w, 4), np.float32)
            rgba[..., :3] = arr
            img = bpy.data.images.new(name, w, h, alpha=False)
            if not colour:
                img.colorspace_settings.name = 'Non-Color'
            img.pixels.foreach_set(rgba.ravel())
            img.filepath_raw = os.path.join(out_dir, name + '.png')
            img.file_format = 'PNG'
            img.save()
            return img

        col = save(self.name + '_col', self.rgb, True)
        nrm = save(self.name + '_nrm', self.nrm, False)
        mr = np.ones((N, N, 3), np.float32)
        mr[..., 1] = self.rough
        if mr_size and mr_size < N:
            f = N // mr_size
            mr = mr.reshape(mr_size, f, mr_size, f, 3).mean(axis=(1, 3))
        rough = save(self.name + '_mr', mr, False)
        return col, nrm, rough


def material(name, col, nrm, mr):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = col
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    t2 = nt.nodes.new('ShaderNodeTexImage')
    t2.image = mr
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(t2.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    t3 = nt.nodes.new('ShaderNodeTexImage')
    t3.image = nrm
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 1.0
    nt.links.new(t3.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    p.inputs['Metallic'].default_value = 0.0
    p.inputs['Specular IOR Level'].default_value = 0.5
    m.use_backface_culling = True
    return m


def build_materials(out_dir, wings, sizes):
    """paint the three atlases → {material name: bpy material}; wings = (left WingShape, right WingShape)"""
    import roach_body as RB
    mats = {}
    # shell
    at = Atlas('roach_shell', sizes['shell'])
    for shape, key in zip(wings, ('tegmen_L', 'tegmen_R')):
        smin, smax, zmin, zmax = shape.uv_box
        at.region(LAYOUT[key], lambda U, V, s=shape: paint_tegmen(U, V, s), (smax - smin, zmax - zmin))
    P = A.PRONOTUM
    at.region(LAYOUT['pronotum'], paint_pronotum, (10.6, P['front'] - P['rear'] + 1.0))
    at.region(LAYOUT['head'], paint_head, (15.0, A.HEAD['length']))
    mats['roach_shell'] = material('roach_shell', *at.images(out_dir, sizes.get('mr')))
    # body
    at = Atlas('roach_body', sizes['body'])
    z_front, z_tip = A.ABDOMEN[0][0], A.ABDOMEN[-1][0]
    import roach_dorsum as RD
    at.region(LAYOUT['abdomen'], paint_abdomen, (34.0 * (1 - 2 * RB.ABD_HIDDEN) / (1 - 2 * RB.ABD_HIDDEN_U), z_front - z_tip))
    for key, painter, box in (('nota', paint_nota, RD.NOTA_BOX), ('tergites', paint_tergites, RD.TERG_BOX)):
        at.region(LAYOUT[key], painter, (box[1] - box[0], box[3] - box[2]))
    at.region(LAYOUT['root'], paint_root, (3.6, 0.9))
    at.region(LAYOUT['seta'], paint_seta, (0.3, 0.7))
    at.region(LAYOUT['thorax'], paint_thorax, (20.0, 11.0))
    at.region(LAYOUT['eye'], lambda U, V: paint_eye(U, V, (3.6, 2.8)), (3.6, 2.8))
    at.region(LAYOUT['cercus'], paint_cercus, (1.6, A.CERCUS['length']))
    at.region(LAYOUT['antenna'], paint_antenna, (1.2, A.ANTENNA['length']))
    at.region(LAYOUT['palp'], lambda U, V: paint_palp(U, V, A.MAX_PALP), (1.1, sum(A.MAX_PALP)))
    at.region(LAYOUT['lpalp'], lambda U, V: paint_palp(U, V, A.LAB_PALP), (0.8, sum(A.LAB_PALP)))
    at.region(LAYOUT['mouth'], paint_mouth, (6.0, 2.0))
    at.region(LAYOUT['hindwing'], paint_hindwing, (A.hind_across() * A.HIND['unfold'], A.HIND['length']))
    mats['roach_body'] = material('roach_body', *at.images(out_dir, sizes.get('mr')))
    # legs
    at = Atlas('roach_legs', sizes['legs'])
    for k in (1, 2, 3):
        p = A.LEGS[k]
        lens = {'coxa': p['coxa'] + 0.75, 'femur': p['femur'] + 0.75, 'tibia': p['tibia'] + 0.4,
                'tarsus1': p['tarsi'][0], 'tarsus2': sum(p['tarsi'][1:])}
        circ = {'coxa': 2 * (p['coxa_w'][0] + p['coxa_t']) * 2, 'femur': math.pi * sum(p['femur_r']),
                'tibia': math.pi * sum(p['tibia_r']), 'tarsus1': 2 * math.pi * p['tarsus_r'],
                'tarsus2': 2 * math.pi * p['tarsus_r']}
        for seg in LEG_V:
            LEG_PHYS.setdefault(k, {})[seg] = (circ[seg], lens[seg])
            at.region(leg_rect(k, seg), lambda U, V, k=k, seg=seg: paint_leg(U, V, k, seg), (circ[seg], lens[seg]))
    at.region(LAYOUT['spine'], paint_spine, (0.5, 1.2))
    at.region(LAYOUT['claw'], paint_claw, (0.4, 0.6))
    at.region(LAYOUT['pad'], paint_pad, (1.0, 1.0))
    mats['roach_legs'] = material('roach_legs', *at.images(out_dir, sizes.get('mr')))
    return mats
