"""
Parts laid on the Impreza's shell (after the boolean cuts): lamps, shut lines, door handles, side markers, the fuel
lid, grilles, fog lamps, number plates and the tailpipe. Decals are projected along a frame's direction onto the
shell (ray casts on its BVH), so they follow its curves; the left side is built and mirrored.
"""
import math

import bmesh
from mathutils import Matrix, Vector

import raijin_data as D
import raijin_kit as K
import raijin_shell as SH


class Frame:
    """a projection plane: origin o, axes W (outward / along) and V, rays along d into the shell"""

    def __init__(self, o, d, W, V):
        self.o, self.d, self.W, self.V = Vector(o), Vector(d).normalized(), Vector(W).normalized(), Vector(V).normalized()
        # does a counter-clockwise (w, v) outline face the viewer?
        self.ccw_out = self.W.cross(self.V).dot(-self.d) > 0

    def ray(self, w, v):
        p = self.o + self.W * w + self.V * v
        return tuple(p - self.d * 0.6), tuple(self.d)

    @staticmethod
    def lamp(spec):
        (o, yaw, end) = spec
        s, c = math.sin(yaw), math.cos(yaw)
        if end == 'front':
            return Frame(o, (-s, 0, -c), (c, 0, -s), (0, 1, 0))
        return Frame(o, (-s, 0, c), (c, 0, s), (0, 1, 0))

    @staticmethod
    def side(x=2.0):
        """seen from the left: w = z (forward), v = y (rays start outside the car)"""
        return Frame((x, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))

    @staticmethod
    def top():
        """seen from above: w = x, v = z"""
        return Frame((0, 2.5, 0), (0, -1, 0), (1, 0, 0), (0, 0, 1))

    @staticmethod
    def rear():
        """seen from behind: w = x (left), v = y"""
        return Frame((0, 0, -3.0), (0, 0, 1), (1, 0, 0), (0, 1, 0))

    @staticmethod
    def front():
        return Frame((0, 0, 3.0), (0, 0, -1), (1, 0, 0), (0, 1, 0))


def _laid(surf, frame, w, v, lift):
    o, d = frame.ray(w, v)
    return surf.on(o, d, lift)


def patch(part, surf, frame, outline, mat, box=None, rings=5, lift=0.004, dome=0.0, centre=None):
    """a filled outline laid on the shell (concentric rings round `centre`); UVs over `box` (w0, w1, v0, v1)"""
    n = len(outline)
    cw = centre or (sum(p[0] for p in outline) / n, sum(p[1] for p in outline) / n)
    rows = []
    for k in range(rings + 1):
        t = k / rings
        row = []
        for w, v in outline:
            pw, pv = cw[0] + (w - cw[0]) * t, cw[1] + (v - cw[1]) * t
            row.append((pw, pv, lift + dome * (1 - t * t)))
        rows.append(row)
    pts = [[_laid(surf, frame, w, v, l) for w, v, l in row] for row in rows]

    def uv(w, v):
        if box is None:
            return (0.5, 0.5)
        return ((w - box[0]) / (box[1] - box[0]), (v - box[2]) / (box[3] - box[2]))

    for k in range(rings):
        for i in range(n):
            j = (i + 1) % n
            if k == 0:
                q = [(0, i), (1, i), (1, j)]
            else:
                q = [(k, i), (k + 1, i), (k + 1, j), (k, j)]
            ps = [pts[a][b] for a, b in q]
            if any(p is None for p in ps):
                continue
            uvs = [uv(rows[a][b][0], rows[a][b][1]) for a, b in q]
            if not frame.ccw_out:
                ps, uvs = ps[::-1], uvs[::-1]
            part.face(ps, mat, uvs=uvs)


def strip(part, surf, frame, poly, width, mat, lift=0.0015, closed=False):
    """a ribbon `width` wide along a polyline in the frame's plane, laid on the shell"""
    raw = list(poly) + ([poly[0]] if closed else [])
    pts = [raw[0]]
    for (w0, v0), (w1, v1) in zip(raw, raw[1:]):
        n = max(1, int(math.hypot(w1 - w0, v1 - v0) / 0.02))
        pts += [(w0 + (w1 - w0) * k / n, v0 + (v1 - v0) * k / n) for k in range(1, n + 1)]
    quads = []
    for i in range(len(pts) - 1):
        (w0, v0), (w1, v1) = pts[i], pts[i + 1]
        dw, dv = w1 - w0, v1 - v0
        L = math.hypot(dw, dv) or 1.0
        nw, nv = -dv / L * width / 2, dw / L * width / 2
        a0, a1 = _laid(surf, frame, w0 - nw, v0 - nv, lift), _laid(surf, frame, w1 - nw, v1 - nv, lift)
        b0, b1 = _laid(surf, frame, w0 + nw, v0 + nv, lift), _laid(surf, frame, w1 + nw, v1 + nv, lift)
        q = [a0, a1, b1, b0]
        if any(p is None for p in q):
            continue
        if not frame.ccw_out:
            q.reverse()
        part.face(q, mat)


def arc(cz, cy, r, a0, a1, n=12):
    return [(cz + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def rounded(w0, w1, v0, v1, r, seg=4):
    pts = []
    for cw, cv, a in ((w1 - r, v0 + r, -90), (w1 - r, v1 - r, 0), (w0 + r, v1 - r, 90), (w0 + r, v0 + r, 180)):
        for s in range(seg + 1):
            t = math.radians(a + 90 * s / seg)
            pts.append((cw + r * math.cos(t), cv + r * math.sin(t)))
    return pts


def mirror(part):
    """add the mirror image (x → −x) of everything in the part"""
    bm = part.bm
    faces = list(bm.faces)
    vmap = {}
    for f in faces:
        vs = []
        for v in f.verts:
            if v not in vmap:
                co = v.co.copy()
                co.x = -co.x
                vmap[v] = bm.verts.new(co)
            vs.append(vmap[v])
        uvs = [l[part.uv].uv.copy() for l in f.loops]
        try:
            nf = bm.faces.new(list(reversed(vs)))
        except ValueError:
            continue
        nf.material_index = f.material_index
        nf.smooth = f.smooth
        for l, uv in zip(nf.loops, reversed(uvs)):
            l[part.uv].uv = uv


# ---------------------------------------------------------------------------------------------------------------
def lamps(part, surf):
    """head lamps (lens, amber indicator cover), tail lamps (lens, clear strip): left side"""
    hf = Frame.lamp(D.HEAD_FRAME)
    k = D.HEAD_SCALE
    kv = D.HEAD_VSCALE
    out = D.scaled(D.closed_spline(D.HEAD_OUTLINE, 3), k, kv)
    b = D.HEAD_BOX
    box = (b[0] * k, b[1] * k, b[2] * k * kv, b[3] * k * kv)
    patch(part, surf, hf, out, 'headlight', box=box, rings=6, lift=0.004, dome=0.012, centre=(0.0, -0.02))
    # dark seam round the lens
    strip(part, surf, hf, out, 0.006, 'under', lift=0.002, closed=True)
    tf = Frame.lamp(D.TAIL_FRAME)
    k = D.TAIL_SCALE
    out = D.scaled(D.closed_spline(D.TAIL_OUTLINE, 3), k)
    box = tuple(b * k for b in D.TAIL_BOX)
    patch(part, surf, tf, out, 'taillight', box=box, rings=6, lift=0.004, dome=0.012, centre=(0.02, 0.02))
    strip(part, surf, tf, out, 0.006, 'under', lift=0.002, closed=True)


def _normal(rows, j, i):
    a = Vector(rows[j][min(i + 1, len(rows[j]) - 1)]) - Vector(rows[j][max(i - 1, 0)])
    b = Vector(rows[min(j + 1, len(rows) - 1)][i]) - Vector(rows[max(j - 1, 0)][i])
    n = a.cross(b)
    p = Vector(rows[j][i])
    if n.dot(Vector((p.x, p.y - 0.6, p.z))) < 0:
        n = -n
    return n.normalized()


def _edge_ribbon(part, rows, i, i_towards, width, mat, lift=0.0015):
    """a ribbon along shell column i (stations `rows`), `width` wide towards column i_towards"""
    a, b = [], []
    for j, row in enumerate(rows):
        p = Vector(row[i])
        d = (Vector(row[i_towards]) - p)
        d = d.normalized() * min(width, d.length)
        n = _normal(rows, j, i)
        a.append(tuple(p + n * lift))
        b.append(tuple(p + d + n * lift))
    for j in range(len(rows) - 1):
        q = [a[j], a[j + 1], b[j + 1], b[j]]
        nq = (Vector(q[1]) - Vector(q[0])).cross(Vector(q[3]) - Vector(q[0]))
        if nq.dot(_normal(rows, j, i)) < 0:
            q.reverse()
        part.face(q, mat)


def lips(part, rows):
    """the black lower lip round the front bumper and the diffuser lip under the rear one (left side)"""
    ib, il = sum(SH.SEGS[:SH.IDX['sill_b']]), sum(SH.SEGS[:SH.IDX['low']])
    up = Vector((0, 1, 0))
    for sub, extra in ((rows[-15:], 0.014), (rows[:15], -0.004)):
        profs = []
        pts = [Vector(r[ib]) for r in sub]
        for j, r in enumerate(sub):
            t = pts[min(j + 1, len(pts) - 1)] - pts[max(j - 1, 0)]
            n = Vector((t.z, 0, -t.x)).normalized()
            p = pts[j]
            if n.dot(Vector((p.x, 0, p.z))) < 0:
                n = -n
            delta = max(0.0, (Vector(r[il]) - p).dot(n))
            out = max(0.006, delta + extra)
            profs.append([tuple(p + up * 0.035), tuple(p + n * out + up * 0.012), tuple(p + n * (out + 0.004) - up * 0.004),
                          tuple(p - n * 0.03 - up * 0.008)])
        bm = bmesh.new()
        vs = [[bm.verts.new(K.B(*q)) for q in prof] for prof in profs]
        for j in range(len(vs) - 1):
            for k in range(4):
                bm.faces.new([vs[j][k], vs[j][(k + 1) % 4], vs[j + 1][(k + 1) % 4], vs[j + 1][k]])
        bm.faces.new(vs[0])
        bm.faces.new(vs[-1][::-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        part.merge(bm, 'trim', smooth=False)


def shut_lines(part, surf, rows=None):
    """panel gaps (left side): doors, bumpers, hood, trunk"""
    W = 0.0055
    side = Frame.side()
    R = SH.ARCH_R if hasattr(SH, 'ARCH_R') else None
    rear_arc = arc(SH.REAR_AXLE, 0.335, 0.415, 57, -9, 14)
    lines = [
        [(0.812, 0.268), (0.815, 0.70), (0.822, 0.885), (0.842, 0.935)],                 # front door, front edge
        [(-0.272, 0.268), (-0.280, 0.70), (-0.298, 0.985)],                             # between the doors
        [(-1.132, 0.995), (-1.118, 0.80), (-1.075, 0.715)] + rear_arc,                  # rear door, rear edge
        [(0.812, 0.268), (-0.272, 0.268), (rear_arc[-1][0], 0.268)],                    # door bottoms
        [(1.845, 0.618), (1.76, 0.565), (1.66, 0.52), (1.55, 0.50)],                    # front bumper / wing
        [(-2.075, 0.662), (-1.90, 0.645), (-1.74, 0.615), (-1.62, 0.58)],                # rear bumper / quarter
    ]
    for ln in lines:
        strip(part, surf, side, ln, W, 'under')
    top = Frame.top()
    # hood / wing: from the cowl along the wing's top to the lamp
    strip(part, surf, top, [(0.666, 0.955), (0.664, 1.30), (0.661, 1.60), (0.660, 1.70)], W, 'under')
    if rows is not None:
        # round the hood's leading edge: a ribbon from the shell's belt vertices 5.5 mm down the front face
        ib = sum(SH.SEGS[:SH.IDX['belt']])
        _edge_ribbon(part, rows[-15:], ib, ib - 1, W, 'under')
    # trunk lid sides
    strip(part, surf, top, [(0.676, -1.485), (0.676, -1.75), (0.676, -2.0), (0.676, -2.035)], W, 'under')
    rear = Frame.rear()
    # trunk lid: down its side, along the lamp's top, down the lamp's inner edge, across above the bumper
    strip(part, surf, rear, [(0.676, 1.000), (0.672, 0.962), (0.60, 0.958), (0.44, 0.958), (0.410, 0.940), (0.402, 0.86),
                             (0.400, 0.75), (0.398, 0.690), (0.37, 0.676), (0.0, 0.676)], W, 'under')
    # rear bumper's upper edge under the lamps
    strip(part, surf, rear, [(0.398, 0.690), (0.50, 0.672), (0.62, 0.671), (0.80, 0.680)], W, 'under')


def side_details(part, surf):
    """door handles, side marker (left side)"""
    side = Frame.side()
    for zc, yc in ((-0.035, 0.858), (-0.965, 0.885)):
        patch(part, surf, side, rounded(zc - 0.105, zc + 0.105, yc - 0.025, yc + 0.025, 0.022), 'under', rings=2, lift=0.0015)
        patch(part, surf, side, rounded(zc - 0.085, zc + 0.085, yc - 0.015, yc + 0.013, 0.012), 'paint', rings=2, lift=0.009,
              dome=0.003)
    # side marker on the wing behind the front wheel
    oval = [(0.90 + 0.036 * math.cos(math.radians(a)), 0.655 + 0.016 * math.sin(math.radians(a))) for a in range(0, 360, 30)]
    patch(part, surf, side, oval, 'indicator', rings=2, lift=0.004, dome=0.003)


def fuel_lid(part, surf):
    """the fuel lid on the right rear quarter (built on the left, mirrored by the caller)"""
    side = Frame.side()
    strip(part, surf, side, rounded(-1.585, -1.425, 0.812, 0.930, 0.022), 0.005, 'under', closed=True)


def grilles(part, surf):
    """honeycomb in the grille with its thin bar, the central intake's mesh and bar, the side intakes' fog lamps"""
    import raijin_cuts as CU
    z = 1.996
    part.face([(x, y, z) for x, y in CU.GRILLE], 'grille', uvs=[(x * 4, y * 4) for x, y in CU.GRILLE])
    part.box('paint', -0.272, 0.272, 0.621, 0.633, 1.997, 2.034, bevel=0.004, segments=1)
    z = 2.085
    part.face([(x, y, z) for x, y in CU.INTAKE], 'grille', uvs=[(x * 4, y * 4) for x, y in CU.INTAKE])
    part.box('trim', -0.42, 0.42, 0.352, 0.372, 2.086, 2.125, bevel=0.004, segments=1)
    # fog lamps in the side intakes (left; mirrored with the rest), a mesh behind them
    m = CU.fog_frame(1)
    c = m @ Vector((0.012, 0.0, 0.040))
    ax = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
    _disc(part, c, ax, 0.044, 0.030, 'chrome', 'lamp_clear')
    back = [tuple(m @ Vector((x, y, 0.032))) for x, y in CU.FOG]
    part.face(back, 'grille', uvs=[(p[0] * 4, p[1] * 4) for p in back])


def _disc(part, centre, axis, r, depth, rim_mat, lens_mat, seg=20):
    """a round lamp: a reflector cup (rim_mat) with a domed lens (lens_mat) facing along axis"""
    axis = Vector(axis).normalized()
    t = axis.orthogonal().normalized()
    b = axis.cross(t)
    ring = lambda rad, off: [tuple(Vector(centre) + axis * off + (t * math.cos(2 * math.pi * k / seg) + b * math.sin(2 * math.pi * k / seg)) * rad) for k in range(seg)]
    back, rim, lens = ring(r * 0.8, -depth), ring(r, 0.0), ring(r * 0.86, 0.004)
    tip = tuple(Vector(centre) + axis * 0.012)
    for k in range(seg):
        j = (k + 1) % seg
        part.face([back[k], back[j], rim[j], rim[k]], rim_mat)
        part.face([rim[k], rim[j], lens[j], lens[k]], rim_mat)
        part.face([lens[k], lens[j], tip], lens_mat)


def plates(part, surf, clean):
    """front plate on a mount in front of the central intake, rear plate on the bumper (a few mm proud)"""
    pw, ph = D.PLATE
    zs = [clean.hit((x, y, 4.0), (0, 0, -1)) for x in (-pw / 2, 0, pw / 2) for y in (0.37 - ph / 2, 0.37, 0.37 + ph / 2)]
    zf = max(h[0].z for h in zs if h) + 0.004
    q = [(pw / 2, 0.37 - ph / 2, zf), (-pw / 2, 0.37 - ph / 2, zf), (-pw / 2, 0.37 + ph / 2, zf), (pw / 2, 0.37 + ph / 2, zf)]
    # seen from the front, +x is on the right: counter-clockwise from the bottom left (−x)…
    part.face([q[1], q[0], q[3], q[2]], 'plate', uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    part.box('trim', -pw / 2 - 0.006, pw / 2 + 0.006, 0.37 - ph / 2 - 0.006, 0.37 + ph / 2 + 0.006, zf - 0.016, zf - 0.002)
    part.box('trim', -0.12, 0.12, 0.33, 0.41, 2.084, zf - 0.015)
    yr = 0.475
    zs = [surf.hit((x, y, -4.0), (0, 0, 1)) for x in (-pw / 2, 0, pw / 2) for y in (yr - ph / 2, yr, yr + ph / 2)]
    zr = min(h[0].z for h in zs if h) - 0.006
    q = [(pw / 2, yr - ph / 2, zr), (-pw / 2, yr - ph / 2, zr), (-pw / 2, yr + ph / 2, zr), (pw / 2, yr + ph / 2, zr)]
    # seen from behind, +x is on the left
    part.face([q[0], q[1], q[2], q[3]], 'plate', uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    part.box('trim', -pw / 2 - 0.006, pw / 2 + 0.006, yr - ph / 2 - 0.006, yr + ph / 2 + 0.006, zr + 0.002, zr + 0.03)


def exhaust(part):
    """the single big round tip under the left of the rear bumper"""
    c = (0.455, 0.272, -2.20)
    part.cylinder('chrome', c, 0.052, 0.20, axis='z', segments=24, cap=False)
    # the inside of the tip, seen from behind, and a dark plug further in
    part.cylinder('under', (c[0], c[1], c[2] + 0.005), 0.046, 0.19, axis='z', segments=24, cap=False, flip=True)
    part.cylinder('under', (c[0], c[1], c[2] + 0.07), 0.047, 0.004, axis='z', segments=16, cap=True)
    # a roll at the tip's mouth
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.052, radius2=0.044, depth=0.004)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(K.B(c[0], c[1], c[2] - 0.102)) @ Matrix.Rotation(math.pi / 2, 4, 'X'),
                        verts=bm.verts)
    part.merge(bm, 'chrome', smooth=True)


# ---------------------------------------------------------------------------------------------------------------
def _deck(surf, x, z):
    h = surf.hit((x, 3.0, z), (0, -1, 0))
    return h[0].y if h else 1.0


def _extrude_x(part, mat, poly, x0, x1, bevel=0.0):
    """a polygon in the (z, y) plane, counter-clockwise seen from +x, extruded from x0 to x1"""
    bm = bmesh.new()
    a = [bm.verts.new(K.B(x0, y, z)) for z, y in poly]
    b = [bm.verts.new(K.B(x1, y, z)) for z, y in poly]
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([a[i], a[j], b[j], b[i]])
    bm.faces.new(b)
    bm.faces.new(list(reversed(a)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2, profile=0.5, affect='EDGES', clamp_overlap=True)
    part.merge(bm, mat, smooth=True)


def _loft_x(part, mat, sections, closed=True, smooth=True):
    """sections [(x, [(z, y) ...])] with the same point count, lofted along x; ends capped"""
    rows = [[(x, y, z) for z, y in sec] for x, sec in sections]
    part.grid(rows, mat, closed_u=closed, smooth=smooth)
    if closed:
        for k, flip in ((0, False), (-1, True)):
            pts = rows[k]
            part.face(pts[::-1] if flip else pts, mat, smooth=False)


def wing(part, surf):
    """the STI's big rear wing: two broad swept uprights standing on the trunk lid's edges, the blade at about roof
    height between them; a small lip along the lid's rear edge (left half + mirror)"""
    x0, x1 = 0.572, 0.628
    xm = (x0 + x1) / 2
    db = lambda z: _deck(surf, xm, z)
    # upright: long foot on the lid, the front edge sweeping up and back, the top under the blade, a near-vertical rear
    poly = [(-1.955, db(-1.95) - 0.012), (-1.500, db(-1.50) - 0.012), (-1.515, db(-1.50) + 0.012),
            (-1.560, db(-1.56) + 0.040), (-1.620, db(-1.62) + 0.085), (-1.680, 1.215), (-1.730, 1.262),
            (-1.780, 1.284), (-1.980, 1.296), (-2.020, 1.282), (-2.030, 1.230), (-1.975, db(-1.95) + 0.045)]
    _extrude_x(part, 'paint', poly, x0, x1, bevel=0.012)
    # blade: a cambered airfoil, leading edge (front, low) → trailing edge (rear, high), from the middle to the uprights'
    # outer faces
    le, te = (-1.735, 1.268), (-2.035, 1.318)
    upper, lower = [], []
    for k in range(13):
        t = (1 - math.cos(math.pi * k / 12)) / 2
        z = le[0] + (te[0] - le[0]) * t
        y = le[1] + (te[1] - le[1]) * t + 0.016 * math.sin(math.pi * t)      # camber
        th = 0.050 * (1.4845 * math.sqrt(t) - 0.63 * t - 1.758 * t * t + 1.4215 * t ** 3 - 0.5075 * t ** 4) / 0.6 + 0.002
        upper.append((z, y + th * 0.6))
        lower.append((z, y - th * 0.4))
    sec = list(reversed(lower[1:])) + upper     # trailing edge (lower) → leading edge → trailing edge (upper)
    sec = list(reversed(sec))
    _loft_x(part, 'paint', [(x, sec) for x in (0.0, 0.25, 0.48, x1 + 0.002)], closed=False)
    end = [(x1 + 0.002, y, z) for z, y in sec]
    part.face(end[::-1], 'paint', smooth=False)
    # lip along the lid's rear edge
    secs = []
    for x in (0.0, 0.15, 0.30, 0.42, 0.50, 0.56):
        ze = -2.040 + 0.06 * (x / 0.6) ** 4          # the lid's rear edge rounds forward towards the corners
        zf = ze + 0.16
        d0, d1 = _deck(surf, x, zf), _deck(surf, x, ze)
        r = [(ze - 0.008, d1 - 0.010), (zf, d0 - 0.006), (zf - 0.01, d0 + 0.002), (ze + 0.004, d1 + 0.020),
             (ze - 0.008, d1 + 0.016)]
        secs.append((x, r))
    _loft_x(part, 'paint', secs, closed=False)
    part.face([(0.56, y, z) for z, y in secs[-1][1]], 'paint', smooth=False)
    # high-mount stop lamp in the lip's rear face
    d = _deck(surf, 0.0, -2.040)
    part.face([(0.14, d + 0.000, -2.0485), (0.0, d + 0.000, -2.0485), (0.0, d + 0.012, -2.0485), (0.14, d + 0.012, -2.0485)],
              'lamp_clear')


def door_mirror(part, surf):
    """the door mirror: a body-coloured housing (squarish, flat back with the glass) on a short black arm from the black
    triangular sail in the front corner of the door glass (left side)"""
    side = Frame.side()
    # the sail: a black triangle laid on the glass's front corner
    patch(part, surf, side, [(0.858, 0.936), (0.600, 0.944), (0.640, 0.968), (0.760, 1.008)], 'trim', rings=2,
          lift=0.006)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
    c = Vector((0.940, 0.990, 0.560))
    hx, hy, hz = 0.122, 0.064, 0.095
    for v in bm.verts:
        x, y, z = v.co.x, v.co.z, -v.co.y      # Blender sphere → game axes
        # a superellipsoid: boxier than a sphere
        sx = math.copysign(abs(x) ** 0.7, x)
        sy = math.copysign(abs(y) ** 0.7, y)
        sz = math.copysign(abs(z) ** 0.8, z)
        gx, gy, gz = sx * hx, sy * hy, sz * hz
        gz = max(gz, -0.052)                      # flat back for the glass
        gz += 0.018 * (gx / hx + 1) * 0.5 * (gz < 0)   # the outer end sweeps back a little less
        gy -= 0.012 * (gx / hx)                   # the outer end drops slightly
        v.co = K.B(c.x + gx, c.y + gy, c.z + gz)
    part.merge(bm, 'paint', smooth=True)
    # glass on the flat back
    gl = [(c.x + 0.100 * math.copysign(abs(math.cos(math.radians(a))) ** 0.7, math.cos(math.radians(a))),
           c.y + 0.056 * math.copysign(abs(math.sin(math.radians(a))) ** 0.7, math.sin(math.radians(a))))
          for a in range(0, 360, 20)]
    pts = [(x, y - 0.012 * ((x - c.x) / hx), c.z - 0.0525) for x, y in gl]
    part.face(pts[::-1], 'chrome')
    # the arm from the sail
    part.beam('trim', (0.785, 0.972, 0.730), (0.860, 0.982, 0.610), 0.046, 0.040)


def hood_scoop(part, surf):
    """the STI's bonnet scoop: lofted along z on the hood, open at the front (dark slot)"""
    z_rear, z_front = 1.02, 1.52
    nz = 10
    rows = []
    for k in range(nz + 1):
        t = k / nz
        z = z_rear + (z_front - z_rear) * t
        hw = 0.255 + 0.060 * t
        h = 0.060 * min(1.0, (t / 0.6)) ** 0.9 + 0.004
        base_c = _deck(surf, 0.0, z)
        top = max(base_c + h, base_c + 0.004)
        sec = []
        r = min(0.03, h * 0.6 + 0.004)
        sec.append((hw + 0.01, _deck(surf, hw + 0.01, z) - 0.01))
        sec.append((hw, _deck(surf, hw, z) + 0.004))
        for a in range(0, 91, 30):
            ang = math.radians(a)
            sec.append((hw - r + r * math.cos(ang), top - r + r * math.sin(ang)))
        sec.append((0.0, top + 0.004))
        full = sec + [(-x, y) for x, y in reversed(sec[:-1])]
        rows.append([(x, y, z) for x, y in full])
    part.grid(rows, 'paint', flip=True)
    # front: a frame round the slot, the slot recessed and dark
    front = rows[-1]
    inner = []
    cx = 0.0
    cy = sum(p[1] for p in front) / len(front)
    for x, y, z in front:
        inner.append((x * 0.86, cy + (y - cy) * 0.55 + 0.004, z))
    back = [(x, y, z - 0.07) for x, y, z in inner]
    n = len(front)
    for i in range(n - 1):
        part.face([front[i], front[i + 1], inner[i + 1], inner[i]][::-1], 'paint')
        part.face([inner[i], inner[i + 1], back[i + 1], back[i]][::-1], 'under')
    part.face(back, 'under')


def wipers(part, surf):
    """two black wiper arms with blades resting on the screen's lower edge (right-hand drive)"""
    for x0, x1, zoff in ((-0.62, -0.03, 0.05), (-0.02, 0.50, 0.035)):
        pts = []
        for k in range(7):
            x = x0 + (x1 - x0) * k / 6
            h = surf.hit((x, 3.0, 0.80 - zoff * 0.3), (0, -1, 0))
            pts.append(Vector((x, h[0].y + 0.012, 0.80 - zoff * 0.3)) if h else None)
        pts = [p for p in pts if p]
        for a, b in zip(pts, pts[1:]):
            part.beam('trim', tuple(a), tuple(b), 0.012, 0.016, up=(0, 1, 0.4))
        # the arm: from the pivot on the cowl up to the blade's middle
        piv = Vector((x1 - 0.02, 0.0, 0.905))
        h = surf.hit((piv.x, 3.0, piv.z), (0, -1, 0))
        if h:
            piv.y = h[0].y + 0.02
            mid = pts[len(pts) // 2] + Vector((0, 0.012, 0))
            part.beam('trim', tuple(piv), tuple(mid), 0.014, 0.012, up=(0, 1, 0.3))
            part.cylinder('trim', tuple(piv), 0.018, 0.02, axis='y', segments=10)


def nozzles(part, surf):
    for x in (0.30,):
        h = surf.hit((x, 3.0, 1.02), (0, -1, 0))
        if h:
            p = h[0]
            part.box('trim', x - 0.012, x + 0.012, p.y - 0.004, p.y + 0.012, 1.005, 1.035, bevel=0.005)


def arch_lips(part, surf):
    """the wide wings' rolled lips round the wheel openings (left side)"""
    import raijin_cuts as CU
    for key, zc in (('front', SH.FRONT_AXLE), ('rear', SH.REAR_AXLE)):
        R = CU.ARCH_R[key]
        yc = CU.ARCH_Y
        rows = []
        a0 = math.degrees(math.asin((0.215 - yc) / R))
        n = 26
        for k in range(n + 1):
            a = math.radians(a0 + (180 - 2 * a0) * k / n)
            ca, sa = math.cos(a), math.sin(a)
            ring = []
            for dr, dx in ((0.050, -0.002), (0.022, 0.006), (0.008, 0.010), (0.0, 0.004), (0.0, -0.012)):
                rr = R + dr
                z, y = zc + rr * ca, yc + rr * sa
                h = surf.hit((2.0, y, z), (-1, 0, 0))
                if h is None:
                    ring = None
                    break
                ring.append((h[0].x + dx, y, z))
            if ring:
                rows.append(ring)
        part.grid(rows, 'paint')


def _torus(part, mat, centre, axis, R, r, seg=28, rseg=8):
    axis = Vector(axis).normalized()
    t = axis.orthogonal().normalized()
    b = axis.cross(t)
    rows = []
    for i in range(seg + 1):
        a = 2 * math.pi * i / seg
        radial = t * math.cos(a) + b * math.sin(a)
        c = Vector(centre) + radial * R
        rows.append([tuple(c + (radial * math.cos(2 * math.pi * j / rseg) + axis * math.sin(2 * math.pi * j / rseg)) * r)
                     for j in range(rseg + 1)])
    part.grid(rows, mat, flip=True)


def interior(part):
    """a basic cabin seen through the glass: tub (inward faces), dash, steering wheel (right-hand drive), seats"""
    M = 'interior'
    zf, zr = 0.86, -1.12
    # floor, door cards, headliner, parcel shelf, the back of the cabin (faces point into the cabin)
    part.face([(-0.72, 0.30, zr), (0.72, 0.30, zr), (0.72, 0.30, zf), (-0.72, 0.30, zf)][::-1], M, smooth=False)
    for s in (1, -1):
        x = s * 0.745
        q = [(x, 0.30, zr), (x, 0.30, zf), (x, 0.955, zf), (x, 0.955, zr)]
        part.face(q if s > 0 else q[::-1], M, smooth=False)
        # arm rest strip on the door card
        xi = s * 0.745 - s * 0.05
        part.box(M, min(x, xi), max(x, xi), 0.62, 0.66, -0.95, 0.65)
    part.face([(-0.48, 1.33, -0.92), (-0.48, 1.33, -0.14), (0.48, 1.33, -0.14), (0.48, 1.33, -0.92)][::-1], M, smooth=False)
    part.face([(-0.70, 1.0, -1.48), (-0.70, 1.0, zr), (0.70, 1.0, zr), (0.70, 1.0, -1.48)], M, smooth=False)
    part.face([(-0.72, 0.30, zr), (-0.72, 1.0, zr), (0.72, 1.0, zr), (0.72, 0.30, zr)][::-1], M, smooth=False)
    # dash: a block with a sloped top and the binnacle in front of the driver
    part.box(M, -0.72, 0.72, 0.55, 0.86, 0.50, zf, bevel=0.03)
    part.box(M, -0.72, 0.72, 0.80, 0.93, 0.62, zf, bevel=0.04)
    part.box(M, -0.55, -0.18, 0.86, 0.98, 0.50, 0.66, bevel=0.03)
    part.box(M, -0.10, 0.10, 0.32, 0.72, 0.20, 0.62, bevel=0.03)          # centre console
    # steering wheel (driver on the right, −x)
    _torus(part, 'trim', (-0.37, 0.93, 0.36), (0, 0.42, 1), 0.185, 0.016)
    part.beam('trim', (-0.37, 0.93, 0.36), (-0.37, 0.86, 0.52), 0.06, 0.06)
    for a in (0, 2.1, 4.2):
        p = Vector((-0.37 + 0.17 * math.cos(a + 1.57), 0.93 + 0.17 * math.sin(a + 1.57) * 0.92, 0.36 - 0.07 * math.sin(a + 1.57)))
        part.beam('trim', (-0.37, 0.93, 0.36), tuple(p), 0.03, 0.012)
    # front bucket seats
    for xc in (-0.37, 0.37):
        part.box(M, xc - 0.25, xc + 0.25, 0.34, 0.52, -0.22, 0.30, bevel=0.05)
        m = Matrix.Translation((xc, 0.48, -0.28)) @ Matrix.Rotation(math.radians(-14), 4, 'X')
        part.box(M, -0.25, 0.25, 0.0, 0.66, -0.06, 0.08, bevel=0.05, matrix=m)
        for s in (-1, 1):   # side bolsters
            part.box(M, s * 0.22 - 0.05, s * 0.22 + 0.05, 0.05, 0.55, -0.02, 0.14, bevel=0.03, matrix=m)
        part.box(M, -0.13, 0.13, 0.70, 0.88, -0.04, 0.06, bevel=0.03, matrix=m)
    # rear bench
    part.box(M, -0.68, 0.68, 0.34, 0.52, -0.98, -0.48, bevel=0.05)
    m = Matrix.Translation((0, 0.50, -1.02)) @ Matrix.Rotation(math.radians(-22), 4, 'X')
    part.box(M, -0.68, 0.68, 0.0, 0.56, -0.05, 0.10, bevel=0.05, matrix=m)
