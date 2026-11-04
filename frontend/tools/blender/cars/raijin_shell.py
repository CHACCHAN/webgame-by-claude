"""
The Impreza WRX STI (GDB-C/D, 2002.11-2005.6 "tear-drop") body shell: a loft over longitudinal feature lines.

Each line (sill, max width, shoulder, beltline, window top, roof rail, centre line ...) is a curve of z: x(z), y(z) in
the middle of the car (ZR..ZF); at the ends it wraps round the corner to the centre line (a superellipse quadrant in
plan, reaching `reach` at x = 0 with height `end_y`). A station of the loft is a section through all lines at one z
(or one corner angle), interpolated between them (monotone cubic along the chord), so window edges, pillars and the
beltline fall on grid lines and the materials follow them exactly.

Figures (mm): length 4415, width 1740, height 1425, wheelbase 2525, track 1485 / 1480 (Subaru catalogue figures for
the GDB-C STI; US 2004 STI: 173.8 × 68.5 × 56.3 in, wheelbase 99.4 in). The profile, the glasshouse and the lamps are
measured on Commons side / 3/4 photos (see the agent notes), scaled from the wheelbase.
"""
import math

import raijin_kit as K

WB = 2.525
FRONT_AXLE = WB / 2
REAR_AXLE = -WB / 2
Z_FRONT = 2.158          # front overhang 0.895
Z_REAR = -2.257          # rear overhang 0.995
ZF = 1.70                # corners start here
ZR = -1.80
HALF_W = 0.87

# line names, bottom to top
NAMES = ['floor_c', 'floor_e', 'sill_b', 'sill', 'low', 'maxw', 'shoulder', 'belt', 'gl_b', 'gl_t', 'sash', 'rail',
         'frit', 'centre']
IDX = {n: i for i, n in enumerate(NAMES)}
# pieces between consecutive lines
SEGS = [3, 1, 2, 3, 3, 4, 3, 1, 4, 1, 2, 1, 6]

# glasshouse z marks
COWL = 0.88              # windscreen's lower edge (centre)
HOOD_REAR = 0.95         # hood's rear edge
HEADER = -0.12           # windscreen top
REAR_HEADER = -0.93      # rear window top
BACKLIGHT_LOW = -1.47    # rear window's lower edge
A_BASE = 0.86            # side glass front tip (A pillar foot)
C_BASE = -1.10           # side glass rear tip
B_PILLAR = (-0.37, -0.27)


def centre_y(z):
    return _CENTRE(z)


_CENTRE = K.Pchip([(-1.75, 1.052), (-1.6, 1.058), (-1.47, 1.068), (-1.35, 1.140), (-1.15, 1.287), (-0.93, 1.400),
                   (-0.8, 1.417), (-0.6, 1.425), (-0.4, 1.422), (-0.12, 1.395), (0.0, 1.355), (0.3, 1.23), (0.6, 1.095),
                   (COWL, 0.975), (HOOD_REAR, 0.925), (1.10, 0.895), (1.40, 0.840), (1.70, 0.785)])
_CROWN = K.Pchip([(-1.75, 0.018), (-1.5, 0.02), (-0.93, 0.04), (COWL, 0.025), (HOOD_REAR, 0.04), (1.7, 0.04)])
# the roof rail's height in the glasshouse (windscreen and rear window side edges)
_RAIL_Y = K.Pchip([(BACKLIGHT_LOW, 1.045), (-1.2, 1.222), (REAR_HEADER, 1.372), (-0.5, 1.390), (HEADER, 1.356),
                   (0.4, 1.150), (COWL, 0.950), (1.0, 0.905)])


def deck_y(x, z):
    """the top surface (hood, roof, screens, trunk) at a column x: lower towards the sides"""
    return centre_y(z) - _CROWN(z) * min(1.0, (x / 0.68)) ** 2


def _deck_w(z):
    """1 on the hood / trunk, 0 in the glasshouse"""
    return max(K.smoothstep(A_BASE - 0.02, HOOD_REAR + 0.06, z), K.smoothstep(BACKLIGHT_LOW + 0.04, BACKLIGHT_LOW - 0.12, z))


def _plateau(z, c, inner, outer):
    return 1.0 - K.smoothstep(inner, outer, abs(z - c))


def flare(z):
    """the STI's wide wings: extra half-width over the wheels, flat on top with short steep ends (crisp blisters)"""
    return 0.040 * _plateau(z, FRONT_AXLE, 0.30, 0.52) + 0.044 * _plateau(z, REAR_AXLE, 0.30, 0.50)


def skirt(z):
    """the side sill extension between the wheel arches"""
    return 0.020 * (1.0 - K.smoothstep(0.66, 0.84, abs(z + 0.02)))


# middle-part tables: name → (x pts, y pts); corners: name → front (reach_z, end_y, n), rear (reach_z, end_y, n)
def _tables():
    T = {}
    T['floor_c'] = ([(0, 0.0)], [(-1.72, 0.27), (-1.35, 0.205), (1.3, 0.200), (1.7, 0.215)])
    T['floor_e'] = ([(0, 0.70)], [(-1.72, 0.26), (-1.35, 0.195), (1.3, 0.192), (1.7, 0.195)])
    T['sill_b'] = ([(-1.72, 0.80), (0, 0.80), (1.7, 0.80)], [(-1.72, 0.26), (-1.3, 0.215), (0, 0.205), (1.3, 0.20), (1.7, 0.195)])
    T['sill'] = ([(-1.72, 0.825), (0, 0.818), (1.7, 0.825)], [(-1.72, 0.33), (-1.3, 0.29), (0, 0.27), (1.3, 0.27), (1.7, 0.27)])
    T['low'] = ([(-1.72, 0.836), (0, 0.828), (1.7, 0.836)], [(-1.72, 0.45), (0, 0.42), (1.7, 0.42)])
    T['maxw'] = ([(-1.72, 0.838), (0, 0.836), (1.7, 0.836)], [(-1.72, 0.62), (0, 0.60), (1.7, 0.585)])
    T['shoulder'] = ([(-1.72, 0.800), (-1.26, 0.812), (0, 0.818), (1.26, 0.810), (1.7, 0.790)],
                     [(-1.72, 0.895), (-1.26, 0.905), (-0.9, 0.885), (0, 0.862), (0.9, 0.85), (1.26, 0.825), (1.7, 0.772)])
    # beltline: on the hood it is the hood / wing shut line, on the trunk the trunk / quarter shut line
    T['belt'] = ([(-1.72, 0.672), (-1.55, 0.675), (-1.30, 0.725), (-1.10, 0.772), (-0.9, 0.780), (-0.3, 0.786),
                  (0.3, 0.776), (A_BASE, 0.748), (HOOD_REAR + 0.02, 0.672), (1.3, 0.665), (1.7, 0.660)],
                 [(-1.72, 1.036), (-1.5, 1.032), (-1.3, 1.020), (-1.10, 1.008), (-0.9, 0.997), (-0.3, 0.977), (0.3, 0.957),
                  (A_BASE, 0.928), (1.0, 0.884), (1.3, 0.842), (1.7, 0.770)])
    # side window top: the A pillar, the roof's side, the C pillar
    T['sash'] = ([(-1.72, 0.50), (-1.60, 0.52), (BACKLIGHT_LOW, 0.62), (-1.30, 0.68), (C_BASE, 0.752), (-0.95, 0.700), (-0.7, 0.648),
                  (-0.4, 0.640), (HEADER, 0.643), (0.4, 0.690), (A_BASE, 0.728), (HOOD_REAR + 0.03, 0.50), (1.7, 0.50)],
                 [(-1.55, 1.040), (-1.30, 1.030), (C_BASE, 1.024), (-0.95, 1.170), (-0.75, 1.302), (-0.5, 1.338),
                  (-0.3, 1.342), (HEADER, 1.332), (0.0, 1.302), (0.4, 1.098), (A_BASE, 0.948), (1.0, 0.900)])
    # roof rail = the windscreen's and the rear window's side edge
    T['rail'] = ([(-1.72, 0.33), (-1.58, 0.33), (BACKLIGHT_LOW, 0.555), (-1.2, 0.574), (REAR_HEADER, 0.585),
                  (-0.5, 0.586), (HEADER, 0.590), (0.4, 0.655), (COWL, 0.700), (HOOD_REAR + 0.04, 0.33), (1.7, 0.33)], None)
    T['centre'] = ([(0, 0.0)], None)
    return T


FRONT = {'floor_c': (1.95, 0.235, 2.0), 'floor_e': (2.04, 0.180, 2.6), 'sill_b': (2.11, 0.172, 2.8),
         'sill': (2.150, 0.265, 3.0), 'low': (2.158, 0.42, 3.0), 'maxw': (2.125, 0.555, 2.8),
         'shoulder': (2.070, 0.690, 2.3), 'belt': (2.055, 0.705, 2.2), 'gl_b': (2.050, 0.710, 2.1),
         'gl_t': (2.045, 0.716, 2.0), 'sash': (2.040, 0.720, 2.0), 'rail': (2.030, 0.728, 2.0),
         'frit': (2.025, 0.732, 2.0), 'centre': (2.020, 0.738, 2.0)}
REAR = {'floor_c': (-2.06, 0.33, 2.0), 'floor_e': (-2.16, 0.335, 3.0), 'sill_b': (-2.215, 0.345, 3.4),
        'sill': (-2.240, 0.40, 3.6), 'low': (-2.257, 0.50, 3.6), 'maxw': (-2.245, 0.630, 3.6),
        'shoulder': (-2.125, 0.820, 3.4), 'belt': (-2.082, 0.978, 3.6), 'gl_b': (-2.074, 0.995, 3.6),
        'gl_t': (-2.070, 1.003, 3.6), 'sash': (-2.067, 1.008, 3.6), 'rail': (-2.064, 1.013, 3.6),
        'frit': (-2.062, 1.017, 3.6), 'centre': (-2.060, 1.021, 2.0)}


class Lines:
    def __init__(self):
        T = _tables()
        self.fx, self.fy = {}, {}
        for n, (xs, ys) in T.items():
            self.fx[n] = K.Pchip(xs if len(xs) > 1 else [(-9, xs[0][1]), (9, xs[0][1])])
            if ys is not None:
                self.fy[n] = K.Pchip(ys if len(ys) > 1 else [(-9, ys[0][1]), (9, ys[0][1])])

    def mid(self, n, z):
        """(x, y) of line n at z in the middle part"""
        w = _deck_w(z)
        if n in ('floor_c', 'floor_e', 'sill_b', 'sill', 'low', 'maxw', 'shoulder', 'belt'):
            x = self.fx[n](z)
            if n in ('low', 'maxw', 'shoulder'):
                x += flare(z)
            elif n == 'sill':
                x += 0.7 * flare(z) + skirt(z)
            elif n == 'sill_b':
                x += 0.5 * flare(z) + 0.8 * skirt(z)
            return x, self.fy[n](z)
        if n == 'centre':
            return 0.0, centre_y(z)
        if n == 'rail':
            x = self.fx['rail'](z)
            return x, K.lerp(_RAIL_Y(z), deck_y(x, z), w)
        if n == 'frit':
            xr = self.fx['rail'](z)
            x = xr - K.lerp(0.065, 0.06, w)
            yr = _RAIL_Y(z)
            gh = yr + (centre_y(z) - yr) * (1 - (x / xr) ** 2)
            return x, K.lerp(gh, deck_y(x, z), w)
        if n == 'sash':
            x = self.fx['sash'](z)
            y = self.fy['sash'](z)
            return x, K.lerp(y, deck_y(x, z), w)
        bx, by = self.mid('belt', z)
        sx, sy = self.mid('sash', z)
        glass = 1.0 - w
        if n == 'gl_b':
            x = K.lerp(bx, sx, 0.04) - 0.013 * glass
            return x, K.lerp(by + 0.012, deck_y(x, z), w)
        if n == 'gl_t':
            x = K.lerp(sx, bx, 0.085) - 0.012 * glass
            return x, K.lerp(sy - 0.026, deck_y(x, z), w)
        raise KeyError(n)

    def corner(self, n, phi, front):
        """line n on the front/rear corner, phi 0 (start) .. 1 (centre line)"""
        z0 = ZF if front else ZR
        x0, y0 = self.mid(n, z0)
        reach, end_y, ex = (FRONT if front else REAR)[n]
        th = phi * math.pi / 2
        c, s = math.cos(th), math.sin(th)
        x = x0 * (c ** (2 / ex) if c > 0 else 0.0)
        dz = (reach - z0) * (s ** (2 / ex))
        t = abs(dz / (reach - z0))
        y = y0 + (end_y - y0) * K.smoothstep(0.0, 1.0, t) if n not in ('floor_c', 'floor_e') else y0 + (end_y - y0) * t
        return x, y, z0 + dz


def stations():
    """[(kind, value)]: ('rear', phi) .. ('mid', z) .. ('front', phi), rear to front"""
    marks = [COWL, HOOD_REAR, HEADER, REAR_HEADER, BACKLIGHT_LOW, A_BASE, C_BASE, *B_PILLAR, 0.92,
             FRONT_AXLE - 0.40, FRONT_AXLE + 0.40, REAR_AXLE - 0.40, REAR_AXLE + 0.40]
    zs = []
    n = int((ZF - ZR) / 0.042)
    for i in range(n + 1):
        z = ZR + (ZF - ZR) * i / n
        if all(abs(z - m) > 0.014 for m in marks):
            zs.append(z)
    zs = sorted(set(zs + [m for m in marks if ZR < m < ZF]))
    out = [('rear', 1 - i / 14) for i in range(14)]
    out += [('mid', z) for z in zs]
    out += [('front', i / 14) for i in range(1, 15)]
    return out


def section(L, st):
    kind, v = st
    pts3 = []
    for n in NAMES:
        if kind == 'mid':
            x, y = L.mid(n, v)
            pts3.append((x, y, v))
        else:
            pts3.append(L.corner(n, v, kind == 'front'))
    # interpolate in the (x, y) plane; z interpolated along the same parameter
    xy = [(p[0], p[1]) for p in pts3]
    xz = [(p[0], p[2]) for p in pts3]
    sec = K.resample_polyline(xy, SEGS)
    # z per point: piecewise linear by segment index (the corner stations are not planar)
    zs = []
    for i, cnt in enumerate(SEGS):
        za, zb = pts3[i][2], pts3[i + 1][2]
        for k in range(cnt):
            zs.append(za + (zb - za) * k / cnt)
    zs.append(pts3[-1][2])
    # fair the hood and the trunk lid: across the deck (belt → centre) y is a parabola in x through both lines
    wd = _deck_w(v) if kind == 'mid' else 1.0
    if wd > 0:
        ib = sum(SEGS[:IDX['belt']])
        xb, yb = sec[ib]
        yc = sec[-1][1]
        if xb > 1e-4:
            sec = sec[:ib + 1] + [(x, K.lerp(y, yc - (yc - yb) * (x / xb) ** 2, wd)) for x, y in sec[ib + 1:]]
    return [(x, y, z) for (x, y), z in zip(sec, zs)]


def band_of_column():
    out = []
    for i, cnt in enumerate(SEGS):
        out += [i] * cnt
    return out


def material(band, z, kind):
    """which material a face of the shell gets"""
    n0 = NAMES[band]
    if n0 in ('floor_c', 'floor_e'):
        return 'under'
    if kind != 'mid':
        return 'trim' if n0 == 'sill_b' else 'paint'     # black lower lip (front) / diffuser lip (rear)
    glass_side = C_BASE - 0.02 < z < A_BASE + 0.02
    if HOOD_REAR - 0.005 > z > COWL - 0.03 and band >= IDX['belt']:
        return 'cowl'
    if n0 == 'belt' or n0 == 'gl_t':
        return 'trim' if glass_side else 'paint'
    if n0 == 'gl_b':
        if B_PILLAR[0] < z < B_PILLAR[1]:
            return 'trim'
        return 'glass' if glass_side else 'paint'
    if n0 == 'rail':
        return 'trim' if (HEADER < z < COWL or BACKLIGHT_LOW < z < REAR_HEADER) else 'paint'
    if n0 == 'frit':
        return 'glass' if (HEADER < z < COWL or BACKLIGHT_LOW < z < REAR_HEADER) else 'paint'
    return 'paint'


def build(part):
    """the closed shell into `part` (both halves)"""
    L = Lines()
    sts = stations()
    rows = [section(L, st) for st in sts]
    bands = band_of_column()
    meta = [(st[0], st[1] if st[0] == 'mid' else (ZF if st[0] == 'front' else ZR)) for st in sts]

    def mats(i, j):
        kind, z = meta[j]
        kind2, z2 = meta[j + 1]
        zc = (z + z2) / 2
        k = kind if kind == kind2 else 'corner'
        return material(bands[i], zc, 'mid' if k == 'mid' else k)

    left = rows
    right = [[(-x, y, z) for x, y, z in row] for row in rows]
    part.grid(left, None, mats=mats)
    part.grid(right, None, mats=mats, flip=True)
    return L, rows
