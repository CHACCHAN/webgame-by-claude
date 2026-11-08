"""
The FD3S's smaller parts: the intake's duct with its body-colour struts and fog lamps, number plates, the late
Type RS rear wing, door mirrors, wipers and washer nozzles, door handles, shut lines, a basic cabin, the exhaust.

cut(shell): material splits on the shell (black front lip, rear valance, dark underside) — before the shell is
built.
"""
import math

import numpy as np

import shiden_body as BODY
import shiden_shape as SH
from shiden_surf import Mesh, lay_on, ribbon, smooth_outline, resample, patch


def cut(shell):
    # black lip under the front bumper, black valance under the rear one
    shell.split([(-0.62, -0.2), (0.62, -0.2), (0.62, 0.200), (0.0, 0.203), (-0.62, 0.200)],
                'z', 1, lambda f, c, n: c[2] > 1.72 and n[2] > 0.2 and n[1] < 0.7, mat='trim')
    # (photo s14: body colour down to y 0.26 behind the plate, the black rising to 0.32 under the reflectors)
    shell.split([(-0.70, -0.2), (0.70, -0.2), (0.70, 0.325), (0.55, 0.300), (0.40, 0.275), (0.0, 0.262), (-0.40, 0.275),
                 (-0.55, 0.300), (-0.70, 0.325)], 'z', -1, lambda f, c, n: c[2] < -1.85 and n[2] < -0.2 and n[1] < 0.7,
                mat='trim')
    # the air outlets behind the front wheels: the shell is opened, a recess is built into it
    for s in (1, -1):
        shell.split(outlet_outline(0.0), 'x', s, lambda f, c, n, s=s: c[0] * s > 0.7 and n[0] * s > 0.5 and
                    0.5 < c[2] < 0.85 and 0.25 < c[1] < 0.53, delete=True)
    # the underside
    idx = shell.mesh.slot('trim')
    for f in shell.bm.faces:
        c = f.calc_center_median()
        if c.z < 0.24 and f.normal.z < -0.85:
            f.material_index = idx


# ---------------------------------------------------------------- helpers


def box(m, c, size, mat, smooth=False):
    """axis-aligned box (game frame) centred at c"""
    cx, cy, cz = c
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    P = lambda i, j, k: (cx + i * hx, cy + j * hy, cz + k * hz)
    for ax in range(3):
        for sgn in (-1, 1):
            q = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                v = [0, 0, 0]
                v[ax] = sgn
                v[(ax + 1) % 3] = a
                v[(ax + 2) % 3] = b
                q.append(P(*v))
            out = [0, 0, 0]
            out[ax] = sgn
            m.face(q, mat, smooth=smooth, out=tuple(out))


def loft(m, sections, mat, closed=True, caps=True, smooth=True):
    """quads between consecutive closed sections (lists of 3-D points of equal length); outward = away from the
    section's centroid"""
    S = [np.asarray(s, float) for s in sections]
    n = len(S[0])
    for a, b in zip(S[:-1], S[1:]):
        ca, cb = a.mean(axis=0), b.mean(axis=0)
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            q = [a[k], a[k2], b[k2], b[k]]
            mid = np.mean(q, axis=0)
            out = mid - (ca + cb) / 2
            m.face([tuple(p) for p in q], mat, smooth=smooth, out=tuple(out))
    if caps:
        for s, other in ((S[0], S[1]), (S[-1], S[-2])):
            c = s.mean(axis=0)
            out = c - other.mean(axis=0)
            for k in range(n):
                m.face([tuple(c), tuple(s[k]), tuple(s[(k + 1) % n])], mat, smooth=False, out=tuple(out))


def tube_z(m, c, r, z0, z1, mat, n=16, inner=None, mat_in='trim'):
    """a tube along z (exhaust tip): outer wall, rolled lip, inner wall, a dark plug inside"""
    cx, cy = c
    ring = lambda rr, z: [(cx + rr * math.cos(2 * math.pi * i / n), cy + rr * math.sin(2 * math.pi * i / n), z)
                          for i in range(n)]
    ri = inner or r * 0.86
    secs = [ring(r, z0), ring(r, z1), ring(r * 0.95, z1 - 0.004), ring(ri, z1 - 0.004), ring(ri, z1 - 0.05)]
    for j in range(len(secs) - 1):
        a, b = secs[j], secs[j + 1]
        for k in range(n):
            k2 = (k + 1) % n
            mid = np.mean([a[k], b[k2]], axis=0)
            rad = (mid[0] - cx, mid[1] - cy, 0.0)
            out = rad if j < 1 else ((0, 0, -1) if j == 1 else (-rad[0], -rad[1], 0))
            m.face([a[k], a[k2], b[k2], b[k]], mat if j < 3 else mat_in, out=out)
    m.face(secs[-1], mat_in, smooth=False, out=(0, 0, -1))


# ---------------------------------------------------------------- the intake


def intake(m, shell):
    """the duct behind the central mouth: the bumper rolls in round its edge (body colour: the bright lip along the
    bottom in photos r01 / s08), black walls run back to a ribbed core, a black bar crosses it low down"""
    half = SH.INTAKE
    outline = [(x, y) for x, y in half] + [(-x, y) for x, y in reversed(half[1:-1])]
    P = resample(outline, 0.025)
    n = len(P)
    c2 = P.mean(axis=0)
    inward = []
    for k in range(n):
        t = P[(k + 1) % n] - P[k - 1]
        d = np.array((-t[1], t[0])) / max(np.linalg.norm(t), 1e-9)
        inward.append(d if np.dot(d, c2 - P[k]) > 0 else -d)
    zf = [SH.front_face_z(x, y) + 0.004 for x, y in P]
    ring = lambda a, b: [(P[k][0] + inward[k][0] * a, P[k][1] + inward[k][1] * a, zf[k] - b) for k in range(n)]
    rings = [ring(0.0, 0.0), ring(0.003, 0.006), ring(0.005, 0.016)]
    depth = 0.20
    zb = min(zf) - depth
    cy = float(c2[1])
    back = [(p[0] * 0.97, p[1] - (cy - p[1]) * 0.10, zb) for p in rings[-1]]
    for ra, rb, mat in ((rings[0], rings[1], 'paint'), (rings[1], rings[2], 'paint'), (rings[2], back, 'trim')):
        for k in range(n):
            k2 = (k + 1) % n
            q = [ra[k], ra[k2], rb[k2], rb[k]]
            mid = np.mean(q, axis=0)
            m.face(q, mat, out=(-0.2 * mid[0], cy - mid[1], 0.3 if mat == 'paint' else 0.0))
    m.face(back, 'trim', smooth=False, out=(0, 0, 1))
    # a mesh-like back: thin dark horizontal ribs
    ys = [p[1] for p in back]
    for j in range(4):
        y = min(ys) + (max(ys) - min(ys)) * (j + 0.5) / 4
        box(m, (0.0, y, zb + 0.02), (0.62, 0.006, 0.03), 'gloss_black')
    # the bar across the mouth (photo r01: 4 cm under the plate's foot), set back from the face
    box(m, (0.0, 0.262, SH.front_face_z(0.0, 0.262) - 0.06), (0.64, 0.014, 0.02), 'brake')


# ---------------------------------------------------------------- plates


def plate(m, centre, front):
    """a 330 × 165 mm plate (texture across it) on a black backing, following the bumper face"""
    W, H = 0.33, 0.165
    cx, cy = centre
    nu, nv = 4, 2
    sgn = 1 if front else -1
    zf = (lambda x, y: SH.front_face_z(x, y) + 0.012) if front else (lambda x, y: SH.rear_face_z(x, y) - 0.010)
    grid = np.zeros((nu + 1, nv + 1, 3))
    uv = np.zeros((nu + 1, nv + 1, 2))
    for i in range(nu + 1):
        for j in range(nv + 1):
            x = cx - W / 2 + W * i / nu
            y = cy - H / 2 + H * j / nv
            grid[i, j] = (x, y, zf(x, y))
            uv[i, j] = ((i / nu) if front else (1 - i / nu), j / nv)
    if front:
        grid = grid[::-1]
        uv = uv[::-1]
    m.grid(grid, 'plate', smooth=False, uv=uv)
    # backing / edge: a frame strip round it, stepping back to the bumper
    ring = [grid[i, 0] for i in range(nu + 1)] + [grid[nu, j] for j in range(1, nv + 1)] + \
           [grid[i, nv] for i in range(nu - 1, -1, -1)] + [grid[0, j] for j in range(nv - 1, 0, -1)]
    n = len(ring)
    c = np.mean(ring, axis=0)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        a2 = a - np.array((0, 0, sgn * 0.016))
        b2 = b - np.array((0, 0, sgn * 0.016))
        mid = (a + b) / 2
        m.face([tuple(a), tuple(b), tuple(b2), tuple(a2)], 'trim', smooth=False, out=tuple(mid - c))


# ---------------------------------------------------------------- the rear wing


WING_LE, WING_Y, WING_CHORD, WING_AOA = -1.85, 0.925, 0.20, math.radians(6)
WING_SPAN = 0.580          # half span of the blade (its ends sit on the stays' tops)
# the stays (photo s14 close up, s13): seen from behind each is an L — the blade's end turns down into a broad upright
# at the outside, which bends round into a thick foot running inwards along the deck's crest to x 0.36; both are
# long fore and aft (rounded slabs), the foot reaching further forward than the blade
STAY_PATH = [(0.584, None), (0.597, 0.075), (0.585, 0.042), (0.540, 0.031), (0.450, 0.029), (0.360, 0.024)]
#             (|x|, centre height over the deck; None = under the blade)
STAY_T = (0.032, 0.030, 0.022)               # half thickness: upright, foot, tip
STAY_Z = ((-2.000, -1.850), (-1.955, -1.770))  # fore-aft extent: under the blade .. along the foot
STAY_DECK_Z = -1.94                          # behind this the tail rolls down: the foot stands on the deck's crest


def wing_y(x):
    """the blade's leading-edge height across the span: flat, a faint arch in the middle (bundle: the blade's top
    rear edge at y 0.95–0.96, z −2.05, ending at x ±0.6 in the pods)"""
    return WING_Y + 0.008 * (1 - min(1.0, abs(x) / WING_SPAN) ** 2)


def wing(m, shell):
    """late Type RS wing: a low inverted-airfoil blade between two swept pods that rise from the deck at the ends of
    the lamp band (photos r03 / r11 / r19)"""
    chord, thick = WING_CHORD, 0.024
    nsec = 14
    upper = []
    lower = []
    for i in range(nsec):
        u = (1 - math.cos(math.pi * i / nsec)) / 2
        upper.append((u, thick * 1.76 * (math.sqrt(u) - u)))
        v = 1 - u
        lower.append((v, -thick * 1.2 * (math.sqrt(v) - v)))
    loop = upper + lower

    def section(x):
        return [(x, wing_y(x) + t + u * chord * math.tan(WING_AOA), WING_LE - u * chord) for u, t in loop]

    xs = list(np.linspace(-WING_SPAN, WING_SPAN, 15))
    S = [np.asarray(section(x)) for x in xs]
    n = len(loop)
    for a, b in zip(S[:-1], S[1:]):
        for k in range(n):
            k2 = (k + 1) % n
            q = [a[k], a[k2], b[k2], b[k]]
            out = np.mean(q, axis=0) - (a.mean(axis=0) + b.mean(axis=0)) / 2
            out[0] = 0
            m.face([tuple(p) for p in q], 'paint', out=tuple(out))
    for sec in (S[0], S[-1]):
        m.face([tuple(p) for p in (sec if sec is S[-1] else sec[::-1])], 'paint', smooth=False,
               out=(float(np.sign(sec[0][0])), 0, 0))
    # the arms' tops follow the blade's mean line, 4 mm under it
    y_blade = lambda z: wing_y(WING_SPAN) + min(1.0, max(0.0, (WING_LE - z) / chord)) * chord * math.tan(WING_AOA) - 0.004
    nu = 16

    def deck(x, z):
        h = shell.hit((x, 3.0, max(z, STAY_DECK_Z)), (0, -1, 0))
        return h[0][1] if h is not None else 0.82

    for s in (1, -1):
        zmid = sum(STAY_Z[0]) / 2
        P = [np.array((s * x, y_blade(zmid) if hgt is None else deck(s * x, zmid) + hgt)) for x, hgt in STAY_PATH]
        P = [P[0] + (P[0] - P[1]) * 0.3] + P + [P[-1] + (P[-1] - P[-2]) * 0.3]
        path = []
        for i in range(1, len(P) - 2):
            for t in np.linspace(0, 1, 4, endpoint=False):
                p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
                path.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                                   (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        path.append(P[-2])
        n = len(path)
        secs = []
        for k, c in enumerate(path):
            u = k / (n - 1)
            tg = path[min(k + 1, n - 1)] - path[max(k - 1, 0)]
            tg = tg / np.linalg.norm(tg)
            across = np.array((-tg[1], tg[0]))                     # in the (x, y) plane
            g = min(1.0, u / 0.45)
            g = g * g * (3 - 2 * g)                                # upright → foot
            za = STAY_Z[0][0] + (STAY_Z[1][0] - STAY_Z[0][0]) * g
            zb = STAY_Z[0][1] + (STAY_Z[1][1] - STAY_Z[0][1]) * g
            T = STAY_T[0] + (STAY_T[1] - STAY_T[0]) * g
            if u > 0.8:                                            # the foot thins to a rounded tip
                e = (u - 0.8) / 0.2
                T += (STAY_T[2] - STAY_T[1]) * e
                f = math.sqrt(max(0.15, 1 - e ** 4))
                za, zb = (za + zb) / 2 - (zb - za) / 2 * f, (za + zb) / 2 + (zb - za) / 2 * f
            zc, L = (za + zb) / 2, (zb - za) / 2
            sec = []
            for j in range(nu):
                th = 2 * math.pi * j / nu
                ca, sa = math.cos(th), math.sin(th)
                a_ = T * math.copysign(abs(sa) ** 0.7, sa)
                z = zc + L * math.copysign(abs(ca) ** 0.7, ca)
                tilt = (y_blade(z) - y_blade(zmid)) * (1 - g)          # the top follows the blade's incidence
                sec.append((c[0] + across[0] * a_, c[1] + across[1] * a_ + tilt, z))
            secs.append(sec)
        loft(m, secs, 'paint', caps=True, smooth=True)


# ---------------------------------------------------------------- mirrors, wipers, handles


# door mirror head in the final (photo-fitted) shape: centre |x|, y, z and radii; measured on head-on, side and 3/4
# photos (fitdata/shiden: the head's outline drawn from the solved cameras). The FFD moves the body afterwards, so the
# head is placed where the deformation brings it onto these numbers.
MIRROR = {'x': 0.915, 'y': 0.86, 'z': 0.12, 'rx': 0.097, 'ry': 0.075, 'rz': 0.08}


def mirrors(m, shell):
    """aero mirrors: an egg-shaped head (long round nose, short back holding the glass) on a slim neck that rises
    from the door's front top corner to the head's inner underside, all body colour"""
    import shiden_ffd as FFD
    M = MIRROR
    rx, ry, rz = M['rx'], M['ry'], M['rz']
    for s in (1, -1):
        tgt = np.array((s * M['x'], M['y'], M['z']))
        hc = tgt.copy()
        for _ in range(3):
            hc = tgt - (FFD.deform_game(hc[None])[0] - hc)
        nu, nv = 16, 9
        rings = []
        for j in range(1, nv):
            phi = math.pi * j / nv                     # 0 at the nose (+z), π at the back
            ring = []
            for i in range(nu):
                th = 2 * math.pi * i / nu
                x = rx * math.sin(phi) * math.cos(th)
                y = ry * math.sin(phi) * math.sin(th) * (0.85 if math.sin(th) > 0 else 1.0)
                z = rz * math.cos(phi) * (1.25 if phi < math.pi / 2 else 0.35)
                ring.append(tuple(hc + (s * x, y, z)))
            rings.append(ring)
        nose = tuple(hc + (0, 0, rz * 1.25))
        for j in range(len(rings) - 1):
            for i in range(nu):
                i2 = (i + 1) % nu
                q = [rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]]
                m.face(q, 'paint', out=tuple(np.mean(q, axis=0) - hc))
        for i in range(nu):
            m.face([nose, rings[0][i], rings[0][(i + 1) % nu]], 'paint', out=(0, 0, 1))
        last = rings[-1]
        glass = [tuple(hc + (np.array(p) - hc) * 0.9 + (0, 0, 0.004)) for p in last]
        for i in range(nu):
            i2 = (i + 1) % nu
            m.face([last[i], last[i2], glass[i2], glass[i]], 'paint', smooth=False, out=(0, 0, -1))
        m.face(glass, 'chrome', smooth=False, out=(0, 0, -1))
        # neck: from the door skin up and out into the head's inner underside, flared at the door
        top = hc + (-s * rx * 0.42, -ry * 0.55, 0.004)
        base = np.array(shell.hit((s * 2.0, hc[1] - ry - 0.05, hc[2] + 0.012), (-s, 0, 0))[0])
        mid = base + (s * 0.012, 0.03, 0.0)
        ctrl = [base - (s * 0.004, 0, 0), mid, top - (s * 0.006, 0.012, 0), top + (s * 0.004, 0.012, 0)]
        secs = []
        for k, p in enumerate(ctrl):
            a = ctrl[min(k + 1, 3)] - ctrl[max(k - 1, 0)]
            t = a / np.linalg.norm(a)
            wz = np.array((0.0, 0.0, 1.0))
            wb = np.cross(t, wz); wb /= np.linalg.norm(wb)
            w = (0.040, 0.030, 0.028, 0.030)[k]
            h = (0.022, 0.015, 0.014, 0.016)[k]
            secs.append([tuple(p - wz * w - wb * h), tuple(p + wz * w - wb * h), tuple(p + wz * w + wb * h),
                         tuple(p - wz * w + wb * h)])
        loft(m, secs, 'paint', caps=False)


# the air outlet behind each front wheel (photo s12, picked on the solved camera, (z, y)): a scoop pressed into the
# wing, a rounded parallelogram leaning back, with a dark slot in its upper front part
OUTLET = [(0.762, 0.489), (0.679, 0.495), (0.665, 0.488), (0.634, 0.417), (0.599, 0.346), (0.583, 0.294),
          (0.691, 0.285), (0.795, 0.306), (0.791, 0.399)]
OUTLET_SLOT = [(0.738, 0.472), (0.680, 0.479), (0.661, 0.438), (0.662, 0.369), (0.682, 0.333), (0.727, 0.349),
               (0.747, 0.397)]


def outlet_outline(grow):
    return [tuple(p) for p in _grow(smooth_outline(OUTLET, 4), grow)]


def _grow(poly, d):
    """offset a convex-ish closed 2-D outline outwards by d (inwards if negative), along the vertex normals"""
    P = np.asarray(poly, float)
    n = len(P)
    c = P.mean(axis=0)
    out = []
    for k in range(n):
        t = P[(k + 1) % n] - P[k - 1]
        nn = np.array((t[1], -t[0])) / max(np.linalg.norm(t), 1e-9)
        if np.dot(nn, P[k] - c) < 0:
            nn = -nn
        out.append(P[k] + nn * d)
    return np.array(out)


def _ray_poly(c, d, poly):
    """distance from c along the unit 2-D direction d to the outline (the farthest crossing)"""
    best = None
    n = len(poly)
    for k in range(n):
        a, b = np.asarray(poly[k]), np.asarray(poly[(k + 1) % n])
        e = b - a
        den = d[0] * (-e[1]) + d[1] * e[0]
        if abs(den) < 1e-12:
            continue
        w = a - c
        t = (w[0] * (-e[1]) + w[1] * e[0]) / den
        u = (d[0] * w[1] - d[1] * w[0]) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = t if best is None else max(best, t)
    return best


def air_outlet(m, shell):
    """the scoop: a dish from the wing's surface down into the slot (body colour, its edge crisp), the slot's black
    walls going on into the wing, and the side badge ahead of it"""
    outer = outlet_outline(0.003)
    slot = smooth_outline(OUTLET_SLOT, 4)
    cs = np.mean(np.asarray(slot), axis=0)
    N = 36
    D1, D2 = 0.030, 0.075
    ts = (0.0, 0.10, 0.25, 0.45, 0.70, 1.0)
    for s in (1, -1):
        def at(z, y, depth):
            h = shell.hit((s * 3.0, y, z), (-s, 0, 0))
            x = h[0][0] if h is not None else s * 0.86
            return (x - s * depth, y, z)
        rings = [[] for _ in ts]
        deep = []
        for k in range(N):
            ang = 2 * math.pi * k / N
            d = np.array((math.cos(ang), math.sin(ang)))
            ro, rs = _ray_poly(cs, d, outer), _ray_poly(cs, d, slot)
            for i, t in enumerate(ts):
                r = ro + (rs - ro) * t
                depth = -0.0006 if t == 0 else D1 * (1 - (1 - t) ** 2)
                z, y = cs + d * r
                rings[i].append(at(z, y, depth))
            z, y = cs + d * rs * 0.9
            deep.append(at(z, y, D2))
        for i in range(len(ts) - 1):
            for k in range(N):
                k2 = (k + 1) % N
                m.face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], 'paint', out=(s, 0, 0))
        last = rings[-1]
        for k in range(N):
            k2 = (k + 1) % N
            q = [last[k], last[k2], deep[k2], deep[k]]
            mid = np.mean(q, axis=0)
            m.face(q, 'trim', out=(0.0, cs[1] - mid[1], cs[0] - mid[2]))
        m.face(deep, 'trim', smooth=False, out=(s, 0, 0))
        # the badge on the wing ahead of the scoop (s12): a chrome-rimmed black shield, a small rotor in it
        shield = smooth_outline([(0.632, 0.601), (0.600, 0.604), (0.566, 0.600), (0.572, 0.576), (0.600, 0.548),
                                 (0.627, 0.576)], 4)
        patch(m, shell, shield, 'x', s, 'chrome', lift=0.0015, rings=2)
        patch(m, shell, [tuple(p) for p in _grow(shield, -0.0035)], 'x', s, 'gloss_black', lift=0.0025, rings=2)
        rotor = [(0.599 + 0.010 * math.cos(a + math.pi / 2), 0.582 + 0.010 * math.sin(a + math.pi / 2))
                 for a in (2 * math.pi * i / 3 for i in range(3))]
        rotor = smooth_outline(rotor, 4)
        patch(m, shell, rotor, 'x', s, 'chrome', lift=0.0035, rings=1)


def wipers(m, shell):
    """two arms parked along the bottom of the windscreen (towards the left side on this RHD car)"""
    for x0, x1, zoff in ((-0.42, 0.20, 0.0), (0.10, 0.62, 0.025)):
        pts = []
        for t in np.linspace(0, 1, 9):
            x = x0 + (x1 - x0) * t
            z = 0.52 - 0.153 * (x / 0.688) ** 2 - 0.05 - zoff - 0.02 * t
            h = shell.hit((x, 3.0, z), (0, -1, 0))
            pts.append(np.array(h[0]) + (0, 0.016, 0))
        for a, b in zip(pts[:-1], pts[1:]):
            d = b - a
            w = np.cross(d, (0, 1, 0))
            w = w / np.linalg.norm(w) * 0.007
            q = [a - w, b - w, b + w, a + w]
            m.face([tuple(p) for p in q], 'trim', smooth=False, out=(0, 1, 0))
            q2 = [a - w - (0, 0.012, 0), b - w - (0, 0.012, 0), b - w, a - w]
            m.face([tuple(p) for p in q2], 'trim', smooth=False, out=tuple(-w))
        # the pivot cap
        p = pts[0]
        box(m, (p[0], p[1] - 0.004, p[2] - 0.01), (0.03, 0.02, 0.03), 'trim')
    # washer nozzles on the bonnet's rear edge
    for s in (1, -1):
        h = shell.hit((s * 0.26, 3.0, 0.66), (0, -1, 0))
        box(m, (s * 0.26, h[0][1] + 0.004, 0.66), (0.018, 0.012, 0.026), 'trim')


def handles(m, shell):
    for s in (1, -1):
        pts = []
        for z, y in ((-0.56, 0.770), (-0.66, 0.775), (-0.66, 0.800), (-0.56, 0.795)):
            h = shell.hit((s * 2.0, y, z), (-s, 0, 0))
            pts.append(np.array(h[0]) + (s * 0.002, 0, 0))
        m.face([tuple(p) for p in pts], 'trim', smooth=False, out=(s, 0, 0))


# ---------------------------------------------------------------- shut lines


def shut_lines(m, shell):
    for s in (1, -1):
        door = [(0.37, 0.30), (0.375, 0.55), (0.38, 0.82), ]
        ribbon(m, shell, [(z, y) for z, y in door], 'x', s, 'trim', closed=False)
        ribbon(m, shell, [(0.37, 0.295), (-0.40, 0.29), (-0.73, 0.295)], 'x', s, 'trim', closed=False)
        ribbon(m, shell, [(-0.73, 0.295), (-0.78, 0.55), (-0.815, 0.80), (-0.83, 0.86)], 'x', s, 'trim',
               closed=False)
        # fuel lid (left rear wing only)
        if s > 0:
            circ = [(-1.574 + 0.056 * math.cos(2 * math.pi * i / 24), 0.606 + 0.056 * math.sin(2 * math.pi * i / 24))
                    for i in range(24)]
            ribbon(m, shell, circ, 'x', s, 'trim', closed=True, step=0.006)
        # bonnet edge along the wing crest, from the windscreen corner to the lid
        ribbon(m, shell, [(s * 0.690, 0.50), (s * 0.705, 0.90), (s * 0.712, 1.25), (s * 0.708, 1.49)], 'y', 1, 'trim',
               closed=False)
        # front bumper to wing, down the side in front of the arch
        ribbon(m, shell, [(1.82, 0.62), (1.70, 0.60), (1.60, 0.56)], 'x', s, 'trim', closed=False)
    # bonnet's front edge between the lids
    ribbon(m, shell, [(x, BODY.nose_edge_z(x) - 0.012) for x in np.linspace(-0.45, 0.45, 19)], 'y', 1, 'trim',
           closed=False)
    # the hatch round its glass, and the rear panel line under the wing
    ribbon(m, shell, BODY.hatch_outline(-0.035), 'y', 1, 'trim', closed=True, step=0.02)


# ---------------------------------------------------------------- the cabin


def cabin(m):
    """dash, seats, steering wheel (right-hand drive: the driver sits at −x), door cards, headliner, floor, the
    bulkhead behind the seats"""
    # dash: a wedge under the windscreen
    dash = [[(-0.70, 0.60, 0.45), (0.70, 0.60, 0.45), (0.70, 0.80, 0.42), (-0.70, 0.80, 0.42)],
            [(-0.70, 0.60, 0.10), (0.70, 0.60, 0.10), (0.70, 0.84, 0.14), (-0.70, 0.84, 0.14)]]
    loft(m, dash, 'interior', smooth=False)
    # instrument binnacle
    box(m, (-0.37, 0.85, 0.15), (0.30, 0.06, 0.12), 'interior')
    # steering wheel: a ring in a plane leaning back, centre (−0.37, 0.80, 0.02)
    c = np.array((-0.37, 0.79, 0.0))
    tilt = math.radians(25)
    n = 20
    R, r = 0.18, 0.016
    ex = np.array((1.0, 0, 0))
    ey = np.array((0, math.cos(tilt), math.sin(tilt)))
    en = np.cross(ex, ey)
    rings = []
    for i in range(n):
        a = 2 * math.pi * i / n
        cen = c + R * (math.cos(a) * ex + math.sin(a) * ey)
        rad = math.cos(a) * ex + math.sin(a) * ey
        rings.append([tuple(cen + r * (math.cos(b) * rad + math.sin(b) * en)) for b in
                      (2 * math.pi * k / 6 for k in range(6))])
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        cen = c + R * (math.cos(2 * math.pi * (i + 0.5) / n) * ex + math.sin(2 * math.pi * (i + 0.5) / n) * ey)
        for k in range(6):
            k2 = (k + 1) % 6
            q = [a[k], a[k2], b[k2], b[k]]
            mid = np.mean(q, axis=0)
            m.face(q, 'interior', out=tuple(mid - cen))
    box(m, tuple(c - en * 0.03), (0.09, 0.07, 0.06), 'interior')
    # column
    loft(m, [[tuple(c - en * 0.05 + d) for d in ((-0.025, -0.025, 0), (0.025, -0.025, 0), (0.025, 0.025, 0),
                                                   (-0.025, 0.025, 0))],
             [tuple(c - en * 0.30 + d) for d in ((-0.03, -0.03, 0), (0.03, -0.03, 0), (0.03, 0.03, 0),
                                                  (-0.03, 0.03, 0))]], 'interior', smooth=False)
    # seats: cushion + raked back with side bolsters
    for s in (1, -1):
        x = s * 0.37
        box(m, (x, 0.33, -0.48), (0.48, 0.12, 0.50), 'interior')
        back = [[(x - 0.24, 0.36, -0.76), (x + 0.24, 0.36, -0.76), (x + 0.24, 0.36, -0.86), (x - 0.24, 0.36, -0.86)],
                [(x - 0.22, 0.86, -0.90), (x + 0.22, 0.86, -0.90), (x + 0.22, 0.86, -0.98), (x - 0.22, 0.86, -0.98)]]
        loft(m, back, 'interior', smooth=False)
        box(m, (x, 0.92, -0.93), (0.24, 0.11, 0.08), 'interior')
        # door card
        q = [(s * 0.76, 0.32, 0.35), (s * 0.76, 0.32, -0.74), (s * 0.74, 0.84, -0.80), (s * 0.74, 0.84, 0.38)]
        m.face(q, 'interior', smooth=False, out=(-s, 0, 0))
    # tunnel and console
    box(m, (0.0, 0.36, -0.15), (0.24, 0.20, 0.95), 'interior')
    # floor, bulkhead and luggage deck behind the seats, headliner
    m.face([(-0.78, 0.24, 0.42), (0.78, 0.24, 0.42), (0.78, 0.24, -1.05), (-0.78, 0.24, -1.05)], 'interior',
           smooth=False, out=(0, 1, 0))
    m.face([(-0.76, 0.24, -1.05), (0.76, 0.24, -1.05), (0.70, 0.62, -1.08), (-0.70, 0.62, -1.08)], 'interior',
           smooth=False, out=(0, 0, 1))
    m.face([(-0.70, 0.62, -1.08), (0.70, 0.62, -1.08), (0.66, 0.66, -1.80), (-0.66, 0.66, -1.80)], 'interior',
           smooth=False, out=(0, 1, 0))
    m.face([(-0.55, 1.10, 0.02), (0.55, 1.10, 0.02), (0.55, 1.14, -0.80), (-0.55, 1.14, -0.80)], 'interior',
           smooth=False, out=(0, -1, 0))


# ---------------------------------------------------------------- exhaust


def exhaust(mats, body, counts):
    """twin round tips under the bumper's right-hand side (photo s14: 75 mm across, outboard under the reflector)"""
    m = Mesh('exhaust_tip')
    for x in (-0.478, -0.556):
        y = 0.290
        z1 = SH.rear_face_z(-0.517, y) - 0.025
        tube_z(m, (x, y), 0.037, z1 + 0.30, z1, 'chrome', n=16)
    counts['exhaust'] = m.tris()
    m.build(body, mats, weld=1e-6)


# ---------------------------------------------------------------- badges (own shapes; the only font is Noto Sans CJK)


FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


def lettering(m, shell, text, x0, x1, yc, h, lift=0.003):
    """chrome letters laid on the tail: the text's box stretched from x0 to x1 (reading as seen from behind), h tall"""
    import bpy
    font = bpy.data.fonts.load(FONT, check_existing=True)
    cu = bpy.data.curves.new('badge_text', 'FONT')
    cu.body = text
    cu.font = font
    cu.resolution_u = 3
    ob = bpy.data.objects.new('badge_text', cu)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    me.calc_loop_triangles()
    V = np.array([(v.co.x, v.co.y) for v in me.vertices])
    T = [tuple(t.vertices) for t in me.loop_triangles]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    g0, g1 = V.min(axis=0), V.max(axis=0)
    pts2 = [(x0 + (x1 - x0) * (gx - g0[0]) / (g1[0] - g0[0]), yc - h / 2 + h * (gy - g0[1]) / (g1[1] - g0[1]))
            for gx, gy in V]
    P = lay_on(shell, pts2, 'z', -1, lift)
    for a, b, c in T:
        if P[a] is None or P[b] is None or P[c] is None:
            continue
        m.face([tuple(P[a]), tuple(P[b]), tuple(P[c])], 'chrome', smooth=False, out=(0, 0, -1))


def emblem(m, shell, cx, cy, rx, ry, side):
    """the maker's badge as our own shape: a chrome oval ring, dark inside, a chrome wing (a broad V with an inner
    tulip) across it; side +1 on the nose, −1 on the tail"""
    ell = lambda a, b, n=28: [(cx + a * math.cos(2 * math.pi * i / n), cy + b * math.sin(2 * math.pi * i / n))
                              for i in range(n)]
    patch(m, shell, ell(rx, ry), 'z', side, 'chrome', lift=0.002, rings=2)
    patch(m, shell, ell(rx - 0.0045, ry - 0.0045), 'z', side, 'gloss_black', lift=0.003, rings=2)
    w = min(rx, ry) * 0.11
    for poly in ([(-0.84, 0.22), (-0.52, 0.06), (-0.20, -0.36), (0.0, -0.74), (0.20, -0.36), (0.52, 0.06),
                  (0.84, 0.22)],
                 [(-0.30, 0.46), (-0.12, -0.20), (0.0, -0.74), (0.12, -0.20), (0.30, 0.46)]):
        pts = [(cx + u * rx, cy + v * ry) for u, v in poly]
        ribbon(m, shell, pts, 'z', side, 'chrome', width=w, lift=0.004, closed=False, step=0.004)


def badges(m, shell):
    """front: the maker's badge on the nose over the plate (r01); tail (s14): the badge in the middle of the
    garnish, RX-7 on its left, mazda on its right, the hatch lock under the badge, the seam along the garnish's foot"""
    emblem(m, shell, 0.0, 0.546, 0.038, 0.022, 1)
    emblem(m, shell, 0.0, 0.721, 0.040, 0.030, -1)
    lettering(m, shell, 'RX-7', 0.352, 0.236, 0.701, 0.020)
    lettering(m, shell, 'mazda', -0.226, -0.350, 0.704, 0.022)
    lock = [(0.0 + 0.011 * math.cos(2 * math.pi * i / 16), 0.668 + 0.011 * math.sin(2 * math.pi * i / 16))
            for i in range(16)]
    patch(m, shell, lock, 'z', -1, 'chrome', lift=0.002, rings=1)
    patch(m, shell, [(-0.0015, 0.661), (0.0015, 0.661), (0.0015, 0.675), (-0.0015, 0.675)], 'z', -1, 'trim',
          lift=0.003, rings=1)
    seam = [(x, 0.676) for x in np.linspace(-0.455, 0.455, 31)]
    ribbon(m, shell, seam, 'z', -1, 'trim', width=0.0035, lift=0.0008, closed=False, step=0.02)


def front_lip(m, shell):
    """the Type RS's black lip spoiler: a blade standing 7 cm proud of the bumper's lower edge, arch to arch, its top
    sloping down to a sharp front edge"""
    y_bot, y_in, y_edge = 0.168, 0.200, 0.180
    inner, outer = [], []
    for a in np.linspace(-1.0, 1.0, 33):
        ang = a * 1.25
        d = np.array((math.sin(ang), 0.0, math.cos(ang)))
        o = np.array((0.0, 0.21, 1.30)) + d * 3.0
        h = shell.hit(tuple(o), tuple(-d))
        if h is None or h[0][2] < SH.ZF + 0.30:
            continue
        p = np.array(h[0])
        nrm = np.array((h[1][0], 0.0, h[1][2]))
        nrm /= max(np.linalg.norm(nrm), 1e-6)
        k = 1.0 - 0.45 * abs(a) ** 3          # shallower towards the arches
        inner.append(p - nrm * 0.012)
        outer.append(p + nrm * 0.07 * k)
    up = lambda p, y: (p[0], y, p[2])
    for a, b, c, d in zip(inner[:-1], inner[1:], outer[:-1], outer[1:]):
        m.face([up(a, y_in), up(b, y_in), up(d, y_edge), up(c, y_edge)], 'trim', smooth=False, out=(0, 1, 0))
        m.face([up(a, y_bot), up(b, y_bot), up(d, y_bot), up(c, y_bot)], 'trim', smooth=False, out=(0, -1, 0))
        mid = (c + d) / 2 - (a + b) / 2
        m.face([up(c, y_bot), up(d, y_bot), up(d, y_edge), up(c, y_edge)], 'trim', smooth=False, out=tuple(mid))
    for p, q in ((inner[0], outer[0]), (inner[-1], outer[-1])):
        m.face([up(p, y_bot), up(q, y_bot), up(q, y_edge), up(p, y_in)], 'trim', smooth=False,
               out=(-1 if p[0] < 0 else 1, 0, 0))


def build(body, shell, mats, counts):
    m = Mesh('details')
    front_lip(m, shell)
    intake(m, shell)
    plate(m, (0.0, 0.398), True)      # front: top 0.48 (photos r01, s08), its foot over the mouth
    plate(m, (0.0, 0.378), False)     # rear: s14
    wing(m, shell)
    badges(m, shell)
    mirrors(m, shell)
    air_outlet(m, shell)
    wipers(m, shell)
    handles(m, shell)
    shut_lines(m, shell)
    # muffler under the rear
    box(m, (-0.18, 0.27, -1.78), (0.62, 0.12, 0.30), 'trim')
    counts['details'] = m.tris()
    m.build(body, mats, weld=1e-6)
    c = Mesh('cabin')
    cabin(c)
    counts['cabin'] = c.tris()
    c.build(body, mats, weld=1e-6)
    exhaust(mats, body, counts)
