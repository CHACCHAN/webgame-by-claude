"""
The FD3S's lamps: the pop-up headlamp pods (modelled raised, hinged on empties popup_l / popup_r that fold them
flush by their custom property popupClosed), the bumper's combination lamps (clear position lamp + amber
indicator), fog lamps in the intake's side pockets, side markers and reflectors, the rear lamp band (smoked round
lamps either side of a black garnish) and the rear bumper's reflector / reverse lamps.

cut(shell): the openings these need in the shell (the lid wells) — before the shell is built.
build(...): the parts, after.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import shiden_shape as SH
from shiden_surf import B, G, Mesh, lay_on, patch, ribbon, smooth_outline, inside

# ---------------------------------------------------------------- pop-up pods

POD_ANGLE = 0.68          # rad: raised → closed rotation about the hinge (+x folds the front down)
HINGE_Z = 1.505
WELL_FLOOR = 0.47


def lid_outline(s=1, inset=0.0):
    """the lid seen from above (x, z) on side s: front edge along the bonnet's front crease, outer edge along the
    wing's crest, straight rear edge = hinge line"""
    ctrl = [(0.470, 1.812), (0.560, 1.808), (0.640, 1.778), (0.692, 1.725), (0.716, 1.650), (0.718, 1.570),
            (0.705, HINGE_Z + 0.004), (0.600, HINGE_Z), (0.495, HINGE_Z + 0.004), (0.458, 1.560), (0.446, 1.660),
            (0.450, 1.760)]
    pts = smooth_outline(ctrl, 4)
    if inset:
        c = np.mean(np.array(pts), axis=0)
        pts = [tuple(np.array(p) - (np.array(p) - c) / np.linalg.norm(np.array(p) - c) * inset) for p in pts]
    return [(s * x, z) for x, z in pts]


def cut(shell):
    for s in (1, -1):
        for outline in (combo_outline(s), fog_outline(s)):
            shell.split(outline, 'z', 1, lambda f, c, n, s=s: c[2] > 1.6 and n[2] > 0.1 and c[0] * s > 0.3,
                        delete=True)
    for s in (1, -1):
        shell.split(lid_outline(s), 'y', 1, lambda f, c, n, s=s: c[0] * s > 0.35 and c[1] > 0.5 and n[1] > 0.25,
                    delete=True)


def _hinge(shell, s):
    """the hinge: along x under the lid's rear edge, 8 mm below the surface"""
    h = shell.hit((s * 0.60, 3.0, HINGE_Z), (0, -1, 0))
    return np.array((s * 0.60, h[0][1] - 0.008, HINGE_Z))


def _lid_surface(shell, outline, lift, rings=4):
    """rings of points on the shell inside `outline` (plan), outermost first; and the centre"""
    poly = np.asarray(outline, float)
    c = poly.mean(axis=0)
    out = []
    for k in range(rings, 0, -1):
        pts2 = [tuple(c + (p - c) * (k / rings)) for p in poly]
        out.append([np.array(p) for p in lay_on(shell, pts2, 'y', 1, lift)])
    centre = np.array(lay_on(shell, [tuple(c)], 'y', 1, lift)[0])
    return out, centre


def _fan(mesh, rings, centre, mat, out_sign):
    n = len(rings[0])
    for j in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            mesh.face([tuple(rings[j][k]), tuple(rings[j][k2]), tuple(rings[j + 1][k2]), tuple(rings[j + 1][k])],
                      mat, out=(0, out_sign, 0))
    for k in range(n):
        mesh.face([tuple(centre), tuple(rings[-1][k]), tuple(rings[-1][(k + 1) % n])], mat, out=(0, out_sign, 0))


def _rot_x(p, h, ang):
    """rotate game point p about the x axis through h by ang (right-handed about +x)"""
    d = np.asarray(p, float) - h
    c, s_ = math.cos(ang), math.sin(ang)
    return h + np.array((d[0], d[1] * c - d[2] * s_, d[1] * s_ + d[2] * c))


def well(mesh, shell, s):
    """the opening under the lid: black walls down to a floor"""
    rim = [np.array(p) for p in lay_on(shell, lid_outline(s), 'y', 1, 0.0)]
    c = np.mean(rim, axis=0)
    n = len(rim)
    for k in range(n):
        a, b = rim[k], rim[(k + 1) % n]
        q = [tuple(a), tuple(b), (b[0], WELL_FLOOR, b[2]), (a[0], WELL_FLOOR, a[2])]
        m = (a + b) / 2
        mesh.face(q, 'trim', out=(c[0] - m[0], 0, c[2] - m[2]))
    mesh.face([(p[0], WELL_FLOOR, p[2]) for p in rim], 'trim', out=(0, 1, 0))


def pod(root_body, shell, mats, counts, s):
    side = 'l' if s > 0 else 'r'
    H = _hinge(shell, s)
    e = bpy.data.objects.new(f'popup_{side}', None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(*H)
    e.parent = root_body
    e['popupClosed'] = POD_ANGLE
    e.empty_display_size = 0.1

    # the lid in its closed pose: the shell's own surface inside the outline, a 12 mm thick edge, black underside
    lid = Mesh(f'popup_lid_{side}')
    top, ctop = _lid_surface(shell, lid_outline(s, 0.003), 0.0)
    bot, cbot = _lid_surface(shell, lid_outline(s, 0.006), -0.012)
    _fan(lid, top, ctop, 'paint', 1)
    _fan(lid, bot, cbot, 'trim', -1)
    n = len(top[0])
    cc = np.mean(top[0], axis=0)
    for k in range(n):
        k2 = (k + 1) % n
        a, b = top[0][k], top[0][k2]
        m = (a + b) / 2
        lid.face([tuple(a), tuple(b), tuple(bot[0][k2]), tuple(bot[0][k])], 'paint', out=(m[0] - cc[0], 0, m[2] - cc[2]))
    # raise it: rotate by −POD_ANGLE about the hinge
    for v in lid.bm.verts:
        v.co = Vector(B(*_rot_x(G(v.co), H, -POD_ANGLE)))

    # the lamp unit under the raised lid: a black wedge whose front carries the lens, facing straight ahead
    raised = [_rot_x(p, H, -POD_ANGLE) for p in bot[0]]
    raised = np.array(raised)
    zf = raised[:, 2].max()
    # the lid's underside as a plane y = a + b z (least squares over its edge)
    A = np.c_[np.ones(len(raised)), raised[:, 2]]
    coef, *_ = np.linalg.lstsq(A, raised[:, 1], rcond=None)
    y_lid = lambda z: coef[0] + coef[1] * z - 0.004
    xs_front = raised[raised[:, 2] > zf - 0.06][:, 0]
    x_in, x_out = (xs_front.min(), xs_front.max()) if s > 0 else (xs_front.max(), xs_front.min())
    x_in += s * 0.012
    x_out -= s * 0.012
    z_f = zf - 0.022
    z_b = HINGE_Z + 0.03
    y_b = H[1] - 0.035

    def proud(off):
        """how far the unit's top corners would stand above the body with the pod closed"""
        worst = -1.0
        for x in (x_in, (x_in + x_out) / 2, x_out):
            for z in np.linspace(z_b, z_f + 0.012, 6):
                p = _rot_x((x, y_lid(z) - off, z), H, POD_ANGLE)
                hh = shell.hit((p[0], 3.0, p[2]), (0, -1, 0))
                if hh is not None:
                    worst = max(worst, p[1] - hh[0][1])
        return worst

    off = 0.0
    for _ in range(8):
        w = proud(off)
        if w < -0.004:
            break
        off += w + 0.005
    y_top = lambda z: y_lid(z) - off
    box = Mesh(f'popup_lamp_{side}')
    corners = {}
    for xi, x in (('i', x_in), ('o', x_out)):
        for zi, z in (('f', z_f), ('b', z_b)):
            corners[xi + zi + 't'] = (x, y_top(z), z)
            corners[xi + zi + 'b'] = (x, y_b, z)
    C = corners
    box.face([C['ift'], C['oft'], C['ofb'], C['ifb']], 'trim', smooth=False, out=(0, 0, 1))      # front (bezel)
    box.face([C['ibt'], C['obt'], C['obb'], C['ibb']], 'trim', smooth=False, out=(0, 0, -1))
    box.face([C['ift'], C['oft'], C['obt'], C['ibt']], 'trim', smooth=False, out=(0, 1, 0))
    box.face([C['ifb'], C['ofb'], C['obb'], C['ibb']], 'trim', smooth=False, out=(0, -1, 0))
    box.face([C['ift'], C['ibt'], C['ibb'], C['ifb']], 'trim', smooth=False, out=(-s, 0, 0))
    box.face([C['oft'], C['obt'], C['obb'], C['ofb']], 'trim', smooth=False, out=(s, 0, 0))
    # the lens: a slightly domed rounded rectangle on the front, texture across it
    yt, yb = y_top(z_f) - 0.010, y_b + 0.012
    xa, xb = x_in + s * 0.010, x_out - s * 0.010
    w, h = abs(xb - xa), yt - yb
    cx, cy = (xa + xb) / 2, (yt + yb) / 2
    nu, nv = 8, 4
    grid = np.zeros((nu + 1, nv + 1, 3))
    uv = np.zeros((nu + 1, nv + 1, 2))
    for i in range(nu + 1):
        for j in range(nv + 1):
            u, v = i / nu, j / nv
            dome = 0.010 * (1 - (2 * u - 1) ** 2) * (1 - (2 * v - 1) ** 2) + 0.002
            x = xa + (xb - xa) * u
            grid[i, j] = (x, yb + h * v, z_f + dome)
            uv[i, j] = ((u if s > 0 else 1 - u), v)
    vs = box.grid(grid, 'popup_lens', uv=uv, flip=(s < 0))
    # make sure the lens faces forward
    box.bm.normal_update()
    for f in box.bm.faces:
        if f.material_index == box.slot('popup_lens') and G(f.normal)[2] < 0:
            f.normal_flip()

    # both into the hinge frame
    for m in (lid, box):
        for v in m.bm.verts:
            v.co = Vector(v.co) - Vector(B(*H))
        counts[m.name] = m.tris()
        m.build(e, mats, weld=1e-6)

    # check: closed, nothing may stand proud of the body
    worst = -1.0
    for name in (f'popup_lid_{side}', f'popup_lamp_{side}'):
        ob = bpy.data.objects[name]
        for v in ob.data.vertices:
            p = _rot_x(np.array(G(v.co)) + H, H, POD_ANGLE)
            hh = shell.hit((p[0], 3.0, p[2]), (0, -1, 0))
            if hh is not None:
                worst = max(worst, p[1] - hh[0][1])
    print(f'POPUP {side} hinge {np.round(H, 3).tolist()} closed: highest point {worst * 1000:.1f} mm vs surface')
    return e


# ---------------------------------------------------------------- outlines in the front / rear views


def clip(poly, x0, keep_greater, s=1):
    """Sutherland–Hodgman against the line x = s·x0 (2-D polys); keep x·s > x0 if keep_greater"""
    out = []
    n = len(poly)
    f = (lambda p: p[0] * s - x0) if keep_greater else (lambda p: x0 - p[0] * s)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        fa, fb = f(a), f(b)
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def shrink(poly, d):
    c = np.mean(np.array(poly), axis=0)
    return [tuple(np.array(p) - (np.array(p) - c) / max(np.linalg.norm(np.array(p) - c), 1e-9) * d) for p in poly]


def combo_outline(s):
    ctrl = [(0.440, 0.472), (0.446, 0.512), (0.490, 0.535), (0.580, 0.552), (0.675, 0.576), (0.722, 0.582),
            (0.739, 0.562), (0.716, 0.538), (0.640, 0.512), (0.560, 0.488), (0.490, 0.462)]
    return [(s * x, y) for x, y in smooth_outline(ctrl, 4)]


# the rear lamp band: one smoked strip across the tail (x from −X_END to X_END), lamps outboard of ±X_LAMP
X_END, X_LAMP = 0.748, 0.355


def band_edges(x):
    """bottom and top of the rear band at x (bundle cameras of r19 / r11: a thin garnish high up in the middle,
    y 0.765–0.80; the lamps lower and taller, y 0.66–0.78 at x 0.55); the outer ends are rounded"""
    t = abs(x) / X_END
    top = 0.800 - 0.045 * t * t
    lamp = _smooth(0.20, 0.40, abs(x))
    bot = 0.765 - 0.105 * lamp + 0.012 * t * t
    x0 = 0.67
    if abs(x) > x0:
        f = math.sqrt(max(0.0, 1 - ((abs(x) - x0) / (X_END - x0)) ** 2))
        mid = (top + bot) / 2 + 0.008 * (1 - f)
        top = mid + (top - mid) * f
        bot = mid - (mid - bot) * f
    return bot, top


def _smooth(a, b, t):
    t = min(1.0, max(0.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def strip(m, shell, x0, x1, mat, lift, nu, nv=4, uv=False, inset=0.0):
    """a grid between x0 and x1 under band_edges, laid on the tail (crisp edges, no fan)"""
    xs = list(np.linspace(x0, x1, nu + 1))
    rows = []
    uvs = []
    for x in xs:
        bot, top = band_edges(x)
        bot, top = bot + inset, top - inset
        pts = [(x, bot + (top - bot) * j / nv) for j in range(nv + 1)]
        rows.append(lay_on(shell, pts, 'z', -1, lift))
        u = (abs(x) - X_LAMP) / (X_END - X_LAMP)
        uvs.append([(u, j / nv) for j in range(nv + 1)])
    for i in range(nu):
        for j in range(nv):
            q = [rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]]
            if any(p is None for p in q):
                continue
            uq = [uvs[i][j], uvs[i + 1][j], uvs[i + 1][j + 1], uvs[i][j + 1]] if uv else None
            m.face([tuple(p) for p in q], mat, uvs=uq, out=(0, 0, -1))


def tail_band(m, shell):
    # the smoked base, end to end, then the red lenses outboard and a black rim round the whole band
    strip(m, shell, -X_END, X_END, 'gloss_black', 0.002, 60)
    for s in (1, -1):
        a, b = (X_LAMP + 0.008, X_END - 0.006) if s > 0 else (-(X_END - 0.006), -(X_LAMP + 0.008))
        strip(m, shell, a, b, 'taillight', 0.004, 24, uv=True, inset=0.006)
    # the band's frame: a thin dark lip standing proud round the edge
    edge = [(x, band_edges(x)[1]) for x in np.linspace(-X_END, X_END, 61)] + \
           [(x, band_edges(x)[0]) for x in np.linspace(X_END, -X_END, 61)]
    pts = lay_on(shell, edge, 'z', -1, 0.0)
    out = lay_on(shell, edge, 'z', -1, 0.007)
    n = len(pts)
    for k in range(n):
        k2 = (k + 1) % n
        q = [pts[k], pts[k2], out[k2], out[k]]
        if any(p is None for p in q):
            continue
        m.face([tuple(p) for p in q], 'trim', smooth=False, out=(0, 0, -1))


def pocket(m, shell, outline, depth, wall, back):
    """a recess behind an opening cut in the shell: walls back along −z, a back face; returns z_back(x, y)"""
    rim = [np.array(p) for p in lay_on(shell, outline, 'z', 1, 0.0) if p is not None]
    c = np.mean(rim, axis=0)
    bk = [np.array((c[0] + (p[0] - c[0]) * 0.93, c[1] + (p[1] - c[1]) * 0.90, p[2] - depth)) for p in rim]
    n = len(rim)
    for k in range(n):
        k2 = (k + 1) % n
        q = [rim[k], rim[k2], bk[k2], bk[k]]
        mid = np.mean(q, axis=0)
        m.face([tuple(p) for p in q], wall, out=(c[0] - mid[0], c[1] - mid[1], 0.0))
    m.face([tuple(p) for p in bk], back, smooth=False, out=(0, 0, 1))
    ribbon(m, shell, outline, 'z', 1, 'trim', width=0.006, lift=0.001)

    def z_back(x, y):
        h = shell.hit((x, y, 4.0), (0, 0, -1))
        return (h[0][2] if h is not None else c[2]) - depth
    return z_back


def disc(m, z_back, cx, cy, rx, ry, mat, lift, uv=False, n=20):
    """a flat ellipse standing `lift` in front of a pocket's back"""
    z = z_back(cx, cy) + lift
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n), z) for i in range(n)]
    uvs = None
    if uv:   # the headlight map's bowl: centre (300, 66), radius 58 px in 512 × 128
        uvs = [((300 + 58 * math.cos(2 * math.pi * i / n)) / 512, 1 - (66 + 58 * math.sin(2 * math.pi * i / n)) / 128)
               for i in range(n)]
    m.face(pts, mat, smooth=False, uvs=uvs, out=(0, 0, 1))


def fog_outline(s):
    ctrl = [(0.440, 0.296), (0.560, 0.288), (0.650, 0.300), (0.690, 0.335), (0.672, 0.385), (0.590, 0.405),
            (0.470, 0.400), (0.430, 0.350)]
    return [(s * x, y) for x, y in smooth_outline(ctrl, 4)]


def ellipse(cx, cy, rx, ry, n=20):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def build(body, shell, mats, counts):
    m = Mesh('lamps')
    for s in (1, -1):
        well(m, shell, s)
        # front combination lamp: a recessed unit — dark housing, round projector in a chrome ring, a chrome
        # reflector outboard and a small amber segment at the tip
        back = pocket(m, shell, combo_outline(s), 0.035, 'gloss_black', 'gloss_black')
        disc(m, back, s * 0.492, 0.499, 0.032, 0.032, 'chrome', 0.004)
        disc(m, back, s * 0.492, 0.499, 0.023, 0.023, 'headlight', 0.008, uv=True)
        disc(m, back, s * 0.615, 0.533, 0.034, 0.016, 'chrome', 0.003)
        disc(m, back, s * 0.700, 0.556, 0.016, 0.009, 'amber', 0.005)
        # fog lamp deep in its own corner intake
        back = pocket(m, shell, fog_outline(s), 0.06, 'trim', 'trim')
        disc(m, back, s * 0.530, 0.346, 0.042, 0.038, 'gloss_black', 0.010)
        disc(m, back, s * 0.530, 0.346, 0.033, 0.030, 'lens_clear', 0.016)
        # side marker (amber) on the front wing, side reflector (red) on the rear quarter
        patch(m, shell, ellipse(0.646, 0.574, 0.022, 0.010), 'x', s, 'amber', lift=0.002, rings=2)
        patch(m, shell, ellipse(-1.697, 0.445, 0.030, 0.008), 'x', s, 'reflector', lift=0.002, rings=2)
        # bumper: red reflector / rear fog bar with the clear reverse lamp at its inner end
        bar = [(s * x, y) for x, y in smooth_outline([(0.395, 0.474), (0.615, 0.470), (0.622, 0.490),
                                                      (0.400, 0.500)], 3)]
        patch(m, shell, bar, 'z', -1, 'gloss_black', lift=0.002, rings=2)
        red = clip(shrink(bar, 0.004), 0.47, True, s)
        rev = clip(shrink(bar, 0.004), 0.47, False, s)
        patch(m, shell, red, 'z', -1, 'reflector', lift=0.004, rings=2)
        patch(m, shell, rev, 'z', -1, 'lens_clear', lift=0.004, rings=2)
    tail_band(m, shell)
    counts['lamps'] = m.tris()
    m.build(body, mats, weld=1e-6)
    for s in (1, -1):
        pod(body, shell, mats, counts, s)
