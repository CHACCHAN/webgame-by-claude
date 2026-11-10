"""
The Cybertruck's body as flat panels, in plain Python (no Blender): the Blender build (cybertruck.py) and the photo
fitting tools (fitdata/cybertruck/tools) share it.

The stainless shell is a convex polyhedron, the intersection of half-spaces: the body side (vertical), the upper side
(the tumblehome from the beltline up to the roof rail: fender, A-pillar, window band and sail are one plane), the hood,
the windscreen, the roof (glass roof and vault cover), the tailgate, the front face (centre and two corner facets),
the lower side facet and the floor; the light bar is a chamfer between the hood and the front face. So every panel is
exactly flat and every crease is the straight intersection of two planes, as on the truck. The wheel arches are
prisms cut out of it (their walls are the wheel-well liners). Bumpers, the arch cladding, the rocker and the lamps are
separate pieces.

Game frame: metres, x = the truck's left, y up (0 = road), z forward, origin midway between the axles.
All parameters are in P (defaults below, fitted values in fitdata/cybertruck/shape.json); features(P) gives the named
points that were read off the photos (fitdata/cybertruck/annot.json), faces(P) the panels.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHAPE_JSON = os.path.join(HERE, 'fitdata', 'cybertruck', 'shape.json')

WB = 3.635                 # wheelbase (143.1 in)
LENGTH, WIDTH, HEIGHT = 5.683, 2.027, 1.791

# --- parameters (metres, degrees); left side, mirrored for the right
DEFAULTS = {
    'sw': 1.0135,                    # half width of the body side (published width 2027 mm)
    'belt_f': 1.056, 'belt_r': 1.317,   # beltline crease height at z = +2.0 / -2.8 (a straight line)
    'tumble': 21.0,                  # upper side: inward lean from vertical
    'zf': 2.570, 'yk': 0.990,        # front face plane (top) and the hood's front edge height (centre)
    'face_lean': 0.015,              # front face bottom (at y_ff) this far ahead of its top
    'xk': 0.600,                     # front edge kink: centre section to the corner facets
    'y_ff': 0.648,                   # bottom of the stainless front face (above the lamp strip)
    'bar': 0.030,                    # light bar chamfer (size along the front face)
    'bar_h': 0.012,                  # ... and along the hood
    'bar_lip': 0.020,                # the dark lip under the light bar, down the face
    'hl_x0': 0.40, 'hl_x1': 0.64, 'hl_h': 0.014, 'hl_gap': 0.004,   # headlamp slits under the face (inner, outer x)
    'tl_kx': 0.004, 'tl_kw': 0.124, 'tl_kt': 0.020, 'tl_kh': 0.085,  # tail corner blocks: inset, width, top inset, height
    'tl_cy': 0.055, 'tl_ch': 0.010, 'tl_cw': 0.345,                  # tail line: below the band top, height, lit centre half
    'tk_w': 0.140,                   # corner lamp housings (the line runs between them)
    'zws': 1.965, 'yws': 1.201,      # windscreen base line
    'zpk': 0.301, 'ypk': 1.766,      # roof peak line
    'roof': 7.46,                    # roof slope behind the peak (deg, down to the rear)
    'ztg': -2.961, 'tg_lean': 0.043,  # tailgate plane at the top corner; its foot (y_tgb) this far forward
    'y_lb': 1.206,                   # bottom of the tail light band (black) on the tailgate
    'y_tgb': 0.706,                  # bottom of the stainless tailgate
    'z_rg': -1.10,                   # glass roof ends, vault cover begins
    'rail': 0.08,                    # the bed rails: the stainless strip between the sail edge and the vault cover
    'lc_f': 0.541, 'lc_r': 0.603,    # lower crease height at z = +1.17 / -0.93
    'lower': 18.0,                   # lower side facet: inward lean below the crease
    'y_db': 0.387,                   # bottom of the doors (lower edge of the stainless)
    'z_sa': 1.170, 'z_sb': 0.090, 'z_sc': -0.920,   # door shut lines (front door front edge, B, rear door rear edge)
    'w_bot': 0.075, 'w_top': 0.030, 'w_a': 0.085,    # window: band under it, seal under the rail, A-pillar strip
    'w_cb': -0.890, 'w_ct': -0.899,  # window rear edge (C pillar) at the bottom / top
    'w_b': 0.040,                    # B pillar half width
    # arch cladding outline on the side (z, y): front arch bf, tf, tr, br; rear arch bf, tf, tr, br
    'af_bf_z': 2.267, 'af_bf_y': 0.662, 'af_tf_z': 2.130, 'af_tf_y': 0.976, 'af_tr_z': 1.494, 'af_tr_y': 0.986,
    'af_br_z': 1.202, 'af_br_y': 0.541,
    'ar_bf_z': -1.174, 'ar_bf_y': 0.565, 'ar_tf_z': -1.473, 'ar_tf_y': 1.033, 'ar_tr_z': -2.154, 'ar_tr_y': 1.052,
    'ar_br_z': -2.448, 'ar_br_y': 0.683,
    'cl_w': 0.070, 'cl_out': 0.025,  # cladding band width, how far it stands out of the side
    'liner_x': 0.56,                 # wheel well inner wall
    'y_rk': 0.300,                   # rocker cladding bottom
    # bumpers
    'fb_top': 0.615, 'fb_z': 2.665, 'fb_low': 0.380, 'fb_bot': 0.280, 'fb_botz': 2.585, 'fb_side': 0.985,
    'rb_top': 0.640, 'rb_z': -3.000, 'rb_bot': 0.300, 'rb_side': 0.990,
    'rb_mid': 0.440, 'rb_lw': 0.66, 'rb_lz': 0.06,   # rear bumper: upper block's bottom; lower block half width, set-in
    'flap_y': 0.20,                                  # the rear mud flaps' lower edge
    'rb_cx': 0.33, 'rb_cd': 0.10,                    # the upper block's recessed middle (number plate): half width, depth
    'plf_y': 0.485, 'plf_z': 2.680, 'plr_y': 0.630, 'plr_z': -2.990,
    # wheels
    'hub_x': 0.935, 'hub_y': 0.423, 'track': 1.745, 'tyre_r': 0.439,
}


def load(path=SHAPE_JSON):
    P = dict(DEFAULTS)
    if path and os.path.exists(path):
        P.update(json.load(open(path)).get('params', {}))
    return P


# --- small vector helpers (tuples)
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)
def lerp(a, b, t): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
def mirror(p): return (-p[0], p[1], p[2])


def plane(n, p):
    """half-space n·x <= d through point p (n points outwards)"""
    n = unit(n)
    return (n, dot(n, p))


def plane3(a, b, c, out_hint):
    """plane through three points, normal turned towards out_hint"""
    n = unit(cross(sub(b, a), sub(c, a)))
    if dot(n, out_hint) < 0:
        n = mul(n, -1)
    return (n, dot(n, a))


def mirror_plane(pl):
    n, d = pl
    return ((-n[0], n[1], n[2]), d)


EPS = 1e-9


def clip_poly(poly, pl):
    """the part of a convex polygon with n·x <= d; also the points on the cut"""
    n, d = pl
    out, cut = [], []
    m = len(poly)
    ds = [dot(n, p) - d for p in poly]
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da, db = ds[i], ds[(i + 1) % m]
        if da <= EPS:
            out.append(a)
            if abs(da) <= EPS:
                cut.append(a)
        if (da < -EPS and db > EPS) or (da > EPS and db < -EPS):
            p = lerp(a, b, da / (da - db))
            out.append(p)
            cut.append(p)
    return out, cut


def _dedupe(pts, tol=1e-7):
    res = []
    for p in pts:
        if all(norm(sub(p, q)) > tol for q in res):
            res.append(p)
    return res


def _order(pts, n):
    """points of a convex polygon in a plane with normal n, counter-clockwise seen from n's side"""
    c = mul(pts[0], 0)
    for p in pts:
        c = add(c, p)
    c = mul(c, 1.0 / len(pts))
    u = unit(sub(pts[0], c))
    v = cross(n, u)
    return sorted(pts, key=lambda p: math.atan2(dot(sub(p, c), v), dot(sub(p, c), u)))


class Face:
    __slots__ = ('pts', 'tag', 'mat', 'uvs')

    def __init__(self, pts, tag, mat='paint'):
        self.pts, self.tag, self.mat, self.uvs = pts, tag, mat, None

    def normal(self):
        n = (0.0, 0.0, 0.0)
        m = len(self.pts)
        for i in range(m):
            a, b = self.pts[i], self.pts[(i + 1) % m]
            n = add(n, ((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])))
        return unit(n) if norm(n) > 1e-12 else (0.0, 1.0, 0.0)

    def centre(self):
        c = (0.0, 0.0, 0.0)
        for p in self.pts:
            c = add(c, p)
        return mul(c, 1.0 / len(self.pts))


def box_faces(x0, x1, y0, y1, z0, z1, tag='box'):
    V = lambda i, j, k: ((x0, x1)[i], (y0, y1)[j], (z0, z1)[k])
    quads = [[(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)], [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
             [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
             [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)], [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]]
    return [Face([V(*q) for q in quad], tag) for quad in quads]


def clip_solid(faces, pl, tag):
    """cut a convex solid (its faces) by a half-space; the cut is closed by a new face tagged `tag`"""
    out, cuts = [], []
    for f in faces:
        p, c = clip_poly(f.pts, pl)
        p = _dedupe(p)
        if len(p) >= 3:
            out.append(Face(p, f.tag, f.mat))
        cuts += c
    cuts = _dedupe(cuts)
    if len(cuts) >= 3:
        out.append(Face(_order(cuts, pl[0]), tag))
    return out


def solid(planes, bounds=(-1.5, 1.5, 0.0, 2.2, -3.4, 3.2)):
    """convex solid from (tag, plane) pairs"""
    faces = box_faces(*bounds)
    for tag, pl in planes:
        faces = clip_solid(faces, pl, tag)
    return [f for f in faces if f.tag != 'box']


def split(faces, pl, mat_in=None, mat_out=None, select=None, tag_in=None):
    """split the selected faces by a plane; the part with n·x <= d gets mat_in (if given), the other mat_out"""
    res = []
    for f in faces:
        if select is not None and not select(f):
            res.append(f)
            continue
        a, _ = clip_poly(f.pts, pl)
        b, _ = clip_poly(f.pts, (mul(pl[0], -1), -pl[1]))
        a, b = _dedupe(a), _dedupe(b)
        if len(a) >= 3:
            res.append(Face(a, tag_in or f.tag, mat_in or f.mat))
        if len(b) >= 3:
            res.append(Face(b, f.tag, mat_out or f.mat))
    return res


def cut_prism(faces, prism):
    """remove from the faces everything inside a convex prism (list of half-spaces, inside = n·x <= d)"""
    res = []
    for f in faces:
        pieces = [f.pts]
        for pl in prism:
            nxt = []
            for poly in pieces:
                outside, _ = clip_poly(poly, (mul(pl[0], -1), -pl[1]))
                outside = _dedupe(outside)
                if len(outside) >= 3 and _area(outside) > 1e-10:
                    res.append(Face(outside, f.tag, f.mat))
                inside, _ = clip_poly(poly, pl)
                inside = _dedupe(inside)
                if len(inside) >= 3 and _area(inside) > 1e-10:
                    nxt.append(inside)
            pieces = nxt
    return res


def _area(pts):
    n = (0.0, 0.0, 0.0)
    for i in range(1, len(pts) - 1):
        n = add(n, cross(sub(pts[i], pts[0]), sub(pts[i + 1], pts[0])))
    return 0.5 * norm(n)


def plane_quad(pl, size=20.0):
    """a big square in a plane, facing along its normal"""
    n, d = pl
    c = mul(n, d)
    a = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = unit(cross(n, a))
    v = cross(n, u)
    return [add(c, add(mul(u, s * size), mul(v, t * size))) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def wall(pl, bounds, tag, mat):
    """the face on plane pl inside all half-spaces `bounds`, facing against pl's normal (into the cut-out)"""
    poly = list(reversed(plane_quad(pl)))
    for b in bounds:
        poly, _ = clip_poly(poly, b)
        poly = _dedupe(poly)
        if len(poly) < 3:
            return None
    return Face(poly, tag, mat) if _area(poly) > 1e-8 else None


# --- the design
class Shape:
    """derived geometry of a parameter set"""

    def __init__(self, P):
        self.P = P
        sw = P['sw']
        self.sw = sw
        # beltline y(z)
        self.sb = (P['belt_f'] - P['belt_r']) / (2.0 - -2.8)
        self.yb0 = P['belt_f'] - self.sb * 2.0
        th = math.radians(P['tumble'])
        self.th = th
        # upper side plane: contains the beltline (sw, yb(z), z) and the inward-up direction (-sin th, cos th, 0)
        nU = (math.cos(th), math.sin(th), -self.sb * math.sin(th))
        self.upper = plane(nU, (sw, self.yb0, 0.0))
        self.side = plane((1, 0, 0), (sw, 0, 0))
        # hood: flat across, front edge (yk at zf) to the windscreen base (yws at zws)
        self.tan_h = (P['yws'] - P['yk']) / (P['zf'] - P['zws'])
        self.hood = plane((0, 1, self.tan_h), (0, P['yk'], P['zf']))
        self.tan_w = (P['ypk'] - P['yws']) / (P['zws'] - P['zpk'])
        self.ws = plane((0, 1, self.tan_w), (0, P['yws'], P['zws']))
        self.tan_r = math.tan(math.radians(P['roof']))
        self.roof = plane((0, 1, -self.tan_r), (0, P['ypk'], P['zpk']))
        # front face: z <= zf at the top (yk), leaning forward by face_lean at y_ff
        lean = P['face_lean'] / max(1e-6, P['yk'] - P['y_ff'])
        self.face_lean = lean
        self.front = plane((0, lean, 1), (0, P['yk'], P['zf']))
        # nose corner: hood ∩ beltline on the side
        zn = (P['yk'] + self.tan_h * P['zf'] - self.yb0) / (self.sb + self.tan_h)
        self.N = (sw, self.yb(zn), zn)
        self.K = (P['xk'], P['yk'], P['zf'])
        # corner facet: through K and N, leaning like the front face
        d = sub(self.N, self.K)
        nC = unit(cross((0, -1, lean), d))
        if nC[2] < 0:
            nC = mul(nC, -1)
        self.corner = (nC, dot(nC, self.K))
        # tail corner: roof ∩ beltline
        zt = (P['ypk'] - self.tan_r * P['zpk'] - self.yb0) / (self.sb - self.tan_r)
        self.T = (sw, self.yb(zt), zt)
        # tailgate through the tail corner, foot (y_tgb) tg_lean forward
        tl = P['tg_lean'] / max(1e-6, self.T[1] - P['y_tgb'])
        self.tg_tl = tl
        self.tailgate = plane((0, -tl, -1), self.T)   # z = T.z + (T.y - y) tl: the foot stands forward
        # lower facet: contains the lower crease line (sw, ylc(z), z), leans in by `lower` going down
        self.slc = (P['lc_f'] - P['lc_r']) / (P['z_sa'] - P['z_sc'])
        self.ylc0 = P['lc_f'] - self.slc * P['z_sa']
        ph = math.radians(P['lower'])
        nL = (math.cos(ph), -math.sin(ph), self.slc * math.sin(ph))
        self.lowerp = plane(nL, (sw, self.ylc0, 0.0))
        self.floor = plane((0, -1, 0), (0, P['y_db'], 0))
        # light bar chamfer: cuts the hood/front-face edge `bar` down the face and `bar_h` back along the hood
        self.bar_c = self._chamfer(self.front, self.hood, (0, P['yk'], P['zf']), P['bar'], P['bar_h'], (0, 1, 1))
        kc = self._chamfer(self.corner, self.hood, self.K, P['bar'], P['bar_h'], add(self.corner[0], (0, 1, 0)))
        self.bar_k = kc

    def yb(self, z):
        return self.yb0 + self.sb * z

    def ylc(self, z):
        return self.ylc0 + self.slc * z

    def _chamfer(self, face_pl, hood_pl, p_edge, a, b, hint):
        """plane through the point `a` down the face from the edge and the point `b` back along the hood"""
        nf, nh = face_pl[0], hood_pl[0]
        e = unit(cross(nf, nh))                     # edge direction
        down = unit(cross(e, nf))                   # in the face, away from the edge
        if down[1] > 0:
            down = mul(down, -1)
        back = unit(cross(nh, e))                   # in the hood, away from the edge
        if dot(back, nf) > 0:
            back = mul(back, -1)
        # the edge line passes through p_edge (on both planes); find a point on it
        p0 = self._on_both(face_pl, hood_pl, p_edge)
        pa = add(p0, mul(down, a))
        pb = add(p0, mul(back, b))
        return plane3(pa, pb, add(pa, e), hint)

    @staticmethod
    def _on_both(p1, p2, near):
        """the point of the line p1 ∩ p2 nearest to `near`"""
        n1, d1 = p1
        n2, d2 = p2
        e = cross(n1, n2)
        # solve for the point x = near + s n1 + t n2 projected onto both planes
        a11, a12, a22 = dot(n1, n1), dot(n1, n2), dot(n2, n2)
        r1, r2 = d1 - dot(n1, near), d2 - dot(n2, near)
        det = a11 * a22 - a12 * a12
        s = (r1 * a22 - r2 * a12) / det
        t = (r2 * a11 - r1 * a12) / det
        return add(near, add(mul(n1, s), mul(n2, t)))

    # points in the upper plane: (z, v) with v = height above the beltline
    def up(self, z, v):
        return (self.sw - v * math.tan(self.th), self.yb(z) + v, z)

    def v_ws(self, z):
        """height of the windscreen's side edge above the beltline at z (in the upper plane)"""
        # y on the windscreen plane: yws + (zws - z) tan_w; the upper plane at that y has x = sw - v tan
        P = self.P
        return P['yws'] + (P['zws'] - z) * self.tan_w - self.yb(z)

    def v_roof(self, z):
        P = self.P
        return P['ypk'] + (z - P['zpk']) * self.tan_r - self.yb(z)

    def planes(self):
        """(tag, half-space) of the shell, both sides"""
        L = [('side', self.side), ('upper', self.upper), ('corner', self.corner), ('lower', self.lowerp),
             ('bar_k', self.bar_k)]
        res = [('hood', self.hood), ('ws', self.ws), ('roof', self.roof), ('face', self.front), ('tg', self.tailgate),
               ('floor', self.floor), ('bar_c', self.bar_c)]
        for t, pl in L:
            res.append((t + '_l', pl))
            res.append((t + '_r', mirror_plane(pl)))
        return res

    def arch_prism(self, front, right=False):
        P = self.P
        k = 'af_' if front else 'ar_'
        bf = (P[k + 'bf_z'], P[k + 'bf_y'])
        tf = (P[k + 'tf_z'], P[k + 'tf_y'])
        tr = (P[k + 'tr_z'], P[k + 'tr_y'])
        br = (P[k + 'br_z'], P[k + 'br_y'])

        def zy_plane(a, b, inside_pt):
            # plane parallel to x through the side line a-b (z, y), inside towards inside_pt
            n = unit((0.0, -(b[0] - a[0]), (b[1] - a[1])))
            pa = (0.0, a[1], a[0])
            pl = (n, dot(n, pa))
            if dot(n, (0.0, inside_pt[1], inside_pt[0])) > pl[1]:
                pl = (mul(n, -1), -pl[1])
            return pl
        cz = 0.5 * (tf[0] + tr[0])
        cy = 0.5 * (tf[1] + br[1])
        c = (cz, cy)
        if not front:
            # rear arch: bf is the front leg's foot (vertical below), br the rear leg's foot
            prism = [zy_plane(bf, tf, c), zy_plane(tf, tr, c), zy_plane(tr, br, c), plane((0, 0, 1), (0, 0, bf[0])),
                     plane((-1, 0, 0), (P['liner_x'], 0, 0))]
        else:
            prism = [zy_plane(bf, tf, c), zy_plane(tf, tr, c), zy_plane(tr, br, c), plane((0, 0, -1), (0, 0, br[0])),
                     plane((-1, 0, 0), (P['liner_x'], 0, 0))]
        if right:
            prism = [mirror_plane(p) for p in prism]
        return prism


def shell(P, arches=True, materials=True):
    """the stainless shell's faces (with the wheel-well liners)"""
    S = Shape(P)
    planes = S.planes()
    faces = solid(planes)
    liners = []
    if arches:
        for front in (True, False):
            for right in (False, True):
                pr = S.arch_prism(front, right)
                faces = cut_prism(faces, pr)
                for i, pl in enumerate(pr):
                    w = wall(pl, [q for j, q in enumerate(pr) if j != i] + [p for _, p in planes], 'liner', 'under')
                    if w is not None:
                        liners.append(w)
    faces += liners
    if materials:
        faces = paint_zones(S, faces)
    return S, faces


def _offset_in(face_pts, n, w):
    """half-spaces keeping a polygon `w` in from each edge (in its plane)"""
    res = []
    m = len(face_pts)
    for i in range(m):
        a, b = face_pts[i], face_pts[(i + 1) % m]
        e = sub(b, a)
        if norm(e) < 1e-6:
            continue
        inward = unit(cross(n, e))
        # keep inward·x >= inward·a + w  →  (-inward)·x <= -(inward·a + w)
        res.append((mul(inward, -1), -(dot(inward, a) + w)))
    return res


def paint_zones(S, faces):
    """materials: glass (windscreen, side windows, glass roof), the black vault cover, seals, the light bars"""
    P = S.P
    by = lambda *tags: (lambda f: f.tag in tags)
    out = []
    for f in faces:
        t = f.tag
        if t in ('floor', 'liner'):
            f.mat = 'under'
        elif t in ('bar_c', 'bar_k_l', 'bar_k_r'):
            f.mat = 'headlight'
        out.append(f)
    faces = out
    # windscreen: glass with a black border (frit)
    res = []
    for f in faces:
        if f.tag != 'ws':
            res.append(f)
            continue
        n = f.normal()
        piece = [Face(f.pts, 'ws', 'glass')]
        for hs in _offset_in(f.pts, n, 0.045):
            nxt = []
            for g in piece:
                a, _ = clip_poly(g.pts, (mul(hs[0], -1), -hs[1]))
                a = _dedupe(a)
                if len(a) >= 3 and _area(a) > 1e-9:
                    res.append(Face(a, 'ws_frit', 'trim'))
                b, _ = clip_poly(g.pts, hs)
                b = _dedupe(b)
                if len(b) >= 3:
                    nxt.append(Face(b, 'ws', 'glass'))
            piece = nxt
        res += piece
    faces = res
    # roof: glass from the peak back to z_rg, then the vault cover
    faces = split(faces, plane((0, 0, -1), (0, 0, P['z_rg'])), mat_in='glass', mat_out='vault', select=by('roof'))
    # the bed rails along the sail edges stay stainless: the vault cover lies between them
    zr0, zr1 = P['z_rg'], S.T[2]
    a, b = S.up(zr0, S.v_roof(zr0)), S.up(zr1, S.v_roof(zr1))
    a, b = (a[0] - P['rail'], a[1], a[2]), (b[0] - P['rail'], b[1], b[2])
    rail = plane3(a, b, add(a, (0, 1, 0)), (1, 0, 0))
    is_vault = lambda f: f.tag == 'roof' and f.mat == 'vault'
    faces = split(faces, rail, mat_in='vault', mat_out='paint', select=is_vault)
    faces = split(faces, mirror_plane(rail), mat_in='vault', mat_out='paint', select=is_vault)
    # front face: stainless above y_ff, the dark lamp strip / bumper backing below
    sel = lambda f: f.tag in ('face', 'corner_l', 'corner_r')
    faces = split(faces, plane((0, 1, 0), (0, P['y_ff'], 0)), mat_in='trim', select=sel)
    # the dark lip under the light bar: a strip of the face and the corner facets just below the chamfer
    def lip_plane(ch, face):
        e = unit(cross(face[0], ch[0]))
        down = unit(cross(e, face[0]))
        if down[1] > 0:
            down = mul(down, -1)
        return (ch[0], ch[1] + P['bar_lip'] * dot(ch[0], down))
    for ch, face, tag in ((S.bar_c, S.front, 'face'), (S.bar_k, S.corner, 'corner_l'),
                          (mirror_plane(S.bar_k), mirror_plane(S.corner), 'corner_r')):
        faces = split(faces, lip_plane(ch, face), mat_out='trim', select=lambda f, t=tag: f.tag == t and f.mat == 'paint')
    # tailgate: black light band from the top down to y_lb, stainless to y_tgb, black below (behind the bumper)
    faces = split(faces, plane((0, -1, 0), (0, P['y_lb'], 0)), mat_in='trim', select=by('tg'), tag_in='tg_band')
    faces = split(faces, plane((0, 1, 0), (0, P['y_tgb'], 0)), mat_in='trim', select=by('tg'))
    # behind the rear arch the stainless ends at the same height (the photos: the arch's rear foot, the tailgate's
    # lower edge): below it the bumper's black side runs forward to the arch flare
    sel = lambda f: f.tag in ('side_l', 'side_r', 'lower_l', 'lower_r') and f.mat == 'paint'
    faces = split(faces, plane((0, 0, 1), (0, 0, P['ar_br_z'])), select=sel, tag_in='rq')
    faces = split(faces, plane((0, 1, 0), (0, P['y_tgb'], 0)), mat_in='clad', select=by('rq'))
    # side windows in the upper side plane
    for side in ('l', 'r'):
        faces = _windows(S, faces, side)
    return faces


def window_poly(S):
    """the side window outline (left side), counter-clockwise from outside: bottom front tip, ..."""
    P = S.P
    vb = P['w_bot']

    def front_v(z):   # window's front edge: the windscreen edge lowered by the A-pillar strip
        return S.v_ws(z) - P['w_a']

    def top_v(z):
        return S.v_roof(z) - P['w_top']
    # front tip: front_v(z) = vb
    z0, z1 = P['zpk'], P['zws']
    for _ in range(60):
        zm = 0.5 * (z0 + z1)
        if front_v(zm) > vb:
            z0 = zm
        else:
            z1 = zm
    z_tip = 0.5 * (z0 + z1)
    # peak corner of the window: front edge meets the top edge
    z0, z1 = P['w_ct'], z_tip
    for _ in range(60):
        zm = 0.5 * (z0 + z1)
        if front_v(zm) < top_v(zm):
            z1 = zm
        else:
            z0 = zm
    z_pk = 0.5 * (z0 + z1)
    pts = [S.up(z_tip, vb), S.up(z_pk, front_v(z_pk)), S.up(P['w_ct'], top_v(P['w_ct'])), S.up(P['w_cb'], vb)]
    return pts


def _windows(S, faces, side):
    P = S.P
    win = window_poly(S)
    if side == 'r':
        win = [mirror(p) for p in win]
    sel_tag = 'upper_' + side
    nU = S.upper[0] if side == 'l' else mirror_plane(S.upper)[0]
    # half-spaces bounding the window: planes through each window edge, perpendicular to the upper plane
    hs = []
    m = len(win)
    # window_poly runs clockwise seen from the left; the half-spaces need counter-clockwise
    order = list(reversed(win)) if side == 'l' else win
    for i in range(m):
        a, b = order[i], order[(i + 1) % m]
        inward = unit(cross(nU, sub(b, a)))
        hs.append((mul(inward, -1), -dot(inward, a)))
    res = []
    for f in faces:
        if f.tag != sel_tag:
            res.append(f)
            continue
        pieces = [f.pts]
        for h in hs:
            nxt = []
            for poly in pieces:
                o, _ = clip_poly(poly, (mul(h[0], -1), -h[1]))
                o = _dedupe(o)
                if len(o) >= 3 and _area(o) > 1e-10:
                    res.append(Face(o, f.tag, f.mat))
                i_, _ = clip_poly(poly, h)
                i_ = _dedupe(i_)
                if len(i_) >= 3 and _area(i_) > 1e-10:
                    nxt.append(i_)
            pieces = nxt
        for poly in pieces:
            # seal band round the glass, and the B pillar
            g = [Face(poly, 'win_' + side, 'glass')]
            g2 = []
            for gf in g:
                inner = [gf]
                for hh in _offset_in(gf.pts, nU, 0.014):
                    nx = []
                    for q in inner:
                        a, _ = clip_poly(q.pts, (mul(hh[0], -1), -hh[1]))
                        a = _dedupe(a)
                        if len(a) >= 3 and _area(a) > 1e-10:
                            g2.append(Face(a, 'seal_' + side, 'trim'))
                        b, _ = clip_poly(q.pts, hh)
                        b = _dedupe(b)
                        if len(b) >= 3:
                            nx.append(Face(b, 'win_' + side, 'glass'))
                    inner = nx
                g2 += inner
            zb = P['z_sb']
            g2 = split(g2, plane((0, 0, 1), (0, 0, zb + P['w_b'])), select=lambda q: q.mat == 'glass')
            out = []
            for q in g2:
                if q.mat == 'glass':
                    c = q.centre()
                    if abs(c[2] - zb) < P['w_b']:
                        q.mat = 'trim'
                out.append(q)
            g2 = split(out, plane((0, 0, -1), (0, 0, zb - P['w_b'])), select=lambda q: q.mat == 'glass')
            for q in g2:
                if q.mat == 'glass' and abs(q.centre()[2] - zb) < P['w_b']:
                    q.mat = 'trim'
            res += g2
    return res


def features(P, S=None):
    """named points (left side) as read off the photos"""
    S = S or Shape(P)
    sw = S.sw
    f = {}
    f['nose'] = S.N
    f['lbk'] = S.K
    zff = P['zf'] + P['face_lean']
    f['ffk'] = (P['xk'], P['y_ff'], zff)
    # the corner facet's foot on the side
    nC, dC = S.corner
    # point on corner plane with x = sw, y = y_ff: nC.x*sw + nC.y*y + nC.z*z = dC
    f['ffo'] = (sw, P['y_ff'], (dC - nC[0] * sw - nC[1] * P['y_ff']) / nC[2])
    # windscreen base corner and peak corner: those lines meet the upper plane
    vb = S.v_ws(P['zws'])
    f['wsb'] = S.up(P['zws'], vb)
    f['peak'] = S.up(P['zpk'], S.v_roof(P['zpk']))
    f['tail'] = S.T
    rg = S.up(P['z_rg'], S.v_roof(P['z_rg']))             # the vault cover's front corner, inboard of the bed rail
    f['rg'] = (rg[0] - P['rail'], rg[1], rg[2])
    tl = S.tg_tl
    zt = lambda y: S.T[2] + (S.T[1] - y) * tl
    f['lbr'] = (sw, P['y_lb'], zt(P['y_lb']))
    f['tgb'] = (sw, P['y_tgb'], zt(P['y_tgb']))
    for k, z in (('a', P['z_sa']), ('b', P['z_sb']), ('c', P['z_sc'])):
        f['bd_' + k] = (sw, S.yb(z), z)
        f['lc_' + k] = (sw, S.ylc(z), z)
        f['db_' + k] = (sw - (S.ylc(z) - P['y_db']) * math.tan(math.radians(P['lower'])), P['y_db'], z)
    w = window_poly(S)
    f['wf'] = w[0]
    f['wct'] = w[2]
    f['wcb'] = w[3]
    xo = sw + P['cl_out']
    for k in ('af_bf', 'af_tf', 'af_tr', 'af_br', 'ar_bf', 'ar_tf', 'ar_tr', 'ar_br'):
        f[k] = (xo, P[k + '_y'], P[k + '_z'])
    f['fb_to'] = (P['fb_side'], P['fb_top'], P['fb_z'] - 0.20)
    f['rb_to'] = (P['rb_side'], P['rb_top'], P['rb_z'])
    return f


def _cut_arches(S, faces):
    for front in (True, False):
        for right in (False, True):
            faces = cut_prism(faces, S.arch_prism(front, right))
    return faces


def bumpers(P, S=None):
    """front and rear bumpers (the black textured plastic of the arch flares), each a convex block cut by the arches"""
    S = S or Shape(P)
    sw = S.sw
    # front: top, upper face, lower chamfer, floor; plan corners parallel to the body's corner facets
    nC = S.corner[0]
    zff = P['zf'] + P['face_lean']
    off = P['fb_z'] - zff                     # how far the bumper face stands ahead of the stainless face
    cf = (nC[0], 0.0, nC[2])
    cf = unit(cf)
    corner_pt = (P['xk'] + 0.02, 0.5, P['fb_z'])
    fpl = [('fb_top', plane((0, 1, 0), (0, P['fb_top'], 0))),
           ('fb_face', plane((0, 0, 1), (0, 0, P['fb_z']))),
           ('fb_low', plane3((0, P['fb_low'], P['fb_z']), (1, P['fb_low'], P['fb_z']), (0, P['fb_bot'], P['fb_botz']), (0, -1, 1))),
           ('fb_bot', plane((0, -1, 0), (0, P['fb_bot'], 0))),
           ('fb_back', plane((0, 0, -1), (0, 0, P['af_bf_z'] - 0.25))),
           ('fb_corner_l', plane(cf, corner_pt)), ('fb_corner_r', mirror_plane(plane(cf, corner_pt))),
           ('fb_side_l', plane((1, 0, 0), (P['fb_side'], 0, 0))), ('fb_side_r', plane((-1, 0, 0), (-P['fb_side'], 0, 0)))]
    fb = solid(fpl)
    for f in fb:
        f.mat = 'clad'
    # rear: a full-width upper block (top, rear face, chamfered corners) down to rb_mid, and under it a narrower lower
    # block round the hitch (half width rb_lw, its face rb_lz further forward) with a chamfer to the floor
    cr = plane3((P['rb_side'] - 0.06, 0, P['rb_z']), (P['rb_side'], 0, P['rb_z'] + 0.06), (P['rb_side'], 1, P['rb_z'] + 0.06), (1, 0, -1))
    rpl = [('rb_top', plane((0, 1, 0), (0, P['rb_top'], 0))),
           ('rb_bot', plane((0, -1, 0), (0, P['rb_mid'], 0))),
           ('rb_front', plane((0, 0, 1), (0, 0, P['ar_br_z'] + 0.25))),
           ('rb_corner_l', cr), ('rb_corner_r', mirror_plane(cr)),
           ('rb_side_l', plane((1, 0, 0), (P['rb_side'], 0, 0))), ('rb_side_r', plane((-1, 0, 0), (-P['rb_side'], 0, 0)))]
    # the upper block's middle (the number plate's place, |x| < rb_cx) stands rb_cd further forward than the wings
    zc = min(P['rb_z'] + P['rb_cd'], S.T[2] + (S.T[1] - P['rb_top']) * S.tg_tl - 0.005)   # not forward of the tailgate
    rb = solid(rpl + [('rb_face', plane((0, 0, -1), (0, 0, zc)))])
    wing = rpl[:1] + rpl[1:2] + [('rb_face', plane((0, 0, -1), (0, 0, P['rb_z']))), ('rb_wfront', plane((0, 0, 1), (0, 0, zc))),
                                 ('rb_corner_l', cr), ('rb_side_l', rpl[-2][1]), ('rb_wing_in', plane((-1, 0, 0), (P['rb_cx'], 0, 0)))]
    w = solid(wing)
    rb += w + [Face([mirror(p) for p in reversed(f.pts)], f.tag, f.mat) for f in w]
    zl = P['rb_z'] + P['rb_lz']
    lpl = [('rl_top', plane((0, 1, 0), (0, P['rb_mid'] + 0.01, 0))),
           ('rl_face', plane((0, 0, -1), (0, 0, zl))),
           ('rl_low', plane3((0, P['rb_bot'] + 0.06, zl), (1, P['rb_bot'] + 0.06, zl), (0, P['rb_bot'], zl + 0.06), (0, -1, -1))),
           ('rl_bot', plane((0, -1, 0), (0, P['rb_bot'], 0))),
           ('rl_front', plane((0, 0, 1), (0, 0, P['ar_br_z'] + 0.10))),
           ('rl_side_l', plane((1, 0, 0), (P['rb_lw'], 0, 0))), ('rl_side_r', plane((-1, 0, 0), (-P['rb_lw'], 0, 0)))]
    rb = rb + solid(lpl)
    for f in rb:
        f.mat = 'clad'
    return _cut_arches(S, fb), _cut_arches(S, rb)


def arch_outline(P, front):
    """the cladding's outer outline on the side, (z, y) from the lower end of one leg to the other"""
    k = 'af_' if front else 'ar_'
    pts = [(P[k + n + '_z'], P[k + n + '_y']) for n in ('bf', 'tf', 'tr', 'br')]
    if front:
        return pts + [(P[k + 'br_z'], P['y_rk'])]
    # the rear leg carries on straight down as the mud flap (photos p193, p150)
    return [(P[k + 'bf_z'], P['y_rk'])] + pts + [(P[k + 'br_z'], P['flap_y'])]


def _offset_line(pts, w, inside):
    """offset a (z, y) polyline by w towards the point `inside` (mitred)"""
    def nrm(a, b):
        dz, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dz, dy)
        n = (-dy / L, dz / L)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if (inside[0] - mid[0]) * n[0] + (inside[1] - mid[1]) * n[1] < 0:
            n = (-n[0], -n[1])
        return n
    ns = [nrm(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    out = []
    for i, p in enumerate(pts):
        if i == 0:
            n = ns[0]; k = 1.0
        elif i == len(pts) - 1:
            n = ns[-1]; k = 1.0
        else:
            a, b = ns[i - 1], ns[i]
            n = (a[0] + b[0], a[1] + b[1])
            L = math.hypot(*n)
            n = (n[0] / L, n[1] / L)
            k = 1.0 / max(0.3, n[0] * a[0] + n[1] * a[1])
        out.append((p[0] + n[0] * w * k, p[1] + n[1] * w * k))
    return out


def cladding(P, S=None):
    """the black arch cladding: a band round each arch, standing cl_out off the side, its inner edge folding into
    the wheel well; the legs run down to the rocker line. Left side; mirror for the right."""
    S = S or Shape(P)
    sw = S.sw
    xo = sw + P['cl_out']
    faces = []
    for front in (True, False):
        o = arch_outline(P, front)
        k = 'af_' if front else 'ar_'
        c = (0.5 * (P[k + 'tf_z'] + P[k + 'tr_z']), 0.3)
        inn = _offset_line(o, P['cl_w'], c)
        tag = 'clad_f' if front else 'clad_r'
        for i in range(len(o) - 1):
            a, b, bi, ai = o[i], o[i + 1], inn[i + 1], inn[i]
            # face (outwards +x): order so the normal is +x
            q = [(xo, a[1], a[0]), (xo, b[1], b[0]), (xo, bi[1], bi[0]), (xo, ai[1], ai[0])]
            f = Face(q, tag, 'clad')
            if f.normal()[0] < 0:
                f.pts.reverse()
            faces.append(f)
            # step from the side out to the face, along the outer outline
            st = Face([(sw - 0.002, a[1], a[0]), (xo, a[1], a[0]), (xo, b[1], b[0]), (sw - 0.002, b[1], b[0])], tag, 'clad')
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            away = (mid[0] - c[0], mid[1] - c[1])
            if st.normal()[2] * away[0] + st.normal()[1] * away[1] < 0:
                st.pts.reverse()
            faces.append(st)
            # return into the wheel well along the inner outline
            rt = Face([(xo, ai[1], ai[0]), (xo, bi[1], bi[0]), (sw - 0.12, bi[1], bi[0]), (sw - 0.12, ai[1], ai[0])], tag, 'clad')
            if rt.normal()[2] * away[0] + rt.normal()[1] * away[1] > 0:
                rt.pts.reverse()
            faces.append(rt)
        # end caps at the leg feet
        for i, j in ((0, 0), (len(o) - 1, len(o) - 1)):
            a, ai = o[i], inn[j]
            cap = Face([(sw - 0.002, a[1], a[0]), (xo, a[1], a[0]), (xo, ai[1], ai[0]), (sw - 0.12, ai[1], ai[0])], tag, 'clad')
            if cap.normal()[1] > 0 and a[1] < 0.5:
                cap.pts.reverse()
            faces.append(cap)
    return faces


def rocker(P, S=None):
    """black sill cladding under the doors, between the arches (left side)"""
    S = S or Shape(P)
    x_top = S.sw - (S.ylc(0.0) - P['y_db']) * math.tan(math.radians(P['lower']))
    pl = [('rk_out', plane3((x_top + 0.008, P['y_db'], 0), (x_top + 0.008, P['y_db'], 1), (x_top - 0.010, P['y_rk'], 0), (1, 0, 0))),
          ('rk_top', plane((0, 1, 0), (0, P['y_db'], 0))), ('rk_bot', plane((0, -1, 0), (0, P['y_rk'], 0))),
          ('rk_in', plane((-1, 0, 0), (0.55, 0, 0))),
          ('rk_f', plane((0, 0, 1), (0, 0, P['af_br_z'] + 0.02))), ('rk_r', plane((0, 0, -1), (0, 0, P['ar_bf_z'] - 0.02)))]
    f = solid(pl)
    for q in f:
        q.mat = 'clad'
    return f


def all_faces(P):
    """every panel of the body (both sides) for silhouettes: shell, bumpers, cladding, rocker"""
    S, F = shell(P)
    fb, rb = bumpers(P, S)
    cl = cladding(P, S)
    rk = rocker(P, S)
    side = cl + rk
    mir = [Face([mirror(p) for p in reversed(f.pts)], f.tag + '_m', f.mat) for f in side]
    return S, F + fb + rb + side + mir
