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
    shell.split([(-0.62, -0.2), (0.62, -0.2), (0.62, 0.212), (0.0, 0.215), (-0.62, 0.212)],
                'z', 1, lambda f, c, n: c[2] > 1.72 and n[2] > 0.2 and n[1] < 0.7, mat='trim')
    shell.split([(-0.70, -0.2), (0.70, -0.2), (0.70, 0.335), (0.45, 0.350), (0.0, 0.355), (-0.45, 0.350), (-0.70, 0.335)], 'z', -1, lambda f, c, n: c[2] < -1.85 and n[2] < -0.2 and n[1] < 0.7, mat='trim')
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
    """the duct behind the central mouth: black walls, a dark ribbed back"""
    half = SH.INTAKE
    outline = [(x, y) for x, y in half] + [(-x, y) for x, y in reversed(half[1:-1])]
    rim = [(x, y, SH.front_face_z(x, y) + 0.004) for x, y in resample(outline, 0.03)]
    depth = 0.15
    zb = min(p[2] for p in rim) - depth
    cx = 0.0
    cy = np.mean([p[1] for p in rim])
    n = len(rim)
    for k in range(n):
        a, b = rim[k], rim[(k + 1) % n]
        q = [a, b, (b[0] * 0.97, b[1] + (cy - b[1]) * 0.15, zb), (a[0] * 0.97, a[1] + (cy - a[1]) * 0.15, zb)]
        mid = np.mean(q, axis=0)
        m.face(q, 'trim', out=(cx - mid[0], cy - mid[1], 0))
    back = [(p[0] * 0.97, p[1] + (cy - p[1]) * 0.15, zb) for p in rim]
    m.face(back, 'trim', smooth=False, out=(0, 0, 1))
    # a mesh-like back: thin dark horizontal ribs
    ys = [p[1] for p in back]
    for j in range(4):
        y = min(ys) + (max(ys) - min(ys)) * (j + 0.5) / 4
        box(m, (0.0, y, zb + 0.02), (0.78, 0.006, 0.03), 'gloss_black')


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
WING_SPAN = 0.585          # half span of the blade (it ends in the pods' tops)
POD_X = (0.43, 0.555)      # the pods' centre at the deck → at the top (swept outwards as they rise)


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
    # the pods: horizontal teardrop sections (round front, pointed back... reversed: long tapering nose running
    # forward down the deck, full rounded tail under the blade), lofted from the deck to a rounded top
    y_top = wing_y(WING_SPAN) + chord * math.tan(WING_AOA) + 0.030
    for s in (1, -1):
        secs = []
        levels = 9
        for i in range(levels + 1):
            t = i / levels
            cx = s * (POD_X[0] + (POD_X[1] - POD_X[0]) * t ** 0.8)
            z_back = -1.995 - 0.05 * t
            z_front = -1.70 + (-1.93 - -1.70) * t ** 0.7
            half = 0.060 - 0.022 * t
            if t > 0.75:            # round the top over
                k = (t - 0.75) / 0.25
                f = math.sqrt(max(0.0, 1 - k * k))
                half *= max(f, 0.08)
                zm = (z_front + z_back) / 2
                z_front = zm + (z_front - zm) * max(f, 0.08) ** 0.5
                z_back = zm + (z_back - zm) * max(f, 0.08) ** 0.5
            sec = []
            for j in range(14):
                a = 2 * math.pi * j / 14
                u = (1 - math.cos(a)) / 2                      # 0 at the front, 1 at the back
                w = math.sin(a) * half * (u ** 0.55) * (1.0 - 0.25 * u)
                z = z_front + (z_back - z_front) * u
                x = cx + w
                h = shell.hit((x, 3.0, z), (0, -1, 0))
                y0 = (h[0][1] - 0.008) if h is not None else 0.80
                sec.append((x, y0 + (y_top - y0) * t, z))
            secs.append(sec)
        loft(m, secs, 'paint', caps=True, smooth=True)


# ---------------------------------------------------------------- mirrors, wipers, handles


def mirrors(m, shell):
    """small aero mirrors: a teardrop head (round nose, tapering back to the glass) on a short curved stalk from the
    door's front top corner, all body colour"""
    for s in (1, -1):
        base = np.array(shell.hit((s * 2.0, 0.872, 0.31), (-s, 0, 0))[0])
        hc = np.array((s * 0.838, 0.912, 0.30))
        nu, nv = 16, 9
        rx, ry, rz = 0.086, 0.052, 0.056
        rings = []
        for j in range(1, nv):
            phi = math.pi * j / nv                     # 0 at the nose (+z), π at the back
            ring = []
            for i in range(nu):
                th = 2 * math.pi * i / nu
                # aero section: flatter top, fuller bottom, outer end rounder than the inner
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
        # stalk: a flattened arm curving up and out from the door to the head's inner underside
        tip = hc + (-s * rx * 0.55, -ry * 0.55, 0.0)
        ctrl = [base + (s * 0.004, 0, 0), base + (s * 0.03, 0.012, 0.008), tip + (-s * 0.012, -0.008, 0.004), tip]
        secs = []
        for k, p in enumerate(ctrl):
            w = 0.030 - 0.010 * k / 3
            h = 0.011
            secs.append([tuple(p + (0, -h, -w)), tuple(p + (0, -h, w)), tuple(p + (0, h, w)), tuple(p + (0, h, -w))])
        loft(m, secs, 'paint', caps=False)


def air_outlet(m, shell):
    """the outlet behind each front wheel: its vertical slot, dark"""
    for s in (1, -1):
        slot = smooth_outline([(0.795, 0.365), (0.765, 0.345), (0.735, 0.360), (0.722, 0.440), (0.730, 0.520),
                               (0.755, 0.545), (0.785, 0.530), (0.800, 0.450)], 4)
        patch(m, shell, slot, 'x', s, 'trim', lift=0.002, rings=3)


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
    m = Mesh('exhaust_tip')
    x, y = -0.465, 0.300
    z1 = SH.rear_face_z(x, y) - 0.025
    tube_z(m, (x, y), 0.050, z1 + 0.30, z1, 'chrome', n=20)
    counts['exhaust'] = m.tris()
    m.build(body, mats, weld=1e-6)


def front_lip(m, shell):
    """the Type RS's black lip spoiler: a blade standing 7 cm proud of the bumper's lower edge, arch to arch, its top
    sloping down to a sharp front edge"""
    y_bot, y_in, y_edge = 0.168, 0.212, 0.184
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
    plate(m, (0.0, 0.476), True)
    plate(m, (0.0, 0.421), False)
    wing(m, shell)
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
